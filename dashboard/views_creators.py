from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from . import data as D
from .theme import (BUTTER, DEEP_SAGE, DIM_COLORS, HAIR, INK, IVORY, MUTED, SAGE, SERIES, STONE, TERRA, badge, chip, comp_bar, dim_legend, esc,
                    kpi, note, page_header, plot, prov, ribbon, section, spread, style)


def _rgba(hex_: str, a: float) -> str:
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def radar(series: dict[str, pd.Series], height=360):
    cats = [D.DIM_SHORT[d] for d in D.DIMS]
    fig = go.Figure()
    for i, (name, s) in enumerate(series.items()):
        vals = [float(s[d]) for d in D.DIMS]
        col = SERIES[i % len(SERIES)] if name != "Cohort mean" else STONE
        fig.add_scatterpolar(r=vals + vals[:1], theta=cats + cats[:1], name=name, fill="toself" if name != "Cohort mean" else "none",
                             line=dict(color=col, width=2, dash="dot" if name == "Cohort mean" else "solid"),
                             fillcolor=_rgba(col, 0.14), opacity=0.95)
    fig.update_polars(radialaxis=dict(range=[0, 100], gridcolor="#E6DFCF", linecolor="#E6DFCF", tickfont=dict(size=9, color=MUTED), angle=90),
                      angularaxis=dict(tickfont=dict(size=11), gridcolor="#E6DFCF", linecolor=STONE), bgcolor="rgba(0,0,0,0)")
    return style(fig, height, margin=dict(l=40, r=40, t=24, b=40))


def fmt_pct(x, d=1):
    return "n/a" if pd.isna(x) else f"{x * 100:.{d}f}%"


