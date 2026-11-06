# Little Joys – Creator Intelligence Platform: Data Audit

Audit date: 2026-11-04. All figures below were computed from the four CSVs in `data/raw/` by `scripts/run_audit.py` and ad-hoc profiling; none are estimated. No creators are selected here, and no causal conclusions are drawn.

> **Note:** the brief mentions a README, but only the four CSVs were received. Anything the README would define (metric definitions, attribution window, label-generation method, how `revenue_inr` was measured) is listed under *Open questions* (§9).

---

## 1. Dataset overview and relationships

| Dataset | Rows × cols | Grain | Key |
|---|---|---|---|
| `ads.csv` | 100 × 56 | one Meta ad (creative + delivery results) | `ad_id` (unique), `meta_ad_library_id` (unique) |
| `creators.csv` | 20 × 21 | one creator profile | `creator_id`, `handle` |
| `creator_posts.csv` | 392 × 32 | one Instagram post (`/p/` URL) | `post_url` |
| `creator_audience.csv` | 3 × 10 | one creator's audience snapshot (as of 2026-10-29) | `creator_id` |

**Relationships**
- `creator_posts.creator_id` → `creators.creator_id` (many-to-one). Verified: every post links, handles match, and `posts_in_file` equals actual row counts (CR-18 has 12 posts, all others 20).
- `creator_audience.creator_id` → `creators.creator_id` (one-to-one, but only CR-14, CR-15, CR-20).
- **`ads.csv` has no creator key.** Ads cannot be joined to creators. The link between "what works in Little Joys ads" and "which creators fit" must go through *shared attribute vocabulary* (language, format, child presence, setting, tone…), not a join. Those vocabularies are **not identical** between the ad and post files (e.g. ads `ad_format` vs posts `content_form`, ads `hook_type` vs posts `hook_style` which is free text), so a mapping table is required.

```
ads (100)  ··· no key ···  creators (20) ──1:N── creator_posts (392)
                                │
                                └──1:0..1── creator_audience (3)
```

## 2. Column inventory by type

### ads.csv
- **IDs / URLs:** `ad_id`, `meta_ad_library_id`, `video_url`
- **Dates:** `launch_date` (2026-06-10 → 2026-10-09), `stopped_date`
- **Numeric – platform-reported outcomes:** `spend_inr`, `impressions`, `video_3s_views`, `thruplays`, `link_clicks`, `add_to_carts`, `purchases`, `revenue_inr`
- **Numeric – other:** `days_live`, `duration_s` (12.3–82.2 s)
- **Categorical (single value):** language, hook_type, hook_driver, hook_delivered_by, ad_format, story_structure, main_benefit, performance_style, humour, creator_type, creator_gender, creator_age, people_on_screen, child_on_screen, child_age, child_in_first_3s, brand_first_said, brand_said_aloud, product_form, product_shown_as, production, audio, music, captions, language_mixing, first_frame, setting, cta_type, offer
- **Multi-label (`;`-separated):** child_role, demo_shown, proof_used, persuasion, narratives, ad_categories, claims_made
- **Text:** ad_copy, transcript, hook_line, on_screen_text, hook_text_on_screen

### creators.csv
- **Numeric:** followers, following, total_posts, posts_in_file · **Categorical:** verified
- **Text (all LLM-style prose):** bio (raw), name, persona, persona_description, feed_story, voice, language_use, catchphrases, themes, format_habits, what_feels_native, what_would_feel_foreign
- **JSON-in-string:** `audience_read` (sentiment, who_replies, recurring_asks, reply_language, comment_evidence, what_provokes_reply, authenticity_concerns)

### creator_posts.csv
- **Numeric:** duration_s, plays, likes, comments, reshares, production_quality_1to5
- **Dates:** posted_on (2022-03-03 → 2026-10-27)
- **Categorical:** type (video 353 / carousel 34 / photo 5), content_type, content_form, creator_on_camera, children_on_camera, presenter_age, presenter_gender, language, product_shown, is_sponsored, transcript_language
- **Multi-label:** child_ages, brands_visible
- **Text:** caption, topic, hook_style, setting, tone, audience_signal, on_screen_text, what_stands_out, transcript

