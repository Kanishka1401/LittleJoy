"""Creator Analysis Engine – explainable ranking of the 20 candidate creators for Little Joys.

Pipeline
    1. post_features()      one row per post: relevance tier, format/setting/language fit,
                            storytelling, product integration, engagement rates (no creator-level logic)
    2. creator_metrics()    one row per creator: medians, posting frequency, recent-window (90 d) vs
                            full-history performance, sponsorship behaviour, content shares
    3. score_creators()     five dimension scores (0-100) built from named components, weighted
                            25/20/20/20/15 into a composite; every component, weight and value is kept
    4. coverage / confidence, bootstrap rank stability, sensitivity rankings, top-5 explanations

Principles (see docs/creator_analysis.md)
    * Missing evidence is NEVER imputed and NEVER scored as zero. A component that cannot be computed is
      dropped and the remaining weights inside that dimension are re-normalised; the loss shows up in
      `evidence_coverage` / `confidence`, not in the score.
    * Audience demographics exist for 3 creators only. Audience fit is scored for all 20 from an
      observable content-targeting proxy; the three demographic snapshots refine (never replace) it.
    * Every label from the post/creator files is AI-generated (audit §4) – scores are exploratory.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from .clean import build_creative_table
from .loaders import split_multilabel
from .metrics import safe_div

# ----------------------------------------------------------------------------------------------
# Configuration (single place to audit every assumption)
# ----------------------------------------------------------------------------------------------
DIMENSION_WEIGHTS = {
    "content_relevance": 0.25,
    "engagement_quality": 0.20,
    "creative_compatibility": 0.20,
    "authenticity": 0.20,
    "audience_fit": 0.15,
}
RECENT_DAYS = 90
MIN_RECENT_VIDEOS = 4          # videos with plays needed inside the recent window to score it
MIN_SPONSORED_VIDEOS = 3       # per side, to compute the sponsored/organic engagement ratio
AD_FIT_SATURATION = 0.15       # a format/setting used in >=15% of Little Joys creatives counts as full fit
SPONSOR_SATURATION = 0.50      # >=50% sponsored posts => sponsorship_balance score 0
DEMO_BLEND = 0.50              # weight of demographics inside audience fit when usable
DEMO_BLEND_PLATFORM_MISMATCH = 0.25
B_DEFAULT = 300
STABILITY_WIDTH = 20.0         # 90% bootstrap score interval this wide (points) => stability 0
CONF_LOW, CONF_HIGH = 0.70, 0.85
SEED = 20261105

# component spec: dimension -> [(name, metric column, transform, weight)]
COMPONENTS = {
    "content_relevance": [
        ("post_relevance", "relevance_mean", "share", 1.00),
    ],
    "engagement_quality": [
        ("er_full_history", "er_full_median", "pct", 0.30),
        ("er_recent_window", "er_recent_median", "pct", 0.20),
        ("comment_rate", "comment_rate_median", "pct", 0.15),
        ("interaction_depth", "depth_median", "pct", 0.20),
        ("er_consistency", "er_robust_cv", "inv_pct", 0.15),
    ],
    "creative_compatibility": [
        ("child_presence", "child_share", "share", 0.20),
        ("format_fit", "format_fit_mean", "share", 0.25),
        ("storytelling", "story_share", "share", 0.15),
        ("setting_fit", "setting_fit_mean", "share", 0.10),
        ("language_fit", "language_fit_mean", "share", 0.10),
        ("product_integration", "product_share", "share", 0.20),
    ],
    "authenticity": [
        ("reach_to_follower", "view_to_follower", "pct", 0.35),
        ("sponsorship_balance", "sponsored_share", "sponsor_balance", 0.25),
        ("sponsored_vs_organic_er", "sponsored_er_ratio", "ratio", 0.25),
        ("on_camera_presence", "on_camera_share", "share", 0.15),
    ],
}
for _d, _c in COMPONENTS.items():
    assert abs(sum(w for *_, w in _c) - 1) < 1e-9, _d
assert abs(sum(DIMENSION_WEIGHTS.values()) - 1) < 1e-9

# ----------------------------------------------------------------------------------------------
# Lexicons / normalisers (documented heuristics over AI-labelled text; no ML)
# ----------------------------------------------------------------------------------------------
NUTRITION_RE = re.compile(
    r"\b(nutrition\w*|nutrient\w*|food\w*|recipe\w*|tiffin|lunch\s?box\w*|lunch|snack\w*|breakfast|meals?|"
    r"milk\w*|protein\w*|vitamin\w*|supplement\w*|gumm(?:y|ies)|immun\w*|fussy|picky|weaning|solids?|"
    r"diet\w*|cook\w*|calcium|iron|sugar\w*|health\s?drink\w*|malt|chocolate|feeding|breastfe\w*|"
    r"lactation|appetite|puree|porridge|khichdi|ragi|millet\w*|dry\s?fruit\w*|weight\s?gain|"
    r"height|eating|eat|healthy)\b", re.I)
CHILD_RE = re.compile(
    r"\b(child\w*|kids?|baby|babies|toddler\w*|infant\w*|newborn\w*|mom|moms|mum|mums|mother\w*|"
    r"parent\w*|son|daughter|school\w*|pediatric\w*|paediatric\w*|little one\w*|preschool\w*)\b", re.I)
CHILD_HEALTH_RE = re.compile(
    r"\b(pediatric\w*|paediatric\w*|vaccin\w*|fever|cough|cold|teething|sleep\w*|doctor|health\w*|"
    r"illness|infection\w*|allerg\w*|growth|development\w*|medicine\w*|medical)\b", re.I)
STORY_TEXT_RE = re.compile(r"\b(?:stor(?:y|ies|ytelling)|narrat\w*|relatable|routine|skit|humou?r\w*|funny|"
                           r"emotional|journey|sentimental)\b", re.I)
PARENT_AUDIENCE_RE = re.compile(r"\b(parent\w*|mother\w*|mom|moms|mum|mums|mamas?|caregiver\w*|famil\w*|"
                                r"child\w*|kids?|baby|babies|newborn\w*|toddler\w*|infant\w*)\b", re.I)
INTERACTION_PROMPT_RE = re.compile(r"\b(comment|share|tag|dm|follow|link in bio|let me know|tell me)\b", re.I)
COMPETITOR_BRANDS = ["gritzo", "little tummys", "horlicks", "bournvita", "pediasure", "complan",
                     "protinex", "cerelac", "nestle", "slurrp"]
OWN_BRAND_RE = re.compile(r"little\s*joys", re.I)

STORY_CONTENT_TYPES = {"comedy_skit", "day_in_life", "testimonial", "tribute"}
MAINSTREAM_LANGS = {"english", "hindi", "hinglish"}
# regional languages Little Joys ads already use (ads.csv) -> full language fit; others partial
AD_REGIONAL_LANGS = {"kannada", "malayalam", "tamil", "punjabi"}
LANG_PARTIAL_FIT = 0.5    # regional language never used in LJ ads, or no speech: neither good nor bad

# post label -> (ad column, ad value). Post values absent from this map have "no equivalent" => fit 0.
FORMAT_CROSSWALK = {
    "voiceover_montage": ("ad_format", "voiceover_montage"),
    "piece_to_camera": ("ad_format", "explainer_to_camera"),
    "skit": ("ad_format", "skit"),
    "demo_or_haul": ("performance_style", "demo_walkthrough"),
    "interview": ("ad_format", "podcast_interview"),
}
SETTING_CROSSWALK = {
    "kitchen": ("setting", "kitchen"),
    "indoor_home": ("setting", "indoor_home"),
    "studio": ("setting", "studio"),
    "retail_store": ("setting", "retail_store"),
    "outdoor": ("setting", "outdoor"),
}
AD_STORY_STRUCTURES = {"routine_integration", "problem_agitate_solve", "family_skit", "day_in_life",
                       "testimonial_review"}


def normalise_language(value) -> tuple[str, ...]:
    """'Hindi/English (Hinglish)' -> ('english','hindi','hinglish'); NaN -> ()."""
    if pd.isna(value):
        return ()
    toks = re.split(r"\s+and\s+|[/,()+]", str(value).lower())
    return tuple(sorted({t.strip() for t in toks if t.strip()}))


def language_fit(tokens: tuple[str, ...]) -> float:
    if not tokens:
        return np.nan
    s = set(tokens)
    if s & MAINSTREAM_LANGS or s & AD_REGIONAL_LANGS:
        return 1.0
    return LANG_PARTIAL_FIT


def categorise_setting(value) -> str:
    if pd.isna(value):
        return "unknown"
    t = str(value).lower()
    if re.search(r"kitchen|dining", t):
        return "kitchen"
    if re.search(r"clinic|hospital|office|doctor|medical", t):
        return "clinical"
    if re.search(r"studio", t):
        return "studio"
    if re.search(r"store|shop|mall|market|retail|supermarket", t):
        return "retail_store"
    if re.search(r"\bcar\b|vehicle|auto|taxi", t):
        return "vehicle"
    if re.search(r"outdoor|park|garden|street|terrace|road|beach|playground|temple|stage|event", t):
        return "outdoor"
    if re.search(r"home|bedroom|living|bathroom|sofa|house|room|indoor|nursery|balcony", t):
        return "indoor_home"
    return "other"


def parse_pct_list(text) -> dict[str, float]:
    """'25-34 48.3%; 35-44 40.1%' -> {'25-34': 0.483, '35-44': 0.401}. NaN -> {}. Never fills gaps."""
    out = {}
    if pd.isna(text):
        return out
    for part in str(text).split(";"):
        m = re.match(r"\s*(.+?)\s+([\d.]+)\s*%\s*$", part)
        if m:
            out[m.group(1).strip()] = float(m.group(2)) / 100
    return out


def pct_rank(s: pd.Series) -> pd.Series:
    """Percentile 0-100 among creators with a value (average ties); NaN stays NaN; single value -> 50."""
    s = s.astype(float)
    ok = s.notna()
    out = pd.Series(np.nan, index=s.index)
    m = int(ok.sum())
    if m == 0:
        return out
    if m == 1:
        out[ok] = 50.0
        return out
    out[ok] = (rankdata(s[ok], method="average") - 1) / (m - 1) * 100
    return out


# ----------------------------------------------------------------------------------------------
# Ad-side reference shares (computed from the completed ad analysis inputs, never hard-coded)
# ----------------------------------------------------------------------------------------------
def ad_reference(ads: pd.DataFrame) -> dict:
    """Shares over the 97 unique creatives; used to build the ad<->post crosswalk fit values."""
    cr, _ = build_creative_table(ads)
    n = len(cr)
    share = lambda col, val: float((cr[col] == val).mean())  # noqa: E731
    return {
        "n_creatives": n,
        "format": {k: share(*v) for k, v in FORMAT_CROSSWALK.items()},
        "setting": {k: share(*v) for k, v in SETTING_CROSSWALK.items()},
        "child_on_screen": float((cr.child_on_screen != "none").mean()),
        "storytelling": float((cr.story_structure.isin(AD_STORY_STRUCTURES)
                               | (cr.performance_style == "storytelling")).mean()),
        "languages": cr.language.str.lower().value_counts(normalize=True).to_dict(),
    }


def crosswalk_table(ref: dict) -> pd.DataFrame:
    rows = []
    for k, (col, val) in FORMAT_CROSSWALK.items():
        rows.append(("content_form", k, col, val, ref["format"][k], min(1, ref["format"][k] / AD_FIT_SATURATION),
                     "mapped"))
    for k, (col, val) in SETTING_CROSSWALK.items():
        rows.append(("setting (normalised)", k, col, val, ref["setting"][k],
                     min(1, ref["setting"][k] / AD_FIT_SATURATION), "mapped"))
    rows += [
        ("children_on_camera", "yes", "child_on_screen", "!= none", ref["child_on_screen"], np.nan,
         "mapped; binary share of posts (no saturation)"),
        ("content_form/content_type/text cues", "narrative", "story_structure/performance_style",
         "routine|problem_agitate_solve|family_skit|day_in_life|testimonial|storytelling", ref["storytelling"],
         np.nan, "mapped; binary share of posts"),
        ("language (normalised)", "english/hindi/hinglish/ad-used regional", "language", "same", np.nan, 1.0,
         "mapped; Gujarati/Telugu/no-speech = 0.5 (no LJ ad evidence)"),
        ("product_shown", "yes", "(no direct ad equivalent)", "", np.nan, np.nan,
         "proxy for comfort with product content; not validated"),
    ]
    for k in ["still_or_carousel", "music_edit", "reaction", "event_footage", "news_package", "other"]:
        rows.append(("content_form", k, "(none)", "", np.nan, 0.0, "NO EQUIVALENT in ad vocabulary -> fit 0"))
    rows.append(("setting (normalised)", "clinical/vehicle/other", "(none)", "", np.nan, 0.0,
                 "NO EQUIVALENT in ad vocabulary -> fit 0"))
    rows.append(("production_quality_1to5", "-", "production", "ugc/semi_pro/studio", np.nan, np.nan,
                 "NOT USED: scales are not comparable and ad analysis found no clear UGC/studio effect"))
    return pd.DataFrame(rows, columns=["post_field", "post_value", "ad_field", "ad_value", "ad_share",
                                       "fit_value", "note"])


# ----------------------------------------------------------------------------------------------
# 1. Post-level features
# ----------------------------------------------------------------------------------------------
def _text_blob(p: pd.DataFrame) -> pd.Series:
    cols = ["topic", "caption", "hook_style", "what_stands_out", "on_screen_text", "transcript"]
    return p[cols].fillna("").agg(" ".join, axis=1).str.lower()


def relevance_tier(blob: str, child_on_camera: bool) -> float:
    """1.0 nutrition+child | 0.7 nutrition only | 0.5 child health | 0.4 child/parenting only | 0 otherwise."""
    nutri = bool(NUTRITION_RE.search(blob))
    child = child_on_camera or bool(CHILD_RE.search(blob))
    if nutri and child:
        return 1.0
    if nutri:
        return 0.7
    if child and CHILD_HEALTH_RE.search(blob):
        return 0.5
    if child:
        return 0.4
    return 0.0


def post_features(posts: pd.DataFrame, ref: dict) -> pd.DataFrame:
    p = posts.copy()
    p["posted_on"] = pd.to_datetime(p["posted_on"])
    blob = _text_blob(p)
    child_cam = p.children_on_camera.eq("yes")
    p["relevance"] = [relevance_tier(b, c) for b, c in zip(blob, child_cam)]
    p["nutrition_hit"] = blob.apply(lambda b: bool(NUTRITION_RE.search(b)))

    # engagement
    eng = p.likes + p.comments + p.reshares
    p["engagements"] = eng
    p["er"] = safe_div(eng, p.plays)                          # videos only
    p["comment_rate"] = safe_div(p.comments, p.plays)
    p["depth"] = safe_div(p.comments + p.reshares, eng)       # share of interactions that are comments/shares
    p["has_plays"] = p.plays.notna()

    # creative compatibility
    p["child_flag"] = child_cam.astype(float).where(p.children_on_camera.notna())
    fmt_fit = {k: min(1.0, v / AD_FIT_SATURATION) for k, v in ref["format"].items()}
    p["format_fit"] = p.content_form.map(lambda v: np.nan if pd.isna(v) else fmt_fit.get(v, 0.0))
    p["setting_cat"] = p.setting.map(categorise_setting)
    set_fit = {k: min(1.0, v / AD_FIT_SATURATION) for k, v in ref["setting"].items()}
    p["setting_fit"] = p.setting_cat.map(lambda v: np.nan if v == "unknown" else set_fit.get(v, 0.0))
    p["lang_tokens"] = p.language.map(normalise_language)
    p["language_fit"] = p.lang_tokens.map(language_fit)
    story_cue = (p.content_form.eq("skit") | p.content_type.isin(STORY_CONTENT_TYPES)
                 | (p.hook_style.fillna("") + " " + p.what_stands_out.fillna("")).str.contains(STORY_TEXT_RE))
    p["story_flag"] = story_cue.astype(float)
    p["product_flag"] = p.product_shown.eq("yes").astype(float).where(p.product_shown.notna())

    # authenticity inputs
    p["sponsored_w"] = p.is_sponsored.map({"yes": 1.0, "no": 0.0, "unclear": 0.5})
    p["is_sponsored_yes"] = p.is_sponsored.eq("yes")
    p["on_camera_w"] = p.creator_on_camera.map({"yes": 1.0, "partial": 0.5, "no": 0.0})

    # audience proxy: is the post aimed at parents / families?
    p["parent_targeted"] = p.audience_signal.map(
        lambda s: np.nan if pd.isna(s) else float(bool(PARENT_AUDIENCE_RE.search(str(s)))))

    # interaction prompts in the caption (reported, not scored)
    p["interaction_prompt"] = p.caption.map(lambda s: np.nan if pd.isna(s) else float(bool(INTERACTION_PROMPT_RE.search(s))))

    # risk flags (reported, not scored)
    brands = p.brands_visible.fillna("").str.lower()
    p["competitor_brand"] = brands.map(lambda b: any(c in b for c in COMPETITOR_BRANDS))
    p["own_brand_seen"] = p.brands_visible.fillna("").map(lambda b: bool(OWN_BRAND_RE.search(b)))
    return p


# ----------------------------------------------------------------------------------------------
# 2. Creator-level metrics
# ----------------------------------------------------------------------------------------------
def _med(s: pd.Series) -> float:
    s = s.dropna()
    return float(s.median()) if len(s) else np.nan


def _robust_cv(s: pd.Series) -> float:
    s = s.dropna()
    if len(s) < 4:
        return np.nan
    m = s.median()
    return float(1.4826 * (s - m).abs().median() / m) if m > 0 else np.nan


def _mean(s: pd.Series) -> float:
    s = s.dropna()
    return float(s.mean()) if len(s) else np.nan


def creator_metrics(feat: pd.DataFrame, creators: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    cut = as_of - pd.Timedelta(days=RECENT_DAYS)
    foll = creators.set_index("creator_id").followers
    rows = []
    for cid, g in feat.groupby("creator_id", sort=True):
        rec = g[g.posted_on >= cut]
        vid, rvid = g[g.has_plays], rec[rec.has_plays]
        n = len(g)
        span = max(1, (g.posted_on.max() - g.posted_on.min()).days)
        sp_v, org_v = vid[vid.is_sponsored.eq("yes")], vid[vid.is_sponsored.eq("no")]
        sp_er, org_er = _med(sp_v.er), _med(org_v.er)
        ratio_ok = len(sp_v) >= MIN_SPONSORED_VIDEOS and len(org_v) >= MIN_SPONSORED_VIDEOS and org_er > 0
        recent_ok = len(rvid) >= MIN_RECENT_VIDEOS
        r = {
            "creator_id": cid, "followers": float(foll[cid]),
            # --- volume / window
            "n_posts": n, "n_video_with_plays": len(vid), "first_post": str(g.posted_on.min().date()),
            "last_post": str(g.posted_on.max().date()), "history_span_days": span,
            "n_recent_posts": len(rec), "n_recent_video_with_plays": len(rvid),
            "posts_per_30d_full": (n - 1) / span * 30 if n > 1 else np.nan,
            "posts_per_30d_recent": len(rec) / RECENT_DAYS * 30,
            "days_since_last_post": (as_of - g.posted_on.max()).days,
            # --- performance: full history vs recent window
            "plays_full_median": _med(vid.plays), "plays_recent_median": _med(rvid.plays) if recent_ok else np.nan,
            "er_full_median": _med(vid.er), "er_recent_median": _med(rvid.er) if recent_ok else np.nan,
            "comment_rate_median": _med(vid.comment_rate), "depth_median": _med(g.depth),
            "er_robust_cv": _robust_cv(vid.er),
            "view_to_follower": _med(vid.plays) / foll[cid] if foll[cid] > 0 else np.nan,
            "er_recent_vs_full": (_med(rvid.er) / _med(vid.er)) if recent_ok and _med(vid.er) > 0 else np.nan,
            # --- relevance
            "relevance_mean": _mean(g.relevance), "relevance_recent_mean": _mean(rec.relevance) if len(rec) >= 3 else np.nan,
            "nutrition_child_share": float((g.relevance == 1.0).mean()),
            "nutrition_any_share": float(g.nutrition_hit.mean()),
            # --- creative compatibility inputs
            "child_share": _mean(g.child_flag), "format_fit_mean": _mean(g.format_fit), "story_share": _mean(g.story_flag),
            "setting_fit_mean": _mean(g.setting_fit), "language_fit_mean": _mean(g.language_fit),
            "product_share": _mean(g.product_flag),
            "interaction_prompt_share": _mean(g.interaction_prompt),
            # --- authenticity inputs
            "sponsored_share": _mean(g.sponsored_w), "sponsored_er_median": sp_er, "organic_er_median": org_er,
            "n_sponsored_videos": len(sp_v), "n_organic_videos": len(org_v),
            "sponsored_er_ratio": sp_er / org_er if ratio_ok else np.nan,
            "on_camera_share": _mean(g.on_camera_w),
            # --- audience proxy
            "parent_targeted_share": _mean(g.parent_targeted),
            # --- completeness of the inputs behind each dimension (for evidence coverage)
            "complete_relevance": float(g[["topic", "what_stands_out"]].notna().any(axis=1).mean()),
            "complete_engagement": len(vid) / n,
            "complete_compat": float(g[["content_form", "children_on_camera", "setting", "language",
                                        "product_shown"]].notna().all(axis=1).mean()),
            "complete_authenticity": float(g.is_sponsored.isin(["yes", "no"]).mean()),
            "complete_audience_proxy": float(g.audience_signal.notna().mean()),
            "transcript_coverage": float(g.transcript.notna().mean()),
            # --- risk flags (never scored)
            "competitor_brand_posts": int(g.competitor_brand.sum()),
            "own_brand_posts": int(g.own_brand_seen.sum()),
        }
        rows.append(r)
    return pd.DataFrame(rows).set_index("creator_id")


# ----------------------------------------------------------------------------------------------
# Audience demographics (3 creators) – parsed, never filled
# ----------------------------------------------------------------------------------------------
def audience_detail(creators: pd.DataFrame, audience: pd.DataFrame) -> pd.DataFrame:
    """One row per creator (20). Creators without a snapshot keep NaN / False: nothing is fabricated."""
    base = creators[["creator_id", "handle"]].copy()
    a = audience.copy()
    a["india_share"] = a.top_countries.map(lambda t: parse_pct_list(t).get("India", np.nan))
    ages = a.age_split.map(parse_pct_list)
    a["age_25_44_share"] = ages.map(lambda d: d.get("25-34", 0.0) + d.get("35-44", 0.0) if d else np.nan)
    a["women_share"] = a.women_pct / 100
    a["demo_match"] = a[["women_share", "india_share", "age_25_44_share"]].mean(axis=1, skipna=False)
    a["platform_mismatch"] = False
    plat = creators.set_index("creator_id")["profile_url"].str.contains("instagram.com")
    a["platform_mismatch"] = [(r.platform != "instagram") and bool(plat.get(r.creator_id, True)) for r in a.itertuples()]
    keep = ["creator_id", "platform", "as_of", "women_share", "india_share", "age_25_44_share", "demo_match",
            "platform_mismatch"]
    d = base.merge(a[keep], on="creator_id", how="left")
    d["has_demographics"] = d.demo_match.notna()
    d["platform_mismatch"] = d.platform_mismatch.fillna(False).astype(bool)
    return d.set_index("creator_id")


# ----------------------------------------------------------------------------------------------
# 3. Scoring
# ----------------------------------------------------------------------------------------------
def _transform(metric: pd.Series, kind: str) -> pd.Series:
    if kind == "pct":
        return pct_rank(metric)
    if kind == "inv_pct":
        return 100 - pct_rank(metric)
    if kind == "share":
        return metric * 100
    if kind == "sponsor_balance":
        return (1 - (metric / SPONSOR_SATURATION).clip(upper=1)) * 100
    if kind == "ratio":
        return metric.clip(lower=0, upper=1) * 100
    raise ValueError(kind)


@dataclass
class ScoreResult:
    scores: pd.DataFrame       # one row per creator
    components: pd.DataFrame   # long: creator x dimension x component


def score_creators(metrics: pd.DataFrame, demo: pd.DataFrame, *, weights: dict | None = None,
                   use_demographics: bool = True, drop_components: tuple[str, ...] = ()) -> ScoreResult:
    """Composite score. Missing components are dropped and weights re-normalised inside the dimension."""
    weights = weights or DIMENSION_WEIGHTS
    comp_rows, dim_scores, dim_cov = [], {}, {}
    idx = metrics.index
    for dim, comps in COMPONENTS.items():
        num = pd.Series(0.0, index=idx)
        den = pd.Series(0.0, index=idx)
        for name, col, kind, w in comps:
            if name in drop_components:
                continue
            sc = _transform(metrics[col], kind)
            ok = sc.notna()
            num += sc.fillna(0) * w * ok
            den += w * ok
            for cid in idx:
                comp_rows.append((cid, dim, name, col, kind, metrics.at[cid, col], sc[cid], w, bool(ok[cid])))
        total_w = sum(w for n, *_, w in comps if n not in drop_components)
        dim_scores[dim] = num / den.replace(0, np.nan)
        dim_cov[dim] = den / total_w

    # audience fit: proxy for everyone, demographics blended in only where they exist
    proxy = metrics.parent_targeted_share * 100
    d = demo.reindex(idx)
    has = d.has_demographics.fillna(False) & use_demographics
    blend = np.where(d.platform_mismatch.fillna(False), DEMO_BLEND_PLATFORM_MISMATCH, DEMO_BLEND)
    blend = pd.Series(np.where(has, blend, 0.0), index=idx)
    demo_score = (d.demo_match * 100).where(has)
    aud = (1 - blend) * proxy + blend * demo_score.fillna(0)
    aud = aud.where(proxy.notna())
    dim_scores["audience_fit"] = aud
    for cid in idx:
        comp_rows.append((cid, "audience_fit", "content_audience_proxy", "parent_targeted_share", "share",
                          metrics.at[cid, "parent_targeted_share"], proxy[cid], 1 - blend[cid], bool(pd.notna(proxy[cid]))))
        comp_rows.append((cid, "audience_fit", "demographic_match", "demo_match(women,india,age25-44)", "share",
                          d.at[cid, "demo_match"], demo_score[cid], blend[cid], bool(has[cid])))
    # coverage: proxy alone = half of the intended evidence; demographics add the rest (0.25 if platform mismatch)
    dim_cov["audience_fit"] = pd.Series(np.where(has, np.where(d.platform_mismatch.fillna(False), 0.75, 1.0), 0.5),
                                        index=idx) * metrics.complete_audience_proxy

    comps = pd.DataFrame(comp_rows, columns=["creator_id", "dimension", "component", "metric", "transform",
                                             "raw_value", "component_score", "effective_weight", "available"])
    # effective weights inside each dimension (re-normalised) so contributions are explicit
    comps["dim_weight"] = comps.dimension.map(weights)
    scores = pd.DataFrame(dim_scores)
    scores["composite_score"] = sum(scores[d_] * w for d_, w in weights.items())
    cov = pd.DataFrame(dim_cov)
    cov = cov.add_prefix("coverage_")
    # input completeness folded into coverage
    comp_map = {"content_relevance": "complete_relevance", "engagement_quality": "complete_engagement",
                "creative_compatibility": "complete_compat", "authenticity": "complete_authenticity"}
    for d_, m_ in comp_map.items():
        cov[f"coverage_{d_}"] = cov[f"coverage_{d_}"] * metrics[m_]
    cov["evidence_coverage"] = sum(cov[f"coverage_{d_}"] * w for d_, w in weights.items())
    out = scores.join(cov)
    out["has_demographics"] = has
    out["demographic_blend_weight"] = blend
    return ScoreResult(out, comps)


def confidence(metrics: pd.DataFrame, scored: pd.DataFrame, boot: pd.DataFrame | None = None) -> pd.DataFrame:
    """Confidence index (0-1): evidence coverage, sample sufficiency and (if given) score stability under
    post resampling. It describes how much to trust a score; it never changes the score itself."""
    c = pd.DataFrame(index=metrics.index)
    c["sufficiency_posts"] = (metrics.n_posts / 20).clip(upper=1)
    c["sufficiency_videos"] = (metrics.n_video_with_plays / 15).clip(upper=1)
    c["sufficiency_recent"] = (metrics.n_recent_video_with_plays / 8).clip(upper=1)
    if boot is not None:
        width = boot.score_p95 - boot.score_p05
        c["stability"] = 1 - (width / STABILITY_WIDTH).clip(upper=1)
        c["confidence_index"] = (0.35 * scored.evidence_coverage + 0.15 * c.sufficiency_posts
                                 + 0.15 * c.sufficiency_videos + 0.15 * c.sufficiency_recent + 0.20 * c.stability)
    else:
        c["stability"] = np.nan
        c["confidence_index"] = (0.4 * scored.evidence_coverage + 0.2 * c.sufficiency_posts
                                 + 0.2 * c.sufficiency_videos + 0.2 * c.sufficiency_recent)
    c["confidence_level"] = pd.cut(c.confidence_index, [-np.inf, CONF_LOW, CONF_HIGH, np.inf],
                                   labels=["Low", "Medium", "High"]).astype(str)
    flags = []
    for cid, m in metrics.iterrows():
        f = []
        if not scored.at[cid, "has_demographics"]:
            f.append("no_demographics(audience fit from content proxy only)")
        if m.n_recent_video_with_plays < MIN_RECENT_VIDEOS:
            f.append("recent_window_thin(recent ER not scored)")
        if m.n_posts < 20:
            f.append(f"short_history({int(m.n_posts)} posts)")
        if m.complete_engagement < 0.75:
            f.append(f"plays_missing_for_{1 - m.complete_engagement:.0%}_of_posts")
        if pd.isna(m.sponsored_er_ratio):
            f.append("sponsored_vs_organic_ER_not_estimable")
        if m.competitor_brand_posts > 0:
            f.append(f"competitor_nutrition_brand_in_{int(m.competitor_brand_posts)}_posts")
        flags.append("; ".join(f))
    c["flags"] = flags
    return c


# ----------------------------------------------------------------------------------------------
# 4. Ranking, bootstrap stability, sensitivity, explanations
# ----------------------------------------------------------------------------------------------
def rank(scored: pd.DataFrame) -> pd.Series:
    order = scored.sort_values(["composite_score"], ascending=False, kind="mergesort")
    return pd.Series(np.arange(1, len(order) + 1), index=order.index).reindex(scored.index)


def bootstrap_ranks(feat: pd.DataFrame, creators: pd.DataFrame, demo: pd.DataFrame, as_of, B=B_DEFAULT, seed=SEED):
    """Resample posts within each creator (with replacement) and re-score the whole cohort."""
    rng = np.random.default_rng(seed)
    pos = {cid: np.flatnonzero((feat.creator_id == cid).to_numpy()) for cid in sorted(feat.creator_id.unique())}
    ids = list(pos)
    S, R = [], []
    for _ in range(B):
        idx = np.concatenate([rng.choice(pos[c], size=len(pos[c]), replace=True) for c in ids])
        m = creator_metrics(feat.iloc[idx], creators, as_of)
        s = score_creators(m, demo).scores.composite_score
        S.append(s)
        R.append(rank(pd.DataFrame({"composite_score": s})))
    S, R = pd.DataFrame(S), pd.DataFrame(R)
    return pd.DataFrame({
        "score_p05": S.quantile(0.05), "score_p95": S.quantile(0.95),
        "rank_p05": R.quantile(0.05), "rank_p95": R.quantile(0.95),
        "p_top5": (R <= 5).mean(), "p_rank1": (R == 1).mean(),
    })


def sensitivity_ranks(metrics, demo) -> pd.DataFrame:
    base = score_creators(metrics, demo).scores
    variants = {
        "base": base,
        "no_demographics": score_creators(metrics, demo, use_demographics=False).scores,
        "full_history_only": score_creators(metrics, demo, drop_components=("er_recent_window",)).scores,
        "equal_weights": score_creators(metrics, demo, weights={k: 0.2 for k in DIMENSION_WEIGHTS}).scores,
    }
    out = pd.DataFrame({f"rank_{k}": rank(v) for k, v in variants.items()})
    for k, v in variants.items():
        out[f"score_{k}"] = v.composite_score
    out["rank_min"] = out.filter(like="rank_").min(axis=1)
    out["rank_max"] = out.filter(like="rank_").max(axis=1)
    return out


def explain(cid: str, scored: pd.DataFrame, comps: pd.DataFrame, metrics: pd.DataFrame, conf: pd.DataFrame,
            boot: pd.DataFrame | None = None, weights=DIMENSION_WEIGHTS) -> dict:
    s, m, c = scored.loc[cid], metrics.loc[cid], conf.loc[cid]
    dims = {d: float(s[d]) for d in weights}
    contrib = {d: dims[d] * weights[d] for d in weights}
    cohort_mean = {d: float(scored[d].mean()) for d in weights}
    strengths = sorted(weights, key=lambda d: dims[d] - cohort_mean[d], reverse=True)[:2]
    weakest = min(weights, key=lambda d: dims[d] - cohort_mean[d])
    cc = comps[(comps.creator_id == cid) & comps.available & (comps.dimension != "audience_fit")]
    top_comp = cc.assign(rel=cc.component_score * cc.dim_weight).sort_values("component_score", ascending=False).head(3)
    label = lambda d: d.replace("_", " ")  # noqa: E731
    parts = [f"Composite {s.composite_score:.1f}/100 (cohort mean {scored.composite_score.mean():.1f}).",
             "Strongest vs cohort: " + "; ".join(f"{label(d)} {dims[d]:.0f} (cohort {cohort_mean[d]:.0f})" for d in strengths) + ".",
             f"{m.nutrition_child_share:.0%} of posts combine nutrition/feeding with children; relevance mean {m.relevance_mean:.2f}.",
             f"Median video ER {m.er_full_median:.2%} (full history, n={int(m.n_video_with_plays)})"
             + (f", {m.er_recent_median:.2%} in last {RECENT_DAYS} days (n={int(m.n_recent_video_with_plays)})."
                if pd.notna(m.er_recent_median) else f"; recent window too thin to score (n={int(m.n_recent_video_with_plays)})."),
             f"Posts ~{m.posts_per_30d_full:.1f}/30 d; {m.child_share:.0%} of posts show children; {m.sponsored_share:.0%} sponsored.",
             f"Weakest vs cohort: {label(weakest)} ({dims[weakest]:.0f} vs cohort {cohort_mean[weakest]:.0f})."]
    if s.has_demographics:
        parts.append("Audience demographics available and blended into audience fit.")
    else:
        parts.append("No demographic data: audience fit uses the content-targeting proxy only (not penalised; lowers coverage).")
    parts.append(f"Evidence coverage {s.evidence_coverage:.0%}; confidence {c['confidence_level']}"
                 + (f"; P(top-5) {boot.at[cid, 'p_top5']:.0%} under post resampling." if boot is not None else "."))
    return {"creator_id": cid, "composite_score": float(s.composite_score), "dimension_scores": dims,
            "weighted_contributions": contrib,
            "strongest_components": [{"dimension": r.dimension, "component": r.component, "score": float(r.component_score)}
                                     for r in top_comp.itertuples()],
            "evidence_coverage": float(s.evidence_coverage), "confidence": c["confidence_level"],
            "flags": c["flags"], "explanation": " ".join(parts)}