def render():
    page_header("Creator profiles",
                "Scores, evidence and content for all 20 candidates. Counts are platform-scraped; content labels are AI-generated.",
                "20 creators, 392 posts")
    c, raw = D.creator_outputs(), D.raw_creator_data()
    rk = c["ranking"].set_index("creator_id")
    met = c["metrics"].set_index("creator_id")
    cre = raw["creators"].set_index("creator_id")
    posts = raw["posts"]
    df = rk.join(met[["followers", "er_full_median", "er_recent_median", "plays_full_median", "posts_per_30d_full", "sponsored_share",
                      "nutrition_child_share", "child_share", "n_posts", "n_recent_posts"]], rsuffix="_m")

    f1, f2, f3, f4 = st.columns([1.4, 1, 1, 1.2], gap="large")
    q = f1.text_input("Search", placeholder="handle, name or persona")
    conf = f2.multiselect("Confidence", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    tier = f3.selectbox("Audience size", ["All", "< 100K", "100K – 500K", "500K – 1M", "> 1M"])
    demo_only = f4.toggle("Has demographics only", value=False)
    d = df[df.confidence_level.isin(conf)]
    if q:
        txt = (cre.name.fillna("") + " " + cre.handle + " " + cre.persona.fillna("")).str.lower()
        d = d[txt.reindex(d.index).str.contains(q.lower(), regex=False)]
    bounds = {"< 100K": (0, 1e5), "100K – 500K": (1e5, 5e5), "500K – 1M": (5e5, 1e6), "> 1M": (1e6, 1e12)}
    if tier != "All":
        lo, hi = bounds[tier]
        d = d[(d.followers >= lo) & (d.followers < hi)]
    if demo_only:
        d = d[d.has_demographics]
    if d.empty:
        st.warning("No creators match these filters.")
        return

    options = d.sort_values("rank").index.tolist()
    sel = st.selectbox("Open profile", options, format_func=lambda i: f"#{int(rk.at[i, 'rank'])}  @{rk.at[i, 'handle']} ({i})")

    with spread("The field", "Each bubble is a creator. Darker means a higher composite score; the terracotta ring marks the open profile."):
        fig = px.scatter(d.reset_index(), x="followers", y="er_full_median", size="plays_full_median", color="composite_score", log_x=True,
                         color_continuous_scale=[SAGE, DEEP_SAGE, INK], size_max=46, hover_name="handle",
                         hover_data={"creator_id": True, "followers": ":,.0f", "er_full_median": ":.2%", "plays_full_median": ":,.0f", "composite_score": ":.1f", "rank": True},
                         labels={"followers": "Followers (log)", "er_full_median": "Median engagement rate (video)", "composite_score": "Score"})
        fig.update_yaxes(tickformat=".1%")
        fig.update_xaxes(tickvals=[2e4, 5e4, 1e5, 2e5, 5e5, 1e6, 2e6, 3e6], ticktext=["20K", "50K", "100K", "200K", "500K", "1M", "2M", "3M"])
        fig.update_traces(marker=dict(line=dict(width=1, color=INK)), text=d.reset_index().handle.str.slice(0, 14), textposition="top center",
                          textfont=dict(size=10, color=MUTED), mode="markers+text")
        if sel in d.index and pd.notna(d.at[sel, "er_full_median"]):
            fig.add_scatter(x=[d.at[sel, "followers"]], y=[d.at[sel, "er_full_median"]], mode="markers", hoverinfo="skip", showlegend=False,
                            marker=dict(size=40, color="rgba(0,0,0,0)", line=dict(width=2.5, color=TERRA)))
        style(fig, 420, title=f"{len(d)} creators. Bubble size is median plays.", coloraxis_colorbar=dict(thickness=9, len=0.7, title=""))
        plot(fig)

    r, m, p = rk.loc[sel], met.loc[sel], cre.loc[sel]
    name = (p["name"] if isinstance(p["name"], str) else p["handle"]).split("|")[0].strip()
    persona = p.persona if isinstance(p.persona, str) else ""
    st.markdown('<div class="sp-rule"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="pf"><div><div class="pf-n">{esc(name)}</div>'
        f'<div class="pf-p"><a href="{esc(p.profile_url)}" target="_blank">@{esc(p.handle)}</a>{(", " + esc(persona)) if persona else ""}'
        f'{", verified" if p.verified == "yes" else ""}</div></div>'
        f'<div class="pf-r"><div class="pf-rk">{int(r["rank"])}</div><div class="pf-sc">Score {r.composite_score:.1f} of 100</div>{badge(r.confidence_level)}</div></div>',
        unsafe_allow_html=True)
    k = st.columns(6, gap="large")
    tiles = [("Followers", D.millions(m.followers), f"following {int(p.following):,}"),
             ("Median ER, full history", fmt_pct(m.er_full_median, 2), f"{int(m.n_video_with_plays)} videos with plays"),
             ("Median ER, 90 days", fmt_pct(m.er_recent_median, 2), f"{int(m.n_recent_video_with_plays)} recent videos" + ("" if pd.notna(m.er_recent_median) else ", too thin")),
             ("Posts per 30 days", f"{m.posts_per_30d_full:.1f}", f"{int(m.n_recent_posts)} in last 90 days"),
             ("Median plays", D.millions(m.plays_full_median), f"{m.view_to_follower:.2f}× followers"),
             ("Sponsored share", fmt_pct(m.sponsored_share, 0), f"{int(m.n_sponsored_videos)} sponsored videos")]
    for col, (l, v, s) in zip(k, tiles):
        col.markdown(kpi(l, v, s), unsafe_allow_html=True)

    labels = {x: D.DIM_SHORT[x] for x in D.DIMS}
    comps = c["comps"]
    mine = comps[(comps.creator_id == sel) & comps.available & comps.component_score.notna()].copy()

    # ------------------------------------------------------------ scoring
    with spread("Scoring", "Where this creator sits against the cohort on each criterion, and how the composite is built."):
        a1, a2 = st.columns([1.1, 1], gap="large")
        with a1:
            cm = rk[D.DIMS].mean()
            fig = go.Figure()
            ylab = [D.DIM_LABEL[x] for x in D.DIMS]
            for x, yl in zip(D.DIMS, ylab):
                fig.add_scatter(x=[cm[x], r[x]], y=[yl, yl], mode="lines", line=dict(color=STONE, width=3), showlegend=False, hoverinfo="skip")
            fig.add_scatter(x=[cm[x] for x in D.DIMS], y=ylab, mode="markers", name="Cohort mean", marker=dict(size=11, color=IVORY, line=dict(color=INK, width=1.6)),
                            hovertemplate="Cohort mean %{x:.0f}<extra></extra>")
            fig.add_scatter(x=[r[x] for x in D.DIMS], y=ylab, mode="markers", name=f"@{r.handle}", marker=dict(size=14, color=TERRA, line=dict(color=INK, width=1)),
                            hovertemplate="%{y}: %{x:.0f}<extra></extra>")
            style(fig, 330, title="Dimension scores against the cohort mean (0–100)", xaxis=dict(range=[0, 104], title=""), yaxis=dict(autorange="reversed", title=""))
            plot(fig)
        with a2:
            st.markdown(f'<div class="ch-t" style="margin-bottom:.4rem">Weighted contribution to {r.composite_score:.1f}</div>'
                        + dim_legend(labels, D.CA.DIMENSION_WEIGHTS)
                        + ribbon({x: r[f"contrib_{x}"] for x in D.DIMS}, labels, r.score_p05, r.score_p95), unsafe_allow_html=True)
            st.markdown("".join(comp_bar(D.DIM_LABEL[x], r[x], DIM_COLORS[x]) for x in D.DIMS), unsafe_allow_html=True)
            st.caption(f"The bracket under the bar is the 90% bootstrap interval ({r.score_p05:.1f} to {r.score_p95:.1f}).")

    # ------------------------------------------------------------ strengths
    body = mine[mine.dimension != "audience_fit"].sort_values("component_score", ascending=False)
    with spread("Strengths and watch-outs", "Component scores on a 0–100 scale. Engagement components are percentile ranks across the 20 creators."):
        s1, s2 = st.columns(2, gap="large")
        with s1:
            section("Highest-scoring components")
            st.markdown("".join(comp_bar(f"{x.component.replace('_', ' ')}", x.component_score, DEEP_SAGE) for x in body.head(4).itertuples()), unsafe_allow_html=True)
        with s2:
            section("Lowest-scoring components")
            st.markdown("".join(comp_bar(f"{x.component.replace('_', ' ')}", x.component_score, TERRA) for x in body.tail(4).iloc[::-1].itertuples()), unsafe_allow_html=True)
        cv = c["coverage"].set_index("creator_id").loc[sel]
        flags = [f for f in str(r["flags"]).split("; ") if f and f != "nan"]
        st.markdown(f'<div class="sec-t">Evidence</div><div class="sec-d">Coverage {cv.evidence_coverage:.0%}, confidence index {cv.confidence_index:.2f}, stability {cv.stability:.2f}.</div>'
                    + ("".join(chip(f.replace("_", " "), risk="competitor" in f) for f in flags) or "No flags"), unsafe_allow_html=True)

    # ------------------------------------------------------------ creative compatibility
    with spread("Creative compatibility", "How close this creator's natural content is to the formats Little Joys already runs."):
        cc = mine[mine.dimension == "creative_compatibility"].sort_values("component_score", ascending=False)
        b1, b2 = st.columns([1, 1.2], gap="large")
        with b1:
            st.markdown("".join(comp_bar(x.component.replace("_", " "), x.component_score, DIM_COLORS["creative_compatibility"]) for x in cc.itertuples())
                        or "No compatibility components are available for this creator.", unsafe_allow_html=True)
            chips = [f"Children on camera {fmt_pct(m.child_share, 0)}", f"Nutrition + child posts {fmt_pct(m.nutrition_child_share, 0)}",
                     f"Storytelling {fmt_pct(m.story_share, 0)}", f"Product shown {fmt_pct(m.product_share, 0)}", f"Format fit {fmt_pct(m.format_fit_mean, 0)}"]
            st.markdown('<div style="margin-top:.8rem">' + "".join(chip(x) for x in chips) + "</div>", unsafe_allow_html=True)
        with b2:
            if D.dna_ready() and sel in D.dna_outputs()["profiles"]:
                pr = D.dna_outputs()["profiles"][sel]
                att = pr["attention_alignment"]
                st.markdown(f'<div class="sec-t" style="margin-top:0">Natural content style {prov("ai", "post labels (AI)")}</div>'
                            f'<div class="en-b">{esc(pr["natural_style"]["summary"])}</div>'
                            f'<div class="sec-d" style="margin-top:.8rem">Attention-pattern alignment: {"not scored" if att is None else f"{att:.0f} of 100"}. See Creative DNA for the evidence.</div>'
                            + "".join(chip(it["feature"]) for it in pr["strengths"])
                            + "".join(chip(it["feature"], risk=True) for it in pr["gaps"]), unsafe_allow_html=True)
            else:
                st.markdown('<div class="sec-d">The Creative DNA match is built for the five shortlisted creators only.</div>', unsafe_allow_html=True)

    # ------------------------------------------------------------ evidence tabs
    st.markdown('<div class="sp-rule"></div>', unsafe_allow_html=True)
    t1, t2, t3, t4, t5 = st.tabs(["Performance over time", "Content mix", "Posts", "Audience and risk", "Profile text"])
    pp = posts[posts.creator_id == sel].sort_values("posted_on")
    with t1:
        v = pp[pp.plays.notna()]
        cutoff = posts.posted_on.max() - pd.Timedelta(days=D.CA.RECENT_DAYS)
        fig = go.Figure()
        fig.add_scatter(x=v.posted_on, y=v.er, mode="markers+lines", line=dict(color=STONE, width=1), marker=dict(size=np.clip(np.sqrt(v.plays) / 60, 6, 32), color=INK, opacity=.8,
                        line=dict(width=1, color=IVORY)), customdata=np.c_[v.plays, v.likes, v.comments, v.reshares, v.content_form.fillna("")],
                        hovertemplate="%{x|%d %b %Y}<br>ER %{y:.2%}<br>plays %{customdata[0]:,.0f}<br>%{customdata[4]}<extra></extra>", name="Video ER")
        fig.add_hline(y=m.er_full_median, line_dash="dot", line_color=TERRA, annotation_text=f"median {m.er_full_median:.2%}")
        if v.posted_on.max() >= cutoff:
            fig.add_vrect(x0=max(cutoff, v.posted_on.min()), x1=v.posted_on.max(), fillcolor=BUTTER, opacity=0.35, line_width=0, annotation_text="last 90 d", annotation_position="top left")
        style(fig, 380, title="Engagement rate per video (bubble = plays)", yaxis=dict(tickformat=".1%", title="(likes + comments + shares) / plays"), xaxis_title="")
        plot(fig)
        w = c["window"].set_index("creator_id").loc[sel]
        st.dataframe(pd.DataFrame({"Window": ["Full history (file)", f"Last {D.CA.RECENT_DAYS} days"], "Posts": [int(w.n_posts), int(w.n_recent_posts)],
                                   "Posts / 30 d": [w.posts_per_30d_full, w.posts_per_30d_recent], "Median ER": [w.er_full_median, w.er_recent_median],
                                   "Median plays": [w.plays_full_median, w.plays_recent_median]}), hide_index=True, width="stretch",
                     column_config={"Median ER": st.column_config.NumberColumn(format="percent"),
                                    "Posts / 30 d": st.column_config.NumberColumn(format="%.1f"), "Median plays": st.column_config.NumberColumn(format="%d")})
    with t2:
        a1, a2, a3 = st.columns(3, gap="large")
        for col, field, title in [(a1, "content_form", "Format"), (a2, "content_type", "Content type"), (a3, "language_norm", "Language")]:
            vc = pp[field].fillna("unknown").value_counts().rename_axis("k").reset_index(name="n").iloc[::-1]
            fig = go.Figure(go.Bar(y=vc.k.str.replace("_", " "), x=vc.n, orientation="h", marker_color=INK, text=vc.n, textposition="outside"))
            style(fig, 300, title=title, xaxis_title="posts", margin=dict(l=10, r=24, t=10, b=10))
            with col:
                plot(fig)
    with t3:
        show = pp.sort_values("plays", ascending=False)[["posted_on", "type", "content_form", "topic", "plays", "likes", "comments", "reshares", "er", "is_sponsored", "post_url"]]
        st.dataframe(show, hide_index=True, width="stretch", column_config={
            "posted_on": st.column_config.DateColumn("Date"), "er": st.column_config.NumberColumn("ER", format="%.4f"), "post_url": st.column_config.LinkColumn("Link", display_text="open"),
            "plays": st.column_config.NumberColumn(format="%d"), "topic": st.column_config.TextColumn(width="large")})
    with t4:
        dm = c["demo"].set_index("creator_id").loc[sel]
        a1, a2 = st.columns(2, gap="large")
        with a1:
            section("Audience demographics")
            if dm.has_demographics:
                aud = raw["audience"].set_index("creator_id").loc[sel]
                fig = go.Figure(go.Bar(x=["Women", "India", "Age 25–44"], y=[dm.women_share, dm.india_share, dm.age_25_44_share], marker_color=[TERRA, DEEP_SAGE, INK],
                                       text=[f"{x:.0%}" for x in (dm.women_share, dm.india_share, dm.age_25_44_share)], textposition="outside"))
                style(fig, 280, title=f"Match to target (women, India, 25–44) = {dm.demo_match:.0%}", yaxis=dict(tickformat=".0%", range=[0, 1.1]))
                plot(fig)
                st.caption(f"Platform: {aud.platform}, as of {aud.as_of}. Top cities: {aud.top_cities}.")
                if dm.platform_mismatch:
                    note("This snapshot is a <b>Facebook</b> audience for an Instagram account; its weight in audience fit is halved.", warn=True)
            else:
                note("<b>No demographic data for this creator.</b> Nothing is estimated or imputed. Audience fit is scored from a content-targeting proxy "
                     f"({fmt_pct(m.parent_targeted_share, 0)} of posts aimed at parents/families) and is <i>not</i> penalised; evidence coverage is lower instead.")
        with a2:
            section("Flags")
            st.markdown("".join(chip(f.replace("_", " "), risk="competitor" in f) for f in flags) or "No flags", unsafe_allow_html=True)
    with t5:
        note("The text below is AI-generated by the data provider, not verified. It is shown for briefing context and is not used in scoring.", warn=True)
        for lab, col in [("Bio", "bio"), ("Themes", "themes"), ("Format habits", "format_habits"), ("Voice", "voice"), ("Feels native", "what_feels_native"), ("Would feel foreign", "what_would_feel_foreign")]:
            v = p.get(col)
            if isinstance(v, str) and v.strip():
                st.markdown(f"**{lab}**  \n{v}")
