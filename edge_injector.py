"""
╔══════════════════════════════════════════════════════════════════╗
║  COMPONENT 6 — The Edge Injector                               ║
║  Injects a <base> tag for CSS fidelity and a MutationObserver  ║
║  script that continuously swaps target element text with the    ║
║  AI-generated mutations.                                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import logging
from typing import Dict, Any
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup, Comment

# ──────────────────────────────────────────────────────────
# Module-level logger
# ──────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)


def _compute_base_href(target_url: str) -> str:
    """
    Derives a proper base href from the target URL.
    Strips the path and query, keeping only scheme + netloc + trailing slash.

    Example:
        https://example.com/pricing?ref=ad  →  https://example.com/
    """
    parsed = urlparse(target_url)
    # Keep up to the last '/' in the path for relative resource resolution
    base_path = parsed.path.rsplit("/", 1)[0] + "/" if "/" in parsed.path else "/"
    return f"{parsed.scheme}://{parsed.netloc}{base_path}"


def _build_mutation_script(verified_json: Dict[str, Any]) -> str:
    """
    Generates the JavaScript MutationObserver script that will be
    injected into the <body> of the proxied HTML.

    The script:
      1. Parses the verified mutations JSON.
      2. Defines an `applyMutations()` function that querySelector's
         each target element and replaces its innerText.
      3. Runs `applyMutations()` immediately on DOMContentLoaded.
      4. Sets up a MutationObserver on <body> to re-apply mutations
         whenever the DOM changes (handles lazy-loading, SPA hydration).
      5. Self-terminates after 15 seconds to avoid infinite loops.
    """

    # Serialise the mutations to a JS-safe JSON string
    mutations_json_str = json.dumps(verified_json["mutations"], ensure_ascii=False)

    return f"""
<script data-injector="dynamic-dom-weaver">
(function() {{
    'use strict';

    // ── Mutation payload (injected by Python) ──────────
    var MUTATIONS = {mutations_json_str};

    // ── Track applied mutations for idempotency ────────
    var applied = {{}};

    /**
     * Applies text mutations to matched DOM elements.
     * Uses querySelector to find the FIRST matching element
     * for each selector.
     */
    function applyMutations() {{
        MUTATIONS.forEach(function(mut) {{
            // Skip if already applied with same text
            if (applied[mut.selector] === mut.new_text) return;

            var el = document.querySelector(mut.selector);
            if (el) {{
                // Store original for debugging
                if (!el.dataset.originalText) {{
                    el.dataset.originalText = el.innerText;
                }}

                el.innerText = mut.new_text;
                applied[mut.selector] = mut.new_text;

                console.log(
                    '[DOM Weaver] Mutated <' + mut.selector + '>:',
                    el.dataset.originalText, '→', mut.new_text
                );
            }}
        }});
    }}

    // ── Initial application on DOM ready ───────────────
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', applyMutations);
    }} else {{
        applyMutations();
    }}

    // ── MutationObserver for late-rendering elements ───
    var observer = new MutationObserver(function(mutationsList) {{
        applyMutations();
    }});

    // Start observing once body is available
    function startObserver() {{
        if (document.body) {{
            observer.observe(document.body, {{
                childList: true,
                subtree: true,
                characterData: true
            }});
        }} else {{
            // Body not yet available — retry
            setTimeout(startObserver, 50);
        }}
    }}
    startObserver();

    // ── Self-destruct timer (prevent infinite looping) ─
    setTimeout(function() {{
        observer.disconnect();
        console.log('[DOM Weaver] Observer disconnected after timeout.');
    }}, 15000);

}})();
</script>
"""


def _inject_base_tag(soup: BeautifulSoup, target_url: str) -> None:
    """
    Injects or updates the <base href="..."> tag in the <head>.
    This ensures all relative CSS, JS, and image paths resolve
    correctly against the original domain.
    """
    base_href = _compute_base_href(target_url)

    # Check if a <head> exists; create if missing
    head = soup.find("head")
    if head is None:
        head = soup.new_tag("head")
        if soup.html:
            soup.html.insert(0, head)
        else:
            soup.insert(0, head)

    # Remove any existing <base> to avoid conflicts
    existing_base = head.find("base")
    if existing_base:
        existing_base.decompose()

    # Create and prepend new <base> tag (must be first in <head>)
    base_tag = soup.new_tag("base", href=base_href)
    head.insert(0, base_tag)

    logger.info("Injected <base href='%s'>", base_href)


def _inject_meta_csp_override(soup: BeautifulSoup) -> None:
    """
    Injects a permissive Content-Security-Policy meta tag to prevent
    the proxied page's CSP from blocking our injected script.

    This is necessary because some pages set strict CSP headers that
    would block inline scripts.
    """
    head = soup.find("head")
    if head is None:
        return

    # Remove any existing CSP meta tags
    for meta in head.find_all("meta", attrs={"http-equiv": "Content-Security-Policy"}):
        meta.decompose()

    # We intentionally do NOT inject a new one — we rely on the
    # Streamlit iframe sandbox being permissive enough. This function
    # only removes blocking CSPs from the original page.
    logger.info("Cleared existing CSP meta tags (if any).")


# ══════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════

def inject_and_render(
    raw_html: str,
    target_url: str,
    verified_json: Dict[str, Any],
) -> str:
    """
    Component 6 — Main entry point.

    Takes the raw HTML, injects a <base> tag for asset resolution,
    clears restrictive CSP headers, and appends a MutationObserver
    script that applies the verified text mutations.

    Args:
        raw_html:       The full HTML string from Component 1.
        target_url:     The original URL (for <base href>).
        verified_json:  The hallucination-verified mutations dict
                        from Component 4 (shape: {"mutations": [...]}).

    Returns:
        str — the modified HTML string, ready for rendering
              via `st.components.v1.html()`.

    Note:
        We deliberately do NOT strip native <script> tags from the
        original page — the spec requires preserving them.
    """

    # ── 1. Parse the raw HTML ────────────────────────────
    soup = BeautifulSoup(raw_html, "html.parser")

    # ── 2. Inject <base href> for CSS/asset fidelity ─────
    _inject_base_tag(soup, target_url)

    # ── 3. Clear restrictive CSP meta tags ───────────────
    _inject_meta_csp_override(soup)

    # ── 4. Build and inject the MutationObserver script ──
    mutation_script = _build_mutation_script(verified_json)

    # Ensure <body> exists
    body = soup.find("body")
    if body is None:
        body = soup.new_tag("body")
        if soup.html:
            soup.html.append(body)
        else:
            soup.append(body)

    # Append script at the very end of <body>
    # (BeautifulSoup needs us to parse the script as a fragment)
    script_soup = BeautifulSoup(mutation_script, "html.parser")
    script_tag = script_soup.find("script")
    if script_tag:
        body.append(script_tag)

    # ── 5. Add a debug comment for traceability ──────────
    comment = Comment(" Dynamic DOM Weaver — AI-personalized landing page ")
    if soup.html:
        soup.html.insert(0, comment)

    # ── 6. Serialise and return ──────────────────────────
    modified_html = str(soup)
    logger.info(
        "Edge injection complete. Output size: %d chars", len(modified_html)
    )

    return modified_html