### creator_audience.csv
- **Numeric:** women_pct, men_pct · **Categorical:** platform
- **Packed strings (need parsing into long format):** age_split, top_cities, top_countries, brands_in_past_year

## 3. Missing values, duplicates, inconsistencies, unusual records

Full machine-readable list: `reports/tables/data_quality_report.csv` (0 ERROR, 24 WARN after final run). Highlights:

### ads.csv
| # | Issue | Evidence |
|---|---|---|
| A1 | **Same creative appears under multiple `ad_id`s** | 3 `video_url`s each shared by 2 ads (LJ-073/093, LJ-036/056, LJ-003/059). Transcript, hook_line and all labels are identical; launch dates, spend and results differ. 97 unique creatives, not 100. |
| A2 | **`stopped_date` looks like a snapshot date, not a true stop date** | only 8 distinct values across 100 ads; 37 ads share 2026-10-03. |
| A3 | **`days_live` disagrees with dates** | `days_live` = `(stopped − launch)` days for 26 ads and one day *less* for 74. Counting convention unclear. |
| A4 | **Spend is mostly a function of run time** | Spearman ρ(days_live, spend) = 0.71. |
| A5 | **Extreme concentration** | LJ-004 = 30.3% of all revenue (₹3.30M of ₹10.87M; ROAS 5.00 on ₹659k spend); top 5 ads = 51.1% of revenue; top 10 ads = 48.9% of spend. |
| A6 | **Tiny-sample ads** | 10 ads with spend < ₹5,000; 10 with < 10 purchases; 2 with 0 purchases (ROAS 0, CPA undefined); 16 ran ≤ 3 days. LJ-072 has ROAS 3.00 on ₹4,117 spend — noise, not signal. |
| A7 | **Missing labels** | `hook_type`, `ad_format`, `story_structure`, `child_role`, `brand_first_said` null for 2 rows (LJ-001, LJ-035); `creator_age` null for 1; `hook_text_on_screen` null for 15; `ad_copy` null for 12. |
| A8 | **Contradictory AI labels** | `brand_said_aloud = no` yet `brand_first_said = under_3s` for 18 ads. |
| A9 | **`ad_copy` is campaign-level** | only 17 distinct values across 88 non-null rows (one value appears 25×) – not a creative-level variable. |
| A10 | **Sparse category levels** | e.g. `hook_type`: 10 levels, only 3 with n ≥ 10; `story_structure`: 12 levels, 4 with n ≥ 10; `cta_type` 8 levels, 2 with n ≥ 10. Rare levels cannot be tested individually. |
| A11 | **Skewed launch timing** | 69 of 100 ads launched in Sept 2026; 2 in June, 2 in July. Recent ads are right-censored. |
| A12 | **Confounded with product** | `product_form` is not balanced: milk_mix_powder 51 / other 26 / gummies 23. Unadjusted ROAS by form (ratio of sums) is 1.88 / 1.01 / 0.99 – an observation that a creative-attribute analysis must control for, not a finding. |
| A13 | Order-of-magnitude outcome | Blended ROAS (ΣRevenue/ΣSpend) = 1.50; mean of per-ad ROAS = 1.26. These differ, so aggregation method matters. |

Funnel logic is consistent: no row has 3s views > impressions, thruplays > 3s views, clicks > impressions, ATC > clicks, or purchases > ATC; revenue > 0 iff purchases > 0. Implied AOV ranges ₹431–₹711 (median ~₹643).

### creators.csv
- `bio` null for CR-14, CR-16, CR-18.
- **`audience_read` is empty of information:** all 20 records have `comment_evidence = "none"`, `sentiment = "inert"`, recurring_asks empty for 19/20. Do not use.
- Persona labels are near-duplicates of each other ("Relatable Mom-Next-Door" ×2, several "Clinical Pediatric…" variants, inconsistent capitalisation), so persona is not a clean categorical.
- Wide scale: followers 22,659 → 2,831,180; `following` of 1 (CR-03) to 7,442 (CR-13).
- CR-18 has only 12 posts in file (others 20).

