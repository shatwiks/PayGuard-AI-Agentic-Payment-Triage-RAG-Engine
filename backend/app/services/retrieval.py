"""Hybrid RAG Retrieval Engine combining PostgreSQL Full-Text Search and pgvector semantic search."""

import logging
from typing import Dict, List, Optional, Tuple
import uuid
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.models.knowledge import DocumentChunk, KnowledgeDocument
from backend.app.schemas.investigation import PolicyCitation
from backend.app.schemas.knowledge import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    RankingDetails,
    SearchResultItem,
)
from backend.app.services.embedding import (
    EmbeddingProviderUnavailableException,
    IEmbeddingProvider,
    get_embedding_provider,
)

logger = logging.getLogger("payguard.retrieval")


class HybridRetrievalService:
    """Combines PostgreSQL Full-Text Search (lexical) and pgvector cosine similarity (semantic) via RRF."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: Optional[IEmbeddingProvider] = None,
        rrf_k: Optional[int] = None,
        lexical_weight: Optional[float] = None,
        semantic_weight: Optional[float] = None,
    ):
        self.session = session
        self.provider = embedding_provider or get_embedding_provider()
        self.rrf_k = rrf_k or settings.RETRIEVAL_HYBRID_RRF_K
        self.lexical_weight = lexical_weight or settings.RETRIEVAL_LEXICAL_WEIGHT
        self.semantic_weight = semantic_weight or settings.RETRIEVAL_SEMANTIC_WEIGHT

    def _is_postgresql(self) -> bool:
        """Determines if the active session is connected to a PostgreSQL database."""
        bind = self.session.bind
        return bool(bind and bind.dialect.name == "postgresql")

    async def lexical_search(
        self,
        query: str,
        top_k: int = 10,
        doc_type: Optional[str] = None,
    ) -> List[Tuple[DocumentChunk, int, float]]:
        """Executes lexical search returning (chunk, rank, score). Uses PostgreSQL tsvector if available."""
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        results: List[Tuple[DocumentChunk, int, float]] = []

        if self._is_postgresql():
            # Native PostgreSQL Full-Text Search over generated tsvector column
            stmt = (
                select(
                    DocumentChunk,
                    func.ts_rank_cd(DocumentChunk.tsv, func.plainto_tsquery("english", cleaned_query)).label("score"),
                )
                .join(DocumentChunk.document)
                .where(
                    KnowledgeDocument.is_active == True,  # noqa: E712
                    DocumentChunk.tsv.op("@@")(func.plainto_tsquery("english", cleaned_query)),
                )
                .options(selectinload(DocumentChunk.document))
            )
            if doc_type:
                stmt = stmt.where(KnowledgeDocument.doc_type == doc_type)

            stmt = stmt.order_by(func.ts_rank_cd(DocumentChunk.tsv, func.plainto_tsquery("english", cleaned_query)).desc())
            stmt = stmt.limit(top_k)

            res = await self.session.execute(stmt)
            rows = res.all()
            for rank_idx, (chunk, score) in enumerate(rows, start=1):
                results.append((chunk, rank_idx, float(score or 0.0)))
        else:
            # Fallback for SQLite in-memory unit tests: word token match
            terms = [w.lower() for w in cleaned_query.split() if len(w) > 1]
            if not terms:
                return []

            or_conditions = []
            for t in terms:
                or_conditions.append(DocumentChunk.content.ilike(f"%{t}%"))
                or_conditions.append(DocumentChunk.section_header.ilike(f"%{t}%"))

            stmt = (
                select(DocumentChunk)
                .join(DocumentChunk.document)
                .where(
                    KnowledgeDocument.is_active == True,  # noqa: E712
                    or_(*or_conditions),
                )
                .options(selectinload(DocumentChunk.document))
            )
            if doc_type:
                stmt = stmt.where(KnowledgeDocument.doc_type == doc_type)

            stmt = stmt.limit(top_k)
            res = await self.session.execute(stmt)
            chunks = res.scalars().all()

            for rank_idx, chunk in enumerate(chunks, start=1):
                # Basic token overlap heuristic score
                matches = sum(1 for t in terms if t in chunk.content.lower() or t in chunk.section_header.lower())
                score = matches / len(terms)
                results.append((chunk, rank_idx, score))

        return results

    async def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        doc_type: Optional[str] = None,
        min_similarity: Optional[float] = None,
    ) -> List[Tuple[DocumentChunk, int, float, float]]:
        """Executes pgvector semantic search returning (chunk, rank, distance, similarity)."""
        if not self.provider.is_available:
            return []

        query_vector = await self.provider.embed_query(query)
        target_model = self.provider.model_name

        results: List[Tuple[DocumentChunk, int, float, float]] = []

        if self._is_postgresql():
            # PostgreSQL pgvector native cosine distance (<=>)
            distance_expr = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
            stmt = (
                select(DocumentChunk, distance_expr)
                .join(DocumentChunk.document)
                .where(
                    KnowledgeDocument.is_active == True,  # noqa: E712
                    DocumentChunk.embedding_model == target_model,
                    DocumentChunk.embedding.isnot(None),
                )
                .options(selectinload(DocumentChunk.document))
            )
            if doc_type:
                stmt = stmt.where(KnowledgeDocument.doc_type == doc_type)

            stmt = stmt.order_by(distance_expr.asc()).limit(top_k)
            res = await self.session.execute(stmt)
            rows = res.all()

            for rank_idx, (chunk, distance) in enumerate(rows, start=1):
                dist_val = float(distance or 0.0)
                similarity = max(0.0, min(1.0, 1.0 - dist_val))
                if min_similarity is None or similarity >= min_similarity:
                    results.append((chunk, rank_idx, dist_val, similarity))
        else:
            # Fallback for SQLite unit tests
            stmt = (
                select(DocumentChunk)
                .join(DocumentChunk.document)
                .where(
                    KnowledgeDocument.is_active == True,  # noqa: E712
                    DocumentChunk.embedding.isnot(None),
                )
                .options(selectinload(DocumentChunk.document))
                .limit(top_k)
            )
            if doc_type:
                stmt = stmt.where(KnowledgeDocument.doc_type == doc_type)

            res = await self.session.execute(stmt)
            chunks = res.scalars().all()
            for rank_idx, chunk in enumerate(chunks, start=1):
                # Placeholder distance 0.1 for SQLite mock tests
                results.append((chunk, rank_idx, 0.10, 0.90))

        return results

    async def search(self, request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
        """Executes hybrid, lexical-only, or semantic-only retrieval with Reciprocal Rank Fusion."""
        requested_mode = request.retrieval_mode
        candidate_map: Dict[uuid.UUID, Dict] = {}

        # 1. Lexical retrieval
        lexical_items = []
        if requested_mode in ("hybrid", "lexical_only"):
            lexical_items = await self.lexical_search(
                query=request.query,
                top_k=request.top_k * 3,
                doc_type=request.doc_type,
            )
            for chunk, rank, score in lexical_items:
                candidate_map[chunk.id] = {
                    "chunk": chunk,
                    "lexical_rank": rank,
                    "lexical_score": score,
                    "semantic_rank": None,
                    "semantic_distance": None,
                    "semantic_similarity": None,
                }

        # 2. Semantic retrieval
        semantic_items = []
        semantic_available = self.provider.is_available

        if requested_mode == "semantic_only" and not semantic_available:
            raise EmbeddingProviderUnavailableException(
                "Semantic-only retrieval requested, but embedding provider is not configured or unavailable"
            )

        if requested_mode in ("hybrid", "semantic_only") and semantic_available:
            try:
                semantic_items = await self.semantic_search(
                    query=request.query,
                    top_k=request.top_k * 3,
                    doc_type=request.doc_type,
                )
                for chunk, rank, dist, sim in semantic_items:
                    if chunk.id in candidate_map:
                        candidate_map[chunk.id]["semantic_rank"] = rank
                        candidate_map[chunk.id]["semantic_distance"] = dist
                        candidate_map[chunk.id]["semantic_similarity"] = sim
                    else:
                        candidate_map[chunk.id] = {
                            "chunk": chunk,
                            "lexical_rank": None,
                            "lexical_score": None,
                            "semantic_rank": rank,
                            "semantic_distance": dist,
                            "semantic_similarity": sim,
                        }
            except Exception as e:
                logger.warning(f"Semantic search encountered an error: {e}")
                if requested_mode == "semantic_only":
                    raise

        # Determine effective active retrieval mode
        if requested_mode == "hybrid" and not semantic_available:
            effective_mode = "lexical_only"
        elif requested_mode == "semantic_only":
            effective_mode = "semantic_only"
        elif requested_mode == "lexical_only":
            effective_mode = "lexical_only"
        else:
            effective_mode = "hybrid" if semantic_items and lexical_items else ("semantic_only" if semantic_items else "lexical_only")

        # 3. Reciprocal Rank Fusion (RRF) calculation
        scored_candidates: List[SearchResultItem] = []

        for cid, data in candidate_map.items():
            chunk: DocumentChunk = data["chunk"]
            signals = []
            fusion_score = 0.0

            if data["lexical_rank"] is not None:
                signals.append("lexical")
                fusion_score += self.lexical_weight / (self.rrf_k + data["lexical_rank"])

            if data["semantic_rank"] is not None:
                signals.append("semantic")
                fusion_score += self.semantic_weight / (self.rrf_k + data["semantic_rank"])

            # Filter by min_score if requested
            if request.min_score is not None and fusion_score < request.min_score:
                continue

            ranking_info = RankingDetails(
                lexical_rank=data["lexical_rank"],
                lexical_score=data["lexical_score"],
                semantic_rank=data["semantic_rank"],
                semantic_distance=data["semantic_distance"],
                semantic_similarity=data["semantic_similarity"],
                fusion_score=round(fusion_score, 6),
                signals_used=signals,
            )

            scored_candidates.append(
                SearchResultItem(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    title=chunk.document.title if chunk.document else "Unknown Document",
                    source_id=chunk.document.source_id if chunk.document else None,
                    source_url=chunk.document.source_url if chunk.document else None,
                    doc_type=chunk.document.doc_type if chunk.document else "policy",
                    chunk_index=chunk.chunk_index,
                    section_header=chunk.section_header,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    embedding_model=chunk.embedding_model,
                    ranking=ranking_info,
                )
            )

        # 4. Sort descending by fusion score and take top_k
        scored_candidates.sort(key=lambda x: x.ranking.fusion_score, reverse=True)
        top_results = scored_candidates[: request.top_k]

        return KnowledgeSearchResponse(
            query=request.query,
            retrieval_mode=effective_mode,
            total_candidates=len(candidate_map),
            results_count=len(top_results),
            results=top_results,
        )

    def to_citations(self, results: List[SearchResultItem]) -> List[PolicyCitation]:
        """Maps search result passages to grounded policy citations for triage reasoning."""
        citations = []
        for r in results:
            citations.append(
                PolicyCitation(
                    document_title=r.title,
                    section_header=r.section_header,
                    excerpt=r.content[:350] + "..." if len(r.content) > 350 else r.content,
                    confidence_score=min(1.0, round(r.ranking.fusion_score * 30, 2)),
                    source_id=r.source_id,
                    source_url=r.source_url,
                    document_id=r.document_id,
                    chunk_id=r.chunk_id,
                    is_synthetic_demonstration=True,
                )
            )
        return citations
