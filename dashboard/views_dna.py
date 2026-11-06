from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import data as D
from .theme import (BUTTER, BUTTER_DEEP, DEEP_SAGE, HAIR, INK, IVORY, MUTED, SAGE_MID, STONE, TERRA, chip, esc, kpi, note, page_header, plot, prov,
                    section, style)

QUAL_COLOR = {"direct": INK, "approximate": DEEP_SAGE, "weak": BUTTER_DEEP, "none": TERRA}


def legend() -> str:
    return "".join(prov(k) for k in ("observed", "ai", "rule", "assume"))


def post_link(pid: str) -> str:
    return f'<a href="https://www.instagram.com/p/{esc(pid)}/" target="_blank" style="text-decoration:none"><span class="chip">{esc(pid)}</span></a>'


def _entry(it: dict, ids_: dict, gap: bool) -> str:
    share = chip("%.0f%% of posts, %d/%d" % (it["prevalence"] * 100, it["n_posts_with_feature"], it["n_posts_labelled"]))
    return (f'<div class="en{" gap" if gap else ""}"><div class="en-h">{esc(it["feature"])} '
            f'{share}{chip("mapping: " + str(it["mapping_quality"]))}</div>'
            f'<div class="en-r">{esc(it["reading"])}</div>'
            f'<div class="en-b"><b>Opportunity</b> {prov("assume", "suggested test")} {esc(it.get("opportunity", ""))}</div>'
            f'<div class="en-c">Caution: {esc(it.get("caution", "")) or "none"}</div>'
            f'<div class="en-c" style="margin-top:.6rem">Ad creatives ({esc(ids_.get("ad_order", ""))}):<br>'
            + "".join(chip(x) for x in ids_.get("ad_creative_ids", [])) +
            f'<br>Creator posts ({ids_.get("n_posts", 0)} matching, latest shown):<br>' + "".join(post_link(x) for x in ids_.get("post_ids", [])) + '</div></div>')


