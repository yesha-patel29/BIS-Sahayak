"""
main.py — FastAPI server for BIS Sahayak.

Version 3.0

Run:

    pip install -r requirements.txt

    uvicorn main:app --reload

API:

    http://127.0.0.1:8000

Docs:

    http://127.0.0.1:8000/docs
"""

import os
import re
import traceback

from typing import Optional, Any, Union, List, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from retrieval import KnowledgeBase
from conversation import ConversationManager


# =========================================================
# APP
# =========================================================

app = FastAPI(

    title="BIS Sahayak API",

    description=(
        "BIS Sahayak — Retrieval-based BIS "
        "standards assistant"
    ),

    version="3.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    # Development mode: allow all local origins and Chrome extension
    allow_origins=["*"],
    allow_origin_regex=r"^(chrome-extension://.*|http://localhost:.*|http://127\.0\.0\.1:.*)",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# PATHS
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(
        __file__
    )
)

DATA_DIR = os.path.join(
    BASE_DIR,
    "data"
)


# =========================================================
# KNOWLEDGE BASE
# =========================================================

print(
    "[BIS Sahayak] Starting knowledge base..."
)

kb = KnowledgeBase(
    data_dir=DATA_DIR
)

# =========================================================
# CONVERSATION MANAGER
# =========================================================

conv_mgr = ConversationManager()

print(
    "[BIS Sahayak] Conversation manager ready."
)


# =========================================================
# REQUEST MODELS
# =========================================================

class AskRequest(BaseModel):

    query: str

    language: str = "en"

    page_context: Any = ""


class ChatRequest(BaseModel):
    """Request model for the conversation-aware chat endpoint."""

    message: str

    language: str = "en"

    conversation_id: str = ""

    page_context: Any = ""

    history: list = []


