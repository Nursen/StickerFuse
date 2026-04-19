"""Mine TikTok search results via Playwright (no API keys).

Adapted from Lecture 18's tiktok_search.py. Launches a real browser,
searches TikTok, scrolls to load results, and extracts video/profile
cards with view counts.

Usage:
  python -m miners.tiktok_miner "Taylor Swift" --limit 20 --headed
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

# ---------------------------------------------------------------------------
# Anti-detection browser setup (copied from Lecture 18 tiktok_search.py)
# ---------------------------------------------------------------------------

_IGNORE_PLAYWRIGHT_DEFAULTS = ["--enable-automation"]
_EXTRA_BROWSER_ARGS = ["--disable-blink-features=AutomationControlled"]
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

WAIT_AFTER_SEARCH_S = 5.0


def _open_browser_context(p, *, headed: bool):
    """Launch Chrome (preferred) or bundled Chromium. Returns (browser, context, page)."""
    headless = not headed
    context_opts = {
        "locale": "en-US",
        "user_agent": _DEFAULT_USER_AGENT,
        "viewport": {"width": 1280, "height": 800},
    }
    # Try installed Chrome first, then bundled Chromium
    for channel in ("chrome", "msedge", None):
        try:
            launch_kw = {
                "headless": headless,
                "ignore_default_args": _IGNORE_PLAYWRIGHT_DEFAULTS,
                "args": _EXTRA_BROWSER_ARGS,
            }
            if channel:
                launch_kw["channel"] = channel
            browser = p.chromium.launch(**launch_kw)
            context = browser.new_context(**context_opts)
            page = context.new_page()
            return browser, context, page
        except Exception:
            continue

    raise RuntimeError(
        "Could not start a browser. Install Google Chrome, "
        "or run: playwright install chromium"
    )


def _tiktok_search_url(query: str, *, user_tab: bool = False) -> str:
    """Build a TikTok search URL. Always includes the `t` param TikTok expects."""
    t = str(int(time.time() * 1000))
    path = "https://www.tiktok.com/search/user" if user_tab else "https://www.tiktok.com/search"
    qs = urlencode({"q": query.strip(), "t": t}, quote_via=quote)
    return f"{path}?{qs}"


def _scroll_results(page, rounds: int = 4) -> None:
    """Scroll to load more results from TikTok's virtualized list."""
    for _ in range(rounds):
        try:
            page.mouse.wheel(0, 800)
        except Exception:
            break
        time.sleep(0.4)


# ---------------------------------------------------------------------------
# View count parsing
# ---------------------------------------------------------------------------

def parse_tiktok_count(text: str) -> int | None:
    """Parse TikTok's abbreviated counts into integers.

    Examples: '1.2M' -> 1200000, '456K' -> 456000, '89' -> 89
    """
    if not text or not isinstance(text, str):
        return None
    text = text.strip().replace(",", "")
    m = re.match(r"^([\d.]+)\s*([KkMmBb]?)$", text)
    if not m:
        return None
    num = float(m.group(1))
    suffix = m.group(2).upper()
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "": 1}
    return int(num * multipliers.get(suffix, 1))


# ---------------------------------------------------------------------------
# Search result extraction (JS runs in browser)
# ---------------------------------------------------------------------------

_EXTRACT_VIDEO_CARDS_JS = """
(maxResults) => {
  const results = [];
  const seen = new Set();

  // Strategy 1: Look for search card containers with data-e2e attributes
  for (const card of document.querySelectorAll('[data-e2e="search_top-item"], [data-e2e="search-card-desc"], [class*="DivVideoCardContainer"], [class*="DivItemCardContainer"]')) {
    const container = card.closest('[class*="Container"]') || card.parentElement?.parentElement || card;
    const link = container.querySelector('a[href*="/video/"]') || container.querySelector('a[href*="/@"]');
    if (!link) continue;
    const href = link.getAttribute('href') || '';
    if (seen.has(href)) continue;
    seen.add(href);

    const videoMatch = href.match(/\\/video\\/(\\d+)/);
    const handleMatch = href.match(/@([^/?#]+)/);

    // Try to find view count — TikTok puts these in strong tags or spans near thumbnails
    let viewText = '';
    for (const el of container.querySelectorAll('strong, [class*="Count"], [class*="count"], [class*="play"], [class*="view"]')) {
      const t = (el.textContent || '').trim();
      if (/^[\\d.]+[KkMmBb]?$/.test(t) && t.length < 10) {
        viewText = t;
        break;
      }
    }

    // Caption/description
    let caption = '';
    const descEl = container.querySelector('[data-e2e="search-card-desc"], [class*="SpanText"], [class*="desc"]');
    if (descEl) caption = (descEl.textContent || '').trim();
    if (!caption) caption = (container.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 200);

    results.push({
      kind: videoMatch ? 'video' : 'profile',
      url: href.startsWith('http') ? href : 'https://www.tiktok.com' + href,
      video_id: videoMatch ? videoMatch[1] : null,
      handle: handleMatch ? handleMatch[1] : null,
      caption: caption.slice(0, 300),
      view_count: viewText || null,
      text: (container.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 300),
    });
    if (results.length >= maxResults) break;
  }

  // Strategy 2: Fallback — harvest all video and profile links like Lecture 18
  if (results.length < 3) {
    for (const a of document.querySelectorAll('a[href]')) {
      const raw = (a.getAttribute('href') || '').trim();
      if (!raw) continue;
      const abs = raw.startsWith('http') ? raw : ('https://www.tiktok.com' + (raw.startsWith('/') ? raw : '/' + raw));

      const videoMatch = abs.match(/\\/video\\/(\\d+)/);
      const handleMatch = abs.match(/tiktok\\.com\\/@([^/?#]+)/);
      if (!videoMatch && !handleMatch) continue;
      if (seen.has(abs)) continue;
      seen.add(abs);

      // Walk up the DOM to find view count text near this link
      let viewText = '';
      let el = a;
      for (let i = 0; i < 5 && el; i++) {
        for (const child of el.querySelectorAll('strong, span')) {
          const t = (child.textContent || '').trim();
          if (/^[\\d.]+[KkMmBb]?$/.test(t) && t.length < 10) {
            viewText = t;
            break;
          }
        }
        if (viewText) break;
        el = el.parentElement;
      }

      const text = (a.innerText || '').replace(/\\s+/g, ' ').trim();

      results.push({
        kind: videoMatch ? 'video' : 'profile',
        url: abs,
        video_id: videoMatch ? videoMatch[1] : null,
        handle: handleMatch ? handleMatch[1] : null,
        caption: '',
        view_count: viewText || null,
        text: text.slice(0, 300),
      });
      if (results.length >= maxResults) break;
    }
  }

  return results;
}
"""


