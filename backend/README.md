# BIS Sahayak — Backend

A real (if simple) retrieval backend replacing the hardcoded JS knowledge
base in the frontend. No API key needed — uses TF-IDF similarity search
over your `data/*.csv` files.

## Folder structure expected

```
bis-sahayak/
├── bis-sahayak-site.html
└── backend/
    ├── main.py
    ├── retrieval.py
    ├── requirements.txt
    └── data/              <- copy your 6 CSVs here (or symlink to ../data)
        ├── 01_electronics.csv
        ├── 02_food_and_water.csv
        ├── 03_jewellery_and_hallmarking.csv
        ├── 04_footwear.csv
        ├── 05_construction.csv
        └── 06_textiles.csv
```

**Important**: copy your actual `data/` folder (the CSVs you've already
been editing) into `backend/data/` — or edit the `data_dir` path in
`main.py` to point at your existing folder instead of duplicating it.

## How to run it

Open a terminal in VS Code, inside the `backend/` folder:

```bash
# 1. create a virtual environment (recommended, keeps things clean)
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. run the server
uvicorn main:app --reload
```

You should see something like:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

## Test it's working

Open **http://127.0.0.1:8000** in a browser — you should see a JSON
response confirming it loaded your CSV rows.

Open **http://127.0.0.1:8000/docs** — this is an auto-generated
interactive API tester. Try the `/api/ask` endpoint with a body like:
```json
{ "query": "what standard applies to LED bulbs" }
```

## Connecting the frontend

Right now `bis-sahayak-site.html` has a hardcoded `KB` array and does
`KB.find(...)`. To connect it to this real backend, replace that logic
in the `handleQuery()` function with a fetch call:

```javascript
async function handleQuery(text) {
  if (!text.trim()) return;
  addRow('user', escapeHTML(text));
  document.getElementById('input').value = '';

  const typingRow = addTyping();
  try {
    const res = await fetch('http://127.0.0.1:8000/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text })
    });
    const data = await res.json();
    typingRow.remove();
    const citHTML = data.citations.map(c =>
      `<span class="stamp">${c.is_number}</span>`
    ).join('');
    addRow('assistant', `<p>${data.answer.replace(/\n/g,'<br>')}</p><div class="citations">${citHTML}</div>`);
  } catch (err) {
    typingRow.remove();
    addRow('assistant', `<p>Couldn't reach the backend — make sure it's running at 127.0.0.1:8000.</p>`);
  }
}
```

**Note**: both the backend (port 8000) and frontend (Live Server, port
5500) need to be running at the same time in two separate terminals/tabs
for this to work.

## What this does and doesn't do

- **Does**: real similarity search against your actual CSV data, returns
  ranked results with citations, has a proper API you can demo in
  `/docs`, correctly says "not found" for irrelevant queries (tested)
- **Doesn't**: generate natural free-form language like a real LLM —
  answers are templated from your CSV fields, not generated text. Good
  enough to show real retrieval working; the next upgrade is piping the
  retrieved rows into an actual LLM call (OpenAI/Gemini) for natural
  phrasing — that's a small change inside `retrieval.py`'s `answer()`
  method once you have an API key.

## Known limitation to mention if asked

TF-IDF matches on word overlap, not true semantic meaning — e.g. it
won't automatically know "sneakers" means "footwear" unless that word
appears in your CSV text. A real deployment would use embedding-based
search (sentence-transformers + FAISS) for better semantic matching.
This is a reasonable, explainable trade-off for hackathon time
constraints — say so directly if a judge asks.