class PageInfo(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    pageTitle: Optional[str] = None
    domain: Optional[str] = None
    type: Optional[str] = "product_page"
    product: Optional[Dict[str, Any]] = None
    productName: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    material: Optional[str] = None
    price: Optional[str] = None
    manufacturer: Optional[str] = None
    countryOfOrigin: Optional[str] = None
    claims: Any = []
    isiClaims: Any = []
    bisClaims: Any = []
    huid: Any = []
    standardNumbers: Any = []
    content: str = ""
    main_text: str = ""
    jsonLd: Any = None
    json_ld: Any = None
    specs: Dict[str, Any] = {}
    specifications: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    headings: List[str] = []
    selectedText: Optional[str] = None

    class Config:
        extra = "allow"

# Aliased for backwards compatibility
PageData = PageInfo


class AnalyzePageRequest(BaseModel):
    language: str = "en"
    page: Optional[PageInfo] = None
    page_data: Optional[PageInfo] = None
    conversation_id: Optional[str] = None


# =========================================================
# CHAT ENDPOINT (conversation-aware)
# =========================================================

@app.post("/api/chat")
def chat(req: ChatRequest):

    """
    Conversation-aware chat endpoint.

    Handles:
    1. Conversation memory & structured page context
    2. Query rewriting for follow-ups
    3. Multilingual query translation for retrieval
    4. Intent detection
    5. RAG retrieval
    6. Smart Gemini response
    7. Dynamic follow-up suggestions
    """

    if not req.message or not req.message.strip():

        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty."
        )

    user_message = req.message.strip()
    language = req.language or "en"

    try:

        # -------------------------------------------------
        # 1. Conversation management & page context parsing
        # -------------------------------------------------

        conversation_id = conv_mgr.get_or_create(
            req.conversation_id or None
        )

        # Safely parse page_context whether string or dict
        page_ctx_str = ""
        if isinstance(req.page_context, dict):
            p_info = req.page_context
            prod = p_info.get("product") or {}
            p_name = prod.get("name") or p_info.get("productName") or p_info.get("title") or ""
            p_cat = prod.get("category") or p_info.get("category") or ""
            p_brand = prod.get("brand") or p_info.get("brand") or ""
            p_claims = p_info.get("claims", [])
            p_claims_str = ", ".join(str(c) for c in p_claims) if isinstance(p_claims, list) else str(p_claims)
            p_content = p_info.get("content") or p_info.get("main_text") or ""
            page_ctx_str = (
                f"Product: {p_name}\n"
                f"Category: {p_cat}\n"
                f"Brand: {p_brand}\n"
                f"Claims: {p_claims_str}\n"
                f"Page URL: {p_info.get('url', '')}\n"
                f"Content Summary: {p_content[:1000]}"
            )
        elif isinstance(req.page_context, str):
            page_ctx_str = req.page_context.strip()

        # Store user message
        conv_mgr.add_message(
            conversation_id, "user", user_message
        )

        # Get conversation context for Gemini
        conversation_context = conv_mgr.get_context_for_prompt(
            conversation_id, max_turns=5
        )

        # Combine conversation context with page context for query rewriting
        combined_rewrite_context = conversation_context
        if page_ctx_str:
            combined_rewrite_context = f"Page Context:\n{page_ctx_str}\n\n{conversation_context}".strip()

        # -------------------------------------------------
        # 2. Query rewriting (follow-ups → standalone)
        # -------------------------------------------------

        rewritten_query = kb.rewrite_query(
            user_message, combined_rewrite_context
        )

        # -------------------------------------------------
        # 3. Translate to English for retrieval
        # -------------------------------------------------

        retrieval_query = kb.translate_to_english(
            rewritten_query
        )

        # -------------------------------------------------
        # 4. Intent detection
        # -------------------------------------------------

        intent = kb.detect_intent(retrieval_query)

        # -------------------------------------------------
        # 5. RAG retrieval
        # -------------------------------------------------

        result = kb.answer(
            retrieval_query,
            language=language,
            page_context=page_ctx_str,
            conversation_context=conversation_context
        )

        answer_text = result.get("answer", "")

        # -------------------------------------------------
        # 6. Generate follow-up suggestions
        # -------------------------------------------------

        suggested_questions = kb.generate_follow_ups(
            user_message, answer_text, intent, language
        )

        # -------------------------------------------------
        # 7. Store assistant response
        # -------------------------------------------------

        conv_mgr.add_message(
            conversation_id, "assistant", answer_text[:1000]
        )

        # -------------------------------------------------
        # 8. Confidence scoring
        # -------------------------------------------------

        best_score = 0.0
        if result.get("results"):
            best_score = float(
                result["results"][0].get("_score", 0)
            )

        confidence = round(
            min(best_score * 1.2, 1.0), 2
        )

        # -------------------------------------------------
        # 9. Return response
        # -------------------------------------------------

        return {

            "answer": answer_text,

            "language": language,

            "conversation_id": conversation_id,

            "intent": intent,

            "confidence": confidence,

            "citations": result.get("citations", []),

            "sources": result.get("citations", []),

            "suggested_questions": suggested_questions,

            "category": result.get("category"),

            "best_match": result.get("best_match"),

            "rewritten_query": rewritten_query,
        }

    except Exception as e:

        print("\n[ERROR] /api/chat failed:")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "The BIS Sahayak assistant "
                "encountered an internal error."
            )
        )


# =========================================================
# OFFLINE PAGE ANALYSIS BUILDER
# =========================================================

