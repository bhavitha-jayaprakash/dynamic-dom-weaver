"""
╔══════════════════════════════════════════════════════════════════╗
║  COMPONENT 1 — The Ingestion & DOM Extractor                    ║
║  Fetches raw HTML, extracts clean text via Jina Reader, and     ║
║  isolates the first H1, its adjacent P, and the first CTA (A). ║
╚══════════════════════════════════════════════════════════════════╝
"""

import re
import logging
from typing import Dict, Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

# ──────────────────────────────────────────────────────────
# Module-level logger
# ──────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────
JINA_READER_BASE = "https://r.jina.ai/"
REQUEST_TIMEOUT  = 20  # seconds
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _build_headers() -> Dict[str, str]:
    """
    Returns browser-like request headers to bypass basic bot-detection
    on target URLs.

    NOTE: We intentionally omit Accept-Encoding and let the `requests`
    library handle content negotiation and decompression automatically.
    Hardcoding 'br' (Brotli) caused gibberish when the brotli package
    was not available.
    """
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _validate_url(url: str) -> str:
    """
    Normalises and validates the incoming URL.
    Raises ValueError on malformed input.
    """
    url = url.strip()
    if not url:
        raise ValueError("URL cannot be empty.")

    # Prepend scheme if missing
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL — no domain found: {url}")

    return url


