import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cip.loaders import load_all, split_multilabel  # noqa: E402
from cip.metrics import add_ad_metrics, aggregate_roas, safe_div  # noqa: E402
from cip.validate import validate_all  # noqa: E402


@pytest.fixture(scope="module")
def data():
    return load_all()


def test_shapes(data):
    assert data["ads"].shape == (100, 56)
    assert data["posts"].shape == (392, 32)
    assert data["audience"].shape == (3, 10)
    assert data["creators"].shape[0] == 20


def test_no_validation_errors(data):
    rep = validate_all(data)
    assert not (rep.severity == "ERROR").any(), rep[rep.severity == "ERROR"]


def test_keys_unique_and_linked(data):
    assert data["ads"].ad_id.is_unique
    assert data["posts"].post_url.is_unique
    assert set(data["posts"].creator_id) <= set(data["creators"].creator_id)
    assert set(data["audience"].creator_id) <= set(data["creators"].creator_id)


def test_safe_div_handles_zero():
    out = safe_div(pd.Series([1, 2]), pd.Series([0, 4]))
    assert np.isnan(out.iloc[0]) and out.iloc[1] == 0.5


def test_roas_is_ratio_of_sums(data):
    ads = add_ad_metrics(data["ads"])
    g = aggregate_roas(ads, "product_form")
    total = g.revenue_inr.sum() / g.spend_inr.sum()
    assert total == pytest.approx(ads.revenue_inr.sum() / ads.spend_inr.sum())


def test_split_multilabel():
    s = pd.Series(["a; b", None, "c"])
    assert split_multilabel(s).tolist() == [["a", "b"], [], ["c"]]
