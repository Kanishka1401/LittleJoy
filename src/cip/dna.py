"""Creative DNA Matching – compare creators' natural content style with creative patterns found in Little Joys ads.

What this module does NOT do
    * It does not re-estimate ad effects: every effect size comes from reports/ad/tables/attribute_effects_stability.csv.
    * It does not use organic engagement (likes, plays, ER) anywhere. Organic engagement is not evidence of paid performance.
    * It does not claim causality. Ad effects are observational associations among AI-labelled ads.

Provenance tags used throughout (column `evidence_type`)
    ad_platform_metric   spend / impressions / 3s views / clicks / purchases reported by the ad platform
    ad_ai_label          creative attribute labelled by a model (ads.csv)
    post_ai_label        post attribute labelled by a model (creator_posts.csv)
    post_platform_field  post URL / date / type scraped from the platform
    rule_derived         our keyword/regex rule applied to AI-labelled text (documented in MAPPING)
    assumption           a judgement call (mapping quality, thresholds, templates) – not data
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

from .clean import build_creative_table, add_derived_attributes, add_flags
from .creator_analysis import normalise_language, categorise_setting

# ----------------------------------------------------------------------------------------------
# Configuration (all assumptions in one place)
# ----------------------------------------------------------------------------------------------
SCORABLE_QUALITY = {"direct", "approximate"}     # mapping qualities allowed to enter a score
MIN_SCORED_FEATURES = 3                          # a lens is scored only with >= this many eligible features
MIN_LABELLED_POSTS = 10                          # a feature is eligible for a creator with >= this many labelled posts
STRENGTH_ALIGN, GAP_ALIGN = 0.60, 0.30           # alignment thresholds for the narrative
STAGE_METRIC = {"attention": "hook_rate", "purchase": "cvr_click"}
STAGE_LABEL = {"attention": "Attention (3-second hook rate)", "purchase": "Purchase (click → purchase rate)"}
TOP_QUANTILE = 0.75                              # success cohort = top quartile of ROAS within product form
MIN_STRATUM = 8

HUMOUR_RE = re.compile(r"humou?r|funny|comed|satir|playful|witty|jok", re.I)
GROWTH_RE = re.compile(r"\b(?:growth|growing|height|taller|weight gain|milestone\w*|development)\b", re.I)
SHORTCODE_RE = re.compile(r"/p/([^/]+)/")


def post_id(url: str) -> str:
    m = SHORTCODE_RE.search(str(url))
    return m.group(1) if m else str(url)


def _tokens(s: pd.Series) -> pd.Series:
    return s.fillna("").map(lambda v: {t.strip() for t in str(v).split(";") if t.strip()})


def _na_if(series_bool: pd.Series, source_null: pd.Series) -> pd.Series:
    out = series_bool.astype(float)
    out[source_null] = np.nan
    return out


# ----------------------------------------------------------------------------------------------
# Feature registry = the explicit ad ↔ post mapping
# ----------------------------------------------------------------------------------------------
@dataclass
class Feature:
    id: str
    label: str
    ad_definition: str
    post_definition: str
    quality: str                      # direct | approximate | weak | none
    rationale: str                    # why this quality
    caveat: str
    ad_flag: Callable[[pd.DataFrame], pd.Series]
    post_flag: Callable[[pd.DataFrame], pd.Series] | None
    rows: list = field(default_factory=list)       # (stage, metric, attribute, level, invert)
    post_evidence: str = "post_ai_label"
    opp_strength: str = ""
    opp_gap: str = ""


def _humour_post(p):
    txt = p.tone.fillna("")
    f = p.content_type.eq("comedy_skit") | txt.str.contains(HUMOUR_RE)
    return _na_if(f, p.tone.isna() & p.content_type.isna())


def _story_post(p):
    cue = (p.content_form.eq("skit") | p.content_type.isin({"comedy_skit", "day_in_life", "testimonial", "tribute"})
           | (p.hook_style.fillna("") + " " + p.what_stands_out.fillna("")).str.contains(
               r"\b(?:stor(?:y|ies|ytelling)|narrat\w*|relatable|routine|skit|emotional|journey|sentimental)\b", case=False, regex=True))
    return _na_if(cue, p.content_form.isna() & p.content_type.isna())


def _growth_post(p):
    txt = p.topic.fillna("") + " " + p.caption.fillna("") + " " + p.hook_style.fillna("") + " " + p.what_stands_out.fillna("")
    return _na_if(txt.str.contains(GROWTH_RE), p.topic.isna() & p.caption.isna())


def _english_only(p):
    toks = p.language.map(normalise_language)
    return _na_if(toks.map(lambda t: set(t) == {"english"}), p.language.isna())


FEATURES: list[Feature] = [
    Feature("child_present", "Child visible on screen",
            "child_on_screen ≠ none (any child on screen, any time)", "children_on_camera = yes", "direct",
            "Same concept (a child is visible); both are AI labels of video content.",
            "Ads: the strongest signal is a child in the FIRST 3 s, which posts cannot show (no timing label).",
            lambda c: c.child_present.eq("yes").astype(float), lambda p: _na_if(p.children_on_camera.eq("yes"), p.children_on_camera.isna()),
            rows=[("attention", "hook_rate", "child_present", "yes", False), ("purchase", "cvr_click", "child_present", "yes", False)],
            opp_strength="Build the brief around the creator's own child in the product's routine moment (breakfast, tiffin, milk time).",
            opp_gap="Ask for a child to appear on screen; the creator rarely shows children, so check comfort and consent first."),
    Feature("skit", "Skit format",
            "ad_format = skit", "content_form = skit", "direct",
            "Same label vocabulary on both sides.",
            "Mixed signal in ads: skits earn more 3-second views but have directionally LOWER click→purchase and ROAS.",
            lambda c: c.ad_format.eq("skit").astype(float), lambda p: _na_if(p.content_form.eq("skit"), p.content_form.isna()),
            rows=[("attention", "hook_rate", "ad_format", "skit", False), ("purchase", "cvr_click", "ad_format", "skit", False)],
            opp_strength="A short family skit is the creator's native format; test it as an attention-stage creative and pair it with a clear product step.",
            opp_gap="Skits are not this creator's habit; forcing the format may feel foreign. Consider a lighter scripted moment instead."),
    Feature("explainer_to_camera", "Explainer / piece to camera",
            "ad_format = explainer_to_camera", "content_form = piece_to_camera", "approximate",
            "Both are talking-to-camera formats, but a post 'piece to camera' is not necessarily an explainer.",
            "Post label is broader than the ad label.",
            lambda c: c.ad_format.eq("explainer_to_camera").astype(float), lambda p: _na_if(p.content_form.eq("piece_to_camera"), p.content_form.isna()),
            rows=[("attention", "hook_rate", "ad_format", "explainer_to_camera", False)],
            opp_strength="Creator rarely relies on talking-to-camera, the format with lower hook rates in Little Joys ads; native formats already differ from it.",
            opp_gap="Talking-to-camera is this creator's default; in Little Joys ads it had LOWER hook rates, so test an opening visual or story beat before the explanation."),
    Feature("voiceover_montage", "Voiceover montage",
            "ad_format = voiceover_montage", "content_form = voiceover_montage", "direct", "Same label vocabulary.",
            "Ad evidence is directional only (lower hook rate), so it is not scored.",
            lambda c: c.ad_format.eq("voiceover_montage").astype(float), lambda p: _na_if(p.content_form.eq("voiceover_montage"), p.content_form.isna()),
            rows=[("attention", "hook_rate", "ad_format", "voiceover_montage", False)]),
    Feature("humour", "Humour",
            "humour ≠ none", "content_type = comedy_skit OR tone text contains humour/funny/playful/satire", "approximate",
            "Post side is a keyword rule on AI-written tone text.",
            "Ads: humour raises 3-s hook rate but 'no humour' has HIGHER click→purchase (stable candidate). Humour in ads is rare (15 of 97).",
            lambda c: c.humour.ne("none").astype(float), _humour_post,
            rows=[("attention", "hook_rate", "humour", "situational", False), ("purchase", "cvr_click", "humour", "none", True)],
            post_evidence="rule_derived",
            opp_strength="Light situational humour is natural for this creator; use it to earn attention, and keep the offer/product step unambiguous for conversion.",
            opp_gap="Humour is not part of this creator's style; avoid forcing it."),
    Feature("storytelling", "Storytelling / narrative",
            "persuasion includes storytelling", "skit, day-in-life, testimonial, tribute, or story/relatable/routine cues in text", "approximate",
            "Post side is a rule over AI text and labels; ad side is a persuasion label.",
            "Rule is generous: any 'relatable' or 'routine' cue counts.",
            lambda c: _tokens(c.persuasion).map(lambda s: "storytelling" in s).astype(float), _story_post,
            rows=[("attention", "hook_rate", "ml:persuasion", "storytelling", False)],
            post_evidence="rule_derived",
            opp_strength="Narrative is how this creator already talks; brief a short story with a problem moment and the product in the routine.",
            opp_gap="Little Joys can supply a story outline; the creator posts few narrative pieces."),
    Feature("lifestyle_routine", "Kids' lifestyle / routine content",
            "ad_categories includes lifestyle_kids_routine", "content_type ∈ {lifestyle, day_in_life}", "approximate",
            "Both describe everyday family routine content, labelled independently.",
            "Post 'lifestyle' is a broad catch-all category.",
            lambda c: _tokens(c.ad_categories).map(lambda s: "lifestyle_kids_routine" in s).astype(float),
            lambda p: _na_if(p.content_type.isin({"lifestyle", "day_in_life"}), p.content_type.isna()),
            rows=[("attention", "hook_rate", "ml:ad_categories", "lifestyle_kids_routine", False)],
            opp_strength="Routine/lifestyle content is the creator's base; embed the product in an everyday moment.",
            opp_gap="Routine content is not this creator's focus; the product would need a different setting."),
    Feature("english_only", "English-only language",
            "language_group = English", "post language = English only", "approximate",
            "Both are language labels, but ads label spoken language and posts may label caption language.",
            "English-only ads had lower hook rates than Hindi/Hinglish/regional ads; this is an association, confounded with other attributes.",
            lambda c: c.language_group.eq("English").astype(float), _english_only,
            rows=[("attention", "hook_rate", "language_group", "English", False)],
            opp_strength="Creator posts in Hindi, Hinglish or regional languages; English-only ads had lower hook rates (association, confounded).",
            opp_gap="Creator posts mostly in English only; consider testing a Hinglish/Hindi cut (association only, confounded with other attributes)."),
    Feature("growth_claim", "'Overall growth' narrative",
            "narratives includes kids_overall_growth", "topic/caption/hook text mentions growth/height/development/milestones", "approximate",
            "Post side is a keyword rule; it detects topic mentions, not product claims.",
            "In ads this narrative has LOWER click→purchase and ROAS (stable candidate, size halves without LJ-004).",
            lambda c: _tokens(c.narratives).map(lambda s: "kids_overall_growth" in s).astype(float), _growth_post,
            rows=[("purchase", "cvr_click", "ml:narratives", "kids_overall_growth", False), ("purchase", "roas", "ml:narratives", "kids_overall_growth", False)],
            post_evidence="rule_derived",
            opp_strength="", opp_gap=""),
    # ---- weak / no-equivalent features: shown for transparency, never scored
    Feature("parent_presenter", "Parent/caregiver presenter",
            "creator_type = parent_or_caregiver", "(adult presenter on camera)", "weak",
            "Post presenter labels (age/gender) do not say 'parent' vs 'doctor' vs 'creator'; the ad label means a parent figure.",
            "Not scored: the post side cannot be defined faithfully.",
            lambda c: c.creator_type.eq("parent_or_caregiver").astype(float), None,
            rows=[("purchase", "cvr_click", "creator_type", "parent_or_caregiver", False)]),
    Feature("child_first_3s", "Child in first 3 seconds",
            "child_in_first_3s = yes", "(no equivalent)", "none",
            "creator_posts.csv has no within-video timing labels.", "The strongest attention signal in the ad analysis cannot be matched.",
            lambda c: c.child_in_first_3s.eq("yes").astype(float), None,
            rows=[("attention", "hook_rate", "child_in_first_3s", "yes", False)]),
    Feature("child_speaks", "Child speaks",
            "child_role includes speaks", "(no equivalent)", "none", "No post label for who speaks.", "",
            lambda c: _tokens(c.child_role).map(lambda s: "speaks" in s).astype(float), None,
            rows=[("attention", "hook_rate", "ml:child_role", "speaks", False)]),
    Feature("product_feature_demo", "Product-feature demo",
            "demo_shown includes product_feature_demo", "demo_or_haul (not equivalent)", "weak",
            "Posts' demo_or_haul mixes hauls and unboxing with feature demos.", "Not scored.",
            lambda c: _tokens(c.demo_shown).map(lambda s: "product_feature_demo" in s).astype(float), None,
            rows=[("attention", "hook_rate", "ml:demo_shown", "product_feature_demo", False)]),
    Feature("language_borrowing", "Occasional language borrowing",
            "language_mixing = occasional_borrowing", "language lists both Hindi and English (not equivalent)", "weak",
            "Ads label how much of one language borrows words from another; posts list languages used.", "Not scored.",
            lambda c: c.language_mixing.eq("occasional_borrowing").astype(float), None,
            rows=[("attention", "hook_rate", "language_mixing", "occasional_borrowing", False), ("purchase", "cvr_click", "language_mixing", "occasional_borrowing", False)]),
    Feature("earnest_talk", "Earnest talk style", "performance_style = earnest_talk", "(overlaps explainer; no clean equivalent)", "weak",
            "Would double-count the explainer feature.", "Not scored.", lambda c: c.performance_style.eq("earnest_talk").astype(float), None,
            rows=[("attention", "hook_rate", "performance_style", "earnest_talk", False)]),
    Feature("first_frame_product", "Product in first frame", "first_frame = product", "(no equivalent)", "none",
            "Posts carry no first-frame label.", "", lambda c: c.first_frame.eq("product").astype(float), None,
            rows=[("attention", "hook_rate", "first_frame", "product", False)]),
]
FEATURE_BY_ID = {f.id: f for f in FEATURES}

NO_EQUIVALENT_FIELDS = [
    ("production (ugc / semi_pro / studio)", "production_quality_1to5 is a different, compressed scale; no clear ad effect either."),
    ("proof_used, persuasion (statistics, competitor contrast), cta_type, offer, brand_*", "Organic posts have no CTA/offer/brand-mention structure."),
    ("hook_type / hook_driver", "Post hook_style is free text; no controlled vocabulary to map."),
    ("audio / music / captions", "Not labelled on posts."),
]


# ----------------------------------------------------------------------------------------------
# Ad side
# ----------------------------------------------------------------------------------------------
def ad_units(creatives: pd.DataFrame) -> pd.DataFrame:
    """Creative-level table (97 unique videos) with outcome metrics and one 0/1 column per feature."""
    c = creatives.copy()
    c["hook_rate"] = c.video_3s_views / c.impressions
    c["cvr_click"] = c.purchases / c.link_clicks.replace(0, np.nan)
    c["roas"] = c.revenue_inr / c.spend_inr.replace(0, np.nan)
    for f in FEATURES:
        c[f"f_{f.id}"] = f.ad_flag(c)
    return c


def load_stability(path) -> pd.DataFrame:
    s = pd.read_csv(path)
    return s[s.variant == "creative_all"].copy()


def build_pattern_table(stab: pd.DataFrame, ads: pd.DataFrame) -> pd.DataFrame:
    """One row per (feature, stage-row) with the EXISTING ad-analysis estimate, LJ-004 sensitivity and eligibility."""
    rows = []
    for f in FEATURES:
        for stage, metric, attr, level, invert in f.rows:
            m = stab[(stab.metric == metric) & (stab.attribute == attr) & (stab.level.astype(str) == level)]
            if m.empty:
                continue
            r = m.iloc[0]
            sgn = -1 if invert else 1
            eff, lo, hi = sgn * r.ctrl_diff, sorted([sgn * r.ctrl_lo, sgn * r.ctrl_hi])[0], sorted([sgn * r.ctrl_lo, sgn * r.ctrl_hi])[1]
            ex = sgn * r.diff__creative_excl_LJ004
            exlo, exhi = sorted([sgn * r.lo__creative_excl_LJ004, sgn * r.hi__creative_excl_LJ004])
            scale = 100 if metric in ("hook_rate", "cvr_click") else 1
            has = ads.loc[ads.is_lj004, f"f_{f.id}"]
            lj_has = bool(has.iloc[0] == 1) if len(has) else False
            lj_ok = bool(exlo > 0 or exhi < 0) and np.sign(ex) == np.sign(eff)
            eligible = (r.status == "stable_candidate") and f.quality in SCORABLE_QUALITY and f.post_flag is not None
            if eligible:
                why = ""
            elif r.status != "stable_candidate":
                why = f"ad evidence is '{r.status}' (not a stable candidate)"
            elif f.quality not in SCORABLE_QUALITY:
                why = f"mapping quality '{f.quality}'"
            else:
                why = "no post-side definition"
            rows.append(dict(
                feature_id=f.id, feature=f.label, stage=stage, metric=metric, ad_attribute=attr, ad_level=level,
                effect_inverted_to_feature_present=invert, direction="+" if eff > 0 else "−",
                effect=eff * scale, ci_lo=lo * scale, ci_hi=hi * scale, effect_unit="pts" if scale == 100 else "ROAS",
                n_level=int(r.n_level), q_bh=r.q_bh, ad_status=r.status,
                effect_excl_LJ004=ex * scale, ci_lo_excl_LJ004=exlo * scale, ci_hi_excl_LJ004=exhi * scale,
                lj004_has_feature=lj_has, survives_without_LJ004=lj_ok,
                mapping_quality=f.quality, scored=eligible, reason_not_scored=why,
                evidence_type="ad_ai_label + ad_platform_metric (existing ad analysis, observational)"))
    return pd.DataFrame(rows)


def unmapped_stable_signals(stab: pd.DataFrame, patterns: pd.DataFrame) -> pd.DataFrame:
    """Every stable-candidate ad signal, with its mapping status (nothing silently dropped)."""
    st = stab[(stab.status == "stable_candidate") & stab.duplicate_of.isna()].copy()
    cov = set(zip(patterns.metric, patterns.ad_attribute, patterns.ad_level))
    st["in_registry"] = [(m, a, str(l)) in cov for m, a, l in zip(st.metric, st.attribute, st.level)]
    out = st[["metric", "attribute", "level", "n_level", "ctrl_diff", "ctrl_lo", "ctrl_hi", "diff__creative_excl_LJ004", "in_registry"]].copy()
    out["status"] = np.where(out.in_registry, "mapped (see mapping table)", "no post-side equivalent / mirror / not in registry")
    return out


def success_cohort(ads: pd.DataFrame, top_q: float = TOP_QUANTILE) -> pd.DataFrame:
    """Descriptive only: prevalence of each feature among top-quartile-ROAS creatives (within product form) vs the rest.
    Excludes LJ-004 and low-evidence creatives; LJ-004's own flag is reported separately."""
    d = ads[~ads.is_lj004 & ~ads.low_evidence & ads.roas.notna()].copy()
    d["top"] = False
    for form, g in d.groupby("product_form"):
        if len(g) >= MIN_STRATUM:
            d.loc[g.index, "top"] = g.roas >= g.roas.quantile(top_q)
    rows = []
    lj = ads[ads.is_lj004].iloc[0]
    for f in FEATURES:
        col = f"f_{f.id}"
        a, b = d.loc[d.top, col].dropna(), d.loc[~d.top, col].dropna()
        if len(a) == 0 or len(b) == 0:
            continue
        ta, tb = int(a.sum()), int(b.sum())
        _, p = fisher_exact([[ta, len(a) - ta], [tb, len(b) - tb]])
        rows.append(dict(feature_id=f.id, feature=f.label, n_top=len(a), n_rest=len(b), with_feature_top=ta, with_feature_rest=tb,
                         prevalence_top=ta / len(a), prevalence_rest=tb / len(b), diff=ta / len(a) - tb / len(b), fisher_p_exploratory=p,
                         lj004_has_feature=bool(lj[col] == 1), mapping_quality=f.quality,
                         evidence_type="ad_ai_label + ad_platform_metric (descriptive, exploratory; no multiple-testing control)"))
    return pd.DataFrame(rows)


