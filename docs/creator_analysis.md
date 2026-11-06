# Creator Analysis Engine – Methods, Results, Output Dictionary

Reproduce: `python scripts/run_creator_analysis.py` (≈70 s, seed 20261105, 300 post-resamples). Re-running gives byte-identical files (hashes in `reports/creator/json/run_manifest.json`). Code: `src/cip/creator_analysis.py`; tests: `tests/test_creator_analysis.py` (21 tests). The completed ad analysis (`reports/ad/`, `data/processed/`) is untouched; a test checks its files against the original manifest hashes.

> **All post and creator labels are AI-generated and unvalidated (data_audit §4). The ranking is exploratory decision support, not a prediction of campaign results.** There is no creator-level sales/ROAS data, and ads cannot be joined to creators.

## 1. Pipeline
1. `post_features` – one row per post (392): relevance tier, format/setting/language fit, storytelling, product integration, ER, comment rate, interaction depth.
2. `creator_metrics` – one row per creator (20): medians, posting frequency, **full-history vs last-90-days** performance (as-of = latest post, 2026-10-27), sponsorship behaviour, content shares.
3. `score_creators` – named components → five dimension scores (0–100) → weighted composite (25/20/20/20/15). All components, raw values and weights are saved (`component_scores.csv`).
4. `confidence`, `bootstrap_ranks`, `sensitivity_ranks`, `explain`.

## 2. Dimensions (see `weights_and_config.json`)
| Dimension (weight) | Components (weight inside dimension) |
|---|---|
| **Content relevance (25%)** | Mean post relevance tier: 1.0 nutrition/feeding + children, 0.7 nutrition only, 0.5 child health, 0.4 parenting/children only, 0 otherwise (keyword lexicons over topic, caption, hook, what-stands-out, on-screen text, transcript when present) |
| **Engagement quality (20%)** | Median ER by play, full history (.30); median ER in last 90 d (.20, only if ≥4 videos with plays); median comment rate per play (.15); interaction depth = (comments+shares)/all interactions (.20); ER consistency = robust CV, lower is better (.15). Percentile-ranked across the 20 creators. |
| **Creative compatibility (20%)** | Share of posts with children on camera (.20); format fit via ad↔post crosswalk (.25); storytelling/skit/humour cues (.15); setting fit (.10); language fit (.10); product shown (.20) |
| **Authenticity (20%)** | Median plays ÷ followers (.35); sponsorship balance (0 sponsored = 100, ≥50% sponsored = 0) (.25); sponsored vs organic median ER ratio (.25, needs ≥3 videos each side); on-camera presence (.15) |
| **Audience fit (15%)** | Content-targeting proxy (share of posts whose `audience_signal` targets parents/families) for **all 20**; for the three creators with demographics, blended 50/50 with the demographic match (mean of women share, India share, 25–44 share) |

The ad↔post vocabulary mapping is written out in `ad_post_crosswalk.csv` (including values with **no equivalent** and fields deliberately **not used**, e.g. `production_quality_1to5`). Format/setting fit = `min(1, share of Little Joys creatives using it / 0.15)`, so formats used in ≥15% of the 97 unique creatives count as full fit. This measures *familiarity with Little Joys' own creative vocabulary*; the ad analysis found no clear format effect on purchases, so no format is "rewarded" for performance.

