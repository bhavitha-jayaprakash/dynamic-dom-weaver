"""
╔══════════════════════════════════════════════════════════════════╗
║  COMPONENT 1 — The Ingestion & DOM Extractor                    ║
║  Fetches raw HTML, extracts clean text via Jina Reader, and     ║
║  isolates the first H1, its adjacent P, and the first CTA (A). ║
║  Stamps found tags with `data-troopod-target` attributes for    ║
║  exact downstream targeting by Component 6.                     ║
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

# Data-attribute selectors used throughout the pipeline
SELECTOR_HEADLINE    = '[data-troopod-target="headline"]'
SELECTOR_SUBHEADLINE = '[data-troopod-target="subheadline"]'
SELECTOR_CTA         = '[data-troopod-target="cta"]'


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


def _is_inside_ignorable(tag: Tag) -> bool:
    """
    Returns True if any ancestor of `tag` matches common non-content
    zones (navigation, header chrome, footer, utility widgets).
    """
    ignorable_patterns = re.compile(
        r"nav|header|footer|cart-widget|login|utility", re.IGNORECASE
    )
    for parent in tag.parents:
        if parent.name and parent.name in ("nav", "header", "footer"):
            return True
        parent_classes = " ".join(parent.get("class", []))
        parent_id = parent.get("id", "")
        if ignorable_patterns.search(parent_classes) or ignorable_patterns.search(parent_id):
            return True
    return False


def _extract_key_elements(soup: BeautifulSoup, jina_text: str = "") -> Dict[str, Any]:
    """
    Extracts the three critical DOM strings with aggressive fallback chains
    and negative exclusion rules to avoid nav/header/footer noise:

      1. Headline:  Prioritise <h1> inside <main> or product-details/info
                    containers, then fall back to whole-page <h1> → <h2> → etc.
      2. Subtext:   p adjacent to headline → first p on page
      3. CTA:       Explicit e-commerce patterns ("Add to Cart", "Buy Now",
                    "Pre-order") inside <button>/<a> outside ignorable zones
                    → short <a> outside ignorable zones → any <button>

    For each, we store the original text, its character length, and the
    exact CSS selector (using data-troopod-target attributes) so
    Component 6 can target the precise node.

    If a node cannot be found at all, a clear sentinel string is stored
    (e.g., "No Headline Found") so the AI knows to skip that mutation.
    """

    # ── Sentinel strings (passed to AI when extraction fails) ──
    NO_HEADLINE = "No Headline Found"
    NO_SUBTEXT  = "No Subheadline Found"
    NO_CTA      = "No CTA Button Found"

    # Regex to match common hero/title class names
    hero_pattern = re.compile(r"hero|title|header|banner|headline|heading", re.IGNORECASE)

    # Regex to match product-detail containers (React / e-commerce sites)
    product_zone_pattern = re.compile(r"product-details|product-info", re.IGNORECASE)

    # Regex to match explicit e-commerce CTA text
    cta_text_pattern = re.compile(r"add to cart|buy now|pre-order", re.IGNORECASE)

    # ── 1. Headline — priority zones then aggressive fallback ─
    robust_h1_tag = None

    # Priority A: <h1> inside a <main> tag
    main_tag = soup.find("main")
    if main_tag is not None:
        robust_h1_tag = main_tag.find("h1")

    # Priority B: <h1> inside a product-details/product-info container
    if robust_h1_tag is None:
        product_container = soup.find(class_=product_zone_pattern)
        if product_container is not None:
            robust_h1_tag = product_container.find("h1")

    # Priority C: any <h1> on the whole page
    if robust_h1_tag is None:
        robust_h1_tag = soup.find("h1")

    if robust_h1_tag is None:
        # Fallback D: <h2> with a class hinting at hero/title/header
        robust_h1_tag = soup.find("h2", class_=hero_pattern)

    if robust_h1_tag is None:
        # Fallback E: any <h2>
        robust_h1_tag = soup.find("h2")

    if robust_h1_tag is None:
        # Fallback F: any <h3>
        robust_h1_tag = soup.find("h3")

    if robust_h1_tag is None:
        # Fallback G: <div> or <span> with a class containing
        # title/hero/header/heading (common in React/SPA sites)
        for tag_name in ("div", "span"):
            robust_h1_tag = soup.find(tag_name, class_=hero_pattern)
            if robust_h1_tag:
                break

    h1_text = _find_first_visible_text(robust_h1_tag)

    if not h1_text:
        # Fallback H (last resort): use the first 60 characters of
        # the Jina Reader clean text to give the AI some context
        if jina_text:
            h1_text = jina_text.strip()[:60]
            logger.info("Using Jina text snippet as headline fallback: '%s'", h1_text)
        else:
            h1_text = NO_HEADLINE

    # ── 2. Adjacent P (sibling or first P after headline) ─────
    p_tag = None
    p_text = ""
    if robust_h1_tag is not None:
        # Strategy A: next <p> sibling of the headline tag
        next_p = robust_h1_tag.find_next_sibling("p")
        if next_p:
            p_tag = next_p
            p_text = _find_first_visible_text(next_p)

        # Strategy B: first <p> anywhere after the headline in
        # document order
        if not p_text:
            next_p = robust_h1_tag.find_next("p")
            if next_p:
                p_tag = next_p
                p_text = _find_first_visible_text(next_p)

    # Fallback: grab the first <p> on the page
    if not p_text:
        first_p = soup.find("p")
        if first_p:
            p_tag = first_p
            p_text = _find_first_visible_text(first_p)

    if not p_text:
        p_text = NO_SUBTEXT

    # ── 3. CTA — semantic e-commerce targeting ───────────────
    robust_cta_tag = None
    cta_text = ""

    # Priority A: explicit e-commerce CTA text ("Add to Cart", etc.)
    # inside <button> or <a>, excluding nav/header/footer zones
    for tag in soup.find_all(["button", "a"]):
        candidate = _find_first_visible_text(tag)
        if candidate and cta_text_pattern.search(candidate):
            if not _is_inside_ignorable(tag):
                robust_cta_tag = tag
                cta_text = candidate
                logger.info("CTA matched via e-commerce pattern: '%s'", cta_text)
                break

    # Priority B: first short <a> outside ignorable zones
    if not cta_text:
        for a_tag in soup.find_all("a"):
            if _is_inside_ignorable(a_tag):
                continue
            candidate = _find_first_visible_text(a_tag)
            if candidate and 2 <= len(candidate) <= 60:
                robust_cta_tag = a_tag
                cta_text = candidate
                break

    # Priority C: first <button> element outside ignorable zones
    if not cta_text:
        for btn_tag in soup.find_all("button"):
            if _is_inside_ignorable(btn_tag):
                continue
            candidate = _find_first_visible_text(btn_tag)
            if candidate and 2 <= len(candidate) <= 60:
                robust_cta_tag = btn_tag
                cta_text = candidate
                break

    # Priority D (last resort): any <a> with non-empty text
    if not cta_text:
        for a_tag in soup.find_all("a"):
            candidate = _find_first_visible_text(a_tag)
            if candidate and len(candidate) >= 2:
                robust_cta_tag = a_tag
                cta_text = candidate
                break

    if not cta_text:
        cta_text = NO_CTA

    # ──────────────────────────────────────────────────────
    #  DATA ATTRIBUTE STAMPING
    #  Inject data-troopod-target attributes into the actual
    #  BeautifulSoup tags so the raw_html serialisation carries
    #  them. Component 6 uses these exact selectors to mutate
    #  the correct nodes — no more guessing with generic tags.
    # ──────────────────────────────────────────────────────
    if robust_h1_tag:
        robust_h1_tag['data-troopod-target'] = 'headline'
        logger.info("Stamped data-troopod-target='headline' on <%s>", robust_h1_tag.name)

    if p_tag:
        p_tag['data-troopod-target'] = 'subheadline'
        logger.info("Stamped data-troopod-target='subheadline' on <%s>", p_tag.name)

    if robust_cta_tag:
        robust_cta_tag['data-troopod-target'] = 'cta'
        logger.info("Stamped data-troopod-target='cta' on <%s>", robust_cta_tag.name)

    return {
        "h1": {
            "text": h1_text,
            "char_length": len(h1_text),
            "selector": SELECTOR_HEADLINE,
        },
        "p": {
            "text": p_text,
            "char_length": len(p_text),
            "selector": SELECTOR_SUBHEADLINE,
        },
        "a": {
            "text": cta_text,
            "char_length": len(cta_text),
            "selector": SELECTOR_CTA,
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
        "raw_html":      str  — full HTML source (with data-troopod-target
                                attributes stamped on found nodes),
        "jina_text":     str  — clean text via Jina Reader,
        "elements": {
            "h1": {"text": str, "char_length": int, "selector": str},
            "p":  {"text": str, "char_length": int, "selector": str},
            "a":  {"text": str, "char_length": int, "selector": str},
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
    #     This also stamps data-troopod-target attributes into the soup.
    soup = BeautifulSoup(raw_html, "html.parser")
    elements = _extract_key_elements(soup, jina_text=jina_text)

    # 5 ▸ Re-serialise HTML WITH the data-troopod-target stamps
    stamped_html = str(soup)

    # 6 ▸ Sanity check — warn if H1 is empty (may indicate SPA/JS-rendered page)
    if not elements["h1"]["text"]:
        logger.warning(
            "No <h1> found on %s — page may be client-side rendered. "
            "Falling back to Jina text for context.",
            url,
        )

    return {
        "url": url,
        "raw_html": stamped_html,
        "jina_text": jina_text,
        "elements": elements,
    }
