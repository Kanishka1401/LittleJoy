"""Data validation. Each check returns a Finding; nothing is silently fixed.

Severity:
  ERROR – breaks an assumption analysis depends on (pipeline should stop)
  WARN  – real data-quality issue; handle explicitly in analysis
  INFO  – worth knowing; not necessarily wrong
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd

from .schema import SCHEMAS, EXPECTED_ROWS, EXPECTED_COLS

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"
LOW_SPEND_INR = 5_000        # below this, ratios are noise
LOW_PURCHASES = 10
MAX_LANG_LEN = 30            # longer transcript_language values are corrupted


@dataclass
class Finding:
    dataset: str
    check: str
    severity: str
    n_affected: int
    detail: str
    ids: str = ""

    def as_dict(self):
        return asdict(self)


def _f(ds, check, sev, mask_or_n, detail, id_series=None):
    if isinstance(mask_or_n, pd.Series):
        n = int(mask_or_n.sum())
        ids = ",".join(map(str, id_series[mask_or_n].head(15))) if id_series is not None else ""
    else:
        n, ids = int(mask_or_n), ""
    return Finding(ds, check, sev if n else INFO, n, detail if n else "OK", ids)


# ---------------------------------------------------------------- generic
def check_shape_and_columns(name, df):
    out = []
    schema = SCHEMAS[name]
    declared = {c for k, v in schema.items() if k not in ("ai_labelled", "outcome") for c in v}
    missing = declared - set(df.columns)
    out.append(_f(name, "declared_columns_present", ERROR, len(missing), f"missing: {sorted(missing)}"))
    out.append(_f(name, "row_count_as_expected", WARN, int(len(df) != EXPECTED_ROWS[name]),
                  f"{len(df)} rows vs {EXPECTED_ROWS[name]} expected"))
    out.append(_f(name, "column_count_as_expected", WARN, int(df.shape[1] != EXPECTED_COLS[name]),
                  f"{df.shape[1]} cols vs {EXPECTED_COLS[name]} expected"))
    out.append(_f(name, "exact_duplicate_rows", ERROR, int(df.duplicated().sum()), "duplicate rows"))
    return out


# ------------------------------------------------------------------- ads
def validate_ads(a: pd.DataFrame):
    o = check_shape_and_columns("ads", a)
    ds = "ads"
    o.append(_f(ds, "ad_id_unique", ERROR, int(a.ad_id.duplicated().sum()), "duplicate ad_id"))
    o.append(_f(ds, "meta_id_unique", ERROR, int(a.meta_ad_library_id.duplicated().sum()), "duplicate meta id"))
    for c in ["spend_inr", "impressions", "video_3s_views", "thruplays", "link_clicks",
              "add_to_carts", "purchases", "revenue_inr"]:
        o.append(_f(ds, f"{c}_non_negative_non_null", ERROR, (a[c].isna() | (a[c] < 0)), f"{c} null/negative", a.ad_id))
    # funnel monotonicity
    for hi, lo in [("impressions", "video_3s_views"), ("video_3s_views", "thruplays"),
                   ("impressions", "link_clicks"), ("link_clicks", "add_to_carts"),
                   ("add_to_carts", "purchases")]:
        o.append(_f(ds, f"funnel_{lo}_le_{hi}", ERROR, a[lo] > a[hi], f"{lo} > {hi}", a.ad_id))
    o.append(_f(ds, "revenue_without_purchases", ERROR, (a.revenue_inr > 0) & (a.purchases == 0), "rev>0, purchases=0", a.ad_id))
    o.append(_f(ds, "purchases_without_revenue", ERROR, (a.revenue_inr == 0) & (a.purchases > 0), "purchases>0, rev=0", a.ad_id))
    o.append(_f(ds, "zero_purchase_ads", WARN, a.purchases == 0, "ROAS=0 / CPA undefined", a.ad_id))
    # dates
    o.append(_f(ds, "stopped_before_launch", ERROR, a.stopped_date < a.launch_date, "stop < launch", a.ad_id))
    delta = (a.stopped_date - a.launch_date).dt.days
    o.append(_f(ds, "days_live_vs_dates_mismatch", WARN, a.days_live != delta,
                "days_live != (stopped-launch).days; check inclusive/exclusive counting", a.ad_id))
    n_stop = a.stopped_date.nunique()
    o.append(_f(ds, "stopped_date_clustered", WARN, int(n_stop <= 0.2 * len(a)),
                f"only {n_stop} distinct stopped_date values for {len(a)} ads — likely export/snapshot dates, not true stop dates"))
    o.append(_f(ds, "short_run_ads(<=3d)", INFO, a.days_live <= 3, "days_live<=3: unstable", a.ad_id))
    # sample-size cautions
    o.append(_f(ds, "low_spend_ads", WARN, a.spend_inr < LOW_SPEND_INR, f"spend<{LOW_SPEND_INR}", a.ad_id))
    o.append(_f(ds, "low_purchase_ads", WARN, a.purchases < LOW_PURCHASES, f"purchases<{LOW_PURCHASES}", a.ad_id))
    # duplicate creatives
    dup = a.duplicated("video_url", keep=False)
    o.append(_f(ds, "same_video_multiple_ad_ids", WARN, dup, "same video_url under >1 ad_id: aggregate to creative level", a.ad_id))
    o.append(_f(ds, "duplicate_transcripts", WARN, a.duplicated("transcript", keep=False), "identical transcript", a.ad_id))
    # missing labels
    for c in ["hook_type", "ad_format", "story_structure", "child_role", "brand_first_said", "creator_age"]:
        o.append(_f(ds, f"{c}_missing", WARN, a[c].isna(), f"{c} null", a.ad_id))
    o.append(_f(ds, "ad_copy_missing", INFO, a.ad_copy.isna(), "ad_copy null"))
    # AI-label internal contradictions
    o.append(_f(ds, "brand_not_said_but_first_said_under_3s", WARN,
                (a.brand_said_aloud == "no") & (a.brand_first_said == "under_3s"),
                "contradictory brand-mention labels (brand_first_said may include on-screen brand?)", a.ad_id))
    o.append(_f(ds, "child_none_but_child_age", WARN,
                (a.child_on_screen == "none") & (a.child_age != "none"), "child contradiction", a.ad_id))
    o.append(_f(ds, "no_speech_but_speaks_role", WARN,
                (a.language == "no speech") & a.child_role.fillna("").str.contains("speaks"), "contradiction", a.ad_id))
    # ad_copy is campaign-level, not creative-level
    o.append(_f(ds, "ad_copy_shared_across_ads", INFO,
                a.ad_copy.notna() & a.duplicated("ad_copy", keep=False),
                f"{a.ad_copy.nunique()} distinct ad_copy values: copy is not a creative-level variable"))
    # confounding: longer-running ads accumulate spend
    rho = a[["days_live", "spend_inr"]].corr(method="spearman").iloc[0, 1]
    o.append(Finding(ds, "spend_vs_days_live_spearman", INFO, len(a), f"rho={rho:.2f} — spend is largely a function of run time"))
    o.append(Finding(ds, "no_creator_key", INFO, len(a), "ads.csv has no creator_id/handle: ads cannot be joined to creators.csv"))
    return o


# -------------------------------------------------------------- creators
def validate_creators(c: pd.DataFrame, posts: pd.DataFrame):
    o = check_shape_and_columns("creators", c.drop(columns=["audience_comment_evidence"], errors="ignore"))
    ds = "creators"
    o.append(_f(ds, "creator_id_unique", ERROR, int(c.creator_id.duplicated().sum()), "dup creator_id"))
    o.append(_f(ds, "handle_unique", ERROR, int(c.handle.duplicated().sum()), "dup handle"))
    o.append(_f(ds, "verified_values", ERROR, ~c.verified.isin(["yes", "no"]), "unexpected verified value", c.creator_id))
    o.append(_f(ds, "bio_missing", INFO, c.bio.isna(), "bio null", c.creator_id))
    actual = posts.groupby("creator_id").size()
    mism = c.set_index("creator_id").posts_in_file != actual.reindex(c.creator_id).values
    o.append(_f(ds, "posts_in_file_matches_posts_csv", ERROR, int(mism.sum()), "posts_in_file != actual rows"))
    short = c.posts_in_file < c.posts_in_file.max()
    o.append(_f(ds, "creators_with_fewer_posts", WARN, short, "fewer posts in sample → noisier", c.creator_id))
    if "audience_comment_evidence" in c:
        none_ct = (c.audience_comment_evidence == "none").sum()
        o.append(_f(ds, "audience_read_has_no_comment_evidence", WARN, int(none_ct),
                    f"{none_ct}/{len(c)} audience_read blobs say comment_evidence='none' → field carries no information"))
    o.append(_f(ds, "persona_not_unique", INFO, int(c.persona.nunique() < len(c)), "persona labels repeat/near-duplicate"))
    o.append(_f(ds, "followers_zero_or_negative", ERROR, c.followers <= 0, "bad followers", c.creator_id))
    return o


# ----------------------------------------------------------------- posts
def validate_posts(p: pd.DataFrame, c: pd.DataFrame):
    o = check_shape_and_columns("posts", p)
    ds = "posts"
    o.append(_f(ds, "post_url_unique", ERROR, int(p.post_url.duplicated().sum()), "dup post_url"))
    o.append(_f(ds, "creator_fk_valid", ERROR, ~p.creator_id.isin(c.creator_id), "creator_id not in creators", p.post_url))
    m = p.merge(c[["creator_id", "handle"]], on="creator_id", how="left", suffixes=("", "_c"))
    o.append(_f(ds, "handle_matches_creator", ERROR, int((m.handle != m.handle_c).sum()), "handle mismatch"))
    o.append(_f(ds, "posted_on_in_future", ERROR, p.posted_on > pd.Timestamp.today().normalize(), "future date", p.post_url))
    non_video = p.type != "video"
    o.append(_f(ds, "plays_missing_for_video", ERROR, (p.type == "video") & p.plays.isna(), "video without plays", p.post_url))
    o.append(_f(ds, "plays_missing_non_video", INFO, non_video & p.plays.isna(),
                "carousel/photo have no plays → exclude from play-based rates"))
    v = p.dropna(subset=["plays"])
    o.append(_f(ds, "likes_gt_plays", WARN, int((v.likes > v.plays).sum()), "likes>plays"))
    o.append(_f(ds, "negative_counts", ERROR, int(((p[["likes", "comments", "reshares"]] < 0).any(axis=1)).sum()), "negative engagement"))
    o.append(_f(ds, "caption_missing", INFO, p.caption.isna(), "caption null"))
    o.append(_f(ds, "duplicate_captions", INFO, p.caption.notna() & p.caption.duplicated(keep=False), "same caption on >1 post", p.post_url))
    o.append(_f(ds, "child_ages_vs_children_on_camera", WARN,
                ((p.children_on_camera == "yes") & p.child_ages.isna()) | ((p.children_on_camera == "no") & p.child_ages.notna()),
                "inconsistent", p.post_url))
    spons_no_brand = (p.is_sponsored == "yes") & p.brands_visible.isna()
    o.append(_f(ds, "sponsored_without_brand", WARN, spons_no_brand, "sponsored but no brand listed", p.post_url))
    o.append(_f(ds, "sponsored_unclear", INFO, p.is_sponsored == "unclear", "is_sponsored='unclear'", p.post_url))
    o.append(_f(ds, "language_label_variants", WARN, int(p.language.nunique() > 8),
                f"{p.language.nunique()} spellings of language (e.g. 'Hindi/English', 'Hindi and English', 'English and Hindi', 'telugu'/'Telugu') → normalise"))
    bad_tl = p.transcript_language.fillna("").str.len() > MAX_LANG_LEN
    o.append(_f(ds, "transcript_language_corrupted", WARN, bad_tl, "transcript text leaked into transcript_language", p.post_url))
    o.append(_f(ds, "transcript_coverage_low", WARN, int(p.transcript.notna().mean() < 0.5),
                f"transcript for only {p.transcript.notna().mean():.0%} of posts"))
    o.append(_f(ds, "transcript_on_non_video", INFO, non_video & p.transcript.notna(), "transcript on non-video"))
    # observation windows differ hugely by creator
    span = p.groupby("creator_id").posted_on.agg(lambda s: (s.max() - s.min()).days)
    o.append(Finding(ds, "observation_window_days", WARN if span.max() > 5 * max(span.min(), 1) else INFO,
                     len(span), f"per-creator span {int(span.min())}–{int(span.max())} days for ~20 posts each → rates not comparable without a common window"))
    o.append(_f(ds, "quality_score_range", WARN, int(p.production_quality_1to5.nunique() <= 4),
                f"production_quality_1to5 uses only {sorted(int(x) for x in p.production_quality_1to5.unique())}"))
    lj = p.brands_visible.fillna("").str.contains("little joys", case=False)
    o.append(_f(ds, "little_joys_posts", INFO, lj, "posts already showing Little Joys (check case variants)", p.post_url))
    return o


# -------------------------------------------------------------- audience
def validate_audience(au: pd.DataFrame, c: pd.DataFrame):
    o = check_shape_and_columns("audience", au)
    ds = "audience"
    o.append(_f(ds, "creator_fk_valid", ERROR, ~au.creator_id.isin(c.creator_id), "unknown creator", au.creator_id))
    pct = au.women_pct + au.men_pct
    o.append(_f(ds, "gender_pct_sums_to_100", WARN, (pct - 100).abs() > 0.5, "women+men != 100", au.creator_id))
    o.append(_f(ds, "brands_in_past_year_missing", INFO, au.brands_in_past_year.isna(), "null — unknown vs none", au.creator_id))
    m = au.merge(c[["creator_id", "profile_url"]], on="creator_id")
    plat_mismatch = ~m.apply(lambda r: r.platform in r.profile_url, axis=1)
    plat_mismatch.index = au.index
    o.append(_f(ds, "platform_matches_profile_url", WARN, plat_mismatch,
                "audience platform differs from the Instagram profile_url in creators.csv", au.creator_id))
    o.append(Finding(ds, "coverage", WARN, len(au),
                     f"audience data for {len(au)}/{c.shape[0]} creators ({', '.join(au.creator_id)}) — cannot be used for the other {c.shape[0]-len(au)}"))
    return o


def validate_all(d: dict) -> pd.DataFrame:
    findings = (validate_ads(d["ads"]) + validate_creators(d["creators"], d["posts"])
                + validate_posts(d["posts"], d["creators"]) + validate_audience(d["audience"], d["creators"]))
    df = pd.DataFrame([f.as_dict() for f in findings])
    order = {ERROR: 0, WARN: 1, INFO: 2}
    df["_o"] = df.severity.map(order)
    return df.sort_values(["dataset", "_o", "check"]).drop(columns="_o").reset_index(drop=True)
