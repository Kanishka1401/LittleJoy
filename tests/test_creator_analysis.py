import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cip import creator_analysis as CA  # noqa: E402
from cip.loaders import load_all        # noqa: E402


# ------------------------------------------------------------------ pure helpers
def test_dimension_weights_match_brief():
    assert CA.DIMENSION_WEIGHTS == {"content_relevance": 0.25, "engagement_quality": 0.20,
                                    "creative_compatibility": 0.20, "authenticity": 0.20, "audience_fit": 0.15}
    assert sum(CA.DIMENSION_WEIGHTS.values()) == pytest.approx(1.0)
    for dim, comps in CA.COMPONENTS.items():
        assert sum(w for *_, w in comps) == pytest.approx(1.0), dim


def test_pct_rank_ties_nan_and_singleton():
    r = CA.pct_rank(pd.Series([10, 20, 20, 40, np.nan]))
    assert r.iloc[0] == 0 and r.iloc[3] == 100 and r.iloc[1] == r.iloc[2] == pytest.approx(50 * 1.0 * 1.0, abs=20)
    assert np.isnan(r.iloc[4])                       # missing stays missing, is not ranked as 0
    assert CA.pct_rank(pd.Series([5.0, np.nan])).iloc[0] == 50


def test_parsers_do_not_fabricate():
    assert CA.parse_pct_list("25-34 48.3%; 35-44 40.1%") == {"25-34": 0.483, "35-44": 0.401}
    assert CA.parse_pct_list(np.nan) == {} and CA.parse_pct_list("garbage") == {}
    assert CA.normalise_language("Hindi/English (Hinglish)") == ("english", "hindi", "hinglish")
    assert CA.normalise_language("English and Telugu") == ("english", "telugu")
    assert CA.normalise_language(np.nan) == ()
    assert np.isnan(CA.language_fit(()))
    assert CA.language_fit(("english", "telugu")) == 1.0 and CA.language_fit(("telugu",)) == CA.LANG_PARTIAL_FIT
    assert CA.categorise_setting("home kitchen and living area") == "kitchen"
    assert CA.categorise_setting("office or clinic with curtains") == "clinical"
    assert CA.categorise_setting("indoor bedroom") == "indoor_home"
    assert CA.categorise_setting(np.nan) == "unknown"


def test_relevance_tiers():
    assert CA.relevance_tier("healthy tiffin recipe for kids", False) == 1.0
    assert CA.relevance_tier("protein smoothie recipe", False) == 0.7
    assert CA.relevance_tier("baby fever and vaccine advice", False) == 0.5
    assert CA.relevance_tier("a mom day out", False) == 0.4
    assert CA.relevance_tier("a street comedy skit", False) == 0.0
    assert CA.relevance_tier("a street comedy skit", True) == 0.4     # children on camera alone = parenting context


def test_sponsor_balance_and_ratio_transforms():
    s = pd.Series([0.0, 0.25, 0.5, 1.0])
    assert CA._transform(s, "sponsor_balance").tolist() == [100, 50, 0, 0]
    assert CA._transform(pd.Series([0.5, 1.0, 2.0]), "ratio").tolist() == [50, 100, 100]


# ------------------------------------------------------------------ synthetic cohort
def _synthetic(n_creators=4, posts_each=12, as_of="2026-10-27"):
    rng = np.random.default_rng(0)
    as_of = pd.Timestamp(as_of)
    creators = pd.DataFrame({"creator_id": [f"C{i}" for i in range(n_creators)],
                             "handle": [f"h{i}" for i in range(n_creators)],
                             "followers": [1000.0 * (i + 1) for i in range(n_creators)],
                             "profile_url": [f"https://www.instagram.com/h{i}/" for i in range(n_creators)]})
    rows = []
    for i, cid in enumerate(creators.creator_id):
        for k in range(posts_each):
            plays = 1000 * (k + 1)
            rows.append(dict(
                creator_id=cid, post_url=f"u{i}_{k}", posted_on=as_of - pd.Timedelta(days=10 * k),
                plays=plays, likes=int(plays * 0.02 * (i + 1)), comments=10, reshares=5,
                topic="healthy tiffin recipe for kids", caption="c", hook_style="h", what_stands_out="w",
                on_screen_text=None, transcript=None, content_type="lifestyle", content_form="voiceover_montage",
                creator_on_camera="yes", children_on_camera="yes", setting="home kitchen", language="Hindi",
                product_shown="yes", is_sponsored="yes" if k % 4 == 0 else "no",
                audience_signal="parents of young children", brands_visible=None))
    return creators, pd.DataFrame(rows), as_of


