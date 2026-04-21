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
import re
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

from pydantic_ai.messages import ToolReturnPart  # noqa: E402

from backend.chat_agent import run_chat_with_retries, _run_in_thread  # noqa: E402
from backend.sticker_library import get_library  # noqa: E402

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

        # Run the agent with retries + optional fallback model (see .env)
        result = await run_chat_with_retries(user_prompt)

        tool_results = _collect_tool_results_from_run(result)

        return ChatResponse(
            reply=result.output,
            tool_results=tool_results,
        )

    except Exception as exc:
        return ChatResponse(
            reply=f"Something went wrong: {exc}",
            tool_results=[],
        )


# ---------------------------------------------------------------------------
# Sticker Studio — direct pipeline (no chat agent; guaranteed JSON for the UI)
# ---------------------------------------------------------------------------


class StudioBrainstormRequest(BaseModel):
    parent_topic: str = ""
    moment: str
    trend_context: str = ""
    mode: str = "auto"  # auto | phrase | visual


class StudioPhrasesRequest(BaseModel):
    parent_topic: str = ""
    moment: str
    trend_context: str = ""


class StudioImageRequest(BaseModel):
    prompt: str
    parent_topic: str = ""
    moment: str = ""


def _studio_brainstorm_context(req: StudioBrainstormRequest) -> str:
    bits: list[str] = []
    if req.parent_topic.strip():
        bits.append(f"Parent topic / franchise: {req.parent_topic.strip()}")
    if req.trend_context.strip():
        bits.append(f"Signals and evidence: {req.trend_context.strip()}")
    if req.mode == "visual":
        bits.append(
            "Emphasize image-led sticker concepts; tie visuals to the parent topic's aesthetic, "
            "era, and recognizable character types — not generic stock imagery."
        )
    elif req.mode == "phrase":
        bits.append(
            "Emphasize text-forward stickers with varied typography treatments; ground copy in the "
            "parent topic when provided."
        )
    else:
        bits.append(
            "Balance phrase-led and visual-led concepts; ground all visuals in the parent topic when "
            "it is provided."
        )
    return "\n".join(bits)


@app.post("/api/studio/brainstorm")
async def studio_brainstorm(req: StudioBrainstormRequest):
    """Run sticker idea generation directly — returns structured ideas for the React Studio."""
    from agents.sticker_idea_agent import generate_sticker_ideas

    if not req.moment.strip():
        return JSONResponse({"status": "error", "error": "moment is required"}, status_code=400)
    try:
        ctx = _studio_brainstorm_context(req)
        out = await _run_in_thread(generate_sticker_ideas, req.moment.strip(), ctx)
        data = out.model_dump()
        return {"status": "ok", "data": data}
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


@app.post("/api/studio/suggest-phrases")
async def studio_suggest_phrases(req: StudioPhrasesRequest):
    """Return 5 distinct phrase options for phrase-focused mode."""
    from agents.sticker_idea_agent import suggest_phrase_variants

    if not req.moment.strip():
        return JSONResponse({"status": "error", "error": "moment is required"}, status_code=400)
    try:
        out = await _run_in_thread(
            suggest_phrase_variants,
            req.parent_topic,
            req.moment.strip(),
            req.trend_context,
        )
        return {"status": "ok", "phrases": out.phrases}
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


@app.post("/api/studio/generate-image")
async def studio_generate_image(req: StudioImageRequest):
    """Generate a sticker PNG and return filename for the Studio gallery."""
    from agents.image_gen_agent import generate_sticker_image

    if not req.prompt.strip():
        return JSONResponse({"status": "error", "error": "prompt is required"}, status_code=400)
    try:
        full = req.prompt.strip()
        if req.parent_topic.strip() or req.moment.strip():
            full = (
                f"{full}\n\n"
                f"Context — parent topic: {req.parent_topic or 'n/a'}; "
                f"moment: {req.moment or 'n/a'}"
            )
        path = await _run_in_thread(generate_sticker_image, full)
        name = path.name
        return {"status": "ok", "filename": name, "url": f"/stickers/{name}"}
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


def _sticker_output_dir() -> Path:
    return PROJECT_ROOT / "outputs" / "stickers"


