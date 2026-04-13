"""
╔══════════════════════════════════════════════════════════════════╗
║  Dynamic DOM Weaver — Streamlit Application (Main Entry)       ║
║  B2B SaaS Growth Tool: Ad Creative → Personalized Landing Page ║
║                                                                 ║
║  Full Pipeline:                                                 ║
║    ✅ Component 1 — Ingestion & DOM Extractor                   ║
║    ✅ Component 2 — Relevance Gatekeeper                        ║
║    ✅ Component 3 — Context-Aware Optimizer                     ║
║    ✅ Component 4 — Deterministic Hallucination Verifier        ║
║    ✅ Component 5 — Structured Formatter                        ║
║    ✅ Component 6 — Edge Injector                               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import logging
import streamlit as st
import streamlit.components.v1 as components

# ──────────────────────────────────────────────────────────
# Configure logging for all modules
# ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)s │ %(levelname)s │ %(message)s",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Component Imports
# ──────────────────────────────────────────────────────────
from dom_extractor import extract_dom_data
from relevance_gate import check_brand_alignment, BrandMismatchError
from mutation_generator import generate_mutations
from hallucination_verifier import verify_hallucinations
from edge_injector import inject_and_render

# ──────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────
MAX_HALLUCINATION_RETRIES = 3

# ══════════════════════════════════════════════════════════
#  PAGE CONFIGURATION
# ══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Dynamic DOM Weaver — AI Landing Page Personalizer",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════
#  CUSTOM STYLES
# ══════════════════════════════════════════════════════════
st.markdown("""
<style>
    /* ── Import premium font ─────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    * { font-family: 'Inter', sans-serif; }

    /* ── Dark-glass hero section ─────────────────────── */
    .main-header {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        padding: 2.2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .main-header h1 {
        background: linear-gradient(90deg, #00d2ff, #7b2ff7, #ff6ec7);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.4rem;
        font-weight: 800;
        margin-bottom: 0.3rem;
        animation: shimmer 3s ease-in-out infinite;
    }
    @keyframes shimmer {
        0%, 100% { background-position: 0% center; }
        50% { background-position: 200% center; }
    }
    .main-header p {
        color: rgba(255,255,255,0.65);
        font-size: 1.05rem;
        margin: 0;
    }

    /* ── Pipeline step cards ─────────────────────────── */
    .step-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 1rem 1.4rem;
        margin-bottom: 0.75rem;
        transition: all 0.3s ease;
    }
    .step-card:hover {
        border-color: rgba(123, 47, 247, 0.3);
        box-shadow: 0 4px 20px rgba(123, 47, 247, 0.1);
    }
    .step-card h4 {
        color: #9ca3af;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.4rem;
        font-weight: 600;
    }
    .step-card p {
        font-size: 0.95rem;
        font-weight: 600;
        margin: 0;
        line-height: 1.4;
    }

    /* ── Metric cards ────────────────────────────────── */
    .metric-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.5rem;
    }
    .metric-card h4 {
        color: #7b8794;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
    }
    .metric-card p {
        font-size: 1rem;
        font-weight: 600;
        margin: 0;
    }

    /* ── Accent colours ──────────────────────────────── */
    .text-green { color: #10b981 !important; }
    .text-purple { color: #a78bfa !important; }
    .text-cyan { color: #22d3ee !important; }
    .text-amber { color: #fbbf24 !important; }

    /* ── Final output frame ──────────────────────────── */
    .output-frame {
        border: 2px solid rgba(123, 47, 247, 0.3);
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 12px 48px rgba(0,0,0,0.4);
    }

    /* ── JSON viewer ─────────────────────────────────── */
    .json-viewer {
        background: #1a1b26;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        overflow-x: auto;
        color: #a9b1d6;
    }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════
st.markdown("""
<div class="main-header">
    <h1>🧬 Dynamic DOM Weaver</h1>
    <p>Upload an Ad Creative & a Target URL → Watch the landing page rewrite itself in real-time.</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  INPUT SECTION
# ══════════════════════════════════════════════════════════
col_left, col_right = st.columns([1, 1.5], gap="large")

with col_left:
    st.subheader("📎 Ad Creative")
    uploaded_file = st.file_uploader(
        "Upload your ad image (PNG, JPG, WEBP)",
        type=["png", "jpg", "jpeg", "webp"],
        help="The ad creative whose offer will be injected into the target landing page.",
    )
    if uploaded_file:
        st.image(uploaded_file, caption="Uploaded Ad Creative", use_container_width=True)

with col_right:
    st.subheader("🌐 Target Landing Page")
    target_url = st.text_input(
        "Enter the URL of the page to personalize",
        placeholder="https://example.com/pricing",
        help="The landing page whose H1, subheadline, and CTA will be rewritten to match the ad.",
    )

st.divider()

# ══════════════════════════════════════════════════════════
#  PIPELINE EXECUTION
# ══════════════════════════════════════════════════════════
run_button = st.button(
    "🚀  Generate Personalization",
    use_container_width=True,
    type="primary",
    disabled=not (uploaded_file and target_url),
)

if run_button and uploaded_file and target_url:

    # ── Phase tracker ────────────────────────────────────
    progress = st.progress(0, text="Initializing agents…")
    status_area = st.container()

    try:
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #  COMPONENT 1 — DOM Extraction
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        progress.progress(10, text="🔍 Component 1 — Extracting DOM from target URL…")

        with st.spinner("Fetching & parsing target page…"):
            dom_data = extract_dom_data(target_url)

        with status_area:
            st.success("✅ Component 1 — DOM Extraction Complete")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown('<div class="metric-card"><h4>H1 — Headline</h4>', unsafe_allow_html=True)
                h1_text = dom_data["elements"]["h1"]["text"] or "⚠️ Not found"
                h1_len  = dom_data["elements"]["h1"]["char_length"]
                st.markdown(f'<p>{h1_text}</p><small>{h1_len} chars</small></div>', unsafe_allow_html=True)

            with c2:
                st.markdown('<div class="metric-card"><h4>P — Subheadline</h4>', unsafe_allow_html=True)
                p_text = dom_data["elements"]["p"]["text"] or "⚠️ Not found"
                p_len  = dom_data["elements"]["p"]["char_length"]
                display_p = p_text[:120] + "…" if len(p_text) > 120 else p_text
                st.markdown(f'<p>{display_p}</p><small>{p_len} chars</small></div>', unsafe_allow_html=True)

            with c3:
                st.markdown('<div class="metric-card"><h4>A — CTA Button</h4>', unsafe_allow_html=True)
                a_text = dom_data["elements"]["a"]["text"] or "⚠️ Not found"
                a_len  = dom_data["elements"]["a"]["char_length"]
                st.markdown(f'<p>{a_text}</p><small>{a_len} chars</small></div>', unsafe_allow_html=True)

            if dom_data["jina_text"]:
                st.info(f"📄 Jina Reader extracted {len(dom_data['jina_text']):,} characters of clean text.")
            else:
                st.warning("⚠️ Jina Reader unavailable — proceeding with BeautifulSoup extraction only.")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #  COMPONENT 2 — Relevance Gatekeeper
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        progress.progress(25, text="🛡️ Component 2 — Checking brand alignment…")

        with st.spinner("Running brand-safety analysis via NVIDIA NIM Vision…"):
            ad_bytes = uploaded_file.getvalue()
            extracted_h1 = dom_data["elements"]["h1"]["text"]

            # Sentinel strings from the extractor are not useful for alignment
            if not extracted_h1 or extracted_h1 == "No Headline Found":
                extracted_h1 = dom_data["jina_text"][:200] if dom_data["jina_text"] else "Unknown page content"
                st.warning("⚠️ No H1 found — using Jina text excerpt for brand alignment check.")

            ad_info = check_brand_alignment(ad_bytes, extracted_h1)

        with status_area:
            st.success("✅ Component 2 — Brand Alignment Verified")

            # Show all extracted ad fields
            ai_c1, ai_c2, ai_c3 = st.columns(3)
            with ai_c1:
                st.markdown(
                    f'<div class="metric-card">'
                    f'<h4>Core Offer</h4>'
                    f'<p class="text-green" style="font-size: 1.1rem;">{ad_info["core_offer"]}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with ai_c2:
                tagline_display = ad_info["tagline"] or "—"
                st.markdown(
                    f'<div class="metric-card">'
                    f'<h4>Tagline</h4>'
                    f'<p class="text-purple">{tagline_display}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with ai_c3:
                promo_display = ad_info["promo_code"] or "—"
                st.markdown(
                    f'<div class="metric-card">'
                    f'<h4>Promo Code</h4>'
                    f'<p class="text-amber">{promo_display}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #  COMPONENT 3 & 5 — Mutation Generation
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        progress.progress(45, text="✍️ Component 3 — Generating optimized mutations…")

        with st.spinner("Calling NVIDIA NIM Text model for CRO copywriting…"):
            mutations_json = generate_mutations(ad_info, dom_data)

        with status_area:
            st.success("✅ Component 3 & 5 — Mutations Generated & Formatted")

            # Display mutation preview
            for mut in mutations_json["mutations"]:
                tag = mut["selector"].upper()
                original = dom_data["elements"].get(mut["selector"], {}).get("text", "—")
                st.markdown(
                    f'<div class="step-card">'
                    f'<h4>&lt;{tag}&gt; Mutation</h4>'
                    f'<p><span style="color:#ef4444;text-decoration:line-through;">{original}</span></p>'
                    f'<p class="text-cyan">→ {mut["new_text"]}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #  COMPONENT 4 — Hallucination Verification
        #  (with retry loop back to Component 3)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        progress.progress(65, text="🔬 Component 4 — Verifying for hallucinations…")

        verified = False
        verification_attempts = 0

        while not verified and verification_attempts < MAX_HALLUCINATION_RETRIES:
            verification_attempts += 1

            with st.spinner(f"Hallucination check — attempt {verification_attempts}/{MAX_HALLUCINATION_RETRIES}…"):
                is_clean, reason = verify_hallucinations(ad_info["core_offer"], mutations_json)

            if is_clean:
                verified = True
                with status_area:
                    st.success(
                        f"✅ Component 4 — Hallucination Check Passed "
                        f"(attempt {verification_attempts})"
                    )
            else:
                with status_area:
                    st.warning(
                        f"⚠️ Hallucination detected (attempt {verification_attempts}): {reason}\n\n"
                        f"Re-generating mutations…"
                    )
                # Retry: regenerate mutations
                progress.progress(
                    65 + verification_attempts * 5,
                    text=f"🔄 Regenerating mutations (retry {verification_attempts})…"
                )
                with st.spinner("Re-calling NVIDIA NIM for cleaner output…"):
                    mutations_json = generate_mutations(ad_info, dom_data)

        if not verified:
            raise ValueError(
                f"Hallucination verification failed after {MAX_HALLUCINATION_RETRIES} attempts.\n"
                f"Last issue: {reason}"
            )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #  COMPONENT 6 — Edge Injection & Rendering
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        progress.progress(85, text="💉 Component 6 — Injecting mutations into DOM…")

        with st.spinner("Building personalized landing page…"):
            modified_html = inject_and_render(
                raw_html=dom_data["raw_html"],
                target_url=dom_data["url"],
                verified_json=mutations_json,
            )

        progress.progress(100, text="✅ Pipeline complete — personalized page rendered!")

        with status_area:
            st.success("✅ Component 6 — Edge Injection Complete")
            st.markdown(
                f'<div class="metric-card">'
                f'<h4>Output Size</h4>'
                f'<p>{len(modified_html):,} characters</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #  FINAL OUTPUT — Render the personalized page
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        st.divider()
        st.subheader("🎯 Personalized Landing Page")
        st.caption("The page below has been mutated to match your ad creative's core offer.")

        # Render in an iframe via Streamlit's html component
        st.markdown('<div class="output-frame">', unsafe_allow_html=True)
        components.html(modified_html, height=800, scrolling=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Optional: show the raw JSON & debug info ─────
        with st.expander("🔧 Debug — Mutation JSON Payload"):
            st.json(mutations_json)

        with st.expander("🔧 Debug — Pipeline Summary"):
            st.markdown(f"""
| Step | Status |
|------|--------|
| DOM Extraction | ✅ Complete |
| Jina Reader | {"✅ Available" if dom_data["jina_text"] else "⚠️ Unavailable"} |
| Brand Alignment | ✅ Matched |
| Core Offer | `{ad_info["core_offer"]}` |
| Tagline | `{ad_info.get("tagline", "—")}` |
| Promo Code | `{ad_info.get("promo_code", "—")}` |
| Mutation Generation | ✅ Complete |
| Hallucination Check | ✅ Passed (attempt {verification_attempts}) |
| Edge Injection | ✅ Rendered |
| Output Size | {len(modified_html):,} chars |
""")

    except BrandMismatchError as bme:
        progress.progress(100, text="❌ Brand mismatch — pipeline halted.")
        st.error(str(bme))

    except ValueError as ve:
        progress.progress(100, text="❌ Validation error.")
        st.error(f"⚠️ Validation Error:\n\n{ve}")

    except Exception as exc:
        progress.progress(100, text="❌ Unexpected error.")
        st.error(f"💥 Unexpected error:\n\n```\n{exc}\n```")
        logger.exception("Unhandled error in pipeline")

# ══════════════════════════════════════════════════════════
#  FOOTER
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.caption(
    "Dynamic DOM Weaver v1.0.0 • "
    "Powered by NVIDIA NIM + Jina Reader • "
    "Zero-cost inference stack • "
    "Components: Extractor → Gatekeeper → Optimizer → Verifier → Injector"
)
