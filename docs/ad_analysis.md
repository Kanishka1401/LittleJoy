# Ad Performance Analysis (Phase 2–3) – Methods, Results, Output Dictionary

Reproduce: `python scripts/run_ad_analysis.py` (≈19 s). Seed 20261104, 2,000 bootstrap resamples. Re-running produces byte-identical files (verified; hashes in `reports/ad/json/run_manifest.json`). Creators are **not** selected or scored anywhere in this phase.

## 1. How the ten requirements are implemented

| # | Requirement | Implementation | Where to see it |
|---|---|---|---|
| 1 | Don't double-count duplicate creatives | `clean.build_creative_table` collapses ads sharing a `video_url` (counts summed; labels verified identical for all 3 pairs). Every analysis runs on **creative (97, primary)** and **ad (100, comparison)** | `variants.json`, `label_quality.csv` (check `duplicate_video_label_equality`) |
| 2 | LJ-004 sensitivity | Every analysis has an `…_excl_LJ004` variant; "stable" status *requires* the effect to survive without it | `baseline_by_variant.csv`, `concentration_leave_one_out.csv`, `diff__creative_excl_LJ004` columns |
| 3 | Control for `product_form` | Attribute effects are **within-product_form** (level vs rest inside each of the 3 forms, weighted by denominator, bootstrap stratified by form). `raw_diff` is shown next to `ctrl_diff` so the confounding is visible | `attribute_effects_*.csv`; unit test `test_product_control_removes_simpsons_paradox` |
| 4 | Platform vs AI labels | Outcomes are platform-reported only; all creative attributes are predictors tagged `source_type=ai_label` | `column_provenance.csv/json`, `source_type` column everywhere |
| 5 | Contradictory brand labels | 18 creatives flagged; `brand_*` attributes carry a `contradictory_brand_labels` note, are re-run on the consistent subset (79 creatives), and can never reach `stable_candidate` | `label_quality.csv`, variant `creative_brand_consistent` |
| 6 | Post observation windows | **Not part of this phase** (creator side). Planned next with the audit's per-creator window finding | — |
| 7 | Robust statistics | Ratio-of-sums for aggregates, medians per unit, Spearman rank correlations, percentile bootstrap; no mean-of-ratios | `baseline_*`, `*_median_*` columns |
| 8 | Audience data for 3 creators only | **Not part of this phase**; will be enforced as explicit nulls for the other 17 | — |
| 9 | Documented ad↔post mapping first | **Not part of this phase**; will be a standalone reviewed table before any compatibility score | — |
| 10 | n and uncertainty | `n_units`/`n_level`/`n_rest` and 95% bootstrap CIs on every estimate; low-n and not-estimable flags in `notes` | all tables |

## 2. Methods

- **Units / variants** (`variants.json`): `creative_all` (97, primary), `creative_excl_LJ004` (96), `creative_min_evidence` (85; spend ≥ ₹5,000 and purchases ≥ 10), `ad_all` (100), `ad_excl_LJ004` (99), `creative_brand_consistent` (79; brand attributes only).
- **Metrics:** ROAS, CPA, CVR (purchases/link clicks), AOV, hook rate (3s views/impressions), hold rate, link CTR, click→ATC, ATC→purchase, CPM. All group values are ratio-of-sums.
- **Controlled effect (`ctrl_diff`):** within each product_form with ≥3 units in both the level and the comparison group, compute ratio(level) − ratio(rest); average across forms weighted by that form's denominator. Bootstrap resamples units *within* forms. `strata_used` shows how many forms contributed.
- **Multiple testing:** 147 unique level-vs-rest splits per metric. Identical or mirror-image levels (e.g. `child_on_screen=none` ≡ `child_age=none` ≡ `child_present=no`; yes/no pairs) count as one test (`duplicate_of`). Benjamini–Hochberg q-values are computed over unique tests per variant × metric.
- **Statuses** (`attribute_effects_stability.csv`): `stable_candidate` = CI excludes 0, q < 0.10, n_level ≥ 10, ≥ 2 forms, same sign in all four other variants, and CI still excludes 0 without LJ-004. Other values: `directional_only`, `unstable_across_variants`, `no_clear_effect`, `not_estimable`, `caution_brand_labels`. "Stable" means *survived these checks*, not *validated*.

## 3. Results (all numbers from `reports/ad/`)

**Baseline (creative level).** 97 creatives, ₹7.26M spend, ₹10.87M revenue, 16,856 purchases. Blended ROAS 1.50 (95% CI 0.97–2.20). Median per-creative ROAS 1.13 (0.94–1.29). The ad-level result is the same (1.50, 0.97–2.23).

**LJ-004 dominates the aggregate.** It is 30.3% of revenue on 9.1% of spend. Top 5 = 51.1% of revenue; Gini 0.73; the revenue is equivalent to ~9 equally sized units. Without it: ROAS 1.15 (0.92–1.39), CPA ₹551 vs ₹431. The median ROAS barely moves (1.13 → 1.11), so the typical creative is near break-even; the blended figure is carried by one ad.

