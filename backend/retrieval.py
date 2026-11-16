"""
retrieval.py — BIS Sahayak RAG / retrieval core.

Version 3.0

Responsibilities:
    1. Load BIS standards from CSV files.
    2. Build a TF-IDF search index.
    3. Understand common user/product terminology.
    4. Retrieve the most relevant BIS standards.
    5. Generate a clearer assistant-style answer.
    6. Return citation and relevance information.
    7. Safely convert pandas NaN values before returning JSON.

No external API key required.
"""

import glob
import os
import re

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------
# Gemini (optional — works without API key too)
# ---------------------------------------------------------

GEMINI_AVAILABLE = False
GEMINI_CLIENT = None

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if GEMINI_API_KEY:

    try:
        # New package (recommended)
        from google import genai

        GEMINI_CLIENT = genai.Client(
            api_key=GEMINI_API_KEY
        )
        GEMINI_AVAILABLE = True
        print("[BIS Sahayak] Gemini AI enabled (google-genai).")

    except ImportError:

        try:
            # Old package (fallback)
            import google.generativeai as genai_old

            genai_old.configure(api_key=GEMINI_API_KEY)
            GEMINI_CLIENT = genai_old.GenerativeModel(
                "gemini-2.0-flash"
            )
            GEMINI_AVAILABLE = True
            print(
                "[BIS Sahayak] Gemini AI enabled "
                "(google-generativeai, deprecated)."
            )

        except ImportError:
            print(
                "[BIS Sahayak] No Gemini package installed. "
                "Running in TF-IDF-only mode."
            )
else:
    print(
        "[BIS Sahayak] No GEMINI_API_KEY set. "
        "Running in TF-IDF-only mode."
    )


