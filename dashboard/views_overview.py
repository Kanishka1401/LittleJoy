from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from . import data as D
from .theme import (HAIR, INK, STONE, TERRA, badge, chip, creator_row, dim_legend, esc, kpi, note, page_header, plot, spread, style,
                    table_html)


def finding(title: str, desc: str) -> str:
    return f'<div class="fd"><div class="fd-t">{title}</div><div class="fd-d">{desc}</div></div>'


def _sentence(text: str, prefix: str) -> str:
    """Pick one sentence of the engine's own explanation text (no wording is added)."""
    for s in str(text).split(". "):
        if s.strip().startswith(prefix):
            return s.strip().rstrip(".") + "."
    return ""


def render():
    c, a, raw = D.creator_outputs(), D.ad_outputs(), D.raw_creator_data()
    rk = c["ranking"].set_index("creator_id")
    base = a["baseline"].set_index("variant")
    b, bx = base.loc["creative_all"], base.loc["creative_excl_LJ004"]
    conc = a["conc"].set_index(["variant", "metric"]).loc[("creative_all", "revenue_inr")]
    corr = a["corr"][(a["corr"].variant == "creative_all") & (a["corr"].stratum == "pooled_within")].set_index(["x", "y"])
    n_dem = int(c["demo"].has_demographics.sum())
    n_posts = len(raw["posts"])
    top = rk.sort_values("rank").head(5)
    lead = top.handle.iloc[0]

    page_header(f"@{lead} leads the shortlist, and one ad carries the ad account",
                "What the advertising data says works, which creators fit Little Joys best, and how far to trust each conclusion.",
                "Exploratory", long=True)

    cols = st.columns(6, gap="large")
    items = [("Creators analysed", "20", f"{n_posts} posts, 2022–2026", ""),
             ("Ad creatives", f"{int(b.n_units)}", "100 ads, 3 duplicate videos merged", ""),
             ("Ad spend", D.compact(b.spend_inr), f"{int(b.purchases):,} purchases", "synthetic"),
             ("Blended ROAS", f"{b.roas_ratio:.2f}", f"95% CI {b.roas_lo:.2f} to {b.roas_hi:.2f}, median {b.roas_median_unit:.2f}", "synthetic"),
             ("Audience data", f"{n_dem} of 20", "creators with demographics", ""),
             ("Top creator score", f"{rk.composite_score.max():.1f}", f"@{lead}", "")]
    for col, (l, v, s, tg) in zip(cols, items):
        col.markdown(kpi(l, v, s, tag=tg), unsafe_allow_html=True)

    # ------------------------------------------------------------ shortlist
    weights = D.CA.DIMENSION_WEIGHTS
    labels = {d: D.DIM_SHORT[d] for d in D.DIMS}
    with spread("The shortlist", "Bar length is the composite score out of 100. Each colour is what one criterion contributed. The bracket under a bar is the 90% bootstrap interval."):
        rows = "".join(creator_row(int(r["rank"]), r.handle, cid, r.composite_score, {d: r[f"contrib_{d}"] for d in D.DIMS}, labels,
                                   r.confidence_level, p_top5=r.p_top5, lo=r.score_p05, hi=r.score_p95, lead=(i == 0))
                       for i, (cid, r) in enumerate(top.iterrows()))
        st.markdown(dim_legend(labels, weights) + rows, unsafe_allow_html=True)
        gap = top.composite_score.iloc[1] - top.composite_score.iloc[4]
        n6 = rk.sort_values("rank").iloc[5]
        note(f"<b>How firm is this?</b> @{esc(lead)} leads clearly. Ranks 2 to 5 sit within {gap:.1f} points of each other and of "
             f"#6 (@{esc(n6.handle)}, {n6.composite_score:.1f}); treat them as a shortlist. Open <i>Creator shortlist</i> to re-weight the criteria.")

    # ------------------------------------------------------------ recommendations
    with spread("Who to approach", "Taken from the creator engine's own explanation for each of the five."):
        html = ""
        for t in c["top5"]:
            r = rk.loc[t["creator_id"]]
            strong = _sentence(t["explanation"], "Strongest vs cohort")
            weak = _sentence(t["explanation"], "Weakest vs cohort")
            risks = "".join(chip(f.replace("_", " "), risk=True) for f in str(t["flags"]).split("; ") if "competitor" in f)
            html += (f'<div class="fd"><div><div class="fd-t">#{int(r["rank"])} @{esc(t["handle"])}</div><div style="margin-top:.45rem">{badge(t["confidence"])}</div></div>'
                     f'<div class="fd-d">{esc(strong)} {esc(weak)}<div style="margin-top:.4rem">{risks}</div></div></div>')
        st.markdown(html, unsafe_allow_html=True)

    # ------------------------------------------------------------ findings
    with spread("Key findings"):
        hook = corr.loc[("hook_rate", "roas")]
        ctr = corr.loc[("ctr_link", "roas")]
        stable = a["stability"][a["stability"].status == "stable_candidate"]
        n_hook = int((stable.metric == "hook_rate").sum())
        st.markdown("".join([
            finding("One ad carries the account",
                    f"LJ-004 earns {conc.top1_share:.0%} of revenue on 9% of spend. Blended ROAS is {b.roas_ratio:.2f}, but {bx.roas_ratio:.2f} without it; "
                    f"the median creative ({b.roas_median_unit:.2f}) is near break-even. These are synthetic figures."),
            finding("Attention is not sales",
                    f"Within product forms, hook rate vs ROAS is ρ = {hook.spearman_rho:+.2f} (CI {hook.lo:+.2f} to {hook.hi:+.2f}); "
                    f"link CTR vs ROAS is {ctr.spearman_rho:+.2f}. Optimising for 3-second views would not reliably raise returns."),
            finding("Creative signals mostly move attention",
                    f"{len(stable)} attribute effects survive the stability checks, {n_hook} of them on hook rate (e.g. a child in the first 3 s). "
                    "Few survive for purchases, and all are unvalidated AI labels."),
            finding("A shortlist, not a podium",
                    f"@{esc(lead)} is robustly first (P(top-5) {top.p_top5.iloc[0]:.0%}). Profiles differ: some win on relevance, others on engagement."),
            finding("Audience data is the biggest gap",
                    f"Only {n_dem} of 20 creators have demographics. The rest are scored on a content-targeting proxy, never penalised, but with lower evidence coverage."),
        ]), unsafe_allow_html=True)

    # ------------------------------------------------------------ all 20
    with spread("All 20 creators", "Composite score with a 90% bootstrap interval from resampling posts. Dark marks are the top five."):
        d = rk.sort_values("composite_score")
        fig = go.Figure(go.Scatter(
            y=d.handle, x=d.composite_score, mode="markers",
            marker=dict(size=11, color=[INK if rnk <= 5 else STONE for rnk in d["rank"]], line=dict(width=0)),
            error_x=dict(type="data", symmetric=False, array=d.score_p95 - d.composite_score, arrayminus=d.composite_score - d.score_p05,
                         color=TERRA, thickness=1.6, width=0),
            customdata=d[["rank", "confidence_level"]],
            hovertemplate="<b>%{y}</b><br>Score %{x:.1f}, rank %{customdata[0]}<br>%{customdata[1]} confidence<extra></extra>"))
        style(fig, 580, xaxis=dict(range=[30, 85], title="Composite score"), yaxis=dict(title="", gridcolor=HAIR), margin=dict(l=10, r=14, t=6, b=10))
        plot(fig)

    # ------------------------------------------------------------ coverage
    with spread("Dataset coverage", "What each file contains and what it can support."):
        st.markdown(table_html(["Dataset", "Rows", "What it supports"], [
            ["creators.csv", 20, "Profile, persona, followers (platform-scraped; persona prose is AI-generated)"],
            ["creator_posts.csv", n_posts, "Engagement, content mix, sponsorship, windows (counts are platform-scraped; labels are AI)"],
            ["creator_audience.csv", n_dem, "Demographics for CR-14, CR-15, CR-20 only; CR-14 is a Facebook audience"],
            ["ads.csv (97 unique creatives)", 100, "Spend and ROAS (synthetic for this assignment); creative attributes are AI labels; no creator key"]]),
            unsafe_allow_html=True)