def _build_offline_page_analysis(
    lang,
    product_name,
    brand,
    model,
    material,
    page_type,
    detected_category,
    best_hit,
    claims_detected
):
    """
    Build a structured, grounded BIS page analysis report when Gemini is offline.
    Strictly distinguishes page claims from BIS database verification.
    """
    is_num = best_hit.get("is_number", "Not directly found") if best_hit else "Not directly found"
    std_title = best_hit.get("title", "") if best_hit else ""
    scheme = best_hit.get("scheme", "") if best_hit else ""
    scope = best_hit.get("scope_description", "") if best_hit else ""
    is_mandatory = "Mandatory" in str(best_hit.get("certification_type", "")) if best_hit else False

    claims_text = ", ".join(claims_detected) if claims_detected else "None detected"

    if lang == "hi":
        claims_summary = (
            f"पेज पर पाए गए दावे: **{claims_text}**"
            if claims_detected
            else "वेबपेज पर कोई स्पष्ट BIS या ISI प्रमाणन का दावा नहीं मिला।"
        )
        mandatory_text = "हाँ (अनिवार्य QCO आदेश के तहत)" if is_mandatory else "स्वैच्छिक / लागू नहीं"
        return f"""## 📄 वेबपेज विश्लेषण रिपोर्ट

**पहचाना गया उत्पाद:** {product_name}  
**ब्रांड:** {brand} | **मॉडल:** {model} | **सामग्री:** {material}  
**श्रेणी:** {detected_category} | **पेज का प्रकार:** {page_type}

---

### 🏛️ BIS प्रासंगिकता
यह उत्पाद भारतीय मानक ब्यूरो (BIS) के गुणवत्ता और उपभोक्ता सुरक्षा मानकों के दायरे में आता है।
- **अनिवार्य प्रमाणन:** {mandatory_text}
- **प्रमाणन योजना:** {scheme or 'ISI / उत्पाद प्रमाणन योजना'}

### 📋 लागू भारतीय मानक (IS)
**{is_num}** — {std_title}
> {scope[:250] if scope else 'भारतीय मानक ब्यूरो के तहत विनिर्देश।'}

### 🔍 पेज पर किए गए दावे
{claims_summary}

### ⚠️ स्वतंत्र सत्यापन स्थिति
**सत्यापन अस्वीकरण:** केवल वेबपेज पर "ISI मार्क" या "BIS प्रमाणित" लिखने से उत्पाद सत्यापित नहीं माना जाता। उत्पाद की प्रामाणिकता के लिए उस पर 7-अंकों का आधिकारिक **CM/L लाइसेंस नंबर** या सोने के आभूषणों के लिए 6-अंकीय **HUID** मुद्रित होना अनिवार्य है।

### ✅ उपभोक्ता सत्यापन चेकलिस्ट
1. **CM/L लाइसेंस नंबर जांचें:** उत्पाद और पैकेजिंग पर ISI मार्क के नीचे 7-अंकों का लाइसेंस नंबर देखें।
2. **BIS CARE ऐप पर सत्यापन करें:** आधिकारिक **BIS CARE** मोबाइल ऐप या [manakonline.in](https://www.manakonline.in/) पर लाइसेंस नंबर दर्ज कर निर्माता का नाम और वैधता सत्यापित करें।
3. **मानक संख्या का मिलान करें:** उत्पाद श्रेणी के लिए लागू मानक ({is_num}) का मिलान करें।
4. **शिकायत निवारण:** नकली या भ्रामक ISI मार्क पाए जाने पर BIS पोर्टल पर शिकायत दर्ज की जा सकती है।"""

    elif lang == "gu":
        claims_summary = (
            f"પેજ પર મળેલા દાવા: **{claims_text}**"
            if claims_detected
            else "વેબપેજ પર કોઈ સ્પષ્ટ BIS અથવા ISI પ્રમાણપત્રનો દાવો મળ્યો નથી."
        )
        mandatory_text = "હા (ફરજિયાત QCO ઓર્ડર હેઠળ)" if is_mandatory else "મરજિયાત / લાગુ નથી"
        return f"""## 📄 વેબપેજ વિશ્લેષણ અહેવાલ

**ઓળખાયેલ ઉત્પાદન:** {product_name}  
**બ્રાન્ડ:** {brand} | **મોડેલ:** {model} | **મટિરિયલ:** {material}  
**કેટેગરી:** {detected_category} | **પેજ પ્રકાર:** {page_type}

---

### 🏛️ BIS સુસંગતતા
આ ઉત્પાદન બ્યુરો ઓફ ઇન્ડિયન સ્ટાન્ડર્ડ્સ (BIS) ના ગુણવત્તા અને સલામતી નિયમો હેઠળ આવે છે.
- **ફરજિયાત પ્રમાણપત્ર:** {mandatory_text}
- **યોજના:** {scheme or 'ISI / પ્રોડક્ટ સર્ટિફિકેશન સ્કીમ'}

### 📋 લાગુ પડતું ભારતીય ધોરણ (IS)
**{is_num}** — {std_title}
> {scope[:250] if scope else 'બ્યુરો ઓફ ઇન્ડિયન સ્ટાન્ડર્ડ્સ હેઠળ વિશિષ્ટતાઓ.'}

### 🔍 પેજ પરના દાવા
{claims_summary}

### ⚠️ સ્વતંત્ર ચકાસણી સ્થિતિ
**અસ્વીકરણ:** માત્ર વેબપેજ પર "ISI માર્ક" લખેલું હોવાથી ઉત્પાદન પ્રમાણિત સાબિત થતું નથી. અસલી BIS લાયસન્સ માટે ઉત્પાદન પર 7-અંકનો સત્તાવાર **CM/L લાયસન્સ નંબર** અથવા સોના માટે 6-અંકનો **HUID** હોવો જરૂરી છે.

### ✅ ગ્રાહક ચકાસણી ચેકલિસ્ટ
1. **CM/L લાયસન્સ નંબર તપાસો:** ઉત્પાદન અને પેકેજિંગ પર ISI માર્કની નીચે 7-અંકનો લાયસન્સ નંબર શોધો.
2. **BIS CARE એપ પર ચકાસો:** સત્તાવાર **BIS CARE** એપ અથવા [manakonline.in](https://www.manakonline.in/) પર લાયસન્સ નંબર દાખલ કરીને ઉત્પાદકની વિગતો ચકાસો.
3. **માનક નંબર ચકાસો:** ઉત્પાદન કેટેગરી માટે લાગુ પડતા માનક ({is_num}) ની ખાતરી કરો.
4. **ગ્રાહક સુરક્ષા:** નકલી માર્કિંગ જણાય તો BIS પોર્ટલ પર ફરિયાદ નોંધાવો."""

    else:
        claims_summary = (
            f"Claims detected on page: **{claims_text}**"
            if claims_detected
            else "No explicit BIS or ISI certification claims were detected on this webpage."
        )
        mandatory_text = "Yes (Mandatory under Quality Control Order)" if is_mandatory else "Voluntary / Consult QCO status"
        return f"""## 📄 Webpage Analysis Report

**Product Identified:** {product_name}  
**Brand:** {brand} | **Model:** {model} | **Material:** {material}  
**Category:** {detected_category} | **Page Type:** {page_type}

---

### 🏛️ BIS Relevance
This product category falls under the quality, safety, and compliance scope of the Bureau of Indian Standards (BIS).
- **Mandatory Certification:** {mandatory_text}
- **Certification Scheme:** {scheme or 'ISI / Product Certification Scheme'}

### 📋 Applicable Indian Standard (IS)
**{is_num}** — {std_title}
> {scope[:250] if scope else 'Standard specification under the Bureau of Indian Standards catalogue.'}

### 🔍 Claims Made on Webpage
{claims_summary}

### ⚠️ Independent Verification Status
**Consumer Protection Notice:** A seller or webpage claiming "ISI Mark" or "BIS Certified" does **not** constitute independent legal verification. Genuine BIS certification requires an official 7-digit **CM/L license number** (or 6-digit **HUID** for hallmarked jewellery) visibly stamped on the product.

### ✅ What You Can Check (Actionable Checklist)
1. **Inspect for CM/L License Number:** Look for the standard ISI mark on the product with the format `CM/L-XXXXXXX` directly below the mark.
2. **Verify on Official BIS CARE App:** Download the **BIS CARE** mobile app or visit [manakonline.in](https://www.manakonline.in/) to confirm the manufacturer's name, brand, address, and license validity.
3. **Verify Applicable IS Number:** Confirm that the standard printed ({is_num}) matches the specific appliance or goods being purchased.
4. **Report Counterfeits:** If a product claims an ISI mark without a valid CM/L number, report it directly via the consumer grievance redressal feature in the BIS CARE app."""


