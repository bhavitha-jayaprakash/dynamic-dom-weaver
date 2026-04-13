"""
╔══════════════════════════════════════════════════════════════════╗
║  COMPONENT 4 — The Deterministic Hallucination Verifier         ║
║  Pure-Python regex-based checker. Ensures no fabricated numbers ║
║  (digits, percentages, dollar amounts) leak into the generated  ║
║  mutations beyond what the core offer actually contains.        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import re
import logging
from typing import Dict, Any, Set, Tuple

# ──────────────────────────────────────────────────────────
# Module-level logger
# ──────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Regex patterns for numerical claim extraction
# ──────────────────────────────────────────────────────────

# Matches patterns like: $100, $99.99, $1,000, $1,000.00
DOLLAR_PATTERN = re.compile(r"\$[\d,]+(?:\.\d{1,2})?")

# Matches patterns like: 30%, 99.5%, 100%
PERCENT_PATTERN = re.compile(r"\d+(?:\.\d+)?%")

# Matches standalone integers/floats that are NOT part of a
# dollar or percent pattern (e.g. "7 days", "24/7", "3x")
# We use a negative lookbehind for $ and negative lookahead for %
BARE_NUMBER_PATTERN = re.compile(r"(?<!\$)\b\d+(?:[.,]\d+)*\b(?!%)")


def _extract_numerical_claims(text: str) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Extracts three categories of numerical claims from a text string:
      1. Dollar amounts  →  {"$100", "$99.99"}
      2. Percentages     →  {"30%", "99.5%"}
      3. Bare numbers    →  {"7", "24", "3"}

    Returns a 3-tuple of sets.
    """
    dollars   = set(DOLLAR_PATTERN.findall(text))
    percents  = set(PERCENT_PATTERN.findall(text))
    bare_nums = set(BARE_NUMBER_PATTERN.findall(text))

    # Normalise: strip commas from dollar amounts for comparison
    dollars_normalised = {d.replace(",", "") for d in dollars}

    # Normalise: strip commas from bare numbers
    bare_nums_normalised = {n.replace(",", "") for n in bare_nums}

    return dollars_normalised, percents, bare_nums_normalised


def _flatten_mutations_text(mutations_json: Dict[str, Any]) -> str:
    """
    Concatenates all `new_text` values from the mutations JSON
    into a single string for scanning.
    """
    texts = []
    for mut in mutations_json.get("mutations", []):
        new_text = mut.get("new_text", "")
        if new_text:
            texts.append(new_text)
    return " ".join(texts)


# ══════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════

def verify_hallucinations(
    core_offer_string: str,
    generated_json: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Component 4 — Main entry point.

    Compares every numerical claim (dollars, percentages, bare numbers)
    found in the generated mutations against those present in the
    core offer string.

    Args:
        core_offer_string:  The offer extracted by Component 2
                            (e.g., "30% off annual plans").
        generated_json:     The mutations dict from Component 3
                            (e.g., {"mutations": [...]}).

    Returns:
        Tuple[bool, str]:
          - True  + ""              → clean, no hallucinated numbers
          - False + reason string   → hallucination detected

    This function has ZERO external dependencies — pure Python + regex.
    """

    # ── 1. Extract claims from the core offer ────────────
    offer_dollars, offer_percents, offer_nums = _extract_numerical_claims(
        core_offer_string
    )

    logger.info(
        "Core offer claims — $: %s | %%: %s | nums: %s",
        offer_dollars, offer_percents, offer_nums,
    )

    # ── 2. Extract claims from the generated mutations ───
    mutations_text = _flatten_mutations_text(generated_json)
    gen_dollars, gen_percents, gen_nums = _extract_numerical_claims(
        mutations_text
    )

    logger.info(
        "Generated claims  — $: %s | %%: %s | nums: %s",
        gen_dollars, gen_percents, gen_nums,
    )

    # ── 3. Detect hallucinated claims ────────────────────
    hallucinated = []

    # Check dollar amounts
    fabricated_dollars = gen_dollars - offer_dollars
    if fabricated_dollars:
        hallucinated.append(f"Dollar amounts not in offer: {fabricated_dollars}")

    # Check percentages
    fabricated_percents = gen_percents - offer_percents
    if fabricated_percents:
        hallucinated.append(f"Percentages not in offer: {fabricated_percents}")

    # Check bare numbers — more lenient: we allow common
    # "harmless" numbers that are not promotional claims
    ALLOWED_BARE = {"1", "2", "3", "24", "7", "365", "0", "100"}
    fabricated_nums = gen_nums - offer_nums - ALLOWED_BARE
    if fabricated_nums:
        hallucinated.append(f"Bare numbers not in offer: {fabricated_nums}")

    # ── 4. Verdict ───────────────────────────────────────
    if hallucinated:
        reason = " | ".join(hallucinated)
        logger.warning("🚨 Hallucination detected: %s", reason)
        return False, reason

    logger.info("✅ Hallucination check passed — all claims verified.")
    return True, ""
