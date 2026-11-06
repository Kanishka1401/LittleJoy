"""Cached loaders. Everything is read from outputs the engines already wrote; nothing is recomputed except
the (linear) re-weighting of saved dimension scores on the Rankings page."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cip import creator_analysis as CA   # noqa: E402

CR = ROOT / "reports" / "creator"
AD = ROOT / "reports" / "ad"
RAW = ROOT / "data" / "raw"

DIMS = list(CA.DIMENSION_WEIGHTS)
DIM_LABEL = {"content_relevance": "Content relevance", "engagement_quality": "Engagement quality",
             "creative_compatibility": "Creative compatibility", "authenticity": "Authenticity",
             "audience_fit": "Audience fit"}
DIM_SHORT = {"content_relevance": "Relevance", "engagement_quality": "Engagement", "creative_compatibility": "Compatibility",
             "authenticity": "Authenticity", "audience_fit": "Audience"}


def outputs_ready() -> bool:
    return (CR / "tables" / "creator_ranking.csv").exists() and (AD / "tables" / "baseline_by_variant.csv").exists()


@st.cache_data(show_spinner=False)
def creator_outputs() -> dict:
    t = CR / "tables"
    rd = lambda n: pd.read_csv(t / n)  # noqa: E731
    return dict(
        ranking=rd("creator_ranking.csv"), metrics=rd("creator_metrics.csv"), comps=rd("component_scores.csv"),
        window=rd("window_performance.csv"), coverage=rd("evidence_coverage_confidence.csv"),
        demo=rd("audience_demographics_parsed.csv"), sens=rd("sensitivity_rankings.csv"),
        crosswalk=rd("ad_post_crosswalk.csv"), top5=json.loads((CR / "json" / "top5.json").read_text()),
        config=json.loads((CR / "json" / "weights_and_config.json").read_text()),
        manifest=json.loads((CR / "json" / "run_manifest.json").read_text()))


@st.cache_data(show_spinner=False)
def raw_creator_data() -> dict:
    creators = pd.read_csv(RAW / "creators.csv")
    posts = pd.read_csv(RAW / "creator_posts.csv", parse_dates=["posted_on"])
    posts["engagements"] = posts.likes + posts.comments + posts.reshares
    posts["er"] = posts.engagements / posts.plays.replace(0, np.nan)
    posts["language_norm"] = posts.language.map(lambda v: "+".join(CA.normalise_language(v)) or "none").str.title()
    audience = pd.read_csv(RAW / "creator_audience.csv")
    return dict(creators=creators, posts=posts, audience=audience)


@st.cache_data(show_spinner=False)
def ad_outputs() -> dict:
    t = AD / "tables"
    rd = lambda n: pd.read_csv(t / n)  # noqa: E731
    cre = pd.read_csv(ROOT / "data" / "processed" / "creatives.csv")
    cre["roas"] = cre.revenue_inr / cre.spend_inr.replace(0, np.nan)
    sig = pd.DataFrame(json.loads((AD / "json" / "key_signals.json").read_text())["signals"])
    guard = json.loads((AD / "json" / "key_signals.json").read_text())["interpretation_guardrails"]
    return dict(baseline=rd("baseline_by_variant.csv"), pf=rd("product_form_performance.csv"), funnel=rd("funnel_by_product_form.csv"),
                conc=rd("concentration.csv"), lorenz=rd("concentration_lorenz.csv"), loo=rd("concentration_leave_one_out.csv"),
                corr=rd("correlations_within_product_form.csv"), contrasts=rd("product_form_roas_contrasts.csv"),
                stability=rd("attribute_effects_stability.csv"), signals=sig, guardrails=guard, creatives=cre,
                variants=json.loads((AD / "json" / "variants.json").read_text())["variants"])


def dna_ready() -> bool:
    return (ROOT / "reports" / "dna" / "tables" / "creator_dna_scores.csv").exists()


@st.cache_data(show_spinner=False)
def dna_outputs() -> dict:
    d = ROOT / "reports" / "dna"
    rd = lambda n: pd.read_csv(d / "tables" / n)  # noqa: E731
    return dict(mapping=rd("attribute_mapping.csv"), patterns=rd("ad_success_patterns.csv"), cohort=rd("success_cohort_prevalence.csv"),
                scores=rd("creator_dna_scores.csv"), align=rd("creator_feature_alignment.csv"), ev_posts=rd("evidence_posts.csv"),
                ev_ads=rd("evidence_ads.csv"), stable=rd("stable_signals_mapping_status.csv"),
                profiles=json.loads((d / "json" / "creator_dna_profiles.json").read_text()),
                config=json.loads((d / "json" / "config.json").read_text()))


def reweight(ranking: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    """Composite is a linear blend of the saved 0-100 dimension scores, so re-weighting needs no engine re-run."""
    tot = sum(weights.values())
    w = {k: v / tot for k, v in weights.items()}
    r = ranking.copy()
    for d in DIMS:
        r[f"w_{d}"] = r[d] * w[d]
    r["custom_score"] = r[[f"w_{d}" for d in DIMS]].sum(axis=1)
    r["custom_rank"] = r.custom_score.rank(ascending=False, method="first").astype(int)
    r["rank_change"] = r["rank"] - r["custom_rank"]
    return r.sort_values("custom_rank")


def compact(n: float) -> str:
    n = float(n)
    for div, suf in ((1e7, " Cr"), (1e5, " L")):
        if abs(n) >= div:
            return f"₹{n / div:.2f}{suf}"
    return f"₹{n:,.0f}"


def millions(n: float) -> str:
    return f"{n / 1e6:.2f}M" if abs(n) >= 1e6 else f"{n / 1e3:.0f}K"