# =========================================================
# PAGE ANALYSIS ENDPOINT
# =========================================================

@app.post("/api/analyze-page")
def analyze_page(req: AnalyzePageRequest):
    """
    Analyzes visible webpage content on explicit user button click.
    """
    try:
        lang = req.language or "en"
        page = req.page or req.page_data or PageData()
        url = (page.url or "").strip()
        title = (page.title or "").strip()
        content = (page.content or page.main_text or "").strip()
        json_ld = page.jsonLd or page.json_ld or {}
        specs = page.specs or page.specifications or {}
        headings = page.headings or []

        if isinstance(page.claims, list):
            claims_detected = [str(c) for c in page.claims]
        elif isinstance(page.claims, dict):
            claims_detected = list(page.claims.get("raw_matches", []))
            if page.claims.get("has_isi_claim") and "ISI Mark" not in claims_detected:
                claims_detected.append("ISI Mark")
            if page.claims.get("has_bis_claim") and "BIS Certified" not in claims_detected:
                claims_detected.append("BIS Certified")
            if page.claims.get("has_hallmark_claim") and "BIS Hallmark" not in claims_detected:
                claims_detected.append("BIS Hallmark")
            if page.claims.get("has_huid_claim") and "HUID" not in claims_detected:
                claims_detected.append("HUID")
            for isn in page.claims.get("is_numbers", []):
                if isn not in claims_detected:
                    claims_detected.append(isn)
        else:
            claims_detected = []

        if not title and not content and not url:
            raise HTTPException(status_code=400, detail="Page content cannot be empty.")

        # 1. Conversation Management
        conversation_id = conv_mgr.get_or_create(req.conversation_id or None)

        # 2. Page Type Detection
        page_type = "unknown"
        url_lower = url.lower()
        text_sample = (title + " " + " ".join(headings) + " " + content[:800]).lower()

        if json_ld and json_ld.get("name"):
            page_type = "product_page"
        elif any(ecom in url_lower for ecom in ["amazon.", "flipkart.", "myntra.", "croma.", "reliancedigital.", "indiamart.", "gem.gov.in", "/product", "/dp/", "/item/"]):
            page_type = "ecommerce_page"
        elif "bis.gov.in" in url_lower or "manakonline" in url_lower:
            page_type = "bis_page"
        elif any(w in text_sample for w in ["manufacturer", "factory", "exporter", "supplier", "industrial supply", "oem"]):
            page_type = "manufacturer_page"
        elif any(w in text_sample for w in ["news", "article", "report", "gazette", "press release"]):
            page_type = "news_article"
        elif specs or any(w in text_sample for w in ["price", "specification", "specifications", "model number", "features", "warranty"]):
            page_type = "product_page"
        else:
            page_type = "document"

        # 3. Product Identification
        product_name = ""
        if json_ld and json_ld.get("name"):
            product_name = json_ld["name"].strip()
        elif headings:
            product_name = headings[0].strip()
        elif title:
            cleaned_title = re.sub(r'\s*([\|\-\–].*)$', '', title).strip()
            product_name = cleaned_title if len(cleaned_title) > 3 else title

        if len(product_name) > 120:
            product_name = product_name[:117] + "..."

        brand = (
            json_ld.get("brand") or
            page.metadata.get("brand") or
            specs.get("Brand") or
            specs.get("Brand Name") or
            specs.get("Manufacturer") or
            "Not found on page"
        )
        model = (
            json_ld.get("model") or
            specs.get("Model") or
            specs.get("Model Number") or
            specs.get("Item Model Number") or
            "Not found on page"
        )
        material = (
            specs.get("Material") or
            specs.get("Primary Material") or
            specs.get("Outer Material") or
            "Not found on page"
        )

        cat_search_text = f"{product_name} {title} {content[:500]}"
        detected_category = kb.detect_category(cat_search_text) or "General Consumer Product"

        # 4. BIS Retrieval
        search_terms = [product_name]
        is_nums = re.findall(r'\bis\s*[:\-]?\s*(\d{3,5})\b', text_sample, re.IGNORECASE)
        if is_nums:
            search_terms.append(f"IS {is_nums[0]}")
        if material != "Not found on page":
            search_terms.append(material)

        rag_query = " ".join(search_terms)
        hits = kb.search(rag_query, top_k=5, min_score=0.10)
        best_hit = hits[0] if hits else None

        # 5. Gemini / Smart Structured Synthesis
        lang_names = {"en": "English", "hi": "Hindi (हिंदी)", "gu": "Gujarati (ગુજરાતી)"}
        resp_lang = lang_names.get(lang, "English")

        gemini_prompt = f"""You are BIS Sahayak, an AI compliance analyst for the Bureau of Indian Standards (BIS).
Analyze the following webpage content from a BIS compliance and consumer protection perspective.

WEBPAGE DETAILS:
- URL: {url}
- Title: {title}
- Detected Page Type: {page_type}
- Identified Product: {product_name}
- Brand: {brand}
- Model: {model}
- Material: {material}
- Specifications: {str(specs)[:500]}
- Explicit Certification Claims Found on Page: {claims_detected}
- Cleaned Text Snippet: {content[:1500]}

RETRIEVED BIS KNOWLEDGE BASE CONTEXT:
{kb._format_standard(best_hit, include_scope=True) if best_hit else "No directly matching standard in local index."}

CRITICAL RULES:
1. DO NOT declare that the product is officially BIS certified without verified license proof (CM/L number). Distinguish strictly between "Claims made on the webpage" and "Independent BIS verification".
2. If the product falls under a mandatory BIS scheme (ISI or CRS or Hallmarking), clearly specify the requirement.
3. Structure your response clearly using markdown headings:
   ## Page Analysis
   **Product:** {product_name}
   **Category / Type:** {detected_category}

   ### BIS Relevance
   [Explain whether and why this product falls under Indian Standards]

   ### Applicable BIS Information
   [Mention exact standard numbers, titles, schemes, and mandatory status]

   ### What the Page Claims
   [List explicit claims like "ISI mark" or state that no claims were detected]

   ### Independent Verification Status
   ⚠️ [Explain that claims on a webpage cannot be treated as verified without a valid 7-digit CM/L number or 6-digit HUID]

   ### What You Can Check
   [Provide 3-4 actionable verification steps for the consumer/buyer]

4. Respond ENTIRELY in {resp_lang}. Keep tone objective, authoritative, and helpful."""

        ai_report = kb._gemini_call(gemini_prompt, fallback=None)

        if not ai_report:
            ai_report = _build_offline_page_analysis(
                lang=lang,
                product_name=product_name,
                brand=brand,
                model=model,
                material=material,
                page_type=page_type,
                detected_category=detected_category,
                best_hit=best_hit,
                claims_detected=claims_detected
            )

        # 6. Citations
        citations = []
        if best_hit:
            citations.append({
                "is_number": str(best_hit.get("is_number", "")),
                "title": str(best_hit.get("title", "")),
                "scheme": str(best_hit.get("scheme", "")),
                "source_url": str(best_hit.get("source_url", "")),
                "verified": str(best_hit.get("verified", ""))
            })

        # 7. Store in Conversation Memory for Follow-Ups
        conv_summary_user = f"Analyzed page: {product_name} (URL: {url[:80]})"
        conv_summary_asst = (
            f"Page Analysis for {product_name}: "
            f"Applicable standard: {best_hit.get('is_number', 'Not identified') if best_hit else 'General'} "
            f"({best_hit.get('title', '') if best_hit else ''}). "
            f"Claims on page: {', '.join(claims_detected) if claims_detected else 'None'}."
        )
        conv_mgr.add_message(conversation_id, "user", conv_summary_user)
        conv_mgr.add_message(conversation_id, "assistant", conv_summary_asst)

        # 8. Follow-up suggestions
        suggested_followups = {
            "en": [
                f"Is certification mandatory for {product_name[:22]}?",
                "What testing requirements apply?",
                "How to verify the CM/L license number?"
            ],
            "hi": [
                f"क्या {product_name[:18]} का प्रमाणन अनिवार्य है?",
                "इसके लिए कौन से टेस्ट आवश्यक हैं?",
                "CM/L लाइसेंस कैसे सत्यापित करें?"
            ],
            "gu": [
                f"શું {product_name[:18]} માટે પ્રમાણન ફરજિયાત છે?",
                "કયા ટેસ્ટિંગ જરૂરી છે?",
                "CM/L લાયસન્સ કેવી રીતે ચકાસવું?"
            ]
        }

        return {
            "success": True,
            "conversation_id": conversation_id,
            "markdown_report": ai_report,
            "page_analysis": {
                "page_type": page_type,
                "product": product_name,
                "brand": brand,
                "model": model,
                "material": material,
                "category": detected_category,
                "claims": claims_detected
            },
            "bis_analysis": {
                "applicable_standard": best_hit.get("is_number") if best_hit else None,
                "standard_title": best_hit.get("title") if best_hit else None,
                "scheme": best_hit.get("scheme") if best_hit else None,
                "mandatory": "Mandatory" in str(best_hit.get("certification_type", "")) if best_hit else False
            },
            "citations": citations,
            "sources": citations,
            "suggested_questions": suggested_followups.get(lang, suggested_followups["en"]),
            "confidence": round(float(best_hit.get("_score", 0.85)) * 1.1, 2) if best_hit else 0.70
        }

    except HTTPException:
        raise
    except Exception as e:
        print("[ERROR] /api/analyze-page failed:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Page analysis failed.")


