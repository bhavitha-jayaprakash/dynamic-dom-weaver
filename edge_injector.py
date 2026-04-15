"""
╔══════════════════════════════════════════════════════════════════╗
║  COMPONENT 6 — The Edge Injector (Hybrid V4)                   ║
║  Injects a <base> tag for CSS fidelity, absolutifies relative  ║
║  URLs for iframe interactivity, injects a network interceptor  ║
║  for client-side API calls (cart/add.js etc.), and appends a   ║
║  hybrid script that performs:                                    ║
║    1. Shimmer CSS + animated gradient banner                    ║
║    2. Top announcement banner with gradient-pan animation       ║
║    3. Animated shimmer badge next to the H1                     ║
║    4. Non-destructive text mutation via data-troopod-target     ║
║       selectors and replaceTextSafely()                         ║
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
    base_path = parsed.path.rsplit("/", 1)[0] + "/" if "/" in parsed.path else "/"
    return f"{parsed.scheme}://{parsed.netloc}{base_path}"


def _compute_origin(target_url: str) -> str:
    """
    Derives the origin (scheme + netloc + trailing slash) from target_url.
    Used by the network interceptor to redirect relative API calls.

    Example:
        https://www.example.com/product-page/shoes  →  https://www.example.com/
    """
    parsed = urlparse(target_url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def _absolutify_urls(soup: BeautifulSoup, target_url: str) -> int:
    """
    Converts relative URLs in href, src, action, and srcset attributes to
    fully qualified absolute URLs using the target_url as the base.

    This is critical for iframe interactivity — buttons, links, forms,
    and resource loads must route to the live server, not the local
    Streamlit host.

    Returns the count of URLs rewritten.
    """
    count = 0

    # ── Un-lazy SPAs ─────────────────────────────────────
    for tag in soup.find_all(["img", "source"]):
        if tag.get("loading") == "lazy":
            del tag["loading"]

        for attr in ["data-src", "data-srcset", "data-lazy-src"]:
            val = tag.get(attr)
            if val:
                if attr == "data-srcset":
                    new_entries = []
                    for entry in val.split(","):
                        entry = entry.strip()
                        if not entry: continue
                        parts = entry.split()
                        url_part = parts[0]
                        descriptor = " ".join(parts[1:]) if len(parts) > 1 else ""
                        if not url_part.startswith(("http://", "https://", "data:")):
                            url_part = urljoin(target_url, url_part)
                        new_entries.append(f"{url_part} {descriptor}".strip())
                    tag["srcset"] = ", ".join(new_entries)
                else:
                    if not val.startswith(("http://", "https://", "data:")):
                        val = urljoin(target_url, val)
                    tag["src"] = val
                count += 1


    # ── Standard single-value attributes ─────────────────
    tag_attr_map = [
        ("a",      "href"),
        ("link",   "href"),
        ("img",    "src"),
        ("img",    "data-src"),
        ("script", "src"),
        ("form",   "action"),
        ("source", "src"),
        ("video",  "src"),
        ("audio",  "src"),
        ("iframe", "src"),
    ]

    for tag_name, attr in tag_attr_map:
        for tag in soup.find_all(tag_name):
            value = tag.get(attr)
            if not value:
                continue
            # Skip data URIs, anchors, javascript:, and already-absolute URLs
            if value.startswith(("http://", "https://", "data:", "javascript:", "#", "mailto:")):
                continue
            absolute_url = urljoin(target_url, value)
            tag[attr] = absolute_url
            count += 1

    # ── srcset attributes (source, img) ──────────────────
    # srcset has the format: "url1 1x, url2 2x" or "url1 300w, url2 600w"
    for tag in soup.find_all(["source", "img"]):
        for attr_name in ["srcset", "data-srcset"]:
            srcset = tag.get(attr_name)
            if not srcset:
                continue

            new_entries = []
            modified = False
            for entry in srcset.split(","):
                entry = entry.strip()
                if not entry:
                    continue
                parts = entry.split()
                url_part = parts[0]
                descriptor = " ".join(parts[1:]) if len(parts) > 1 else ""

                if not url_part.startswith(("http://", "https://", "data:")):
                    url_part = urljoin(target_url, url_part)
                    modified = True

                new_entries.append(f"{url_part} {descriptor}".strip())

            if modified:
                tag[attr_name] = ", ".join(new_entries)
                count += 1

    return count


def _build_network_interceptor(target_url: str) -> str:
    """
    Builds the JavaScript network interceptor snippet.

    This intercepts fetch() and XMLHttpRequest.open() to redirect
    relative API paths (e.g., /cart/add.js) to the live target server
    instead of the local Streamlit host.

    MUST be injected at the TOP of <head> before any native scripts run.
    """
    target_base = _compute_origin(target_url)

    return f"""<script data-troopod="network-interceptor">