def render():
    page_header("Creative DNA",
                "Which creative patterns show up in Little Joys ads, how closely each shortlisted creator's natural style matches them, "
                "and exactly how thin or strong the evidence is.",
                "Descriptive, not a forecast")
    if not D.dna_ready():
        st.error("Creative DNA outputs not found. Run `python scripts/run_creative_dna.py` first.")
        return
    d, c = D.dna_outputs(), D.creator_outputs()
    cfg = d["config"]
    short = cfg["shortlist"]
    rk = c["ranking"].set_index("creator_id")
    sc = d["scores"].set_index("creator_id")
    pat = d["patterns"]

    st.markdown(f'<div style="margin:0 0 .5rem 0">{legend()}</div>', unsafe_allow_html=True)
    note("<b>Read this first.</b> Patterns come from <i>paid-ad</i> data (97 unique creatives, synthetic figures, AI-labelled attributes, observational). Creators are described from "
         "<i>organic posts</i> (AI-labelled). <b>Organic engagement is not used anywhere on this page</b> and is not evidence of paid performance. Alignment says how often a creator "
         "already does what the ad patterns associate with higher attention. It is not a prediction, and nothing here is causal.", warn=True)
    n_scored_att = int(pat[(pat.stage == "attention") & pat.scored].feature_id.nunique())
    n_scored_pur = int(pat[(pat.stage == "purchase") & pat.scored & (pat.metric == "cvr_click")].feature_id.nunique())
    cols = st.columns(4, gap="large")
    for col, (l, v, s_) in zip(cols, [("Features mapped", f"{int(d['mapping'].used_in_score.sum())} of {len(d['mapping'])}", "direct or approximate"),
                                      ("Attention lens", f"{n_scored_att} scored", "stable ad signals on hook rate"),
                                      ("Purchase lens", "Not scored", f"{n_scored_pur} eligible, {cfg['min_scored_features']} required"),
                                      ("Shortlist", "5 creators", "from the engine's default ranking")]):
        col.markdown(kpi(l, v, s_), unsafe_allow_html=True)

    st.markdown('<div class="sp-rule"></div>', unsafe_allow_html=True)
    t1, t2, t3, t4, t5 = st.tabs(["Ad patterns", "Attribute mapping", "Creator comparison", "Creator DNA profiles", "Evidence tables"])

    # ------------------------------------------------------------------ 1
    with t1:
        section("What the ad analysis associates with outcomes", "Estimates are taken unchanged from reports/ad (within product form). Two marks per pattern: with and without LJ-004.")
        stage = st.segmented_control("Outcome stage", ["attention", "purchase"], default="attention",
                                     format_func=lambda x: {"attention": "Attention: hook rate", "purchase": "Purchase: click to purchase"}[x]) or "attention"
        p = pat[pat.stage == stage].copy()
        p["label"] = p.feature + " [" + p.mapping_quality + "]"
        p = p.sort_values("effect")
        fig = go.Figure()
        fig.add_scatter(x=p.effect, y=p.label, mode="markers", name="All creatives", marker=dict(size=12, color=INK),
                        error_x=dict(type="data", symmetric=False, array=p.ci_hi - p.effect, arrayminus=p.effect - p.ci_lo, color=DEEP_SAGE, thickness=1.8),
                        customdata=np.c_[p.ad_status, p.n_level], hovertemplate="<b>%{y}</b><br>%{x:.1f} pts, n=%{customdata[1]}<br>%{customdata[0]}<extra></extra>")
        fig.add_scatter(x=p.effect_excl_LJ004, y=p.label, mode="markers", name="Excluding LJ-004", marker=dict(size=11, symbol="diamond", color=BUTTER, line=dict(width=1.2, color=INK)))
        fig.add_vline(x=0, line_color=MUTED, line_dash="dot")
        style(fig, max(380, 34 * len(p) + 120), title=("Effect on hook rate" if stage == "attention" else "Effect on click-to-purchase rate") + " when the feature is present (pts, 95% CI)", xaxis_title="percentage points")
        plot(fig)
        if stage == "purchase":
            note("Purchase-stage evidence is thin: only humour and the 'overall growth' narrative are both <b>stable</b> and <b>mappable</b>. Skit format is <i>directionally negative</i> for conversion even though it earns attention.")
        show = p.iloc[::-1][["feature", "ad_status", "mapping_quality", "n_level", "effect", "ci_lo", "ci_hi", "effect_excl_LJ004", "survives_without_LJ004", "lj004_has_feature", "scored", "reason_not_scored"]]
        st.dataframe(show.rename(columns={"ad_status": "Ad evidence", "mapping_quality": "Mapping", "n_level": "n ads", "effect": "Effect", "ci_lo": "CI low", "ci_hi": "CI high",
                                          "effect_excl_LJ004": "Effect w/o LJ-004", "survives_without_LJ004": "Survives w/o LJ-004", "lj004_has_feature": "LJ-004 has it",
                                          "scored": "Used in score", "reason_not_scored": "Why not"}), hide_index=True, width="stretch",
                     column_config={k: st.column_config.NumberColumn(format="%.1f") for k in ["Effect", "CI low", "CI high", "Effect w/o LJ-004"]})

        section("Do high-ROAS ads look different? (descriptive)", "Top quartile of ROAS within product form vs the rest. LJ-004 and low-evidence creatives excluded. n is small; p-values are exploratory and uncorrected.")
        co = d["cohort"].sort_values("diff")
        fig = go.Figure()
        fig.add_bar(y=co.feature, x=co.prevalence_rest, orientation="h", name=f"Rest (n={int(co.n_rest.iloc[0])})", marker_color=SAGE_MID)
        fig.add_bar(y=co.feature, x=co.prevalence_top, orientation="h", name=f"Top-quartile ROAS (n={int(co.n_top.iloc[0])})", marker_color=INK,
                    customdata=co.fisher_p_exploratory, hovertemplate="%{y}<br>%{x:.0%} of top-quartile ads<br>exploratory p=%{customdata:.2f}<extra></extra>")
        style(fig, max(420, 28 * len(co) + 120), title="Share of ads with each feature", barmode="group", xaxis=dict(tickformat=".0%"))
        plot(fig)
        note("The one clear difference, the 'overall growth' narrative being rarer in high-ROAS ads, matches the stable purchase-stage signal. "
             "Attention-linked features (skit, humour, explainer) are <b>not</b> more common among high-ROAS ads, so attention-pattern alignment must not be read as a sales signal.")
        with st.expander("All stable-candidate ad signals and whether they can be mapped to posts"):
            st.dataframe(d["stable"], hide_index=True, width="stretch")

    # ------------------------------------------------------------------ 2
    with t2:
        section("Explicit ad to creator-post mapping", "Each row says how an ad attribute is matched to a post attribute, how good that match is, and why.")
        m = d["mapping"]
        q = st.multiselect("Mapping quality", ["direct", "approximate", "weak", "none"], default=["direct", "approximate", "weak", "none"])
        mm = m[m.mapping_quality.isin(q)]
        st.dataframe(mm[["feature", "mapping_quality", "ad_definition", "post_definition", "rationale", "caveat", "post_side_evidence_type", "used_in_score"]].rename(
            columns={"feature": "Feature", "mapping_quality": "Quality", "ad_definition": "Ad side (AI label)", "post_definition": "Post side", "rationale": "Why this quality",
                     "caveat": "Caveat", "post_side_evidence_type": "Post evidence type", "used_in_score": "Used in score"}), hide_index=True, width="stretch")
        a, b = st.columns(2, gap="large")
        with a:
            vc = m.mapping_quality.value_counts().reindex(["direct", "approximate", "weak", "none"]).fillna(0)
            fig = go.Figure(go.Bar(x=vc.index, y=vc.values, marker_color=[QUAL_COLOR[k] for k in vc.index], width=0.55, text=vc.values.astype(int), textposition="outside"))
            style(fig, 300, title="Mapping quality of the 16 ad features", yaxis=dict(visible=False))
            plot(fig)
        with b:
            section("Ad attributes with no post equivalent (never scored)")
            for k, v in cfg["no_equivalent_fields"]:
                st.markdown(f"- **{k}**: {v}")
        note("<b>Scoring rule.</b> A feature enters a creator's score only if (1) the ad evidence is a <i>stable candidate</i> that survives the LJ-004 check, (2) mapping quality is "
             f"<i>direct</i> or <i>approximate</i>, and (3) the creator has ≥ {cfg['min_labelled_posts']} labelled posts. A lens is scored only with ≥ {cfg['min_scored_features']} eligible features. "
             "Quality ratings are our judgement (assumption), not measured.")

    # ------------------------------------------------------------------ 3
    with t3:
        scope = st.radio("Creators", ["Shortlisted five", "All 20 (context)"], horizontal=True)
        ids = short if scope.startswith("Short") else list(rk.sort_values("rank").index)
        al = d["align"]
        al = al[(al.creator_id.isin(ids)) & al.scored_pattern & (al.metric == "hook_rate")].drop_duplicates(["creator_id", "feature_id"])
        feats = list(al.drop_duplicates("feature_id").sort_values("direction", ascending=False).feature)
        order = [i for i in rk.sort_values("rank").index if i in ids]
        piv = al.pivot(index="creator_id", columns="feature", values="alignment").reindex(index=order, columns=feats)
        prev = al.pivot(index="creator_id", columns="feature", values="prevalence").reindex(index=order, columns=feats)
        dirs = al.drop_duplicates("feature").set_index("feature").direction
        ylab = [f"#{int(rk.at[i, 'rank'])} @{rk.at[i, 'handle']}" for i in order]
        xlab = [f"{f} ({'↑' if dirs[f] == '+' else '↓'})" for f in feats]
        fig = go.Figure(go.Heatmap(z=piv.values * 100, x=xlab, y=ylab, colorscale=[[0, "#F0B9A6"], [.5, IVORY], [1, "#5F8068"]], zmin=0, zmax=100, xgap=3, ygap=3,
                                   text=[[f"{v:.0%}" if pd.notna(v) else "" for v in r] for r in prev.values], texttemplate="%{text}", colorbar=dict(title="Alignment", thickness=9),
                                   hovertemplate="%{y}<br>%{x}<br>creator does it in %{text} of posts<br>alignment %{z:.0f}<extra></extra>"))
        section("Natural style vs ad patterns", "Cell text is the share of the creator's posts with the feature. Colour is alignment with the ad pattern (↑ associated with more hook rate, ↓ with less).")
        style(fig, max(300, 56 * len(order) + 190), yaxis=dict(autorange="reversed"), xaxis=dict(side="top", tickangle=-25), margin=dict(l=16, r=16, t=140, b=14))
        plot(fig)
        a, b = st.columns(2, gap="large")
        with a:
            s2 = sc.loc[order].copy()
            fig = go.Figure(go.Bar(y=[f"@{rk.at[i, 'handle']}" for i in order], x=s2.attention_alignment, orientation="h", marker_color=[INK if i in short else SAGE_MID for i in order],
                                   text=[f"{v:.0f}" for v in s2.attention_alignment], textposition="outside",
                                   customdata=s2.attention_alignment_effect_weighted, hovertemplate="%{y}<br>equal-weight %{x:.0f}<br>effect-weighted %{customdata:.0f}<extra></extra>"))
            style(fig, max(300, 34 * len(order) + 100), title="Attention-pattern alignment (0–100)", xaxis=dict(range=[0, 100]), yaxis=dict(autorange="reversed"))
            plot(fig)
            st.caption("Purchase-stage alignment: **not scored** for any creator (too few stable, mappable purchase patterns). See purchase context in each profile.")
        with b:
            all_ = sc.join(rk[["composite_score"]])
            fig = go.Figure()
            for flag, name, col in [(False, "Other creators", SAGE_MID), (True, "Shortlisted", INK)]:
                z = all_[all_.index.isin(short) == flag]
                fig.add_scatter(x=z.composite_score, y=z.attention_alignment, mode="markers+text", name=name, text=[f"@{rk.at[i, 'handle'][:12]}" if flag else "" for i in z.index], textposition="top center",
                                textfont=dict(size=10, color=MUTED), marker=dict(size=13 if flag else 10, color=col, line=dict(width=1, color=INK)),
                                hovertemplate="%{text}<br>engine score %{x:.1f}<br>DNA alignment %{y:.0f}<extra></extra>")
            style(fig, 400, title="Engine composite vs attention-pattern alignment", xaxis_title="Engine composite score", yaxis_title="Attention alignment")
            plot(fig)
            st.caption("They answer different questions (brand relevance and credibility vs similarity to attention-linked ad formats), so they need not agree.")
        tbl = sc.loc[order][["handle", "engine_rank", "attention_alignment", "attention_alignment_effect_weighted", "attention_n_features", "purchase_status"]].reset_index()
        st.dataframe(tbl.rename(columns={"handle": "Creator", "engine_rank": "Engine rank", "attention_alignment": "Alignment (equal weights)",
                                         "attention_alignment_effect_weighted": "Alignment (effect-weighted)", "attention_n_features": "Features", "purchase_status": "Purchase lens"}),
                     hide_index=True, width="stretch", column_config={"Alignment (equal weights)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                                                                       "Alignment (effect-weighted)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f")})

    # ------------------------------------------------------------------ 4
    with t4:
        who = st.selectbox("Shortlisted creator", short, format_func=lambda i: f"#{int(rk.at[i, 'rank'])}  @{rk.at[i, 'handle']} ({i})")
        pr = d["profiles"][who]
        ns = pr["natural_style"]
        a, b = st.columns([1.6, 1], gap="large")
        with a:
            st.markdown(f'<div class="sec-t" style="margin-top:0">Natural content style</div><div style="margin:.3rem 0 .6rem 0">{prov("ai", "post labels (AI)")}{prov("observed", "counts from post fields")}</div>'
                        f'<div class="en-b" style="font-size:1.08rem">{esc(ns["summary"])}</div>', unsafe_allow_html=True)
        with b:
            att = pr["attention_alignment"]
            st.markdown(kpi("Attention-pattern alignment", f"{att:.0f} / 100" if att is not None else "Not scored", f"engine rank #{pr['engine_rank']}, purchase lens not scored"), unsafe_allow_html=True)
        with st.expander("What the provider's AI text says about this creator (context only, unverified)"):
            st.markdown(f"**Persona** {prov('ai')}  \n{ns['persona_ai_generated'] or 'n/a'}")
            st.markdown(f"**Format habits** {prov('ai')}  \n{ns['format_habits_ai_generated'] or 'n/a'}")

        ca, cb = st.columns(2, gap="large")
        for col, key, title, gap_, empty in [(ca, "strengths", "Matching creative characteristics (strengths)", False, "No feature reaches the strength threshold."),
                                             (cb, "gaps", "Gaps versus the ad patterns", True, "No feature falls below the gap threshold.")]:
            with col:
                section(title)
                if not pr[key]:
                    st.info(empty)
                st.markdown("".join(_entry(it, pr["supporting_ids"].get(it["feature_id"], {}), gap_) for it in pr[key]), unsafe_allow_html=True)

        section("Purchase-stage context (not scored)", "Where ad evidence links a feature to lower or higher click-to-purchase. Shown so attention gains are not mistaken for sales gains.")
        pc = pd.DataFrame(pr["purchase_context"])
        if not pc.empty:
            st.dataframe(pc[["feature", "prevalence", "ad_direction_on_cvr", "ad_effect_pts", "ad_status", "reading"]].rename(columns={
                "feature": "Feature", "prevalence": "Creator does it", "ad_direction_on_cvr": "Ad direction", "ad_effect_pts": "Ad effect (pts)", "ad_status": "Ad evidence", "reading": "Reading"}),
                hide_index=True, width="stretch", column_config={"Creator does it": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent"),
                                                                  "Ad effect (pts)": st.column_config.NumberColumn(format="%.2f")})
        if pr["mixed_signal_features"]:
            note("<b>Mixed signal:</b> " + ", ".join(pr["mixed_signal_features"]) + " are creator strengths for attention, but in ads they are associated with <i>lower</i> click-to-purchase. "
                 "Treat them as attention-stage creative and pair them with a clear product/offer step.", warn=True)
        note(f"<b>Full explanation.</b> {esc(pr['explanation'])}")

    # ------------------------------------------------------------------ 5
    with t5:
        a, b = st.columns(2, gap="large")
        who2 = a.selectbox("Creator", short + [i for i in rk.sort_values("rank").index if i not in short], format_func=lambda i: f"@{rk.at[i, 'handle']} ({i})", key="ev_cr")
        mp = d["mapping"].set_index("feature_id")
        scorable = [f for f in mp.index if mp.at[f, "used_in_score"]]
        feat = b.selectbox("Feature", scorable, format_func=lambda f: mp.at[f, "feature"], key="ev_f")
        section("Creator posts matching this feature", "Rows are posts where our rule/label sets the feature to yes. Evidence type shows how the flag was produced.")
        ep = d["ev_posts"]
        ep = ep[(ep.creator_id == who2) & (ep.feature_id == feat)].copy()
        ep["evidence_type"] = ep.evidence_type.map({"post_ai_label": "AI label", "rule_derived": "Rule on AI text"}).fillna(ep.evidence_type)
        st.dataframe(ep[["post_id", "posted_on", "post_type", "content_form", "content_type", "evidence_type", "post_url"]], hide_index=True, width="stretch",
                     column_config={"post_url": st.column_config.LinkColumn("Link", display_text="open")})
        st.caption(f"{len(ep)} posts. Alignment uses prevalence among labelled posts; carousels and photos are included.")
        section("Little Joys ads with this feature", "Outcomes for ads that carry the feature (AI-labelled; spend and ROAS are synthetic). LJ-004 is flagged because it is 30% of revenue.")
        ea = d["ev_ads"]
        ea = ea[ea.feature_id == feat].sort_values("hook_rate", ascending=False)
        st.dataframe(ea[["creative_id", "ad_ids", "product_form", "hook_rate", "cvr_click", "roas", "spend_inr", "purchases", "is_lj004", "low_evidence"]], hide_index=True, width="stretch",
                     column_config={"hook_rate": st.column_config.NumberColumn("Hook rate", format="percent"), "cvr_click": st.column_config.NumberColumn("Click→purchase", format="percent"),
                                    "roas": st.column_config.NumberColumn("ROAS", format="%.2f"), "spend_inr": st.column_config.NumberColumn("Spend ₹", format="%d")})
        st.caption("Per-ad figures are descriptive. Associations in the pattern table are estimated within product form and are not read off this list.")
