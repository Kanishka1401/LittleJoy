"""Campaign Studio page. Generation lives in src/cip/studio.py; this file is UI only."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from . import data as D
from .theme import esc, kpi, note, page_header, section

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cip import studio as S            # noqa: E402
from cip import studio_content as C    # noqa: E402

SECTION_LABEL = {"concept": "Concept", "hooks": "Hooks", "script": "Script lines", "visuals": "Visual directions",
                 "onscreen": "On-screen text", "cta": "CTA"}


@st.cache_resource(show_spinner=False)
def studio() -> S.Studio:
    return S.Studio.load(ROOT)


def ready() -> bool:
    return (ROOT / "reports" / "dna" / "json" / "creator_dna_profiles.json").exists()


def _k(cid: str, name: str) -> str:
    return f"studio_{cid}_{st.session_state['studio_rev'][cid]}_{name}"


def _sync(stu: S.Studio, cid: str):
    """Fold widget values (user edits) back into the stored brief before anything else happens."""
    b = st.session_state["studio_briefs"].get(cid)
    if not b:
        return
    ss = st.session_state
    g = lambda n, d: ss.get(_k(cid, n), d)  # noqa: E731
    hooks = [dict(text=g(f"h{i}", h["text"]), on_screen=g(f"ho{i}", h["on_screen"])) for i, h in enumerate(b["hooks"])]
    scenes = [dict(voice=g(f"v{i}", s["voice"]), visual=g(f"vi{i}", s["visual"]), text=g(f"t{i}", s["text"]))
              for i, s in enumerate(b["scenes"])]
    cta = dict(spoken=g("cta_s", b["cta"]["spoken"]), on_screen=g("cta_o", b["cta"]["on_screen"]))
    sel = b["selected_hook"]
    # scene 1 mirrors the selected hook and scene 5 the CTA (their scene widgets are read-only)
    scenes[0].update(voice=hooks[sel]["text"], text=hooks[sel]["on_screen"])
    scenes[4].update(voice=cta["spoken"], text=cta["on_screen"])
    nb = stu.apply_edits(b, hooks=hooks, scenes=scenes, cta=cta, caption=g("cap", b["post_caption"]))
    changed = any(nb[k] != b[k] for k in ("hooks", "scenes", "cta", "post_caption"))
    if changed:
        ss["studio_briefs"][cid] = nb
    else:
        ss["studio_briefs"][cid] = b


def _regen(stu, cid, sec, llm):
    ss = st.session_state
    ss["studio_briefs"][cid] = stu.regenerate(ss["studio_briefs"][cid], sec, llm=llm)
    ss["studio_rev"][cid] += 1
    st.rerun()


def _head(stu, cid, sec, title, llm):
    st.markdown('<div class="sp-rule" style="margin-top:2rem"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([5, 1.3])
    with c1:
        st.markdown(f'<div class="sp-t">{esc(title)}</div>', unsafe_allow_html=True)
    src = st.session_state["studio_briefs"][cid]["source"][sec]
    if c2.button("Regenerate", key=f"regen_{cid}_{sec}", help=f"Regenerate only: {SECTION_LABEL[sec]} ({src})", use_container_width=True):
        _regen(stu, cid, sec, llm)
    c1.caption(f"Source: {src}")


def _timeline(scenes: list) -> str:
    parts = []
    for i, s in enumerate(scenes):
        cls = "hook" if i == 0 else ("cta" if i == len(scenes) - 1 else "")
        label = "Hook" if i == 0 else ("CTA" if i == len(scenes) - 1 else f"Scene {s['n']}")
        parts.append(f'<div class="tl-s {cls}" style="flex:{max(float(s["end"]) - float(s["start"]), 1):.1f}"><b>{label}</b>{s["start"]}–{s["end"]} s</div>')
    return f'<div class="tl">{"".join(parts)}</div>'


def render():
    page_header("Campaign Studio",
                "Personalised campaign briefs for the five shortlisted creators, written from each creator's real posts, their Creative DNA profile "
                "and only the product statements found in Little Joys' own ad files.",
                "Drafts, brand to confirm")
    if not ready() or not D.outputs_ready():
        st.error("Required outputs are missing. Run the creator and Creative DNA scripts first.")
        return
    stu = studio()
    ss = st.session_state
    ss.setdefault("studio_briefs", {})
    ss.setdefault("studio_rev", {c: 0 for c in S.SHORTLIST})
    rk = D.creator_outputs()["ranking"].set_index("creator_id")

    # ---------- controls
    c1, c2, c3, c4 = st.columns([2.4, 1.4, 1.2, 1.6], gap="large")
    cid = c1.selectbox("Creator", S.SHORTLIST, key="studio_creator",
                       format_func=lambda c: f"#{int(rk.at[c, 'rank'])}  {stu.creators.at[c, 'handle']}  ({c})")
    default_prod = C.CREATORS[cid]["product"]
    product = c2.selectbox("Product", list(C.PRODUCTS), index=list(C.PRODUCTS).index(default_prod), key=f"studio_prod_{cid}")
    seed = c3.number_input("Variant seed", 0, 50, 0, key=f"studio_seed_{cid}")
    llm_fn = S.anthropic_callable()
    use_llm = c4.toggle("Use LLM when regenerating", value=False, disabled=llm_fn is None, key="studio_llm",
                        help="Needs ANTHROPIC_API_KEY and the anthropic package. Output is claim-validated and falls back to templates."
                        if llm_fn is None else "Output is claim-validated; unsafe output falls back to templates.")
    llm = llm_fn if (use_llm and llm_fn) else None
    if llm_fn is None:
        st.caption("Running in template mode (no API key needed). Every section is generated from templates, evidence and verified facts.")

    _sync(stu, cid)
    if st.button("Generate campaign brief", key="studio_generate"):
        ss["studio_briefs"][cid] = stu.new_brief(cid, product, int(seed))
        ss["studio_rev"][cid] += 1
        st.rerun()
    if cid not in ss["studio_briefs"]:
        ss["studio_briefs"][cid] = stu.new_brief(cid, product, int(seed))
    b = ss["studio_briefs"][cid]
    if b["product"] != product:
        ss["studio_briefs"][cid] = b = stu.new_brief(cid, product, int(seed))
        ss["studio_rev"][cid] += 1
        st.rerun()

    findings = S.validate_brief(b, stu.facts)
    errs = [f for f in findings if f.severity == "error"]
    warns = [f for f in findings if f.severity == "warning"]
    ph = b["placeholders"]

    k = st.columns(4, gap="large")
    k[0].markdown(kpi("Timeline", f"{b['timing']['total_s']} s", f"about {b['timing']['est_speech_s']:.0f} s of speech"), unsafe_allow_html=True)
    k[1].markdown(kpi("Claim check", "Pass" if not errs else f"{len(errs)} issue(s)", "no banned or untraceable claims" if not errs else "see the checks panel"), unsafe_allow_html=True)
    k[2].markdown(kpi("Placeholders", str(len(ph)), "need Little Joys input"), unsafe_allow_html=True)
    k[3].markdown(kpi("Facts used", str(len(b["fact_table"])), "brand-stated, from ads.csv"), unsafe_allow_html=True)

    left, right = st.columns([3, 1.35], gap="large")
    with right:
        st.markdown('<div class="sp-rule" style="margin-top:2.4rem"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sp-t">Checks</div>', unsafe_allow_html=True)
        if errs:
            for f in errs:
                st.error(f"{f.where}: {f.message} ('{f.match}')")
        else:
            st.success("No banned, untraceable or competitor claims found in the current text (including your edits).")
        for f in warns:
            st.warning(f"{f.where}: {f.message}")
        if ph:
            with st.expander(f"Placeholders to resolve ({len(ph)})", expanded=True):
                for p in ph:
                    st.markdown(f"- `{p}`")
        with st.expander("Verified product facts used", expanded=False):
            st.caption("Quoted verbatim from Little Joys' own ad claims. Brand-stated; confirm with the brand before publishing.")
            if b["fact_table"]:
                st.dataframe(pd.DataFrame(b["fact_table"]).assign(ad_ids=lambda d: d.ad_ids.map(", ".join)), hide_index=True, use_container_width=True)
            else:
                st.caption("No brand-stated product facts were found in the ad files for this product, so the script relies on placeholders.")
        with st.expander("Restricted claims found in ad files (never used)", expanded=False):
            st.dataframe(S.restricted_claims(stu.ads), hide_index=True, use_container_width=True)
        section("Download")
        md, js = S.to_markdown(b, findings), S.to_json(b, findings)
        st.download_button("Download brief (.md)", md, file_name=f"brief_{cid}_{b['product']}.md", mime="text/markdown", use_container_width=True)
        st.download_button("Download brief (.json)", js, file_name=f"brief_{cid}_{b['product']}.json", mime="application/json", use_container_width=True)

    with left:
        # 1 concept
        _head(stu, cid, "concept", "1. Campaign concept", llm)
        co = b["concept"]
        st.markdown(f'<div class="pf-n" style="font-size:clamp(1.8rem,3vw,2.6rem)">{esc(co["title"])}</div>'
                    f'<div class="pf-p">{esc(co["archetype"])}</div>', unsafe_allow_html=True)
        st.write(co["big_idea"])
        note(esc(co["objective"]))
        with st.expander("Why this creator (Creative DNA) and supporting evidence", expanded=False):
            for x in co["why_fit"]:
                st.markdown(f"- {x}")
            ev = pd.DataFrame(co["evidence"]).rename(columns={"kind": "type", "id": "ID", "note": "What it shows", "url": "link"})
            st.dataframe(ev, hide_index=True, use_container_width=True,
                         column_config={"link": st.column_config.LinkColumn("link")})

        # 2 hooks
        _head(stu, cid, "hooks", "2. Three alternative hooks", llm)
        for i, h in enumerate(b["hooks"]):
            a, bcol = st.columns([5, 2])
            a.text_area(f"Hook {i + 1}: {h['angle']}", h["text"], key=_k(cid, f"h{i}"), height=80)
            bcol.text_input("On-screen", h["on_screen"], key=_k(cid, f"ho{i}"))
            st.caption(h["rationale"])
        sel = st.radio("Hook used in the script", [1, 2, 3], index=b["selected_hook"], horizontal=True, key=_k(cid, "sel"))
        if sel - 1 != b["selected_hook"]:
            ss["studio_briefs"][cid] = stu.select_hook(b, sel - 1)
            ss["studio_rev"][cid] += 1
            st.rerun()

        # 3 script
        _head(stu, cid, "script", f"3. Script ({b['timing']['total_s']} s)", llm)
        st.markdown(_timeline(b["scenes"]), unsafe_allow_html=True)
        st.caption("Scene 1 is the selected hook and scene 5 is the CTA (read-only here; edit them in sections 2 and 6).")
        for i, s in enumerate(b["scenes"]):
            st.text_area(f"Scene {s['n']}, {s['start']}–{s['end']} s (about {s['est_speech_s']:.0f} s of speech)", s["voice"], key=_k(cid, f"v{i}"), height=90,
                         disabled=i in (0, 4), help="Edit this line in the Hooks / CTA section." if i in (0, 4) else None)

        # 4 visuals
        _head(stu, cid, "visuals", "4. Scene-by-scene visual directions", llm)
        for i, s in enumerate(b["scenes"]):
            st.text_area(f"Scene {s['n']}, {s['start']}–{s['end']} s", s["visual"], key=_k(cid, f"vi{i}"), height=80)

        # 5 on-screen
        _head(stu, cid, "onscreen", "5. On-screen text and captions", llm)
        for i, s in enumerate(b["scenes"]):
            a, bcol = st.columns(2)
            a.text_input(f"Scene {s['n']} overlay", s["text"], key=_k(cid, f"t{i}"), disabled=i in (0, 4))
            bcol.text_input(f"Scene {s['n']} subtitle (auto from spoken line)", s["caption"], disabled=True, key=_k(cid, f"c{i}"))
        st.text_area("Post caption", b["post_caption"], key=_k(cid, "cap"), height=90)

        # 6 CTA
        _head(stu, cid, "cta", "6. Suggested CTA", llm)
        st.text_area("Spoken CTA (scene 5)", b["cta"]["spoken"], key=_k(cid, "cta_s"), height=80)
        st.text_input("On-screen CTA", b["cta"]["on_screen"], key=_k(cid, "cta_o"))
        st.caption(b["cta"]["note"])

        # 7 tone
        st.markdown('<div class="sp-rule" style="margin-top:2rem"></div><div class="sp-t">7. Tone and delivery</div>', unsafe_allow_html=True)
        t = b["tone"]
        st.write(t["summary"])
        for x in t["delivery"]:
            st.markdown(f"- {x}")
        st.caption(f"Language: {t['language']}. Camera: {t['camera']}. Profile voice (AI-generated): {t['creator_voice_in_profile']}")

        # 8 avoid
        st.markdown('<div class="sp-rule" style="margin-top:2rem"></div><div class="sp-t">8. Claims and statements to avoid</div>', unsafe_allow_html=True)
        for a in b["avoid"]:
            st.markdown(f"- {a['item']}  \n  <span style='color:#5E6A62;font-size:.85rem'>{esc(a['reason'])}. Source: {esc(a['source'])}</span>", unsafe_allow_html=True)
    note("Scripts are drafts. Product statements are brand-stated claims from Little Joys' ad files, not independently verified. Hinglish lines need native-speaker review "
         "and legal/brand sign-off before shooting.", warn=True)
