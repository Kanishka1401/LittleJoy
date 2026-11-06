"""Landing page: what the platform is for, what is inside, and how to read it. Uses existing outputs only."""
from __future__ import annotations

import streamlit as st

from . import data as D
from .theme import creator_row, dim_legend, esc, kpi

SECTIONS = [
    ("Overview", "The executive summary: key findings and the creators to approach first."),
    ("Creator shortlist", "The ranking of all 20 creators. Change the weights and watch it respond."),
    ("Creator profiles", "One creator at a time: scores, evidence, strengths and content."),
    ("Ad intelligence", "What Little Joys' ads earn, how concentrated the results are, and which creative signals matter."),
    ("Creative DNA", "How closely each shortlisted creator's natural style matches the patterns in the ads."),
    ("Campaign Studio", "Editable campaign briefs for the five shortlisted creators: concept, hooks, script and claim checks."),
    ("Methodology", "How scores are built, how gaps are handled, and what this analysis cannot tell you."),
]
STEPS = [
    ("Read the ads", "Measure what the ads earn and which creative attributes show any signal, checking how much one ad drives the result."),
    ("Score the creators", "Rate all 20 on relevance, engagement, creative compatibility, authenticity and audience fit, each with a confidence level."),
    ("Match the style", "Compare each shortlisted creator's natural content with the patterns found in the ads."),
    ("Draft the brief", "Generate a concept, hooks, script and claim check for each of the five, from the creator's real posts."),
]


def _go(page: str):
    st.session_state["nav"] = page


def render():
    c, a, raw = D.creator_outputs(), D.ad_outputs(), D.raw_creator_data()
    rk = c["ranking"].set_index("creator_id")
    b = a["baseline"].set_index("variant").loc["creative_all"]
    top = rk.sort_values("rank").head(3)
    n_short = len(D.dna_outputs()["config"]["shortlist"]) if D.dna_ready() else 5

    st.markdown(
        '<div class="hero"><h1 class="hero-t">Which creators should Little Joys work with, and how sure can we be?</h1>'
        '<div class="hero-d">A working tool for choosing creators for Little Joys, a children\'s nutrition brand. It reads the brand\'s ad results and '
        f'{len(rk)} creators\' posts, ranks the creators on five criteria, shows the evidence behind every score, and drafts a campaign brief for each of the top five.</div></div>',
        unsafe_allow_html=True)
    b1, b2, _ = st.columns([1, 1, 3])
    b1.button("See the shortlist", key="home_go_short", on_click=_go, args=("Creator shortlist",), width="stretch")
    b2.button("Read the overview", key="home_go_over", on_click=_go, args=("Overview",), width="stretch")

    st.write("")
    cols = st.columns(4, gap="large")
    for col, (l, v, s) in zip(cols, [("Creators compared", f"{len(rk)}", f"{len(raw['posts'])} posts"),
                                    ("Ad creatives studied", f"{int(b.n_units)}", "unique creatives"),
                                    ("Scoring criteria", f"{len(D.DIMS)}", "weights you can change"),
                                    ("Briefs drafted", str(n_short), "for the shortlisted creators")]):
        col.markdown(kpi(l, v, s), unsafe_allow_html=True)

    st.markdown('<div class="sp-rule"></div>', unsafe_allow_html=True)
    q = st.columns(3, gap="large")
    for col, (t, d) in zip(q, [("What works in the ads", "Which product forms earn, which creative attributes move attention or sales, and how much a single ad changes the picture."),
                               ("Who fits the brand", "Which creators combine nutrition and parenting content, real engagement and a credible voice, and how confident each score is."),
                               ("What to make with them", "Creator-specific hooks, scripts and briefs, written only from claims found in Little Joys' own ad files.")]):
        col.markdown(f'<div class="fd-t">{esc(t)}</div><div class="fd-d" style="margin-top:.5rem">{esc(d)}</div>', unsafe_allow_html=True)

    st.markdown('<div class="sp-rule"></div><div class="sp-t">A first look</div><div class="sec-d">The current top three. Bar length is the score out of 100; each colour is one criterion.</div>', unsafe_allow_html=True)
    labels = {d: D.DIM_SHORT[d] for d in D.DIMS}
    rows = "".join(creator_row(int(r["rank"]), r.handle, cid, r.composite_score, {d: r[f"contrib_{d}"] for d in D.DIMS}, labels, r.confidence_level,
                               p_top5=r.p_top5, lo=r.score_p05, hi=r.score_p95, lead=(i == 0)) for i, (cid, r) in enumerate(top.iterrows()))
    st.markdown(dim_legend(labels, D.CA.DIMENSION_WEIGHTS) + rows, unsafe_allow_html=True)

    st.markdown('<div class="sp-rule"></div><div class="sp-t">How it works</div>', unsafe_allow_html=True)
    st.markdown('<div class="steps">' + "".join(f'<div class="step"><div class="step-n">{i}</div><div class="fd-t">{esc(t)}</div><div class="fd-d">{esc(d)}</div></div>'
                                                for i, (t, d) in enumerate(STEPS, 1)) + "</div>", unsafe_allow_html=True)

    st.markdown('<div class="sp-rule"></div><div class="sp-t">What is inside</div>', unsafe_allow_html=True)
    for name, desc in SECTIONS:
        r1, r2, r3 = st.columns([1.1, 3, 0.8], vertical_alignment="center", gap="large")
        r1.markdown(f'<div class="fd-t">{esc(name)}</div>', unsafe_allow_html=True)
        r2.markdown(f'<div class="fd-d">{esc(desc)}</div>', unsafe_allow_html=True)
        r3.button("Open", key=f"home_open_{name}", on_click=_go, args=(name,), width="stretch")

    st.markdown('<div class="sp-rule"></div><div class="sp-t">How far to trust it</div>', unsafe_allow_html=True)
    st.markdown('<div class="fd-d" style="max-width:46rem">This is an exploratory analysis. Content labels are AI-generated and unvalidated, samples are small, '
                'and the ads cannot be joined to individual creators, so nothing here is a prediction or a causal claim. Every score carries a confidence level, '
                'and ranks 2 to 5 are close enough that they should be read as a shortlist. The Methodology page sets all of this out.</div>', unsafe_allow_html=True)
