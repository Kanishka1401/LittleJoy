# Creative DNA Matching – Methods, Results, Output Dictionary

Reproduce: `python scripts/run_creative_dna.py` (≈2 s). Code: `src/cip/dna.py`; page: `dashboard/views_dna.py` ("Creative DNA" in the app); tests: `tests/test_creative_dna.py`.
The module **reads** `reports/ad/` (existing effect estimates) and `reports/creator/` (shortlist) and writes only `reports/dna/`. A test verifies that the ad and creator outputs are byte-identical to their manifests.

## 1. Rules that keep it honest
- **No organic engagement anywhere.** Likes, plays and ER never enter a score (a test permutes them and asserts identical output). Organic engagement is not evidence of paid performance.
- **No re-estimation.** Effect sizes, CIs, statuses and LJ-004 sensitivity are copied from `attribute_effects_stability.csv` (primary variant `creative_all`).
- **Two outcome stages, never blended.** *Attention* = hook rate (3-s views / impressions); *Purchase* = click→purchase. In this data they do not move together (hook rate vs ROAS ρ = −0.18 within product form), so one "success" score would mislead.
- **Provenance on every row** (`evidence_type`): `ad_platform_metric`, `ad_ai_label`, `post_ai_label`, `post_platform_field`, `rule_derived` (our keyword rule over AI text), `assumption` (mapping quality, thresholds, opportunity templates).
- **Not causal, not a forecast.** "Alignment" = how often a creator already does what the ad analysis associates with higher attention.

## 2. Task 1 – Creative characteristics associated with outcomes (LJ-004 accounted for)
Every pattern carries its estimate **with and without LJ-004**, whether LJ-004 itself has the feature, and whether the CI still excludes 0 without it (`ad_success_patterns.csv`).
- **Attention (hook rate), stable candidates that survive the LJ-004 check:** humour (+9.7 pts), child in first 3 s (+8.4), skit (+7.5), storytelling persuasion (+6.9), child on screen (+5.8), lifestyle/routine category (+4.9); lower: explainer-to-camera (−8.3), English-only (−5.2), product-feature demo (−7.9), earnest talk (−8.1), product in first frame (−6.3). Effects move by ≤ 1.5 pts without LJ-004.
- **Purchase (click→purchase), stable candidates:** "overall growth" narrative −2.4 pts (CVR) and −1.5 ROAS (halves to −0.75 without LJ-004); no humour +2.0 pts (humour −2.0); parent/caregiver presenter −1.9; occasional language borrowing −2.4. Skit format is *directionally* −2.3 pts despite earning attention.
- **Descriptive "success cohort"** (`success_cohort_prevalence.csv`): top-quartile ROAS within product form, excluding LJ-004 and low-evidence creatives (n = 23 vs 61). The only clear difference is the growth narrative (26% of top-quartile ads vs 57%, exploratory p = 0.01), consistent with the stable purchase signal. Skit, humour and explainer are **not** more common among high-ROAS ads, so attention-linked patterns are not sales evidence.
- All 29 stable-candidate signals are listed with their mapping status (`stable_signals_mapping_status.csv`).

## 3. Task 2 – Explicit ad ↔ post mapping (`attribute_mapping.csv`)
16 ad features, each with the ad definition, post definition, **quality** (direct / approximate / weak / none), rationale, caveat and post-side evidence type. 9 are usable (direct/approximate): child visible, skit, explainer↔piece-to-camera, voiceover (not scored: directional evidence only), humour (keyword rule on AI tone text), storytelling (rule), lifestyle/routine, English-only language, growth narrative (keyword rule). Weak/none (never scored): parent presenter, product-feature demo, language borrowing, earnest talk, **child in first 3 s** (posts have no timing labels), child speaks, product in first frame. Fields with no post equivalent: production style, proof/CTA/offer/brand-mention, hook type/driver, audio/music/captions. Quality ratings are our judgement.

