#!/usr/bin/env python
"""Run the Creator Analysis Engine. Outputs: reports/creator/{tables,json}. Raw data and reports/ad are never touched."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np   # noqa: E402
import pandas as pd  # noqa: E402

from cip import creator_analysis as CA          # noqa: E402
from cip.loaders import RAW_DIR, load_all      # noqa: E402

TOP_N = 5


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(raw_dir, out_dir, B=CA.B_DEFAULT, seed=CA.SEED):
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    tdir, jdir = out_dir / "tables", out_dir / "json"
    tdir.mkdir(parents=True, exist_ok=True)
    jdir.mkdir(parents=True, exist_ok=True)

    d = load_all(raw_dir)
    creators, posts, audience, ads = d["creators"], d["posts"], d["audience"], d["ads"]
    as_of = posts.posted_on.max()
    ref = CA.ad_reference(ads)
    feat = CA.post_features(posts, ref)
    metrics = CA.creator_metrics(feat, creators, as_of)
    demo = CA.audience_detail(creators, audience)
    res = CA.score_creators(metrics, demo)
    boot = CA.bootstrap_ranks(feat, creators, demo, as_of, B=B, seed=seed)
    conf = CA.confidence(metrics, res.scores, boot)
    sens = CA.sensitivity_ranks(metrics, demo)

    scores = res.scores.join(conf).join(boot).join(sens[["rank_base", "rank_no_demographics",
                                                          "rank_full_history_only", "rank_equal_weights",
                                                          "rank_min", "rank_max"]])
    scores["rank"] = CA.rank(scores)
    scores.insert(0, "handle", creators.set_index("creator_id").handle)
    for dim, w in CA.DIMENSION_WEIGHTS.items():
        scores[f"contrib_{dim}"] = scores[dim] * w
    scores = scores.sort_values("rank")
    scores.index.name = "creator_id"

    top = scores.index[:TOP_N].tolist()
    expl = [CA.explain(c, res.scores, res.components, metrics, conf, boot) for c in top]
    for e, c in zip(expl, top):
        e["rank"] = int(scores.at[c, "rank"])
        e["handle"] = scores.at[c, "handle"]

    # ---- tables
    def r4(df):
        num = df.select_dtypes("number").columns
        return df.assign(**{c: df[c].round(4) for c in num})
    r4(scores.reset_index()).to_csv(tdir / "creator_ranking.csv", index=False)
    r4(metrics.reset_index()).to_csv(tdir / "creator_metrics.csv", index=False)
    r4(res.components).to_csv(tdir / "component_scores.csv", index=False)
    cov_cols = [c for c in res.scores.columns if c.startswith("coverage_")] + ["evidence_coverage"]
    r4(res.scores[cov_cols].join(metrics[["transcript_coverage"]]).join(conf).reset_index()
       ).to_csv(tdir / "evidence_coverage_confidence.csv", index=False)
    r4(demo.reset_index()).to_csv(tdir / "audience_demographics_parsed.csv", index=False)
    CA.crosswalk_table(ref).round(4).to_csv(tdir / "ad_post_crosswalk.csv", index=False)
    r4(sens.reset_index().rename(columns={"index": "creator_id"})).to_csv(tdir / "sensitivity_rankings.csv", index=False)
    window = metrics[["n_posts", "first_post", "last_post", "history_span_days", "posts_per_30d_full",
                      "n_recent_posts", "posts_per_30d_recent", "n_recent_video_with_plays",
                      "er_full_median", "er_recent_median", "er_recent_vs_full",
                      "plays_full_median", "plays_recent_median"]]
    r4(window.reset_index()).to_csv(tdir / "window_performance.csv", index=False)
    r4(pd.DataFrame(expl)[["rank", "creator_id", "handle", "composite_score", "evidence_coverage", "confidence",
                           "flags", "explanation"]]).to_csv(tdir / "top5_explanations.csv", index=False)

    # ---- json
    (jdir / "top5.json").write_text(json.dumps(expl, indent=2, default=float, sort_keys=True))
    (jdir / "weights_and_config.json").write_text(json.dumps({
        "dimension_weights": CA.DIMENSION_WEIGHTS,
        "components": {k: [dict(name=n, metric=m, transform=t, weight=w) for n, m, t, w in v]
                       for k, v in CA.COMPONENTS.items()},
        "recent_days": CA.RECENT_DAYS, "min_recent_videos": CA.MIN_RECENT_VIDEOS,
        "min_sponsored_videos": CA.MIN_SPONSORED_VIDEOS, "ad_fit_saturation": CA.AD_FIT_SATURATION,
        "sponsor_saturation": CA.SPONSOR_SATURATION, "demo_blend": CA.DEMO_BLEND,
        "demo_blend_platform_mismatch": CA.DEMO_BLEND_PLATFORM_MISMATCH,
        "as_of": str(as_of.date()), "bootstrap_B": B, "seed": seed}, indent=2, sort_keys=True))
    outputs = sorted(p for p in list(tdir.glob("*.csv")) + list(jdir.glob("*.json")) if p.name != "run_manifest.json")
    (jdir / "run_manifest.json").write_text(json.dumps({
        "seed": seed, "bootstrap_B": B, "as_of": str(as_of.date()),
        "numpy": np.__version__, "pandas": pd.__version__,
        "inputs_sha256": {k: sha(raw_dir / f) for k, f in
                          dict(creators="creators.csv", posts="creator_posts.csv", audience="creator_audience.csv",
                               ads="ads.csv").items()},
        "outputs_sha256": {p.name: sha(p) for p in outputs}}, indent=2, sort_keys=True))
    return scores, expl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=str(RAW_DIR))
    ap.add_argument("--out-dir", default=str(ROOT / "reports" / "creator"))
    ap.add_argument("--B", type=int, default=CA.B_DEFAULT)
    ap.add_argument("--seed", type=int, default=CA.SEED)
    a = ap.parse_args()
    t = time.time()
    scores, expl = run(a.raw_dir, a.out_dir, a.B, a.seed)
    pd.set_option("display.width", 250)
    print(scores[["handle", "composite_score", "content_relevance", "engagement_quality", "creative_compatibility",
                  "authenticity", "audience_fit", "evidence_coverage", "confidence_level", "p_top5"]].round(2).to_string())
    print(f"done in {time.time() - t:.1f}s -> {a.out_dir}")


if __name__ == "__main__":
    main()