# =========================================================
# ROOT & STATIC WEB APP
# =========================================================

HTML_PATH = os.path.join(os.path.dirname(BASE_DIR), "bis-sahayak-v2.html.html")

@app.get("/")
def root(request: Request):
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return {
            "status": "ok",
            "message": "BIS Sahayak API is running.",
            "version": "3.0.0",
            "rows_loaded": len(kb.df),
            "categories": sorted(kb.df["category_file"].unique().tolist())
        }

    if os.path.exists(HTML_PATH):
        return FileResponse(HTML_PATH, media_type="text/html")

    return {
        "status": "ok",
        "message": "BIS Sahayak API is running.",
        "version": "3.0.0",
        "rows_loaded": len(kb.df),
        "categories": sorted(kb.df["category_file"].unique().tolist())
    }

@app.get("/app")
def serve_app():
    if os.path.exists(HTML_PATH):
        return FileResponse(HTML_PATH, media_type="text/html")
    raise HTTPException(status_code=404, detail="Web application HTML not found.")


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "BIS Sahayak",
        "knowledge_base_loaded": True,
        "rows_loaded": len(kb.df) if hasattr(kb, "df") else 0,
        "categories": kb.df["category_file"].nunique() if hasattr(kb, "df") else 0
    }


# =========================================================
# ASK ASSISTANT
# =========================================================

