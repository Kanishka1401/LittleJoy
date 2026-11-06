"""Visual system for the Little Joys editorial interface.

Palette, global CSS, Plotly template and the small HTML components shared by every page.
Nothing in here touches data or scoring: it only decides how existing numbers are drawn.
"""
from __future__ import annotations

import html

import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------- palette
IVORY, PAPER, INK = "#F5F0E7", "#FBF8F2", "#242D27"          # page, raised surfaces, forest
SAGE, TERRA, BUTTER = "#D6E2D2", "#E98C70", "#E8D99F"
MUTED, HAIR, TRACK, STONE = "#5E6A62", "#D8D1C2", "#EAE3D3", "#B9B2A0"
DEEP_SAGE, SAGE_MID, CLAY, BUTTER_DEEP = "#7E9A84", "#B5C9B2", "#B04E33", "#C9B45E"   # tints of the brand colours

# names kept so older imports keep working
LINE, BG, CARD = HAIR, IVORY, PAPER
PRIMARY, TEAL, AMBER, ROSE, SKY, VIOLET = INK, DEEP_SAGE, BUTTER_DEEP, TERRA, SAGE_MID, CLAY
SERIES = [INK, TERRA, DEEP_SAGE, BUTTER_DEEP, CLAY, SAGE_MID, STONE]
DIM_COLORS = {"content_relevance": INK, "engagement_quality": TERRA, "creative_compatibility": BUTTER,
              "authenticity": DEEP_SAGE, "audience_fit": SAGE}
CONF_COLORS = {"High": INK, "Medium": DEEP_SAGE, "Low": TERRA}

_FONTS = """
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,300..800&family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,300..800&display=swap');
"""

_ROOT = (":root{--ivory:%s;--paper:%s;--ink:%s;--sage:%s;--terra:%s;--butter:%s;--muted:%s;--hair:%s;--track:%s;--stone:%s;"
         "--deep-sage:%s;--sage-mid:%s;--clay:%s;--butter-deep:%s;"
         "--sans:'Bricolage Grotesque','Avenir Next','Helvetica Neue',Arial,sans-serif;"
         "--serif:'Newsreader',Georgia,'Times New Roman',serif;}"
         % (IVORY, PAPER, INK, SAGE, TERRA, BUTTER, MUTED, HAIR, TRACK, STONE, DEEP_SAGE, SAGE_MID, CLAY, BUTTER_DEEP))