### creator_posts.csv
| # | Issue | Evidence |
|---|---|---|
| P1 | **`plays`/`duration_s` missing for all 39 carousels and photos** | structural, not random. Play-based rates only exist for 353 videos. |
| P2 | **Very different observation windows** | each creator has ~20 posts, but the date span is 33 days (CR-20) to 1,670 days (CR-06). Only 4 posts for CR-09 since 2026-07-01 vs 20 for CR-02/CR-12/CR-14/CR-20. Recency and rate comparisons are confounded. |
| P3 | **Transcripts exist for only 113/392 posts (29%)**; 5–6 per creator (4 for CR-12) | the transcript is a sample, not the full feed. |
| P4 | **Corrupted label** | one `transcript_language` value contains an entire transcript snippet instead of a language. |
| P5 | **13 spellings of `language`** | e.g. "Hindi/English", "Hindi and English", "English and Hindi", "Hindi/English (Hinglish)", "telugu" vs "Telugu"; ads use a different vocabulary ("Hinglish"). Needs a normalisation map. |
| P6 | Sponsorship labels | `is_sponsored` yes 105 / no 278 / unclear 9; 52 `no` posts still show a brand; 1 `yes` post has none. |
| P7 | Brand already seen | only 1 post shows "Little joys" (CR-09, 2025-07-11, sponsored; note lower-case 'joys'). Brand spellings are free text (149 distinct `brands_visible`). |
| P8 | `production_quality_1to5` | only values 2–5 occur; 267/392 are 3 → little spread. |
| P9 | 3 posts (all CR-10) share one caption ("Welcome to our Life…"); 4 posts have no caption | likely templated captions. |
| P10 | Heavy tails | plays median 431,561; mean 2.46M; max 79.1M. Likes max 2.98M. Raw averages are dominated by a few posts/creators. |
| P11 | 7 of CR-04's and 8 of CR-09's posts have no plays (carousels/photos) | per-creator play medians use fewer posts for those creators. |

Positive checks: no duplicate `post_url`; `likes ≤ plays` for every video; all counts non-negative; `child_ages` is present exactly when `children_on_camera = yes`.

### creator_audience.csv
- **Coverage:** 3 of 20 creators (CR-14, CR-15, CR-20).
- Percentages sum to 100 for gender; age/city/country strings are packed text.
- CR-14's row says `platform = facebook`, but `creators.csv` and all its posts are Instagram – the audience snapshot may describe a different account/page. Its top cities include Dhaka and Karachi, and India is only 64.4% (vs 88.3% and 95.7% for the others).
- CR-20: 70.1% men, whereas the creator is a child performer whose persona is "family chronicler" – plausible (audience of parents/relatives/others) but un-testable here.
- `brands_in_past_year` null for CR-14 (unknown vs none); CR-20 lists **Little Joys**; CR-15 lists two other baby brands.
- All three as-of 2026-10-29; no history.

## 4. AI-generated labels – treat cautiously

Nothing in the files documents how labels were produced; their structure (long prose, `"comment_evidence": "none"`, taxonomies with "other") indicates model-generated annotation of video/transcripts. Treat as *noisy measurements*, not ground truth.

