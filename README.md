# LittleJoy — Creator Intelligence Platform

**Turning creator data and advertising insights into smarter campaign decisions.**

LittleJoy is a data-driven creator intelligence and campaign recommendation platform designed to help brands understand advertising performance, evaluate creators, identify creative patterns, and make more informed influencer marketing decisions.

The platform combines reproducible data analysis, explainable creator ranking, creative intelligence, and an interactive dashboard into one integrated workflow.

---

## What LittleJoy Does

LittleJoy goes beyond traditional influencer discovery. It connects three important questions:

- **What works?** Analyze advertising patterns and identify attributes associated with purchases and revenue.
- **Who fits?** Evaluate and rank creators using multiple dimensions rather than follower count alone.
- **Why does it work?** Connect successful advertising patterns with creator content styles to generate actionable creative recommendations.

## Core Features

### 1. Ad Performance Intelligence
- Analyze relationships between ad creative attributes, purchases, and revenue.
- Identify patterns across advertising campaigns.
- Generate structured analytical reports and visualizations.
- Maintain reproducible outputs with seeded analysis and hash-logged run manifests.

### 2. Explainable Creator Intelligence
- Evaluate 20 creators across five weighted dimensions:
  - Relevance — 25%
  - Engagement — 20%
  - Creative Compatibility — 20%
  - Authenticity — 20%
  - Audience Fit — 15%
- Generate an explainable creator shortlist.
- Include evidence coverage, confidence scores, and bootstrap-based ranking stability.
- Support interactive weight adjustments through the dashboard.

### 3. Creative DNA Matching
- Map advertising attributes to creator content characteristics.
- Identify creative similarities and potential compatibility.
- Generate creator-specific style, strengths, and improvement-gap profiles.
- Link recommendations to supporting advertisement and post IDs.

### 4. AI Creative Studio
Generate structured campaign briefs for shortlisted creators, including:
- Campaign concepts and creative hooks.
- 30–45 second video scripts.
- Visual directions and on-screen text.
- Calls to action and tone recommendations.
- Claims to avoid and information requiring confirmation.

Features include editable outputs, section-level regeneration, and Markdown/JSON downloads.

The studio works offline using templates, with an optional Anthropic API integration for LLM-powered generation.

### 5. Interactive Streamlit Dashboard

The platform includes eight main dashboard sections:

| Page | Purpose |
|---|---|
| Home | Platform introduction |
| Overview | Key analytical insights |
| Creator Shortlist | Interactive creator ranking |
| Creator Profiles | Individual creator analysis |
| Ad Intelligence | Advertising performance insights |
| Creative DNA | Ad-to-creator creative matching |
| Campaign Studio | AI-assisted campaign briefs |
| Methodology | Analytical methods and explanations |

---

## Technology Stack

| Category | Technologies |
|---|---|
| Language | Python |
| Data Analysis | Pandas, NumPy |
| Visualization | Matplotlib, Seaborn |
| Machine Learning | Scikit-learn |
| Dashboard | Streamlit |
| Testing | Pytest |
| AI Integration | Anthropic API (optional) |
| Version Control | Git, GitHub |

---

## Project Architecture

```text
LittleJoy/
│
├── app.py
├── requirements.txt
│
├── dashboard/
│   ├── theme.py
│   ├── data loaders
│   └── dashboard pages
│
├── scripts/
│   ├── run_audit.py
│   ├── run_ad_analysis.py
│   ├── run_creator_analysis.py
│   ├── run_creative_dna.py
│   └── run_creative_studio.py
│
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
│
├── reports/
│   ├── tables/
│   ├── ad/
│   ├── creator/
│   └── dna/
│
├── docs/
│   ├── data_audit.md
│   ├── ad_analysis.md
│   ├── creator_analysis.md
│   ├── creative_dna.md
│   └── creative_studio.md
│
└── tests/
```

---

## Getting Started

### Prerequisites
- Python 3.10+
- pip
- Git

### 1. Clone the repository

```bash
git clone https://github.com/Kanishka1401/LittleJoy.git
cd LittleJoy
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

**Windows**
```bash
.venv\Scripts\activate
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the data audit

```bash
python scripts/run_audit.py
```

### 5. Run the analytical pipelines

```bash
python scripts/run_ad_analysis.py
python scripts/run_creator_analysis.py
python scripts/run_creative_dna.py
```

### 6. Launch the dashboard

```bash
streamlit run app.py
```

Open the local URL provided by Streamlit in your browser.

### 7. Run tests

```bash
pytest -q
```

For creator-specific tests:

```bash
pytest -q tests/test_creator_analysis.py
```

---

## Design Principles

**Reproducibility:** Analytical pipelines use deterministic outputs and documented methods.

**Explainability:** Creator recommendations are supported by individual scoring dimensions and evidence rather than unexplained rankings.

**Data Integrity:** Raw input files are treated as read-only. Cleaning and transformations happen through code, with outputs written to separate directories.

**Transparency:** Synthetic advertising performance figures are explicitly identified as synthetic in the dashboard. The platform does not present them as verified real-world campaign results.

**Responsible Recommendations:** The Creative Studio uses available evidence and flags unverified claims with confirmation placeholders.

---

## Documentation

Detailed implementation notes, methodologies, assumptions, and output dictionaries are available in the `docs/` directory.

| Document | Description |
|---|---|
| `data_audit.md` | Data validation and preprocessing |
| `ad_analysis.md` | Advertising analysis methodology |
| `creator_analysis.md` | Creator scoring and ranking |
| `creative_dna.md` | Creative compatibility methodology |
| `creative_studio.md` | AI Creative Studio implementation |

---

## Project

**LittleJoy — Creator Intelligence Platform**

Built to make creator discovery, advertising analysis, and campaign planning more evidence-driven, explainable, and actionable.

**Repository:** [Kanishka1401/LittleJoy](https://github.com/Kanishka1401/LittleJoy)
