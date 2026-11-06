from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from . import data as D
from .theme import (BUTTER_DEEP, DEEP_SAGE, DIM_COLORS, INK, IVORY, SAGE, STONE, TERRA, TRACK, dim_legend, esc, note, page_header, plot, ribbon,
                    section, style, table_html)

COMP_DESC = {
    "post_relevance": "Mean post relevance: 1.0 nutrition + children, 0.7 nutrition only, 0.5 child health, 0.4 parenting only, 0 otherwise",
    "er_full_history": "Median (likes + comments + shares) / plays over all videos with plays",
    "er_recent_window": "Same, last 90 days; scored only with ≥ 4 videos with plays",
    "comment_rate": "Median comments per play: conversation, not passive likes",
    "interaction_depth": "Share of interactions that are comments or shares",
    "er_consistency": "Robust coefficient of variation of ER; lower = more predictable",
    "child_presence": "Share of posts with children on camera",
    "format_fit": "Post format mapped to a Little Joys ad format; full fit if used in ≥ 15% of ad creatives",
    "storytelling": "Skit / day-in-life / story cues in content type, format or text",
    "setting_fit": "Setting mapped to ad settings (home, kitchen…); clinics have no ad equivalent",
    "language_fit": "English/Hindi/Hinglish or languages already used in ads = 1; others 0.5",
    "product_integration": "Share of posts showing a product",
    "reach_to_follower": "Median plays ÷ followers (organic reach vs follower base)",
    "sponsorship_balance": "100 at 0% sponsored posts falling to 0 at ≥ 50%",
    "sponsored_vs_organic_er": "Median ER of sponsored ÷ organic videos (capped at 1); needs ≥ 3 of each",
    "on_camera_presence": "Share of posts with the creator on camera",
}


