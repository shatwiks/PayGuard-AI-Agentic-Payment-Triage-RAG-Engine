"""Tests for Pydantic v2 schemas and validation rules."""

from datetime import datetime, timezone
from decimal import Decimal
import uuid
import pytest
from pydantic import ValidationError

from backend.app.schemas.common import ErrorDetail, ErrorResponse, HealthResponse, PaginatedResponse, PaginationParams
from backend.app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from backend.app.schemas.payment import (
    PaymentDetailResponse,
    PaymentEventResponse,
    PaymentFilterParams,
    PaymentSummaryResponse,
)
from backend.app.schemas.investigation import (
    InvestigationCaseResponse,
    InvestigationCreateRequest,
    InvestigationFilterParams,
    InvestigationResultResponse,
    PolicyCitation,
)


def test_pagination_params_validation():
    params = PaginationParams(page=2, page_size=50)
    assert params.page == 2
    assert params.page_size == 50

    with pytest.raises(ValidationError):
        PaginationParams(page=0)  # must be ge=1

    with pytest.raises(ValidationError):
        PaginationParams(page_size=101)  # must be le=100


def test_paginated_response_helper():
    items = ["item1", "item2", "item3"]
    paginated = PaginatedResponse.create(items=items, total=25, page=1, page_size=10)
    assert paginated.total == 25
    assert paginated.total_pages == 3
    assert len(paginated.items) == 3


def test_investigation_create_request_validation():
    # Valid
    req = InvestigationCreateRequest(
        customer_query="Customer claims they were charged twice for transaction tx_12345.",
        payment_reference="tx_12345",
        priority="high",
    )
    assert req.priority == "high"

    # Query too short (< 5 chars)
    with pytest.raises(ValidationError):
        InvestigationCreateRequest(customer_query="why")

    # Invalid priority enum
    with pytest.raises(ValidationError):
        InvestigationCreateRequest(
            customer_query="Valid query text here",
            priority="critical_emergency",
        )


def test_policy_citation_schema():
    citation = PolicyCitation(
        document_title="Visa Core Rules and Visa Product and Service Rules",
        section_header="Dispute Condition 10.4: Other Fraud - Card-Absent Environment",
        excerpt="The merchant is responsible for disputed transactions if 3D Secure authentication was not obtained.",
        confidence_score=0.95,
    )
    assert citation.confidence_score == 0.95
    assert "Dispute Condition 10.4" in citation.section_header


def test_payment_detail_response_schema():
    payment_id = uuid.uuid4()
    detail = PaymentDetailResponse(
        id=payment_id,
        payment_reference="tx_test_99",
        customer_id="cust_123",
        merchant_id="merch_456",
        amount=Decimal("129.99"),
        currency="USD",
        payment_method="credit_card",
        status="failed",
        gateway_name="stripe",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        failure_code="insufficient_funds",
        failure_message="Card has insufficient funds",
    )
    assert detail.amount == Decimal("129.99")
    assert detail.failure_code == "insufficient_funds"