# ---------------------------------------------------------------------------
# Main miner function
# ---------------------------------------------------------------------------

def mine_tiktok(
    query: str,
    *,
    limit: int = 20,
    headed: bool = False,
    timeout_ms: int = 30_000,
) -> dict:
    """Search TikTok and return structured results with engagement metrics.

    Args:
        query: Search term.
        limit: Max results to return.
        headed: Show the browser window (useful for debugging).
        timeout_ms: Navigation timeout in milliseconds.

    Returns:
        Dict matching the project's miner output format.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

    query = query.strip()
    if not query:
        return {"source": "tiktok", "error": "Empty query"}

    search_url = _tiktok_search_url(query)
    warnings: list[str] = []

    with sync_playwright() as p:
        browser, context, page = _open_browser_context(p, headed=headed)
        try:
            # Navigate directly to search URL (most reliable)
            page.goto(search_url, wait_until="domcontentloaded", timeout=timeout_ms)
            time.sleep(WAIT_AFTER_SEARCH_S)

            # Wait for results to appear
            try:
                page.wait_for_selector(
                    'a[href*="@"], a[href*="/video/"]',
                    timeout=min(15_000, timeout_ms),
                )
            except PwTimeout:
                warnings.append(
                    "Timed out waiting for results. TikTok may have shown a captcha or login wall."
                )

            # Scroll to load more results
            scroll_rounds = max(2, limit // 5)
            _scroll_results(page, rounds=min(scroll_rounds, 10))
            time.sleep(0.5)

            # Extract video cards from the DOM
            raw_results = []
            for frame in page.frames:
                try:
                    if frame.is_detached():
                        continue
                except Exception:
                    continue
                try:
                    chunk = frame.evaluate(_EXTRACT_VIDEO_CARDS_JS, limit)
                except Exception:
                    continue
                if isinstance(chunk, list):
                    raw_results.extend(chunk)
                if len(raw_results) >= limit:
                    break

        except Exception as exc:
            warnings.append(f"Browser error: {exc}")
            raw_results = []
        finally:
            context.close()
            browser.close()

    # Deduplicate and enrich results
    seen: set[str] = set()
    results: list[dict] = []
    for item in raw_results:
        key = item.get("video_id") or item.get("url") or ""
        if not key or key in seen:
            continue
        seen.add(key)

        view_text = item.get("view_count") or ""
        item["view_count"] = view_text or None
        item["view_count_numeric"] = parse_tiktok_count(view_text)

        results.append(item)
        if len(results) >= limit:
            break

    return {
        "source": "tiktok",
        "query": query,
        "mined_at": datetime.now(tz=timezone.utc).isoformat(),
        "search_kind": "general",
        "result_count": len(results),
        "results": results,
        "note": "Data scraped via Playwright. View counts are approximate as displayed by TikTok.",
        **({"warnings": warnings} if warnings else {}),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Mine TikTok search results (no API key needed)"
    )
    ap.add_argument("query", help="Search term (e.g. 'Taylor Swift')")
    ap.add_argument(
        "--limit", type=int, default=20,
        help="Max results to return (default: 20)",
    )
    ap.add_argument(
        "--headed", action="store_true",
        help="Show the browser window (useful for debugging captchas)",
    )
    ap.add_argument(
        "--timeout", type=int, default=30_000,
        help="Navigation timeout in ms (default: 30000)",
    )
    ap.add_argument(
        "-o", "--out", type=Path, default=None,
        help="Write JSON output to this file",
    )
    args = ap.parse_args()

    result = mine_tiktok(
        args.query,
        limit=args.limit,
        headed=args.headed,
        timeout_ms=args.timeout,
    )

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