@app.post("/api/ask")
def ask(
    req: AskRequest
):

    # -----------------------------------------------------
    # Validate request
    # -----------------------------------------------------

    if req.query is None:

        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty."
        )

    query = req.query.strip()

    if not query:

        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty."
        )

    # -----------------------------------------------------
    # Ask knowledge base
    # -----------------------------------------------------

    try:

        result = kb.answer(
            query,
            language=req.language,
            page_context=req.page_context.strip()
        )

        return result

    except Exception as e:

        print(
            "\n[ERROR] /api/ask failed:"
        )

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=(
                "The BIS Sahayak assistant "
                "encountered an internal error."
            )
        )


# =========================================================
# FIND STANDARD
# =========================================================

@app.get("/api/standards")
def standards(

    category: str = "all",

    q: str = ""
):

    try:

        # -------------------------------------------------
        # Search mode
        # -------------------------------------------------

        if q.strip():

            hits = kb.search(

                q,

                top_k=20,

                min_score=0.05,

                category=(
                    None
                    if category == "all"
                    else category
                )
            )

            return {

                "query": q,

                "category": category,

                "count": len(
                    hits
                ),

                "results": hits
            }

        # -------------------------------------------------
        # Browse mode
        # -------------------------------------------------

        df = kb.df

        if category != "all":

            mask = df[
                "category_file"
            ].str.contains(

                category,

                case=False,

                na=False
            )

            df = df[
                mask
            ]

        # -------------------------------------------------
        # Make sure NaN cannot reach JSON
        # -------------------------------------------------

        df = df.fillna("")

        results = []

        for record in df.to_dict(
            orient="records"
        ):

            results.append(
                kb._safe_row(
                    record
                )
            )

        return {

            "query": "",

            "category": category,

            "count": len(
                results
            ),

            "results": results
        }

    except Exception as e:

        print(
            "\n[ERROR] /api/standards failed:"
        )

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=(
                "Unable to retrieve "
                "BIS standards."
            )
        )


