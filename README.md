# StickerFuse

**Fandom DNA x Internet Culture = Sticker Packs**

AI-powered sticker design pipeline. Search any fandom or topic, brainstorm concepts grounded in real Reddit/YouTube/Wikipedia data, generate sticker variations, and export print-ready packs.

Built for MGT 575 (Generative AI & Social Media) at Yale SOM.

---

<!--
## Cleanup Notes (Dead Code Candidates)

The following files may be candidates for removal or refactoring:

- `run_pipeline.py` — CLI entry point from the old linear pipeline (mine → subtopics →
  viral bites → sticker ideas → design). Still works standalone but is not used by the
  web app. The web app's pack-centric flow replaced this workflow.
- `agents/design_agent.py` — Only used via `chat_agent.py` tool. The Studio now uses
  `variation_agent.py` → `image_gen_agent.py` directly. Kept for chat backward compat.
- `agents/subtopic_agent.py` — Only used via `chat_agent.py` tool. Not part of the main
  Studio/IdeaBank flow.
- `agents/viral_bite_agent.py` — Only used via `chat_agent.py` tool. Same as above.
- `miners/tiktok_miner.py` — Playwright-based TikTok scraper. Not imported by server or
  trend_scorer. Works standalone via CLI only.
- `miners/trends_mcp.py` — Trends MCP client. Not imported by server or trend_scorer.
  Works standalone via CLI only.
- `miners/velocity_forecast.py` — Imported by no other module (not even trend_scorer).
  Appears fully orphaned.
- `backend/sticker_library.py` — Earlier library approach, still has endpoints in server
  but the Pack system (`pack_manager.py`) is the primary workflow now.
- `frontend/src/components/TrendPulse.jsx` — The old "Trend Pulse" tab. Still rendered in
  App.jsx but the main user journey now starts from PackHome.
- `frontend/src/components/CommunityView.jsx` — Beta community mining view. Rendered in
  App.jsx but lightly used.
- `frontend/src/components/StickerViewer.jsx` — Sticker viewing component. Check if still
  referenced or superseded by PackView.
- `frontend/src/components/SaveToLibraryButton.jsx` — Tied to the old sticker_library
  system. May be superseded by pack-based saving.
-->

## Quick Start

### 1. Clone & install

```bash
git clone git@github.com:Nursen/StickerFuse.git
cd StickerFuse

# Python deps
pip install -r requirements.txt

# Frontend deps
cd frontend && npm install && cd ..

# Playwright (for TikTok mining — optional)
playwright install chromium
```

### 2. Configure API keys

```bash
cp .env.example .env
```

Edit `.env` and add your **Gemini API key** (required):

```
GEMINI_API_KEY=your-key-here
```

Optional keys for richer data:
```
YOUTUBE_API_KEY=your-youtube-key     # enables video stats (free at console.cloud.google.com)
TRENDSMCP_API_KEY=your-key           # 12+ platform trends (free at trendsmcp.ai)
```

> **Reddit and Google Trends require NO API keys.** Wikipedia and YouTube RSS fallback also work without keys.

### 3. Run

```bash
# Terminal 1: Backend
uvicorn backend.server:app --port 8000 --reload

# Terminal 2: Frontend
cd frontend && npm run dev
```

Open **http://localhost:5173**

---

## How It Works

### User Journey

```
Create Pack → Idea Bank (manual + AI brainstorm) → Studio (generate + refine) → Pack View (export)
```

### Three Ways to Add Ideas

| Method | How | What happens |
|--------|-----|-------------|
| **Type your own** | Manual input in Idea Bank | Add any concept directly |
| **AI Brainstorm** | Search a fandom/topic | Get ~15 concepts grounded in Reddit, YouTube, and Wikipedia data |
| **Community Mining** (Beta) | Paste Discord/Slack chat logs | Extract niche in-jokes and community language |

### The Studio

Two-column creative workspace:

- **Left panel**: edit text, art style tiles, layout picker, visual direction, color mood
- **Right panel**: generate 3 distinct variations (AI creates different creative directions), refine, compare, save to pack

### The AI Pipeline

```
Reddit + YouTube + Wikipedia mining
        ↓
Community synthesis
        ↓
Merch ideation agent (fandom DNA × internet culture)
        ↓
Variation agent (3 distinct creative directions)
        ↓
Image generation (Gemini Nano Banana)
        ↓
Sticker PNG
```

### Marketing Kit (Beta)

- **Comment drafter** — reads thread tone, writes natural comments
- **Listing generator** — Redbubble/Etsy optimized titles, descriptions, 13 tags

---

## Project Structure

