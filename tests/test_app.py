import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["Home", "Overview", "Creator shortlist", "Creator profiles", "Ad intelligence", "Creative DNA", "Campaign Studio", "Methodology"]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exceptions(page):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at.radio(key="nav").set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]


def test_reweight_matches_engine_composite_at_default_weights():
    from dashboard import data as D
    r = D.creator_outputs()["ranking"].set_index("creator_id")
    rw = D.reweight(r, dict(D.CA.DIMENSION_WEIGHTS))
    assert (abs(rw.custom_score - r.composite_score.reindex(rw.index)) < 0.01).all()
    assert (rw.rank_change == 0).all()
