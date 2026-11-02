"""Route modules, combined into one router."""

from fastapi import APIRouter

from app.api.routes import companies, health, markets, stats

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(stats.router, prefix="/api")
api_router.include_router(markets.router, prefix="/api")
api_router.include_router(companies.router, prefix="/api")

__all__ = ["api_router"]