def ad_evidence(ads: pd.DataFrame, feature_ids: list[str] | None = None, per_feature: int = 8) -> pd.DataFrame:
    rows = []
    for f in FEATURES:
        if feature_ids and f.id not in feature_ids:
            continue
        g = ads[ads[f"f_{f.id}"] == 1].sort_values("hook_rate", ascending=False)
        for r in g.itertuples():
            rows.append(dict(feature_id=f.id, creative_id=r.creative_id, ad_ids=r.ad_ids, product_form=r.product_form, hook_rate=r.hook_rate,
                             cvr_click=r.cvr_click, roas=r.roas, spend_inr=r.spend_inr, purchases=r.purchases, is_lj004=bool(r.is_lj004),
                             low_evidence=bool(r.low_evidence), evidence_type="ad_platform_metric + ad_ai_label"))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------------------------
# Creator side
# ----------------------------------------------------------------------------------------------
def post_unit(posts: pd.DataFrame) -> pd.DataFrame:
    p = posts.copy()
    p["post_id"] = p.post_url.map(post_id)
    for f in FEATURES:
        if f.post_flag is not None:
            p[f"f_{f.id}"] = f.post_flag(p)
    return p


def alignment_table(posts: pd.DataFrame, patterns: pd.DataFrame) -> pd.DataFrame:
    """Creator × feature prevalence and alignment with the ad pattern (+ → prevalence, − → 1 - prevalence)."""
    rows = []
    for cid, g in posts.groupby("creator_id"):
        for f in FEATURES:
            if f.post_flag is None:
                continue
            col = f"f_{f.id}"
            if col not in g:
                continue
            lab = g[col].dropna()
            n, k = len(lab), int(lab.sum())
            prev = k / n if n else np.nan
            for pr in patterns[patterns.feature_id == f.id].itertuples():
                align = np.nan if np.isnan(prev) else (prev if pr.direction == "+" else 1 - prev)
                rows.append(dict(creator_id=cid, feature_id=f.id, feature=f.label, stage=pr.stage, metric=pr.metric, direction=pr.direction,
                                 n_posts_labelled=n, n_posts_with_feature=k, prevalence=prev, alignment=align,
                                 mapping_quality=f.quality, scored_pattern=bool(pr.scored), ad_status=pr.ad_status,
                                 evidence_type=f.post_evidence))
    return pd.DataFrame(rows)


