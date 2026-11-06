import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cip import dna  # noqa: E402


@pytest.fixture(scope="module")
def world():
    creatives = pd.read_csv(ROOT / "data/processed/creatives.csv")
    stab = dna.load_stability(ROOT / "reports/ad/tables/attribute_effects_stability.csv")
    ads = dna.ad_units(creatives)
    pat = dna.build_pattern_table(stab, ads)
    raw = pd.read_csv(ROOT / "data/raw/creator_posts.csv", parse_dates=["posted_on"])
    posts = dna.post_unit(raw)
    align = dna.alignment_table(posts, pat)
    return dict(stab=stab, ads=ads, pat=pat, posts=posts, raw=raw, align=align, scores=dna.score_creators(align, pat),
                creators=pd.read_csv(ROOT / "data/raw/creators.csv"))


def test_registry_is_consistent():
    ids = [f.id for f in dna.FEATURES]
    assert len(ids) == len(set(ids))
    assert {f.quality for f in dna.FEATURES} <= {"direct", "approximate", "weak", "none"}
    for f in dna.FEATURES:
        if f.quality in ("weak", "none") or f.post_flag is None:
            assert f.quality in ("weak", "none") and f.post_flag is None or f.quality in ("weak", "none")
        assert f.rationale


def test_weak_and_unmapped_features_never_scored(world):
    pat = world["pat"]
    assert not pat[pat.mapping_quality.isin(["weak", "none"])].scored.any()
    assert (pat[pat.scored].ad_status == "stable_candidate").all()
    assert pat[pat.scored].mapping_quality.isin(dna.SCORABLE_QUALITY).all()
    # directional-only evidence is never scored, even if mapping is direct (voiceover, skit-on-purchase)
    assert not pat[(pat.feature_id == "voiceover_montage")].scored.any()
    assert not pat[(pat.feature_id == "skit") & (pat.stage == "purchase")].scored.any()


def test_effects_are_copied_from_existing_ad_analysis_not_recomputed(world):
    stab, pat = world["stab"], world["pat"]
    r = pat[(pat.feature_id == "skit") & (pat.stage == "attention")].iloc[0]
    s = stab[(stab.metric == "hook_rate") & (stab.attribute == "ad_format") & (stab.level == "skit")].iloc[0]
    assert r.effect == pytest.approx(s.ctrl_diff * 100) and r.ci_lo == pytest.approx(s.ctrl_lo * 100)
    assert r.effect_excl_LJ004 == pytest.approx(s.diff__creative_excl_LJ004 * 100)


def test_inverted_row_flips_sign_for_feature_present(world):
    stab, pat = world["stab"], world["pat"]
    s = stab[(stab.metric == "cvr_click") & (stab.attribute == "humour") & (stab.level == "none")].iloc[0]
    r = pat[(pat.feature_id == "humour") & (pat.stage == "purchase")].iloc[0]
    assert s.ctrl_diff > 0 and r.effect == pytest.approx(-s.ctrl_diff * 100) and r.direction == "−"
    assert r.ci_lo < r.ci_hi


def test_lj004_sensitivity_is_reported_for_every_pattern(world):
    pat = world["pat"]
    for col in ["effect_excl_LJ004", "ci_lo_excl_LJ004", "ci_hi_excl_LJ004", "survives_without_LJ004", "lj004_has_feature"]:
        assert pat[col].notna().all()
    # the one purchase-stage signal that shrinks without LJ-004 is flagged consistently
    g = pat[(pat.feature_id == "growth_claim") & (pat.metric == "roas")].iloc[0]
    assert abs(g.effect_excl_LJ004) < abs(g.effect)


def test_success_cohort_excludes_lj004_and_low_evidence(world):
    ads = world["ads"]
    co = dna.success_cohort(ads)
    d = ads[~ads.is_lj004 & ~ads.low_evidence]
    assert co.n_top.iloc[0] + co.n_rest.iloc[0] == len(d)
    assert co.with_feature_top.le(co.n_top).all() and co.prevalence_top.between(0, 1).all()
    gc = co[co.feature_id == "growth_claim"].iloc[0]
    assert gc.prevalence_top < gc.prevalence_rest       # matches the existing stable purchase-stage signal


