"""Authentication endpoints for support operations personnel."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.errors import UnauthorizedException
from backend.app.core.security import create_access_token, verify_password
from backend.app.models.user import User
from backend.app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticates support operations engineer and returns JWT access token.",
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # Query user by email
    stmt = select(User).where(User.email == request.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise UnauthorizedException("Incorrect email or password")

    if not user.is_active:
        raise UnauthorizedException("User account is disabled")

    access_token = create_access_token(subject=user.id, role=user.role)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=3600,
        user_id=user.id,
        user_role=user.role,
    )