@app.delete("/api/studio/sticker/{filename}")
async def studio_delete_sticker(filename: str):
    """Remove a generated sticker PNG from disk (Studio gallery delete)."""
    safe = Path(filename).name
    if safe != filename or ".." in filename:
        return JSONResponse({"status": "error", "error": "Invalid filename"}, status_code=400)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.png", safe):
        return JSONResponse({"status": "error", "error": "Invalid filename"}, status_code=400)
    base = _sticker_output_dir().resolve()
    path = (base / safe).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        return JSONResponse({"status": "error", "error": "Invalid path"}, status_code=400)
    if not path.is_file():
        return JSONResponse({"status": "error", "error": "Not found"}, status_code=404)
    path.unlink()
    return {"status": "ok", "deleted": safe}


# ---------------------------------------------------------------------------
# Sticker Viewer — persistent library (copies; independent of Studio deletes)
# ---------------------------------------------------------------------------

_sticker_lib = get_library(PROJECT_ROOT)


class StickerLibraryFolderCreate(BaseModel):
    name: str


class StickerLibrarySaveItem(BaseModel):
    folder_id: str
    source_filename: str


class StickerLibraryMoveItem(BaseModel):
    folder_id: str


@app.get("/api/sticker-library")
async def sticker_library_list():
    """Folders and items for the Sticker Viewer tab."""
    try:
        data = _sticker_lib.list_all()
        return {"status": "ok", **data}
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


@app.post("/api/sticker-library/folders")
async def sticker_library_create_folder(req: StickerLibraryFolderCreate):
    try:
        folder = _sticker_lib.create_folder(req.name)
        return {"status": "ok", "folder": folder}
    except ValueError as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


@app.delete("/api/sticker-library/folders/{folder_id}")
async def sticker_library_delete_folder(folder_id: str):
    try:
        _sticker_lib.delete_folder(folder_id)
        return {"status": "ok", "deleted_folder": folder_id}
    except ValueError as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


@app.post("/api/sticker-library/items")
async def sticker_library_save_item(req: StickerLibrarySaveItem):
    """Copy a PNG from outputs/stickers into a library folder."""
    try:
        item = _sticker_lib.add_item_from_stickers_folder(req.folder_id, req.source_filename)
        return {
            "status": "ok",
            "item": item,
            "url": f"/library/{item['folder_id']}/{item['filename']}",
        }
    except ValueError as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


@app.patch("/api/sticker-library/items/{item_id}")
async def sticker_library_move_item(item_id: str, req: StickerLibraryMoveItem):
    try:
        item = _sticker_lib.move_item(item_id, req.folder_id)
        return {
            "status": "ok",
            "item": item,
            "url": f"/library/{item['folder_id']}/{item['filename']}",
        }
    except ValueError as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


@app.delete("/api/sticker-library/items/{item_id}")
async def sticker_library_delete_item(item_id: str):
    try:
        _sticker_lib.delete_item(item_id)
        return {"status": "ok", "deleted": item_id}
    except ValueError as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# Direct trend analysis endpoint (bypasses chat agent for speed)
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    topic: str
    subreddits: list[str] = []
    limit: int = 15


@app.post("/api/analyze")
async def analyze_trends_direct(req: AnalyzeRequest):
    """Run trend analysis directly — parallel mining, no chat agent overhead.

    Returns a TrendReport with progress updates via structured JSON.
    """
    import asyncio

    topic = req.topic.strip()
    subreddits = req.subreddits or [topic.lower().replace(" ", "")]
    search_terms = [topic]
    limit = min(req.limit, 50)

    # Track progress
    progress = {"sources_total": 5, "sources_done": 0, "errors": []}

    async def mine_reddit():
        try:
            from miners.reddit_miner import mine_multiple_subreddits
            return await _run_in_thread(mine_multiple_subreddits, subreddits, limit=limit)
        except Exception as e:
            progress["errors"].append(f"Reddit: {e}")
            return None
        finally:
            progress["sources_done"] += 1

    async def mine_google_trends():
        try:
            from miners.trends_miner import mine_multiple_keywords
            return await _run_in_thread(mine_multiple_keywords, search_terms)
        except Exception as e:
            progress["errors"].append(f"Google Trends: {e}")
            return None
        finally:
            progress["sources_done"] += 1

    async def mine_yt():
        try:
            from miners.youtube_miner import mine_youtube
            return await _run_in_thread(mine_youtube, topic, limit=10)
        except Exception as e:
            progress["errors"].append(f"YouTube: {e}")
            return None
        finally:
            progress["sources_done"] += 1

    async def mine_wiki():
        try:
            from miners.wikipedia_miner import search_wikipedia_trends
            return await _run_in_thread(search_wikipedia_trends, topic, limit=5)
        except Exception as e:
            progress["errors"].append(f"Wikipedia: {e}")
            return None
        finally:
            progress["sources_done"] += 1

    async def mine_web():
        try:
            from miners.web_search_miner import mine_web_search
            return await _run_in_thread(mine_web_search, f"{topic} trending")
        except Exception as e:
            progress["errors"].append(f"Web search: {e}")
            return None
        finally:
            progress["sources_done"] += 1

    # Run ALL sources in parallel
    reddit_data, trends_data, youtube_data, wikipedia_data, web_search_data = (
        await asyncio.gather(
            mine_reddit(),
            mine_google_trends(),
            mine_yt(),
            mine_wiki(),
            mine_web(),
        )
    )

    # Score with cross-platform correlation
    try:
        from miners.trend_scorer import score_trends
        report = await _run_in_thread(
            score_trends,
            reddit_data,
            trends_data,
            youtube_data,
            wikipedia_data,
            web_search_data,
        )
        return {
            "status": "ok",
            "report": report.model_dump(),
            "progress": progress,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "progress": progress,
        }


