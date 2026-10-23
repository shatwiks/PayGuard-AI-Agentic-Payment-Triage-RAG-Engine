"""Schemas for knowledge base hybrid search, document retrieval, and citation tracking."""

from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, computed_field


class KnowledgeSearchRequest(BaseModel):
    """Payload to query the hybrid RAG retrieval engine."""
    query: str = Field(min_length=2, max_length=1000, description="Payment query, error code, or policy topic")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of candidate chunks to return")
    retrieval_mode: str = Field(
        default="hybrid",
        pattern="^(hybrid|semantic_only|lexical_only)$",
        description="Retrieval engine mode: 'hybrid' (RRF combined), 'semantic_only' (pgvector), or 'lexical_only' (PostgreSQL FTS)",
    )
    doc_type: Optional[str] = Field(
        default=None,
        description="Filter by document type (e.g. scheme_rules, refund_policy, dispute_guide, sla_spec)",
    )
    min_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional minimum reciprocal rank fusion or similarity threshold",
    )


class RankingDetails(BaseModel):
    """Transparent scoring breakdown explaining how the chunk was ranked."""
    lexical_rank: Optional[int] = Field(default=None, description="1-based rank from PostgreSQL full-text search")
    lexical_score: Optional[float] = Field(default=None, description="PostgreSQL ts_rank_cd relevance score")
    semantic_rank: Optional[int] = Field(default=None, description="1-based rank from pgvector cosine distance")
    semantic_distance: Optional[float] = Field(default=None, description="pgvector cosine distance (0.0 to 2.0)")
    semantic_similarity: Optional[float] = Field(default=None, description="Normalized similarity (1 - distance)")
    fusion_score: float = Field(description="Combined Reciprocal Rank Fusion (RRF) score")
    signals_used: List[str] = Field(description="Signals active during ranking (e.g. ['lexical', 'semantic'])")


class SearchResultItem(BaseModel):
    """Individual retrieved document chunk with source provenance and scoring metadata."""
    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID = Field(description="UUID of the matched document chunk")
    document_id: uuid.UUID = Field(description="UUID of the parent knowledge document")
    title: str = Field(description="Title of the source policy document")
    source_id: Optional[str] = Field(default=None, description="Stable source URI or identifier")
    source_url: Optional[str] = Field(default=None, description="Canonical link or reference location")
    doc_type: str = Field(description="Document category")
    chunk_index: int = Field(description="0-based sequence index in document")
    section_header: str = Field(description="Heading or rule section")
    content: str = Field(description="Verbatim chunk text content")
    token_count: int = Field(description="Estimated token count")
    embedding_model: Optional[str] = Field(default=None, description="Model identifier used to produce embedding")
    retrieval_mode: Optional[str] = Field(default="hybrid", description="Retrieval mode used for this result")
    ranking: RankingDetails = Field(description="Scoring and ranking diagnostics")

    @computed_field
    @property
    def text(self) -> str:
        return self.content


class KnowledgeSearchResponse(BaseModel):
    """Structured response from the hybrid RAG retrieval engine."""
    query: str = Field(description="Normalized query searched")
    retrieval_mode: str = Field(description="Active retrieval mode used (hybrid, lexical_only, or semantic_only)")
    total_candidates: int = Field(description="Total candidate chunks evaluated before filtering")
    results_count: int = Field(description="Number of results returned in this response")
    results: List[SearchResultItem] = Field(default_factory=list, description="Ranked list of relevant chunks")

    def __iter__(self):
        return iter(self.results)

    def __getitem__(self, idx):
        return self.results[idx]

    def __len__(self):
        return len(self.results)