def score_creators(align: pd.DataFrame, patterns: pd.DataFrame) -> pd.DataFrame:
    """Per-lens alignment score: mean alignment over eligible features. NaN (with reason) when not justified."""
    eff = patterns.set_index(["feature_id", "stage", "metric"]).effect.abs()
    out = []
    for cid, g in align.groupby("creator_id"):
        r = {"creator_id": cid}
        for stage in STAGE_METRIC:
            s = g[(g.stage == stage) & g.scored_pattern & (g.n_posts_labelled >= MIN_LABELLED_POSTS)]
            s = s[s.metric == STAGE_METRIC[stage]]          # one pattern per feature per lens
            s = s.drop_duplicates("feature_id")
            n_feat = len(s)
            if n_feat >= MIN_SCORED_FEATURES:
                r[f"{stage}_alignment"] = 100 * s.alignment.mean()
                w = np.array([eff[(a, stage, STAGE_METRIC[stage])] for a in s.feature_id])
                r[f"{stage}_alignment_effect_weighted"] = 100 * float((s.alignment.values * w).sum() / w.sum())
                r[f"{stage}_status"] = "scored"
            else:
                r[f"{stage}_alignment"] = np.nan
                r[f"{stage}_alignment_effect_weighted"] = np.nan
                r[f"{stage}_status"] = f"not scored: {n_feat} eligible feature(s) < required {MIN_SCORED_FEATURES}"
            r[f"{stage}_n_features"] = n_feat
        out.append(r)
    df = pd.DataFrame(out).set_index("creator_id")
    df["attention_rank"] = df.attention_alignment.rank(ascending=False, method="min")
    return df


