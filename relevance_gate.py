"""
╔══════════════════════════════════════════════════════════════════╗
║  COMPONENT 2 — The Relevance Gatekeeper                        ║
║  Uses the NVIDIA NIM Vision model to verify brand alignment     ║
║  between an uploaded ad creative and the target page headline.  ║
║  Extracts the core offer string for downstream mutation.        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import base64
import logging
import re
from typing import Dict, Any, Tuple

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
VISION_MODEL = "meta/llama-3.2-90b-vision-instruct"

# System prompt for the brand-safety filter
GATEKEEPER_SYSTEM_PROMPT = """You are a strict brand safety filter for a B2B SaaS platform.

Your ONLY task:
1. Determine if the industry/category of the Ad Image matches the industry/category of the provided Headline.
2. Extract ALL textual information from the Ad Image:
   a. The core promotional offer (e.g., "30% off", "$50 discount", "Free trial").
   b. The ad's tagline or slogan (the catchy phrase, e.g., "Scale Without Limits").
   c. Any promo/coupon code visible in the ad (e.g., "SAVE30", "WELCOME50").

RULES:
- "Match" means both the Ad and the Headline belong to the same broad industry or a closely related one (e.g., "SaaS" and "Cloud Software" match; "Pizza delivery" and "Enterprise Security" do NOT match).
- If no clear offer is visible in the ad, set core_offer to "General Promotion".
- If no tagline is visible, set tagline to "".
- If no promo code is visible, set promo_code to "".
- You MUST respond with ONLY valid JSON — no markdown fences, no commentary.

OUTPUT FORMAT (strict JSON, nothing else):
{"is_match": true, "core_offer": "30% off annual plans", "tagline": "Scale Without Limits", "promo_code": "SAVE30"}
"""


def _get_nim_client() -> OpenAI:
    """
    Initialises and returns an OpenAI-compatible client pointed
    at the NVIDIA NIM inference endpoint.

    Raises StreamlitError if the API key is missing.
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


def _encode_image_to_base64(image_bytes: bytes) -> str:
    """
    Encodes raw image bytes to a base64 data-URI string
    suitable for the NIM Vision API.
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _sanitise_json_response(raw: str) -> dict:
    """
    Robustly extracts and parses a JSON object from raw LLM output.

    Handles common model quirks:
      - "Answer: {...}"  or  "Output: {...}"  preambles
      - Markdown code fences (```json ... ```)
      - Trailing commas before closing braces
      - Leading/trailing whitespace

    Strategy: locate the first '{' and last '}' and parse only
    the text between them.

    Returns the parsed dict.
    Raises ValueError if no JSON object can be found.
    """
    raw = raw.strip()

    # Locate the JSON object boundaries
    start_idx = raw.find("{")
    end_idx = raw.rfind("}") + 1

    if start_idx == -1 or end_idx == 0:
        raise ValueError(f"No JSON object found in response: {raw}")

    json_str = raw[start_idx:end_idx]

    # Clean trailing commas (e.g. {"a": 1,} → {"a": 1})
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)

    return json.loads(json_str)


def _parse_gatekeeper_response(raw_text: str) -> Dict[str, Any]:
    """
    Parses and validates the JSON response from the Vision model.

    Expected shape:
      {"is_match": bool, "core_offer": str, "tagline": str, "promo_code": str}

    Raises ValueError if the response cannot be parsed or is
    missing required fields.
    """
    try:
        data = _sanitise_json_response(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Failed to parse gatekeeper JSON: %s\nRaw: %s", exc, raw_text)
        raise ValueError(
            f"The brand-safety model returned unparseable output.\n"
            f"Raw response: {raw_text}"
        ) from exc

    # ── Validate required fields ─────────────────────────
    if "is_match" not in data:
        raise ValueError(
            f"Gatekeeper response missing 'is_match' field. Got: {data}"
        )
    if "core_offer" not in data:
        raise ValueError(
            f"Gatekeeper response missing 'core_offer' field. Got: {data}"
        )

    # Coerce is_match to bool (some models return strings)
    if isinstance(data["is_match"], str):
        data["is_match"] = data["is_match"].lower() in ("true", "yes", "1")

    # Ensure core_offer is a non-empty string
    data["core_offer"] = str(data.get("core_offer", "")).strip()
    if not data["core_offer"]:
        data["core_offer"] = "General Promotion"

    # Normalise optional fields — default to empty string
    data["tagline"] = str(data.get("tagline", "")).strip()
    data["promo_code"] = str(data.get("promo_code", "")).strip()

    return data


# ══════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════

class BrandMismatchError(Exception):
    """
    Raised when the ad creative's industry does not align
    with the target page's headline/industry.
    """
    pass


def check_brand_alignment(
    ad_image_bytes: bytes,
    extracted_h1: str,
) -> Dict[str, str]:
    """
    Component 2 — Main entry point.

    Sends the Ad Image + extracted H1 to the NVIDIA NIM Vision
    model for brand-safety verification.

    Args:
        ad_image_bytes: Raw bytes of the uploaded ad image.
        extracted_h1:   The H1 text extracted from the target URL
                        (from Component 1).

    Returns:
        dict — {
            "core_offer":  str,  e.g. "30% off annual plans"
            "tagline":     str,  e.g. "Scale Without Limits"
            "promo_code":  str,  e.g. "SAVE30"
        }

    Raises:
        BrandMismatchError — if the ad and page industries don't match.
        ValueError         — if the API key is missing or the model
                             response is malformed.
    """

    # ── 1. Build the NIM client ──────────────────────────
    client = _get_nim_client()

    # ── 2. Encode the ad image ───────────────────────────
    image_data_uri = _encode_image_to_base64(ad_image_bytes)

    # ── 3. Construct the multimodal message ──────────────
    user_content = [
        {
            "type": "text",
            "text": (
                f"**Ad Image:** (attached below)\n"
                f"**Target Page Headline:** \"{extracted_h1}\"\n\n"
                f"Analyse the ad image and the headline. "
                f"Extract the core offer, tagline, and any promo code. "
                f"Respond with the JSON object as instructed."
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": image_data_uri,
            },
        },
    ]

    logger.info("Calling NVIDIA NIM Vision model for brand alignment check...")

    # ── 4. Call the Vision model ─────────────────────────
    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": GATEKEEPER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,     # deterministic
            max_tokens=256,      # response is tiny JSON
            top_p=1.0,
        )
    except Exception as exc:
        logger.error("NVIDIA NIM Vision API call failed: %s", exc)
        raise ValueError(
            f"Failed to reach the NVIDIA NIM Vision model.\n"
            f"Error: {exc}"
        ) from exc

    # ── 5. Extract and parse the response ────────────────
    raw_text = response.choices[0].message.content
    logger.info("Gatekeeper raw response: %s", raw_text)

    result = _parse_gatekeeper_response(raw_text)

    # ── 6. Gate check — halt pipeline on mismatch ────────
    if not result["is_match"]:
        raise BrandMismatchError(
            "🚫 Brand Mismatch Detected!\n\n"
            "The ad creative's industry does not align with the "
            "target page. Personalization aborted to prevent "
            "off-brand mutations.\n\n"
            f"Core offer detected: **{result['core_offer']}**\n"
            f"Target headline: **{extracted_h1}**"
        )

    logger.info(
        "✅ Brand alignment verified. Offer: %s | Tagline: %s | Promo: %s",
        result["core_offer"], result["tagline"], result["promo_code"],
    )

    return {
        "core_offer": result["core_offer"],
        "tagline": result["tagline"],
        "promo_code": result["promo_code"],
    }
