"""LLM service wrapping Databricks Foundation Model API."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import requests

from app.config import DATABRICKS_HOST, EMBEDDING_ENDPOINT, LLM_ENDPOINT, LLM_MAX_TOKENS, LLM_TEMPERATURE

logger = logging.getLogger(__name__)


def _get_token() -> str:
    """Get Databricks auth token from env or SDK."""
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if token:
        return token
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        if w.config.token:
            return w.config.token
        headers = w.config.authenticate()
        auth_header = headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return auth_header
    except Exception as e:
        logger.warning("Failed to get SDK token: %s", e)
        return ""


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    json_mode: bool = False,
) -> str:
    """Call LLM endpoint and return text response."""
    host = DATABRICKS_HOST.rstrip("/") if DATABRICKS_HOST else ""
    if not host:
        try:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()
            host = w.config.host.rstrip("/")
        except Exception:
            return ""

    url = f"{host}/serving-endpoints/{LLM_ENDPOINT}/invocations"
    token = _get_token()

    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature if temperature is not None else LLM_TEMPERATURE,
        "max_tokens": max_tokens if max_tokens is not None else LLM_MAX_TOKENS,
    }

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        body = ""
        if e.response is not None:
            body = e.response.text[:500]
        logger.error("LLM call failed: %s | body: %s", e, body)
        return ""
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return ""


def call_llm_json(system_prompt: str, user_prompt: str, **kwargs) -> dict[str, Any]:
    """Call LLM and parse response as JSON."""
    raw = call_llm(system_prompt, user_prompt, **kwargs)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean = "\n".join(lines)
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON: %s", raw[:200])
            return {}


def call_llm_chat(messages: list[dict[str, str]], temperature: Optional[float] = None) -> str:
    """Call LLM with full message history."""
    host = DATABRICKS_HOST.rstrip("/") if DATABRICKS_HOST else ""
    if not host:
        try:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()
            host = w.config.host.rstrip("/")
        except Exception:
            return ""

    url = f"{host}/serving-endpoints/{LLM_ENDPOINT}/invocations"
    token = _get_token()

    payload = {
        "messages": messages,
        "temperature": temperature if temperature is not None else LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
    }

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        body = ""
        if e.response is not None:
            body = e.response.text[:500]
        logger.error("LLM chat call failed: %s | body: %s", e, body)
        return ""
    except Exception as e:
        logger.error("LLM chat call failed: %s", e)
        return ""


def generate_embeddings(texts: list[str]) -> list[Optional[list[float]]]:
    """Generate embeddings using Databricks embedding endpoint."""
    host = DATABRICKS_HOST.rstrip("/")
    if not host or not texts:
        return [None] * len(texts)

    url = f"{host}/serving-endpoints/{EMBEDDING_ENDPOINT}/invocations"
    token = _get_token()

    batch_size = 16
    all_embeddings: list[Optional[list[float]]] = []

    for i in range(0, len(texts), batch_size):
        batch = [t[:8000] for t in texts[i:i + batch_size]]
        try:
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"input": batch},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            batch_results: list[Optional[list[float]]] = [None] * len(batch)
            for item in data.get("data", []):
                idx = item.get("index", 0)
                if idx < len(batch_results):
                    batch_results[idx] = item.get("embedding")
            all_embeddings.extend(batch_results)
        except Exception as e:
            logger.error("Embedding call failed: %s", e)
            all_embeddings.extend([None] * len(batch))

    return all_embeddings
