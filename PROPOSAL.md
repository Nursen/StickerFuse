# StickerFuse: Viral Moments to Monetizable Merch

**MGT 575 — Generative AI and Social Media | Final Project Proposal**

---

## The Problem

Platforms like Redbubble and Etsy are flooded with sticker designs that ride viral waves — "rat girl summer," Brat Summer aesthetics, niche fandom quotes. But the creator pipeline is slow and manual: spot a trend, brainstorm an idea, design it, format it for print. By the time most creators ship, the moment has passed.

## The Solution

**StickerFuse** is a web app that collapses the viral-moment-to-merch pipeline into minutes. Users explore trending cultural moments through an AI-guided discovery flow and generate print-ready sticker designs (Cricut-compatible) with one click.

### The Pipeline

```
Topic  →  Subtopics  →  Viral Bites  →  Sticker Ideas  →  Print-Ready Design
```

| Stage | Example | What the AI Does |
|---|---|---|
| **Topic** | "Taylor Swift" | User inputs or picks from curated suggestions |
| **Subtopics** | "Travis Kelce engagement," "Eras Tour final show" | AI agent surfaces timely subtopics from social media signals |
| **Viral Bites** | "I'm the problem, it's me" / specific meme formats | AI identifies hyper-niche, monetizable moments — quotes, lyrics, phrases, visual memes |
| **Sticker Ideas** | Text-only, image-only, or text+image concepts with art style options | AI generates multiple sticker concepts with style references (kawaii, retro, minimalist, etc.) |
| **Design** | Final PNG/SVG with transparent background | AI image generation + an edit chat for tweaks, exported Cricut-ready |

### Community Configuration

Users can tune how the AI agents discover content by setting preferences:
- **Source communities** (Twitter/X, TikTok, Reddit, Tumblr, etc.)
- **Tone filters** (wholesome, edgy, ironic, earnest)
- **Content type priorities** (quotes, visual memes, catchphrases, lyrics)
- **Recency window** (last 24h, last week, evergreen)

This makes the tool flexible across wildly different niches — cottagecore Tumblr aesthetics vs. NBA Twitter vs. K-pop stan communities.

---

## High-Level Tech Stack

| Layer | Choice | Why |
|---|---|---|
| **Frontend** | Next.js (React) | Aligns with course material (Lecture 15); server-side rendering for fast loads |
| **Backend/API** | Next.js API Routes | Keep it simple — one codebase, one deploy |
| **Database** | Supabase (Postgres) | Free tier, built-in auth, aligns with course DB lecture (Lecture 9) |
| **AI — Trend Discovery** | Claude API | Multi-step agentic reasoning to go from topic → subtopics → viral bites → sticker concepts |
| **AI — Image Generation** | DALL-E 3 or Flux | Generate sticker artwork from concept descriptions |
| **AI — Design Chat** | Claude API | Conversational refinement of generated designs |
| **Hosting** | Vercel | Free tier, native Next.js support, covered in Lecture 14 |
| **Payments (stretch)** | Stripe | Covered in Lecture 17; could enable direct sales or credits |

### Key API Integrations (for trend signals)

- **Twitter/X API** — trending topics, viral tweets
- **Reddit API** — hot posts by subreddit
- **Google Trends API** — search volume spikes
- **TikTok** — trending sounds/hashtags (scraping or unofficial API)

---

## Architecture Sketch

```
┌─────────────────────────────────────────────────┐
│                   Frontend (Next.js)             │
│                                                   │
│  ┌───────────┐  ┌───────────┐  ┌──────────────┐ │
│  │  Explore   │→│  Viral     │→│  Design       │ │
│  │  Topics    │  │  Bites    │  │  Studio       │ │
│  └───────────┘  └───────────┘  └──────────────┘ │
└──────────────────────┬──────────────────────────┘
                       │
              ┌────────▼────────┐
              │  API Routes      │
              │  (Next.js)       │
              └──┬─────┬─────┬──┘
                 │     │     │
        ┌────────▼┐ ┌──▼──┐ ┌▼────────┐
        │ Claude   │ │Image│ │Supabase  │
        │ (Agentic │ │ Gen │ │(DB/Auth) │
        │  Search) │ │ API │ │          │
        └─────────┘ └─────┘ └──────────┘
```

---

## What Makes This an "Outstanding" Project

Per the syllabus, outstanding projects demonstrate **creativity, originality, and lasting impression**:

1. **Multi-agent AI pipeline** — Not just one API call. Chained AI reasoning across discovery, ideation, and generation stages (ties into Lecture 18: Agentic AI).
2. **Real commercial viability** — Output is literally sellable product. Cricut-compatible designs can go straight to an Etsy shop.
3. **Social media analysis at its core** — Trend detection across platforms is applied sentiment/virality analysis (Lectures 2, 11).
4. **Touches nearly every course topic** — Image generation (L7), chatbots (L10), React (L15), databases (L9), hosting (L14), payments (L17), agentic AI (L18).
5. **Community-configurable** — The tuning knobs for different digital communities show understanding of how content varies across social platforms.

---

## Scope & Milestones

| Phase | Deliverable | Status |
|---|---|---|
| **Phase 0** | Project proposal & team formation | *Current* |
| **Phase 1** | Topic exploration flow (Claude-powered discovery) | |
| **Phase 2** | Viral bites → sticker idea generation | |
| **Phase 3** | Image generation + Cricut-ready export | |
| **Phase 4** | Design chat agent for refinements | |
| **Phase 5** | Community config + polish | |
| **Stretch** | User accounts, saved projects, Stripe payments | |

---

## Team

- Nursen Ogutveren
- Stephanie Duernas
- Theo Pedas

---

*Presentations: April 23 – May 5, 2026*
