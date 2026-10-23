"""Payment investigation request, response, and structured recommendation schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.payment import PaymentSummaryResponse


class InvestigationCreateRequest(BaseModel):
    """Payload to initiate an automated payment triage investigation."""
    customer_query: str = Field(
        min_length=5,
        max_length=4000,
        description="Customer or support agent query describing the payment issue"
    )
    payment_reference: Optional[str] = Field(
        default=None,
        description="Optional payment transaction reference (e.g. tx_10293848)"
    )
    payment_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional internal payment UUID if already known"
    )
    priority: Optional[str] = Field(
        default="medium",
        pattern="^(low|medium|high|urgent)$",
        description="Requested initial case priority"
    )


class PolicyCitation(BaseModel):
    """Grounding citation referencing an official regulatory or platform policy document chunk."""
    document_title: str = Field(description="Title of cited document (e.g., Visa Dispute Rules, NACHA ACH Guide)")
    section_header: str = Field(description="Section or rule clause identifier (e.g., Condition 10.4, Return Code R01)")
    excerpt: str = Field(description="Extracted verbatim policy excerpt supporting the recommendation")
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="RAG retrieval similarity score")
    source_id: Optional[str] = Field(default=None, description="Stable source identifier or URI")
    source_url: Optional[str] = Field(default=None, description="Canonical source URL")
    document_id: Optional[uuid.UUID] = Field(default=None, description="UUID of source knowledge document")
    chunk_id: Optional[uuid.UUID] = Field(default=None, description="UUID of cited chunk")
    is_synthetic_demonstration: bool = Field(default=True, description="Flag indicating synthetic demonstration status")

    @property
    def title(self) -> str:
        return self.document_title

    @property
    def exact_passage(self) -> str:
        return self.excerpt

    @property
    def relevant_section(self) -> str:
        return self.section_header


class InvestigationResultResponse(BaseModel):
    """Structured evidence, classification, and recommended next steps."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    issue_category: str = Field(
        description="Classified category: failed_payment, pending_payment, duplicate_charge, refund_status, or unknown_or_other"
    )
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence in the classification and diagnosis")
    investigation_summary: str = Field(description="Synthesized explanation grounded strictly in transaction facts and policy")
    recommended_action: str = Field(description="Action enum: VOID_HOLD, INITIATE_REFUND, WAIT_SETTLEMENT, REQUEST_EVIDENCE, ESCALATE")
    recommended_action_details: str = Field(description="Step-by-step guidance for support operations engineer")
    policy_citations: List[PolicyCitation] = Field(default_factory=list, description="Policy excerpts supporting the recommendation")
    missing_or_conflicting_info: List[str] = Field(default_factory=list, description="Gaps, missing data, or conflicting records identified")
    human_review_required: bool = Field(default=False, description="Flag indicating whether an analyst must manually approve the resolution")
    human_review_reason: Optional[str] = Field(default=None, description="Explanation for human review requirement")
    execution_time_ms: int = Field(description="End-to-end investigation latency in milliseconds")
    llm_model_name: str = Field(description="Model identifier used for grounded explanation generation")
    created_at: datetime


class InvestigationCaseResponse(BaseModel):
    """Full investigation case envelope containing customer query, status, associated payment, and triage result."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_number: str
    customer_query: str
    sanitized_query: str
    status: str
    priority: str
    payment_id: Optional[uuid.UUID] = None
    created_by_user_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    payment: Optional[PaymentSummaryResponse] = None
    result: Optional[InvestigationResultResponse] = None


class InvestigationFilterParams(BaseModel):
    """Query parameter filters for the GET /investigations search endpoint."""
    status: Optional[str] = Field(default=None, description="Case status: open, in_progress, triaged, escalated, closed")
    priority: Optional[str] = Field(default=None, description="Case priority: low, medium, high, urgent")
    issue_category: Optional[str] = Field(default=None, description="Classified issue category")
    human_review_required: Optional[bool] = Field(default=None, description="Filter for cases requiring human approval")
