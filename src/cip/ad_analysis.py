"""Advertising performance analysis (platform outcomes ~ AI-labelled creative attributes).

Entry point: run(raw_dir, out_dir, B, seed). Writes structured CSV + JSON; nothing is printed as a
"finding" that is not also in a file.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

from . import stats as S
from .clean import (BRAND_ATTRS, DERIVED_ATTRS, MIN_EVIDENCE_PURCHASES, MIN_EVIDENCE_SPEND,
                    MIN_TOKEN_SUPPORT, prepare_units)
from .loaders import FILES, load_ads
from .metrics import add_ad_metrics
from .schema import ADS

# metric -> (numerator, denominator, scale). All aggregated as ratio-of-sums.
METRIC_DEFS = {
    "roas": ("revenue_inr", "spend_inr", 1.0),
    "cpa": ("spend_inr", "purchases", 1.0),
    "cvr_click": ("purchases", "link_clicks", 1.0),
    "aov": ("revenue_inr", "purchases", 1.0),
    "hook_rate": ("video_3s_views", "impressions", 1.0),
    "hold_rate": ("thruplays", "video_3s_views", 1.0),
    "ctr_link": ("link_clicks", "impressions", 1.0),
    "click_to_atc": ("add_to_carts", "link_clicks", 1.0),
    "atc_to_purchase": ("purchases", "add_to_carts", 1.0),
    "cpm": ("spend_inr", "impressions", 1000.0),
}
BASELINE_METRICS = ["roas", "cpa", "cvr_click", "aov", "hook_rate", "hold_rate", "ctr_link", "cpm"]
FUNNEL_METRICS = ["hook_rate", "hold_rate", "ctr_link", "click_to_atc", "atc_to_purchase", "cvr_click"]
EFFECT_METRICS = ["roas", "cvr_click", "hook_rate", "ctr_link", "aov"]
MEDIAN_EFFECT_METRICS = ["roas", "cvr_click"]
MIN_LEVEL_N = 5          # smallest level/rest group that is analysed at all
LOW_N = 10               # below this the row is flagged low-n
OUTCOME_COLS = ["spend_inr", "impressions", "video_3s_views", "thruplays", "link_clicks",
                "add_to_carts", "purchases", "revenue_inr"]

PRIMARY = "creative_all"
STABILITY_VARIANTS = ["creative_excl_LJ004", "creative_min_evidence", "ad_all", "ad_excl_LJ004"]

HYPOTHESES = [  # id, attribute, level, metrics
    ("H1", "child_in_first_3s", "yes", ["hook_rate", "cvr_click", "roas"]),
    ("H1", "child_present", "yes", ["hook_rate", "cvr_click", "roas"]),
    ("H3", "cta_group", "buy_now", ["hook_rate", "cvr_click", "roas"]),
    ("H4", "brand_said_aloud", "yes", ["cvr_click", "roas"]),
    ("H5", "hook_driver", "curiosity_gap", ["hook_rate", "cvr_click"]),
    ("H5", "hook_driver", "fear_pain_point", ["hook_rate", "cvr_click"]),
    ("H5", "hook_driver", "personal_experience", ["hook_rate", "cvr_click"]),
    ("H6", "creator_type", "parent_or_caregiver", ["cvr_click", "aov", "roas"]),
    ("H6", "creator_type", "child_presenter", ["cvr_click", "aov", "roas"]),
    ("H6", "creator_type", "none_visible", ["cvr_click", "aov", "roas"]),
    ("H7", "production", "ugc", ["cvr_click", "roas"]),
    ("H7", "production", "semi_pro", ["cvr_click", "roas"]),
    ("H7", "production", "studio", ["cvr_click", "roas"]),
    ("H8", "language_group", "English", ["ctr_link", "cvr_click", "roas"]),
    ("H8", "language_group", "Hindi_Hinglish", ["ctr_link", "cvr_click", "roas"]),
    ("H8", "language_group", "regional_other", ["ctr_link", "cvr_click", "roas"]),
    ("H9", "setting", "kitchen", ["cvr_click", "roas"]),
    ("H9", "setting", "indoor_home", ["cvr_click", "roas"]),
    ("H9", "ml:demo_shown", "child_consuming", ["cvr_click", "roas"]),
    ("H9", "ml:demo_shown", "taste_test", ["cvr_click", "roas"]),
    ("H9", "ml:demo_shown", "mixing_prep", ["cvr_click", "roas"]),
    ("H10", "duration_bin", "<=30s", ["hook_rate", "cvr_click", "roas"]),
    ("H10", "duration_bin", "30-45s", ["hook_rate", "cvr_click", "roas"]),
    ("H10", "duration_bin", ">45s", ["hook_rate", "cvr_click", "roas"]),
]

CORR_PAIRS = [("hook_rate", "roas"), ("hold_rate", "roas"), ("ctr_link", "roas"), ("cvr_click", "roas"),
              ("hook_rate", "cvr_click"), ("duration_s", "roas"), ("duration_s", "hold_rate"),
              ("spend_inr", "roas"), ("days_live", "roas"), ("cpm", "roas")]


# ------------------------------------------------------------------ context
class Ctx:
    """One analysis dataset + its seeded, product_form-stratified bootstrap."""

    def __init__(self, name: str, unit: str, df: pd.DataFrame, B: int, seed: int):
        self.name, self.unit = name, unit
        self.df = add_ad_metrics(df.reset_index(drop=True))
        self.n = len(self.df)
        self.pf = self.df.product_form.to_numpy()
        codes = pd.factorize(self.df.product_form, sort=True)[0]
        self.boot = S.make_boot(codes, B=B, seed=seed)
        self.arr = {c: self.df[c].to_numpy(float) for c in self.df.columns
                    if pd.api.types.is_numeric_dtype(self.df[c]) and not pd.api.types.is_bool_dtype(self.df[c])}
        self.unit_vals = {m: self.df[m].to_numpy(float) for m in METRIC_DEFS}

    def all_mask(self):
        return np.ones(self.n, dtype=bool)


def group_summary(ctx: Ctx, mask: np.ndarray, metrics: list[str]) -> dict:
    out = {"n_units": int(mask.sum())}
    for c in ("spend_inr", "purchases", "revenue_inr", "link_clicks", "impressions"):
        out[c] = float(ctx.arr[c][mask].sum())
    for m in metrics:
        num, den, sc = METRIC_DEFS[m]
        pt = S.ratio_point(ctx.arr[num], ctx.arr[den], mask, sc)
        lo, hi = S.pct_ci(S.ratio_boot(ctx.arr[num], ctx.arr[den], mask, ctx.boot, sc))
        med = S.median_point(ctx.unit_vals[m], mask)
        mlo, mhi = S.pct_ci(S.median_boot(ctx.unit_vals[m], mask, ctx.boot))
        out.update({f"{m}_ratio": pt, f"{m}_lo": lo, f"{m}_hi": hi,
                    f"{m}_median_unit": med, f"{m}_median_lo": mlo, f"{m}_median_hi": mhi})
    return out


def build_variants(units: dict, B: int, seed: int) -> dict[str, Ctx]:
    cr, ad = units["creative"], units["ad"]
    spec = {
        "creative_all": ("creative", cr),
        "creative_excl_LJ004": ("creative", cr[~cr.is_lj004]),
        "creative_min_evidence": ("creative", cr[~cr.low_evidence]),
        "ad_all": ("ad", ad),
        "ad_excl_LJ004": ("ad", ad[~ad.is_lj004]),
        "creative_brand_consistent": ("creative", cr[~cr.brand_label_contradiction]),
    }
    return {name: Ctx(name, unit, df, B, seed + i) for i, (name, (unit, df)) in enumerate(spec.items())}


VARIANT_NOTES = {
    "creative_all": "PRIMARY: 97 unique creatives (duplicate-video ads collapsed)",
    "creative_excl_LJ004": "sensitivity: primary without LJ-004 (30.3% of revenue)",
    "creative_min_evidence": f"sensitivity: creatives with spend>={MIN_EVIDENCE_SPEND} and purchases>={MIN_EVIDENCE_PURCHASES}",
    "ad_all": "comparison: 100 ads as delivered (3 videos counted twice)",
    "ad_excl_LJ004": "comparison: 100 ads without LJ-004",
    "creative_brand_consistent": "brand attributes only: creatives without contradictory brand labels",
}


# ---------------------------------------------------------------- baseline
def baseline(ctxs: dict[str, Ctx]):
    rows, js = [], {}
    for name, c in ctxs.items():
        s = group_summary(c, c.all_mask(), BASELINE_METRICS)
        rows.append({"variant": name, "unit": c.unit, "note": VARIANT_NOTES[name], **s})
        js[name] = {
            "unit": c.unit, "note": VARIANT_NOTES[name], "n_units": s["n_units"],
            "totals": {k: s[k] for k in ("spend_inr", "revenue_inr", "purchases", "link_clicks", "impressions")},
            "metrics": {m: {"ratio_of_sums": s[f"{m}_ratio"], "ci95": [s[f"{m}_lo"], s[f"{m}_hi"]],
                            "median_per_unit": s[f"{m}_median_unit"],
                            "median_ci95": [s[f"{m}_median_lo"], s[f"{m}_median_hi"]]}
                        for m in BASELINE_METRICS},
        }
    return pd.DataFrame(rows), js


def product_form_tables(ctxs):
    perf, funnel, contrasts = [], [], []
    for name, c in ctxs.items():
        if name == "creative_brand_consistent":
            continue
        for lvl in ["ALL"] + sorted(set(c.pf)):
            mask = c.all_mask() if lvl == "ALL" else (c.pf == lvl)
            base = {"variant": name, "unit": c.unit, "product_form": lvl}
            perf.append({**base, **group_summary(c, mask, BASELINE_METRICS)})
            funnel.append({**base, **group_summary(c, mask, FUNNEL_METRICS)})
        num, den, _ = METRIC_DEFS["roas"]
        forms = sorted(set(c.pf))
        for i, a in enumerate(forms):
            for b in forms[i + 1:]:
                da = S.ratio_boot(c.arr[num], c.arr[den], c.pf == a, c.boot) - S.ratio_boot(c.arr[num], c.arr[den], c.pf == b, c.boot)
                pa = S.ratio_point(c.arr[num], c.arr[den], c.pf == a) - S.ratio_point(c.arr[num], c.arr[den], c.pf == b)
                lo, hi = S.pct_ci(da)
                contrasts.append({"variant": name, "form_a": a, "form_b": b, "roas_diff_a_minus_b": pa,
                                  "lo": lo, "hi": hi, "n_a": int((c.pf == a).sum()), "n_b": int((c.pf == b).sum())})
    return pd.DataFrame(perf), pd.DataFrame(funnel), pd.DataFrame(contrasts)


# ----------------------------------------------------------- concentration
def gini(x):
    x = np.sort(np.asarray(x, float))
    cum = np.cumsum(x)
    return float((len(x) + 1 - 2 * (cum / cum[-1]).sum()) / len(x))


def concentration(ctxs):
    rows, lor, loo = [], [], []
    for name in ("creative_all", "ad_all"):
        c = ctxs[name]
        d = c.df
        for col in ("revenue_inr", "spend_inr", "purchases"):
            v = d[col].to_numpy(float)
            sv = np.sort(v)[::-1]
            tot = v.sum()
            sh = v / tot
            rows.append({"variant": name, "metric": col, "n_units": len(v), "total": tot,
                         "top1_share": sv[:1].sum() / tot, "top3_share": sv[:3].sum() / tot,
                         "top5_share": sv[:5].sum() / tot, "top10_share": sv[:10].sum() / tot,
                         "gini": gini(v), "effective_n_units": float(1 / (sh ** 2).sum())})
        v = np.sort(d.revenue_inr.to_numpy(float))
        cum = np.concatenate([[0], np.cumsum(v)]) / v.sum()
        for i, y in enumerate(cum):
            lor.append({"variant": name, "cum_unit_share": i / len(v), "cum_revenue_share": float(y)})
        order = d.sort_values("revenue_inr", ascending=False).head(5)
        tot_roas = d.revenue_inr.sum() / d.spend_inr.sum()
        for _, r in order.iterrows():
            rest = d[d.ad_id != r.ad_id]
            row = {"variant": name, "excluded_unit": r.ad_id, "excluded_revenue_share": r.revenue_inr / d.revenue_inr.sum(),
                   "excluded_spend_share": r.spend_inr / d.spend_inr.sum(), "roas_all": tot_roas,
                   "roas_without_unit": rest.revenue_inr.sum() / rest.spend_inr.sum()}
            for pf in sorted(set(d.product_form)):
                sub = rest[rest.product_form == pf]
                row[f"roas_without_unit__{pf}"] = sub.revenue_inr.sum() / sub.spend_inr.sum()
            loo.append(row)
    return pd.DataFrame(rows), pd.DataFrame(lor), pd.DataFrame(loo)


# ----------------------------------------------------------- attribute scan
def source_type(attr: str) -> str:
    base = attr
    if attr.startswith("ml:"):
        base = attr[3:]
    base = {"duration_bin": "duration_s", "language_group": "language",
            "child_present": "child_on_screen", "cta_group": "cta_type"}.get(base, base)
    return "ai_label" if base in ADS["ai_labelled"] else "platform_reported"


def iter_specs(df: pd.DataFrame):
    single = [c for c in ADS["categorical"] if c != "product_form"] + DERIVED_ATTRS
    for col in single:
        valid = df[col].notna().to_numpy()
        for lvl in sorted(df[col].dropna().unique()):
            yield col, str(lvl), ("derived" if col in DERIVED_ATTRS else "single"), (df[col] == lvl).to_numpy(), valid
    for col in [c for c in df.columns if c.startswith("ml:")]:
        attr, lvl = col.split("=", 1)
        yield attr, lvl, "multilabel", df[col].to_numpy(bool), np.ones(len(df), bool)


def _split_key(mask: np.ndarray, rest: np.ndarray) -> tuple:
    """Order-free identity of a level-vs-rest split: identical sets *and* mirror images share a key."""
    h = [hashlib.md5(np.packbits(x).tobytes()).hexdigest() for x in (mask, rest)]
    return tuple(sorted(h))


def scan_variant(ctx: Ctx, only_attrs: list[str] | None = None) -> pd.DataFrame:
    rows = []
    seen: dict[tuple, str] = {}
    for attr, lvl, kind, mask, universe in iter_specs(ctx.df):
        if only_attrs and attr not in only_attrs:
            continue
        n1, n0 = int(mask.sum()), int((universe & ~mask).sum())
        if n1 < MIN_LEVEL_N or n0 < MIN_LEVEL_N:
            continue
        rest = universe & ~mask
        key = _split_key(mask & universe, rest)
        dup_of = seen.setdefault(key, f"{attr}={lvl}")
        dup_of = "" if dup_of == f"{attr}={lvl}" else dup_of
        spend = ctx.arr["spend_inr"]
        for m in EFFECT_METRICS:
            num, den, sc = METRIC_DEFS[m]
            x, y = ctx.arr[num], ctx.arr[den]
            r1 = S.ratio_point(x, y, mask, sc)
            lo, hi = S.pct_ci(S.ratio_boot(x, y, mask, ctx.boot, sc))
            r0 = S.ratio_point(x, y, rest, sc)
            e = S.std_diff(x, y, mask, ctx.boot, scale=sc, universe=universe)
            if m in MEDIAN_EFFECT_METRICS:
                med = S.median_point(ctx.unit_vals[m], mask)
                mlo, mhi = S.pct_ci(S.median_boot(ctx.unit_vals[m], mask, ctx.boot))
            else:
                med = mlo = mhi = np.nan
            notes = []
            if n1 < LOW_N:
                notes.append("low_n")
            if e["strata_used"] == 0:
                notes.append("not_estimable_within_product_form")
            if attr in BRAND_ATTRS:
                notes.append("contradictory_brand_labels")
            rows.append({
                "variant": ctx.name, "unit": ctx.unit, "metric": m, "attribute": attr, "level": lvl, "kind": kind,
                "source_type": source_type(attr), "duplicate_of": dup_of,
                "n_level": n1, "n_rest": n0, "level_spend_share": float(spend[mask].sum() / spend[universe].sum()),
                "ratio_level": r1, "ratio_level_lo": lo, "ratio_level_hi": hi, "ratio_rest": r0,
                "raw_diff": r1 - r0 if np.isfinite(r1) and np.isfinite(r0) else np.nan,
                "median_level": med, "median_level_lo": mlo, "median_level_hi": mhi,
                "median_rest": S.median_point(ctx.unit_vals[m], rest),
                "ctrl_diff": e["diff"], "ctrl_lo": e["lo"], "ctrl_hi": e["hi"], "p_boot": e["p"],
                "strata_used": e["strata_used"], "strata_sign_consistent": e["sign_consistent"],
                "notes": ";".join(notes),
            })
    return pd.DataFrame(rows)


def scan_all(ctxs):
    parts = []
    for name, c in ctxs.items():
        parts.append(scan_variant(c, only_attrs=BRAND_ATTRS if name == "creative_brand_consistent" else None))
    eff = pd.concat(parts, ignore_index=True)
    eff["test_id"] = eff.attribute + "=" + eff.level
    eff["q_bh"] = np.nan
    # BH is applied to UNIQUE splits only: identical / mirror-image levels are one test, not several.
    for (v, m), idx in eff.groupby(["variant", "metric"]).groups.items():
        sub = eff.loc[idx]
        uniq = sub[sub.duplicate_of == ""]
        q = S.bh_qvalues(uniq.p_boot)
        eff.loc[uniq.index, "q_bh"] = q.values
        dups = sub[sub.duplicate_of != ""]
        lookup = pd.Series(q.values, index=uniq.test_id.values)
        eff.loc[dups.index, "q_bh"] = dups.duplicate_of.map(lookup).values
    return eff


def stability(eff: pd.DataFrame) -> pd.DataFrame:
    key = ["metric", "attribute", "level"]
    base = eff[eff.variant == PRIMARY].copy()
    for v in STABILITY_VARIANTS:
        o = eff[eff.variant == v][key + ["ctrl_diff", "ctrl_lo", "ctrl_hi", "n_level"]]
        o = o.rename(columns={"ctrl_diff": f"diff__{v}", "ctrl_lo": f"lo__{v}", "ctrl_hi": f"hi__{v}", "n_level": f"n__{v}"})
        base = base.merge(o, on=key, how="left")

    def same_sign(r, v):
        d = r[f"diff__{v}"]
        return bool(np.isfinite(d) and np.isfinite(r.ctrl_diff) and np.sign(d) == np.sign(r.ctrl_diff))

    def excl0(r, v):
        lo, hi = r[f"lo__{v}"], r[f"hi__{v}"]
        return bool(np.isfinite(lo) and (lo > 0 or hi < 0))

    base["ci_excludes_0_primary"] = (base.ctrl_lo > 0) | (base.ctrl_hi < 0)
    for v in STABILITY_VARIANTS:
        base[f"same_sign__{v}"] = base.apply(lambda r, v=v: same_sign(r, v), axis=1)
    base["ci_excludes_0__creative_excl_LJ004"] = base.apply(lambda r: excl0(r, "creative_excl_LJ004"), axis=1)
    all_same = base[[f"same_sign__{v}" for v in STABILITY_VARIANTS]].all(axis=1)

    def status(r):
        if r.attribute in BRAND_ATTRS:
            return "caution_brand_labels"
        if not np.isfinite(r.ctrl_diff):
            return "not_estimable"
        if not r.ci_excludes_0_primary:
            return "no_clear_effect"
        robust = (r.q_bh < 0.10 and r.n_level >= LOW_N and r.strata_used >= 2
                  and r["ci_excludes_0__creative_excl_LJ004"] and all_same.loc[r.name])
        if robust:
            return "stable_candidate"
        if all_same.loc[r.name]:
            return "directional_only"
        return "unstable_across_variants"

    base["status"] = base.apply(status, axis=1)
    return base


def hypothesis_table(stab: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for hid, attr, lvl, metrics in HYPOTHESES:
        for m in metrics:
            r = stab[(stab.attribute == attr) & (stab.level == lvl) & (stab.metric == m)]
            if r.empty:
                rows.append({"hypothesis": hid, "attribute": attr, "level": lvl, "metric": m, "status": "level_too_small_or_absent"})
            else:
                rows.append({"hypothesis": hid, **r.iloc[0].to_dict()})
    return pd.DataFrame(rows)


# ------------------------------------------------------------ correlations
def correlations(ctxs, B=1000):
    rows = []
    for name in ("creative_all", "creative_excl_LJ004"):
        c = ctxs[name]
        for k, (xv, yv) in enumerate(CORR_PAIRS):
            x = c.df[xv].to_numpy(float)
            y = c.df[yv].to_numpy(float)
            for r in S.spearman_within(x, y, c.boot.strata, B=B, seed=S.SEED + 100 + k):
                s = r["stratum"]
                label = s if s == "pooled_within" else sorted(set(c.pf))[int(s)]
                rows.append({"variant": name, "x": xv, "y": yv, "stratum": label,
                             "n": r["n"], "spearman_rho": r["rho"], "lo": r["lo"], "hi": r["hi"],
                             "x_source": source_type(xv) if xv in ADS["ai_labelled"] else "platform_reported",
                             "y_source": "platform_reported"})
    return pd.DataFrame(rows)


# ----------------------------------------------------------- label quality
def label_quality(units, dup_check):
    out = []
    for uname, d in units.items():
        ct = pd.crosstab(d.brand_said_aloud, d.brand_first_said.fillna("MISSING"))
        for a in ct.index:
            for b in ct.columns:
                out.append({"unit": uname, "check": "brand_said_aloud_x_brand_first_said",
                            "a": a, "b": b, "n": int(ct.loc[a, b])})
        out.append({"unit": uname, "check": "brand_contradiction_total", "a": "said_aloud=no", "b": "first=under_3s",
                    "n": int(d.brand_label_contradiction.sum())})
        for col in ["hook_type", "ad_format", "story_structure", "child_role", "brand_first_said", "creator_age"]:
            out.append({"unit": uname, "check": "missing_label", "a": col, "b": "", "n": int(d[col].isna().sum())})
    out.extend({"unit": "ad", "check": "duplicate_video_label_equality", "a": r.ad_ids,
                "b": r.labels_differing, "n": r.n_ads} for r in dup_check.itertuples())
    return pd.DataFrame(out)


def provenance_catalog(ads: pd.DataFrame) -> pd.DataFrame:
    notes = {
        "stopped_date": "only 8 distinct values; looks like snapshot dates, not true stops",
        "days_live": "disagrees with launch/stopped dates by 1 day for 74/100 ads",
        "brand_said_aloud": "contradicts brand_first_said in 18/100 ads", "brand_first_said": "see brand_said_aloud",
        "ad_copy": "campaign-level text (17 distinct values)", "duration_s": "likely measured from video file; unverified",
    }
    rows = []
    for c in ads.columns:
        if c in OUTCOME_COLS:
            st, role = "platform_reported", "outcome"
        elif c in ("ad_id", "meta_ad_library_id", "video_url", "launch_date", "stopped_date", "days_live", "ad_copy"):
            st, role = "platform_reported", "id_or_delivery_context"
        else:
            st, role = ("ai_label", "predictor") if c in ADS["ai_labelled"] else ("unknown", "other")
        rows.append({"column": c, "source_type": st, "analysis_role": role, "caution": notes.get(c, "")})
    return pd.DataFrame(rows)


# -------------------------------------------------------------------- io
def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def write_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(obj), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format="%.6g")


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(raw_dir: Path, out_dir: Path, processed_dir: Path, B: int = S.B_DEFAULT, seed: int = S.SEED):
    raw_dir, out_dir, processed_dir = Path(raw_dir), Path(out_dir), Path(processed_dir)
    ads = load_ads(raw_dir)
    units, dup_check, tokens = prepare_units(ads)
    ctxs = build_variants(units, B, seed)
    tdir, jdir = out_dir / "tables", out_dir / "json"

    # processed unit tables
    write_csv(units["creative"].drop(columns=[c for c in units["creative"].columns if c.startswith("ml:")]), processed_dir / "creatives.csv")
    write_csv(units["ad"].drop(columns=[c for c in units["ad"].columns if c.startswith("ml:")]), processed_dir / "ads_enriched.csv")

    base_df, base_js = baseline(ctxs)
    write_csv(base_df, tdir / "baseline_by_variant.csv")
    perf, funnel, contrasts = product_form_tables(ctxs)
    write_csv(perf, tdir / "product_form_performance.csv")
    write_csv(funnel, tdir / "funnel_by_product_form.csv")
    write_csv(contrasts, tdir / "product_form_roas_contrasts.csv")
    conc, lor, loo = concentration(ctxs)
    write_csv(conc, tdir / "concentration.csv")
    write_csv(lor, tdir / "concentration_lorenz.csv")
    write_csv(loo, tdir / "concentration_leave_one_out.csv")

    eff = scan_all(ctxs)
    write_csv(eff, tdir / "attribute_effects_all_variants.csv")
    stab = stability(eff)
    write_csv(stab, tdir / "attribute_effects_stability.csv")
    write_csv(hypothesis_table(stab), tdir / "hypothesis_results.csv")
    write_csv(correlations(ctxs), tdir / "correlations_within_product_form.csv")
    write_csv(label_quality(units, dup_check), tdir / "label_quality.csv")
    write_csv(provenance_catalog(ads), tdir / "column_provenance.csv")

    # JSON
    uniq = stab[stab.duplicate_of == ""]
    dups = (stab[stab.duplicate_of != ""].assign(t=lambda d: d.attribute + "=" + d.level)
            .groupby(["metric", "duplicate_of"]).t.apply(list).to_dict())
    sig = uniq[uniq.status.isin(["stable_candidate", "directional_only", "caution_brand_labels"]) & uniq.ci_excludes_0_primary].copy()
    sig["also_appears_as"] = [dups.get((m, t), []) for m, t in zip(sig.metric, sig.test_id)]
    keep = ["metric", "attribute", "level", "also_appears_as", "source_type", "n_level", "n_rest", "ctrl_diff", "ctrl_lo", "ctrl_hi",
            "diff__creative_excl_LJ004", "lo__creative_excl_LJ004", "hi__creative_excl_LJ004",
            "diff__creative_min_evidence", "diff__ad_all", "raw_diff", "p_boot", "q_bh", "strata_used", "status", "notes"]
    status_counts = uniq.groupby(["metric", "status"]).size().unstack(fill_value=0).to_dict("index")
    write_json({
        "primary_variant": PRIMARY,
        "interpretation_guardrails": [
            "Exploratory and observational: AI-generated labels, unvalidated; no causal claim.",
            "ctrl_diff = within-product_form difference (level minus rest) in the metric, denominator-weighted; 95% bootstrap CI.",
            "stable_candidate = CI excludes 0, BH q<0.10 (unique tests only), n_level>=10, >=2 product strata, same sign in all 4 other variants, and CI still excludes 0 without LJ-004. It means 'survived the sensitivity checks', not 'validated'.",
            "Effect SIZES can change a lot without LJ-004 (compare ctrl_diff with diff__creative_excl_LJ004).",
            "Many hook_rate signals describe overlapping sets of the same ads (e.g. child present, storytelling, skit); they are not independent evidence.",
            "Brand-mention attributes are never promoted: the underlying labels contradict each other.",
            "Identical or mirror-image levels are one test; see also_appears_as.",
        ],
        "unique_tests_primary": int(((uniq.status != "not_estimable")).sum() / max(uniq.metric.nunique(), 1)),
        "status_counts_by_metric_unique_tests": status_counts,
        "signals": sig[keep].sort_values(["status", "metric", "q_bh"]).to_dict("records"),
    }, jdir / "key_signals.json")
    write_json(base_js, jdir / "baseline_summary.json")
    write_json({"columns": provenance_catalog(ads).to_dict("records"),
                "multilabel_tokens_analysed": tokens, "min_token_support": MIN_TOKEN_SUPPORT}, jdir / "column_provenance.json")
    write_json({"variants": {k: {"n_units": c.n, "unit": c.unit, "note": VARIANT_NOTES[k]} for k, c in ctxs.items()}},
               jdir / "variants.json")

    outputs = sorted(p for p in list(tdir.glob("*.csv")) + list(jdir.glob("*.json")) if p.name != "run_manifest.json")
    write_json({
        "seed": seed, "bootstrap_B": B, "ci_level": 0.95, "min_level_n": MIN_LEVEL_N, "low_n_flag": LOW_N,
        "min_stratum_n": S.MIN_STRATUM_N, "stratification": "product_form",
        "versions": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "scipy": scipy.__version__},
        "inputs_sha256": {k: sha256(raw_dir / f) for k, f in FILES.items() if (raw_dir / f).exists()},
        "outputs_sha256": {p.name: sha256(p) for p in outputs},
    }, jdir / "run_manifest.json")
    return {"eff": eff, "stab": stab, "base": base_df}
