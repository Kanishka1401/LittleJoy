# AI Creative Studio

Code: `src/cip/studio.py` (engine, validator, LLM path, export), `src/cip/studio_content.py` (templates, fact specs), `dashboard/views_studio.py` (page), `tests/test_studio.py`.
Batch run (no API key): `python scripts/run_creative_studio.py` -> `reports/studio/` (briefs as .md/.json, summary, restricted claims). The page is **AI Creative Studio** in the sidebar.

## What it produces per creator
Concept (with Creative DNA fit and real post/ad evidence IDs), three hooks (each tied to a real post's hook style), a 5-scene 30-45 s script (timeline + estimated speech time), visual directions, on-screen text, auto-captions and post caption, CTA, tone/delivery, and an avoid list.

| Creator | Product | Format |
|---|---|---|
| CR-03 ekamichildcare | Nutrimix | calm clinic label walk-through |
| CR-11 raja_choudhary04 | Nutrimix | family day-in-the-life vlog |
| CR-02 livesimply_withkripa | Proteinmix | multi-character kitchen skit |
| CR-05 sia_3vedi | Nutrimix | child-performer bargaining sketch (adult voiceover reads the label) |
| CR-01 drgarima_mehta | Proteinmix | doctor split-screen label check |

## Product truth
No product spec sheet exists in the files. The only product statements are Little Joys' own `claims_made` in `ads.csv`. Each fact has an ID (`N_SWEET`, `P_PROT`, ...), is matched by regex to the ads that mention the product and quoted **verbatim** with its ad IDs. They are *brand-stated*, not independently verified. Anything else (age band, serving, price, offer, link, brand handle, allergen statement) is a `[[CONFIRM: ...]]` placeholder. Claims in the ad files that look unsubstantiated (immunity, "boost", superlatives, multipliers, popularity, lab-test, growth, digestive, rating, behavioural outcome) are listed on the page and in `reports/studio/restricted_claims.csv` and are never used.

## Validator
Runs on generated, LLM-produced and hand-edited text: banned claim classes, competitor names, numbers/units not found in the verified facts, unresolved fact references, timeline outside 30-45 s, speech longer than the timeline. Placeholders are reported as info.

## Generation modes
- **Template (default, offline).** Each section has creator-specific variants; "Regenerate" advances that section's variant index only. Other sections and your edits are preserved.
- **LLM (optional).** If `ANTHROPIC_API_KEY` and the `anthropic` package exist, the page enables a toggle. The prompt contains only the verified facts and rules; output is parsed, shape-checked and claim-validated, and any failure falls back to the template.

## Limitations
Scripts are drafts: Hinglish lines need native-speaker review; creator profiles and post labels are AI-generated; the Creative DNA purchase lens is not scored, so nothing here predicts sales or ROAS. Doctor and child creators carry extra regulatory risk (endorsement, child advertising); get brand/legal sign-off. Tone and avoid sections are deterministic and edited by hand rather than regenerated.
