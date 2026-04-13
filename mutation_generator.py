"""
╔══════════════════════════════════════════════════════════════════╗
║  COMPONENT 3 & 5 — The Hybrid V3 Optimizer & Formatter        ║
║  Calls the NVIDIA NIM Text model to:                           ║
║    1. Surgically edit H1, P, and CTA text (preserving the      ║
║       original product name AND core CTA utility word).        ║
║    2. Generate a top announcement banner copy.                  ║
║    3. Generate a short badge label for shimmer injection.       ║
║  Uses data-troopod-target attribute selectors for exact node   ║
║  targeting. Passes the two-color gradient palette through.     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import re
import logging
from typing import Dict, Any, List

from openai import OpenAI

import streamlit as st

# ──────────────────────────────────────────────────────────
# Module-level logger
# ──────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────
NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
TEXT_MODEL = "meta/llama-3.2-90b-vision-instruct"

# Character-length tolerance band: allow ±30% of original length
LENGTH_TOLERANCE = 0.30

# Maximum retries for malformed JSON from the LLM
MAX_RETRIES = 3

# The exact CSS selectors used by Component 1's data-attribute stamps.
# These MUST stay in sync with dom_extractor.py constants.
SEL_HEADLINE    = '[data-troopod-target="headline"]'
SEL_SUBHEADLINE = '[data-troopod-target="subheadline"]'
SEL_CTA         = '[data-troopod-target="cta"]'

# ──────────────────────────────────────────────────────────
# The Hybrid V3 system prompt
# ──────────────────────────────────────────────────────────
OPTIMIZER_SYSTEM_PROMPT = """You are a surgical copy-editor and senior conversion-rate-optimization (CRO) copywriter.

Your task is to do THREE things:

A) SURGICALLY EDIT three pieces of text from a landing page so they
   align with a specific promotional offer, while preserving the
   original tone, brand voice, and approximate character length.

B) Write a SHORT BANNER HEADLINE (max 10 words) for a top-of-page
   announcement strip. It should convey urgency, the core offer,
   and the promo code if available.

C) Write a SHORT BADGE LABEL (max 3 words) that will be visually
   injected next to the product headline (e.g., "30% Off", "Limited Offer").

⚠️  CRITICAL — IDENTITY PRESERVATION RULES:
You are a surgical copy-editor.

1. When mutating the HEADLINE, you MUST retain the original product name.
   Only append or neatly integrate the `core_offer`. Do NOT replace the
   product name entirely.
   Example: "Cloudtilt Sneakers" → "Cloudtilt Sneakers — 30% Off" ✅
   Example: "Cloudtilt Sneakers" → "30% Off Everything!" ❌

2. When mutating the CTA BUTTON, you MUST retain the core utility word
   (e.g., "Add to Cart", "Buy", "Shop", "Get"). Do NOT replace the core
   text entirely, only append or seamlessly integrate the new offer text.
   Example: "Add to Cart" → "Add to Cart — Save 30%" ✅
   Example: "Add to Cart" → "Claim Your Discount Now" ❌

You will receive:
- A CORE OFFER (e.g., "30% off annual plans")
- A TAGLINE from the ad creative (e.g., "Scale Without Limits")
- A PROMO CODE if available (e.g., "SAVE30")
- TWO BRAND COLORS (pass these through to the output unchanged)
- Three selectors for the target nodes. Use these exact selectors in your output.

RULES:
1. Preserve the original meaning and structure — only weave in the offer.
2. Do NOT invent numbers, percentages, or dollar amounts that are not in
   the core offer. Use ONLY the exact figures provided.
3. Keep each rewrite within the specified character-length range.
4. Intelligently incorporate the tagline into the HEADLINE or SUBHEADLINE
   rewrite where it fits naturally. Do not force it if unnatural.
5. If a promo code is provided, include it in the banner_text or the
   SUBHEADLINE (e.g., "Use code SAVE30").
6. Make the CTA action-oriented while KEEPING the original utility word.
7. If an original element says "No Headline Found", "No Subheadline Found",
   or "No CTA Button Found", skip it — output its new_text as the same
   sentinel string unchanged.
8. NEVER replace the entire headline with purely promotional text.
9. banner_text MUST be at most 10 words.
10. badge_text MUST be at most 3 words.
11. Pass the colors through to the output JSON exactly as received.
12. Use the EXACT selectors provided for each mutation — do not use generic
    tag names like "h1", "p", or "a".
