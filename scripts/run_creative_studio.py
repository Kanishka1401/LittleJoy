#!/usr/bin/env python
"""Generate template-based briefs for the five shortlisted creators -> reports/studio/. Needs no API key.
Reads (never modifies) reports/dna and raw data."""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cip import studio as S  # noqa: E402


def main():
    out = ROOT / "reports" / "studio"
    (out / "briefs").mkdir(parents=True, exist_ok=True)
    st = S.Studio.load(ROOT)
    rows = []
    for cid in S.SHORTLIST:
        b = st.new_brief(cid)
        f = S.validate_brief(b, st.facts)
        (out / "briefs" / f"{cid}.md").write_text(S.to_markdown(b, f))
        (out / "briefs" / f"{cid}.json").write_text(S.to_json(b, f))
        rows.append(dict(creator_id=cid, handle=b["handle"], product=b["product"], archetype=b["concept"]["archetype"],
                         total_s=b["timing"]["total_s"], est_speech_s=b["timing"]["est_speech_s"],
                         claim_errors=sum(x.severity == "error" for x in f), placeholders=len(b["placeholders"]),
                         facts_used=";".join(b["facts_used"])))
    with open(out / "summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    S.restricted_claims(st.ads).to_csv(out / "restricted_claims.csv", index=False)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