## 4. Scoring (transparent, only where justified)
A feature enters a creator's score iff (1) ad status = `stable_candidate` (which already requires surviving the LJ-004 check), (2) mapping quality is direct/approximate, (3) the creator has ≥ 10 labelled posts. A lens is scored only with ≥ 3 eligible features.
- Alignment per feature = prevalence if the ad pattern is "+" else 1 − prevalence; lens score = 100 × mean alignment (equal weights; effect-weighted variant in `*_effect_weighted`). Missing labels give NaN, never 0. Features overlap (many describe the same ads), so they are not independent evidence.
- **Attention lens: scored (7 features). Purchase lens: not scored for any creator**: only 2 eligible features (humour, growth narrative) < 3. Purchase-stage context is shown per creator instead.

## 5. Results for the five shortlisted creators (engine default ranking)
| Creator | Natural style (post labels) | Attention alignment | Main matches | Main gaps |
|---|---|---|---|---|
| CR-03 `ekamichildcare` (#1) | 100% piece-to-camera expert explainers in clinic | 25 | children on camera 75%; never English-only | no skit/humour/story/routine; 100% explainer |
| CR-11 `raja_choudhary04` (#2) | voiceover montage 80%, lifestyle/day-in-life, children 100% | 60 | child present 100%, routine 90%, no explainer | little skit (5%) or humour (15%) |
| CR-02 `livesimply_withkripa` (#3) | skits 85%, comedy, English | 65 | skit 85%, storytelling 90%, humour 75%, no explainer | little routine content (30%); skit/humour are *negative* for conversion in ads (mixed signal) |
| CR-05 `sia_3vedi` (#4) | child-led, Hindi, humour | 57 | children 100%, humour 75%, rarely English-only | little skit (15%) |
| CR-01 `drgarima_mehta` (#5) | 95% explainers, English-only, clinic | 14 | children on camera 85% | no skit/humour/story/routine; English-only; explainer-heavy |

Reading: the DNA view complements the engine ranking rather than confirming it. CR-03 and CR-01 rank highest on relevance and credibility yet are furthest from the formats that earned attention in Little Joys ads; CR-02, CR-11 and CR-05 are closer. Opportunity text per feature (`creator_dna_profiles.json`) is a **suggested test (assumption)**, never evidence. Supporting ad creative IDs (platform-metric ads that carry the feature; LJ-004 and low-evidence ads excluded, ordered by hook rate) and creator post IDs (Instagram shortcodes) are listed per feature; tests assert every ID exists in the source data and truly carries the feature.

## 6. Limitations
- Ad attributes and post attributes are AI labels; post-side humour, storytelling and growth are keyword rules on AI text and will misclassify some posts.
- The strongest attention signal (child in first 3 s) and the child-speaks signal cannot be matched to posts.
- Ad associations are observational, within 3 product forms and 97 creatives; attention-pattern alignment is not validated against sales and may not transfer to a creator's own paid creative.
- Prevalence uses ~20 posts per creator spanning very different date ranges; carousels/photos are included in denominators.
- Thresholds (strength ≥ 0.60, gap ≤ 0.30, ≥ 3 features, ≥ 10 posts) and mapping qualities are assumptions in `dna.py` constants.

## 7. Output dictionary (`reports/dna/`)
| File | Content |
|---|---|
| `tables/attribute_mapping.csv` | The explicit mapping registry with quality, rationale, caveat |
| `tables/ad_success_patterns.csv` | Per feature × stage: effect, CI, with/without LJ-004, eligibility and reason |
| `tables/stable_signals_mapping_status.csv` | All stable ad signals and whether they map |
| `tables/success_cohort_prevalence.csv` | Top-quartile-ROAS vs rest prevalence (descriptive) |
| `tables/creator_dna_scores.csv` | Attention/purchase lens scores, status, engine rank, shortlist flag |
| `tables/creator_feature_alignment.csv` | Creator × feature prevalence and alignment |
| `tables/evidence_posts.csv`, `evidence_ads.csv` | Post IDs/URLs and ad IDs with outcomes behind every match |
| `json/creator_dna_profiles.json` | Natural style, strengths, gaps, purchase context, supporting IDs, explanation |
| `json/config.json`, `run_manifest.json` | Thresholds, provenance legend, shortlist, input/output hashes |
