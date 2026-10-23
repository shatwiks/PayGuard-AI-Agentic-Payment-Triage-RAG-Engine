"""Tests validating API contracts, OpenAPI schema compliance, and triage rules."""

from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient

from backend.app.main import app
from backend.app.schemas.payment import PaymentDetailResponse
from backend.app.services.triage import TriageRulesEngine


def test_openapi_schema_endpoint_contracts():
    """Verify OpenAPI specification exposes all required API contracts."""
    schema = app.openapi()
    assert "paths" in schema
    paths = schema["paths"]

    # Verify required endpoints exist
    assert "/api/v1/health" in paths
    assert "get" in paths["api/v1/health"]

    assert "/api/v1/auth/login" in paths
    assert "post" in paths["api/v1/auth/login"]

    assert "/api/v1/payments" in paths
    assert "get" in paths["api/v1/payments"]

    assert "/api/v1/payments/{payment_id}" in paths
    assert "get" in paths["api/v1/payments/{payment_id}"]

    assert "/api/v1/investigations" in paths
    assert "post" in paths["api/v1/investigations"]
    assert "get" in paths["api/v1/investigations"]

    assert "/api/v1/investigations/{investigation_id}" in paths
    assert "get" in paths["api/v1/investigations/{investigation_id}"]


def test_triage_engine_rules():
    """Verify deterministic triage engine classifies failure codes and intents correctly."""
    engine = TriageRulesEngine()

    # Case 1: Failed payment
    failed_payment = PaymentDetailResponse(
        id=uuid.uuid4(),
        payment_reference="tx_fail_1",
        customer_id="c_1",
        merchant_id="m_1",
        amount=Decimal("100.00"),
        currency="USD",
        payment_method="credit_card",
        status="failed",
        gateway_name="stripe",
        failure_code="insufficient_funds",
        created_at="2026-10-20T10:00:00Z",
        updated_at="2026-10-20T10:00:00Z",
    )
    result1 = engine.classify_payment_issue(failed_payment, "Why did my transaction fail?")
    assert result1.category == "failed_payment"
    assert result1.confidence_score >= 0.95
    assert result1.identified_failure_code == "insufficient_funds"

    # Case 2: Duplicate charge inquiry
    result2 = engine.classify_payment_issue(None, "I was charged twice for order #9921!")
    assert result2.category == "duplicate_charge"
    assert result2.confidence_score >= 0.90

    # Case 3: Refund status inquiry
    result3 = engine.classify_payment_issue(None, "Where is my refund for returned merchandise?")
    assert result3.category == "refund_status"

    # Case 4: Ambiguous query
    result4 = engine.classify_payment_issue(None, "Hello, can you help me?")
    assert result4.category == "unknown_or_other"
    assert result4.is_ambiguous is True


@pytest.mark.asyncio
async def test_health_endpoint_contract(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "version" in data


@pytest.mark.asyncio
async def test_validation_error_envelope(client: AsyncClient):
    """Verify malformed requests return RFC 7807-style error envelope."""
    # Query too short (< 5 chars)
    response = await client.post(
        "/api/v1/investigations",
        json={"customer_query": "no"},
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_investigation_creation_workflow(client: AsyncClient):
    """Verify investigation creation returns 201 Created and structured result."""
    payload = {
        "customer_query": "Customer says transaction tx_20261020_0001 failed with card declined error.",
        "payment_reference": "tx_20261020_0001",
        "priority": "high",
    }
    response = await client.post("/api/v1/investigations", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert "case_number" in data
    assert data["status"] == "triaged"
    assert data["priority"] == "high"
    assert "result" in data
    assert data["result"]["issue_category"] in (
        "failed_payment",
        "pending_payment",
        "duplicate_charge",
        "refund_status",
        "unknown_or_other",
    )
    assert "recommended_action" in data["result"]
    assert "investigation_summary" in data["result"]
