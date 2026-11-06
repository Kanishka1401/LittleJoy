from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from . import data as D
from .theme import DIM_COLORS, HAIR, INK, IVORY, SAGE, creator_row, dim_legend, note, page_header, plot, section, style
from .views_creators import radar

PRESETS = {
    "Brief (default)": dict(zip(D.DIMS, [25, 20, 20, 20, 15])),
    "Equal": dict(zip(D.DIMS, [20] * 5)),
    "Relevance-led": dict(zip(D.DIMS, [40, 15, 15, 15, 15])),
    "Performance-led": dict(zip(D.DIMS, [15, 40, 15, 20, 10])),
    "Brand-safe": dict(zip(D.DIMS, [20, 10, 20, 35, 15])),
}


def _set_preset(name: str):
    for d, v in PRESETS[name].items():
        st.session_state[f"w_{d}"] = v


def render():
    page_header("Creator shortlist",
                "Adjust the five criteria and watch the ranking respond. Dimension scores come from the creator engine; only the blend changes.",
                "Interactive")
    c = D.creator_outputs()
    base = c["ranking"].set_index("creator_id")
    labels = {d: D.DIM_SHORT[d] for d in D.DIMS}
    for d, v in PRESETS["Brief (default)"].items():
        st.session_state.setdefault(f"w_{d}", v)

    ctrl, main = st.columns([1, 3], gap="large")
    with ctrl:
        section("Weights", "Sliders are auto-normalised to 100%.")
        for name in PRESETS:
            st.button(name, key=f"p_{name}", on_click=_set_preset, args=(name,), width="stretch")
        st.write("")
        w = {d: st.slider(D.DIM_LABEL[d], 0, 100, key=f"w_{d}") for d in D.DIMS}
        tot = sum(w.values())
        if tot == 0:
            st.error("Set at least one weight above zero.")
            return
        norm = {d: v / tot for d, v in w.items()}
        section("Filters")
        confs = st.multiselect("Confidence", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
        demo_only = st.toggle("Only creators with demographics", value=False)
        topn = st.slider("Creators in charts", 3, 20, 10)

    rw = D.reweight(base, w)
    view = rw[rw.confidence_level.isin(confs)]
    if demo_only:
        view = view[view.has_demographics]

    with main:
        is_default = all(abs(norm[d] - D.CA.DIMENSION_WEIGHTS[d]) < 1e-9 for d in D.DIMS)
        if not is_default:
            note("Custom weights are active. <b>▲▼</b> compares with the brief's 25/20/20/20/15 weights. Bootstrap intervals, P(top-5) and confidence "
                 "are computed at the brief weights only, so they are hidden here.")
        section("Ranking at these weights", "Bar length is the weighted score out of 100; colours show what each criterion contributed.")
        if view.empty:
            st.info("No creators match these filters.")
        else:
            rows = "".join(creator_row(
                int(r.custom_rank), r.handle, cid, r.custom_score, {d: r[f"w_{d}"] for d in D.DIMS}, labels, r.confidence_level,
                p_top5=r.p_top5 if is_default else None, delta=None if is_default else int(r.rank_change),
                lo=r.score_p05 if is_default else None, hi=r.score_p95 if is_default else None,
                lead=int(r.custom_rank) == 1, top=int(r.custom_rank) <= 5) for cid, r in view.iterrows())
            st.markdown(dim_legend(labels, norm) + rows, unsafe_allow_html=True)

        t1, t2, t3 = st.tabs(["Ranking table", "Score breakdown", "Compare creators"])
        with t1:
            tbl = view.reset_index()[["custom_rank", "rank_change", "creator_id", "handle", "custom_score"] + D.DIMS + ["evidence_coverage", "confidence_level", "p_top5"]]
            st.dataframe(tbl, hide_index=True, width="stretch", height=min(760, 38 * (len(tbl) + 1) + 3), column_config={
                "custom_rank": st.column_config.NumberColumn("Rank", width="small"),
                "rank_change": st.column_config.NumberColumn("Δ rank", format="%+d", width="small", help="Positive = moves up vs the brief's weights"),
                "creator_id": st.column_config.TextColumn("ID", width="small"), "handle": st.column_config.TextColumn("Creator"),
                "custom_score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.1f"),
                **{d: st.column_config.ProgressColumn(D.DIM_SHORT[d], min_value=0, max_value=100, format="%.0f") for d in D.DIMS},
                "evidence_coverage": st.column_config.ProgressColumn("Coverage", min_value=0, max_value=1, format="percent"),
                "confidence_level": st.column_config.TextColumn("Confidence", width="small"),
                "p_top5": st.column_config.NumberColumn("P(top-5)*", format="percent", help="Bootstrap over posts, at the brief's weights")})
            st.download_button("Download ranking (CSV)", tbl.to_csv(index=False).encode(), "creator_ranking_custom_weights.csv", "text/csv")
        with t2:
            d = view.head(topn).iloc[::-1]
            fig = go.Figure()
            for dim in D.DIMS:
                fig.add_bar(y=d.handle, x=d[f"w_{dim}"], orientation="h", name=D.DIM_LABEL[dim], marker=dict(color=DIM_COLORS[dim], line=dict(width=1, color=IVORY)),
                            customdata=d[dim], hovertemplate=f"{D.DIM_LABEL[dim]}<br>score %{{customdata:.0f}} → %{{x:.1f}} pts<extra></extra>")
            style(fig, max(380, 34 * len(d) + 120), title="Weighted contribution to the composite score", barmode="stack", xaxis_title="points", legend=dict(orientation="h", y=-0.12))
            plot(fig)
            hm = view.head(topn)[D.DIMS]
            fig = go.Figure(go.Heatmap(z=hm.values, x=[D.DIM_SHORT[x] for x in D.DIMS], y=view.head(topn).handle, colorscale=[[0, IVORY], [.5, SAGE], [1, INK]],
                                       zmin=0, zmax=100, xgap=3, ygap=3, text=np.round(hm.values, 0), texttemplate="%{text:.0f}",
                                       hovertemplate="%{y} · %{x}: %{z:.0f}<extra></extra>", showscale=False))
            style(fig, max(320, 30 * len(hm) + 100), title="Dimension scores (0–100)", yaxis=dict(autorange="reversed"))
            plot(fig)
        with t3:
            names = view.index.tolist()
            pick = st.multiselect("Choose up to 4 creators", names, default=names[:3], max_selections=4, format_func=lambda i: f"@{base.at[i, 'handle']} ({i})")
            if pick:
                fig = radar({f"@{base.at[i, 'handle']}": base.loc[i] for i in pick}, 440)
                plot(fig)
                comp = c["comps"]
                sub = comp[comp.creator_id.isin(pick) & comp.available & (comp.dimension != "audience_fit")]
                pv = sub.pivot_table(index=["dimension", "component"], columns="creator_id", values="component_score").round(0)
                st.dataframe(pv, width="stretch")
            else:
                st.info("Select at least one creator.")
