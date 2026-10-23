"""API v1 master router aggregating health, auth, payments, and investigations."""

from fastapi import APIRouter
from backend.app.api import auth, health, investigations, knowledge, payments

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(payments.router)
api_router.include_router(investigations.router)
api_router.include_router(knowledge.router)
