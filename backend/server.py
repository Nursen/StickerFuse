"""FastAPI backend for the StickerFuse chatbot.

Endpoints:
  POST /api/chat   -- run the chat agent with tool-calling pipeline
  GET  /api/health -- health check

In production, serves the React build from frontend/dist as static files.

Start:
  uvicorn backend.server:app --reload
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from backend.chat_agent import get_agent  # noqa: E402

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="StickerFuse API", version="0.1.0")

# CORS for local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ToolResult(BaseModel):
    tool_name: str
    args: dict
    result: str


class ChatResponse(BaseModel):
    reply: str
    tool_results: list[ToolResult] = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "stickerfuse"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Run the PydanticAI chat agent with StickerFuse tools."""

    try:
        # Build a single user prompt that includes conversation history for context
        parts: list[str] = []
        for msg in req.history:
            prefix = "User" if msg.role == "user" else "Assistant"
            parts.append(f"{prefix}: {msg.content}")
        parts.append(f"User: {req.message}")

        user_prompt = "\n\n".join(parts)

        # Run the agent (async, lazy-built on first call)
        agent = get_agent()
        result = await agent.run(user_prompt)

        # Extract tool call info from the run messages for the frontend
        tool_results: list[ToolResult] = []
        for msg in result.all_messages():
            msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else {}
            kind = msg_dict.get("kind", "")

            if kind == "tool-return":
                tool_results.append(
                    ToolResult(
                        tool_name=msg_dict.get("tool_name", "unknown"),
                        args={},
                        result=_truncate(msg_dict.get("content", ""), max_len=2000),
                    )
                )

        return ChatResponse(
            reply=result.output,
            tool_results=tool_results,
        )

    except Exception as exc:
        return ChatResponse(
            reply=f"Something went wrong: {exc}",
            tool_results=[],
        )


def _truncate(text: str, max_len: int = 2000) -> str:
    """Truncate long tool outputs so we don't blow up the response."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "... (truncated)"


# ---------------------------------------------------------------------------
# Serve generated sticker images
# ---------------------------------------------------------------------------

STICKERS_DIR = PROJECT_ROOT / "outputs" / "stickers"
STICKERS_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/stickers",
    StaticFiles(directory=str(STICKERS_DIR)),
    name="sticker-images",
)


# ---------------------------------------------------------------------------
# Serve React static files (production)
# ---------------------------------------------------------------------------

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    # Serve static assets (JS, CSS, images) under /assets
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="static-assets",
    )

    # Catch-all: serve index.html for client-side routing
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