| Dataset | Trust level | Columns |
|---|---|---|
| ads | **Platform-reported (higher trust)** | spend, impressions, 3s views, thruplays, link clicks, ATC, purchases, revenue; launch/stopped dates; `meta_ad_library_id`; `video_url` |
| ads | **AI-labelled (validate before relying)** | *every* creative attribute: hook_*, ad_format, story_structure, main_benefit, performance_style, humour, creator_*, child_*, brand_*, product_*, demo_shown, proof_used, persuasion, production, audio, music, captions, language/language_mixing, first_frame, setting, cta_type, offer, narratives, ad_categories, claims_made, plus transcript/hook_line/on_screen_text and measured-looking `duration_s`, `brand_first_said` timing bins |
| creators | **Platform-scraped** | followers, following, total_posts, verified, bio, name, profile_url |
| creators | **AI-generated prose (lowest trust)** | persona, persona_description, feed_story, voice, language_use, catchphrases, themes, format_habits, what_feels_native, what_would_feel_foreign, audience_read |
| posts | **Platform-scraped** | post_url, posted_on, type, plays, likes, comments, reshares, caption, duration_s |
| posts | **AI-labelled** | content_type, content_form, topic, hook_style, creator_on_camera, children_on_camera, child_ages, presenter_*, language, setting, tone, product_shown, **is_sponsored**, **brands_visible**, production_quality_1to5, audience_signal, on_screen_text, what_stands_out, transcript, transcript_language |
| audience | Platform-reported (provenance to confirm) | all columns |

Specific cautions:
- **`is_sponsored` / `brands_visible`** are inferred from the visible content; real disclosure ≠ label. Misclassification would distort any "sponsored vs organic" comparison.
- **`production_quality_1to5`** is subjective and compressed.
- **`audience_signal`** in posts describes who the content is *aimed at*, not who is watching.
- **`what_feels_native` / `what_would_feel_foreign`** are generative opinions about brand fit – useful for qualitative briefing, not as a metric.
- Ad labels have internal contradictions (A8) and a few unlabeled rows; **no inter-rater / re-label check exists** (see plan step 3).

## 5. Metrics we can compute

**Ads (all from platform counts; guard zero denominators)**
- Cost: CPM = spend/impr×1000; CPC(link) = spend/link_clicks; CPA = spend/purchases
- Attention: hook rate = 3s views/impr; hold rate = thruplays/3s views; thruplay rate = thruplays/impr
- Response: link CTR = clicks/impr; click→ATC; ATC→purchase; click→purchase (CVR)
- Value: **ROAS = revenue/spend**, AOV = revenue/purchases, revenue per 1k impressions, purchases per ₹1k spend
- Always aggregate by **ratio of sums** within groups (spend-weighted), never a mean of per-ad ratios (implemented in `metrics.aggregate_roas`).
- Intensity controls: days_live, spend_per_day, launch cohort (week).
- Concentration: share of revenue/spend by ad; Gini/Lorenz.

**Posts**
- Engagement rate by play = (likes+comments+reshares)/plays (videos only); like/comment/share rates
- Per-creator medians (not means) of plays, ER; **view-to-follower ratio** = median plays/followers; coefficient of variation of plays (consistency)
- Share of posts with children on camera, with product shown, sponsored; sponsored-vs-organic ER ratio within creator
- Posting cadence = posts/day over the creator's own window

**Creators/audience**
- Followers tier; follower/following ratio; audience women %, India %, 25–44 %, top-metro share (parse packed strings), prior-brand count

**Cross-file (attribute-level, not join-level)**
- Share of each ad attribute (e.g. child in first 3s, kitchen setting, Hindi/Hinglish) present in a creator's posts, for comparison with the attribute profile of high-ROAS ads – *only after* a vocabulary mapping is built and validated.

## 6. Limitations by dataset

**ads.csv:** n = 100 (97 unique creatives); ≤ 3 products' worth of variation confounded with creative; no creator link; no audience/targeting/placement/budget-optimisation fields; unknown attribution window and whether `revenue_inr` is Meta-attributed or store-reconciled (and therefore likely over/under-credits); non-random assignment of spend (more budget → more run time → more learning); heavy right-skew (one ad = 30% revenue); right-censored recent ads; all creative attributes are AI labels with sparse levels; no experiment design, so any attribute–outcome relation is observational. Language coverage includes Kannada (7), Malayalam (6), Tamil (5), Punjabi (2) ads, while the posts' `language` column shows no creator content in those languages (it does show Hindi, English, Gujarati, Telugu).

**creators.csv:** 20 creators chosen by an unknown process (not a random sample); persona text is AI prose; `audience_read` empty; no pricing, rate card, historical brand-collab performance, or contact/consent data.

