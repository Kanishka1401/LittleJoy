"""Robust, seeded statistics for small-n marketing data.

Design rules
- Ratios (ROAS, CVR, ...) are aggregated as ratio-of-sums, never mean-of-ratios.
- Per-unit summaries use medians.
- Uncertainty = percentile bootstrap, resampling units *within product_form strata*
  (so stratum sizes are fixed and product mix cannot drive the interval).
- "Controlled" effects are within-stratum differences (level vs rest inside each
  product_form), combined with fixed den-share weights (direct standardisation).
- All randomness flows from an explicit seed -> bit-reproducible output.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import rankdata

B_DEFAULT = 2000
SEED = 20261104
MIN_STRATUM_N = 3


@dataclass
class Boot:
    idx: np.ndarray        # (B, n) resampled unit indices
    counts: np.ndarray     # (B, n) multiplicity of each unit per replicate
    strata: np.ndarray     # (n,) stratum codes


def make_boot(strata: np.ndarray, B: int = B_DEFAULT, seed: int = SEED) -> Boot:
    rng = np.random.default_rng(seed)
    n = len(strata)
    idx = np.empty((B, n), dtype=np.int32)
    col = 0
    for s in np.unique(strata):
        members = np.flatnonzero(strata == s)
        m = len(members)
        draws = rng.integers(0, m, size=(B, m))
        idx[:, col:col + m] = members[draws]
        col += m
    counts = np.zeros((B, n), dtype=np.int32)
    np.add.at(counts, (np.repeat(np.arange(B), n), idx.ravel()), 1)
    return Boot(idx, counts, strata)


def pct_ci(arr: np.ndarray, level: float = 0.95):
    a = arr[np.isfinite(arr)]
    if len(a) < 10:
        return (np.nan, np.nan)
    lo, hi = np.percentile(a, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return (float(lo), float(hi))


def ratio_point(num, den, mask, scale=1.0):
    d = den[mask].sum()
    return float(num[mask].sum() / d * scale) if d > 0 else np.nan


def ratio_boot(num, den, mask, boot: Boot, scale=1.0) -> np.ndarray:
    n_ = boot.counts @ (num * mask)
    d_ = boot.counts @ (den * mask)
    out = np.full(len(d_), np.nan)
    ok = d_ > 0
    out[ok] = n_[ok] / d_[ok] * scale
    return out


def median_point(vals, mask):
    v = vals[mask]
    v = v[np.isfinite(v)]
    return float(np.median(v)) if len(v) else np.nan


def median_boot(vals, mask, boot: Boot) -> np.ndarray:
    v = vals[boot.idx]
    m = mask[boot.idx]
    arr = np.where(m & np.isfinite(v), v, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(arr, axis=1)


def std_diff(num, den, mask, boot: Boot, min_n: int = MIN_STRATUM_N, scale=1.0, universe=None):
    """Within-stratum (level - rest) difference in a ratio metric, den-weighted across strata.

    `universe` limits the comparison group (e.g. excludes units whose label is missing).
    Returns dict(diff, lo, hi, p, strata_used, sign_consistent).
    """
    strata = boot.strata
    rest = ~mask if universe is None else (universe & ~mask)
    keep, w, d0, dB = [], [], [], []
    for s in np.unique(strata):
        sm = strata == s
        if (sm & mask).sum() < min_n or (sm & rest).sum() < min_n:
            continue
        r1 = ratio_point(num, den, sm & mask, scale)
        r0 = ratio_point(num, den, sm & rest, scale)
        if not (np.isfinite(r1) and np.isfinite(r0)):
            continue
        keep.append(s)
        w.append(den[sm & (mask | rest)].sum())
        d0.append(r1 - r0)
        dB.append(ratio_boot(num, den, sm & mask, boot, scale) - ratio_boot(num, den, sm & rest, boot, scale))
    if not keep:
        return dict(diff=np.nan, lo=np.nan, hi=np.nan, p=np.nan, strata_used=0, sign_consistent=0)
    w = np.array(w, float)
    d0 = np.array(d0)
    D = np.column_stack(dB)
    valid = np.isfinite(D)
    wb = (valid * w).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        diff_b = np.where(valid, D, 0.0).dot(w) / np.where(wb > 0, wb, np.nan)
    diff = float((d0 * w).sum() / w.sum())
    lo, hi = pct_ci(diff_b)
    fb = diff_b[np.isfinite(diff_b)]
    if len(fb) >= 10:
        p = max(2 * min((fb <= 0).mean(), (fb >= 0).mean()), 1.0 / (len(fb) + 1))
    else:
        p = np.nan
    sign_cons = int((np.sign(d0) == np.sign(diff)).sum()) if diff != 0 else 0
    return dict(diff=diff, lo=lo, hi=hi, p=float(p), strata_used=len(keep), sign_consistent=sign_cons)


def bh_qvalues(p: pd.Series) -> pd.Series:
    """Benjamini–Hochberg adjusted p-values (NaN-safe)."""
    q = pd.Series(np.nan, index=p.index, dtype=float)
    ok = p.notna()
    pv = p[ok].values
    m = len(pv)
    if m == 0:
        return q
    order = np.argsort(pv)
    ranked = pv[order] * m / (np.arange(m) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(ranked, 1.0)
    q[ok] = out
    return q


def spearman_within(x, y, strata, B=1000, seed=SEED, min_n=8):
    """Spearman rho within each stratum + n-weighted pooled-within rho, with bootstrap CIs."""
    rng = np.random.default_rng(seed)
    rows, rho0, ns, rhoB = [], [], [], []
    for s in np.unique(strata):
        m = np.flatnonzero((strata == s) & np.isfinite(x) & np.isfinite(y))
        if len(m) < min_n:
            continue
        xs, ys = x[m], y[m]
        r0 = float(np.corrcoef(rankdata(xs), rankdata(ys))[0, 1])
        draws = rng.integers(0, len(m), size=(B, len(m)))
        rx = rankdata(xs[draws], axis=1)
        ry = rankdata(ys[draws], axis=1)
        rx -= rx.mean(axis=1, keepdims=True)
        ry -= ry.mean(axis=1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            rb = (rx * ry).sum(axis=1) / np.sqrt((rx ** 2).sum(axis=1) * (ry ** 2).sum(axis=1))
        lo, hi = pct_ci(rb)
        rows.append(dict(stratum=s, n=len(m), rho=r0, lo=lo, hi=hi))
        rho0.append(r0)
        ns.append(len(m))
        rhoB.append(rb)
    if rows:
        w = np.array(ns, float)
        pooled = float(np.dot(rho0, w) / w.sum())
        pb = np.nansum(np.column_stack(rhoB) * w, axis=1) / w.sum()
        lo, hi = pct_ci(pb)
        rows.append(dict(stratum="pooled_within", n=int(w.sum()), rho=pooled, lo=lo, hi=hi))
    return rows