# =========================================================
# CATEGORIES
# =========================================================

@app.get("/api/categories")
def categories():

    categories = sorted(

        kb.df[
            "category_file"
        ]
        .unique()
        .tolist()
    )

    return {

        "count": len(
            categories
        ),

        "categories": categories
    }


# =========================================================
# STATISTICS
# =========================================================

@app.get("/api/stats")
def stats():

    counts = (

        kb.df[
            "category_file"
        ]

        .value_counts()

        .to_dict()
    )

    return {

        "total_standards": len(
            kb.df
        ),

        "total_categories": len(
            counts
        ),

        "categories": counts
    }


# =========================================================
# TESTING LABS
# =========================================================

@app.get("/api/labs")
def get_labs(
    category: str = "all",
    state: str = "all",
    q: str = ""
):

    """
    Return testing labs filtered by category, state,
    and/or search query.
    """

    try:

        results = kb.get_labs(
            category=category,
            state=state,
            query=q.strip()
        )

        return {

            "category": category,

            "state": state,

            "query": q,

            "count": len(results),

            "labs": results
        }

    except Exception as e:

        print(
            "\n[ERROR] /api/labs failed:"
        )

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=(
                "Unable to retrieve "
                "testing labs."
            )
        )


@app.post("/api/labs/recommend")
def recommend_labs(
    req: AskRequest
):

    """
    Given a product/standard query, recommend
    appropriate testing labs.
    """

    if not req.query or not req.query.strip():

        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty."
        )

    try:

        result = kb.recommend_labs(
            req.query.strip()
        )

        return result

    except Exception as e:

        print(
            "\n[ERROR] /api/labs/recommend failed:"
        )

        traceback.print_exc()

        raise HTTPException(

            status_code=500,

            detail=(
                "Unable to recommend "
                "testing labs."
            )
        )


@app.get("/api/labs/states")
def lab_states():

    """
    Return list of unique states from lab data
    for filter dropdown.
    """

    try:

        states = kb.get_lab_states()

        return {
            "count": len(states),
            "states": states
        }

    except Exception:

        return {
            "count": 0,
            "states": []
        }