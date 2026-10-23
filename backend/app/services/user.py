"""User repository and service for identity management and authentication."""

from typing import Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import ConflictException
from backend.app.core.security import get_password_hash, verify_password
from backend.app.models.user import User
from backend.app.schemas.auth import UserCreateRequest


class UserService:
    """Manages user persistence, registration, and credential verification."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email.lower().strip())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, request: UserCreateRequest) -> User:
        # Check if email is already registered
        existing = await self.get_by_email(request.email)
        if existing:
            raise ConflictException(f"User with email '{request.email}' already exists.")

        user = User(
            id=uuid.uuid4(),
            email=request.email.lower().strip(),
            hashed_password=get_password_hash(request.password),
            full_name=request.full_name.strip(),
            role=request.role or "support_agent",
            is_active=True,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        user = await self.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
