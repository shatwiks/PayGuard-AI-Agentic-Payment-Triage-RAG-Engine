"""Payment request, response, and filter schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class PaymentEventResponse(BaseModel):
    """Payment state transition and processor webhook log event."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    event_type: str
    from_status: Optional[str] = None
    to_status: str
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
    created_at: datetime


class PaymentSummaryResponse(BaseModel):
    """Compact payment representation for list collections and case associations."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_reference: str
    customer_id: str
    merchant_id: str
    amount: Decimal
    currency: str
    payment_method: str
    status: str
    gateway_name: str
    created_at: datetime


class PaymentDetailResponse(PaymentSummaryResponse):
    """Complete payment representation with failure codes, metadata, and event timeline."""
    gateway_transaction_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    metadata_: Dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")
    authorized_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    updated_at: datetime
    events: List[PaymentEventResponse] = Field(default_factory=list)


class PaymentFilterParams(BaseModel):
    """Query parameter filters for the GET /payments search endpoint."""
    payment_reference: Optional[str] = Field(default=None, description="Exact or partial payment reference code")
    customer_id: Optional[str] = Field(default=None, description="Customer identifier")
    merchant_id: Optional[str] = Field(default=None, description="Merchant account ID")
    status: Optional[str] = Field(default=None, description="Payment lifecycle status")
    payment_method: Optional[str] = Field(default=None, description="Payment rail (credit_card, ach, upi, etc.)")
    gateway_name: Optional[str] = Field(default=None, description="Processor name (stripe, adyen, etc.)")