_RULES = """
/* ---------- base ---------- */
.stApp { background: var(--ivory); color: var(--ink); font-family: var(--sans); }
.stApp button, .stApp input, .stApp textarea, .stApp select { font-family: var(--sans); }
header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none !important; }
.block-container { max-width: 1240px; padding: 1.5rem 2.6rem 5rem 2.6rem; }
h1, h2, h3, h4 { font-family: var(--sans); letter-spacing: -0.025em; color: var(--ink); font-weight: 700; }
div[data-testid="stMarkdown"] p, div[data-testid="stMarkdown"] li { font-family: var(--serif); font-size: 1.02rem; line-height: 1.62; }
div[data-testid="stCaptionContainer"], div[data-testid="stCaptionContainer"] * { font-family: var(--serif); font-style: italic; color: var(--muted); font-size: .92rem; }
a { color: var(--clay); text-underline-offset: 3px; text-decoration-thickness: 1px; }
:focus-visible { outline: 2px solid var(--terra); outline-offset: 2px; }

/* ---------- masthead ---------- */
.brand { display: flex; align-items: baseline; gap: .75rem; flex-wrap: wrap; }
.brand-name { font-weight: 800; font-size: 1.6rem; letter-spacing: -0.045em; font-stretch: 85%; line-height: 1; }
.brand-dot { display: inline-block; width: .46em; height: .46em; border-radius: 50%; background: var(--terra); margin-left: .1em; }
.brand-sub { font-family: var(--serif); font-style: italic; color: var(--muted); font-size: .98rem; }
.st-key-nav [role="radiogroup"], .st-key-nav [data-testid="stRadioGroup"] { gap: .15rem 1.5rem; flex-wrap: wrap; justify-content: flex-end; }
.st-key-nav label { padding: .35rem 0 !important; margin: 0 !important; cursor: pointer; border-bottom: 2px solid transparent; width: auto !important; }
.st-key-nav label p { font-family: var(--sans); font-size: .92rem; font-weight: 500; color: var(--muted); }
.st-key-nav label:hover p { color: var(--ink); }
.st-key-nav label:has(input:checked), .st-key-nav label[data-selected="true"] { border-bottom-color: var(--terra); }
.st-key-nav label:has(input:checked) p, .st-key-nav label[data-selected="true"] p { color: var(--ink); font-weight: 700; }
.st-key-nav label div:not(:has(p)):has(~ div) { display: none !important; }
.colophon { border-top: 1px solid var(--hair); margin-top: 3.5rem; padding-top: .9rem; color: var(--muted); font-family: var(--serif); font-style: italic; font-size: .9rem; }

/* ---------- page header and spreads ---------- */
.ph { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); gap: 2.6rem; align-items: end; padding: 2.4rem 0 1.5rem 0; border-bottom: 1px solid var(--ink); margin-bottom: 1.8rem; }
.ph .ph-title { font-family: var(--sans); font-weight: 700; font-stretch: 85%; font-size: clamp(2.3rem, 4.8vw, 4rem) !important; line-height: 1 !important; letter-spacing: -0.035em; margin: 0 !important; padding: 0 !important; color: var(--ink); }
.ph .ph-title.long { font-size: clamp(1.9rem, 3.5vw, 2.95rem) !important; line-height: 1.07 !important; }
.ph-deck { font-family: var(--serif); font-style: italic; font-size: 1.14rem; line-height: 1.5; color: var(--muted); }
.ph-tag { display: inline-block; margin-top: .85rem; border: 1px solid var(--ink); border-radius: 2px; padding: .1rem .5rem; font-size: .74rem; font-weight: 600; }
.sp-rule { border-top: 1px solid var(--ink); margin: 2.8rem 0 1rem 0; }
.sp-t { font-weight: 700; font-size: 1.3rem; letter-spacing: -0.025em; line-height: 1.12; }
.sp-n { font-family: var(--serif); font-style: italic; color: var(--muted); font-size: .94rem; line-height: 1.45; margin-top: .5rem; }
.sec-t { font-weight: 700; font-size: 1.05rem; letter-spacing: -0.015em; margin: 1.6rem 0 .15rem 0; }
.sec-d { font-family: var(--serif); font-style: italic; color: var(--muted); font-size: .95rem; margin-bottom: .6rem; line-height: 1.45; }
.ch-t { font-weight: 650; font-size: .96rem; letter-spacing: -0.01em; margin: .5rem 0 -.7rem 0; line-height: 1.3; }

/* ---------- stats ---------- */
.stat { border-top: 1px solid var(--ink); padding-top: .65rem; height: 100%; }
.stat-l { font-size: .8rem; font-weight: 600; color: var(--muted); display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; }
.stat-v { font-weight: 700; font-stretch: 88%; font-size: 2.3rem; letter-spacing: -0.035em; line-height: 1.05; margin: .25rem 0 .15rem 0; }
.stat-s { font-family: var(--serif); font-style: italic; font-size: .9rem; color: var(--muted); line-height: 1.35; }
.tag-syn { font-size: .64rem; font-weight: 700; background: var(--butter); color: var(--ink); padding: .02rem .35rem; border-radius: 2px; }

/* ---------- findings ---------- */
.fd { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.55fr); gap: 1.8rem; padding: 1.1rem 0; border-top: 1px solid var(--hair); }
.fd:first-child { border-top: 0; padding-top: 0; }
.fd-t { font-weight: 700; font-size: 1.12rem; letter-spacing: -0.018em; line-height: 1.22; }
.fd-d { font-family: var(--serif); font-size: 1.02rem; line-height: 1.6; }

/* ---------- creator board ---------- */
.lg { display: flex; flex-wrap: wrap; gap: .3rem 1.3rem; margin: 0 0 .7rem 0; font-size: .78rem; color: var(--muted); }
.lg i { display: inline-block; width: .72rem; height: .72rem; margin-right: .38rem; vertical-align: -.06rem; box-shadow: inset 0 0 0 1px rgba(36,45,39,.28); }
.cr { display: grid; grid-template-columns: 3.4rem minmax(0, 1.25fr) minmax(0, 2.8fr) 4.4rem 10rem; gap: 1.05rem; align-items: center; padding: .95rem 0; border-top: 1px solid var(--hair); }
.cr:last-child { border-bottom: 1px solid var(--hair); }
.cr.lead { background: rgba(214,226,210,.5); border-top-color: var(--ink); padding-left: .8rem; padding-right: .8rem; margin: 0 -.8rem; }
.cr-rk { font-weight: 800; font-stretch: 80%; font-size: 2.6rem; letter-spacing: -0.05em; line-height: 1; }
.cr.lead .cr-rk { color: var(--clay); }
.cr.rest .cr-rk { color: var(--stone); }
.cr-h { font-weight: 700; font-size: 1.05rem; letter-spacing: -0.015em; overflow-wrap: anywhere; line-height: 1.2; }
.cr-m { font-size: .78rem; color: var(--muted); margin-top: .15rem; }
.cr-m .up { color: #4F7058; font-weight: 700; } .cr-m .dn { color: var(--clay); font-weight: 700; }
.cr-sc { font-weight: 700; font-stretch: 88%; font-size: 1.95rem; letter-spacing: -0.04em; text-align: right; line-height: 1; }
.cr-cf { font-size: .76rem; color: var(--muted); line-height: 1.5; }
.rb-track { display: flex; height: 1.05rem; background: var(--track); }
.rb-s { display: block; height: 100%; box-shadow: inset -1px 0 0 var(--ivory); }
.rb-i { height: 6px; margin-top: 4px; border: 1px solid var(--ink); border-top: 0; opacity: .75; }
.mt { display: inline-flex; align-items: flex-end; gap: 2px; margin-right: .45rem; vertical-align: -1px; }
.mt i { display: block; width: 5px; background: var(--hair); }
.mt i:nth-child(1) { height: 7px; } .mt i:nth-child(2) { height: 11px; } .mt i:nth-child(3) { height: 15px; }
.mt.High i.on { background: var(--ink); } .mt.Medium i.on { background: var(--deep-sage); } .mt.Low i.on { background: var(--terra); }
.mt-l { font-size: .78rem; font-weight: 600; color: var(--ink); }

/* ---------- notes, chips, provenance ---------- */
.note, .warn { font-family: var(--serif); font-size: 1rem; line-height: 1.55; padding: .8rem 1.05rem; margin: .5rem 0 1rem 0; border-radius: 0 2px 2px 0; border-left: 3px solid var(--deep-sage); background: rgba(214,226,210,.55); }
.warn { border-left-color: var(--terra); background: rgba(232,217,159,.42); }
.chip { display: inline-block; border: 1px solid var(--hair); background: var(--paper); border-radius: 2px; padding: .1rem .5rem; font-size: .76rem; margin: .14rem .22rem .14rem 0; font-weight: 500; }
.chip.risk { border-color: var(--terra); color: var(--clay); }
.pv { display: inline-block; border-radius: 2px; padding: .08rem .45rem; font-size: .7rem; font-weight: 700; margin: .1rem .3rem .1rem 0; }
.pv.observed { background: var(--sage); } .pv.ai { background: var(--butter); }
.pv.rule { background: var(--paper); box-shadow: inset 0 0 0 1px var(--ink); } .pv.assume { background: rgba(233,140,112,.32); }

/* ---------- tables, bars, entries ---------- */
.tb { width: 100%; border-collapse: collapse; }
.tb th { text-align: left; font-size: .78rem; font-weight: 600; color: var(--muted); border-bottom: 1px solid var(--ink); padding: .4rem .8rem .4rem 0; }
.tb td { font-family: var(--serif); font-size: .98rem; line-height: 1.45; border-bottom: 1px solid var(--hair); padding: .6rem .8rem .6rem 0; vertical-align: top; }
.tb td:first-child { font-family: var(--sans); font-weight: 600; font-size: .9rem; }
.cb { display: grid; grid-template-columns: minmax(0, 11rem) minmax(0, 1fr) 2.4rem; gap: .8rem; align-items: center; margin: .42rem 0; font-size: .84rem; }
.cb-t { display: block; height: 7px; background: var(--track); }
.cb-f { display: block; height: 100%; }
.cb-v { text-align: right; font-weight: 700; }
.cb-h { font-weight: 700; font-size: .92rem; margin: 1.1rem 0 .2rem 0; }
.en { border-left: 3px solid var(--deep-sage); padding: .15rem 0 .2rem 1.05rem; margin: 0 0 1.35rem 0; }
.en.gap { border-left-color: var(--terra); }
.en-h { font-weight: 700; font-size: 1.02rem; }
.en-r { font-family: var(--serif); font-style: italic; color: var(--muted); font-size: .95rem; margin: .25rem 0 .45rem 0; line-height: 1.45; }
.en-b { font-family: var(--serif); font-size: .98rem; line-height: 1.5; }
.en-c { color: var(--muted); font-size: .8rem; margin-top: .4rem; }
.pf { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2rem; align-items: end; padding: .2rem 0 1.3rem 0; border-bottom: 1px solid var(--hair); margin-bottom: 1.4rem; }
.pf-n { font-weight: 700; font-stretch: 85%; font-size: clamp(2rem, 3.6vw, 3.2rem); letter-spacing: -0.035em; line-height: 1; }
.pf-p { font-family: var(--serif); font-style: italic; color: var(--muted); font-size: 1.06rem; margin-top: .55rem; line-height: 1.45; }
.pf-r { text-align: right; }
.pf-rk { font-weight: 800; font-stretch: 78%; font-size: 5rem; line-height: .85; letter-spacing: -0.06em; color: var(--terra); }
.pf-sc { font-size: .95rem; margin: .35rem 0 .4rem 0; font-weight: 600; }
.fm { font-family: var(--serif); font-size: 1.3rem; line-height: 1.5; border-left: 3px solid var(--terra); padding: .35rem 0 .35rem 1rem; margin: .4rem 0 1rem 0; }
.tl { display: flex; gap: 3px; margin: .3rem 0 1rem 0; }
.tl-s { padding: .5rem .6rem; font-size: .74rem; line-height: 1.3; min-width: 0; background: var(--sage); border-top: 3px solid var(--deep-sage); }
.tl-s.hook { background: var(--butter); border-top-color: var(--butter-deep); } .tl-s.cta { background: rgba(233,140,112,.4); border-top-color: var(--terra); }
.tl-s b { display: block; font-size: .8rem; }

.hero { padding: 3.2rem 0 1.4rem 0; display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 2.6rem; align-items: end; }
.hero .hero-t { font-family: var(--sans); font-weight: 700; font-stretch: 82%; font-size: clamp(2.4rem, 5vw, 4.2rem) !important; line-height: 1 !important; letter-spacing: -0.04em; margin: 0 !important; padding: 0 !important; color: var(--ink); }
.hero-d { font-family: var(--serif); font-style: italic; font-size: 1.2rem; line-height: 1.55; color: var(--muted); }
.steps { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 2rem; margin-top: .8rem; }
.step { border-top: 1px solid var(--hair); padding-top: .7rem; }
.step-n { font-weight: 800; font-stretch: 80%; font-size: 2.4rem; letter-spacing: -0.05em; color: var(--terra); line-height: 1; margin-bottom: .5rem; }

/* ---------- streamlit widgets ---------- */
div[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 1.7rem; border-bottom: 1px solid var(--ink); }
div[data-testid="stTabs"] button[role="tab"] { padding: .55rem 0; background: transparent; }
div[data-testid="stTabs"] button[role="tab"] p { font-family: var(--sans); font-weight: 500; font-size: .93rem; color: var(--muted); }
div[data-testid="stTabs"] button[aria-selected="true"] p { color: var(--ink); font-weight: 700; }
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: var(--terra); height: 3px; }
div[data-testid="stTabs"] [data-baseweb="tab-border"] { background: transparent; }
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, .stTextInput input, .stNumberInput input, .stTextArea textarea { background: var(--paper) !important; border-radius: 3px !important; border-color: var(--hair) !important; }
.stTextArea textarea { font-family: var(--serif); font-size: 1rem; line-height: 1.55; }
div[data-testid="stWidgetLabel"] p { font-family: var(--sans); font-size: .8rem; font-weight: 600; color: var(--muted); }
.stButton > button, .stDownloadButton > button { border-radius: 2px; border: 1px solid var(--ink); background: transparent; color: var(--ink); font-weight: 600; font-size: .84rem; padding: .4rem .95rem; transition: background .15s, color .15s; }
.stButton > button p, .stDownloadButton > button p { font-family: var(--sans); color: inherit; font-size: .84rem; }
.stButton > button:hover, .stDownloadButton > button:hover { background: var(--ink); color: var(--ivory); border-color: var(--ink); }
div[data-testid="stExpander"] details { border: 0 !important; border-top: 1px solid var(--hair) !important; border-radius: 0 !important; background: transparent !important; }
div[data-testid="stExpander"] summary p { font-family: var(--sans); font-weight: 600; }
div[data-testid="stDataFrame"] { border: 1px solid var(--hair); border-radius: 2px; }
div[data-testid="stPlotlyChart"] { background: transparent; }
div[data-testid="stAlert"] { border-radius: 2px; }

@media (max-width: 760px) {
  .block-container { padding: 1rem 1rem 4rem 1rem; }
  .ph, .fd, .pf, .hero { grid-template-columns: 1fr; gap: 1rem; }
  .steps { grid-template-columns: 1fr; }
  .pf-r { text-align: left; }
  .cr { grid-template-columns: 2.6rem minmax(0, 1fr) 4rem; }
  .cr-rb, .cr-cf { grid-column: 2 / -1; }
  .cb { grid-template-columns: 7rem minmax(0, 1fr) 2rem; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

CSS = f"<style>{_FONTS}{_ROOT}{_RULES}</style>"
BRAND_HTML = ('<div class="brand"><span class="brand-name">Little Joys<span class="brand-dot"></span></span>'
              '<span class="brand-sub">Creator Intelligence</span></div>')

# ---------------------------------------------------------------- plotly
_FONT = "Bricolage Grotesque, Avenir Next, Helvetica Neue, Arial, sans-serif"
_AX = dict(gridcolor="#E6DFCF", zerolinecolor=STONE, linecolor=STONE, ticks="outside", tickcolor=STONE, ticklen=3,
           title_font=dict(size=11, color=MUTED), tickfont=dict(size=11, color=MUTED))
pio.templates["lj"] = go.layout.Template(layout=go.Layout(
    font=dict(family=_FONT, size=12, color=INK),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", colorway=SERIES,
    xaxis=dict(**_AX), yaxis=dict(**_AX),
    margin=dict(l=8, r=14, t=16, b=10),
    legend=dict(orientation="h", y=-0.2, x=0, font=dict(size=11), title_text=""),
    hoverlabel=dict(bgcolor=INK, font=dict(color=IVORY, family=_FONT, size=12), bordercolor=INK),
))
pio.templates.default = "lj"
PLOT_CFG = {"displayModeBar": False}


def style(fig: go.Figure, height: int = 380, **kw) -> go.Figure:
    """Apply the house template. A `title` is kept in the figure meta and drawn as HTML by `plot()`."""
    title = kw.pop("title", None)
    fig.update_layout(template="lj", height=height, meta={"t": title}, **kw)
    return fig


def plot(fig: go.Figure):
    """Draw a styled figure with its title set in the page typeface above it."""
    import streamlit as st
    meta = getattr(fig.layout, "meta", None)
    t = meta.get("t") if isinstance(meta, dict) else None
    if t:
        st.markdown(f'<div class="ch-t">{esc(t)}</div>', unsafe_allow_html=True)
    st.plotly_chart(fig, config=PLOT_CFG, width="stretch")


# ---------------------------------------------------------------- html components
def esc(x) -> str:
    return html.escape(str(x))


def colophon() -> str:
    return ('<div class="colophon">Exploratory analysis. Content labels are AI-generated and unvalidated, and nothing here is a causal claim. '
            'Ad performance figures are synthetic.</div>')


def page_header(title: str, deck: str, tag: str = "", long: bool = False):
    import streamlit as st
    tag_html = f'<div><span class="ph-tag">{esc(tag)}</span></div>' if tag else ""
    st.markdown(f'<div class="ph"><h1 class="ph-title{" long" if long else ""}">{esc(title)}</h1>'
                f'<div><div class="ph-deck">{esc(deck)}</div>{tag_html}</div></div>', unsafe_allow_html=True)


def spread(title: str, note: str = ""):
    """A ruled section with its title in the left margin. Use as `with spread(...):` for the body column."""
    import streamlit as st
    st.markdown('<div class="sp-rule"></div>', unsafe_allow_html=True)
    margin, body = st.columns([1, 3.4], gap="large")
    margin.markdown(f'<div class="sp-t">{esc(title)}</div>' + (f'<div class="sp-n">{esc(note)}</div>' if note else ""), unsafe_allow_html=True)
    return body


def section(title: str, desc: str = ""):
    import streamlit as st
    st.markdown(f'<div class="sec-t">{esc(title)}</div>' + (f'<div class="sec-d">{esc(desc)}</div>' if desc else ""), unsafe_allow_html=True)


def kpi(label: str, value: str, sub: str = "", accent: str = "", tag: str = "") -> str:
    tag_html = f'<span class="tag-syn">{esc(tag)}</span>' if tag else ""
    return (f'<div class="stat"><div class="stat-l">{esc(label)}{tag_html}</div><div class="stat-v">{esc(value)}</div>'
            f'<div class="stat-s">{esc(sub)}</div></div>')


def badge(level: str) -> str:
    on = {"High": 3, "Medium": 2, "Low": 1}.get(level, 0)
    bars = "".join(f'<i class="{"on" if i < on else ""}"></i>' for i in range(3))
    return f'<span class="mt {esc(level)}">{bars}</span><span class="mt-l">{esc(level)} confidence</span>'


def note(text: str, warn: bool = False):
    import streamlit as st
    st.markdown(f'<div class="{"warn" if warn else "note"}">{text}</div>', unsafe_allow_html=True)


def chip(text: str, risk: bool = False) -> str:
    return f'<span class="chip{" risk" if risk else ""}">{esc(text)}</span>'


def prov(kind: str, text: str = "") -> str:
    labels = {"observed": "Observed (platform metric)", "ai": "AI-generated label", "rule": "Rule-derived from AI text", "assume": "Assumption / suggestion"}
    return f'<span class="pv {kind}">{esc(text or labels[kind])}</span>'


def dim_legend(labels: dict[str, str], weights: dict[str, float] | None = None) -> str:
    items = "".join(f'<span><i style="background:{DIM_COLORS[d]}"></i>{esc(lab)}{f" {weights[d]:.0%}" if weights else ""}</span>' for d, lab in labels.items())
    return f'<div class="lg">{items}</div>'


def ribbon(contribs: dict[str, float], labels: dict[str, str], lo: float | None = None, hi: float | None = None) -> str:
    """Stacked bar: total length is the composite score on a 0-100 scale, each segment is one criterion's weighted points."""
    segs = "".join(f'<span class="rb-s" style="width:{max(v, 0):.2f}%;background:{DIM_COLORS[d]}" title="{esc(labels[d])}: {v:.1f} points"></span>'
                   for d, v in contribs.items())
    interval = f'<div class="rb-i" style="margin-left:{lo:.2f}%;width:{max(hi - lo, 0.4):.2f}%" title="90% bootstrap interval {lo:.1f} to {hi:.1f}"></div>' if lo is not None and hi is not None else ""
    return f'<div class="rb-track">{segs}</div>{interval}'


