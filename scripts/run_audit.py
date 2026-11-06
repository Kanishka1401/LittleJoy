#!/usr/bin/env python
"""Load all datasets, run validation, write reports/tables/data_quality_report.csv.

Usage:  python scripts/run_audit.py [--raw-dir PATH] [--strict]
Exit code 1 if any ERROR finding (or any WARN with --strict).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cip.loaders import load_all, RAW_DIR  # noqa: E402
from cip.validate import validate_all      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=str(RAW_DIR))
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    data = load_all(Path(args.raw_dir))
    for k, df in data.items():
        print(f"{k:<9} {df.shape[0]:>4} rows x {df.shape[1]:>2} cols")

    report = validate_all(data)
    out = ROOT / "reports" / "tables" / "data_quality_report.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out, index=False)

    issues = report[report.severity != "INFO"]
    print(f"\n{(report.severity=='ERROR').sum()} ERROR | {(report.severity=='WARN').sum()} WARN | "
          f"{(report.severity=='INFO').sum()} INFO/OK   -> {out.relative_to(ROOT)}\n")
    for _, r in issues.iterrows():
        print(f"[{r.severity:<5}] {r.dataset:<9} {r.check:<45} n={r.n_affected:<4} {r.detail}")

    bad = (report.severity == "ERROR").any() or (args.strict and (report.severity == "WARN").any())
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
