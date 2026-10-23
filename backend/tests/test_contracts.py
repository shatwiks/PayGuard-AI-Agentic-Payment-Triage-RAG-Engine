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
    assert "get" in paths["/api/v1/health"]

    assert "/api/v1/auth/login" in paths
    assert "post" in paths["/api/v1/auth/login"]

    assert "/api/v1/payments" in paths
    assert "get" in paths["/api/v1/payments"]

    assert "/api/v1/payments/{payment_id}" in paths
    assert "get" in paths["/api/v1/payments/{payment_id}"]

    assert "/api/v1/investigations" in paths
    assert "post" in paths["/api/v1/investigations"]
    assert "get" in paths["/api/v1/investigations"]

    assert "/api/v1/investigations/{investigation_id}" in paths
    assert "get" in paths["/api/v1/investigations/{investigation_id}"]


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


@pytest.mark.asyncio
async def test_payments_endpoints_flow(client: AsyncClient, db_session):
    """Verify listing and detail retrieval of payments via API routes."""
    from backend.app.services.payment import PaymentService

    service = PaymentService(db_session)
    payment = await service.create_payment(
        payment_reference="tx_contract_test_001",
        customer_id="cust_test_contract",
        merchant_id="merch_test_contract",
        amount=Decimal("89.95"),
        currency="USD",
        payment_method="credit_card",
        status="captured",
        gateway_name="stripe",
    )

    # 1. List payments with pagination and filter
    list_resp = await client.get("/api/v1/payments?payment_reference=tx_contract_test_001")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(p["payment_reference"] == "tx_contract_test_001" for p in list_data["items"])

    # 2. Get payment details by ID
    detail_resp = await client.get(f"/api/v1/payments/{payment.id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["id"] == str(payment.id)
    assert detail_data["payment_reference"] == "tx_contract_test_001"
    assert Decimal(detail_data["amount"]) == Decimal("89.95")

    # 3. Query non-existent payment ID -> 404 Not Found
    random_id = uuid.uuid4()
    not_found_resp = await client.get(f"/api/v1/payments/{random_id}")
    assert not_found_resp.status_code == 404
    err_data = not_found_resp.json()
    assert err_data["error"]["code"] == "ENTITY_NOT_FOUND"


@pytest.mark.asyncio
async def test_investigations_endpoints_flow(client: AsyncClient):
    """Verify creating, listing, and retrieving investigations via API routes."""
    # 1. Create case
    create_payload = {
        "customer_query": "Customer asking why transaction tx_investigate_001 has status pending for 3 days.",
        "payment_reference": "tx_investigate_001",
        "priority": "medium",
    }
    create_resp = await client.post("/api/v1/investigations", json=create_payload)
    assert create_resp.status_code == 201
    created_case = create_resp.json()
    case_id = created_case["id"]

    # 2. List investigations
    list_resp = await client.get("/api/v1/investigations?page=1&page_size=10")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(c["id"] == case_id for c in list_data["items"])

    # 3. Retrieve single investigation case
    get_resp = await client.get(f"/api/v1/investigations/{case_id}")
    assert get_resp.status_code == 200
    case_data = get_resp.json()
    assert case_data["id"] == case_id
    assert case_data["status"] == "triaged"
    assert case_data["result"] is not None

    # 4. Non-existent investigation case -> 404 Not Found
    random_case_id = uuid.uuid4()
    nf_resp = await client.get(f"/api/v1/investigations/{random_case_id}")
    assert nf_resp.status_code == 404
    assert nf_resp.json()["error"]["code"] == "ENTITY_NOT_FOUND"


@pytest.mark.asyncio
async def test_payments_by_reference_endpoint(client: AsyncClient, db_session):
    """Verify retrieval of payment details by human-readable reference code."""
    from backend.app.services.payment import PaymentService

    service = PaymentService(db_session)
    await service.create_payment(
        payment_reference="tx_by_ref_spec_100",
        customer_id="cust_ref_100",
        merchant_id="merch_ref_100",
        amount=Decimal("49.99"),
        currency="USD",
        payment_method="ach",
        status="pending",
        gateway_name="adyen",
    )

    resp = await client.get("/api/v1/payments/by-reference/tx_by_ref_spec_100")
    assert resp.status_code == 200
    data = resp.json()
    assert data["payment_reference"] == "tx_by_ref_spec_100"
    assert data["status"] == "pending"

    # Non-existent reference returns 404
    nf_resp = await client.get("/api/v1/payments/by-reference/tx_nonexistent_reference_xyz")
    assert nf_resp.status_code == 404
    assert nf_resp.json()["error"]["code"] == "ENTITY_NOT_FOUND"


@pytest.mark.asyncio
async def test_investigations_metrics_endpoint(client: AsyncClient):
    """Verify backend metrics endpoint returns aggregate counts for the dashboard."""
    resp = await client.get("/api/v1/investigations/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_cases" in data
    assert "open_cases" in data
    assert "triaged_cases" in data
    assert "escalated_cases" in data
    assert "by_category" in data
    assert isinstance(data["total_cases"], int)
    assert isinstance(data["by_category"], dict)