def _fetch_raw_html(url: str) -> str:
    """
    Fetches the raw HTML source of a given URL.
    Raises requests.RequestException on network/HTTP errors.
    """
    logger.info("Fetching raw HTML from: %s", url)
    response = requests.get(url, headers=_build_headers(), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()  # bubble up 4xx/5xx

    # Guard against non-HTML responses (e.g. PDFs, images)
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        raise ValueError(
            f"Target URL did not return HTML. Content-Type: {content_type}"
        )

    return response.text


def _fetch_jina_text(url: str) -> str:
    """
    Calls the Jina Reader API (free public endpoint) to get a clean,
    markdown-formatted text extraction of the target page.

    Falls back gracefully if Jina is unavailable — the pipeline can
    still run with BS4 extraction alone.
    """
    jina_url = f"{JINA_READER_BASE}{url}"

    try:
        logger.info("Fetching clean text via Jina Reader: %s", jina_url)
        resp = requests.get(jina_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        logger.warning("Jina Reader call failed (non-fatal): %s", exc)
        return ""  # graceful degradation


def _find_first_visible_text(tag: Optional[Tag]) -> str:
    """
    Extracts the first meaningful visible text from a BS4 Tag,
    stripping extra whitespace.  Returns empty string if tag is None.
    """
    if tag is None:
        return ""
    return " ".join(tag.get_text(separator=" ", strip=True).split())


def _extract_key_elements(soup: BeautifulSoup, jina_text: str = "") -> Dict[str, Any]:
    """
    Extracts the three critical DOM strings with aggressive fallback chains:
      1. Headline:  h1 → h2[hero/title/header] → h2 → h3
                    → div/span[title/hero/header/heading] → jina_text[:60]
      2. Subtext:   p adjacent to headline → first p on page
      3. CTA:       short <a> (≤60 chars) → <button> → any <a>

    For each, we store the original text and its character length so
    Component 3 can enforce character-count constraints on the LLM.

    If a node cannot be found at all, a clear sentinel string is stored
    (e.g., "No Headline Found") so the AI knows to skip that mutation.
    """

    # ── Sentinel strings (passed to AI when extraction fails) ──
    NO_HEADLINE = "No Headline Found"
    NO_SUBTEXT  = "No Subheadline Found"
    NO_CTA      = "No CTA Button Found"

    # Regex to match common hero/title class names
    hero_pattern = re.compile(r"hero|title|header|banner|headline|heading", re.IGNORECASE)

    # ── 1. Headline — aggressive cascading fallback ───────────
    headline_tag = soup.find("h1")

    if headline_tag is None:
        # Fallback A: <h2> with a class hinting at hero/title/header
        headline_tag = soup.find("h2", class_=hero_pattern)

    if headline_tag is None:
        # Fallback B: any <h2>
        headline_tag = soup.find("h2")

    if headline_tag is None:
        # Fallback C: any <h3>
        headline_tag = soup.find("h3")

    if headline_tag is None:
        # Fallback D: <div> or <span> with a class containing
        # title/hero/header/heading (common in React/SPA sites)
        for tag_name in ("div", "span"):
            headline_tag = soup.find(tag_name, class_=hero_pattern)
            if headline_tag:
                break

    h1_text = _find_first_visible_text(headline_tag)

    if not h1_text:
        # Fallback E (last resort): use the first 60 characters of
        # the Jina Reader clean text to give the AI some context
        if jina_text:
            h1_text = jina_text.strip()[:60]
            logger.info("Using Jina text snippet as headline fallback: '%s'", h1_text)
        else:
            h1_text = NO_HEADLINE

    # ── 2. Adjacent P (sibling or first P after headline) ─────
    p_text = ""
    if headline_tag is not None:
        # Strategy A: next <p> sibling of the headline tag
        next_p = headline_tag.find_next_sibling("p")
        if next_p:
            p_text = _find_first_visible_text(next_p)

        # Strategy B: first <p> anywhere after the headline in
        # document order
        if not p_text:
            next_p = headline_tag.find_next("p")
            if next_p:
                p_text = _find_first_visible_text(next_p)

    # Fallback: grab the first <p> on the page
    if not p_text:
        first_p = soup.find("p")
        p_text = _find_first_visible_text(first_p)

    if not p_text:
        p_text = NO_SUBTEXT

    # ── 3. CTA — cascading fallback ──────────────────────────
    #    Priority: short <a> text → <button> → any <a>
    cta_text = ""

    # Priority A: first <a> with short, non-empty text (likely a CTA)
    for a_tag in soup.find_all("a"):
        candidate = _find_first_visible_text(a_tag)
        if candidate and 2 <= len(candidate) <= 60:
            cta_text = candidate
            break

    # Priority B: first <button> element
    if not cta_text:
        for btn_tag in soup.find_all("button"):
            candidate = _find_first_visible_text(btn_tag)
            if candidate and 2 <= len(candidate) <= 60:
                cta_text = candidate
                break

    # Priority C: any <a> with non-empty text (no length cap)
    if not cta_text:
        for a_tag in soup.find_all("a"):
            candidate = _find_first_visible_text(a_tag)
            if candidate and len(candidate) >= 2:
                cta_text = candidate
                break

    if not cta_text:
        cta_text = NO_CTA

    return {
        "h1": {
            "text": h1_text,
            "char_length": len(h1_text),
        },
        "p": {
            "text": p_text,
            "char_length": len(p_text),
        },
        "a": {
            "text": cta_text,
            "char_length": len(cta_text),
        },
    }


# ══════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════

def extract_dom_data(url: str) -> Dict[str, Any]:
    """
    Component 1 — Main entry point.

    Takes a target URL and returns:
      {
        "url":           str  — normalised URL,
        "raw_html":      str  — full HTML source,
        "jina_text":     str  — clean text via Jina Reader,
        "elements": {
            "h1": {"text": str, "char_length": int},
            "p":  {"text": str, "char_length": int},
            "a":  {"text": str, "char_length": int},
        }
      }

    Raises:
      ValueError          — malformed URL or non-HTML response
      requests.RequestException — network / HTTP errors
    """
    # 1 ▸ Validate & normalise URL
    url = _validate_url(url)

    # 2 ▸ Fetch raw HTML
    raw_html = _fetch_raw_html(url)

    # 3 ▸ Fetch clean text via Jina (non-blocking on failure)
    jina_text = _fetch_jina_text(url)

    # 4 ▸ Parse & extract key elements (html.parser for max compatibility)
    soup = BeautifulSoup(raw_html, "html.parser")
    elements = _extract_key_elements(soup, jina_text=jina_text)

    # 5 ▸ Sanity check — warn if H1 is empty (may indicate SPA/JS-rendered page)
    if not elements["h1"]["text"]:
        logger.warning(
            "No <h1> found on %s — page may be client-side rendered. "
            "Falling back to Jina text for context.",
            url,
        )

    return {
        "url": url,
        "raw_html": raw_html,
        "jina_text": jina_text,
        "elements": elements,
    }
