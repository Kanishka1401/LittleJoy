<<<<<<< HEAD
# Creator Intelligence Platform – Little Joys

Reproducible analytics for matching ad-creative patterns to purchases/revenue and, later, to creators.

## Quick start
```bash
pip install -r requirements.txt
python scripts/run_audit.py          # loads + validates; writes reports/tables/data_quality_report.csv
pytest -q
```
Set `CIP_RAW_DIR` to read raw CSVs from another folder. Raw files in `data/raw/` are read-only inputs and are never edited;
all cleaning happens in code and is written to `data/interim/` or `data/processed/`.

## Layout
See `docs/data_audit.md` §8 for the full tree and rationale.

## Ad performance analysis
```bash
python scripts/run_ad_analysis.py   # writes reports/ad/{tables,json} and data/processed/*.csv
```
Methods, results and an output dictionary: `docs/ad_analysis.md`. Outputs are deterministic (seeded) and hash-logged in `reports/ad/json/run_manifest.json`.

## Creator analysis engine
```bash
python scripts/run_creator_analysis.py   # ~70 s (300 bootstrap resamples); writes reports/creator/{tables,json}
pytest -q tests/test_creator_analysis.py
```
Explainable 5-dimension ranking of the 20 creators (relevance 25 / engagement 20 / creative compatibility 20 / authenticity 20 / audience fit 15)
with evidence coverage, confidence and bootstrap rank stability. Methods, results and output dictionary: `docs/creator_analysis.md`.
Reads `data/raw/` only; never writes to `reports/ad/` or `data/processed/`.

## Dashboard (Streamlit)
```bash
pip install -r requirements.txt
streamlit run app.py
```
Eight pages behind a top masthead: Home (landing page), Overview, Creator shortlist (interactive weights), Creator profiles, Ad intelligence, Creative DNA, Campaign Studio, Methodology. The interface uses an editorial ivory/forest design (`dashboard/theme.py`); the ad performance figures are synthetic and the app says so on every page. The app only reads
`reports/ad/`, `reports/creator/` and `data/` outputs; re-run `scripts/run_ad_analysis.py` / `scripts/run_creator_analysis.py` to refresh them.
Code: `app.py` (navigation) and `dashboard/` (theme, data loaders, one module per page).

## Creative DNA matching
```bash
python scripts/run_creative_dna.py   # writes reports/dna/ (reads reports/ad and reports/creator; changes neither)
```
Explicit ad↔post attribute mapping, LJ-004-aware ad patterns and per-creator style/strength/gap profiles with supporting ad and post IDs; shown on the
**Creative DNA** page of the dashboard. Methods and caveats: `docs/creative_dna.md`.

## AI Creative Studio
Sidebar page **AI Creative Studio**: pick one of the five shortlisted creators, generate a brief (concept, 3 hooks, 30-45 s script, visual directions, on-screen text, CTA, tone, claims to avoid), edit it, regenerate single sections and download .md/.json. Works offline from templates; an optional LLM path activates with `ANTHROPIC_API_KEY`. Only claims found in Little Joys' own ad files are used; everything else is a `[[CONFIRM: ...]]` placeholder. See `docs/creative_studio.md`; batch outputs via `python scripts/run_creative_studio.py`.
=======
# LittleJoy
Data-driven creator intelligence and campaign recommendation platform
>>>>>>> a6a7eea757619493b483158b506406d0f0d0aacc
