"""
╔══════════════════════════════════════════════════════════════════╗
║  Dynamic DOM Weaver — Streamlit Application (Main Entry)       ║
║  B2B SaaS Growth Tool: Ad Creative → Personalized Landing Page ║
║                                                                 ║
║  Full Pipeline (Hybrid V4 — Deep Proxy + Premium Animations): ║
║    ✅ Component 1 — Ingestion & DOM Extractor + Data Stamping   ║
║    ✅ Component 2 — Relevance Gatekeeper + Gradient Colors      ║
║    ✅ Component 3 & 5 — Hybrid V3 (Exact Target Mutations)     ║
║    ✅ Component 4 — Deterministic Hallucination Verifier        ║
║    ✅ Component 6 — Edge Injector (Network Intercept + Shimmer) ║
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
        help="The landing page whose text will be rewritten, with a gradient banner and badge injected.",
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
            st.success("✅ Component 1 — DOM Extraction Complete (nodes stamped)")

            c1, c2, c3 = st.columns(3)
            with c1:
                h1_node = dom_data["elements"].get("h1", {})
                h1_text = h1_node.get("text", "") or "⚠️ Not found"
                h1_len  = h1_node.get("char_length", 0)
                st.markdown(
                    f'<div class="metric-card">'
                    f'<h4>H1 — Headline</h4>'
                    f'<p>{h1_text}</p>'
                    f'<small style="color:#9ca3af;">{h1_len} chars</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with c2:
                p_node  = dom_data["elements"].get("p", {})
                p_text  = p_node.get("text", "") or "⚠️ Not found"
                p_len   = p_node.get("char_length", 0)
                display_p = p_text[:120] + "…" if len(p_text) > 120 else p_text
                st.markdown(
                    f'<div class="metric-card">'
                    f'<h4>P — Subheadline</h4>'
                    f'<p>{display_p}</p>'
                    f'<small style="color:#9ca3af;">{p_len} chars</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with c3:
                a_node = dom_data["elements"].get("a", {})
                a_text = a_node.get("text", "") or "⚠️ Not found"
                a_len  = a_node.get("char_length", 0)
                st.markdown(
                    f'<div class="metric-card">'
                    f'<h4>CTA — Button</h4>'
                    f'<p>{a_text}</p>'
                    f'<small style="color:#9ca3af;">{a_len} chars</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

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

            # Show all extracted ad fields + gradient preview
            ai_c1, ai_c2, ai_c3, ai_c4 = st.columns(4)
            with ai_c1:
                st.markdown(
                    f'<div class="metric-card">'
                    f'<h4>Core Offer</h4>'
                    f'<p class="text-green" style="font-size: 1.1rem;">{ad_info["core_offer"]}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with ai_c2:
                tagline_display = ad_info.get("tagline") or "—"
                st.markdown(
                    f'<div class="metric-card">'
                    f'<h4>Tagline</h4>'
                    f'<p class="text-purple">{tagline_display}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with ai_c3:
                promo_display = ad_info.get("promo_code") or "—"
                st.markdown(
                    f'<div class="metric-card">'
                    f'<h4>Promo Code</h4>'
                    f'<p class="text-amber">{promo_display}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with ai_c4:
                c_primary = ad_info.get("color_primary_hex", "#7B2FF7")
                c_secondary = ad_info.get("color_secondary_hex", "#00D2FF")
                st.markdown(
                    f'<div class="metric-card">'
                    f'<h4>Brand Gradient</h4>'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-top:4px;">'
                    f'<div style="width:100%;height:24px;border-radius:6px;'
                    f'background:linear-gradient(135deg, {c_primary}, {c_secondary});"></div>'
                    f'</div>'
                    f'<p style="font-size:0.8rem;margin-top:6px;color:#9ca3af;">'
                    f'{c_primary} → {c_secondary}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #  COMPONENT 3, 4 & 5 — Generation & Verification
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        progress.progress(45, text="✍️ Component 3 — Generating exact-target mutations…")

        def _build_verifier_payload(mj):
            items = []
            for m in mj.get("mutations", []):
                items.append({"selector": m.get("selector", ""), "new_text": m.get("new_text", "")})
            inj_data = mj.get("injections", {})
            items.append({"selector": "banner", "new_text": inj_data.get("banner_text", "")})
            items.append({"selector": "badge",  "new_text": inj_data.get("badge_text", "")})
            return {"mutations": items}

        verified = False
        feedback = ""
        reason = ""
        
        generation_placeholder = st.empty()

        for attempt in range(5):
            progress_msg = "✍️ Component 3 — Generating exact-target mutations…" if attempt == 0 else f"🔄 Regenerating mutations (retry {attempt})…"
            progress.progress(45 + attempt * 5, text=progress_msg)

            with st.spinner(f"Calling NVIDIA NIM Text model for CRO copywriting (Attempt {attempt + 1}/5)…"):
                mutations_json = generate_mutations(ad_info, dom_data, feedback=feedback)

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            #  COMPONENT 4 — Hallucination Verification
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            progress.progress(65 + attempt * 5, text="🔬 Component 4 — Verifying for hallucinations…")
            verifier_payload = _build_verifier_payload(mutations_json)

            # Construct original text string to bypass original numerical claims
            original_text = f"{dom_data['elements'].get('h1', {}).get('text', '')} " \
                            f"{dom_data['elements'].get('p', {}).get('text', '')} " \
                            f"{dom_data['elements'].get('a', {}).get('text', '')}"

            with st.spinner(f"Hallucination check — attempt {attempt + 1}/5…"):
                is_clean, reason = verify_hallucinations(
                    ad_info["core_offer"], 
                    verifier_payload, 
                    original_text=original_text
                )

            if is_clean:
                verified = True
                with status_area:
                    st.success(f"✅ Component 4 — Hallucination Check Passed (attempt {attempt + 1})")
                break
            else:
                feedback = reason
                with status_area:
                    st.warning(f"⚠️ Hallucination detected (attempt {attempt + 1}): {reason}\n\nRe-generating mutations…")

        if not verified:
            raise ValueError(
                f"Hallucination verification failed after 5 attempts.\n"
                f"Last issue: {reason}"
            )

        if verified:
            with status_area:
                st.success("✅ Component 3 & 5 — Hybrid V3 Output Generated")

                # ── Gradient colors from response ────────────
                gen_colors = mutations_json.get("colors", {})
                grad_primary = gen_colors.get("primary", ad_info.get("color_primary_hex", "#7B2FF7"))
                grad_secondary = gen_colors.get("secondary", ad_info.get("color_secondary_hex", "#00D2FF"))

                # ── Banner preview ───────────────────────────
                inj = mutations_json.get("injections", {})
                st.markdown(
                    f'<div class="step-card">'
                    f'<h4>🏷️ Banner Preview</h4>'
                    f'<div style="background:linear-gradient(135deg, {grad_primary}, {grad_secondary});'
                    f'color:white;text-align:center;font-weight:bold;padding:12px 16px;'
                    f'border-radius:6px;margin-top:0.5rem;font-size:0.95rem;'
                    f'letter-spacing:0.03em;">'
                    f'{inj.get("banner_text", "—")}'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Text mutation previews ───────────────────
                selector_labels = {
                    '[data-troopod-target="headline"]': ('H1 — Headline', 'h1'),
                    '[data-troopod-target="subheadline"]': ('P — Subheadline', 'p'),
                    '[data-troopod-target="cta"]': ('CTA — Button', 'a'),
                }
                for mut in mutations_json.get("mutations", []):
                    sel = mut.get("selector", "?")
                    label, elem_key = selector_labels.get(sel, (sel, ""))
                    original = dom_data["elements"].get(elem_key, {}).get("text", "—")
                    st.markdown(
                        f'<div class="step-card">'
                        f'<h4>{label} Mutation</h4>'
                        f'<p><span style="color:#ef4444;text-decoration:line-through;">{original}</span></p>'
                        f'<p class="text-cyan">→ {mut.get("new_text", "—")}</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                # ── Badge preview  (shimmer-style) ───────────
                st.markdown(
                    f'<div class="step-card">'
                    f'<h4>✨ Shimmer Badge Preview</h4>'
                    f'<p style="margin-top:0.5rem;">'
                    f'<span style="background:linear-gradient(90deg, {grad_primary} 0%, {grad_secondary} 50%, {grad_primary} 100%);'
                    f'background-size:200% auto;color:white;padding:0.25em 0.6em;border-radius:0.4em;'
                    f'font-size:0.85rem;font-weight:700;display:inline-block;'
                    f'box-shadow:0 4px 12px rgba(0,0,0,0.15);">'
                    f'{inj.get("badge_text", "—")}'
                    f'</span></p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #  COMPONENT 6 — Edge Injection & Rendering
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        progress.progress(85, text="💉 Component 6 — Injecting network proxy + shimmer UI…")

        with st.spinner("Building personalized landing page…"):
            modified_html = inject_and_render(
                raw_html=dom_data["raw_html"],
                target_url=dom_data["url"],
                verified_json=mutations_json,
            )

        progress.progress(100, text="✅ Pipeline complete — personalized page rendered!")

        with status_area:
            st.success("✅ Component 6 — Hybrid V4 Injection Complete")
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
        st.caption("Text mutated (safe mode) + shimmer badge, gradient-pan banner & network intercept injected.")

        # Render in an iframe via Streamlit's html component
        st.markdown('<div class="output-frame">', unsafe_allow_html=True)
        components.html(modified_html, height=800, scrolling=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Optional: show the raw JSON & debug info ─────
        with st.expander("🔧 Debug — Hybrid V4 JSON Payload"):
            st.json(mutations_json)

        with st.expander("🔧 Debug — Pipeline Summary"):
            gen_inj = mutations_json.get("injections", {})
            gen_col = mutations_json.get("colors", {})
            st.markdown(f"""
