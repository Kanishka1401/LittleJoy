#!/usr/bin/env python
"""Run the advertising performance analysis. Outputs: reports/tables/ad, reports/json/ad, data/processed."""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cip import ad_analysis, stats  # noqa: E402
from cip.loaders import RAW_DIR      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=str(RAW_DIR))
    ap.add_argument("--out-dir", default=str(ROOT / "reports" / "ad"))
    ap.add_argument("--processed-dir", default=str(ROOT / "data" / "processed"))
    ap.add_argument("--B", type=int, default=stats.B_DEFAULT)
    ap.add_argument("--seed", type=int, default=stats.SEED)
    a = ap.parse_args()
    t = time.time()
    ad_analysis.run(a.raw_dir, a.out_dir, a.processed_dir, B=a.B, seed=a.seed)
    print(f"done in {time.time() - t:.1f}s -> {a.out_dir}")


if __name__ == "__main__":
    main()
