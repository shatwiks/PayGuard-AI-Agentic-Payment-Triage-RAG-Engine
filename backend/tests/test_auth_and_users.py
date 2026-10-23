"""Unit and functional tests for User authentication, registration, and security foundations."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import ConflictException
from backend.app.core.security import create_access_token, verify_password
from backend.app.schemas.auth import LoginRequest, UserCreateRequest
from backend.app.services.user import UserService


@pytest.mark.asyncio
async def test_user_service_registration_and_authentication(db_session: AsyncSession):
    """Verify UserService creates user with hashed password and authenticates successfully."""
    service = UserService(db_session)
    request = UserCreateRequest(
        email="ops.specialist@payguard.ai",
        password="ValidStrongPassword123!",
        full_name="Operations Specialist",
        role="support_agent",
    )

    created_user = await service.create_user(request)
    assert created_user.id is not None
    assert created_user.email == "ops.specialist@payguard.ai"
    assert created_user.full_name == "Operations Specialist"
    assert created_user.role == "support_agent"
    assert created_user.is_active is True
    # Ensure password hash is stored and never plaintext
    assert created_user.hashed_password != "ValidStrongPassword123!"
    assert verify_password("ValidStrongPassword123!", created_user.hashed_password)

    # Authenticate with correct credentials
    auth_user = await service.authenticate("ops.specialist@payguard.ai", "ValidStrongPassword123!")
    assert auth_user is not None
    assert auth_user.id == created_user.id

    # Authenticate with incorrect password
    failed_auth = await service.authenticate("ops.specialist@payguard.ai", "WrongPassword!")
    assert failed_auth is None

    # Authenticate with non-existent email
    unknown_auth = await service.authenticate("unknown@payguard.ai", "AnyPassword123!")
    assert unknown_auth is None


@pytest.mark.asyncio
async def test_user_service_duplicate_email_rejection(db_session: AsyncSession):
    """Verify duplicate email registrations raise ConflictException (HTTP 409)."""
    service = UserService(db_session)
    req1 = UserCreateRequest(
        email="compliance@payguard.ai",
        password="SecurePassword456!",
        full_name="Compliance Analyst 1",
        role="compliance_analyst",
    )
    await service.create_user(req1)

    req2 = UserCreateRequest(
        email="compliance@payguard.ai",  # same email
        password="DifferentPassword789!",
        full_name="Compliance Analyst 2",
        role="compliance_analyst",
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.create_user(req2)

    assert "compliance@payguard.ai" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_auth_api_registration_and_login_flow(client: AsyncClient):
    """Verify full HTTP authentication flow: register -> login -> profile /auth/me."""
    # 1. Register new user
    reg_payload = {
        "email": "triage.engineer@payguard.ai",
        "password": "EngineerSecret999!",
        "full_name": "Triage Engineer",
        "role": "support_agent",
    }
    reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["email"] == "triage.engineer@payguard.ai"
    assert "password" not in user_data
    assert "password_hash" not in user_data

    # 2. Duplicate registration should return 409 Conflict
    dup_resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_resp.status_code == 409

    # 3. Login with credentials
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "triage.engineer@payguard.ai", "password": "EngineerSecret999!"},
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["user_role"] == "support_agent"

    token = token_data["access_token"]

    # 4. Access /auth/me with Bearer token
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "triage.engineer@payguard.ai"
    assert me_data["role"] == "support_agent"

    # 5. Access /auth/me without token -> 401 Unauthorized
    unauth_resp = await client.get("/api/v1/auth/me")
    assert unauth_resp.status_code == 401

    # 6. Access /auth/me with invalid token -> 401 Unauthorized
    invalid_resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid_jwt_token"})
    assert invalid_resp.status_code == 401
