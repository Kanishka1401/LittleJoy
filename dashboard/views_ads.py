from __future__ import annotations

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from . import data as D
from .theme import (BUTTER, BUTTER_DEEP, DEEP_SAGE, HAIR, INK, IVORY, MUTED, SAGE, SAGE_MID, STONE, TERRA, kpi, note, page_header, plot, spread, style)

VARIANTS = {"creative_all": "All 97 creatives (primary)", "creative_excl_LJ004": "Excluding LJ-004 (96)",
            "creative_min_evidence": "Min-evidence only (85)"}
FORM_COLOR = {"milk_mix_powder": INK, "gummies": TERRA, "other": DEEP_SAGE}
FORM_LABEL = {"milk_mix_powder": "Milk-mix powder", "gummies": "Gummies", "other": "Other", "ALL": "All"}
RATE_METRICS = {"hook_rate": "Hook rate (3s views / impressions)", "hold_rate": "Hold rate (thruplays / 3s views)",
                "ctr_link": "Link CTR", "click_to_atc": "Click → add-to-cart", "atc_to_purchase": "Add-to-cart → purchase",
                "cvr_click": "Click → purchase (CVR)"}
METRIC_LABEL = {"hook_rate": "Hook rate", "cvr_click": "CVR", "ctr_link": "Link CTR", "roas": "ROAS", "aov": "AOV"}
STATUS_COLOR = {"stable_candidate": INK, "directional_only": BUTTER, "caution_brand_labels": TERRA}


