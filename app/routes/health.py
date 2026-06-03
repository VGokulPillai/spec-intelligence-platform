"""Health check route."""
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "spec-intelligence-platform"}