# ----------------------------------------------------------------------------------------------
# Natural style + narrative
# ----------------------------------------------------------------------------------------------
def natural_style(g: pd.DataFrame, persona: str, habits: str | float) -> dict:
    n = len(g)
    top = lambda col, k=2: [(str(v).replace("_", " "), c / n) for v, c in g[col].value_counts().head(k).items()]  # noqa: E731
    set_cat = g.setting.map(categorise_setting).value_counts()
    langs = g.language.map(lambda v: "+".join(normalise_language(v)) or "none").value_counts()
    facts = {
        "n_posts": n, "forms": top("content_form"), "types": top("content_type"),
        "language": [(k.replace("+", " + "), c / n) for k, c in langs.head(2).items()],
        "setting": [(k.replace("_", " "), c / n) for k, c in set_cat.head(2).items()],
        "children_on_camera": float(g.children_on_camera.eq("yes").mean()),
        "creator_on_camera": float(g.creator_on_camera.eq("yes").mean()),
        "product_shown": float(g.product_shown.eq("yes").mean()),
        "sponsored": float(g.is_sponsored.eq("yes").mean()),
    }
    pct = lambda x: f"{x:.0%}"  # noqa: E731
    fm = ", ".join(f"{k} ({pct(v)})" for k, v in facts["forms"])
    tp = ", ".join(f"{k} ({pct(v)})" for k, v in facts["types"])
    lg = ", ".join(f"{k} ({pct(v)})" for k, v in facts["language"])
    st = ", ".join(f"{k} ({pct(v)})" for k, v in facts["setting"])
    facts["summary"] = (f"Across {n} posts: formats {fm}; content {tp}; language {lg}; settings {st}; children on camera "
                        f"{pct(facts['children_on_camera'])}; product shown {pct(facts['product_shown'])}; sponsored {pct(facts['sponsored'])}.")
    facts["persona_ai_generated"] = persona if isinstance(persona, str) else ""
    facts["format_habits_ai_generated"] = habits if isinstance(habits, str) else ""
    return facts