13. Respond with ONLY valid JSON — no markdown fences, no commentary.

OUTPUT FORMAT (strict JSON, nothing else):
{
  "mutations": [
    {"selector": "[data-troopod-target=\\"headline\\"]", "action": "replaceText", "new_text": "..."},
    {"selector": "[data-troopod-target=\\"subheadline\\"]", "action": "replaceText", "new_text": "..."},
    {"selector": "[data-troopod-target=\\"cta\\"]", "action": "replaceText", "new_text": "..."}
  ],
  "injections": {
    "banner_text": "...",
    "badge_text": "..."
  },
  "colors": {
    "primary": "#XXXXXX",
    "secondary": "#YYYYYY"
  }
}
"""


def _get_nim_client() -> OpenAI:
    """
    Initialises and returns an OpenAI-compatible client pointed
    at the NVIDIA NIM inference endpoint.
    """
    api_key = st.secrets.get("NVIDIA_API_KEY", "")
    if not api_key or api_key == "YOUR_NVIDIA_NIM_API_KEY_HERE":
        raise ValueError(
            "NVIDIA API key is not configured. "
            "Please set `NVIDIA_API_KEY` in `.streamlit/secrets.toml`."
        )

    return OpenAI(
        base_url=NVIDIA_NIM_BASE_URL,
        api_key=api_key,
    )


def _compute_length_bounds(original_length: int) -> Dict[str, int]:
    """
    Computes the acceptable min/max character count for a rewritten
    element, based on the original length ± tolerance.

    Ensures a minimum floor of 5 characters and a ceiling of 500.
    """
    if original_length <= 0:
        return {"min": 5, "max": 80}

    delta = int(original_length * LENGTH_TOLERANCE)
    return {
        "min": max(5, original_length - delta),
        "max": min(500, original_length + delta),
    }


def _build_user_prompt(ad_info: Dict[str, str], elements: Dict[str, Any]) -> str:
    """
    Constructs the user-turn prompt with the full ad context
    (offer, tagline, promo code, two colors) and character-length
    constraints for each element, using data-troopod-target selectors.
    """
    h1_bounds = _compute_length_bounds(elements["h1"]["char_length"])
    p_bounds  = _compute_length_bounds(elements["p"]["char_length"])
    a_bounds  = _compute_length_bounds(elements["a"]["char_length"])

    # Build the ad context block
    ad_context = f'CORE OFFER: "{ad_info["core_offer"]}"\n'
    if ad_info.get("tagline"):
        ad_context += f'TAGLINE: "{ad_info["tagline"]}"\n'
    if ad_info.get("promo_code"):
        ad_context += f'PROMO CODE: "{ad_info["promo_code"]}"\n'

    color_primary = ad_info.get("color_primary_hex", "#7B2FF7")
    color_secondary = ad_info.get("color_secondary_hex", "#00D2FF")
    ad_context += f'COLOR PRIMARY: "{color_primary}"\n'
    ad_context += f'COLOR SECONDARY: "{color_secondary}"\n'

    h1_sel = elements["h1"].get("selector", SEL_HEADLINE)
    p_sel  = elements["p"].get("selector", SEL_SUBHEADLINE)
    a_sel  = elements["a"].get("selector", SEL_CTA)

    return (
        f"{ad_context}\n"
        f"--- ORIGINAL LANDING PAGE ELEMENTS ---\n\n"
        f"1. HEADLINE (selector: {h1_sel}):\n"
        f"   Original text: \"{elements['h1']['text']}\"\n"
        f"   Original length: {elements['h1']['char_length']} chars\n"
        f"   ⚠️ New text MUST be between {h1_bounds['min']} and {h1_bounds['max']} characters.\n"
        f"   ⚠️ You MUST keep the original product name in the headline.\n\n"
        f"2. SUBHEADLINE (selector: {p_sel}):\n"
        f"   Original text: \"{elements['p']['text']}\"\n"
        f"   Original length: {elements['p']['char_length']} chars\n"
        f"   ⚠️ New text MUST be between {p_bounds['min']} and {p_bounds['max']} characters.\n\n"
        f"3. CTA BUTTON (selector: {a_sel}):\n"
        f"   Original text: \"{elements['a']['text']}\"\n"
        f"   Original length: {elements['a']['char_length']} chars\n"
        f"   ⚠️ New text MUST be between {a_bounds['min']} and {a_bounds['max']} characters.\n"
        f"   ⚠️ You MUST keep the core utility word (e.g., 'Add to Cart', 'Buy').\n\n"
        f"Rewrite all three elements using the exact selectors above. "
        f"Also generate banner_text (max 10 words) "
        f"and badge_text (max 3 words). Pass colors through unchanged. "
        f"Return ONLY the JSON object."
    )


def _sanitise_json_response(raw: str) -> dict:
    """
    Robustly extracts and parses a JSON object from raw LLM output.

    Handles common model quirks:
      - "Answer: {...}"  or  "Output: {...}"  preambles
      - "**JSON Response:**" or similar markdown headers
      - Markdown code fences (```json ... ```)
      - HTML wrapping (<p>...</p>)
      - Trailing commas before closing braces
      - Leading/trailing whitespace

    Strategy:
      1. Strip markdown code fences and preamble prefixes.
      2. Locate the first '{' and last '}' and parse only
         the text between them.

    Returns the parsed dict.
    Raises ValueError if no JSON object can be found.
    """
    raw = raw.strip()

    # ── Step 1: Strip markdown code fences ─────────────
    raw = re.sub(r"```(?:json|JSON)?\s*", "", raw)
    raw = re.sub(r"```", "", raw)

    # ── Step 2: Strip common preamble prefixes ─────────
    # Matches patterns like "Answer:", "Output:", "Response:",
    # "**JSON Response:**", "Here is the JSON:", etc.
    raw = re.sub(
        r"^(?:\*{0,2}(?:Answer|Output|Response|Result|JSON\s*Response)\s*:?\*{0,2}\s*)+",
        "",
        raw,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    raw = raw.strip()

    # ── Step 3: Locate the JSON object boundaries ──────
    start_idx = raw.find("{")
    end_idx = raw.rfind("}") + 1

    if start_idx == -1 or end_idx == 0:
        raise ValueError(f"No JSON object found in response: {raw}")

    json_str = raw[start_idx:end_idx]

    # ── Step 4: Clean trailing commas ──────────────────
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)

    return json.loads(json_str)


def _normalise_selector(raw_selector: str) -> str:
    """
    Maps LLM-generated selectors (which may be generic tag names)
    back to the correct data-troopod-target attribute selectors.

    This handles the case where the LLM ignores the instruction to
    use attribute selectors and falls back to "h1", "p", "a".
    """
    mapping = {
        "h1": SEL_HEADLINE,
        "p":  SEL_SUBHEADLINE,
        "a":  SEL_CTA,
        "headline": SEL_HEADLINE,
        "subheadline": SEL_SUBHEADLINE,
        "cta": SEL_CTA,
    }
    stripped = raw_selector.strip().lower()
    return mapping.get(stripped, raw_selector.strip())


def _validate_hybrid_v3_schema(
    data: Any,
    fallback_primary: str = "#7B2FF7",
    fallback_secondary: str = "#00D2FF",
) -> Dict[str, Any]:
    """
    Validates and normalises the parsed JSON against the Hybrid V3 schema:
      {
        "mutations": [{"selector": str, "new_text": str}, ...],
        "injections": {"banner_text": str, "badge_text": str},
        "colors": {"primary": str, "secondary": str}
      }

    Returns the validated dict.
    Raises ValueError on schema violations.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")

    # ── Validate mutations array ─────────────────────────
    mutations = data.get("mutations")
    if not isinstance(mutations, list) or len(mutations) == 0:
        raise ValueError("'mutations' key missing or empty.")

    # The canonical set of required data-troopod-target selectors
    required_selectors = {SEL_HEADLINE, SEL_SUBHEADLINE, SEL_CTA}
    found_selectors = set()

    for i, mut in enumerate(mutations):
        if not isinstance(mut, dict):
            raise ValueError(f"Mutation[{i}] is not a dict: {mut}")

        raw_sel = mut.get("selector", "").strip()
        new_text = mut.get("new_text", "").strip()

        if not raw_sel:
            raise ValueError(f"Mutation[{i}] missing 'selector'.")
        if not new_text:
            raise ValueError(f"Mutation[{i}] missing 'new_text'.")

        # Normalise selector to data-troopod-target form
        normalised = _normalise_selector(raw_sel)
        mut["selector"] = normalised
        mut["new_text"] = new_text
        if "action" not in mut:
            mut["action"] = "replaceText"

        found_selectors.add(normalised)

    missing = required_selectors - found_selectors
    if missing:
        raise ValueError(f"Missing mutation(s) for selector(s): {missing}")

    # ── Validate injections ──────────────────────────────
    injections = data.get("injections")
    if not isinstance(injections, dict):
        raise ValueError("'injections' key missing or not an object.")

    banner_text = str(injections.get("banner_text", "")).strip()
    badge_text = str(injections.get("badge_text", "")).strip()

    if not banner_text:
        raise ValueError("'injections.banner_text' is missing or empty.")
    if not badge_text:
        raise ValueError("'injections.badge_text' is missing or empty.")

    # Enforce word-count limits (soft — truncate rather than reject)
    banner_words = banner_text.split()
    if len(banner_words) > 12:
        banner_text = " ".join(banner_words[:10])
        logger.warning("banner_text exceeded 10 words — truncated.")

    badge_words = badge_text.split()
    if len(badge_words) > 5:
        badge_text = " ".join(badge_words[:3])
        logger.warning("badge_text exceeded 3 words — truncated.")

    # ── Validate colors ──────────────────────────────────
    colors = data.get("colors", {})
    if not isinstance(colors, dict):
        colors = {}

    hex_re = re.compile(r"^#[0-9a-fA-F]{6}$")

    primary = str(colors.get("primary", "")).strip()
    if not hex_re.match(primary):
        primary = fallback_primary
        logger.warning("Invalid primary color, using fallback: %s", primary)

    secondary = str(colors.get("secondary", "")).strip()
    if not hex_re.match(secondary):
        secondary = fallback_secondary
        logger.warning("Invalid secondary color, using fallback: %s", secondary)

    return {
        "mutations": mutations,
        "injections": {
            "banner_text": banner_text,
            "badge_text": badge_text,
        },
        "colors": {
            "primary": primary.upper(),
            "secondary": secondary.upper(),
        },
    }


