"""Load raw CSVs with explicit parsing. Raw files are never modified."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from .schema import SCHEMAS

DEFAULT_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
RAW_DIR = Path(os.environ.get("CIP_RAW_DIR", DEFAULT_RAW))

FILES = {
    "ads": "ads.csv",
    "creators": "creators.csv",
    "posts": "creator_posts.csv",
    "audience": "creator_audience.csv",
}


def _read(name: str, raw_dir: Path) -> pd.DataFrame:
    path = Path(raw_dir) / FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"{path} not found (set CIP_RAW_DIR to override)")
    df = pd.read_csv(path, encoding="utf-8")
    for col in SCHEMAS[name].get("dates", []):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def split_multilabel(series: pd.Series, sep: str = ";") -> pd.Series:
    """'a; b' -> ['a', 'b'] (NaN -> []). Use .explode() for per-label analysis."""
    return series.fillna("").apply(
        lambda s: [t.strip() for t in str(s).split(sep) if t.strip()]
    )


def parse_json_cell(value):
    if pd.isna(value):
        return {}
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


def load_ads(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    return _read("ads", raw_dir)


def load_creators(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    df = _read("creators", raw_dir)
    parsed = df["audience_read"].apply(parse_json_cell)
    df["audience_comment_evidence"] = parsed.apply(lambda d: d.get("comment_evidence"))
    return df


def load_posts(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    return _read("posts", raw_dir)


def load_audience(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    return _read("audience", raw_dir)


def load_all(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    return {
        "ads": load_ads(raw_dir),
        "creators": load_creators(raw_dir),
        "posts": load_posts(raw_dir),
        "audience": load_audience(raw_dir),
    }
