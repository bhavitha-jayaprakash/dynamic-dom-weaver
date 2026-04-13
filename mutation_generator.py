"""
╔══════════════════════════════════════════════════════════════════╗
║  COMPONENT 3 & 5 — The Context-Aware Optimizer &               ║
║                     Structured Formatter                        ║
║  Calls the NVIDIA NIM Text model to rewrite H1, P, and CTA     ║
║  text to match the ad's core offer, enforcing character-length  ║
║  constraints from the original DOM elements.                    ║
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

# ──────────────────────────────────────────────────────────
# The mutation-generation system prompt
# ──────────────────────────────────────────────────────────
OPTIMIZER_SYSTEM_PROMPT = """You are a senior conversion-rate-optimization (CRO) copywriter.

Your task is to rewrite three pieces of text from a landing page so they
align with a specific promotional offer, while preserving the original
tone, brand voice, and approximate character length.

You will receive:
- A CORE OFFER (e.g., "30% off annual plans")
- A TAGLINE from the ad creative (e.g., "Scale Without Limits")
- A PROMO CODE if available (e.g., "SAVE30")

RULES:
1. Preserve the original meaning and structure — only weave in the offer.
2. Do NOT invent numbers, percentages, or dollar amounts that are not in
   the core offer. Use ONLY the exact figures provided.
3. Keep each rewrite within the specified character-length range.
4. Intelligently incorporate the tagline into the H1 or P rewrite where
   it fits naturally. Do not force it if unnatural.
5. If a promo code is provided, include it in the CTA button text or the
   P subheadline (e.g., "Use code SAVE30").
6. Make the CTA (button text) action-oriented and urgent.
7. If an original element says "No Headline Found", "No Subheadline Found",
   or "No CTA Button Found", skip it — output its new_text as the same
   sentinel string unchanged.
8. Respond with ONLY valid JSON — no markdown fences, no commentary.

OUTPUT FORMAT (strict JSON, nothing else):
{
  "mutations": [
    {"selector": "h1", "action": "replaceText", "new_text": "..."},
    {"selector": "p",  "action": "replaceText", "new_text": "..."},
    {"selector": "a",  "action": "replaceText", "new_text": "..."}
  ]
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
    (offer, tagline, promo code) and character-length constraints
    injected for each element.
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

    return (
        f"{ad_context}\n"
        f"--- ORIGINAL LANDING PAGE ELEMENTS ---\n\n"
        f"1. HEADLINE (h1):\n"
        f"   Original text: \"{elements['h1']['text']}\"\n"
        f"   Original length: {elements['h1']['char_length']} chars\n"
        f"   ⚠️ New H1 MUST be between {h1_bounds['min']} and {h1_bounds['max']} characters.\n\n"
        f"2. SUBHEADLINE (p):\n"
        f"   Original text: \"{elements['p']['text']}\"\n"
        f"   Original length: {elements['p']['char_length']} chars\n"
        f"   ⚠️ New P MUST be between {p_bounds['min']} and {p_bounds['max']} characters.\n\n"
        f"3. CTA BUTTON (a):\n"
        f"   Original text: \"{elements['a']['text']}\"\n"
        f"   Original length: {elements['a']['char_length']} chars\n"
        f"   ⚠️ New A MUST be between {a_bounds['min']} and {a_bounds['max']} characters.\n\n"
        f"Rewrite all three to incorporate the core offer, tagline, and promo code. "
        f"Return ONLY the JSON object."
    )


def _sanitise_json_response(raw: str) -> str:
    """
    Strips common LLM artefacts so we can safely parse JSON.
    """
    # Remove markdown fences
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)
    raw = raw.strip()

    # Remove trailing commas
    raw = re.sub(r",\s*}", "}", raw)
    raw = re.sub(r",\s*]", "]", raw)

    return raw


def _validate_mutations_schema(data: Any) -> List[Dict[str, str]]:
    """
    Validates and normalises the parsed JSON against the expected schema:
      {"mutations": [{"selector": str, "new_text": str}, ...]}

    Returns the list of mutation dicts.
    Raises ValueError on schema violations.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")

    mutations = data.get("mutations")
    if not isinstance(mutations, list) or len(mutations) == 0:
        raise ValueError("'mutations' key missing or empty.")

    required_selectors = {"h1", "p", "a"}
    found_selectors = set()

    for i, mut in enumerate(mutations):
        if not isinstance(mut, dict):
            raise ValueError(f"Mutation[{i}] is not a dict: {mut}")

        selector = mut.get("selector", "").strip().lower()
        new_text = mut.get("new_text", "").strip()

        if not selector:
            raise ValueError(f"Mutation[{i}] missing 'selector'.")
        if not new_text:
            raise ValueError(f"Mutation[{i}] missing 'new_text'.")

        # Normalise the selector
        mut["selector"] = selector
        mut["new_text"] = new_text

        # Ensure action field exists
        if "action" not in mut:
            mut["action"] = "replaceText"

        found_selectors.add(selector)

    missing = required_selectors - found_selectors
    if missing:
        raise ValueError(f"Missing mutation(s) for selector(s): {missing}")

    return mutations


# ══════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════

def generate_mutations(
    ad_info: Dict[str, str],
    dom_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Component 3 & 5 — Main entry point.

    Calls the NVIDIA NIM Text model to generate rewritten copy
    for H1, P, and A elements, constrained by character lengths.

    Args:
        ad_info:  Dict with keys "core_offer", "tagline", "promo_code"
                  from Component 2's `check_brand_alignment()`.
        dom_data: The full dict returned by Component 1's
                  `extract_dom_data()`.

    Returns:
        dict — validated JSON with shape:
          {"mutations": [
            {"selector": "h1", "action": "replaceText", "new_text": "..."},
            {"selector": "p",  "action": "replaceText", "new_text": "..."},
            {"selector": "a",  "action": "replaceText", "new_text": "..."},
          ]}

    Raises:
        ValueError — after MAX_RETRIES if the model consistently
                     produces malformed output.
    """
    client = _get_nim_client()
    elements = dom_data["elements"]
    user_prompt = _build_user_prompt(ad_info, elements)

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(
            "Generating mutations — attempt %d/%d", attempt, MAX_RETRIES
        )

        try:
            response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": OPTIMIZER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,   # deterministic output
                max_tokens=512,
                top_p=1.0,
            )

            raw_text = response.choices[0].message.content
            logger.info("Optimizer raw response (attempt %d): %s", attempt, raw_text)

            # Parse & validate
            sanitised = _sanitise_json_response(raw_text)
            parsed = json.loads(sanitised)
            mutations = _validate_mutations_schema(parsed)

            logger.info("✅ Mutations generated successfully on attempt %d", attempt)
            return {"mutations": mutations}

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
        f"Mutation generation failed after {MAX_RETRIES} attempts.\n"
        f"Last error: {last_error}"
    )
