"""Hybrid RAG Retrieval Engine combining PostgreSQL Full-Text Search and pgvector semantic search."""

import logging
import math
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Union
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


class LexicalSearchResult(NamedTuple):
    chunk: DocumentChunk
    rank: int
    score: float

    @property
    def chunk_id(self) -> str:
        return str(self.chunk.id)

    @property
    def text(self) -> str:
        return self.chunk.content

    @property
    def title(self) -> str:
        return self.chunk.document.title if self.chunk.document else ""


class SemanticSearchResult(NamedTuple):
    chunk: DocumentChunk
    rank: int
    distance: float
    similarity: float

    @property
    def chunk_id(self) -> str:
        return str(self.chunk.id)

    @property
    def text(self) -> str:
        return self.chunk.content

    @property
    def embedding_model(self) -> Optional[str]:
        return self.chunk.embedding_model

    @property
    def semantic_score(self) -> float:
        return self.similarity


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
        query: str = "",
        query_text: Optional[str] = None,
        top_k: int = 10,
        limit: Optional[int] = None,
        doc_type: Optional[str] = None,
        source_type: Optional[str] = None,
        scheme: Optional[str] = None,
        condition_code: Optional[str] = None,
    ) -> List[LexicalSearchResult]:
        """Executes lexical search returning (chunk, rank, score). Uses PostgreSQL tsvector if available."""
        search_query = (query_text or query).strip()
        eff_limit = limit or top_k
        eff_doc_type = doc_type or source_type
        if not search_query:
            return []

        results: List[LexicalSearchResult] = []

        if self._is_postgresql():
            import re
            raw_terms = [w.strip() for w in re.findall(r"\b[A-Za-z0-9_.-]{2,}\b", search_query) if w.isalnum()]
            or_tsquery = " | ".join(raw_terms) if raw_terms else None

            exact_q = func.plainto_tsquery("english", search_query)

            if or_tsquery:
                or_q = func.to_tsquery("english", or_tsquery)
                match_condition = or_(DocumentChunk.tsv.op("@@")(exact_q), DocumentChunk.tsv.op("@@")(or_q))
                score_expr = (func.ts_rank_cd(DocumentChunk.tsv, exact_q) * 2.0 + func.ts_rank_cd(DocumentChunk.tsv, or_q)).label("score")
            else:
                match_condition = DocumentChunk.tsv.op("@@")(exact_q)
                score_expr = func.ts_rank_cd(DocumentChunk.tsv, exact_q).label("score")

            stmt = (
                select(DocumentChunk, score_expr)
                .join(DocumentChunk.document)
                .where(
                    KnowledgeDocument.is_active == True,  # noqa: E712
                    match_condition,
                    or_(DocumentChunk.chunk_type != "parent", DocumentChunk.chunk_type.is_(None)),
                )
                .options(selectinload(DocumentChunk.document))
            )
            if eff_doc_type:
                stmt = stmt.where(KnowledgeDocument.doc_type == eff_doc_type)

            if scheme:
                stmt = stmt.where(
                    or_(
                        DocumentChunk.metadata_["scheme"].as_string() == scheme,
                        DocumentChunk.content.ilike(f"%{scheme}%"),
                    )
                )

            if condition_code:
                stmt = stmt.where(
                    or_(
                        DocumentChunk.metadata_["condition_code"].as_string() == condition_code,
                        DocumentChunk.content.ilike(f"%{condition_code}%"),
                    )
                )

            stmt = stmt.order_by(score_expr.desc())
            stmt = stmt.limit(eff_limit)

            res = await self.session.execute(stmt)
            rows = res.all()
            for rank_idx, (chunk, score) in enumerate(rows, start=1):
                results.append(LexicalSearchResult(chunk, rank_idx, float(score or 0.0)))
        else:
            # Fallback for SQLite in-memory unit tests: word token match
            terms = [w.lower() for w in search_query.split() if len(w) >= 1]
            if not terms:
                return []

            or_conditions = [
                DocumentChunk.content.ilike(f"%{search_query}%"),
                DocumentChunk.section_header.ilike(f"%{search_query}%"),
            ]
            for t in terms:
                or_conditions.append(DocumentChunk.content.ilike(f"%{t}%"))
                or_conditions.append(DocumentChunk.section_header.ilike(f"%{t}%"))

            stmt = (
                select(DocumentChunk)
                .join(DocumentChunk.document)
                .where(
                    KnowledgeDocument.is_active == True,  # noqa: E712
                    or_(*or_conditions),
                    or_(DocumentChunk.chunk_type != "parent", DocumentChunk.chunk_type.is_(None)),
                )
                .options(selectinload(DocumentChunk.document))
            )
            if eff_doc_type:
                stmt = stmt.where(KnowledgeDocument.doc_type == eff_doc_type)

            if scheme:
                stmt = stmt.where(DocumentChunk.content.ilike(f"%{scheme}%"))

            if condition_code:
                stmt = stmt.where(DocumentChunk.content.ilike(f"%{condition_code}%"))

            stmt = stmt.limit(eff_limit * 2)
            res = await self.session.execute(stmt)
            chunks = res.scalars().all()

            scored = []
            for chunk in chunks:
                matches = sum(1 for t in terms if t in chunk.content.lower() or t in chunk.section_header.lower())
                exact_boost = 1.0 if search_query.lower() in chunk.content.lower() else 0.0
                score = (matches / len(terms)) + exact_boost
                scored.append((chunk, score))

            scored.sort(key=lambda x: x[1], reverse=True)
            for rank_idx, (chunk, score) in enumerate(scored[:eff_limit], start=1):
                results.append(LexicalSearchResult(chunk, rank_idx, score))

        return results

    async def semantic_search(
        self,
        query: str = "",
        query_vector: Optional[List[float]] = None,
        top_k: int = 10,
        limit: Optional[int] = None,
        doc_type: Optional[str] = None,
        source_type: Optional[str] = None,
        scheme: Optional[str] = None,
        condition_code: Optional[str] = None,
        min_similarity: Optional[float] = None,
    ) -> List[SemanticSearchResult]:
        """Executes pgvector semantic search returning (chunk, rank, distance, similarity)."""
        eff_limit = limit or top_k
        eff_doc_type = doc_type or source_type
        target_model = self.provider.model_name

        if target_model == "synthetic_placeholder":
            logger.warning("Semantic search requested with synthetic_placeholder model; rejecting to prevent synthetic matching.")
            return []

        if query_vector is None:
            if not self.provider.is_available:
                return []
            query_vector = await self.provider.embed_query(query)

        results: List[SemanticSearchResult] = []

        if self._is_postgresql():
            # PostgreSQL pgvector native cosine distance (<=>)
            distance_expr = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
            stmt = (
                select(DocumentChunk, distance_expr)
                .join(DocumentChunk.document)
                .where(
                    KnowledgeDocument.is_active == True,  # noqa: E712
                    DocumentChunk.embedding_model == target_model,
                    DocumentChunk.embedding_model != "synthetic_placeholder",
                    DocumentChunk.embedding.isnot(None),
                    or_(DocumentChunk.chunk_type != "parent", DocumentChunk.chunk_type.is_(None)),
                )
                .options(selectinload(DocumentChunk.document))
            )
            if eff_doc_type:
                stmt = stmt.where(KnowledgeDocument.doc_type == eff_doc_type)

            if scheme:
                stmt = stmt.where(
                    or_(
                        DocumentChunk.metadata_["scheme"].as_string() == scheme,
                        DocumentChunk.content.ilike(f"%{scheme}%"),
                    )
                )

            if condition_code:
                stmt = stmt.where(
                    or_(
                        DocumentChunk.metadata_["condition_code"].as_string() == condition_code,
                        DocumentChunk.content.ilike(f"%{condition_code}%"),
                    )
                )

            stmt = stmt.order_by(distance_expr.asc()).limit(eff_limit)
            res = await self.session.execute(stmt)
            rows = res.all()

            for rank_idx, (chunk, distance) in enumerate(rows, start=1):
                dist_val = float(distance or 0.0)
                similarity = max(0.0, min(1.0, 1.0 - dist_val))
                if min_similarity is None or similarity >= min_similarity:
                    results.append(SemanticSearchResult(chunk, rank_idx, dist_val, similarity))
        else:
            # Fallback for SQLite unit tests
            stmt = (
                select(DocumentChunk)
                .join(DocumentChunk.document)
                .where(
                    KnowledgeDocument.is_active == True,  # noqa: E712
                    DocumentChunk.embedding_model == target_model,
                    DocumentChunk.embedding_model != "synthetic_placeholder",
                    DocumentChunk.embedding.isnot(None),
                    or_(DocumentChunk.chunk_type != "parent", DocumentChunk.chunk_type.is_(None)),
                )
                .options(selectinload(DocumentChunk.document))
            )
            if eff_doc_type:
                stmt = stmt.where(KnowledgeDocument.doc_type == eff_doc_type)

            if scheme:
                stmt = stmt.where(DocumentChunk.content.ilike(f"%{scheme}%"))

            if condition_code:
                stmt = stmt.where(DocumentChunk.content.ilike(f"%{condition_code}%"))

            res = await self.session.execute(stmt)
            chunks = res.scalars().all()
            scored: List[Tuple[DocumentChunk, float, float]] = []
            for chunk in chunks:
                vec = chunk.embedding
                if not vec or len(vec) != len(query_vector):
                    continue
                dot = sum(a * b for a, b in zip(vec, query_vector))
                norm_a = math.sqrt(sum(a * a for a in vec)) or 1.0
                norm_b = math.sqrt(sum(b * b for b in query_vector)) or 1.0
                sim = max(0.0, min(1.0, dot / (norm_a * norm_b)))
                dist = max(0.0, 1.0 - sim)
                if min_similarity is None or sim >= min_similarity:
                    scored.append((chunk, dist, sim))
            scored.sort(key=lambda x: x[1])
            for rank_idx, (chunk, dist, sim) in enumerate(scored[:eff_limit], start=1):
                results.append(SemanticSearchResult(chunk, rank_idx, dist, sim))

        return results

    async def search(
        self,
        request: Optional[Union[KnowledgeSearchRequest, str]] = None,
        *,
        query: Optional[str] = None,
        top_k: int = 5,
        retrieval_mode: str = "hybrid",
        doc_type: Optional[str] = None,
        source_type: Optional[str] = None,
        scheme: Optional[str] = None,
        condition_code: Optional[str] = None,
        include_parent_context: bool = True,
        min_score: Optional[float] = None,
    ) -> KnowledgeSearchResponse:
        """Executes hybrid, lexical-only, or semantic-only retrieval with parent context fetching and RRF."""
        search_query = query or (request if isinstance(request, str) else None)
        if isinstance(request, KnowledgeSearchRequest):
            req_obj = request
        elif search_query:
            req_obj = KnowledgeSearchRequest(
                query=search_query,
                top_k=top_k,
                retrieval_mode=retrieval_mode,
                doc_type=doc_type or source_type,
                scheme=scheme,
                condition_code=condition_code,
                include_parent_context=include_parent_context,
                min_score=min_score,
            )
        else:
            raise ValueError("Query string or KnowledgeSearchRequest must be provided to search()")

        requested_mode = req_obj.retrieval_mode
        candidate_map: Dict[uuid.UUID, Dict] = {}

        # 1. Lexical retrieval
        lexical_items = []
        if requested_mode in ("hybrid", "lexical", "lexical_only"):
            lexical_items = await self.lexical_search(
                query=req_obj.query,
                top_k=req_obj.top_k * 3,
                doc_type=req_obj.doc_type,
                scheme=req_obj.scheme,
                condition_code=req_obj.condition_code,
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
                    query=req_obj.query,
                    top_k=req_obj.top_k * 3,
                    doc_type=req_obj.doc_type,
                    scheme=req_obj.scheme,
                    condition_code=req_obj.condition_code,
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
            effective_mode = "lexical"
        elif requested_mode == "semantic_only":
            effective_mode = "semantic_only"
        elif requested_mode in ("lexical", "lexical_only"):
            effective_mode = "lexical"
        else:
            effective_mode = "hybrid" if semantic_items and lexical_items else ("semantic_only" if semantic_items else "lexical")

        # 3. Reciprocal Rank Fusion (RRF) calculation
        scored_candidates: List[SearchResultItem] = []

        # Batch load parent chunks for context attachment if requested
        parent_map: Dict[uuid.UUID, DocumentChunk] = {}
        if req_obj.include_parent_context:
            parent_ids = {
                chunk.parent_chunk_id
                for cid, data in candidate_map.items()
                if (chunk := data.get("chunk")) and chunk.parent_chunk_id is not None
            }
            if parent_ids:
                p_stmt = (
                    select(DocumentChunk)
                    .where(DocumentChunk.id.in_(list(parent_ids)))
                )
                p_res = await self.session.execute(p_stmt)
                for p_chunk in p_res.scalars().all():
                    parent_map[p_chunk.id] = p_chunk

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
            if req_obj.min_score is not None and fusion_score < req_obj.min_score:
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

            parent_chunk_obj = parent_map.get(chunk.parent_chunk_id) if chunk.parent_chunk_id else None
            parent_content = parent_chunk_obj.content if parent_chunk_obj else None
            meta_dict = dict(chunk.metadata_ or {})

            scored_candidates.append(
                SearchResultItem(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    parent_chunk_id=chunk.parent_chunk_id,
                    chunk_type=chunk.chunk_type or "standalone",
                    title=chunk.document.title if chunk.document else "Unknown Document",
                    source_id=chunk.document.source_id if chunk.document else None,
                    source_url=chunk.document.source_url if chunk.document else None,
                    source_document=meta_dict.get("source_document") or (chunk.document.title if chunk.document else None),
                    doc_type=chunk.document.doc_type if chunk.document else "policy",
                    chunk_index=chunk.chunk_index,
                    section_header=chunk.section_header,
                    section_title=chunk.section_title or chunk.section_header,
                    content=chunk.content,
                    parent_content=parent_content,
                    token_count=chunk.token_count,
                    content_hash=chunk.content_hash,
                    scheme=meta_dict.get("scheme"),
                    condition_code=meta_dict.get("condition_code"),
                    effective_date=meta_dict.get("effective_date"),
                    page_number=meta_dict.get("page_number"),
                    embedding_model=chunk.embedding_model,
                    retrieval_mode=effective_mode,
                    metadata=meta_dict,
                    ranking=ranking_info,
                )
            )

        # 4. Sort descending by fusion score and take top_k
        scored_candidates.sort(key=lambda x: x.ranking.fusion_score, reverse=True)
        top_results = scored_candidates[: req_obj.top_k]

        return KnowledgeSearchResponse(
            query=req_obj.query,
            retrieval_mode=effective_mode,
            total_candidates=len(candidate_map),
            results_count=len(top_results),
            results=top_results,
        )

    def to_citations(self, results: Union[List[SearchResultItem], KnowledgeSearchResponse]) -> List[PolicyCitation]:
        """Maps search result passages to grounded policy citations for triage reasoning."""
        items = results.results if isinstance(results, KnowledgeSearchResponse) else results
        citations = []
        for r in items:
            citations.append(
                PolicyCitation(
                    document_title=r.title,
                    section_header=r.section_title or r.section_header,
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
