# BIS Sahayak – AI-Powered Conversational Assistant & Browser Copilot for Indian Standards

**Smart India Hackathon 2026**

BIS Sahayak is an AI-powered conversational assistant designed to simplify access to information related to Indian Standards and Bureau of Indian Standards (BIS) services. It combines a Retrieval-Augmented Generation (RAG) approach with a lightweight Browser Copilot to help users find, understand, and verify BIS-related information seamlessly.

The project was developed as a solution to the SIH problem statement, with the aim of making complex standards, certification procedures, and testing lab details easily accessible to industries, MSMEs, startups, students, and consumers.

---

## Problem Statement

Information related to Indian Standards, BIS certification, testing requirements, hallmarking, and licensing procedures is distributed across multiple portals, technical gazettes, and PDF documents.

Users frequently face challenges in:
- Identifying applicable Indian Standards (IS numbers) for their products.
- Understanding mandatory certification requirements and compliance procedures.
- Locating accredited testing laboratories and facilities.
- Accessing and interpreting dense technical BIS specifications.
- Navigating multiple disjoint official websites.

BIS Sahayak simplifies this process through a unified, conversational interface and a proactive browser copilot.

---

## Our Solution

BIS Sahayak provides a two-pronged solution:

1. **Conversational Assistant (Web Application):** A RAG-powered portal where users can query product standards, compliance procedures, and laboratory information in natural language.
2. **Browser Copilot (Chrome Extension):** A contextual extension that scans product pages and web content as users browse, instantly identifying relevant BIS standards and compliance criteria without requiring tab switching.

The system uses TF-IDF similarity search over curated BIS datasets and optionally integrates Google Gemini for contextual, natural language answer generation.

---

## Key Features

### 1. RAG-Powered Conversational Assistant
- Natural language query understanding for BIS standards and regulations.
- Dual-mode operation: Hybrid TF-IDF retrieval with optional Google Gemini API generation (gracefully falls back to search retrieval without an API key).
- Multi-turn conversation support with contextual continuity.

### 2. Smart Standard Discovery & Verification
- Identifies mandatory and voluntary Indian Standards (IS codes).
- Covers key categories including Electronics, Food & Water, Footwear, Construction, Textiles, Jewellery & Hallmarking, and Consumer Products.

### 3. Contextual Browser Copilot
- Chrome extension that extracts page context from e-commerce and product pages.
- Checks compliance criteria and flags mandatory certifications on the fly via the `/api/analyze-page` endpoint.

### 4. Testing Laboratory Directory & Recommendations
- Search and filter accredited BIS testing laboratories across Indian states.
- Recommends suitable testing facilities based on product categories and applicable standards.

### 5. Multilingual & Terminology Mapping
- Built-in synonym matching and product terminology mapping to bridge colloquial consumer terms with official BIS terminology.

---

## Technology Stack

| Component | Technology |
|---|---|
| **Frontend** | HTML5, CSS3, Modern JavaScript |
| **Backend** | Python 3.12+, FastAPI, Uvicorn |
| **Retrieval Engine** | TF-IDF Vectorization, Scikit-Learn, Pandas |
| **AI / LLM** | Google Gemini API (`google-genai`) |
| **Browser Extension** | Chrome Extensions API (Manifest V3) |
| **Data Format** | Curated CSV Knowledge Bases |

---

## Project Structure

```text
BIS SAHAYAK/
├── backend/
│   ├── main.py              # FastAPI application & REST endpoints
│   ├── retrieval.py         # RAG core, TF-IDF search, & Gemini integration
│   ├── conversation.py      # Session and conversation management
│   ├── requirements.txt     # Python dependencies
│   └── data/                # BIS standards & testing lab datasets (.csv)
├── extension/               # Chrome Browser Copilot extension
│   ├── manifest.json
│   ├── popup/
│   └── content/
├── bis-sahayak-v2.html.html # Web application user interface
├── run.py                   # Root startup script
└── start_backend.bat        # Windows quick-launch script

## System Architecture