def build_profile(cid: str, posts: pd.DataFrame, align: pd.DataFrame, scores: pd.DataFrame, patterns: pd.DataFrame, ad_ev: pd.DataFrame,
                  creators: pd.DataFrame) -> dict:
    g = posts[posts.creator_id == cid]
    a = align[(align.creator_id == cid) & (align.scored_pattern)]
    a = a[a.metric == STAGE_METRIC["attention"]].drop_duplicates("feature_id")
    strengths, gaps = [], []
    for r in a.itertuples():
        f = FEATURE_BY_ID[r.feature_id]
        item = dict(feature_id=r.feature_id, feature=r.feature, direction=r.direction,
                    reading=("pattern is associated with HIGHER hook rate; creator does it often" if r.direction == "+" and r.alignment >= STRENGTH_ALIGN else
                             "pattern is associated with HIGHER hook rate; creator rarely does it" if r.direction == "+" else
                             "pattern is associated with LOWER hook rate; creator rarely does it" if r.alignment >= STRENGTH_ALIGN else
                             "pattern is associated with LOWER hook rate; creator does it often"), prevalence=r.prevalence, alignment=r.alignment,
                    n_posts_with_feature=int(r.n_posts_with_feature), n_posts_labelled=int(r.n_posts_labelled), mapping_quality=r.mapping_quality)
        is_strength = r.alignment >= STRENGTH_ALIGN
        pv = f"{r.prevalence:.0%} of posts"
        item["phrase"] = (f"{r.feature} ({pv})" if r.direction == "+" and is_strength else f"little {r.feature.lower()} ({pv})" if r.direction == "+"
                          else f"avoids {r.feature.lower()} ({pv})" if is_strength else f"heavy on {r.feature.lower()} ({pv})")
        if r.alignment >= STRENGTH_ALIGN:
            item["opportunity"] = f.opp_strength
            item["caution"] = f.caveat
            strengths.append(item)
        elif r.alignment <= GAP_ALIGN:
            item["opportunity"] = f.opp_gap
            item["caution"] = f.caveat
            gaps.append(item)
    strengths.sort(key=lambda x: -x["alignment"])
    gaps.sort(key=lambda x: x["alignment"])
    ids = {}
    for it in strengths + gaps:
        f = FEATURE_BY_ID[it["feature_id"]]
        pm = g[g[f"f_{it['feature_id']}"] == 1].sort_values("posted_on", ascending=False)
        am = ad_ev[ad_ev.feature_id == it["feature_id"]]
        am = am[~am.is_lj004 & ~am.low_evidence]
        am = am.sort_values("hook_rate", ascending=(it["direction"] == "−")).head(5)
        ids[it["feature_id"]] = dict(ad_order=("lowest hook rate first" if it["direction"] == "−" else "highest hook rate first") + " (ads with the feature; LJ-004 and low-evidence ads excluded)",
                                     post_ids=pm.post_id.head(6).tolist(), n_posts=len(pm), ad_creative_ids=am.creative_id.tolist(),
                                     n_ads=int((ad_ev.feature_id == it["feature_id"]).sum()),
                                     lj004_has_feature=bool(ad_ev[(ad_ev.feature_id == it["feature_id"]) & ad_ev.is_lj004].shape[0]))
    c = creators.set_index("creator_id").loc[cid]
    sc = scores.loc[cid]
    mixed = [it for it in strengths if it["feature_id"] in ("skit", "humour")]
    pc = []
    for pr in patterns[patterns.stage == "purchase"].drop_duplicates("feature_id").itertuples():
        row = align[(align.creator_id == cid) & (align.feature_id == pr.feature_id)]
        if row.empty:
            continue
        r0 = row.iloc[0]
        pc.append(dict(feature_id=pr.feature_id, feature=pr.feature, prevalence=None if pd.isna(r0.prevalence) else float(r0.prevalence),
                       ad_direction_on_cvr=pr.direction, ad_effect_pts=float(pr.effect), ad_status=pr.ad_status, scored=bool(pr.scored),
                       reading=f"in ads, '{pr.feature}' is associated with {'higher' if pr.direction == '+' else 'LOWER'} click→purchase ({pr.ad_status.replace('_', ' ')})"))
    return dict(creator_id=cid, handle=c.handle, natural_style=natural_style(g, c.persona, c.format_habits),
                attention_alignment=None if pd.isna(sc.attention_alignment) else float(sc.attention_alignment),
                purchase_status=sc.purchase_status, purchase_context=pc, strengths=strengths, gaps=gaps, supporting_ids=ids,
                mixed_signal_features=[m["feature"] for m in mixed])


def explain_profile(p: dict) -> str:
    s = p["natural_style"]["summary"]
    sc = p["attention_alignment"]
    head = f"Attention-stage pattern alignment {sc:.0f}/100 (descriptive, not a performance forecast). " if sc is not None else "Not scored. "
    st = "; ".join(x["phrase"] for x in p["strengths"][:3]) or "none above threshold"
    gp = "; ".join(x["phrase"] for x in p["gaps"][:3]) or "none below threshold"
    return f"{s} {head}Matches: {st}. Gaps vs pattern: {gp}."