# ══════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════

def generate_mutations(
    ad_info: Dict[str, str],
    dom_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Component 3 & 5 — Main entry point (Hybrid V3).

    Calls the NVIDIA NIM Text model to generate:
      1. Surgical text rewrites for H1, P, and CTA using exact
         data-troopod-target attribute selectors.
      2. A short banner headline for the announcement strip.
      3. A short badge label for shimmer injection.
      4. The two-color gradient palette (passed through from C2).

    Args:
        ad_info:  Dict with keys "core_offer", "tagline", "promo_code",
                  "color_primary_hex", "color_secondary_hex" from C2.
        dom_data: The full dict returned by Component 1's
                  `extract_dom_data()`.

    Returns:
        dict — validated JSON with the Hybrid V3 schema.

    Raises:
        ValueError — after MAX_RETRIES if the model consistently
                     produces malformed output.
    """
    client = _get_nim_client()
    elements = dom_data["elements"]
    user_prompt = _build_user_prompt(ad_info, elements)

    fallback_primary = ad_info.get("color_primary_hex", "#7B2FF7")
    fallback_secondary = ad_info.get("color_secondary_hex", "#00D2FF")

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(
            "Generating hybrid V3 mutations — attempt %d/%d", attempt, MAX_RETRIES
        )

        try:
            response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": OPTIMIZER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,   # deterministic output
                max_tokens=600,
                top_p=1.0,
            )

            raw_text = response.choices[0].message.content
            logger.info("Optimizer raw response (attempt %d): %s", attempt, raw_text)

            # Parse & validate
            parsed = _sanitise_json_response(raw_text)
            result = _validate_hybrid_v3_schema(
                parsed,
                fallback_primary=fallback_primary,
                fallback_secondary=fallback_secondary,
            )

            logger.info("✅ Hybrid V3 mutations generated successfully on attempt %d", attempt)
            return result

        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            logger.warning(
                "Attempt %d failed validation: %s", attempt, exc
            )
            continue

        except Exception as exc:
            logger.error("NVIDIA NIM API call failed: %s", exc)
            raise ValueError(
                f"Failed to reach the NVIDIA NIM Text model.\nError: {exc}"
            ) from exc

    # All retries exhausted
    raise ValueError(
        f"Hybrid V3 mutation generation failed after {MAX_RETRIES} attempts.\n"
        f"Last error: {last_error}"
    )
