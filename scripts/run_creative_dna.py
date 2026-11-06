#!/usr/bin/env python
"""Creative DNA Matching. Reads existing ad + creator outputs; writes reports/dna/{tables,json}. Never touches reports/ad or reports/creator."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from cip import dna  # noqa: E402
from cip.loaders import RAW_DIR  # noqa: E402

TOP_N = 5


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out_dir=ROOT / "reports" / "dna"):
    out_dir = Path(out_dir)
    t, j = out_dir / "tables", out_dir / "json"
    t.mkdir(parents=True, exist_ok=True)
    j.mkdir(parents=True, exist_ok=True)
    creatives = pd.read_csv(ROOT / "data" / "processed" / "creatives.csv")
    stab = dna.load_stability(ROOT / "reports" / "ad" / "tables" / "attribute_effects_stability.csv")
    ads = dna.ad_units(creatives)
    patterns = dna.build_pattern_table(stab, ads)
    cohort = dna.success_cohort(ads)
    ad_ev = dna.ad_evidence(ads)
    posts = dna.post_unit(pd.read_csv(RAW_DIR / "creator_posts.csv", parse_dates=["posted_on"]))
    creators = pd.read_csv(RAW_DIR / "creators.csv")
    rank = pd.read_csv(ROOT / "reports" / "creator" / "tables" / "creator_ranking.csv").set_index("creator_id")
    align = dna.alignment_table(posts, patterns)
    scores = dna.score_creators(align, patterns)
    shortlist = rank.sort_values("rank").index[:TOP_N].tolist()
    profiles = {cid: dna.build_profile(cid, posts, align, scores, patterns, ad_ev, creators) for cid in creators.creator_id}
    for cid, p in profiles.items():
        p["explanation"] = dna.explain_profile(p)
        p["shortlisted"] = cid in shortlist
        p["engine_rank"] = int(rank.at[cid, "rank"])

    mapping = pd.DataFrame([dict(feature_id=f.id, feature=f.label, ad_definition=f.ad_definition, post_definition=f.post_definition,
                                 mapping_quality=f.quality, rationale=f.rationale, caveat=f.caveat, post_side_evidence_type=f.post_evidence if f.post_flag else "n/a",
                                 ad_side_evidence_type="ad_ai_label", used_in_score=f.quality in dna.SCORABLE_QUALITY and f.post_flag is not None)
                            for f in dna.FEATURES])
    sc = scores.join(rank[["rank", "handle", "composite_score"]].rename(columns={"rank": "engine_rank", "composite_score": "engine_composite"}))
    sc["shortlisted"] = sc.index.isin(shortlist)
    ev_posts = []
    for cid, pr in profiles.items():
        g = posts[posts.creator_id == cid]
        for f in dna.FEATURES:
            if f.post_flag is None:
                continue
            m = g[g[f"f_{f.id}"] == 1]
            for r in m.itertuples():
                ev_posts.append(dict(creator_id=cid, feature_id=f.id, post_id=r.post_id, post_url=r.post_url, posted_on=r.posted_on.date(),
                                     post_type=r.type, content_form=r.content_form, content_type=r.content_type, evidence_type=f.post_evidence))
    unm = dna.unmapped_stable_signals(stab, patterns)

    rd = lambda df: df.round(4)  # noqa: E731
    rd(mapping).to_csv(t / "attribute_mapping.csv", index=False)
    rd(patterns).to_csv(t / "ad_success_patterns.csv", index=False)
    rd(unm).to_csv(t / "stable_signals_mapping_status.csv", index=False)
    rd(cohort).to_csv(t / "success_cohort_prevalence.csv", index=False)
    rd(sc.reset_index()).to_csv(t / "creator_dna_scores.csv", index=False)
    rd(align).to_csv(t / "creator_feature_alignment.csv", index=False)
    pd.DataFrame(ev_posts).to_csv(t / "evidence_posts.csv", index=False)
    rd(ad_ev).to_csv(t / "evidence_ads.csv", index=False)
    (j / "creator_dna_profiles.json").write_text(json.dumps(profiles, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o), sort_keys=True))
    (j / "config.json").write_text(json.dumps(dict(
        scorable_quality=sorted(dna.SCORABLE_QUALITY), min_scored_features=dna.MIN_SCORED_FEATURES, min_labelled_posts=dna.MIN_LABELLED_POSTS,
        strength_alignment=dna.STRENGTH_ALIGN, gap_alignment=dna.GAP_ALIGN, success_cohort_quantile=dna.TOP_QUANTILE, shortlist=shortlist,
        no_equivalent_fields=dna.NO_EQUIVALENT_FIELDS,
        provenance_legend={"ad_platform_metric": "reported by ad platform", "ad_ai_label": "model-labelled ad attribute", "post_ai_label": "model-labelled post attribute",
                           "post_platform_field": "scraped (URL/date/type)", "rule_derived": "our keyword/regex rule over AI-labelled text", "assumption": "judgement call, not data"},
        organic_engagement_used=False), indent=2))
    outputs = sorted(p for p in list(t.glob("*.csv")) + list(j.glob("*.json")) if p.name != "run_manifest.json")
    (j / "run_manifest.json").write_text(json.dumps({"inputs_sha256": {k: sha(v) for k, v in {
        "creatives": ROOT / "data/processed/creatives.csv", "stability": ROOT / "reports/ad/tables/attribute_effects_stability.csv",
        "posts": RAW_DIR / "creator_posts.csv", "creators": RAW_DIR / "creators.csv", "ranking": ROOT / "reports/creator/tables/creator_ranking.csv"}.items()},
        "outputs_sha256": {p.name: sha(p) for p in outputs}}, indent=2, sort_keys=True))
    return patterns, cohort, sc, profiles


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(ROOT / "reports" / "dna"))
    a = ap.parse_args()
    patterns, cohort, sc, profiles = run(a.out_dir)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(patterns[["feature_id", "stage", "direction", "effect", "ci_lo", "ci_hi", "effect_excl_LJ004", "survives_without_LJ004", "lj004_has_feature", "mapping_quality", "scored", "reason_not_scored"]].round(2).to_string())
    print(cohort[["feature_id", "n_top", "n_rest", "prevalence_top", "prevalence_rest", "diff", "fisher_p_exploratory", "lj004_has_feature"]].round(2).to_string())
    print(sc[["handle", "engine_rank", "attention_alignment", "attention_alignment_effect_weighted", "attention_n_features", "purchase_status"]].round(1).sort_values("engine_rank").to_string())