| Step | Status |
|------|--------|
| DOM Extraction | ✅ Stamped (data-troopod-target) |
| Jina Reader | {"✅ Available" if dom_data["jina_text"] else "⚠️ Unavailable"} |
| Brand Alignment | ✅ Matched |
| Core Offer | `{ad_info["core_offer"]}` |
| Tagline | `{ad_info.get("tagline", "—")}` |
| Promo Code | `{ad_info.get("promo_code", "—")}` |
| Gradient | `{gen_col.get('primary', '—')}` → `{gen_col.get('secondary', '—')}` |
| Mutations | ✅ {len(mutations_json.get('mutations', []))} nodes via data‑troopod‑target |
| Banner | 🎨 `{gen_inj.get('banner_text', '—')}` (gradient‑pan) |
| Badge | ✨ `{gen_inj.get('badge_text', '—')}` (shimmer) |
| Hallucination Check | ✅ Passed (attempt {attempt + 1}) |
| Network Interceptor | ✅ fetch + XHR redirected |
| Edge Injection | ✅ Shimmer + Gradient‑Pan + Safe Mutation |
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
    "Dynamic DOM Weaver v6.0.0 • "
    "Powered by NVIDIA NIM + Jina Reader • "
    "Zero-cost inference stack • "
    "Hybrid V4: Stamper → Gatekeeper → Optimizer → Verifier → Deep Proxy Injector"
)