**creator_posts.csv:** ~20 recent posts per creator over very different time windows; engagement is public-counts only (no reach, saves, watch time, link clicks, sales); no sponsorship outcome data; carousels/photos have no plays; most transcripts missing; no comments text (so no sentiment); post-level labels cannot tell us causal engagement drivers; `plays` for old posts have had longer to accumulate.

**creator_audience.csv:** 3 of 20 creators; single snapshot; shares of top cities/countries are truncated to four items; platform inconsistency for CR-14; cannot support any cross-creator audience ranking.

## 7. Hypotheses to test (observational; require controls & uncertainty intervals)

**Primary – ad creative → purchases/revenue** (outcome: ROAS, CPA, CVR; control: product_form, spend, days_live, launch cohort; unit: unique creative)
1. H1 Showing a child in the first 3 s (`child_in_first_3s=yes`, n=41) is associated with higher hook rate, and with higher CVR/ROAS after product controls.
2. H2 `product_form` explains a large share of ROAS variance; once it is controlled for, most creative attributes show little residual effect.
3. H3 Explicit `buy_now` CTAs (n=58) lift click→purchase but not hook rate vs `none` (n=32).
4. H4 `brand_said_aloud=yes` / earlier brand mention relates to CVR (watch contradictory labels, A8).
5. H5 Hook driver `fear_pain_point` vs `curiosity_gap` vs `personal_experience`: different effects on hook rate vs on purchase conversion (attention ≠ sales).
6. H6 `parent_or_caregiver` presenters (n=57) vs `child_presenter` (n=9) vs `none_visible` (n=15): difference in CVR / AOV.
7. H7 `production = ugc` (n=26) vs `semi_pro` (61) vs `studio` (12): UGC converts at least as well per rupee.
8. H8 Language (English 38, Hinglish 25, Hindi 10, regional 20): CPM/CVR differences; regional-language ads are small-n.
9. H9 Setting (kitchen 28, indoor_home 42, retail_store 8) and demo type (`child_consuming`, `taste_test`, `mixing_prep`) relate to CVR.
10. H10 Duration: relationship between `duration_s` and hold rate vs CVR (likely non-monotonic).
11. H11 High hook rate does *not* reliably predict high ROAS (rank correlation across ads, tested in-product-form).
12. H12 Funnel stage diagnostics: where do high- vs low-ROAS ads lose users (CTR vs click→ATC vs ATC→purchase)?
13. H13 Interactions (e.g. child_on_screen × UGC) – only if sample allows; otherwise report as exploratory.

**Creator/post-side (descriptive, pre-selection; no ranking yet)**
14. H14 Within creators, posts with children on camera have different median ER than posts without (within-creator paired comparison).
15. H15 Sponsored posts show lower ER/play rates than organic posts for the same creator (watch label reliability).
16. H16 Expert/medical personas have lower ER but different comment/share profiles than comedy/skit personas.
17. H17 Creator-level consistency (CV of plays) differs by content type and follower tier.
18. H18 For the 3 creators with audience data, audience women %, age band and India share differ from the target parent audience (descriptive only).
19. H19 Mapping test: do attribute profiles of high-ROAS ads (e.g. UGC, home/kitchen, Hinglish, child on screen) appear in creator posts at meaningfully different rates across creators? (Defines *fit features*; not a selection.)

## 8. Analysis plan

**Phase 0 – Foundations (done in this repo)**: schema, loaders, validators, metrics, tests, data-quality report.