def render():
    page_header("Ad intelligence",
                "What each product form earns, how concentrated revenue is, and which creative attributes show any signal. "
                "These are the completed analysis outputs, not recomputed here.",
                "Synthetic figures")
    a = D.ad_outputs()
    note("<b>Synthetic data.</b> The spend, revenue, ROAS and funnel figures on this page come from the assignment's synthetic ad dataset. "
         "They show how the analysis behaves and what it can and cannot support. They are not Little Joys' real campaign results.", warn=True)
    v = st.segmented_control("Analysis variant", list(VARIANTS), default="creative_all", format_func=VARIANTS.get,
                             help="Every figure below is a pre-computed output from reports/ad/. LJ-004 is 30% of revenue, so the sensitivity variants matter.")
    v = v or "creative_all"
    b = a["baseline"].set_index("variant").loc[v]
    cols = st.columns(6, gap="large")
    for col, (l, val, s, tg) in zip(cols, [
            ("Units", f"{int(b.n_units)}", "unique creatives", ""), ("Spend", D.compact(b.spend_inr), "", "synthetic"),
            ("Revenue", D.compact(b.revenue_inr), f"{int(b.purchases):,} purchases", "synthetic"),
            ("Blended ROAS", f"{b.roas_ratio:.2f}", f"CI {b.roas_lo:.2f} to {b.roas_hi:.2f}", "synthetic"),
            ("Median ROAS", f"{b.roas_median_unit:.2f}", f"CI {b.roas_median_lo:.2f} to {b.roas_median_hi:.2f}", "synthetic"),
            ("CPA", f"₹{b.cpa_ratio:,.0f}", f"CVR {b.cvr_click_ratio:.1%}", "synthetic")]):
        col.markdown(kpi(l, val, s, tag=tg), unsafe_allow_html=True)

    st.markdown('<div class="sp-rule"></div>', unsafe_allow_html=True)
    t1, t2, t3, t4, t5 = st.tabs(["Performance", "Concentration", "Creative signals", "Funnel and correlations", "Creative explorer"])

    with t1:
        pf = a["pf"][(a["pf"].variant == v)].copy()
        pf["label"] = pf.product_form.map(FORM_LABEL)
        c1, c2 = st.columns(2, gap="large")
        d = pf[pf.product_form != "ALL"]
        with c1:
            fig = go.Figure()
            fig.add_bar(x=d.label, y=d.roas_ratio, marker_color=[FORM_COLOR[f] for f in d.product_form], name="Blended ROAS", width=0.5,
                        error_y=dict(type="data", symmetric=False, array=d.roas_hi - d.roas_ratio, arrayminus=d.roas_ratio - d.roas_lo, color=TERRA, thickness=1.6),
                        customdata=np.c_[d.n_units, d.spend_inr], hovertemplate="<b>%{x}</b><br>ROAS %{y:.2f}<br>n=%{customdata[0]}, spend ₹%{customdata[1]:,.0f}<extra></extra>")
            fig.add_scatter(x=d.label, y=d.roas_median_unit, mode="markers", marker=dict(symbol="diamond", size=12, color=BUTTER, line=dict(width=1.2, color=INK)), name="Median per creative")
            fig.add_hline(y=1, line_dash="dot", line_color=MUTED, annotation_text="break-even", annotation_position="top right")
            style(fig, 400, title="ROAS by product form (95% bootstrap CI)", yaxis_title="ROAS")
            plot(fig)
        with c2:
            fig = go.Figure(go.Bar(x=d.label, y=d.spend_inr, name="Spend", marker_color=SAGE_MID))
            fig.add_bar(x=d.label, y=d.revenue_inr, name="Revenue", marker_color=INK)
            style(fig, 400, title="Spend vs revenue by product form (₹)", barmode="group", yaxis_title="₹")
            plot(fig)
        ct = a["contrasts"][a["contrasts"].variant == v] if "variant" in a["contrasts"] else a["contrasts"]
        if len(ct):
            ct = ct.assign(pair=ct.form_a.map(FORM_LABEL) + " − " + ct.form_b.map(FORM_LABEL))
            fig = go.Figure(go.Scatter(x=ct.roas_diff_a_minus_b, y=ct.pair, mode="markers", marker=dict(size=12, color=INK),
                                       error_x=dict(type="data", symmetric=False, array=ct.hi - ct.roas_diff_a_minus_b,
                                                    arrayminus=ct.roas_diff_a_minus_b - ct.lo, color=TERRA, thickness=1.6)))
            fig.add_vline(x=0, line_color=MUTED, line_dash="dot")
            style(fig, 240, title="Pairwise ROAS differences between forms (95% CI; all include 0 or barely exclude it)", xaxis_title="ROAS difference")
            plot(fig)
        note("Most of the apparent milk-mix advantage is LJ-004: switch the variant to <b>Excluding LJ-004</b> to see the gap shrink.")

    with t2:
        lz = a["lorenz"][a["lorenz"].variant == "creative_all"]
        cc = a["conc"].set_index(["variant", "metric"]).loc[("creative_all", "revenue_inr")]   # engine computes concentration for all creatives only
        if v != "creative_all":
            st.caption("Concentration is computed once, on all 97 creatives, so this tab does not change with the analysis variant.")
        c1, c2 = st.columns([1.2, 1], gap="large")
        with c1:
            fig = go.Figure()
            fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=STONE, dash="dot"), name="Equal share")
            fig.add_scatter(x=lz.cum_unit_share, y=lz.cum_revenue_share, mode="lines", fill="tozeroy", fillcolor="rgba(214,226,210,.65)",
                            line=dict(color=TERRA, width=2.8), name="Cumulative revenue (creatives sorted low to high)")
            style(fig, 400, title=f"Revenue Lorenz curve, Gini {cc.gini:.2f}", xaxis_title="Cumulative share of creatives", yaxis_title="Cumulative share of revenue")
            plot(fig)
        with c2:
            shares = {"Top 1": cc.top1_share, "Top 3": cc.top3_share, "Top 5": cc.top5_share, "Top 10": cc.top10_share}
            fig = go.Figure(go.Bar(x=list(shares), y=list(shares.values()), marker_color=[TERRA, INK, INK, SAGE_MID], width=0.55,
                                   text=[f"{s:.0%}" for s in shares.values()], textposition="outside"))
            style(fig, 400, title=f"Share of revenue. Effective units ≈ {cc.effective_n_units:.1f} of {int(cc.n_units)}", yaxis=dict(tickformat=".0%", range=[0, 0.8]))
            plot(fig)
        loo = a["loo"][a["loo"].variant == "creative_all"].head(8)
        fig = go.Figure(go.Bar(x=loo.excluded_unit, y=loo.roas_without_unit, marker_color=[TERRA] + [SAGE_MID] * (len(loo) - 1),
                               text=[f"{x:.2f}" for x in loo.roas_without_unit], textposition="outside"))
        fig.add_hline(y=loo.roas_all.iloc[0], line_dash="dot", line_color=MUTED, annotation_text=f"all creatives {loo.roas_all.iloc[0]:.2f}")
        style(fig, 320, title="Blended ROAS when one creative is removed (top-revenue creatives)", yaxis=dict(range=[0, 1.9], title="ROAS"))
        plot(fig)

    with t3:
        sig = a["signals"]
        note("<b>Read with care.</b> " + " ".join(a["guardrails"][:2]))
        c1, c2, c3 = st.columns([1, 1, 1.2], gap="large")
        metric = c1.selectbox("Outcome", [m for m in METRIC_LABEL if m in set(sig.metric)], format_func=METRIC_LABEL.get)
        statuses = sorted(sig.status.unique())
        chosen = c2.multiselect("Status", statuses, default=[s for s in statuses if s in ("stable_candidate", "directional_only")])
        topn = c3.slider("Show top N by effect size", 5, 30, 14)
        d = sig[(sig.metric == metric) & sig.status.isin(chosen)].copy()
        scale = 100 if metric in ("hook_rate", "cvr_click", "ctr_link") else 1
        unit = "percentage points" if scale == 100 else ("₹" if metric == "aov" else "ROAS units")
        d["lab"] = d.attribute.str.replace("_", " ") + " = " + d.level.astype(str)
        d = d.reindex(d.ctrl_diff.abs().sort_values(ascending=False).index).head(topn).iloc[::-1]
        if d.empty:
            st.info("No signals match these filters.")
        else:
            fig = go.Figure()
            for s, g in d.groupby("status"):
                fig.add_scatter(x=g.ctrl_diff * scale, y=g.lab, mode="markers", name=s.replace("_", " "),
                                marker=dict(size=12, color=STATUS_COLOR.get(s, MUTED), line=dict(width=1, color=INK)),
                                error_x=dict(type="data", symmetric=False, array=(g.ctrl_hi - g.ctrl_diff) * scale, arrayminus=(g.ctrl_diff - g.ctrl_lo) * scale,
                                             color=STATUS_COLOR.get(s, MUTED) if s != "directional_only" else BUTTER_DEEP, thickness=1.6),
                                customdata=np.c_[g.n_level, g.q_bh, g.source_type], hovertemplate="<b>%{y}</b><br>effect %{x:.2f}<br>n=%{customdata[0]}, q=%{customdata[1]:.3f}<extra></extra>")
            fig.add_vline(x=0, line_color=MUTED, line_dash="dot")
            style(fig, max(340, 28 * len(d) + 120), title=f"Effect on {METRIC_LABEL[metric]}: level vs rest, within product form ({unit}, 95% CI)", xaxis_title=unit)
            plot(fig)
            show = d.iloc[::-1][["lab", "status", "n_level", "n_rest", "ctrl_diff", "ctrl_lo", "ctrl_hi", "q_bh", "diff__creative_excl_LJ004", "notes"]].copy()
            show[["ctrl_diff", "ctrl_lo", "ctrl_hi", "diff__creative_excl_LJ004"]] *= scale
            st.dataframe(show.rename(columns={"lab": "Attribute = level", "ctrl_diff": "Effect", "ctrl_lo": "CI low", "ctrl_hi": "CI high",
                                              "diff__creative_excl_LJ004": "Effect w/o LJ-004", "q_bh": "q (BH)", "n_level": "n level", "n_rest": "n rest"}),
                         hide_index=True, width="stretch")

    with t4:
        c1, c2 = st.columns(2, gap="large")
        with c1:
            m = st.selectbox("Funnel stage", list(RATE_METRICS), format_func=RATE_METRICS.get)
            f = a["funnel"][(a["funnel"].variant == v) & (a["funnel"].product_form != "ALL")].copy()
            f["label"] = f.product_form.map(FORM_LABEL)
            fig = go.Figure(go.Bar(x=f.label, y=f[f"{m}_ratio"], marker_color=[FORM_COLOR[x] for x in f.product_form], width=0.5,
                                   error_y=dict(type="data", symmetric=False, array=f[f"{m}_hi"] - f[f"{m}_ratio"], arrayminus=f[f"{m}_ratio"] - f[f"{m}_lo"], color=TERRA, thickness=1.6)))
            style(fig, 360, title=RATE_METRICS[m] + " by product form", yaxis=dict(tickformat=".1%"))
            plot(fig)
        with c2:
            cr = a["corr"][(a["corr"].variant == "creative_all") & (a["corr"].stratum == "pooled_within")].copy()
            cr["pair"] = cr.x.str.replace("_", " ") + " ↔ " + cr.y.str.replace("_", " ")
            cr = cr.sort_values("spearman_rho")
            fig = go.Figure(go.Scatter(x=cr.spearman_rho, y=cr.pair, mode="markers",
                                       marker=dict(size=12, color=[DEEP_SAGE if (lo > 0) else TERRA if hi < 0 else STONE for lo, hi in zip(cr.lo, cr.hi)], line=dict(width=1, color=INK)),
                                       error_x=dict(type="data", symmetric=False, array=cr.hi - cr.spearman_rho, arrayminus=cr.spearman_rho - cr.lo, color=HAIR, thickness=2)))
            fig.add_vline(x=0, line_color=MUTED, line_dash="dot")
            style(fig, 360, title="Spearman ρ within product form (95% CI)", xaxis=dict(range=[-1, 1], title="ρ"))
            plot(fig)
        note("CVR ↔ ROAS is partly mechanical (conversion drives revenue). The informative pair is <b>hook rate ↔ ROAS</b>: near zero or negative.")

    with t5:
        cre = a["creatives"].copy()
        f1, f2, f3, f4 = st.columns(4, gap="large")
        forms = f1.multiselect("Product form", sorted(cre.product_form.dropna().unique()), default=sorted(cre.product_form.dropna().unique()))
        langs = f2.multiselect("Language", sorted(cre.language_group.dropna().unique()), default=sorted(cre.language_group.dropna().unique()))
        child = f3.selectbox("Child on screen", ["Any", "yes", "no"])
        prod = f4.multiselect("Production", sorted(cre.production.dropna().unique()), default=sorted(cre.production.dropna().unique()))
        d = cre[cre.product_form.isin(forms) & cre.language_group.isin(langs) & cre.production.isin(prod)]
        if child != "Any":
            d = d[d.child_present == child]
        d = d[d.spend_inr > 0]
        fig = px.scatter(d, x="spend_inr", y="roas", size="purchases", color="product_form", color_discrete_map=FORM_COLOR, log_x=True,
                         hover_name="creative_id", size_max=34, hover_data={"spend_inr": ":,.0f", "roas": ":.2f", "purchases": True, "ad_format": True,
                                                                          "language": True, "hook_type": True, "product_form": False},
                         labels={"spend_inr": "Spend (₹, log)", "roas": "ROAS"})
        fig.update_traces(marker=dict(line=dict(width=1, color=IVORY), opacity=.85))
        fig.add_hline(y=1, line_dash="dot", line_color=MUTED)
        for r in d[d.is_lj004].itertuples():
            fig.add_annotation(x=np.log10(r.spend_inr), y=r.roas, text="LJ-004", showarrow=True, arrowhead=2, ax=30, ay=-30, font=dict(color=TERRA, size=12))
        style(fig, 460, title=f"{len(d)} creatives. Bubble size is purchases.")
        plot(fig)
        show = d.sort_values("revenue_inr", ascending=False)[["creative_id", "product_form", "ad_format", "hook_type", "language", "child_present", "production",
                                                              "spend_inr", "purchases", "revenue_inr", "roas", "low_evidence"]]
        st.dataframe(show, hide_index=True, width="stretch", column_config={
            "spend_inr": st.column_config.NumberColumn("Spend ₹", format="%d"), "revenue_inr": st.column_config.NumberColumn("Revenue ₹", format="%d"),
            "roas": st.column_config.NumberColumn("ROAS", format="%.2f"), "low_evidence": st.column_config.CheckboxColumn("Low evidence")})