(function(targetBaseUrl) {{
    // 1. Intercept Fetch API
    var originalFetch = window.fetch;
    window.fetch = function() {{
        var args = Array.prototype.slice.call(arguments);
        if (typeof args[0] === 'string' && args[0].startsWith('/')) {{
            args[0] = targetBaseUrl + args[0].substring(1);
        }}
        return originalFetch.apply(this, args);
    }};

    // 2. Intercept XHR (XMLHttpRequest)
    var originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {{
        if (typeof url === 'string' && url.startsWith('/')) {{
            url = targetBaseUrl + url.substring(1);
        }}
        var newArgs = Array.prototype.slice.call(arguments);
        newArgs[1] = url;
        return originalOpen.apply(this, newArgs);
    }};

    console.log('[DOM Weaver V4] Network interceptor active — redirecting API calls to:', targetBaseUrl);
}})('{target_base}');
</script>"""


def _build_hybrid_v4_script(verified_json: Dict[str, Any]) -> str:
    """
    Generates the JavaScript payload for Hybrid V4 injection.

    The script performs FOUR operations:
      1. SHIMMER CSS + GRADIENT-PAN — Injects a <style> block with CSS
         custom properties, shimmer animation for the badge, and a
         gradient-pan animation for the banner.
      2. BANNER — Creates an animated gradient banner at the top of page.
      3. SHIMMER BADGE — Creates a shimmer-animated badge using
         insertAdjacentElement('afterend') after the matched headline.
      4. SAFE TEXT MUTATION — Uses replaceTextSafely() to update text
         nodes without destroying SVGs, icons, or button HTML layout.
         Targets nodes via data-troopod-target attribute selectors.
    """

    mutations_json_str = json.dumps(
        verified_json.get("mutations", []), ensure_ascii=False
    )

    injections = verified_json.get("injections", {})
    banner_text = json.dumps(injections.get("banner_text", ""), ensure_ascii=False)
    badge_text = json.dumps(injections.get("badge_text", ""), ensure_ascii=False)

    colors = verified_json.get("colors", {})
    color_primary = json.dumps(colors.get("primary", "#7B2FF7"), ensure_ascii=False)
    color_secondary = json.dumps(colors.get("secondary", "#00D2FF"), ensure_ascii=False)

    return f"""