```
StickerFuse/
├── schemas/                     # Pydantic models
│   ├── trend.py                 # TrendSignal (34 fields), TrendReport
│   ├── topic.py                 # Subtopic discovery
│   ├── viral.py                 # Viral bites
│   ├── sticker.py               # Sticker concepts
│   ├── design.py                # Image gen prompts
│   ├── config.py                # Community config
│   └── community.py             # Community mining
│
├── miners/                      # Social listening data sources
│   ├── reddit_miner.py          # Reddit .json (no API key needed)
│   ├── trends_miner.py          # Google Trends via pytrends
│   ├── youtube_miner.py         # YouTube Data API + RSS fallback
│   ├── wikipedia_miner.py       # Wikimedia Pageviews API
│   ├── tiktok_miner.py          # Playwright scraping (CLI only)
│   ├── web_search_miner.py      # Gemini grounded web search
│   ├── trends_mcp.py            # Trends MCP 12+ platforms (CLI only)
│   ├── community_miner.py       # Text analysis for Discord/Slack
│   ├── sentiment.py             # VADER + Gemini Flash-Lite emotions
│   ├── spike_detector.py        # Poisson-based spike detection
│   ├── velocity_forecast.py     # Linear regression forecasting
│   └── trend_scorer.py          # Cross-platform correlation engine
│
├── agents/                      # PydanticAI agents (Gemini)
│   ├── merch_ideation_agent.py  # Fandom DNA × internet culture ideation
│   ├── variation_agent.py       # 3 distinct creative directions per concept
│   ├── image_gen_agent.py       # Generates PNGs (Nano Banana)
│   ├── moment_detector.py       # Detects viral moments from trend data
│   ├── community_agent.py       # Interprets community patterns
│   ├── comment_drafter.py       # (planned) Contextual comment drafting
│   ├── listing_generator.py     # (planned) Redbubble/Etsy listing gen
│   ├── sticker_idea_agent.py    # Generates design concepts
│   ├── design_agent.py          # Creates image gen prompts (chat only)
│   ├── subtopic_agent.py        # Trend analyst (chat only)
│   └── viral_bite_agent.py      # Extracts quotable moments (chat only)
│
├── backend/                     # FastAPI server
│   ├── server.py                # API endpoints + static file serving
│   ├── chat_agent.py            # Chat orchestrator (12 tools)
│   ├── pack_manager.py          # Pack CRUD + idea/sticker management
│   └── sticker_library.py       # Legacy sticker library
│
├── frontend/                    # React dashboard (Vite)
│   └── src/
│       ├── App.jsx              # Tab layout + pack routing
│       ├── App.css
│       ├── main.jsx
│       ├── context/
│       │   └── TrendContext.jsx  # Shared state provider
│       └── components/
│           ├── PackHome.jsx         # Create & manage packs
│           ├── IdeaBank.jsx         # Manual + AI brainstorm ideas
│           ├── StickerStudio.jsx    # Two-column generate + refine
│           ├── PackView.jsx         # View pack contents, export ZIP
│           ├── ChatSidebar.jsx      # Collapsible chat assistant
│           ├── TrendPulse.jsx       # Trend cards with metrics
│           ├── CommunityView.jsx    # Paste-to-analyze (beta)
│           ├── StickerViewer.jsx    # Sticker display
│           ├── SaveToLibraryButton.jsx # Save to library
│           ├── Message.jsx          # Chat messages
│           └── ToolResult.jsx       # Expandable tool results
│
├── utils/
│   └── llm_retry.py             # Gemini retry logic with backoff
│
├── .env.example                 # API key template
├── requirements.txt             # Python dependencies
├── run_pipeline.py              # CLI entry point (legacy pipeline)
└── PROPOSAL.md                  # Original project proposal
```

> **Note:** `agents/comment_drafter.py`, `agents/listing_generator.py`, and `miners/semantic_clusterer.py` are referenced in the design but not yet created. The semantic clusterer lives on a separate branch.

---

## API Reference

### Pack Management
```
POST   /api/packs                  — create pack
GET    /api/packs                  — list packs
GET    /api/packs/:id              — get pack
PATCH  /api/packs/:id              — update pack
DELETE /api/packs/:id              — delete pack
POST   /api/packs/:id/ideas        — add idea
POST   /api/packs/:id/ideas/batch  — add multiple ideas
DELETE /api/packs/:id/ideas/:id    — remove idea
POST   /api/packs/:id/stickers     — add sticker
DELETE /api/packs/:id/stickers/:fn — remove sticker
GET    /api/packs/:id/export       — download ZIP
```

### Studio
```
POST   /api/studio/variations      — 3 distinct creative directions
POST   /api/studio/generate-image  — generate sticker PNG
POST   /api/studio/brainstorm      — sticker concept generation
POST   /api/studio/suggest-phrases — phrase variants
DELETE /api/studio/sticker/:fn     — delete sticker file
```

### Intelligence
```
POST   /api/ideate                 — merch ideation (fandom x internet culture)
POST   /api/analyze                — cross-platform trend analysis
GET    /api/trending               — top trends (cached)
POST   /api/cluster                — semantic clustering
```

### Marketing
```
POST   /api/marketing/draft-comment     — contextual comment drafting
POST   /api/marketing/generate-listing  — Redbubble/Etsy listing
```

### Chat & Health
```
POST   /api/chat                   — context-aware chat assistant
GET    /api/health                 — health check
```

---

## Data Sources

| Source | API Key? | What It Provides | Cost |
|--------|----------|-----------------|------|
| Reddit | No | Post scores, comments, engagement velocity | Free |
| Google Trends | No | Search volume spikes, rising queries | Free |
| YouTube | Optional | View counts, like ratios, views/hour | Free (10K/day) |
| Wikipedia | No | Pageview spikes (proxy for public interest) | Free |
| TikTok | No | Video discovery via Playwright | Free (fragile) |
| Gemini Web Search | Gemini key | Cross-platform mentions (Twitter, news, blogs) | Gemini quota |
| Trends MCP | Optional | TikTok/YouTube/Google growth rates | Free (100/day) |

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| AI Framework | PydanticAI + Gemini | Course standard (MGT 575 Lecture 18) |
| Schemas | Pydantic v2 | Structured agent outputs |
| Backend | FastAPI | One codebase, async support |
| Frontend | React + Vite | Fast dev, matches course material |
| Image Gen | Gemini Nano Banana | Free tier, same API key |
| Sentiment | VADER (free) + Gemini Flash-Lite (cheap) | Cost optimization |
| Spike Detection | Poisson model (Twitter/Gnip method) | Statistical rigor, zero cost |
| Scraping | Playwright | TikTok (adapted from Lecture 18) |

---

## Team

- **Nursen Ogutveren**
- **Stephanie Duernas**
- **Theo Pedas**

Yale SOM -- MGT 575: Generative AI and Social Media

Presentations: April 23 -- May 5, 2026
