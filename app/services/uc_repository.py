"""Unity Catalog SQL operations — generic executor and typed helpers."""
from __future__ import annotations

import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import CATALOG, SCHEMA, VOLUME_PATH, WAREHOUSE_ID

logger = logging.getLogger(__name__)


def _get_workspace_client():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


def generate_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def execute_sql(sql: str) -> list[dict[str, Any]]:
    """Execute SQL and return rows as dicts."""
    try:
        w = _get_workspace_client()
        result = w.statement_execution.execute_statement(
            statement=sql,
            warehouse_id=WAREHOUSE_ID,
            wait_timeout="50s",
        )
        if result.status and result.status.state and result.status.state.value == "FAILED":
            error_msg = result.status.error.message if result.status.error else "Unknown"
            logger.error("SQL failed: %s | %s", error_msg, sql[:200])
            return []

        if not result.manifest or not result.result:
            return []

        columns = [col.name for col in result.manifest.schema.columns]
        rows = []
        if result.result.data_array:
            for row_data in result.result.data_array:
                row_dict = {}
                for i, col_name in enumerate(columns):
                    row_dict[col_name] = row_data[i] if i < len(row_data) else None
                rows.append(row_dict)
        return rows

    except Exception as e:
        logger.error("SQL error: %s | %s", e, sql[:200])
        return []


def execute_sql_no_result(sql: str) -> bool:
    """Execute DDL/DML that returns no rows."""
    try:
        w = _get_workspace_client()
        result = w.statement_execution.execute_statement(
            statement=sql,
            warehouse_id=WAREHOUSE_ID,
            wait_timeout="50s",
        )
        if result.status and result.status.state and result.status.state.value == "FAILED":
            error_msg = result.status.error.message if result.status.error else "Unknown"
            logger.error("SQL failed: %s | %s", error_msg, sql[:200])
            return False
        return True
    except Exception as e:
        logger.error("SQL error: %s | %s", e, sql[:200])
        return False


def upload_file_to_volume(file_bytes: bytes, filename: str, document_id: str) -> Optional[str]:
    """Upload a file to UC Volume. Returns the UC path.

    Uses a flat path (no subdirectories) since UC Volumes may not support
    arbitrary nested directory creation via the files API.
    """
    safe_name = filename.replace(" ", "_").replace("(", "").replace(")", "")
    uc_path = f"{VOLUME_PATH}/{document_id}_{safe_name}"
    try:
        w = _get_workspace_client()
        w.files.upload(file_path=uc_path, contents=io.BytesIO(file_bytes), overwrite=True)
        logger.info("Uploaded %s -> %s (%d bytes)", filename, uc_path, len(file_bytes))
        return uc_path
    except Exception as e:
        logger.error("Upload failed for %s: %s", filename, e)
        # Retry without subdirectory structure
        try:
            flat_path = f"{VOLUME_PATH}/{document_id}.pdf"
            w.files.upload(file_path=flat_path, contents=io.BytesIO(file_bytes), overwrite=True)
            logger.info("Retry upload succeeded: %s -> %s", filename, flat_path)
            return flat_path
        except Exception as e2:
            logger.error("Retry upload also failed: %s", e2)
            return None


def download_file_from_volume(uc_path: str) -> Optional[bytes]:
    """Download a file from UC Volume."""
    try:
        w = _get_workspace_client()
        resp = w.files.download(file_path=uc_path)
        return resp.contents.read()
    except Exception as e:
        logger.error("Download failed for %s: %s", uc_path, e)
        return None
