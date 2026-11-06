"""Cleaning / unit construction for ads.

Two analysis units are produced and must both be reported:
  * ad       – 100 rows as delivered (Meta ad level)
  * creative – 97 rows; ads sharing a video_url are collapsed so one video is
               counted once as *evidence* about creative attributes.
Raw data are never modified.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import ADS

OUTCOME_SUM = ["spend_inr", "impressions", "video_3s_views", "thruplays",
               "link_clicks", "add_to_carts", "purchases", "revenue_inr"]
LABEL_COLS = ADS["categorical"] + ["child_role", "demo_shown", "proof_used", "persuasion",
                                   "narratives", "ad_categories", "claims_made",
                                   "transcript", "hook_line", "on_screen_text", "duration_s"]
BRAND_ATTRS = ["brand_said_aloud", "brand_first_said"]
LJ004 = "LJ-004"
MIN_EVIDENCE_SPEND = 5_000
MIN_EVIDENCE_PURCHASES = 10
MIN_TOKEN_SUPPORT = 8
MULTILABEL_COLS = ["child_role", "demo_shown", "proof_used", "persuasion", "narratives", "ad_categories"]


def build_creative_table(ads: pd.DataFrame):
    """Collapse ads that share a video_url. Returns (creatives, duplicate_label_check)."""
    a = ads.sort_values("ad_id").reset_index(drop=True)
    agg = {c: "sum" for c in OUTCOME_SUM}
    agg.update({"launch_date": "min", "stopped_date": "max", "days_live": "max", "ad_id": "first"})
    for c in a.columns:
        if c not in agg and c != "video_url":
            agg[c] = "first"
    g = a.groupby("video_url", sort=False)
    cr = g.agg(agg).reset_index()
    cr["n_ads"] = g.size().values
    cr["ad_ids"] = g["ad_id"].apply(lambda s: ";".join(s)).values
    cr = cr.rename(columns={"ad_id": "creative_id"})
    cr["ad_id"] = cr["creative_id"]          # keeps downstream metric code unit-agnostic

    # prove that the labels we keep ("first") are identical inside duplicate groups
    rows = []
    for url, sub in a[a.duplicated("video_url", keep=False)].groupby("video_url"):
        diff = [c for c in LABEL_COLS if c in sub and sub[c].nunique(dropna=False) > 1]
        rows.append(dict(video_url=url, ad_ids=";".join(sub.ad_id), n_ads=len(sub),
                         labels_differing=";".join(diff) or "none"))
    return cr, pd.DataFrame(rows)


def add_flags(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    ids = d["ad_ids"] if "ad_ids" in d else d["ad_id"]
    d["is_lj004"] = ids.str.contains(LJ004, regex=False)
    d["brand_label_contradiction"] = (d.brand_said_aloud == "no") & (d.brand_first_said == "under_3s")
    d["low_evidence"] = (d.spend_inr < MIN_EVIDENCE_SPEND) | (d.purchases < MIN_EVIDENCE_PURCHASES)
    return d


def add_derived_attributes(df: pd.DataFrame) -> pd.DataFrame:
    """Coarser groupings of sparse AI labels. All inherit the AI-label caveat."""
    d = df.copy()
    d["duration_bin"] = pd.cut(d.duration_s, [0, 30, 45, np.inf], labels=["<=30s", "30-45s", ">45s"]).astype(str)
    lang = {"English": "English", "Hinglish": "Hindi_Hinglish", "Hindi": "Hindi_Hinglish",
            "no speech": "no_speech"}
    d["language_group"] = d.language.map(lang).fillna("regional_other")
    d["child_present"] = np.where(d.child_on_screen == "none", "no", "yes")
    d["cta_group"] = d.cta_type.map({"buy_now": "buy_now", "none": "none"}).fillna("other_cta")
    return d


DERIVED_ATTRS = ["duration_bin", "language_group", "child_present", "cta_group"]


def multilabel_tokens(ads: pd.DataFrame) -> dict[str, list[str]]:
    """Tokens with >= MIN_TOKEN_SUPPORT ads (decided on the 100-ad table; 'none' excluded)."""
    out = {}
    for c in MULTILABEL_COLS:
        toks = ads[c].fillna("").str.split(";").explode().str.strip()
        vc = toks[(toks != "") & (toks != "none")].value_counts()
        out[c] = sorted(vc[vc >= MIN_TOKEN_SUPPORT].index)
    return out


def add_multilabel_flags(df: pd.DataFrame, tokens: dict[str, list[str]]) -> pd.DataFrame:
    d = df.copy()
    new = {}
    for c, toks in tokens.items():
        sets = d[c].fillna("").apply(lambda s: {t.strip() for t in str(s).split(";")})
        for t in toks:
            new[f"ml:{c}={t}"] = sets.apply(lambda S, t=t: t in S)
    return pd.concat([d, pd.DataFrame(new, index=d.index)], axis=1)


def prepare_units(ads: pd.DataFrame):
    """Return ({'ad': df, 'creative': df}, duplicate_check, tokens)."""
    tokens = multilabel_tokens(ads)
    creative, dup_check = build_creative_table(ads)
    units = {}
    for name, df in (("ad", ads.sort_values("ad_id").reset_index(drop=True)), ("creative", creative)):
        df = add_flags(df)
        df = add_derived_attributes(df)
        df = add_multilabel_flags(df, tokens)
        units[name] = df
    return units, dup_check, tokens
