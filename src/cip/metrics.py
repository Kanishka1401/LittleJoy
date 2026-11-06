"""Derived metrics. Every ratio is NaN (never inf/0) when its denominator is 0."""
from __future__ import annotations

import numpy as np
import pandas as pd


def safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    den = den.replace(0, np.nan)
    return num / den


def add_ad_metrics(ads: pd.DataFrame) -> pd.DataFrame:
    d = ads.copy()
    d["cpm"] = safe_div(d.spend_inr, d.impressions) * 1000
    d["hook_rate"] = safe_div(d.video_3s_views, d.impressions)      # 3s views / impressions
    d["hold_rate"] = safe_div(d.thruplays, d.video_3s_views)        # thruplays / 3s views
    d["ctr_link"] = safe_div(d.link_clicks, d.impressions)
    d["cpc_link"] = safe_div(d.spend_inr, d.link_clicks)
    d["click_to_atc"] = safe_div(d.add_to_carts, d.link_clicks)
    d["atc_to_purchase"] = safe_div(d.purchases, d.add_to_carts)
    d["cvr_click"] = safe_div(d.purchases, d.link_clicks)           # purchases / link clicks
    d["cpa"] = safe_div(d.spend_inr, d.purchases)
    d["aov"] = safe_div(d.revenue_inr, d.purchases)
    d["roas"] = safe_div(d.revenue_inr, d.spend_inr)
    d["rev_per_1k_impr"] = safe_div(d.revenue_inr, d.impressions) * 1000
    d["spend_per_day"] = safe_div(d.spend_inr, d.days_live)
    return d


def aggregate_roas(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Spend-weighted (ratio-of-sums) aggregation — never average per-ad ROAS."""
    g = df.groupby(by, dropna=False).agg(
        n_ads=("ad_id", "size"),
        spend_inr=("spend_inr", "sum"),
        impressions=("impressions", "sum"),
        link_clicks=("link_clicks", "sum"),
        purchases=("purchases", "sum"),
        revenue_inr=("revenue_inr", "sum"),
    )
    g["roas"] = safe_div(g.revenue_inr, g.spend_inr)
    g["cpa"] = safe_div(g.spend_inr, g.purchases)
    g["cvr_click"] = safe_div(g.purchases, g.link_clicks)
    return g


def add_post_metrics(posts: pd.DataFrame) -> pd.DataFrame:
    d = posts.copy()
    d["engagements"] = d.likes + d.comments + d.reshares
    d["er_by_play"] = safe_div(d.engagements, d.plays)   # videos only (plays absent for photo/carousel)
    d["like_rate"] = safe_div(d.likes, d.plays)
    d["comment_rate"] = safe_div(d.comments, d.plays)
    d["share_rate"] = safe_div(d.reshares, d.plays)
    return d