def test_alignment_direction_and_missing_handling():
    pat = pd.DataFrame([dict(feature_id="skit", stage="attention", metric="hook_rate", direction="+", scored=True, ad_status="stable_candidate", effect=7.5),
                        dict(feature_id="explainer_to_camera", stage="attention", metric="hook_rate", direction="−", scored=True, ad_status="stable_candidate", effect=-8.0)])
    posts = pd.DataFrame({"creator_id": ["A"] * 4 + ["B"] * 4, "f_skit": [1, 1, 0, 0, np.nan, np.nan, np.nan, np.nan],
                          "f_explainer_to_camera": [1, 1, 1, 0, 0, 0, 0, 0]})
    al = dna.alignment_table(posts, pat).set_index(["creator_id", "feature_id"])
    assert al.at[("A", "skit"), "alignment"] == pytest.approx(0.5)                      # + : prevalence
    assert al.at[("A", "explainer_to_camera"), "alignment"] == pytest.approx(0.25)      # − : 1 - prevalence
    assert np.isnan(al.at[("B", "skit"), "prevalence"]) and np.isnan(al.at[("B", "skit"), "alignment"])   # missing != 0


def test_lens_scored_only_with_enough_eligible_features_and_posts(world):
    sc = world["scores"]
    assert sc.attention_status.eq("scored").all() and sc.attention_alignment.between(0, 100).all()
    assert sc.purchase_alignment.isna().all()                       # only 2 eligible purchase features (< 3)
    assert sc.purchase_status.str.contains("not scored").all()
    # a creator with too few labelled posts is not scored
    al = world["align"].copy()
    al.loc[al.creator_id == "CR-18", "n_posts_labelled"] = dna.MIN_LABELLED_POSTS - 1
    assert np.isnan(dna.score_creators(al, world["pat"]).loc["CR-18", "attention_alignment"])


def test_scores_do_not_depend_on_organic_engagement(world):
    raw = world["raw"].copy()
    rng = np.random.default_rng(0)
    for c in ["plays", "likes", "comments", "reshares"]:
        raw[c] = rng.permutation(raw[c].values)
    posts2 = dna.post_unit(raw)
    sc2 = dna.score_creators(dna.alignment_table(posts2, world["pat"]), world["pat"])
    pd.testing.assert_frame_equal(sc2, world["scores"])


def test_every_supporting_id_exists_in_source_data(world):
    prof = json.loads((ROOT / "reports/dna/json/creator_dna_profiles.json").read_text())
    ads, posts = world["ads"], world["posts"]
    short = json.loads((ROOT / "reports/dna/json/config.json").read_text())["shortlist"]
    rank = pd.read_csv(ROOT / "reports/creator/tables/creator_ranking.csv").sort_values("rank")
    assert short == rank.creator_id.head(5).tolist()
    for cid in short:
        p = prof[cid]
        assert p["shortlisted"] and {"natural_style", "strengths", "gaps", "supporting_ids", "purchase_context", "explanation"} <= set(p)
        for fid, ids in p["supporting_ids"].items():
            assert set(ids["ad_creative_ids"]) <= set(ads.creative_id)
            sub = ads[ads.creative_id.isin(ids["ad_creative_ids"])]
            assert (sub[f"f_{fid}"] == 1).all() and not sub.is_lj004.any()               # each listed ad truly carries the feature
            mine = posts[(posts.creator_id == cid) & posts.post_id.isin(ids["post_ids"])]
            assert len(mine) == len(ids["post_ids"]) and (mine[f"f_{fid}"] == 1).all()    # each listed post belongs to the creator and matches


def test_post_id_extraction():
    assert dna.post_id("https://www.instagram.com/p/DdjMh_KTKkR/") == "DdjMh_KTKkR"


def test_existing_ad_and_creator_outputs_untouched():
    for rel in ["reports/ad", "reports/creator"]:
        mf = json.loads((ROOT / rel / "json" / "run_manifest.json").read_text())
        for name, h in mf["outputs_sha256"].items():
            p = next((ROOT / rel).rglob(name))
            assert hashlib.sha256(p.read_bytes()).hexdigest() == h, name
