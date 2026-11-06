import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cip import ad_analysis, stats as S  # noqa: E402
from cip.clean import prepare_units      # noqa: E402
from cip.loaders import load_ads         # noqa: E402


@pytest.fixture(scope="module")
def units():
    u, dup, tokens = prepare_units(load_ads())
    return u, dup


def test_creative_table_collapses_duplicates_without_losing_outcomes(units):
    u, dup = units
    ad, cr = u["ad"], u["creative"]
    assert len(ad) == 100 and len(cr) == 97
    assert cr.creative_id.is_unique and cr.video_url.is_unique
    for c in ["spend_inr", "impressions", "purchases", "revenue_inr", "link_clicks"]:
        assert cr[c].sum() == ad[c].sum()
    assert (dup.labels_differing == "none").all() and len(dup) == 3
    assert cr.is_lj004.sum() == 1 and cr[cr.is_lj004].n_ads.iloc[0] == 1


def test_brand_contradiction_flag(units):
    u, _ = units
    assert u["creative"].brand_label_contradiction.sum() == 18


def test_bootstrap_is_seeded_and_preserves_strata():
    strata = np.array([0] * 5 + [1] * 7 + [2] * 4)
    a, b = S.make_boot(strata, B=50, seed=1), S.make_boot(strata, B=50, seed=1)
    assert (a.idx == b.idx).all()
    assert (a.counts.sum(axis=1) == len(strata)).all()
    for s in (0, 1, 2):
        assert (a.counts[:, strata == s].sum(axis=1) == (strata == s).sum()).all()


def test_bh_matches_known_values():
    q = S.bh_qvalues(pd.Series([0.01, 0.04, 0.03, 0.005]))
    assert q.round(4).tolist() == [0.02, 0.04, 0.04, 0.02]


def test_product_control_removes_simpsons_paradox():
    """Level is concentrated in a high-ROAS product but has ZERO effect inside each product."""
    rng = np.random.default_rng(0)
    rows = []
    for pf, base, p_level in (("A", 3.0, 0.8), ("B", 1.0, 0.1)):
        for _ in range(60):
            spend = 1000.0
            rows.append(dict(pf=pf, lvl=rng.random() < p_level, spend=spend,
                             rev=spend * base * rng.uniform(0.9, 1.1)))
    d = pd.DataFrame(rows)
    boot = S.make_boot(pd.factorize(d.pf)[0], B=500, seed=3)
    mask, num, den = d.lvl.to_numpy(), d.rev.to_numpy(), d.spend.to_numpy()
    raw = S.ratio_point(num, den, mask) - S.ratio_point(num, den, ~mask)
    ctrl = S.std_diff(num, den, mask, boot)
    assert raw > 1.0                    # naive comparison is badly confounded
    assert abs(ctrl["diff"]) < 0.15     # controlled comparison is ~0
    assert ctrl["lo"] < 0 < ctrl["hi"]


def test_median_is_robust_to_single_outlier():
    v = np.array([1.0, 1.1, 0.9, 1.0, 50.0])
    assert S.median_point(v, np.ones(5, bool)) == pytest.approx(1.0)


def _hashes(d: Path):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.rglob("*")) if p.is_file()}


def test_pipeline_is_bit_reproducible(tmp_path):
    ad_analysis.run(None or Path(__file__).resolve().parents[1] / "data" / "raw", tmp_path / "r1", tmp_path / "p1", B=100, seed=7)
    ad_analysis.run(Path(__file__).resolve().parents[1] / "data" / "raw", tmp_path / "r2", tmp_path / "p2", B=100, seed=7)
    assert _hashes(tmp_path / "r1") == _hashes(tmp_path / "r2")
    assert _hashes(tmp_path / "p1") == _hashes(tmp_path / "p2")


def test_outputs_carry_provenance_and_sample_sizes(tmp_path):
    root = Path(__file__).resolve().parents[1]
    res = ad_analysis.run(root / "data" / "raw", tmp_path / "r", tmp_path / "p", B=100, seed=7)
    eff = res["eff"]
    assert set(eff.source_type) <= {"ai_label", "platform_reported"}
    assert eff.n_level.notna().all() and eff.n_rest.notna().all()
    brand = eff[eff.attribute.isin(["brand_said_aloud", "brand_first_said"])]
    assert brand.notes.str.contains("contradictory_brand_labels").all()
    stab = res["stab"]
    assert not stab[stab.attribute.isin(["brand_said_aloud", "brand_first_said"])].status.eq("stable_candidate").any()