**Product form.** Blended ROAS: milk-mix powder 1.88 (0.96–2.88), gummies 0.99 (0.78–1.16), other 1.01 (0.74–1.53). The gummies − milk-mix gap is −0.89 (−1.91 to 0.04) and shrinks to −0.30 (−0.75 to 0.16) without LJ-004. Median per-creative ROAS is similar across forms (1.23 / 0.93 / 1.13). Most of the apparent milk-mix advantage is LJ-004.

**Funnel relationships (within product form, Spearman ρ, creative level).** Hook rate vs ROAS: −0.18 (−0.39 to 0.03). Hook rate vs CVR: −0.21 (−0.38 to −0.00). Link CTR vs ROAS: +0.41 (0.21–0.55). CVR vs ROAS: +0.80 (partly mechanical). Attention (3-second views) does not track purchase value here.

**Creative attributes, controlled for product form** (`hypothesis_results.csv`, `key_signals.json`):
- *Attention only (hook rate):* child in first 3 s = yes +8.4 pts (5.0–10.8); storytelling +6.9; skit +7.5; situational humour +9.7; explainer-to-camera −8.3; product-feature demos −7.9; competitor-contrast persuasion −7.5. 19 stable-candidate hook-rate splits, but they describe overlapping sets of ads, so they are not 19 independent findings.
- *Same child-in-first-3s attribute on purchase metrics:* CVR +0.4 pts (−0.9 to 1.5), ROAS +0.46 (−0.31 to 1.22). No clear effect.
- *Purchase conversion (4 stable candidates):* "kids overall growth" narrative −2.4 pts CVR (−3.5 to −0.9); "occasional language borrowing" −2.4 pts; no humour +2.0 pts; parent/caregiver presenter −1.9 pts (q = 0.097, borderline).
- *ROAS (1 stable candidate):* "kids overall growth" narrative −1.48 (−2.30 to −0.43), **but −0.75 (−1.08 to −0.30) without LJ-004**: the direction survives, the size halves. The label is also unevenly spread across forms (31 of 50 milk-mix, 14 of 22 gummies, 2 of 25 other).
- *No clear effect on CVR/ROAS:* buy-now CTA, UGC vs semi-pro vs studio, language group, kitchen/indoor setting, demo types, hook driver, duration bins (UGC, language and demo effects have wide intervals; absence of evidence is not evidence of no effect).
- *Brand-mention attributes:* not interpreted (contradictory labels). Subset results are in the effects file for transparency.

## 4. Limitations specific to these results
- Observational; no randomisation; spend and run time were not assigned at random.
- All creative attributes are unvalidated AI labels; measurement error generally biases effects toward zero and is unquantified.
- 97 creatives, 3 product forms (one small); most level-vs-rest cells have 5–50 units. Bootstrap p-values floor at ≈0.0005 and are approximate with small groups.
- Several attributes are nested within product form (e.g. a level absent from one form is estimated from the others only: see `strata_used`).
- `revenue_inr`/`purchases` attribution rules are unknown (audit open question 1).

## 5. Output dictionary (`reports/ad/`)

| File | Content |
|---|---|
| `tables/baseline_by_variant.csv`, `json/baseline_summary.json` | Totals, ratio-of-sums and per-unit medians with 95% CIs, per variant |
| `tables/product_form_performance.csv` | Same metrics by product form × variant |
| `tables/product_form_roas_contrasts.csv` | Pairwise ROAS differences between forms with CIs |
| `tables/funnel_by_product_form.csv` | Stage rates by product form × variant |
| `tables/concentration*.csv` | Top-k shares, Gini, Lorenz points, leave-one-out ROAS |
| `tables/attribute_effects_all_variants.csv` | Every level-vs-rest estimate, every variant and metric (raw + controlled, CIs, p, q, notes) |
| `tables/attribute_effects_stability.csv` | Primary variant joined to the other four; `status` |
| `tables/hypothesis_results.csv` | Rows tied to hypotheses H1, H3–H10 |
| `tables/correlations_within_product_form.csv` | Spearman ρ by form and pooled-within, with CIs |
| `tables/label_quality.csv` | Brand-label cross-tab, missing labels, duplicate-video label equality |
| `tables/column_provenance.csv`, `json/column_provenance.json` | Platform vs AI label, role, cautions |
| `json/key_signals.json` | Guardrails + signals that pass a CI/stability screen, with `also_appears_as` |
| `json/variants.json`, `json/run_manifest.json` | Variant sizes; seed, B, versions, SHA-256 of inputs and outputs |
| `../../data/processed/creatives.csv`, `ads_enriched.csv` | Unit tables with flags (`is_lj004`, `brand_label_contradiction`, `low_evidence`) |

## 6. Next steps (not done here)
1. Creator-side window metrics (recent + full history, medians, CIs).
2. Written, reviewed ad-attribute ↔ post-attribute mapping, with an explicit "no equivalent" list.
3. Validate a sample of AI labels (the attributes behind the stable candidates first).
4. Only then, creative-compatibility features; audience fit restricted to CR-14, CR-15, CR-20.
