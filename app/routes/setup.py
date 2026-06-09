"""Setup route — initialize UC tables."""
from fastapi import APIRouter

from app.services.uc_setup import run_full_setup

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.post("")
async def run_setup():
    """Initialize all Unity Catalog tables."""
    uc_results = run_full_setup()
    return {"uc_tables": uc_results}
