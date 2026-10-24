from datetime import datetime
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
        description="Filter by document type (e.g. scheme_rules, refund_policy, dispute_guide, sla_spec, user_upload)",
    )
    min_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional minimum reciprocal rank fusion or similarity threshold",
    )
    scheme: Optional[str] = Field(
        default=None,
        description="Optional filter by payment scheme (e.g. Visa, NACHA, Mastercard, UPI, FedNow)",
    )
    condition_code: Optional[str] = Field(
        default=None,
        description="Optional filter by dispute condition or return reason code (e.g. 10.4, R01)",
    )
    include_parent_context: bool = Field(
        default=True,
        description="Whether to fetch and attach surrounding parent chunk context for retrieved child chunks",
    )
    document_ids: Optional[List[uuid.UUID]] = Field(
        default=None,
        description="Optional list of document UUIDs to restrict search scope",
    )
    scope: str = Field(
        default="all",
        description="Search scope: 'all', 'uploaded', or 'knowledge_base'",
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
    """Individual retrieved document chunk with source provenance, hierarchy, and scoring metadata."""
    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID = Field(description="UUID of the matched document chunk")
    document_id: uuid.UUID = Field(description="UUID of the parent knowledge document")
    parent_chunk_id: Optional[uuid.UUID] = Field(default=None, description="UUID of parent section chunk if this is a child chunk")
    chunk_type: str = Field(default="standalone", description="Chunk hierarchy type: parent, child, or standalone")
    title: str = Field(description="Title of the source policy document")
    source_id: Optional[str] = Field(default=None, description="Stable source URI or identifier")
    source_url: Optional[str] = Field(default=None, description="Canonical link or reference location")
    source_document: Optional[str] = Field(default=None, description="Name of source document")
    doc_type: str = Field(description="Document category")
    chunk_index: int = Field(description="0-based sequence index in document")
    section_header: str = Field(description="Heading or rule section")
    section_title: Optional[str] = Field(default=None, description="Clean section title")
    content: str = Field(description="Verbatim chunk text content")
    parent_content: Optional[str] = Field(default=None, description="Surrounding context from parent chunk")
    token_count: int = Field(description="Estimated token count")
    content_hash: Optional[str] = Field(default=None, description="SHA-256 hash of chunk content")
    scheme: Optional[str] = Field(default=None, description="Payment scheme if detected e.g. Visa, NACHA")
    condition_code: Optional[str] = Field(default=None, description="Dispute condition or return reason code")
    effective_date: Optional[str] = Field(default=None, description="Effective policy date in ISO format")
    page_number: Optional[int] = Field(default=None, description="Source page number if applicable")
    embedding_model: Optional[str] = Field(default=None, description="Model identifier used to produce embedding")
    retrieval_mode: Optional[str] = Field(default="hybrid", description="Retrieval mode used for this result")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Structured chunk metadata")
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


class KnowledgeIngestRequest(BaseModel):
    """Payload to ingest an official policy document into the knowledge base."""
    title: str = Field(min_length=3, max_length=255, description="Document title")
    raw_content: str = Field(min_length=10, max_length=100000, description="Full policy text in Markdown format")
    source_id: Optional[str] = Field(default=None, max_length=128, description="Stable source identifier")
    document_type: str = Field(default="policy", max_length=64, description="Document type")
    version: str = Field(default="1.0", max_length=32, description="Version string")
    source_url: Optional[str] = Field(default=None, max_length=512, description="Source URL")
    hierarchical: bool = Field(default=True, description="Enable parent-child hierarchical chunking")


class KnowledgeIngestResponse(BaseModel):
    """Result of document ingestion and chunking."""
    document_id: uuid.UUID
    source_id: Optional[str]
    title: str
    chunks_created: int
    content_hash: str
    status: str


class UserDocumentSummary(BaseModel):
    """Metadata summary for user-uploaded or system knowledge documents."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    doc_type: str
    version: str
    content_hash: Optional[str] = None
    is_system: bool
    processing_status: str
    embedding_status: str
    page_count: Optional[int] = None
    chunk_count: int
    uploaded_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class UserDocumentDetail(UserDocumentSummary):
    """Detailed view of a document including error messages and preview."""
    error_message: Optional[str] = None
    raw_content_preview: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    """Response returned upon uploading a document."""
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    id: Optional[uuid.UUID] = None
    title: str
    file_name: str
    file_size_bytes: int
    chunks_created: int
    chunk_count: Optional[int] = None
    page_count: Optional[int] = None
    processing_status: str
    embedding_status: str
    is_duplicate: bool = False
    message: str


class DocumentAskRequest(BaseModel):
    """Request to ask a question grounded strictly in selected or authorized documents."""
    query: str = Field(min_length=2, max_length=1000, description="Question to answer using document evidence")
    document_ids: Optional[List[uuid.UUID]] = Field(default=None, description="Optional document IDs to restrict search scope")
    scope: str = Field(default="uploaded", description="Scope: 'uploaded', 'knowledge_base', or 'all'")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of evidence excerpts to retrieve")
    retrieval_mode: str = Field(default="hybrid", pattern="^(hybrid|semantic_only|lexical_only)$")


class CitedExcerptItem(BaseModel):
    """Specific passage excerpt with exact document, section, and page provenance."""
    document_id: uuid.UUID
    document_title: str
    chunk_id: Optional[uuid.UUID] = None
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    excerpt: str
    score: float


class DocumentAskResponse(BaseModel):
    """Evidence-grounded answer to a user question regarding documents."""
    query: str
    answer: str
    has_sufficient_evidence: bool
    is_grounded: bool = False
    cited_excerpts: List[CitedExcerptItem] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    retrieval_mode_used: str
    embedding_status: str
    scope_used: str