def _ref():
    return {"format": {k: 0.3 for k in CA.FORMAT_CROSSWALK}, "setting": {k: 0.3 for k in CA.SETTING_CROSSWALK},
            "child_on_screen": 0.6, "storytelling": 0.6, "n_creatives": 97, "languages": {}}


def _demo(creators, rows=None):
    d = pd.DataFrame({"creator_id": creators.creator_id, "handle": creators.handle, "platform": np.nan,
                      "as_of": np.nan, "women_share": np.nan, "india_share": np.nan, "age_25_44_share": np.nan,
                      "demo_match": np.nan, "platform_mismatch": False, "has_demographics": False}).set_index("creator_id")
    for cid, v in (rows or {}).items():
        d.loc[cid, ["demo_match", "has_demographics"]] = [v, True]
    d["has_demographics"] = d.has_demographics.astype(bool)
    return d


def test_creator_metrics_hand_computed():
    creators, posts, as_of = _synthetic()
    feat = CA.post_features(posts, _ref())
    m = CA.creator_metrics(feat, creators, as_of)
    c0 = m.loc["C0"]
    # posts at 0,10,...,110 days before as_of -> span 110 d, 12 posts
    assert c0.n_posts == 12 and c0.history_span_days == 110
    assert c0.posts_per_30d_full == pytest.approx(11 / 110 * 30)
    assert c0.n_recent_posts == 10 and c0.posts_per_30d_recent == pytest.approx(10 / 90 * 30)   # days 0..90 inclusive
    er = feat[feat.creator_id == "C0"].er
    assert c0.er_full_median == pytest.approx(er.median())
    recent = feat[(feat.creator_id == "C0") & (feat.posted_on >= as_of - pd.Timedelta(days=90))].er
    assert c0.er_recent_median == pytest.approx(recent.median())
    assert c0.er_full_median != c0.er_recent_median            # windows are genuinely different
    assert c0.sponsored_share == pytest.approx(3 / 12)
    assert c0.view_to_follower == pytest.approx(feat[feat.creator_id == "C0"].plays.median() / 1000)


def test_thin_recent_window_is_missing_not_zero_and_weights_renormalise():
    creators, posts, as_of = _synthetic()
    posts.loc[posts.creator_id == "C1", "posted_on"] = as_of - pd.Timedelta(days=400)   # nothing recent
    posts.loc[posts.creator_id == "C1", "posted_on"] -= pd.to_timedelta(np.arange(12), unit="D")
    feat = CA.post_features(posts, _ref())
    m = CA.creator_metrics(feat, creators, as_of)
    assert np.isnan(m.at["C1", "er_recent_median"]) and np.isnan(m.at["C1", "plays_recent_median"])
    res = CA.score_creators(m, _demo(creators))
    comp = res.components[(res.components.creator_id == "C1") & (res.components.component == "er_recent_window")].iloc[0]
    assert not comp.available and np.isnan(comp.component_score)
    # engagement score of C1 equals weighted mean of the REMAINING components, re-normalised
    c = res.components[(res.components.creator_id == "C1") & (res.components.dimension == "engagement_quality")
                       & res.components.available]
    expected = (c.component_score * c.effective_weight).sum() / c.effective_weight.sum()
    assert res.scores.at["C1", "engagement_quality"] == pytest.approx(expected)
    assert res.scores.at["C1", "coverage_engagement_quality"] < res.scores.at["C0", "coverage_engagement_quality"]