## 3. Missing demographics (3 of 20 creators have them)
- Nothing is imputed or defaulted. Creators without a snapshot have `NaN` demographic fields (17 rows) and `has_demographics = False`.
- Their audience fit is the proxy alone (blend weight 0), i.e. the same scale as everyone else. A missing component is **dropped, never scored 0**. Within any dimension, weights are re-normalised over the components that exist (e.g. CR-09's recent-window ER is not scorable, so engagement uses its other four components).
- The loss of evidence is shown in `coverage_audience_fit` (0.5 without demographics, 1.0 with, 0.75 for CR-14) and in confidence, not in the score. Tests assert this.
- CR-14's snapshot is a **Facebook** audience while the creator is an Instagram account (audit §3); its demographic weight is halved (0.25) and it is flagged `platform_mismatch`.
- **Asymmetry to be aware of:** demographics can only move the three creators that have them. CR-20's audience is 70% men, which pulls its audience fit from the proxy's 100 to 81 and moves it from 3rd to 6th without that data (`rank_no_demographics`). The 17 others carry an unverified, generous proxy (several score 100). Collecting snapshots for the shortlisted creators is the highest-value next step.

## 4. Evidence coverage and confidence
- `evidence_coverage` (0–1) = weighted mean over dimensions of (share of component weight computable × completeness of the underlying fields: plays present, sponsorship labelled, compatibility labels, etc.).
- `confidence_index` = 0.35 coverage + 0.15 post sufficiency (n/20) + 0.15 video sufficiency (n/15) + 0.15 recent-window sufficiency (n/8) + 0.20 stability (width of the 90% bootstrap score interval, 20 pts = 0). Levels: High ≥ 0.85, Medium ≥ 0.70, else Low. Confidence never changes a score. Reasons are in the `flags` column.
- Bootstrap: posts resampled with replacement within each creator, whole cohort re-scored (percentile ranks included). Gives `score_p05/p95`, `rank_p05/p95`, `p_top5`. This captures post-sampling noise only, not label error or weight choice.
- Sensitivity ranks: no demographics, full-history only, equal dimension weights (`sensitivity_rankings.csv`).

## 5. Results

**Five strongest creators** (`top5_explanations.csv`, `top5.json` hold the full per-creator explanations):

| Rank | Creator | Score (90% interval) | P(top-5) | Confidence | Why |
|---|---|---|---|---|---|
| 1 | CR-03 `ekamichildcare` | 72.6 (69.2–77.7) | 100% | High | Highest relevance (75% of posts nutrition/feeding + children), child-centred, 3.4% median ER stable across windows, low sponsorship. Weakest: creative compatibility (no storytelling, clinical settings). |
| 2 | CR-11 `raja_choudhary04` | 70.9 (64.1–71.7) | 78% | Medium | Relevance 73, high compatibility (75; children in 100% of posts, strong format fit), 4.3% full-history ER. Caution: only 4 videos in the last 90 days (recent ER 3.1%); 35% sponsored; two competitor-nutrition-brand posts. |
| 3 | CR-02 `livesimply_withkripa` | 68.5 (63.3–72.9) | 74% | High | Authenticity 100 (no sponsored posts, highest plays-to-followers ratio in the cohort), 4.8% ER, storytelling-heavy. Weakest: relevance (20% nutrition+children). No sponsored track record to judge brand-deal behaviour. |
| 4 | CR-05 `sia_3vedi` | 68.2 (64.0–70.9) | 68% | High | Best engagement (6.3% ER, 2.8M followers), child on camera in 100% of posts. Relevance low (5% nutrition+children); posts ~1.1/30 d. |
| 5 | CR-01 `drgarima_mehta` | 68.0 (62.7–73.2) | 68% | High | Relevance 82 and clinical credibility; weak engagement (1.2% ER, engagement score 29). Moves 3rd–6th depending on weighting. |

How firm is this? **CR-03 is clearly first.** Positions 2–5 are within ~3 points of each other and of CR-20 (66.4, 6th, P(top-5) 36%); treat them as a shortlist, not an ordered list. CR-20 replaces CR-01 in the top five if demographics are ignored, and CR-01 is 3rd if recent ER is ignored. The bottom four (CR-17, CR-19, CR-06 at 18–20, CR-04 at 16–17) are stable under every variant; CR-06 (observational comedian, no children, 10% relevance) is lowest.

Other points worth knowing:
- **Different strengths, same score:** CR-03/CR-01 win on relevance, CR-05/CR-20 on engagement. The weights decide which profile a campaign prefers; `creator_ranking.csv` has the per-dimension contributions to re-weigh.
- Competitor kids-nutrition brands (Gritzo, Little Tummys, etc.) appear in posts of CR-03, CR-05, CR-11 (flag only, not scored; verify exclusivity).
- Low-confidence creators: CR-18 (only 12 posts) and CR-09 (4 posts in the last 90 days, 80% sponsored).
- ER is not adjusted for account size beyond percentile ranking; very large accounts naturally show lower ER.

## 6. Limitations
- Relevance, compatibility and audience proxy use keyword rules over AI-written text; no label validation sample exists. Expect misclassification at the post level that averages out only partly over 20 posts.
- Each creator has ≤20 posts covering 33 to 1,670 days (audit P2). "Recent window" therefore means different post counts per creator (4 to 20); the engine reports counts and drops windows with <4 videos with plays.
- `is_sponsored` is an inferred label; unlabelled/“unclear” posts count as half. CR-02, CR-03, CR-14, CR-16 and others have no (or too few) sponsored videos, so the sponsored-vs-organic ratio is not estimable for 12 creators (dropped, not penalised).
- Engagement uses public counts only (no reach, saves, watch time, clicks or sales). ER differs by account size and format.
- All thresholds (90 days, 0.15 saturation, 50% sponsorship cap, 0.5 demographic blend, weights inside dimensions) are judgement calls in `creator_analysis.py` constants; only the five top-level weights came from the brief.

## 7. Output dictionary (`reports/creator/`)
| File | Content |
|---|---|
| `tables/creator_ranking.csv` | Rank, composite, five dimension scores and weighted contributions, coverage, confidence, flags, bootstrap intervals/P(top-5), sensitivity ranks |
| `tables/top5_explanations.csv`, `json/top5.json` | Plain-language explanation, contributions, strongest components, flags |
| `tables/creator_metrics.csv` | Every raw metric per creator (medians, frequency, windows, shares) |
| `tables/window_performance.csv` | Full-history vs last-90-days: posts, frequency, ER, plays |
| `tables/component_scores.csv` | Creator × dimension × component: raw value, score, weight, `available` |
| `tables/evidence_coverage_confidence.csv` | Per-dimension coverage, sufficiency, stability, confidence level, flags |
| `tables/audience_demographics_parsed.csv` | Parsed snapshots for CR-14/15/20; NaN for the other 17 |
| `tables/ad_post_crosswalk.csv` | Ad↔post mapping, fit values, unmapped values |
| `tables/sensitivity_rankings.csv` | Ranks/scores under the alternative variants |
| `json/weights_and_config.json`, `json/run_manifest.json` | Weights, components, thresholds, seed, input/output SHA-256 |

## 8. Next steps
1. Obtain audience snapshots for the ~8 shortlisted creators so audience fit rests on measured data.
2. Validate a sample of post labels (is_sponsored, content_form, children_on_camera) by hand.
3. Add creator pricing and exclusivity/competitor-conflict checks before outreach.
