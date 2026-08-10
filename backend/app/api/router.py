"""Aggregate API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import analyses, health, knowledge

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(analyses.router)
api_router.include_router(knowledge.router)

__all__ = ["api_router"]