class KnowledgeBase:

    def __init__(self, data_dir="data"):

        self.data_dir = data_dir

        # -------------------------------------------------
        # Load knowledge base
        # -------------------------------------------------

        self.df = self._load_all_csvs()

        # -------------------------------------------------
        # Build search index
        # -------------------------------------------------

        self.vectorizer = None
        self.matrix = None

        self._build_index()

        print(
            f"[BIS Sahayak] Loaded {len(self.df)} standards "
            f"from {self.df['category_file'].nunique()} categories."
        )

        # -------------------------------------------------
        # Load testing labs data
        # -------------------------------------------------

        self.labs_df = self._load_labs()

        print(
            f"[BIS Sahayak] Loaded {len(self.labs_df)} testing labs."
        )

    # =====================================================
    # LOAD CSV FILES
    # =====================================================

    def _load_all_csvs(self):

        frames = []

        csv_files = sorted(
            glob.glob(
                os.path.join(
                    self.data_dir,
                    "*.csv"
                )
            )
        )

        if not csv_files:

            raise RuntimeError(
                f"No CSV files found in '{self.data_dir}/'"
            )

        for path in csv_files:

            # Skip testing labs CSV (loaded separately)
            if "testing_labs" in os.path.basename(path):
                continue

            category = os.path.splitext(
                os.path.basename(path)
            )[0]

            try:

                df = pd.read_csv(path)

                # Remove completely empty rows
                df = df.dropna(how="all")

                # Add category derived from filename
                df["category_file"] = category

                frames.append(df)

                print(
                    f"[KB] Loaded {len(df)} rows "
                    f"from {category}.csv"
                )

            except Exception as e:

                print(
                    f"[KB] WARNING: Could not read "
                    f"{path}: {e}"
                )

        if not frames:

            raise RuntimeError(
                "CSV files were found but none "
                "could be loaded."
            )

        combined = pd.concat(
            frames,
            ignore_index=True
        )

        # -------------------------------------------------
        # Remove rows without IS number
        # -------------------------------------------------

        if "is_number" in combined.columns:

            combined = combined.dropna(
                subset=["is_number"]
            )

            combined = combined[
                combined["is_number"]
                .astype(str)
                .str.strip()
                != ""
            ]

        # -------------------------------------------------
        # Replace NaN values
        #
        # IMPORTANT:
        # This prevents FastAPI from producing invalid
        # JSON responses later.
        # -------------------------------------------------

        combined = combined.fillna("")

        return combined.reset_index(drop=True)

    # =====================================================
    # SAFE VALUE
    # =====================================================

    def _safe_value(self, value):

        """
        Convert pandas/NumPy values into safe JSON-friendly
        Python values.
        """

        if value is None:
            return ""

        try:

            if pd.isna(value):
                return ""

        except Exception:
            pass

        return value

    # =====================================================
    # SAFE ROW
    # =====================================================

    def _safe_row(self, row):

        """
        Convert a pandas row/dictionary into a JSON-safe
        dictionary.
        """

        cleaned = {}

        for key, value in row.items():

            value = self._safe_value(value)

            # Convert numpy scalar values
            if hasattr(value, "item"):

                try:
                    value = value.item()

                except Exception:
                    value = str(value)

            cleaned[str(key)] = value

        return cleaned

    # =====================================================
    # SEARCHABLE ROW TEXT
    # =====================================================

    def _row_text(self, row):

        """
        Combine useful fields into one searchable document.

        The more useful fields we include here, the better
        TF-IDF can understand natural user questions.
        """

        fields = [

            "is_number",

            "title",

            "scope_description",

            "scheme",

            "certification_type",

            "product",

            "category",

            "keywords",

            "description",

            "application",

            "testing",

        ]

        parts = []

        for field in fields:

            value = row.get(
                field,
                ""
            )

            if pd.isna(value):
                continue

            value = str(value).strip()

            if value:
                parts.append(value)

        return " ".join(parts)

    # =====================================================
    # BUILD TF-IDF INDEX
    # =====================================================

    def _build_index(self):

        texts = [
            self._row_text(row)
            for _, row in self.df.iterrows()
        ]

        self.vectorizer = TfidfVectorizer(

            stop_words="english",

            ngram_range=(1, 2),

            sublinear_tf=True,

            max_features=30000
        )

        self.matrix = self.vectorizer.fit_transform(
            texts
        )

        print(
            f"[KB] Search index built: "
            f"{self.matrix.shape[0]} documents, "
            f"{self.matrix.shape[1]} terms."
        )

    # =====================================================
    # QUERY CLEANING
    # =====================================================

    def _clean_query(self, query):

        if not query:
            return ""

        query = str(query).strip()

        # Remove unnecessary punctuation while preserving Indic scripts (Devanagari & Gujarati)
        query = re.sub(
            r"[^\w\s\-\/\u0900-\u097F\u0A80-\u0AFF]",
            " ",
            query
        )

        # Remove repeated whitespace
        query = re.sub(
            r"\s+",
            " ",
            query
        )

        return query.strip()

    # =====================================================
    # QUERY EXPANSION
    # =====================================================

    def _expand_query(self, query):

        """
        Add common BIS/product terminology.

        Example:

            "Which standard applies to LED bulbs?"

        becomes something closer to:

            "LED bulbs lamps lighting electrical
             LED lamps safety requirements"

        This helps TF-IDF match the user's everyday
        language against formal BIS terminology.
        """

        query_lower = query.lower()

        expansions = []

        keyword_groups = {

            # Electronics
            "led": [
                "LED",
                "LED lamp",
                "LED bulb",
                "lighting",
                "electrical lamp"
            ],

            "bulb": [
                "bulb",
                "lamp",
                "LED lamp",
                "lighting"
            ],

            "light": [
                "lighting",
                "lamp",
                "LED"
            ],

            "lamp": [
                "lamp",
                "lighting",
                "LED"
            ],

            "electronics": [
                "electrical",
                "electronic",
                "appliance"
            ],

            # Consumer Products & Safety
            "helmet": [
                "helmet",
                "helmets",
                "protective helmets",
                "two wheeler",
                "IS 4151"
            ],

            "helmets": [
                "helmet",
                "helmets",
                "protective helmets",
                "two wheeler",
                "IS 4151"
            ],

            "toy": [
                "toy",
                "toys",
                "safety of toys",
                "IS 9873"
            ],

            "toys": [
                "toy",
                "toys",
                "safety of toys",
                "IS 9873"
            ],

            "cooker": [
                "pressure cooker",
                "domestic pressure cookers",
                "IS 2347"
            ],

            "cookers": [
                "pressure cooker",
                "domestic pressure cookers",
                "IS 2347"
            ],

            "cable": [
                "cables",
                "PVC insulated cables",
                "electrical wire",
                "IS 694"
            ],

            "cables": [
                "cables",
                "PVC insulated cables",
                "electrical wire",
                "IS 694"
            ],

            "wire": [
                "cables",
                "PVC insulated cables",
                "electrical wire",
                "IS 694"
            ],

            "wires": [
                "cables",
                "PVC insulated cables",
                "electrical wire",
                "IS 694"
            ],

            "stove": [
                "gas stove",
                "domestic gas stoves",
                "LPG",
                "IS 4246"
            ],

            "stoves": [
                "gas stove",
                "domestic gas stoves",
                "LPG",
                "IS 4246"
            ],

            # Jewellery
            "gold": [
                "gold",
                "jewellery",
                "hallmark",
                "purity"
            ],

            "silver": [
                "silver",
                "jewellery",
                "hallmark",
                "purity"
            ],

            "jewellery": [
                "jewellery",
                "hallmark",
                "gold",
                "silver",
                "purity"
            ],

            "jewelry": [
                "jewellery",
                "hallmark",
                "gold",
                "silver",
                "purity"
            ],

            "hallmark": [
                "hallmark",
                "hallmarking",
                "jewellery",
                "purity"
            ],

            "purity": [
                "purity",
                "hallmark",
                "gold",
                "silver"
            ],

            # Food & water
            "water": [
                "water",
                "packaged water",
                "drinking water",
                "mineral water"
            ],

            "drinking": [
                "drinking water",
                "water",
                "packaged water",
                "IS 14543"
            ],

            "bottle": [
                "bottle",
                "PET bottle",
                "packaged water",
                "IS 15410"
            ],

            "food": [
                "food",
                "food product",
                "food safety"
            ],

            # Footwear
            "footwear": [
                "footwear",
                "shoes",
                "safety footwear",
                "IS 15298"
            ],

            "shoe": [
                "shoe",
                "shoes",
                "footwear",
                "safety footwear"
            ],

            "shoes": [
                "shoe",
                "shoes",
                "footwear",
                "safety footwear"
            ],

            "sole": [
                "sole",
                "footwear",
                "shoe"
            ],

            # Construction
            "steel": [
                "steel",
                "TMT",
                "reinforcement",
                "structural"
            ],

            "tmt": [
                "TMT",
                "steel",
                "reinforcement",
                "IS 1786"
            ],

            "bar": [
                "steel bar",
                "reinforcement",
                "construction"
            ],

            "construction": [
                "construction",
                "building",
                "steel",
                "cement"
            ],

            "cement": [
                "cement",
                "Portland",
                "OPC",
                "concrete"
            ],

            "concrete": [
                "concrete",
                "cement",
                "structural",
                "IS 456"
            ],

            # Textiles
            "textile": [
                "textile",
                "fabric",
                "cloth"
            ],

            "textiles": [
                "textile",
                "fabric",
                "cloth"
            ],

            "fabric": [
                "fabric",
                "textile",
                "cloth"
            ],

            "cotton": [
                "cotton",
                "fabric",
                "textile"
            ],

            "cloth": [
                "cloth",
                "fabric",
                "textile"
            ],

            # Certification
            "certification": [
                "certification",
                "conformity"
            ],

            "certify": [
                "certification",
                "conformity"
            ],

            "isi": [
                "ISI",
                "certification mark"
            ],

            "testing": [
                "testing",
                "test",
                "laboratory"
            ],

            "test": [
                "testing",
                "laboratory"
            ],

            "lab": [
                "laboratory",
                "test"
            ],

        }

        for keyword, terms in keyword_groups.items():

            if re.search(
                r"\b" + re.escape(keyword) + r"\b",
                query_lower
            ):

                expansions.extend(terms)

        if expansions:

            return (
                query
                + " "
                + " ".join(
                    dict.fromkeys(expansions)
                )
            )

        return query

    # =====================================================
    # CATEGORY DETECTION
    # =====================================================

    def detect_category(self, query):

        """
        Detect an obvious product category from the question.

        This is used only as a search boost/filter hint.
        """

        query_lower = query.lower()

        category_keywords = {

            "01_electronics": [
                "electronics",
                "electrical",
                "led",
                "bulb",
                "lamp",
                "light",
                "appliance"
            ],

            "02_food_and_water": [
                "food",
                "water",
                "drinking",
                "bottle",
                "packaged"
            ],

            "03_jewellery_and_hallmarking": [
                "gold",
                "silver",
                "jewellery",
                "jewelry",
                "hallmark",
                "purity"
            ],

            "04_footwear": [
                "footwear",
                "shoe",
                "shoes",
                "sandal",
                "sole"
            ],

            "05_construction": [
                "construction",
                "steel",
                "cement",
                "concrete",
                "building",
                "reinforcement"
            ],

            "06_textiles": [
                "textile",
                "textiles",
                "fabric",
                "cloth",
                "cotton"
            ],
        }

        for category, keywords in category_keywords.items():

            for keyword in keywords:

                if re.search(
                    r"\b" + re.escape(keyword) + r"\b",
                    query_lower
                ):

                    return category

        return None

    # =====================================================
    # SEARCH
    # =====================================================

    def search(
        self,
        query,
        top_k=5,
        min_score=0.10,
        category=None
    ):

        """
        Search the BIS knowledge base using TF-IDF.

        Returns JSON-safe dictionaries.
        """

        query = self._clean_query(query)

        if not query:
            return []

        # Expand everyday product terminology
        expanded_query = self._expand_query(query)

        # -------------------------------------------------
        # Category hint
        # -------------------------------------------------

        detected_category = self.detect_category(
            query
        )

        # Explicit category takes priority
        if category:
            detected_category = category

        # -------------------------------------------------
        # Create query vector
        # -------------------------------------------------

        q_vec = self.vectorizer.transform(
            [expanded_query]
        )

        scores = cosine_similarity(
            q_vec,
            self.matrix
        ).flatten()

        ranked_indices = scores.argsort()[::-1]

        results = []

        for idx in ranked_indices:

            if len(results) >= top_k:
                break

            score = float(
                scores[idx]
            )

            if score < min_score:
                continue

            row = self.df.iloc[idx]

            row_category = str(
                row.get(
                    "category_file",
                    ""
                )
            ).lower()

            # -------------------------------------------------
            # Explicit category filter
            # -------------------------------------------------

            if category:

                if category.lower() not in row_category:
                    continue

            result = self._safe_row(
                row.to_dict()
            )

            result["_score"] = round(
                score,
                4
            )

            # -------------------------------------------------
            # Category match boost
            #
            # Only used when category was automatically
            # detected. It helps avoid unrelated standards
            # having a similar TF-IDF score.
            # -------------------------------------------------

            if (
                detected_category
                and not category
                and detected_category.lower()
                in row_category
            ):

                result["_score"] = round(
                    min(
                        score + 0.08,
                        1.0
                    ),
                    4
                )

            results.append(
                result
            )

        # Re-sort after category boost
        results.sort(
            key=lambda x: x.get(
                "_score",
                0
            ),
            reverse=True
        )

        return results[:top_k]

    # =====================================================
    # FORMAT STANDARD
    # =====================================================

    def _format_standard(
        self,
        hit,
        include_scope=True
    ):

        is_number = str(
            hit.get(
                "is_number",
                ""
            )
        ).strip()

        title = str(
            hit.get(
                "title",
                ""
            )
        ).strip()

        scope = str(
            hit.get(
                "scope_description",
                ""
            )
        ).strip()

        certification = str(
            hit.get(
                "certification_type",
                ""
            )
        ).strip()

        text = ""

        if is_number:

            text += (
                f"**{is_number}**"
            )

        if title:

            if text:
                text += " — "

            text += title

        if include_scope and scope:

            text += (
                f"\n{scope}"
            )

        if certification:

            text += (
                f"\nCertification: "
                f"{certification}"
            )

        return text

    # =====================================================
    # MATCH EXPLANATION
    # =====================================================

    def _match_reason(
        self,
        query,
        hit
    ):

        """
        Generate a simple transparent explanation of why
        the result matched.

        This is intentionally based on the actual CSV data,
        not generated claims.
        """

        query_lower = query.lower()

        title = str(
            hit.get(
                "title",
                ""
            )
        ).strip()

        scope = str(
            hit.get(
                "scope_description",
                ""
            )
        ).strip()

        searchable = (
            title
            + " "
            + scope
        ).lower()

        important_terms = [

            "led",
            "bulb",
            "lamp",
            "gold",
            "silver",
            "hallmark",
            "purity",
            "water",
            "food",
            "footwear",
            "shoe",
            "sole",
            "steel",
            "cement",
            "construction",
            "textile",
            "fabric",
            "cotton",
            "testing",
            "certification",
        ]

        matches = []

        for term in important_terms:

            if term in query_lower and term in searchable:

                matches.append(term)

        if matches:

            unique_matches = list(
                dict.fromkeys(matches)
            )

            return (
                "Matched because the standard's "
                "title/scope relates to: "
                + ", ".join(
                    unique_matches[:4]
                )
                + "."
            )

        if scope:

            return (
                "Matched based on similarity between "
                "your question and the standard's "
                "title and scope."
            )

        return (
            "Matched based on similarity with the "
            "current BIS knowledge base."
        )

    # =====================================================
    # GEMINI HELPER (DRY)
    # =====================================================

    def _gemini_call(self, prompt, fallback=None):
        """Call Gemini and return text, or fallback on error."""
        if not GEMINI_AVAILABLE or not GEMINI_CLIENT:
            return fallback

        try:
            if hasattr(GEMINI_CLIENT, 'models'):
                response = GEMINI_CLIENT.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
                return response.text.strip()
            else:
                response = GEMINI_CLIENT.generate_content(prompt)
                return response.text.strip()

        except Exception as e:
            print(f"[BIS Sahayak] Gemini call error: {e}")
            return fallback

    # =====================================================
    # QUERY REWRITING (conversation context → standalone)
    # =====================================================

    def rewrite_query(self, user_message, conversation_context=""):
        """
        Rewrite a conversational follow-up into a standalone
        search query using conversation context.

        Example:
            Context: User asked about BIS certification for helmets
            Follow-up: "What about testing?"
            Rewritten: "What testing requirements apply to BIS certification for helmets?"
        """
        if not conversation_context:
            return user_message

        prompt = f"""You are a query rewriter for a BIS (Bureau of Indian Standards) assistant.

Given the conversation context and the user's latest message, rewrite the message
into a standalone search query that can be understood WITHOUT the conversation context.

CONVERSATION CONTEXT:
{conversation_context}

USER'S LATEST MESSAGE: {user_message}

RULES:
1. If the message is already a standalone question, return it unchanged.
2. Resolve pronouns (it, this, that, these) using context.
3. Resolve references ("What about testing?" → "What testing is required for [product from context]?")
4. Keep BIS technical terms (IS numbers, ISI, CRS, HUID) unchanged.
5. Return ONLY the rewritten query, nothing else.
6. Keep the query in the same language as the user's message.
7. Be concise — just the query, no explanation.

REWRITTEN QUERY:"""

        result = self._gemini_call(prompt, fallback=None)
        if result and len(result) < 500:
            return result

        # Heuristic offline fallback: extract subject / IS number from conversation context
        indic_pronouns = r'(इसकी|इसका|इनका|इसमें|તેમાં|તેનું|આનું|આમાં|તેના|આના)'
        en_pronouns = r'\b(it|this|that|these|its|the standard|the product)\b'
        has_pronoun = bool(re.search(en_pronouns, user_message, re.IGNORECASE) or re.search(indic_pronouns, user_message))
        if has_pronoun and conversation_context:
            is_in_ctx = re.findall(r'\bis\s*[:\-]?\s*(\d{3,5})\b', conversation_context, re.IGNORECASE)
            prods_in_ctx = []
            for p in ["helmet", "toy", "toys", "pressure cooker", "cooker", "gold", "silver", "cable", "wire", "cement", "steel", "shoe", "footwear", "water", "led", "lamp", "appliance", "bis", "हेलमेट", "खिलौने", "खिलौना", "कुकर", "રમકડાં", "રમકડું", "કુકર"]:
                if p.lower() in conversation_context.lower():
                    prods_in_ctx.append(p)

            ctx_hint = ""
            if is_in_ctx:
                ctx_hint = f"IS {is_in_ctx[0]}"
            elif prods_in_ctx:
                ctx_hint = prods_in_ctx[0]

            if ctx_hint:
                return f"{user_message} {ctx_hint}"

        return user_message

    # =====================================================
    # TRANSLATE QUERY TO ENGLISH (for TF-IDF retrieval)
    # =====================================================

    def translate_to_english(self, query, source_lang=""):
        """
        Translate a Hindi/Gujarati query to English for
        TF-IDF retrieval. Keeps IS numbers and BIS terms unchanged.
        """
        # Check if query is already English
        import unicodedata
        non_ascii = sum(
            1 for c in query
            if unicodedata.category(c).startswith('L')
            and ord(c) > 127
        )
        if non_ascii == 0:
            return query  # Already English

        prompt = f"""Translate the following query to English for searching a BIS standards database.

RULES:
1. Keep IS numbers (e.g., IS 16102, IS 1417) unchanged.
2. Keep BIS terms (BIS, ISI, CRS, HUID, hallmark) unchanged.
3. Translate the meaning accurately, not literally.
4. Return ONLY the English translation, nothing else.

QUERY: {query}

ENGLISH TRANSLATION:"""

        result = self._gemini_call(prompt, fallback=None)
        if result and len(result) < 500:
            return result

        # Offline dictionary fallback for common Hindi and Gujarati queries
        q_trans = query.lower()
        dict_map = {
            # Multi-word phrases first
            "प्रेशर कुकर": "pressure cooker IS 2347",
            "પ્રેશર કુકર": "pressure cooker IS 2347",
            "एलईडी बल्ब": "LED bulb lamp IS 16102",
            "एलईडी": "LED bulb lamp IS 16102",
            "ગેસ ચૂલો": "gas stove IS 4246",
            "गैस चूल्हा": "gas stove IS 4246",

            # Hindi keywords
            "हेलमेट": "helmet safety IS 4151",
            "खिलौना": "toy safety IS 9873",
            "खिलौने": "toy safety IS 9873",
            "कुकर": "pressure cooker IS 2347",
            "जूते": "footwear shoes IS 15298",
            "जूता": "footwear shoes IS 15298",
            "चप्पल": "footwear sandal",
            "पानी": "packaged drinking water IS 14543",
            "बोतल": "PET bottle IS 15410",
            "सोना": "gold jewellery hallmark IS 1417",
            "चांदी": "silver hallmark IS 2112",
            "आभूषण": "jewellery hallmarking IS 1417",
            "गहने": "jewellery hallmarking IS 1417",
            "सीमेंट": "cement Portland IS 269 IS 8112",
            "स्टील": "steel bars reinforcement IS 1786",
            "सरिया": "steel bars reinforcement IS 1786",
            "कपड़ा": "textiles fabric cotton IS 12369",
            "कपड़े": "textiles fabric cotton IS 12369",
            "बल्ब": "LED bulb lamp IS 16102",
            "तार": "cables electrical wire IS 694",
            "केबल": "cables electrical wire IS 694",
            "चूल्हा": "gas stove IS 4246",
            "गीज़र": "water heater electrical appliance IS 302",
            "लैब": "testing laboratory",
            "प्रयोगशाला": "testing laboratory",
            "परीक्षण": "testing laboratory",
            "टेस्टिंग": "testing laboratory",
            "मानक": "standard",
            "प्रमाणन": "certification ISI mark",
            "लाइसेंस": "license certification",

            # Gujarati keywords
            "હેલ્મેટ": "helmet safety IS 4151",
            "હેલમેટ": "helmet safety IS 4151",
            "રમકડાં": "toy safety IS 9873",
            "રમકડું": "toy safety IS 9873",
            "રમકડા": "toy safety IS 9873",
            "કુકર": "pressure cooker IS 2347",
            "બુટ": "footwear shoes IS 15298",
            "ચંપલ": "footwear sandal",
            "પગરખાં": "footwear shoes IS 15298",
            "પાણી": "packaged drinking water IS 14543",
            "બોટલ": "PET bottle IS 15410",
            "સોનું": "gold jewellery hallmark IS 1417",
            "સોના": "gold jewellery hallmark IS 1417",
            "ચાંદી": "silver hallmark IS 2112",
            "દાગીના": "jewellery hallmarking IS 1417",
            "ઘરેણાં": "jewellery hallmarking IS 1417",
            "સિમેન્ટ": "cement Portland IS 269 IS 8112",
            "સ્ટીલ": "steel bars reinforcement IS 1786",
            "સળિયા": "steel bars reinforcement IS 1786",
            "કાપડ": "textiles fabric cotton IS 12369",
            "બલ્બ": "LED bulb lamp IS 16102",
            "વાયર": "cables electrical wire IS 694",
            "કેબલ": "cables electrical wire IS 694",
            "ચૂલો": "gas stove IS 4246",
            "લેબ": "testing laboratory",
            "ટેસ્ટિંગ": "testing laboratory",
            "ટેસ્ટ": "testing laboratory",
            "ધોરણ": "standard",
            "પ્રમાણન": "certification ISI mark",
            "લાયસન્સ": "license certification"
        }

        matched_terms = []
        for phrase, eng in sorted(dict_map.items(), key=lambda x: len(x[0]), reverse=True):
            if phrase in q_trans:
                matched_terms.append(eng)

        # Preserve any IS numbers present in original query
        is_numbers = re.findall(r'\bis\s*[:\-]?\s*\d+\b', query, re.IGNORECASE)
        matched_terms.extend(is_numbers)

        if matched_terms:
            return " ".join(dict.fromkeys(matched_terms))

        return query

    # =====================================================
    # INTENT DETECTION
    # =====================================================

    INTENT_KEYWORDS = {
        "standard_search": [
            "standard", "is number", "which standard",
            "applicable", "code", "specification", "spec",
            "मानक", "स्टैंडर्ड", "ધોરણ"
        ],
        "certification": [
            "certif", "isi mark", "isi", "license", "licence",
            "apply", "application", "registration",
            "प्रमाणन", "लाइसेंस", "પ્રમાણન"
        ],
        "hallmarking": [
            "hallmark", "huid", "gold", "silver", "purity",
            "jewel", "हॉलमार्क", "सोना", "આભૂષણ"
        ],
        "testing_lab": [
            "lab", "testing", "test report", "where to test",
            "laboratory", "लैब", "परीक्षण", "ટેસ્ટિંગ"
        ],
        "complaint": [
            "complain", "report", "fake", "counterfeit", "fraud",
            "शिकायत", "नकली", "ફરિયાદ"
        ],
        "documents_required": [
            "document", "required", "paperwork", "submit",
            "दस्तावेज़", "દસ્તાવેજ"
        ],
        "fees": [
            "fee", "cost", "price", "charge", "how much",
            "शुल्क", "कीमत", "ફી"
        ],
        "process": [
            "process", "procedure", "step", "how to", "how do",
            "प्रक्रिया", "कैसे", "કેવી રીતે"
        ],
        "product_compliance": [
            "comply", "compliance", "manufacture", "import",
            "sell", "mandatory", "compulsory",
            "अनुपालन", "अનુપાલન"
        ],
    }

    def detect_intent(self, query):
        """
        Detect the user's BIS-related intent from their query.
        Returns the most likely intent string.
        """
        query_lower = query.lower()

        scores = {}
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = sum(
                1 for kw in keywords
                if kw.lower() in query_lower
            )
            if score > 0:
                scores[intent] = score

        if scores:
            return max(scores, key=scores.get)

        return "general_bis"

    # =====================================================
    # GENERATE FOLLOW-UP QUESTIONS
    # =====================================================

    def generate_follow_ups(
        self,
        query,
        answer_text,
        intent,
        language="en"
    ):
        """
        Generate contextual follow-up question suggestions
        based on the current Q&A.
        """
        lang_map = {
            "en": "English",
            "hi": "Hindi",
            "gu": "Gujarati"
        }
        lang_name = lang_map.get(language, "English")

        prompt = f"""You are BIS Sahayak. Based on the user's question and the answer given,
suggest exactly 3 natural follow-up questions the user might want to ask next.

USER QUESTION: {query}
DETECTED INTENT: {intent}
ANSWER SUMMARY: {answer_text[:500]}

RULES:
1. Questions must be about BIS standards, certification, testing, hallmarking, or compliance.
2. Questions should be contextually relevant to the conversation.
3. Each question should be short (under 50 characters).
4. Generate questions in {lang_name}.
5. Return ONLY 3 questions, one per line, no numbering, no bullets.

FOLLOW-UP QUESTIONS:"""

        result = self._gemini_call(prompt, fallback=None)

        if result:
            lines = [
                line.strip()
                for line in result.strip().split("\n")
                if line.strip()
                and not line.strip().startswith(("-", "*", "•"))
            ]
            # Clean numbering like "1." "2."
            cleaned = []
            for line in lines[:3]:
                import re as _re
                cleaned_line = _re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                if cleaned_line:
                    cleaned.append(cleaned_line)
            if cleaned:
                return cleaned

        # Static fallbacks per intent
        fallbacks = {
            "en": {
                "standard_search": [
                    "Is this certification mandatory?",
                    "Where can I get testing done?",
                    "What documents are needed?"
                ],
                "certification": [
                    "What documents are required?",
                    "How long does it take?",
                    "What are the fees?"
                ],
                "hallmarking": [
                    "How to verify a HUID?",
                    "Which districts is it mandatory?",
                    "What purity levels exist?"
                ],
                "testing_lab": [
                    "What standards do they test?",
                    "How to get a test report?",
                    "What does testing cost?"
                ],
                "general_bis": [
                    "What are the main functions of BIS?",
                    "How to apply for an ISI mark?",
                    "How to use the BIS CARE app?"
                ]
            },
            "hi": {
                "standard_search": [
                    "क्या यह प्रमाणन अनिवार्य है?",
                    "टेस्टिंग कहाँ होगी?",
                    "कौन से दस्तावेज़ चाहिए?"
                ],
                "certification": [
                    "कौन से दस्तावेज़ चाहिए?",
                    "कितना समय लगता है?",
                    "शुल्क कितना है?"
                ],
                "hallmarking": [
                    "HUID कैसे सत्यापित करें?",
                    "क्या हॉलमार्किंग अनिवार्य है?",
                    "शुद्धता के स्तर क्या हैं?"
                ],
                "testing_lab": [
                    "मान्यता प्राप्त लैब कहाँ हैं?",
                    "टेस्ट रिपोर्ट कैसे प्राप्त करें?",
                    "परीक्षण शुल्क कितना है?"
                ],
                "general_bis": [
                    "BIS के प्रमुख कार्य क्या हैं?",
                    "ISI मार्क कैसे प्राप्त करें?",
                    "BIS CARE ऐप का उपयोग कैसे करें?"
                ]
            },
            "gu": {
                "standard_search": [
                    "શું આ પ્રમાણન ફરજિયાત છે?",
                    "ટેસ્ટિંગ ક્યાં થશે?",
                    "કયા દસ્તાવેજો જોઈએ?"
                ],
                "certification": [
                    "કયા દસ્તાવેજો જોઈએ?",
                    "કેટલો સમય લાગે છે?",
                    "ફી કેટલી છે?"
                ],
                "hallmarking": [
                    "HUID કેવી રીતે ચકાસવું?",
                    "શું હોલમાર્કિંગ ફરજિયાત છે?",
                    "શુદ્ધતાના ગ્રેડ કયા છે?"
                ],
                "testing_lab": [
                    "માન્યતા પ્રાપ્ત લેબ ક્યાં છે?",
                    "ટેસ્ટ રિપોર્ટ કેવી રીતે મેળવવો?",
                    "ટેસ્ટિંગ ફી કેટલી છે?"
                ],
                "general_bis": [
                    "BIS ના મુખ્ય કાર્યો કયા છે?",
                    "ISI માર્ક કેવી રીતે મેળવવો?",
                    "BIS CARE એપ કેવી રીતે વાપરવી?"
                ]
            },
        }

        lang_fallbacks = fallbacks.get(language, fallbacks["en"])
        return lang_fallbacks.get(
            intent,
            lang_fallbacks.get("general_bis", lang_fallbacks.get("standard_search", [
                "Tell me more",
                "What are the requirements?",
                "How to apply?"
            ]))
        )

    # =====================================================
    # GEMINI SMART RESPONSE
    # =====================================================

    def _generate_smart_response(
        self,
        query,
        hits,
        language="en",
        page_context="",
        conversation_context=""
    ):

        """
        Use Gemini to generate a smart, natural response
        based on retrieved BIS standards context.

        Falls back to None if Gemini is unavailable.
        """

        if not GEMINI_AVAILABLE:
            return None

        # Build context from retrieved standards
        context_parts = []

        for i, hit in enumerate(hits[:5], 1):

            is_num = str(hit.get("is_number", ""))
            title = str(hit.get("title", ""))
            scope = str(hit.get("scope_description", ""))
            cert = str(hit.get("certification_type", ""))
            scheme = str(hit.get("scheme", ""))
            score = hit.get("_score", 0)

            context_parts.append(
                f"Standard {i}: {is_num} — {title}\n"
                f"  Scope: {scope}\n"
                f"  Certification: {cert}\n"
                f"  Scheme: {scheme}\n"
                f"  Match score: {score}"
            )

        standards_context = "\n\n".join(context_parts)

        # Language instruction
        lang_map = {
            "en": "English",
            "hi": "Hindi (हिंदी)",
            "gu": "Gujarati (ગુજરાતી)"
        }

        response_language = lang_map.get(
            language,
            "English"
        )

        # Page context section
        page_section = ""
        if page_context:
            trimmed = page_context[:2000]
            page_section = (
                f"\n\nPAGE CONTEXT (user is viewing this webpage):\n"
                f"---\n{trimmed}\n---\n"
                f"Reference this if relevant to the question."
            )

        # Conversation context section
        conv_section = ""
        if conversation_context:
            conv_section = (
                f"\n\nCONVERSATION HISTORY:\n"
                f"{conversation_context}\n"
                f"---\n"
                f"Use this to understand follow-up references."
            )

        # Build the enhanced prompt
        prompt = f"""You are BIS Sahayak, an AI assistant specialized in Bureau of Indian Standards (BIS) information.

Your responsibility is to help users understand BIS standards, certification, hallmarking, testing, compliance, laboratories, and related procedures.

You must ground factual answers in the retrieved BIS knowledge base below.

CRITICAL RULES:
- NEVER invent IS numbers, BIS standards, certification requirements, fees, laboratories, regulations, or procedures.
- If information is NOT present in the retrieved context, clearly state: "I couldn't find verified BIS information for this in my current knowledge base."
- Maintain conversational context. Resolve references like "it", "this", "that", "the above" using the conversation history.
- Preserve technical identifiers exactly: BIS, IS numbers, ISI, CRS, HUID, official product names.
- Use simple language suitable for ordinary citizens, manufacturers, students, importers, and businesses.
- When useful, provide step-by-step guidance.
- Distinguish between verified BIS information and general explanation.
- Do NOT claim to be an official BIS employee. You are an AI assistant.

RETRIEVED BIS STANDARDS (from knowledge base):
{standards_context}
{page_section}
{conv_section}

REQUESTED LANGUAGE: {response_language}
CURRENT USER QUESTION: {query}

RESPONSE INSTRUCTIONS:
1. Answer using ONLY the retrieved standards above.
2. Be specific — mention exact IS numbers, certification types, and schemes.
3. Structure with ** bold headings ** where appropriate.
4. Keep concise but complete (3-6 short paragraphs).
5. End with a practical next step the user can take.
6. If retrieved standards don't match well, say so honestly and provide the closest relevant info.
7. Respond ENTIRELY in {response_language}.
8. If page context is provided and relevant, reference it naturally."""

        return self._gemini_call(prompt, fallback=None)

    # =====================================================
    # ANSWER
    # =====================================================

    def answer(
        self,
        query,
        language="en",
        page_context="",
        conversation_context=""
    ):

        query = self._clean_query(
            query
        )

        # -------------------------------------------------
        # Empty question
        # -------------------------------------------------

        if not query:

            return {

                "answer": (
                    "Please enter a question about "
                    "a product, BIS standard, certification, "
                    "testing, or compliance requirement."
                ),

                "citations": [],

                "verified": None,

                "results": [],

                "query": "",

                "category": None
            }

        # -------------------------------------------------
        # Detect category
        # -------------------------------------------------

        detected_category = self.detect_category(
            query
        )

        lang_map = {"en": "English", "hi": "Hindi (हिंदी)", "gu": "Gujarati (ગુજરાતી)"}
        resp_lang = lang_map.get(language, "English")

        # -------------------------------------------------
        # 1. Non-existent IS standard number hallucination guard
        # -------------------------------------------------
        is_num_match = re.search(r'\bis\s*[:\-]?\s*(\d{3,8})\b', query, re.IGNORECASE)
        if is_num_match:
            queried_is = is_num_match.group(1)
            # Check if this IS number exists in our dataframe
            exists_in_kb = any(
                queried_is in str(val) for val in self.df.get("is_number", [])
            )
            if not exists_in_kb:
                if GEMINI_AVAILABLE:
                    guard_prompt = f"""You are BIS Sahayak, an AI assistant for the Bureau of Indian Standards (BIS).
The user asked about standard: "IS {queried_is}".
CRITICAL: This standard number was NOT found in the official BIS standards catalogue.
Check if IS {queried_is} is a real BIS standard or completely fictitious/unrecognized.
If it is fictitious or unrecognized, clearly state that IS {queried_is} was not found in the official BIS index and caution the user against unverified standards. NEVER invent or hallucinate specifications.
Respond in {resp_lang}."""
                    smart_guard = self._gemini_call(guard_prompt, fallback=None)
                    if smart_guard:
                        return {
                            "answer": smart_guard,
                            "citations": [],
                            "verified": False,
                            "results": [],
                            "query": query,
                            "category": detected_category
                        }

                not_found_answers = {
                    "en": (
                        f"### ⚠️ Unverified / Non-Existent Standard: IS {queried_is}\n\n"
                        f"The standard number **IS {queried_is}** was **not found** in the BIS Sahayak database or official BIS published index.\n\n"
                        f"**Important Consumer Guidance**:\n"
                        f"- Standard numbers under the Bureau of Indian Standards typically range from 1 to ~20000.\n"
                        f"- Fictitious standard numbers are sometimes cited on counterfeit or non-compliant goods to deceive consumers.\n"
                        f"- Always verify genuine standards on the official BIS portal: [bis.gov.in/know-your-standard](https://www.bis.gov.in/know-your-standard/) or using the **BIS CARE** mobile app.\n\n"
                        f"If you are looking for a specific product standard, try searching by product name (e.g., 'helmets', 'toys', 'LED lamps', 'packaged water')."
                    ),
                    "hi": (
                        f"### ⚠️ असत्यापित / अमान्य मानक: IS {queried_is}\n\n"
                        f"मानक संख्या **IS {queried_is}** BIS सहायक डेटाबेस या आधिकारिक BIS प्रकाशित सूची में **नहीं मिली**।\n\n"
                        f"**महत्वपूर्ण उपभोक्ता दिशानिर्देश**:\n"
                        f"- भारतीय मानक ब्यूरो (BIS) की वास्तविक मानक संख्याएं आमतौर पर 1 से लगभग 20000 के दायरे में होती हैं।\n"
                        f"- कुछ नकली या अनधिकृत उत्पाद उपभोक्ताओं को भ्रमित करने के लिए मनगढ़ंत मानक संख्याएं दर्शाते हैं।\n"
                        f"- आधिकारिक BIS पोर्टल [bis.gov.in](https://www.bis.gov.in/know-your-standard/) या **BIS CARE** ऐप पर मानक की प्रामाणिकता अवश्य जांचें।\n\n"
                        f"यदि आप किसी उत्पाद का मानक ढूंढ रहे हैं, तो उत्पाद का नाम लिखकर खोजें (जैसे 'हेलमेट', 'खिलौने', 'एलईडी बल्ब', 'पीने का पानी')।"
                    ),
                    "gu": (
                        f"### ⚠️ અચકાસાયેલ / અસ્તિત્વમાં ન હોય તેવું ધોરણ: IS {queried_is}\n\n"
                        f"માનક નંબર **IS {queried_is}** BIS સહાયક ડેટાબેઝ અથવા સત્તાવાર BIS સૂચિમાં **મળ્યો નથી**।\n\n"
                        f"**મહત્વપૂર્ણ ગ્રાહક માર્ગદર્શન**:\n"
                        f"- બ્યુરો ઓફ ઇન્ડિયન સ્ટાન્ડર્ડ્સ (BIS) ના વાસ્તવિક ધોરણ નંબરો સામાન્ય રીતે 1 થી આશરે 20000 ની વચ્ચે હોય છે.\n"
                        f"- નકલી અથવા બિન-પ્રમાણિત ઉત્પાદનો ગ્રાહકોને છેતરવા માટે કેટલીકવાર કાલ્પનિક માનક નંબર દર્શાવે છે.\n"
                        f"- સત્તાવાર BIS પોર્ટલ [bis.gov.in](https://www.bis.gov.in/know-your-standard/) અથવા **BIS CARE** એપ પર માનકની સત્યતા ચકાસો.\n\n"
                        f"જો તમે કોઈ ઉત્પાદનનું ધોરણ શોધી રહ્યા છો, તો ઉત્પાદનનું નામ લખીને શોધો (જેમ કે 'હેલ્મેટ', 'રમકડાં', 'એલઇડી બલ્બ', 'પીવાનું પાણી')."
                    )
                }
                return {
                    "answer": not_found_answers.get(language, not_found_answers["en"]),
                    "citations": [],
                    "verified": False,
                    "results": [],
                    "query": query,
                    "category": detected_category
                }

        # -------------------------------------------------
        # 2. Unrelated Query Redirection (sports, movies, weather, etc.)
        # -------------------------------------------------
        unrelated_patterns = [
            r'\b(cricket|match|ipl|football|messi|ronaldo|score|scores|world\s*cup|badminton|tennis|wicket|batting)\b',
            r'\b(movie|movies|cinema|actor|actress|bollywood|hollywood|song|songs|lyrics|trailer|box\s*office)\b',
            r'\b(weather|forecast|rain|temperature|climate|sunny|humidity)\b',
            r'\b(election|elections|politics|politician|minister|prime\s*minister|president|bjp|congress)\b',
            r'\b(joke|jokes|riddle|story|poem|recipe|biryani|cook\s*recipe)\b'
        ]
        is_unrelated = any(re.search(pat, query, re.IGNORECASE) for pat in unrelated_patterns)
        bis_terms_present = bool(re.search(r'\b(bis|is\s*\d+|standard|certification|hallmark|isi|crs|huid|testing|lab)\b', query, re.IGNORECASE))

        if is_unrelated and not bis_terms_present:
            redirect_answers = {
                "en": (
                    "I am **BIS Sahayak**, an AI assistant dedicated exclusively to the **Bureau of Indian Standards (BIS)**, Indian Standards (IS), product quality certification, hallmarking, and consumer safety.\n\n"
                    "I cannot assist with questions regarding sports, entertainment, weather, or general trivia.\n\n"
                    "**Please feel free to ask about**:\n"
                    "- Applicable IS standards for products (e.g., helmets, toys, electronics, drinking water, cement)\n"
                    "- ISI Mark (Scheme I) and CRS registration requirements\n"
                    "- Gold and silver Hallmarking (HUID verification)\n"
                    "- BIS recognized testing laboratories and compliance procedures"
                ),
                "hi": (
                    "मैं **BIS सहायक** हूँ, जो विशेष रूप से **भारतीय मानक ब्यूरो (BIS)**, भारतीय मानकों (IS), उत्पाद गुणवत्ता प्रमाणन, हॉलमार्किंग और उपभोक्ता सुरक्षा के लिए समर्पित एक AI सहायक है।\n\n"
                    "मैं खेल, मनोरंजन, मौसम या सामान्य ज्ञान से संबंधित प्रश्नों में सहायता करने में असमर्थ हूँ।\n\n"
                    "**कृपया BIS से संबंधित प्रश्न पूछें, जैसे**:\n"
                    "- उत्पादों के लिए लागू IS मानक (जैसे हेलमेट, खिलौने, इलेक्ट्रॉनिक्स, पीने का पानी, सीमेंट)\n"
                    "- ISI मार्क और CRS अनिवार्य पंजीकरण आवश्यकताएं\n"
                    "- सोना और चांदी हॉलमार्किंग (HUID सत्यापन)\n"
                    "- BIS मान्यता प्राप्त प्रयोगशालाएं और प्रमाणन प्रक्रियाएं"
                ),
                "gu": (
                    "હું **BIS સહાયક** છું, જે ખાસ કરીને **બ્યુરો ઓફ ઇન્ડિયન સ્ટાન્ડર્ડ્સ (BIS)**, ભારતીય ધોરણો (IS), ઉત્પાદન ગુણવત્તા પ્રમાણપત્ર, હોલમાર્કિંગ અને ગ્રાહક સુરક્ષા માટે સમર્પિત AI સહાયક છે.\n\n"
                    "હું રમતગમત, મનોરંજન, હવામાન અથવા સામાન્ય જ્ઞાન સંબંધિત પ્રશ્નોમાં સહાય કરી શકતો નથી.\n\n"
                    "**કૃપા કરીને BIS સંબંધિત પ્રશ્નો પૂછો, જેમ કે**:\n"
                    "- ઉત્પાદનો માટે લાગુ પડતા IS ધોરણો (જેમ કે હેલ્મેટ, રમકડાં, ઇલેક્ટ્રોનિક્સ, પીવાનું પાણી, સિમેન્ટ)\n"
                    "- ISI માર્ક અને CRS ફરજિયાત રજીસ્ટ્રેશન જરૂરિયાતો\n"
                    "- સોના અને ચાંદીનું હોલમાર્કિંગ (HUID ચકાસણી)\n"
                    "- BIS માન્યતા પ્રાપ્ત ટેસ્ટિંગ લેબોરેટરી અને પ્રમાણન પ્રક્રિયા"
                )
            }
            return {
                "answer": redirect_answers.get(language, redirect_answers["en"]),
                "citations": [],
                "verified": None,
                "results": [],
                "query": query,
                "category": None
            }

        # -------------------------------------------------
        # 3. General BIS inquiries (What is BIS? Why is it important? etc.)
        # -------------------------------------------------
        q_lower = query.lower().strip()
        general_bis_patterns = [
            r'\bwhat\s+is\s+bis\b',
            r'\bwho\s+is\s+bis\b',
            r'\bwhy\s+is\s+bis\b',
            r'\bexplain\s+bis\b',
            r'\babout\s+bis\b',
            r'\btell\s+me\s+about\s+bis\b',
            r'\bwhat\s+does\s+bis\s+do\b',
            r'\brole\s+of\s+bis\b',
            r'\bpurpose\s+of\s+bis\b',
            r'\bwhy\s+is\s+it\s+important\b',
            r'\bhow\s+does\s+bis\s+work\b',
            r'\bbis\s+kya\s+hai\b',
            r'\bbis\s+kyun\s+zaroori\b',
            r'\bbis\s+shu\s+chhe\b',
            r'\bbis\s+kem\s+jaruri\b'
        ]
        has_general_pattern = any(re.search(pat, q_lower) for pat in general_bis_patterns)
        is_exact_general = q_lower in [
            "what is bis?", "what is bis", "who is bis", "why is it important?",
            "why is it important", "explain bis", "about bis", "tell me about bis",
            "what does bis do?", "what does bis do"
        ]
        has_specific_product = any(prod in q_lower for prod in [
            "helmet", "toy", "water", "cooker", "gold", "silver", "cable", "cement",
            "steel", "shoe", "lamp", "led", "cloth", "textile", "gas", "wire"
        ])

        if (has_general_pattern or is_exact_general) and not has_specific_product:
            if GEMINI_AVAILABLE:
                gen_prompt = f"""You are BIS Sahayak, an AI assistant for the Bureau of Indian Standards (BIS).
Explain the following query clearly, comprehensively, and accurately:
"{query}"
Cover:
1. What BIS is (National Standards Body of India established under BIS Act 2016).
2. Key certification schemes: ISI Mark (Scheme I), CRS (Scheme II for electronics/IT), Hallmarking (Scheme IV for gold/silver with HUID), and Laboratory Recognition.
3. Why BIS certification is crucial for consumer safety, product reliability, and fair trade.
4. How citizens and businesses can verify standards on Manakonline (manakonline.in) and the BIS CARE app.
Respond strictly in {resp_lang}."""
                smart_gen = self._gemini_call(gen_prompt, fallback=None)
                if smart_gen:
                    return {
                        "answer": smart_gen,
                        "citations": [],
                        "verified": True,
                        "results": [],
                        "query": query,
                        "category": None
                    }

            general_answers = {
                "en": (
                    "### 🏛️ Bureau of Indian Standards (BIS) — Overview\n\n"
                    "The **Bureau of Indian Standards (BIS)** is the National Standards Body of India, established under the **Bureau of Indian Standards Act, 2016**. It operates under the Ministry of Consumer Affairs, Food & Public Distribution.\n\n"
                    "#### 🎯 Key Objectives & Mandate:\n"
                    "1. **Formulation of Indian Standards (IS)**: Developing quality and safety specifications across electronics, mechanical, chemical, food, textiles, and civil engineering.\n"
                    "2. **Product Certification (ISI Mark — Scheme I)**: Licensing manufacturers that comply with Indian Standards. Mandatory for over 500+ critical consumer and industrial products under Quality Control Orders (QCOs).\n"
                    "3. **Compulsory Registration Scheme (CRS — Scheme II)**: Self-declaration of conformity for electronics, IT equipment, solar products, and LED lighting.\n"
                    "4. **Hallmarking Scheme (Scheme IV)**: Mandatory purity certification for gold and silver jewellery using a unique 6-digit alphanumeric **HUID** (Hallmark Unique Identification).\n"
                    "5. **Laboratory Network**: Operating central, regional, and recognized private testing laboratories to ensure independent product quality evaluation.\n\n"
                    "#### 🔍 Verification & Portals:\n"
                    "- **Manakonline Portal**: [manakonline.in](https://www.manakonline.in/) for online license application, renewal, and standard search.\n"
                    "- **BIS CARE Mobile App**: Allows consumers to verify ISI marks, CRS registration numbers, and 6-digit gold HUIDs instantly."
                ),
                "hi": (
                    "### 🏛️ भारतीय मानक ब्यूरो (BIS) — परिचय\n\n"
                    "**भारतीय मानक ब्यूरो (BIS)** भारत का राष्ट्रीय मानक निकाय है, जिसे **भारतीय मानक ब्यूरो अधिनियम, 2016** के तहत स्थापित किया गया है। यह उपभोक्ता मामले, खाद्य एवं सार्वजनिक वितरण मंत्रालय के अंतर्गत कार्य करता है।\n\n"
                    "#### 🎯 मुख्य उद्देश्य और कार्य:\n"
                    "1. **भारतीय मानकों (IS) का निर्माण**: इलेक्ट्रॉनिक्स, मैकेनिकल, रसायन, खाद्य, कपड़ा और निर्माण उत्पादों के लिए गुणवत्ता और सुरक्षा विनिर्देश तैयार करना।\n"
                    "2. **उत्पाद प्रमाणन (ISI मार्क — स्कीम I)**: मानकों का पालन करने वाले निर्माताओं को ISI लाइसेंस देना। 500 से अधिक महत्वपूर्ण उत्पादों के लिए गुणवत्ता नियंत्रण आदेशों (QCO) के तहत अनिवार्य।\n"
                    "3. **अनिवार्य पंजीकरण योजना (CRS — स्कीम II)**: इलेक्ट्रॉनिक्स, आईटी गैजेट्स, सोलर उत्पादों और एलईडी लाइटिंग के लिए अनिवार्य पंजीकरण।\n"
                    "4. **हॉलमार्किंग योजना (स्कीम IV)**: 6-अंकों वाले **HUID** (हॉलमार्क यूनिक आइडेंटिफिकेशन) के साथ सोने और चांदी के आभूषणों की शुद्धता का अनिवार्य प्रमाणन।\n"
                    "5. **प्रयोगशाला नेटवर्क**: निष्पक्ष परीक्षण सुनिश्चित करने के लिए केंद्रीय, क्षेत्रीय और मान्यता प्राप्त निजी प्रयोगशालाओं का संचालन।\n\n"
                    "#### 🔍 सत्यापन और आधिकारिक पोर्टल:\n"
                    "- **मानकऑनलाइन पोर्टल**: [manakonline.in](https://www.manakonline.in/) पर लाइसेंस आवेदन और मानकों की खोज।\n"
                    "- **BIS CARE मोबाइल ऐप**: उपभोक्ता इसके माध्यम से ISI मार्क, CRS नंबर और 6-अंकीय सोने के HUID का तुरंत सत्यापन कर सकते हैं।"
                ),
                "gu": (
                    "### 🏛️ બ્યુરો ઓફ ઇન્ડિયન સ્ટાન્ડર્ડ્સ (BIS) — પરિચય\n\n"
                    "**બ્યુરો ઓફ ઇન્ડિયન સ્ટાન્ડર્ડ્સ (BIS)** એ ભારતની રાષ્ટ્રીય માનક સંસ્થા છે, જેની સ્થાપના **બ્યુરો ઓફ ઇન્ડિયન સ્ટાન્ડર્ડ્સ એક્ટ, 2016** હેઠળ કરવામાં આવી છે. તે ગ્રાહક બાબતોના મંત્રાલય હેઠળ કાર્ય કરે છે.\n\n"
                    "#### 🎯 મુખ્ય ઉદ્દેશ્યો અને કાર્યો:\n"
                    "1. **ભારતીય ધોરણો (IS) ઘડવા**: ઇલેક્ટ્રોનિક્સ, કેમિકલ્સ, ખોરાક, ટેક્સટાઇલ અને બાંધકામ ક્ષેત્રે ગુણવત્તા અને સલામતીના નિયમો ઘડવા.\n"
                    "2. **ઉત્પાદન પ્રમાણપત્ર (ISI માર્ક — સ્કીમ I)**: નિયમોનું પાલન કરતા ઉત્પાદકોને લાયસન્સ આપવું. ક્વોલિટી કંટ્રોલ ઓર્ડર્સ (QCO) હેઠળ 500 થી વધુ ઉત્પાદનો માટે ફરજિયાત.\n"
                    "3. **ફરજિયાત નોંધણી યોજના (CRS — સ્કીમ II)**: ઇલેક્ટ્રોનિક્સ, આઇટી ઉપકરણો અને એલઇડી લાઇટિંગ માટે નોંધણી.\n"
                    "4. **હોલમાર્કિંગ યોજના (સ્કીમ IV)**: 6-અંકના અનોખા **HUID** કોડ સાથે સોના અને ચાંદીના દાગીનાની શુદ્ધતાનું ફરજિયાત પ્રમાણીકરણ.\n"
                    "5. **ટેસ્ટિંગ લેબોરેટરી નેટવર્ક**: ઉત્પાદનોની ગુણવત્તા ચકાસવા માટે કેન્દ્રીય, પ્રાદેશિક અને માન્યતા પ્રાપ્ત ખાનગી લેબનું સંચાલન.\n\n"
                    "#### 🔍 ચકાસણી અને પોર્ટલ:\n"
                    "- **માનકઓનલાઇન પોર્ટલ**: [manakonline.in](https://www.manakonline.in/) લાયસન્સ અને ધોરણો શોધવા માટે.\n"
                    "- **BIS CARE મોબાઇલ એપ**: ગ્રાહકો આ એપ દ્વારા ISI માર્ક, CRS નંબર અને 6-અંકનો ગોલ્ડ HUID તાત્કાલિક ચકાસી શકે છે."
                )
            }
            return {
                "answer": general_answers.get(language, general_answers["en"]),
                "citations": [],
                "verified": True,
                "results": [],
                "query": query,
                "category": None
            }

        # -------------------------------------------------
        # Retrieve standards
        # -------------------------------------------------

        hits = self.search(

            query,

            top_k=5,

            min_score=0.10
        )

        # -------------------------------------------------
        # Handle weak / non-standard matches via Gemini or Trilingual Fallback
        # -------------------------------------------------

        if not hits or hits[0].get("_score", 0) < 0.10:

            lang_map = {"en": "English", "hi": "Hindi (हिंदी)", "gu": "Gujarati (ગુજરાતી)"}
            resp_lang = lang_map.get(language, "English")

            conv_history_prompt = f"\nCONVERSATION CONTEXT:\n{conversation_context}" if conversation_context else ""

            weak_prompt = f"""You are BIS Sahayak, an AI assistant for the Bureau of Indian Standards (BIS).

The user asked: "{query}"
{conv_history_prompt}

TASK & GUIDELINES:
1. If the user is asking a GENERAL question about BIS (e.g. "What is BIS?", "Why is BIS important?", "What services does BIS provide?", "What is ISI mark vs CRS?"):
   - Provide an accurate, helpful, and concise explanation of BIS and its mandate in {resp_lang}.
2. If the user asks about a SPECIFIC IS standard number that does not exist or isn't recognized (e.g., "What is IS 99999999?"):
   - Clearly state that this standard number was not found in the official BIS index and caution the user against unverified or fictitious standards. DO NOT invent details.
3. If the user's question is COMPLETELY UNRELATED to BIS, standards, manufacturing, consumer products, quality, certification, or hallmarking (e.g., sports scores, weather, general trivia, movies):
   - Politely decline and redirect: state that you are BIS Sahayak, focused on Indian Standards, quality certifications, and consumer safety, and invite them to ask a BIS-related question.
4. If the user is asking about a real product but no specific standard was retrieved:
   - Explain politely that a direct standard was not located in the current database, and guide them on how to search or apply on Manakonline.
5. Answer strictly in {resp_lang}.
6. Keep formatting clean with bullet points or bold text if helpful.

ANSWER:"""

            smart_fallback = self._gemini_call(weak_prompt, fallback=None)

            if smart_fallback:
                return {
                    "answer": smart_fallback,
                    "citations": [],
                    "verified": None,
                    "results": [],
                    "query": query,
                    "category": detected_category
                }

            fallback_messages = {
                "en": (
                    "I couldn't find a sufficiently relevant BIS standard in the current knowledge base.\n\n"
                    "Try mentioning the product name, IS number, certification, testing requirement, or category."
                ),
                "hi": (
                    "वर्तमान ज्ञान आधार में कोई पर्याप्त रूप से प्रासंगिक BIS मानक नहीं मिला।\n\n"
                    "कृपया उत्पाद का नाम, IS नंबर, प्रमाणन, परीक्षण आवश्यकता या श्रेणी लिखकर पुनः प्रयास करें।"
                ),
                "gu": (
                    "વર્તમાન જ્ઞાન આધારમાં પૂરતો સુસંગત BIS ધોરણ મળ્યો નથી.\n\n"
                    "કૃપા કરીને ઉત્પાદનનું નામ, IS નંબર, પ્રમાણન, ટેસ્ટિંગ જરૂરિયાત અથવા કેટેગરી લખીને ફરી પ્રયાસ કરો."
                )
            }

            return {
                "answer": fallback_messages.get(language, fallback_messages["en"]),
                "citations": [],
                "verified": None,
                "results": [],
                "query": query,
                "category": detected_category
            }

        # -------------------------------------------------
        # Best result
        # -------------------------------------------------

        best = hits[0]

        best_score = float(
            best.get(
                "_score",
                0
            )
        )

        # -------------------------------------------------
        # Build assistant response
        # -------------------------------------------------

        # Try Gemini smart response first
        smart_answer = self._generate_smart_response(
            query,
            hits,
            language=language,
            page_context=page_context,
            conversation_context=conversation_context
        )

        if smart_answer:

            answer_text = smart_answer

        else:

            # Fallback: TF-IDF template response in user's language
            answer_parts = []

            head_best = {
                "en": "### Best matching BIS standard",
                "hi": "### सबसे उपयुक्त BIS मानक",
                "gu": "### શ્રેષ્ઠ મેળ ખાતું BIS ધોરણ"
            }
            head_other = {
                "en": "### Other relevant standards",
                "hi": "### अन्य प्रासंगिक मानक",
                "gu": "### અન્ય સંબંધિત ધોરણો"
            }
            rel_label = {
                "en": "Relevance to your question",
                "hi": "आपके प्रश्न से प्रासंगिकता",
                "gu": "તમારા પ્રશ્ન સાથે સુસંગતતા"
            }
            note_head = {
                "en": "### Note",
                "hi": "### सूचना",
                "gu": "### નોંધ"
            }
            note_body = {
                "en": "This answer is based on the BIS Sahayak knowledge base currently loaded into the system. Always verify the latest applicable BIS requirements and official source before making a compliance decision.",
                "hi": "यह उत्तर वर्तमान में सिस्टम में लोड किए गए BIS सहायक ज्ञान आधार पर आधारित है। अनुपालन निर्णय लेने से पहले हमेशा नवीनतम लागू BIS आवश्यकताओं और आधिकारिक स्रोत से सत्यापन करें।",
                "gu": "આ જવાબ સિસ્ટમમાં હાલમાં લોડ થયેલ BIS સહાયક જ્ઞાન આધાર પર આધારિત છે. કોઈપણ નિયમનકારી નિર્ણય લેતા પહેલાં હંમેશા સત્તાવાર BIS સ્રોતથી ચકાસણી કરો."
            }

            answer_parts.append(head_best.get(language, head_best["en"]))
            answer_parts.append(self._format_standard(best, include_scope=True))
            answer_parts.append(self._match_reason(query, best))

            # Relevance
            relevance_percent = round(max(0, min(best_score * 100, 100)))
            answer_parts.append(f"{rel_label.get(language, rel_label['en'])}: **{relevance_percent}%**")

            # Additional standards
            additional_hits = hits[1:3]
            if additional_hits:
                answer_parts.append(head_other.get(language, head_other["en"]))
                for hit in additional_hits:
                    formatted = self._format_standard(hit, include_scope=False)
                    if formatted:
                        answer_parts.append(formatted)

            # Note
            answer_parts.append(note_head.get(language, note_head["en"]))
            answer_parts.append(note_body.get(language, note_body["en"]))

            answer_text = "\n\n".join(answer_parts)

        # -------------------------------------------------
        # Citations
        # -------------------------------------------------

        citations = []

        for hit in hits[:3]:

            verified_value = str(
                hit.get(
                    "verified",
                    ""
                )
            ).strip()

            citations.append({

                "is_number": str(
                    hit.get(
                        "is_number",
                        ""
                    )
                ),

                "title": str(
                    hit.get(
                        "title",
                        ""
                    )
                ),

                "verified": verified_value,

                "source_url": str(
                    hit.get(
                        "source_url",
                        ""
                    )
                ),

                "category": str(
                    hit.get(
                        "category_file",
                        ""
                    )
                ),

                "score": float(
                    hit.get(
                        "_score",
                        0
                    )
                )
            })

        # -------------------------------------------------
        # Verification state
        # -------------------------------------------------

        verified = None

        if str(
            best.get(
                "verified",
                ""
            )
        ).lower() == "yes":

            verified = True

        elif str(
            best.get(
                "verified",
                ""
            )
        ).lower() == "no":

            verified = False

        # -------------------------------------------------
        # Final response
        # -------------------------------------------------

        return {

            "answer": answer_text,

            "citations": citations,

            "verified": verified,

            "results": [
                self._safe_row(
                    hit
                )
                for hit in hits
            ],

            "query": query,

            "category": detected_category,

            "best_match": {

                "is_number": str(
                    best.get(
                        "is_number",
                        ""
                    )
                ),

                "title": str(
                    best.get(
                        "title",
                        ""
                    )
                ),

                "score": best_score
            }
        }

    # =====================================================
    # LOAD TESTING LABS
    # =====================================================

    def _load_labs(self):

        """Load testing labs CSV separately."""

        labs_path = os.path.join(
            self.data_dir,
            "07_testing_labs.csv"
        )

        if not os.path.exists(labs_path):
            print(
                "[BIS Sahayak] WARNING: "
                "07_testing_labs.csv not found."
            )
            return pd.DataFrame()

        try:

            df = pd.read_csv(labs_path)
            df = df.dropna(how="all")
            df = df.fillna("")

            return df.reset_index(drop=True)

        except Exception as e:

            print(
                f"[BIS Sahayak] WARNING: "
                f"Could not load labs: {e}"
            )

            return pd.DataFrame()

    # =====================================================
    # GET LABS (filtered)
    # =====================================================

    def get_labs(
        self,
        category="all",
        state="all",
        query=""
    ):

        """
        Return labs filtered by category, state,
        and/or search query.
        """

        if self.labs_df.empty:
            return []

        df = self.labs_df.copy()

        # Filter by category
        if category and category != "all":

            df = df[
                df["category"]
                .str.lower()
                .str.contains(
                    category.lower(),
                    na=False
                )
            ]

        # Filter by state
        if state and state != "all":

            df = df[
                df["state"]
                .str.lower()
                .str.contains(
                    state.lower(),
                    na=False
                )
            ]

        # Search query
        if query:

            query_lower = query.lower()

            mask = (
                df["lab_name"]
                .str.lower()
                .str.contains(
                    query_lower,
                    na=False
                )
                |
                df["city"]
                .str.lower()
                .str.contains(
                    query_lower,
                    na=False
                )
                |
                df["standards_tested"]
                .str.lower()
                .str.contains(
                    query_lower,
                    na=False
                )
                |
                df["category"]
                .str.lower()
                .str.contains(
                    query_lower,
                    na=False
                )
            )

            df = df[mask]

        # Convert to list of dicts
        results = []

        for _, row in df.iterrows():

            results.append({
                "lab_name": str(
                    row.get("lab_name", "")
                ),
                "city": str(
                    row.get("city", "")
                ),
                "state": str(
                    row.get("state", "")
                ),
                "category": str(
                    row.get("category", "")
                ),
                "standards_tested": str(
                    row.get("standards_tested", "")
                ),
                "accreditation": str(
                    row.get("accreditation", "")
                ),
                "contact_phone": str(
                    row.get("contact_phone", "")
                ),
                "contact_email": str(
                    row.get("contact_email", "")
                ),
                "website": str(
                    row.get("website", "")
                )
            })

        return results

    # =====================================================
    # GET LAB STATES
    # =====================================================

    def get_lab_states(self):

        """Return sorted unique states from lab data."""

        if self.labs_df.empty:
            return []

        states = sorted(
            self.labs_df["state"]
            .dropna()
            .unique()
            .tolist()
        )

        return states

    # =====================================================
    # RECOMMEND LABS
    # =====================================================

    def recommend_labs(self, query):

        """
        Given a product or standard query, detect
        the category and recommend matching labs.
        """

        # Use existing category detection
        detected_category = self.detect_category(
            query
        )

        # Map detected category to lab category
        category_map = {
            "electronics": "electronics",
            "food": "food",
            "food_and_water": "food",
            "jewellery": "jewellery",
            "jewellery_and_hallmarking": "jewellery",
            "footwear": "footwear",
            "construction": "construction",
            "textiles": "textiles"
        }

        lab_category = category_map.get(
            detected_category,
            ""
        )

        # Also try to find applicable standard
        hits = self.search(
            query,
            top_k=3,
            min_score=0.05
        )

        applicable_standard = ""

        if hits:
            applicable_standard = str(
                hits[0].get("is_number", "")
            )

        # Get matching labs
        labs = self.get_labs(
            category=(
                lab_category
                if lab_category
                else "all"
            )
        )

        return {

            "query": query,

            "detected_category": (
                detected_category
                or "unknown"
            ),

            "applicable_standard": (
                applicable_standard
            ),

            "labs_found": len(labs),

            "labs": labs
        }


# =========================================================
# STANDALONE TEST
# =========================================================

if __name__ == "__main__":

    kb = KnowledgeBase(
        data_dir="data"
    )

    test_queries = [

        "Which BIS standard applies to LED bulbs?",

        "What is the standard for gold jewellery?",

        "What standard applies to packaged drinking water?",

        "Which BIS standard applies to steel bars?",

        "I need footwear testing",

        "What is the standard for cotton fabric?",

        "What BIS certification is required?",

        "Tell me about rocket engines"
    ]

    print(
        "\n"
        + "=" * 70
    )

    print(
        "BIS SAHAYAK SEARCH TEST"
    )

    print(
        "=" * 70
    )

    for query in test_queries:

        print(
            f"\nQ: {query}"
        )

        result = kb.answer(
            query
        )

        print(
            "\nANSWER:"
        )

        print(
            result["answer"]
        )

        print(
            f"\nCitations: "
            f"{len(result['citations'])}"
        )

        print(
            f"Category: "
            f"{result.get('category')}"
        )

        print(
            "-" * 70
        )