def render():
    page_header("Methodology",
                "How scores are built, how missing data is handled, and what this analysis cannot tell you.",
                "Read before deciding")
    c = D.creator_outputs()
    cfg = c["config"]
    t1, t2, t3, t4, t5 = st.tabs(["Scoring logic", "Missing data", "Evidence and confidence", "Sensitivity", "Limitations"])

    with t1:
        weights = cfg["dimension_weights"]
        labels = {d: D.DIM_SHORT[d] for d in D.DIMS}
        formula = " + ".join(f"{weights[d]:.2f} × {labels[d].lower()}" for d in D.DIMS)
        a, b = st.columns([1, 1.15], gap="large")
        with a:
            ids, lab, parents, values, colors = ["root"], ["Composite"], [""], [0], [TRACK]
            for dim in D.DIMS:
                w = weights[dim]
                ids.append(dim); lab.append(D.DIM_LABEL[dim]); parents.append("root"); values.append(0); colors.append(DIM_COLORS[dim])
                comps = cfg["components"].get(dim, [{"name": "content-audience proxy ⊕ demographics", "weight": 1.0}])
                for comp in comps:
                    ids.append(f"{dim}/{comp['name']}"); lab.append(comp["name"].replace("_", " ")); parents.append(dim)
                    values.append(w * comp["weight"] * 100); colors.append(DIM_COLORS[dim])
            fig = go.Figure(go.Sunburst(ids=ids, labels=lab, parents=parents, values=values, branchvalues="remainder", marker=dict(colors=colors, line=dict(color=IVORY, width=1.5)),
                                        hovertemplate="%{label}<br>%{value:.1f}% of composite<extra></extra>", insidetextorientation="radial"))
            style(fig, 520, title="Share of the composite score by component", margin=dict(l=0, r=0, t=10, b=0))
            plot(fig)
        with b:
            section("Formula")
            st.markdown(f'<div class="fm">composite = {esc(formula)}</div>' + dim_legend(labels, weights) + ribbon({d: weights[d] * 100 for d in D.DIMS}, labels), unsafe_allow_html=True)
            st.markdown("Each dimension is a weighted mean of named components on a 0–100 scale. Engagement and reach components are **percentile ranks across the 20 creators**; "
                        "the rest are absolute shares. If a component cannot be computed it is dropped and the remaining weights are re-normalised: it is never scored as zero.")
            for dim in [d for d in D.DIMS if d in cfg["components"]]:
                comps = cfg["components"][dim]
                with st.expander(f"{D.DIM_LABEL[dim]}, {weights[dim]:.0%}"):
                    st.markdown(table_html(["Component", "Weight", "What it measures"],
                                           [[x["name"].replace("_", " "), f"{x['weight']:.0%}", COMP_DESC.get(x["name"], "")] for x in comps]), unsafe_allow_html=True)
            with st.expander(f"Audience fit, {weights['audience_fit']:.0%}"):
                st.markdown("For **all 20 creators**: share of posts whose audience signal targets parents/families (content proxy). For the **3 creators with demographics** it is blended "
                            "50/50 with the share of audience that is women, in India and aged 25–44 (25% weight for CR-14, whose snapshot is a Facebook audience).")
        section("Ad to post crosswalk", "Ads cannot be joined to creators; compatibility uses this explicit mapping of vocabularies.")
        cw = c["crosswalk"].copy()
        st.dataframe(cw, hide_index=True, width="stretch", column_config={"ad_share": st.column_config.NumberColumn("Ad share", format="percent"),
                                                                      "fit_value": st.column_config.NumberColumn("Fit value", format="%.2f")})

    with t2:
        dem = c["demo"]
        a, b = st.columns(2, gap="large")
        with a:
            section("Who has demographic data?")
            fig = go.Figure(go.Bar(x=dem.creator_id, y=dem.has_demographics.astype(int), marker_color=[INK if x else TRACK for x in dem.has_demographics]))
            style(fig, 260, title="3 of 20 creators have audience snapshots", yaxis=dict(visible=False), xaxis=dict(tickangle=-60, tickfont=dict(size=10)))
            plot(fig)
        with b:
            section("Rules")
            st.markdown("""
- **Never fabricated.** The 17 creators without a snapshot have empty demographic fields. Nothing is filled with averages, estimates or look-alikes.
- **Never penalised.** Their audience fit is the content-targeting proxy alone, on the same 0–100 scale as everyone else. A missing demographic component is dropped, not scored 0.
- **Visible, not hidden.** The gap lowers *evidence coverage* (audience dimension 50% vs 100%) and the confidence index. Scores are unchanged.
- **Asymmetry caveat.** Demographics can only move the 3 creators that have them (CR-20's 70% male audience lowers its audience fit); the others carry an unverified proxy. The *Sensitivity* tab shows rank without demographics.
- **CR-14** is a Facebook audience for an Instagram account, so its demographic weight is halved.
""")
        section("Other missing evidence, handled the same way")
        st.markdown("Plays are absent for carousels and photos (39 posts), so play-based rates use videos only; recent-window ER is dropped when fewer than 4 recent videos have plays "
                    "(e.g. CR-09); the sponsored-vs-organic ratio is dropped when either side has fewer than 3 videos.")

    with t3:
        cov = c["coverage"].set_index("creator_id")
        cols = [x for x in cov.columns if x.startswith("coverage_")]
        hm = cov[cols + ["evidence_coverage"]].sort_values("evidence_coverage")
        fig = go.Figure(go.Heatmap(z=hm.values, x=[x.replace("coverage_", "").replace("_", " ") for x in hm.columns], y=hm.index, colorscale=[[0, "#F0B9A6"], [.6, "#F1E7BE"], [1, DEEP_SAGE]],
                                   zmin=.4, zmax=1, xgap=3, ygap=3, text=hm.values, texttemplate="%{text:.0%}", colorbar=dict(thickness=9)))
        style(fig, 560, title="Evidence coverage by creator and dimension", xaxis=dict(side="top", tickangle=-20))
        plot(fig)
        st.markdown("""
**Evidence coverage** = share of each dimension's intended inputs that exist, combined with field completeness, weighted by the five dimension weights.
**Confidence index** = 0.35 coverage + 0.15 post count (n/20) + 0.15 videos with plays (n/15) + 0.15 recent-window videos (n/8) + 0.20 stability (width of the 90% bootstrap score interval).
*High ≥ 0.85, Medium ≥ 0.70, Low below.* Confidence describes how much to trust a score; it never changes it.
""")

    with t4:
        s = c["sens"].rename(columns={"index": "creator_id"})
        top = s.sort_values("rank_base").head(10)
        fig = go.Figure()
        variants = {"rank_base": "Brief weights", "rank_no_demographics": "No demographics", "rank_full_history_only": "Full history only", "rank_equal_weights": "Equal weights"}
        marks = [(INK, "circle"), (TERRA, "diamond"), (DEEP_SAGE, "square"), (BUTTER_DEEP, "triangle-up")]
        for i, (k, labl) in enumerate(variants.items()):
            fig.add_scatter(x=top.creator_id, y=top[k], mode="markers", name=labl, marker=dict(size=14 - 2 * i, symbol=marks[i][1], color=marks[i][0], line=dict(width=1, color=INK)))
        fig.update_yaxes(autorange="reversed", title="Rank", dtick=1)
        style(fig, 420, title="Rank of the current top ten under alternative specifications")
        plot(fig)
        note("Rank 1 is stable everywhere. Ranks 2–6 reorder under alternative weights, which is why the output is a shortlist. "
             "Bottom-ranked creators stay at the bottom under every specification.")

    with t5:
        note("<b>Synthetic ad data.</b> The ad performance figures supplied for this assignment (spend, revenue, ROAS, funnel rates) are synthetic. They show how the analysis works. "
             "No conclusion about Little Joys' real advertising should be drawn from them.", warn=True)
        st.markdown("""
- **AI-generated labels.** Content type, format, setting, sponsorship, audience signal, tone and all creator persona text are model-generated and unvalidated. Relevance, compatibility and the audience proxy are keyword rules over that text.
- **Observational, small samples.** ~20 posts per creator across 33 to 1,670 days. The "recent window" therefore holds 4 to 20 posts. No sales, reach, saves or watch-time data exist for creators.
- **Ads cannot be joined to creators.** Compatibility reflects familiarity with Little Joys' own creative vocabulary, not predicted conversion; the ad analysis found most creative attributes had no clear effect on purchases.
- **Ad results are concentrated.** One creative (LJ-004) is 30% of revenue; sensitivity variants are provided on the Ad intelligence page.
- **Judgement calls.** Thresholds (90-day window, 15% ad-share saturation, 50% sponsorship cap, 0.5 demographic blend, within-dimension weights) are documented assumptions; only the five top-level weights came from the brief.
- **Competitor brands** (e.g. Gritzo) appear in some creators' posts. They are flagged but not scored: check exclusivity before outreach.
- **Bootstrap** captures post-sampling noise only, not label error or weight choice.
""")
        m = c["manifest"]
        st.caption(f"Engine run: as-of {m['as_of']}, seed {m['seed']}, {m['bootstrap_B']} resamples, pandas {m['pandas']}. Full write-up in docs/creator_analysis.md and docs/ad_analysis.md.")