def creator_row(rank: int, handle: str, cid: str, score: float, contribs: dict[str, float], labels: dict[str, str], level: str,
                p_top5: float | None = None, delta: int | None = None, lo: float | None = None, hi: float | None = None,
                lead: bool = False, top: bool = True) -> str:
    arrow = ""
    if delta:
        arrow = f' <span class="{"up" if delta > 0 else "dn"}">{"▲" if delta > 0 else "▼"}{abs(delta)}</span>'
    p = f'<div>P(top-5) {p_top5:.0%}</div>' if p_top5 is not None else ""
    cls = "lead" if lead else ("" if top else "rest")
    return (f'<div class="cr {cls}"><div class="cr-rk">{rank}</div>'
            f'<div><div class="cr-h">@{esc(handle)}</div><div class="cr-m">{esc(cid)}{arrow}</div></div>'
            f'<div class="cr-rb">{ribbon(contribs, labels, lo, hi)}</div>'
            f'<div class="cr-sc">{score:.1f}</div><div class="cr-cf">{badge(level)}{p}</div></div>')


def comp_bar(label: str, value: float, color: str = INK, vmax: float = 100) -> str:
    return (f'<div class="cb"><span>{esc(label)}</span><span class="cb-t"><span class="cb-f" style="width:{max(min(value / vmax * 100, 100), 0):.1f}%;background:{color}"></span></span>'
            f'<span class="cb-v">{value:.0f}</span></div>')


def table_html(headers: list[str], rows: list[list]) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="tb"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
