"""Health check route."""
import io
import traceback

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "spec-intelligence-platform"}


@router.get("/diag")
async def diagnostics():
    """Test connectivity: SDK auth, SQL warehouse, Files API."""
    results = {}
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        results["sdk_host"] = w.config.host
        results["sdk_auth"] = "ok"
    except Exception as e:
        results["sdk_error"] = str(e)[:200]
        return results

    try:
        from app.config import WAREHOUSE_ID
        result = w.statement_execution.execute_statement(
            statement="SELECT 1 as test", warehouse_id=WAREHOUSE_ID, wait_timeout="20s"
        )
        results["sql"] = result.status.state.value if result.status else "no_status"
    except Exception as e:
        results["sql_error"] = str(e)[:200]

    try:
        from app.config import VOLUME_PATH
        w.files.upload(file_path=f"{VOLUME_PATH}/_test_diag.txt", contents=io.BytesIO(b"test"), overwrite=True)
        results["volume_write"] = "ok"
        w.files.delete(file_path=f"{VOLUME_PATH}/_test_diag.txt")
    except Exception as e:
        results["volume_error"] = str(e)[:300]

    return results