**Phase 1 – Cleaning/normalisation** (`src/cip/clean.py`, outputs to `data/interim/`)
1. Collapse the 3 duplicate-video pairs into creative-level rows (sum counts, keep one label set); keep ad-level table too. Run all results both ways.
2. Normalise `language` (map 13 spellings), fix the corrupted `transcript_language`, standardise brand names, collapse persona labels to a controlled list.
3. Parse multi-label columns into long tables (`ad_id, attribute, value`) and creator audience packed strings into long format.
4. Define one observation window per creator (e.g. last N posts and a common date window) and keep both versions.
5. Flag (don't drop) low-spend/low-purchase ads; define a minimum-evidence rule (e.g. spend ≥ ₹5,000 and purchases ≥ 10) as a *sensitivity* filter.

**Phase 2 – Ad performance baseline**: distributions, concentration (Lorenz), funnel diagnostics, product-form split; ratio-of-sums aggregation; bootstrap CIs; show with and without LJ-004.

**Phase 3 – Creative attribute → outcome**
1. Univariate: group ROAS/CVR/CPA with bootstrap CIs; show n per level; merge levels < 5–10 ads into "other".
2. Multivariate: regularised or Bayesian models (e.g. Poisson/binomial for purchases with log-exposure offset, or beta-binomial for CVR) with `product_form`, days_live/spend, launch cohort as controls; hierarchical shrinkage on sparse levels.
3. Effect sizes + intervals, multiple-comparison control (Benjamini–Hochberg), leave-one-out (esp. LJ-004) stability, permutation tests.
4. Stage-wise analysis: attention (hook/hold) vs intent (CTR/ATC) vs conversion – to avoid optimising for views.
5. Label reliability: manually spot-check 15–20 ads on key attributes against the video; or re-label with a second pass and report agreement (Cohen's κ).

**Phase 4 – Creator-side description**: per-creator medians, ER, consistency, content mix, child/product/sponsorship rates, language mix, windowed vs full; audience stats for the 3 available.

**Phase 5 – Bridge (design only until phases 2–4 pass review)**: build an explicit mapping of ad attributes ↔ post attributes; define fit features and uncertainty; decide what *cannot* be inferred (no ad↔creator link, no creator conversion data).

**Phase 6 – Productisation**: config-driven pipeline (`make audit | clean | analyze`), data contracts (schema + validator in CI), reproducible notebooks, versioned outputs.

Guardrails: report n and intervals everywhere; no causal wording; every table tagged by label provenance; analysis scripts read only from `data/interim|processed`.

## 9. Open questions to resolve with the data owner

1. Attribution window / source of `purchases` and `revenue_inr` (Meta-reported vs store-reconciled)?
2. Are `spend`/results lifetime totals, or for a specific date range? What is the true `stopped_date` logic?
3. Why do three videos appear under two ad IDs (different ad sets/audiences)?
4. How and by which model/prompt were creative and post labels generated; any validation sample?
5. How were the 20 creators and the 3 audience snapshots chosen? Is CR-14's audience from a Facebook page distinct from the Instagram account?
6. Are there ad-level targeting/placement/budget fields available?
7. Which products do the `other` product_form ads cover?

## 10. Proposed project structure

```
creator-intelligence-platform/
├── README.md
├── requirements.txt
├── configs/                  # thresholds, language/brand maps, window definitions (YAML)
├── data/
│   ├── raw/                  # original CSVs, immutable
│   ├── interim/              # cleaned/normalised tables, long-format label tables
│   └── processed/            # analysis-ready marts
├── docs/
│   └── data_audit.md         # this document (+ data dictionary, decisions log)
├── notebooks/                # exploration only; logic moves to src/
├── reports/
│   ├── figures/
│   └── tables/               # data_quality_report.csv, results tables
├── scripts/
│   └── run_audit.py          # CLI: load → validate → report (exit 1 on ERROR)
├── src/cip/
│   ├── schema.py             # column roles, AI-label flags, expected shapes
│   ├── loaders.py            # explicit parsing, multilabel/JSON helpers
│   ├── validate.py           # severity-tagged checks → DataFrame
│   ├── metrics.py            # safe ratios, ratio-of-sums aggregation
│   ├── clean.py              # (Phase 1)
│   ├── features.py           # (Phase 1/3: attribute encoding)
│   ├── models.py             # (Phase 3)
│   └── bridge.py             # (Phase 5: ad↔post attribute mapping)
└── tests/                    # pytest: shapes, keys, metrics, validators
```
