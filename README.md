# StickerFuse

**Viral Moments → Sticker Designs**

AI-powered social listening + sticker design pipeline. Detects trending cultural moments across 6+ platforms, verifies them with hard metrics, and generates print-ready sticker designs — all from a single dashboard.

Built for MGT 575 (Generative AI & Social Media) at Yale SOM.

---

## Quick Start

### 1. Clone & install

```bash
git clone git@github.com:Nursen/StickerFuse.git
cd StickerFuse

# Python deps
pip install -r requirements.txt

# Frontend deps
cd frontend && npm install && cd ..

# Playwright (for TikTok mining)
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

### Three Modes

| Mode | What it does | Status |
|------|-------------|--------|
| **Trend Pulse** | Cross-platform trend detection with verified metrics | ✅ Live |
| **Sticker Studio** | Viral bite → concept → generated sticker PNG | ✅ Live |
| **Community Mining** | Paste Discord/Slack chat to find niche in-jokes | 🧪 Beta |

### The Trend Intelligence Pipeline

```
Reddit ─────┐
Google Trends┤
YouTube ─────┤
Wikipedia ───┤──→ Trend Scorer ──→ Cross-Platform ──→ Dashboard
TikTok ──────┤      │                Correlation
Web Search ──┤      │
Trends MCP ──┘      ▼
               ┌─────────────┐
               │ VADER       │ sentiment analysis (free)
               │ Poisson η   │ statistical spike detection (free)
               │ Velocity    │ "still trending in 3 days?" (free)
               └─────────────┘
```

### What Makes a Trend "Verified"

Every trend in StickerFuse comes with:

- **Spike score** — how far above baseline (Poisson η statistic)
- **Engagement velocity** — score per hour
- **Cross-platform confirmation** — how many sources agree (Reddit, Google, YouTube, Wikipedia, etc.)
- **Confidence rating** — HIGH (3+ platforms, η > 1.5), MEDIUM, LOW
- **Sentiment analysis** — emotional intensity via VADER
- **Velocity forecast** — will it still be trending in 72 hours?
- **Evidence URLs** — actual posts/pages backing every claim

No trend is surfaced without data to support it.

### The Sticker Creation Pipeline

```
Trend → Viral Bites → Sticker Concepts → Design Spec → Generated PNG
         (quotes,       (3-5 variations    (image gen     (Gemini Nano
          phrases)       per bite)           prompt)        Banana)
```

---

## Project Structure

```
StickerFuse/
├── schemas/                 # Pydantic models
│   ├── trend.py             # TrendSignal (34 fields), TrendReport
│   ├── topic.py             # Subtopic discovery
│   ├── viral.py             # Viral bites
│   ├── sticker.py           # Sticker concepts
│   ├── design.py            # Image gen prompts
│   ├── config.py            # Community config
│   └── community.py         # Community mining
│
├── miners/                  # Social listening agents
│   ├── reddit_miner.py      # Reddit .json (no API key needed)
│   ├── trends_miner.py      # Google Trends via pytrends
│   ├── youtube_miner.py     # YouTube Data API + RSS fallback
│   ├── wikipedia_miner.py   # Wikimedia Pageviews API
│   ├── tiktok_miner.py      # Playwright scraping
│   ├── web_search_miner.py  # Gemini grounded web search
│   ├── trends_mcp.py        # Trends MCP (12+ platforms)
│   ├── community_miner.py   # Text analysis for Discord/Slack
│   ├── sentiment.py         # VADER + Gemini Flash-Lite emotions
│   ├── spike_detector.py    # Poisson-based spike detection
│   ├── velocity_forecast.py # Linear regression forecasting
│   └── trend_scorer.py      # Cross-platform correlation engine
│
├── agents/                  # PydanticAI agents (Gemini)
│   ├── subtopic_agent.py    # Trend analyst (data-driven, never invents)
│   ├── viral_bite_agent.py  # Extracts quotable moments
│   ├── sticker_idea_agent.py # Generates design concepts
│   ├── design_agent.py      # Creates image gen prompts
│   ├── image_gen_agent.py   # Generates PNGs (Nano Banana)
│   └── community_agent.py   # Interprets community patterns
│
├── backend/                 # FastAPI server
│   ├── server.py            # API endpoints + static file serving
│   └── chat_agent.py        # Chat orchestrator (12 tools)
│
├── frontend/                # React dashboard (Vite)
│   └── src/
│       ├── App.jsx          # 3-tab layout
│       ├── components/
│       │   ├── TrendPulse.jsx    # Trend cards with metrics
│       │   ├── StickerStudio.jsx # Creation pipeline
│       │   ├── CommunityView.jsx # Paste-to-analyze (beta)
│       │   ├── ChatSidebar.jsx   # Collapsible chat
│       │   ├── Message.jsx       # Chat messages
│       │   └── ToolResult.jsx    # Expandable tool results
│       └── App.css
│
├── .env.example             # API key template
├── requirements.txt         # Python dependencies
├── PROPOSAL.md              # Original project proposal
└── run_pipeline.py          # CLI entry point
```

---

## CLI Usage

Every miner and agent can be used standalone from the command line:

```bash
# Mine data
python -m miners.reddit_miner --subreddits taylorswift nba --limit 20
python -m miners.trends_miner "Taylor Swift" "NBA playoffs"
python -m miners.youtube_miner "Taylor Swift" --limit 10
python -m miners.wikipedia_miner "Taylor Swift" --limit 5
python -m miners.tiktok_miner "Taylor Swift" --headed  # opens browser
python -m miners.web_search_miner "Taylor Swift trending moments"

# Analyze
python -m miners.community_miner --file my_discord_export.txt

# Run agents
python -m agents.subtopic_agent "Taylor Swift" --reddit-data output/reddit.json
python -m agents.viral_bite_agent "Eras Tour finale" --context "Taylor Swift"
python -m agents.sticker_idea_agent "I'm the problem, it's me"
python -m agents.image_gen_agent "kawaii cat with heart, sticker design"

# Full pipeline CLI
python run_pipeline.py mine-reddit --subreddits taylorswift --limit 10
python run_pipeline.py mine-trends "Taylor Swift"
python run_pipeline.py subtopics "Taylor Swift"
python run_pipeline.py viral-bites "Eras Tour finale"
python run_pipeline.py sticker-ideas "I'm the problem, it's me"
python run_pipeline.py design "kawaii cat with problem text" --style kawaii
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

Yale SOM — MGT 575: Generative AI and Social Media

Presentations: April 23 – May 5, 2026
