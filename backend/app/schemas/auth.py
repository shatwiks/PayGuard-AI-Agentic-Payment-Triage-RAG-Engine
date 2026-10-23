"""Authentication and authorization schemas."""

from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """User credentials for obtaining JWT access token."""
    email: EmailStr = Field(description="Corporate user email address")
    password: str = Field(min_length=6, description="Account password")


class TokenResponse(BaseModel):
    """JWT Bearer token response."""
    access_token: str = Field(description="Encoded JWT bearer token")
    token_type: str = Field(default="bearer", description="Token authentication scheme")
    expires_in: int = Field(description="Token lifetime in seconds")
    user_id: uuid.UUID = Field(description="Authenticated user UUID")
    user_role: str = Field(description="Assigned role: support_agent, compliance_analyst, or admin")


class UserResponse(BaseModel):
    """Public user identity model."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