def test_missing_demographics_never_penalise_and_never_fabricate():
    creators, posts, as_of = _synthetic()
    feat = CA.post_features(posts, _ref())
    m = CA.creator_metrics(feat, creators, as_of)
    none = CA.score_creators(m, _demo(creators))
    proxy = m.parent_targeted_share * 100
    # without any demographics, audience fit == content proxy for everyone (no zero, no imputation, no penalty)
    assert np.allclose(none.scores.audience_fit, proxy)
    assert not none.scores.has_demographics.any()
    assert (none.scores.demographic_blend_weight == 0).all()
    # giving ONE creator demographics changes only that creator's audience fit / composite
    one = CA.score_creators(m, _demo(creators, {"C2": 0.4}))
    changed = ~np.isclose(one.scores.composite_score, none.scores.composite_score)
    assert changed.tolist() == [False, False, True, False]
    assert one.scores.at["C2", "audience_fit"] == pytest.approx(0.5 * proxy["C2"] + 0.5 * 40)
    # a creator whose demographics equal the proxy is scored identically to having none
    same = CA.score_creators(m, _demo(creators, {"C2": proxy["C2"] / 100}))
    assert same.scores.at["C2", "audience_fit"] == pytest.approx(proxy["C2"])
    # missing demographics lower coverage (visible) but not the score
    assert none.scores.at["C0", "coverage_audience_fit"] < one.scores.at["C2", "coverage_audience_fit"]
    # the demographic row in components is flagged unavailable, with NaN raw value for C0
    dm = none.components[(none.components.component == "demographic_match") & (none.components.creator_id == "C0")].iloc[0]
    assert not dm.available and np.isnan(dm.raw_value) and dm.effective_weight == 0


def test_composite_is_exact_weighted_sum_and_monotone():
    creators, posts, as_of = _synthetic()
    feat = CA.post_features(posts, _ref())
    m = CA.creator_metrics(feat, creators, as_of)
    s = CA.score_creators(m, _demo(creators)).scores
    exp = sum(s[d] * w for d, w in CA.DIMENSION_WEIGHTS.items())
    assert np.allclose(s.composite_score, exp)
    assert s[list(CA.DIMENSION_WEIGHTS)].min().min() >= 0 and s[list(CA.DIMENSION_WEIGHTS)].max().max() <= 100
    # raising one creator's median engagement can only raise (or keep) its engagement score
    m2 = m.copy()
    m2.loc["C0", "er_full_median"] = m.er_full_median.max() * 2
    s2 = CA.score_creators(m2, _demo(creators)).scores
    assert s2.at["C0", "engagement_quality"] >= s.at["C0", "engagement_quality"]
    assert s2.at["C0", "composite_score"] >= s.at["C0", "composite_score"]


def test_rank_is_deterministic_and_ties_stable():
    s = pd.DataFrame({"composite_score": [50.0, 70.0, 70.0, 10.0]}, index=list("abcd"))
    r = CA.rank(s)
    assert r.to_dict() == {"b": 1, "c": 2, "a": 3, "d": 4}


def test_bootstrap_is_seeded():
    creators, posts, as_of = _synthetic()
    feat = CA.post_features(posts, _ref())
    demo = _demo(creators)
    a = CA.bootstrap_ranks(feat, creators, demo, as_of, B=15, seed=3)
    b = CA.bootstrap_ranks(feat, creators, demo, as_of, B=15, seed=3)
    c = CA.bootstrap_ranks(feat, creators, demo, as_of, B=15, seed=4)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(c)
    assert ((a.p_top5 >= 0) & (a.p_top5 <= 1)).all()


# ------------------------------------------------------------------ real data
@pytest.fixture(scope="module")
def real():
    d = load_all()
    as_of = d["posts"].posted_on.max()
    feat = CA.post_features(d["posts"], CA.ad_reference(d["ads"]))
    m = CA.creator_metrics(feat, d["creators"], as_of)
    demo = CA.audience_detail(d["creators"], d["audience"])
    res = CA.score_creators(m, demo)
    conf = CA.confidence(m, res.scores)
    return dict(d=d, feat=feat, m=m, demo=demo, res=res, conf=conf)


def test_all_20_creators_scored(real):
    assert len(real["res"].scores) == 20 and real["res"].scores.composite_score.notna().all()
    assert real["m"].n_posts.sum() == 392


def test_exactly_three_creators_have_demographics_and_17_stay_empty(real):
    demo = real["demo"]
    assert sorted(demo.index[demo.has_demographics]) == ["CR-14", "CR-15", "CR-20"]
    assert demo.demo_match.notna().sum() == 3 and demo.demo_match.isna().sum() == 17
    assert demo.loc["CR-14", "platform_mismatch"] and not demo.loc["CR-15", "platform_mismatch"]
    assert demo.loc["CR-15", "india_share"] == pytest.approx(0.883)
    assert demo.loc["CR-20", "age_25_44_share"] == pytest.approx(0.444 + 0.135)


