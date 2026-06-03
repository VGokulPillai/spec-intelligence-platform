"""FastAPI application entry point — Spec Intelligence Platform."""
from __future__ import annotations

import logging
import os
import sys
import types

_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)

for p in (_parent_dir, _this_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

if "app" not in sys.modules:
    _pkg = types.ModuleType("app")
    _pkg.__path__ = [_this_dir]
    _pkg.__package__ = "app"
    sys.modules["app"] = _pkg

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes.chat import router as chat_router
from app.routes.compare import router as compare_router
from app.routes.documents import router as documents_router
from app.routes.health import router as health_router
from app.routes.setup import router as setup_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Spec Intelligence Platform",
    description="Document intelligence for engineering specification management — Element Materials Technology",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(compare_router)
app.include_router(setup_router)


@app.on_event("startup")
async def startup_event():
    logger.info("Spec Intelligence Platform starting...")


frontend_dir = os.path.join(_this_dir, "frontend", "dist")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
