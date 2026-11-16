# BIS Sahayak — Data Collection Starter Files

Six CSV files, one per product category, seeded with standard numbers and
metadata to kick off your corpus. **Open these in Excel or Google Sheets**
and have the team divide categories and fill in gaps.

## Files and their state

| File | Verified entries | Placeholder entries | Notes |
|---|---|---|---|
| 01_electronics.csv | 3 | 3 | LED/appliance data confirmed via search, 2024–2026 revisions |
| 02_food_and_water.csv | 0 | 5 | Needs research pass — also check FSSAI overlap |
| 03_jewellery_and_hallmarking.csv | 6 | 0 | Best-covered category — BIS publishes this well publicly |
| 04_footwear.csv | 0 | 4 | Weakly documented publicly — budget extra time |
| 05_construction.csv | 0 | 6 | Distinguish "code of practice" vs "certification" standards |
| 06_textiles.csv | 0 | 4 | Weakest category — verify everything, consider deprioritizing |

"Verified" means I confirmed it via live web search against BIS or a credible
secondary source just now. "Placeholder" means it's a plausible, commonly-cited
number that your team must confirm before relying on it — do not put
unverified standard numbers in front of judges as if they're certain.

## How to verify a placeholder row

1. Go to **[Know Your Standard](https://www.bis.gov.in/know-your-standard/?lang=en)**
2. Search the IS number, or a keyword (e.g. "footwear", "cement")
3. Confirm: exact current title, latest revision year, whether it's under
   mandatory certification (CRS/ISI) or voluntary
4. Update the row: fill `source_url`, change `verified` to `yes`, add
   `date_accessed`

## Columns explained

- `is_number` — the Indian Standard code (e.g. `IS 1417:2016`)
- `title` — official standard title
- `certification_type` — Mandatory / Voluntary / N/A (some are test methods
  or codes of practice, not certifiable products)
- `scheme` — which BIS scheme applies (ISI mark, CRS, Hallmarking, or N/A)
- `scope_description` — 1–2 sentence plain-language summary — this becomes
  your chatbot's answer text, so write it in the tone you want users to read
- `source_url` — where you found/confirmed it
- `verified` — yes / no — be honest here, it matters for the RAG accuracy
- `notes` — anything future-you or a teammate needs to know

## Other free sources worth mining directly

- **FAQ page**: https://www.bis.gov.in/full-faq/ — already in Q&A format,
  good for training/prompting your chatbot's tone
- **Hallmarking brief PDF**: https://www.bis.gov.in/wp-content/uploads/2020/12/brief-on-Hallmarking.pdf
- **BIS Act & Rules**: https://www.bis.gov.in/the-bureau/bis-act-rules-and-regulations/?lang=en
- **Hallmarking jewellers FAQ**: https://www.bis.gov.in/hallmarking-jewellers/?lang=en

## What NOT to do

- Don't scrape or bypass BIS's paid standard-purchase system in bulk —
  it's both against their terms and undermines your own project's premise.
  Buy 2–3 real standards individually if you want authentic clause-level
  text for your strongest demo answers.
- Don't present a "verified: no" row as fact in your pitch — say "sample
  data, pending verification against official source" if asked.

## Suggested division of labor

Assign one person per 2 files. Jewellery/hallmarking is already in good
shape — start there for your strongest demo category, then use remaining
time on whichever of the other five categories your product-recommendation
demo relies on most.