def test_missing_demographics_creators_equal_their_proxy_on_real_data(real):
    s, m = real["res"].scores, real["m"]
    no_demo = s.index[~s.has_demographics]
    assert len(no_demo) == 17
    assert np.allclose(s.loc[no_demo, "audience_fit"], m.loc[no_demo, "parent_targeted_share"] * 100)
    assert (s.loc[no_demo, "coverage_audience_fit"] <= 0.5 + 1e-9).all()
    assert (s.loc[s.has_demographics, "coverage_audience_fit"] > 0.5).all()


def test_window_metrics_present_and_distinct(real):
    m = real["m"]
    assert (m.er_full_median > 0).all()
    assert m.er_recent_median.notna().sum() >= 15
    assert m.loc["CR-09", "n_recent_posts"] == 4 and np.isnan(m.loc["CR-09", "er_recent_median"])   # thin -> not scored
    assert (m.er_recent_median.dropna() != m.er_full_median[m.er_recent_median.notna()]).any()
    assert (m.posts_per_30d_full > 0).all()


def test_composite_matches_contributions_on_real_data(real):
    s = real["res"].scores
    total = sum(s[d] * w for d, w in CA.DIMENSION_WEIGHTS.items())
    assert np.allclose(s.composite_score, total)
    assert s[list(CA.DIMENSION_WEIGHTS)].stack().between(0, 100).all()


def test_confidence_and_coverage_ranges(real):
    s, c = real["res"].scores, real["conf"]
    assert s.evidence_coverage.between(0, 1).all() and c.confidence_index.between(0, 1).all()
    assert set(c.confidence_level) <= {"Low", "Medium", "High"}
    assert c.loc["CR-18", "sufficiency_posts"] == pytest.approx(0.6)          # only 12 posts
    assert "no_demographics" in c.loc["CR-01", "flags"] and "no_demographics" not in c.loc["CR-15", "flags"]
    # no-demographic creators carry lower evidence coverage in the audience dimension only
    assert s.loc["CR-15", "evidence_coverage"] > s.loc["CR-01", "evidence_coverage"] - 0.05


def test_top5_and_explanations(real):
    s, comps, m, conf = real["res"].scores, real["res"].components, real["m"], real["conf"]
    top = CA.rank(s).sort_values().index[:5]
    assert len(set(top)) == 5
    for cid in top:
        e = CA.explain(cid, s, comps, m, conf)
        assert e["composite_score"] == pytest.approx(sum(e["weighted_contributions"].values()))
        assert "Evidence coverage" in e["explanation"] and "confidence" in e["explanation"]
        assert len(e["strongest_components"]) == 3


def test_sensitivity_includes_base_and_no_demographics_equals_base_for_non_demo_creators(real):
    sens = CA.sensitivity_ranks(real["m"], real["demo"])
    assert (sens.rank_base == CA.rank(real["res"].scores)).all()
    assert {"rank_no_demographics", "rank_full_history_only", "rank_equal_weights"} <= set(sens.columns)
    base = real["res"].scores.composite_score
    no_demo = sens.score_no_demographics
    nd = real["res"].scores.index[~real["res"].scores.has_demographics]
    assert np.allclose(base[nd], no_demo[nd])          # scores of non-demographic creators cannot depend on others' demographics


def test_crosswalk_lists_unmapped_values():
    ref = CA.ad_reference(load_all()["ads"])
    cw = CA.crosswalk_table(ref)
    assert (cw.note.str.contains("NO EQUIVALENT")).sum() >= 7
    assert cw.loc[cw.post_value == "voiceover_montage", "ad_share"].iloc[0] == pytest.approx(35 / 97, abs=0.02)


def test_completed_ad_analysis_outputs_untouched():
    manifest = ROOT / "reports" / "ad" / "json" / "run_manifest.json"
    if not manifest.exists():
        pytest.skip("ad manifest absent")
    mf = json.loads(manifest.read_text())
    for name, h in mf["outputs_sha256"].items():
        p = next((ROOT / "reports" / "ad").rglob(name))
        assert hashlib.sha256(p.read_bytes()).hexdigest() == h, name
