# Product Architecture & Technical Documentation:  
## Dynamic DOM Weaver  

---

## Prototype Links & Resources

- **Live Demo (Streamlit):** https://dynamic-dom-weaver.streamlit.app/  

- **Demo Note:**  
Due to standard cross-origin security policies (CORS) within our third-party iframe environment, native JavaScript events on buttons located directly inside the AI-mutation zone may be temporarily disabled by the browser. However, the visual payload renders perfectly, and the surrounding website (headers, footers, and native navigation) remains completely intact and functional.

---

## Testing Matrix (Recommended URLs)

**Note:** Due to iframe sandbox limitations (detailed in Section 5), this prototype is best evaluated on permissive, low-security storefronts.

| Vertical  | Target Landing Page URL | Target Ad Creative |
|----------|------------------------|------------------|
| Footwear | https://www.thesareesneakers.com/product-page/golden-flowers-sneakers | https://drive.google.com/file/d/1CNpLxA8agbwzsG5rH1XGTxQp2mKsfBHM/view?usp=sharing |
| Apparel  | https://www.fetedelaboutique.com/product-page/the-new-society-sakura-long-dress | https://drive.google.com/file/d/1aFD5OzUtpTDvOR9AS5UxW3VIdQGSXFAf/view?usp=sharing |
| Book     | https://franciswilley.bigcartel.com/product/prayer-for-a-bird | https://drive.google.com/file/d/1QRbg67HrK1jPs1C-k4QAvMtseFF19sIu/view?usp=sharing |

---

## 1. Executive Summary

The Dynamic DOM Weaver is an automated, AI-driven Conversion Rate Optimization (CRO) pipeline. It bridges the gap between top-of-funnel ad creatives and bottom-of-funnel landing pages. By dynamically ingesting a target URL and a promotional image, the system utilizes a multi-agent Vision/Text architecture to analyze brand alignment, generate personalized copy, and surgically inject mutations into the live Document Object Model (DOM), all without requiring engineering intervention or hardcoded backend changes.

---

## 2. System Architecture & Data Flow

The system operates on a deterministic, linear, 6-component pipeline to ensure safety, relevance, and visual fidelity:

1. **Extraction:** Scrape the live DOM and identify high-value text nodes (Headline, Subtext, CTA).  
2. **Vision Analysis:** Analyze the inbound Ad Creative for offers, promo codes, and brand colors.  
3. **Generation:** Draft context-aware, CRO-optimized copy mutations.  
4. **Verification:** Programmatically verify AI drafts against hallucinations.  
5. **Injection:** Render a proxied, interactive iframe with the mutated HTML.  

*(For a visual representation of this flow, refer to the architectural diagram at the end.)*

---

## 3. Key Components & Agent Design (The Engine)

### Component 1: The Ingestion & DOM Extractor

- **Function:** Fetches raw HTML and uses heuristic DOM parsing to identify the main Headline (<h1>/hero), Subtext (<p>), and CTA (<button>, <a>).  

- **PM Highlight (Heuristics & Fallbacks):**  
To prevent modifying the wrong elements, C1 utilizes "Negative Exclusion Rules" to ignore navigational menus, footers, and utility widgets. It stamps identified nodes with `data-troopod-target` attributes, ensuring deterministic downstream targeting rather than relying on brittle CSS classes. It also employs the Jina Reader API as a fallback if parsing fails.

---

### Component 2: The Relevance Gatekeeper (Vision Agent)

- **Function:** Utilizes the NVIDIA NIM Vision model (Llama 3.2 90B) to verify brand alignment and extract the ad's core offer, tagline, promo code, and a 2-color gradient hex palette.  

- **PM Highlight (Brand Safety):**  
Acts as a strict firewall. If the ad’s industry does not match the landing page, it throws a `BrandMismatchError` and aborts injection.

---

### Component 3 & 5: The Hybrid Optimizer & JSON Formatter

- **Function:** Generates text mutations and UI injections (Banner & Badge).  

- **PM Highlight (Identity Preservation):**  
Retains original product name and CTA utility words. Enforces +/- 30% character length tolerance to prevent UI breakage.

---

### Component 4: The Deterministic Hallucination Verifier (Feedback Loop)

- **Function:** Regex-based checkpoint validating AI-generated JSON.  

- **PM Highlight:**  
Uses zero-trust logic to verify numbers against original data. Retries up to 5 times on hallucination detection.

---

### Component 6: The Edge Injector

- **Function:** Reassembles HTML and injects CSS/JS payload.  

- **PM Highlight (Non-Destructive Mutation):**  
Uses `replaceTextSafely` to update only text nodes, preserving layout and structure.  

- **PM Highlight (Visual Fidelity & Lazy-Loading):**  
Forces lazy-loaded images and preserves original CSS styles dynamically.

---

## 4. Handling System Reliability & Edge Cases

- **Handling Hallucinations via Set Logic:**  
  - Textual & Structural controls  
  - Numerical validation via Set Theory subtraction  
  - Autonomous retry loop  

- **Handling Inconsistent Outputs & Truncation:**  
  - Regex-based JSON sanitation  

- **Enterprise LLM Temperature Control:**  
  - Locked to 0.0 for deterministic outputs  

- **Handling Broken UI (React Sibling Shift):**  
  - Fixed using `appendChild` instead of destructive DOM manipulation  

---

## 5. Technical Limitations & The Path to Production

### Limitation 1: Third-Party Iframe Sandboxing  
Strict browser security (CORS/CSP) blocks some websites.

### Limitation 2: SPA Router Crashes  
Modern SPAs fail due to iframe URL issues.

- **Cause:** `window.location.href` becomes undefined  
- **Mitigation:** Network interceptor + safe DOM mutation  
- **Production Path:** DNS-level reverse proxy (e.g., Cloudflare Workers)

---

## User Flow

1. User uploads ad creative  
2. Inputs landing page URL  
3. System analyzes ad intent  
4. Generates aligned messaging  
5. Injects personalized content  
6. User views optimized page  

---

## Success Metrics

- CTR improvement on CTA  
- Conversion rate uplift  
- Reduced bounce rate  
- Increased session duration  

---

## Architectural Diagram

[Architectural Diagram](./architecture.svg)
