"""Application configuration — environment variables, UC paths, model endpoints."""
from __future__ import annotations

import os
import sys

_app_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_app_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

# --- Databricks Connection ---
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")

# --- Unity Catalog Hierarchy ---
CATALOG = os.environ.get("SPEC_CATALOG", "serverless_stable_1acr1x_catalog")
SCHEMA = os.environ.get("SPEC_SCHEMA", "spec_docs")

# --- Unity Catalog Volume for raw PDFs ---
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/raw_documents"

# --- Model Endpoints ---
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
EMBEDDING_ENDPOINT = os.environ.get("EMBEDDING_ENDPOINT", "databricks-bge-large-en")

# --- Vector Search ---
VS_ENDPOINT_NAME = os.environ.get("VS_ENDPOINT_NAME", "spec-intelligence-vs")
VS_INDEX_CHUNKS = f"{CATALOG}.{SCHEMA}.document_chunks_vs_index"
ENABLE_VECTOR_SEARCH = os.environ.get("ENABLE_VECTOR_SEARCH", "true").lower() == "true"

# --- Delta Table Names ---
TABLE_DOCUMENTS = f"{CATALOG}.{SCHEMA}.documents"
TABLE_DOCUMENT_PAGES = f"{CATALOG}.{SCHEMA}.document_pages"
TABLE_DOCUMENT_SECTIONS = f"{CATALOG}.{SCHEMA}.document_sections"
TABLE_DOCUMENT_CHUNKS = f"{CATALOG}.{SCHEMA}.document_chunks"
TABLE_DOCUMENT_TABLES = f"{CATALOG}.{SCHEMA}.document_tables"
TABLE_DOCUMENT_VERSIONS = f"{CATALOG}.{SCHEMA}.document_versions"
TABLE_DOCUMENT_COMPARISONS = f"{CATALOG}.{SCHEMA}.document_comparisons"

# --- LLM Settings ---
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 4096

# --- Chunking Settings ---
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