# ---------------------------------------------------------------------------
# Top trending endpoint (pre-canned popular subreddits)
# ---------------------------------------------------------------------------

_trending_cache: dict = {"data": None, "timestamp": 0}
_CACHE_TTL = 300  # 5 minutes


@app.get("/api/trending")
async def top_trending():
    """Get top trends from Google Trends + Wikipedia + Reddit. Cached for 5 minutes."""
    import asyncio
    import time

    now = time.time()
    if _trending_cache["data"] and (now - _trending_cache["timestamp"]) < _CACHE_TTL:
        return _trending_cache["data"]

    async def mine_google_trending():
        """Google Trends is the primary signal for 'what's trending right now'."""
        try:
            from miners.trends_miner import mine_trends
            # Get trending searches (empty keyword = general trending)
            from pytrends.request import TrendReq
            pytrends = TrendReq(hl="en-US", tz=360)
            trending_df = pytrends.trending_searches(pn="united_states")
            topics = trending_df[0].tolist()[:10]

            # Get related queries for the top topics
            results = []
            for topic in topics[:5]:
                try:
                    data = await _run_in_thread(mine_trends, topic, timeframe="now 7-d")
                    results.append(data)
                except Exception:
                    continue
            return {
                "keywords": results,
                "top_trending_searches": topics,
            }
        except Exception:
            return None

    async def mine_wiki_trending():
        try:
            from miners.wikipedia_miner import search_wikipedia_trends
            return await _run_in_thread(search_wikipedia_trends, "trending", limit=10)
        except Exception:
            return None

    async def mine_reddit_popular():
        try:
            from miners.reddit_miner import mine_multiple_subreddits
            return await _run_in_thread(mine_multiple_subreddits, ["popular", "all"], limit=15)
        except Exception:
            return None

    trends_data, wikipedia_data, reddit_data = await asyncio.gather(
        mine_google_trending(), mine_wiki_trending(), mine_reddit_popular()
    )

    try:
        from miners.trend_scorer import score_trends
        report = await _run_in_thread(score_trends, reddit_data, trends_data, None, wikipedia_data, None)
        result = {
            "status": "ok",
            "report": report.model_dump(),
            "cached": False,
            "primary_source": "google_trends",
        }
        _trending_cache["data"] = result
        _trending_cache["timestamp"] = now
        return result
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _truncate(text: str, max_len: int = 20000) -> str:
    """Truncate long tool outputs so we don't blow up the response."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "... (truncated)"


def _collect_tool_results_from_run(run_result) -> list[ToolResult]:
    """Extract tool return payloads from PydanticAI v2 message history.

    Tool outputs live on ModelRequest.parts as ToolReturnPart, not as top-level
    messages with kind 'tool-return'.
    """
    out: list[ToolResult] = []
    for msg in run_result.all_messages():
        parts = getattr(msg, "parts", None)
        if not parts:
            continue
        for part in parts:
            if isinstance(part, ToolReturnPart):
                try:
                    body = part.model_response_str()
                except Exception:
                    body = str(part.content)
                out.append(
                    ToolResult(
                        tool_name=part.tool_name,
                        args={},
                        result=_truncate(body, max_len=20000),
                    )
                )
    return out


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

STICKER_LIBRARY_DATA = PROJECT_ROOT / "outputs" / "sticker_library" / "data"
STICKER_LIBRARY_DATA.mkdir(parents=True, exist_ok=True)

app.mount(
    "/library",
    StaticFiles(directory=str(STICKER_LIBRARY_DATA)),
    name="sticker-library-images",
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
