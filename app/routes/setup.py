"""Setup route — initialize UC tables and vector search."""
from fastapi import APIRouter

from app.services.uc_setup import run_full_setup
from app.services.vector_search_service import create_vector_search_endpoint, create_vector_search_index

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.post("")
async def run_setup():
    """Initialize all Unity Catalog tables and Vector Search."""
    uc_results = run_full_setup()
    vs_endpoint = create_vector_search_endpoint()
    vs_index = create_vector_search_index()

    return {
        "uc_tables": uc_results,
        "vector_search_endpoint": vs_endpoint,
        "vector_search_index": vs_index,
    }