<script data-injector="dynamic-dom-weaver-v4">
(function() {{
    'use strict';

    // ── Payload (injected by Python) ────────────────────
    var MUTATIONS       = {mutations_json_str};
    var BANNER_TEXT     = {banner_text};
    var BADGE_TEXT      = {badge_text};
    var COLOR_PRIMARY   = {color_primary};
    var COLOR_SECONDARY = {color_secondary};

    // ── Track applied mutations for idempotency ─────────
    var applied = {{}};

    // ═══════════════════════════════════════════════════
    //  Step 1 — Inject shimmer CSS + gradient-pan animation
    // ═══════════════════════════════════════════════════
    function injectStyles() {{
        if (document.getElementById('troopod-styles')) return;

        var style = document.createElement('style');
        style.id = 'troopod-styles';
        style.textContent = [
            ':root {{',
            '  --color-primary: ' + COLOR_PRIMARY + ';',
            '  --color-secondary: ' + COLOR_SECONDARY + ';',
            '}}',
            '',
            '/* Badge shimmer animation */',
            '@keyframes troopod-shimmer {{',
            '  0% {{ background-position: -200% center; }}',
            '  100% {{ background-position: 200% center; }}',
            '}}',
            '',
            '/* Banner gradient pan animation */',
            '@keyframes troopod-gradient-pan {{',
            '  0% {{ background-position: 0% 50%; }}',
            '  50% {{ background-position: 100% 50%; }}',
            '  100% {{ background-position: 0% 50%; }}',
            '}}',
            '',
            '.troopod-badge {{',
            '  background: linear-gradient(90deg, var(--color-primary) 0%, var(--color-secondary) 50%, var(--color-primary) 100%);',
            '  background-size: 200% auto;',
            '  animation: troopod-shimmer 3s linear infinite;',
            '  color: white;',
            '  padding: 0.25em 0.6em;',
            '  border-radius: 0.4em;',
            '  font-size: 0.65em;',
            '  margin-left: 0.5em;',
            '  vertical-align: middle;',
            '  display: inline-block;',
            '  white-space: nowrap;',
            '  font-weight: 700;',
            '  box-shadow: 0 4px 12px rgba(0,0,0,0.15);',
            '}}',
            '',
            '.troopod-banner {{',
            '  background: linear-gradient(270deg, var(--color-primary), var(--color-secondary), var(--color-primary));',
            '  background-size: 200% 200%;',
            '  animation: troopod-gradient-pan 6s ease infinite;',
            '  color: white;',
            '  text-align: center;',
            '  padding: 12px;',
            '  font-weight: bold;',
            '  width: 100%;',
            '  box-sizing: border-box;',
            '  position: relative;',
            '  z-index: 99999;',
            '  font-family: Inter, system-ui, -apple-system, sans-serif;',
            '  font-size: 14px;',
            '  letter-spacing: 0.03em;',
            '  box-shadow: 0 2px 10px rgba(0,0,0,0.1);',
            '}}'
        ].join('\\n');

        var head = document.head || document.getElementsByTagName('head')[0];
        if (head) {{
            head.appendChild(style);
            console.log('[DOM Weaver V4] Shimmer + gradient-pan styles injected.');
        }}
    }}

    // ═══════════════════════════════════════════════════
    //  Step 2 — Inject animated gradient banner at top
    // ═══════════════════════════════════════════════════
    function injectBanner() {{
        if (!BANNER_TEXT || document.getElementById('troopod-banner')) return;

        var banner = document.createElement('div');
        banner.id = 'troopod-banner';
        banner.className = 'troopod-banner';
        banner.textContent = BANNER_TEXT;

        document.body.prepend(banner);
        console.log('[DOM Weaver V4] Animated banner injected:', BANNER_TEXT);
    }}

    // ═══════════════════════════════════════════════════
    //  Step 3 — Inject shimmer badge after headline
    // ═══════════════════════════════════════════════════
    function injectBadge() {{
        if (!BADGE_TEXT || document.getElementById('troopod-badge')) return;

        // Target the exact stamped headline node
        var headline = document.querySelector('[data-troopod-target="headline"]');
        if (!headline) {{
            // Fallback to generic h1 if stamp missing
            headline = document.querySelector('h1');
        }}
        if (!headline) return;

        var badge = document.createElement('span');
        badge.id = 'troopod-badge';
        badge.className = 'troopod-badge';
        badge.innerText = BADGE_TEXT;

        headline.insertAdjacentElement('afterend', badge);
        console.log('[DOM Weaver V4] Shimmer badge injected after headline:', BADGE_TEXT);
    }}

    // ═══════════════════════════════════════════════════
    //  Step 4 — Safe text mutation (preserves button HTML)
    // ═══════════════════════════════════════════════════

    /**
     * Replaces the text content of an element without destroying
     * child elements (SVGs, icons, spans, flexbox layout).
     *
     * Strategy: iterate over element.childNodes, collect all
     * TEXT_NODE (nodeType === 3) with non-empty trimmed text,
     * then update the nodeValue of the LONGEST text node.
     * This preserves icons, spans, and event listeners.
     */
    function replaceTextSafely(element, newText) {{
        var originalColor = window.getComputedStyle(element).color;
        var textNodes = [];
        for (var i = 0; i < element.childNodes.length; i++) {{
            var node = element.childNodes[i];
            if (node.nodeType === 3) {{  // Node.TEXT_NODE
                var trimmed = node.nodeValue.trim();
                if (trimmed.length > 0) {{
                    textNodes.push({{ node: node, length: trimmed.length }});
                }}
            }}
        }}

        if (textNodes.length > 0) {{
            // Sort by length descending, pick the largest text node
            textNodes.sort(function(a, b) {{ return b.length - a.length; }});
            textNodes[0].node.nodeValue = newText;
            return true;
        }}

        var coloredSpan = '<span style="color: ' + originalColor + ' !important;">' + newText + '</span>';

        // Fallback: no direct text nodes found — try first-level children
        // that are inline elements (span, strong, em, b, i)
        var inlineTags = ['SPAN', 'STRONG', 'EM', 'B', 'I'];
        for (var j = 0; j < element.children.length; j++) {{
            var child = element.children[j];
            if (inlineTags.indexOf(child.tagName) !== -1 && child.textContent.trim()) {{
                child.innerHTML = coloredSpan;
                return true;
            }}
        }}

        // Last resort — only if element has no complex children
        if (element.children.length === 0) {{
            element.innerHTML = coloredSpan;
            return true;
        }}

        // Truly complex element — prepend a text node (but use our span)
        var tempDiv = document.createElement('div');
        tempDiv.innerHTML = coloredSpan;
        element.insertBefore(tempDiv.firstChild, element.firstChild);
        return true;
    }}

    function applyMutations() {{
        MUTATIONS.forEach(function(mut) {{
            if (applied[mut.selector] === mut.new_text) return;

            var el = document.querySelector(mut.selector);
            if (el) {{
                if (!el.dataset.originalText) {{
                    el.dataset.originalText = el.innerText;
                }}

                replaceTextSafely(el, mut.new_text);
                applied[mut.selector] = mut.new_text;

                console.log(
                    '[DOM Weaver V4] Mutated ' + mut.selector + ':',
                    el.dataset.originalText, '→', mut.new_text
                );
            }} else {{
                console.warn('[DOM Weaver V4] Selector not found:', mut.selector);
            }}
        }});
    }}

    // ═══════════════════════════════════════════════════
    //  Orchestration
    // ═══════════════════════════════════════════════════
    function run() {{
        injectStyles();
        injectBanner();
        applyMutations();
        injectBadge();
    }}

    // ── Initial application on DOM ready ───────────────
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', run);
    }} else {{
        run();
    }}

    // ── MutationObserver for late-rendering SPAs ───────
    var observer = new MutationObserver(function() {{
        run();
    }});

    function startObserver() {{
        if (document.body) {{
            observer.observe(document.body, {{
                childList: true,
                subtree: true,
                characterData: true
            }});
        }} else {{
            setTimeout(startObserver, 50);
        }}
    }}
    startObserver();

    // ── Self-destruct timer ────────────────────────────
    setTimeout(function() {{
        observer.disconnect();
        console.log('[DOM Weaver V4] Observer disconnected after timeout.');
    }}, 15000);

}})();
</script>
"""


def _inject_base_tag(soup: BeautifulSoup, target_url: str) -> None:
    """
    Injects or updates the <base href="..."> tag as the FIRST element
    inside the <head>. This ensures all relative CSS, JS, and image
    paths resolve correctly against the original domain.
    """
    base_href = _compute_base_href(target_url)

    head = soup.find("head")
    if head is None:
        head = soup.new_tag("head")
        if soup.html:
            soup.html.insert(0, head)
        else:
            soup.insert(0, head)

    existing_base = head.find("base")
    if existing_base:
        existing_base.decompose()

    base_tag = soup.new_tag("base", href=base_href)
    head.insert(0, base_tag)

    logger.info("Injected <base href='%s'> as first <head> child.", base_href)


def _inject_network_interceptor(soup: BeautifulSoup, target_url: str) -> None:
    """
    Injects the fetch/XHR network interceptor script at the TOP of <head>,
    immediately after the <base> tag but BEFORE any native scripts.

    This ensures that all relative API calls (e.g., /cart/add.js,
    /api/variants) are redirected to the live target server instead of
    hitting the local Streamlit host.
    """
    head = soup.find("head")
    if head is None:
        return

    interceptor_html = _build_network_interceptor(target_url)
    interceptor_soup = BeautifulSoup(interceptor_html, "html.parser")
    interceptor_tag = interceptor_soup.find("script")

    if interceptor_tag:
        # Insert after <base> (position 1) so it runs before native scripts
        # but after the base href is established
        base_tag = head.find("base")
        if base_tag:
            base_tag.insert_after(interceptor_tag)
        else:
            head.insert(0, interceptor_tag)

        logger.info("Injected network interceptor (fetch + XHR) for: %s",
                     _compute_origin(target_url))


def _inject_meta_csp_override(soup: BeautifulSoup) -> None:
    """
    Removes restrictive Content-Security-Policy meta tags to prevent
    the proxied page's CSP from blocking our injected script.
    """
    head = soup.find("head")
    if head is None:
        return

    for meta in head.find_all("meta", attrs={"http-equiv": "Content-Security-Policy"}):
        meta.decompose()

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
    Component 6 — Main entry point (Hybrid V4).

    Takes the raw HTML (with data-troopod-target stamps from C1),
    absolutifies relative URLs for iframe interactivity, injects a
    <base> tag for asset resolution, a network interceptor for API
    call redirection, clears restrictive CSP headers, and appends a
    Hybrid V4 script that performs:
      - Shimmer CSS + gradient-pan banner animation
      - Top announcement banner with animated gradient
      - Animated shimmer badge after the stamped headline
      - Non-destructive text mutation via replaceTextSafely()

    Args:
        raw_html:       The full HTML string from Component 1
                        (already contains data-troopod-target stamps).
        target_url:     The original URL (for <base href> and
                        URL absolutification).
        verified_json:  The hallucination-verified dict from C4
                        with shape:
                        {"mutations": [...], "injections": {...},
                         "colors": {"primary": ..., "secondary": ...}}.

    Returns:
        str — the modified HTML string, ready for rendering
              via `st.components.v1.html()`.
    """

    # ── 1. Parse the raw HTML ────────────────────────────
    soup = BeautifulSoup(raw_html, "html.parser")

    # ── 2. Inject <base href> as the FIRST <head> child ──
    _inject_base_tag(soup, target_url)

    # ── 3. Inject network interceptor (fetch + XHR fix) ──
    _inject_network_interceptor(soup, target_url)

    # ── 4. Clear restrictive CSP meta tags ───────────────
    _inject_meta_csp_override(soup)

    # ── 5. Absolutify relative URLs (interactivity fix) ──
    rewritten_count = _absolutify_urls(soup, target_url)
    logger.info("Absolutified %d relative URLs for iframe interactivity.", rewritten_count)

    # ── 6. Build and inject the Hybrid V4 script ─────────
    hybrid_script = _build_hybrid_v4_script(verified_json)

    body = soup.find("body")
    if body is None:
        body = soup.new_tag("body")
        if soup.html:
            soup.html.append(body)
        else:
            soup.append(body)

    script_soup = BeautifulSoup(hybrid_script, "html.parser")
    script_tag = script_soup.find("script")
    if script_tag:
        body.append(script_tag)

    # ── 7. Add a debug comment for traceability ──────────
    comment = Comment(" Dynamic DOM Weaver V4 — AI-personalized landing page (shimmer + gradient-pan + network intercept) ")
    if soup.html:
        soup.html.insert(0, comment)

    # ── 8. Serialise and return ──────────────────────────
    modified_html = str(soup)
    logger.info(
        "Edge injection complete. Output size: %d chars", len(modified_html)
    )

    return modified_html
