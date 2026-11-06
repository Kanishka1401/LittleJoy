"""AI Creative Studio: fact-grounded campaign brief generation for the five shortlisted creators.

Design
- Product facts come ONLY from data/raw/ads.csv (Little Joys' own `claims_made`), resolved verbatim with the
  ad IDs that carry them. They are brand-stated, not independently verified. Missing details are
  [[CONFIRM: ...]] placeholders.
- Template generation (studio_content.py) works offline. An optional LLM callable can regenerate a section;
  its output is shape-checked and claim-validated and silently falls back to the template when it fails.
- A claim validator runs on everything (generated, LLM or hand-edited).
- Reads, never writes, the completed ad / creator / DNA outputs.
"""
from __future__ import annotations

import copy
import json
import os
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import studio_content as C

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
DNA_JSON = ROOT / "reports" / "dna" / "json" / "creator_dna_profiles.json"
SHORTLIST = ["CR-03", "CR-11", "CR-02", "CR-05", "CR-01"]
PLACEHOLDER_RE = re.compile(r"\[\[CONFIRM: [^\]]+\]\]")
FACT_RE = re.compile(r"\{([A-Z]_[A-Z0-9]+)\}")
SPEAKER_RE = re.compile(r"\b(?:[A-Z][A-Z]+(?: \([^)]*\))?):\s*")
MIN_S, MAX_S = 30, 45
N_SCENES = 5


# ---------------------------------------------------------------- product facts
@dataclass
class Fact:
    id: str
    product: str
    role: str
    text: str
    ad_ids: list
    n_ads: int
    status: str = "brand-stated (needs brand confirmation)"


def _claims(ads: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in ads.iterrows():
        for c in str(r.get("claims_made") or "").split(";"):
            c = c.strip()
            if c and c != "nan":
                rows.append((r.ad_id, c))
    return pd.DataFrame(rows, columns=["ad_id", "claim"])


def product_ads(ads: pd.DataFrame, product: str) -> pd.DataFrame:
    rx = C.PRODUCTS[product]["ad_regex"]
    blob = ads[["ad_copy", "transcript", "hook_line"]].fillna("").agg(" ".join, axis=1)
    return ads[blob.str.contains(rx, case=False, regex=True)]


def load_facts(ads: pd.DataFrame) -> dict:
    """{product: {fact_id: Fact}}. A fact missing from the data is simply absent (callers get a placeholder)."""
    out = {}
    for product, spec in C.PRODUCTS.items():
        cl = _claims(product_ads(ads, product))
        found = {}
        for fid, rx, role in spec["facts"]:
            m = cl[cl.claim.str.contains(rx, regex=True)]
            if m.empty:
                continue
            found[fid] = Fact(fid, product, role, m.claim.value_counts().index[0],
                              sorted(m.ad_id.unique().tolist()), int(m.ad_id.nunique()))
        out[product] = found
    return out


def restricted_claims(ads: pd.DataFrame) -> pd.DataFrame:
    """Claims in the ad files that look unsubstantiated; shown to users, never used by the generator."""
    cl = _claims(ads)
    rows = []
    for rx, label, why in C.RESTRICTED_AD_PATTERNS:
        m = cl[cl.claim.str.contains(rx, case=False, regex=True)]
        if len(m):
            rows.append(dict(category=label, reason=why, n_ads=int(m.ad_id.nunique()),
                             example=m.claim.iloc[0], example_ad_ids=", ".join(sorted(m.ad_id.unique())[:4])))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- validation
BANNED = [  # (regex, message)
    (r"\bimmun\w*", "Immunity claim"), (r"\bboost\w*", "'Boost' claim"),
    (r"\b(cure[sd]?|treat(s|ed|ment)?|prevent(s|ed)?|heal(s|ed)?)\b", "Treatment/prevention claim"),
    (r"\b(taller|height|weight gain|gain weight|iq|brain|memory|growth|grow faster)\b", "Growth/development claim"),
    (r"\b(clinically|proven|guarantee\w*|100% safe|doctor[- ]recommended|doctor approved|expert approved)\b", "Proof/endorsement claim"),
    (r"\b(best|only|no\.? ?1|number one|bestseller|healthier|better than|stronger|taakat|takat)\b", "Superlative/comparative claim"),
    (r"\b(gritzo|little tummys|troovy|horlicks|bournvita|pediasure|complan|boost)\b", "Competitor brand named"),
    (r"\b(lab[- ]tested|eurofins|third[- ]party)\b", "Third-party testing claim"),
    (r"\b(kids|bacche|bachche) (love|loves|pasand)\b|\blove it\b", "Scripted taste outcome"),
]
NUMERIC_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:g|gm|grams?|mg|%|x|vitamins?|minerals?|kcal|calories?|scoops?)\b", re.I)


@dataclass
class Finding:
    severity: str      # error | warning | info
    kind: str
    match: str
    message: str
    where: str = ""

    def as_dict(self):
        return self.__dict__.copy()


def strip_speakers(text: str) -> str:
    return SPEAKER_RE.sub("", text).strip()


def validate_text(text: str, allowed_fact_texts: list, where: str = "") -> list:
    out = []
    t = text or ""
    scrubbed = t
    for ft in allowed_fact_texts:               # verified fact wording is allowed verbatim
        scrubbed = scrubbed.replace(ft, " ")
    scrubbed = PLACEHOLDER_RE.sub(" ", scrubbed)
    for rx, msg in BANNED:
        for m in re.finditer(rx, scrubbed, flags=re.I):
            out.append(Finding("error", "banned_claim", m.group(0), msg, where))
    for m in NUMERIC_RE.finditer(scrubbed):
        out.append(Finding("error", "untraceable_number", m.group(0),
                           "Numeric claim does not match a verified product fact.", where))
    for p in PLACEHOLDER_RE.findall(t):
        out.append(Finding("info", "placeholder", p, "Needs input from Little Joys.", where))
    if re.search(r"\{[A-Z]_[A-Z0-9]+\}", t):
        out.append(Finding("error", "unresolved_fact", re.search(r"\{[A-Z]_[A-Z0-9]+\}", t).group(0),
                           "A fact reference was not resolved.", where))
    return out


def brief_text_fields(b: dict) -> list:
    """(where, text) for every user-visible text in a brief (used by the validator)."""
    f = [("concept.title", b["concept"]["title"]), ("concept.big_idea", b["concept"]["big_idea"])]
    f += [(f"hook[{i + 1}]", h["text"]) for i, h in enumerate(b["hooks"])]
    f += [(f"hook[{i + 1}].on_screen", h["on_screen"]) for i, h in enumerate(b["hooks"])]
    for s in b["scenes"]:
        f += [(f"scene{s['n']}.voice", s["voice"]), (f"scene{s['n']}.visual", s["visual"]), (f"scene{s['n']}.text", s["text"])]
    f += [("cta.spoken", b["cta"]["spoken"]), ("cta.on_screen", b["cta"]["on_screen"]),
          ("post_caption", b["post_caption"])]
    return f


def validate_brief(b: dict, facts: dict) -> list:
    allowed = [f.text for f in facts[b["product"]].values()]
    out = []
    for where, t in brief_text_fields(b):
        out += validate_text(t, allowed, where)
    dur = b["timing"]["total_s"]
    if not MIN_S <= dur <= MAX_S:
        out.append(Finding("error", "duration", f"{dur}s", f"Scene timeline must be {MIN_S}-{MAX_S}s.", "script"))
    est = b["timing"]["est_speech_s"]
    if est > dur * 1.1:
        out.append(Finding("warning", "too_long", f"{est:.0f}s speech", "Spoken lines may not fit the timeline; trim or re-time.", "script"))
    return out


# ---------------------------------------------------------------- context
class Studio:
    def __init__(self, ads, creators, posts, dna, raw_dir=RAW):
        self.ads, self.creators, self.posts, self.dna = ads, creators.set_index("creator_id"), posts, dna
        self.facts = load_facts(ads)
        self.ad_ids = set(ads.ad_id)
        self.post_by_id = {self.post_id(u): r for u, r in zip(posts.post_url, posts.itertuples())}

    @staticmethod
    def post_id(url: str) -> str:
        m = re.search(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", str(url))
        return m.group(1) if m else str(url)

    @classmethod
    def load(cls, root: Path = ROOT):
        raw = Path(root) / "data" / "raw"
        dna = json.loads((Path(root) / "reports" / "dna" / "json" / "creator_dna_profiles.json").read_text())
        return cls(pd.read_csv(raw / "ads.csv"), pd.read_csv(raw / "creators.csv"),
                   pd.read_csv(raw / "creator_posts.csv"), dna)

    # --- helpers
    def fact_text(self, product: str, fid: str) -> str:
        f = self.facts.get(product, {}).get(fid)
        return f.text if f else f"[[CONFIRM: product fact {fid} not found in the supplied files]]"

    def resolve(self, text: str, product: str, used: set) -> str:
        def rep(m):
            used.add(m.group(1))
            return self.fact_text(product, m.group(1))
        return FACT_RE.sub(rep, text)

    def evidence_posts(self, cid: str) -> list:
        out = []
        for pid in C.CREATORS[cid]["post_evidence"]:
            r = self.post_by_id.get(pid)
            if r is None:
                continue
            ost = "" if pd.isna(r.on_screen_text) else str(r.on_screen_text)[:80]
            out.append(dict(kind="post", id=pid, url=r.post_url,
                            note=f"{r.content_form}; topic: {r.topic}; hook: {r.hook_style}"
                                 + (f"; on-screen: {ost}" if ost else "")))
        return out

    def evidence_ads(self, cid: str, n: int = 3) -> list:
        prof, out, seen = self.dna[cid], [], set()
        items = {x["feature_id"]: x for x in prof["strengths"] + prof["gaps"]}
        for feat in C.CREATORS[cid]["dna_features"]:
            for aid in prof["supporting_ids"].get(feat, {}).get("ad_creative_ids", [])[:n]:
                if aid in self.ad_ids and aid not in seen:
                    seen.add(aid)
                    x = items.get(feat, {})
                    out.append(dict(kind="ad", id=aid, url="",
                                    note=f"Little Joys ad using '{x.get('feature', feat)}'. Creative DNA reading: {x.get('reading', 'n/a')}."))
        return out

    def why_fit(self, cid: str) -> list:
        p = self.dna[cid]
        lines = [f"Creative DNA: {p['natural_style']['summary']}"]
        feats = C.CREATORS[cid]["dna_features"]
        items = {x["feature_id"]: x for x in p["strengths"] + p["gaps"]}
        for f in feats:
            x = items.get(f)
            if x:
                lines.append(f"{x['phrase']}: {x['opportunity']} Caution: {x['caution']}")
        lines.append(f"Attention alignment score {p['attention_alignment']:.0f}/100 (AI-labelled posts vs paid-ad hook-rate patterns; "
                     "organic engagement is not treated as evidence of paid performance).")
        return lines

    # --- section builders (deterministic given variant index n)
    def _pick(self, options, n, offset=0):
        return options[(n + offset) % len(options)]

    def build_concept(self, cid, product, n):
        spec = C.CREATORS[cid]
        title, idea = self._pick(spec["concepts"], n)
        return dict(title=title, big_idea=idea, archetype=spec["archetype"],
                    objective="Attention-stage creative test with this creator. A hypothesis, not a prediction: organic results do not predict paid performance.",
                    why_fit=self.why_fit(cid),
                    evidence=self.evidence_posts(cid) + self.evidence_ads(cid))

    def build_hooks(self, cid, product, n):
        spec = C.CREATORS[cid]
        pool = list(spec["hooks"])
        random.Random(f"{cid}-hooks-{n}").shuffle(pool)
        chosen, angles = [], set()
        for h in pool:
            if h[0] not in angles:
                chosen.append(h)
                angles.add(h[0])
            if len(chosen) == 3:
                break
        out = []
        for angle, text, onscreen, pid in chosen:
            r = self.post_by_id.get(pid)
            why = (f"Echoes this creator's real post {pid} (hook style: {r.hook_style})." if r is not None
                   else f"Based on creator post {pid}.")
            out.append(dict(text=text, angle=angle, on_screen=onscreen, evidence_post=pid, rationale=why))
        return out

    def build_cta(self, cid, product, n):
        d = copy.deepcopy(self._pick(C.CREATORS[cid]["ctas"], n))
        return d

    def build_voice(self, cid, product, n):
        return [self._pick(o, n, offset=i) for i, o in enumerate(C.CREATORS[cid]["voice"])]

    def build_visuals(self, cid, product, n):
        return [self._pick(o, n, offset=i) for i, o in enumerate(C.CREATORS[cid]["visual"])]

    def build_texts(self, cid, product, n):
        return [self._pick(o, n, offset=i) for i, o in enumerate(C.CREATORS[cid]["text"])]

    def tone(self, cid):
        spec, row = C.CREATORS[cid], self.creators.loc[cid]
        t = copy.deepcopy(spec["tone"])
        t["creator_voice_in_profile"] = str(row.voice)
        t["catchphrases_in_profile"] = str(row.catchphrases)
        t["native_in_profile"] = str(row.what_feels_native)
        return t

    def avoid(self, cid):
        out = [dict(item=i, reason=r, source="global rule") for _, i, r in C.GLOBAL_AVOID]
        spec, row = C.CREATORS[cid], self.creators.loc[cid]
        out += [dict(item=i, reason="Creator-specific (from her/his own profile and posts).", source="creator profile") for i in spec["creator_avoid"]]
        p = self.posts[(self.posts.creator_id == cid) & self.posts.brands_visible.notna()]
        brands = sorted({b.strip() for v in p.brands_visible for b in re.split(r"[;,]", str(v)) if b.strip()})
        if brands:
            out.append(dict(item=f"Other brands visible in this creator's posts (AI-labelled): {', '.join(brands[:10])}. Do not show or mention any in the Little Joys video.",
                            reason="Exclusivity and clean-brand framing; verify contracts.", source="post labels"))
        out.append(dict(item="Foreign-feeling styles per profile: " + str(row.what_would_feel_foreign), reason="From the creator's AI-generated profile.", source="creator profile (AI-generated)"))
        return out

    def timing(self, cid, scenes):
        pace = C.CREATORS[cid]["pace"]
        t, tot_est = 0, 0.0
        for s, d in zip(scenes, C.CREATORS[cid]["durations"]):
            s["start"], s["end"] = t, t + d
            t += d
            words = len(PLACEHOLDER_RE.sub("word word word word", strip_speakers(s["voice"])).split())
            s["est_speech_s"] = round(words / pace, 1)
            tot_est += words / pace
        return dict(total_s=t, est_speech_s=round(tot_est, 1), pace_words_per_s=pace)

    @staticmethod
    def captions(voice: str) -> str:
        return re.sub(r"\s+", " ", strip_speakers(voice))

    # --- assemble
    def new_brief(self, cid: str, product: str | None = None, seed: int = 0) -> dict:
        spec = C.CREATORS[cid]
        product = product or spec["product"]
        v = {s: seed for s in C.SECTIONS}
        b = dict(creator_id=cid, handle=str(self.creators.loc[cid, "handle"]), product=product,
                 product_name=C.PRODUCTS[product]["name"], variants=v,
                 source={s: "template" for s in C.SECTIONS}, selected_hook=0, edited=[])
        b["concept"] = self.build_concept(cid, product, v["concept"])
        b["hooks"] = self.build_hooks(cid, product, v["hooks"])
        b["cta"] = self.build_cta(cid, product, v["cta"])
        b["tone"] = self.tone(cid)
        b["avoid"] = self.avoid(cid)
        self._assemble(b, voice=self.build_voice(cid, product, v["script"]),
                       visuals=self.build_visuals(cid, product, v["visuals"]),
                       texts=self.build_texts(cid, product, v["onscreen"]))
        b["post_caption"] = spec["caption"]
        self._resolve_all(b)
        return b

    def _assemble(self, b, voice=None, visuals=None, texts=None):
        """Rebuild the scenes list. Unspecified parts keep the existing values."""
        old = b.get("scenes") or [dict(voice="", visual="", text="") for _ in range(N_SCENES)]
        hook = b["hooks"][b["selected_hook"]]
        v_ = [hook["text"]] + (voice if voice is not None else [s["voice"] for s in old[1:4]]) + [b["cta"]["spoken"]]
        vi = visuals if visuals is not None else [s["visual"] for s in old]
        tx = [hook["on_screen"]] + (texts if texts is not None else [s["text"] for s in old[1:4]]) + [b["cta"]["on_screen"]]
        scenes = []
        for i in range(N_SCENES):
            scenes.append(dict(n=i + 1, voice=v_[i], visual=vi[i], text=tx[i]))
        b["scenes"] = scenes
        b["timing"] = self.timing(b["creator_id"], scenes)

    def _resolve_all(self, b):
        used: set = set()
        prod = b["product"]
        r = lambda s: self.resolve(s, prod, used)  # noqa: E731
        for h in b["hooks"]:
            h["text"], h["on_screen"] = r(h["text"]), r(h["on_screen"])
        b["cta"]["spoken"], b["cta"]["on_screen"] = r(b["cta"]["spoken"]), r(b["cta"]["on_screen"])
        for s in b["scenes"]:
            s["voice"], s["visual"], s["text"] = r(s["voice"]), r(s["visual"]), r(s["text"])
            s["caption"] = self.captions(s["voice"])
        b["post_caption"] = r(b["post_caption"])
        for k in ("title", "big_idea"):
            b["concept"][k] = r(b["concept"][k])
        b["timing"] = self.timing(b["creator_id"], b["scenes"])
        b["facts_used"] = sorted(used)
        facts = self.facts[prod]
        b["fact_table"] = [dict(id=f.id, text=f.text, role=f.role, ad_ids=f.ad_ids[:6], n_ads=f.n_ads, status=f.status)
                           for f in facts.values() if f.id in used]
        b["placeholders"] = sorted({p for _, t in brief_text_fields(b) for p in PLACEHOLDER_RE.findall(t)})

    # --- section regeneration (changes only the requested section)
    def regenerate(self, b: dict, section: str, llm=None) -> dict:
        if section not in C.SECTIONS:
            raise ValueError(f"unknown section {section}")
        nb = copy.deepcopy(b)
        cid, prod = nb["creator_id"], nb["product"]
        nb["variants"][section] += 1
        n = nb["variants"][section]
        if llm is not None:
            res = self._llm_section(nb, section, llm)
            if res is not None:
                nb["source"][section] = "llm"
                self._finish(nb)
                return nb
        nb["source"][section] = "template"
        if section == "concept":
            nb["concept"] = self.build_concept(cid, prod, n)
        elif section == "hooks":
            nb["hooks"] = self.build_hooks(cid, prod, n)
            nb["selected_hook"] = 0
            self._assemble(nb)
        elif section == "script":
            self._assemble(nb, voice=self.build_voice(cid, prod, n))
        elif section == "visuals":
            self._assemble(nb, visuals=self.build_visuals(cid, prod, n))
        elif section == "onscreen":
            self._assemble(nb, texts=self.build_texts(cid, prod, n))
            nb["post_caption"] = C.CREATORS[cid]["caption"]
        elif section == "cta":
            nb["cta"] = self.build_cta(cid, prod, n)
            self._assemble(nb)
        self._finish(nb, only=section)
        return nb

    def _finish(self, nb, only=None):
        """Resolve fact references only in the freshly generated text (edited text is left alone)."""
        used = set(nb.get("facts_used", []))
        prod = nb["product"]
        r = lambda s: self.resolve(s, prod, used)  # noqa: E731
        if only in (None, "concept"):
            for k in ("title", "big_idea"):
                nb["concept"][k] = r(nb["concept"][k])
        if only in (None, "hooks"):
            for h in nb["hooks"]:
                h["text"], h["on_screen"] = r(h["text"]), r(h["on_screen"])
        if only in (None, "cta"):
            nb["cta"]["spoken"], nb["cta"]["on_screen"] = r(nb["cta"]["spoken"]), r(nb["cta"]["on_screen"])
        for s in nb["scenes"]:
            s["voice"], s["visual"], s["text"] = r(s["voice"]), r(s["visual"]), r(s["text"])
            s["caption"] = self.captions(s["voice"])
        nb["post_caption"] = r(nb["post_caption"])
        nb["timing"] = self.timing(nb["creator_id"], nb["scenes"])
        nb["facts_used"] = sorted(used)
        facts = self.facts[prod]
        nb["fact_table"] = [dict(id=f.id, text=f.text, role=f.role, ad_ids=f.ad_ids[:6], n_ads=f.n_ads, status=f.status)
                            for f in facts.values() if any(f.text in t for _, t in brief_text_fields(nb))]
        nb["placeholders"] = sorted({p for _, t in brief_text_fields(nb) for p in PLACEHOLDER_RE.findall(t)})

    def select_hook(self, b: dict, i: int) -> dict:
        nb = copy.deepcopy(b)
        nb["selected_hook"] = i
        h = nb["hooks"][i]
        nb["scenes"][0]["voice"], nb["scenes"][0]["text"] = h["text"], h["on_screen"]
        nb["scenes"][0]["caption"] = self.captions(h["text"])
        nb["timing"] = self.timing(nb["creator_id"], nb["scenes"])
        return nb

    def apply_edits(self, b: dict, hooks=None, scenes=None, cta=None, caption=None) -> dict:
        """Store user edits (plain text). Marks the sections as edited; validation runs on the edited text."""
        nb = copy.deepcopy(b)
        if hooks:
            for h, e in zip(nb["hooks"], hooks):
                h["text"], h["on_screen"] = e.get("text", h["text"]), e.get("on_screen", h["on_screen"])
            nb["source"]["hooks"] = "edited"
        if scenes:
            for s, e in zip(nb["scenes"], scenes):
                for k in ("voice", "visual", "text"):
                    if k in e:
                        s[k] = e[k]
                s["caption"] = self.captions(s["voice"])
            nb["source"]["script"] = "edited"
        if cta:
            nb["cta"].update({k: v for k, v in cta.items() if k in ("spoken", "on_screen")})
            nb["source"]["cta"] = "edited"
        if caption is not None:
            nb["post_caption"] = caption
        nb["timing"] = self.timing(nb["creator_id"], nb["scenes"])
        nb["placeholders"] = sorted({p for _, t in brief_text_fields(nb) for p in PLACEHOLDER_RE.findall(t)})
        return nb

    # --- optional LLM path
    def _llm_section(self, nb, section, llm):
        """Ask the LLM for one section; return the parsed value if it passes shape + claim validation, else None."""
        try:
            prompt = build_prompt(self, nb, section)
            raw = llm(prompt)
            data = json.loads(re.search(r"\{.*\}|\[.*\]", raw, re.S).group(0))
            allowed = [f.text for f in self.facts[nb["product"]].values()]
            if section == "hooks":
                assert isinstance(data, list) and len(data) == 3
                new = [dict(text=str(d["text"]), angle=str(d.get("angle", "llm")), on_screen=str(d.get("on_screen", "")),
                            evidence_post=str(d.get("evidence_post", nb["hooks"][0]["evidence_post"])),
                            rationale="LLM-generated; validated against verified facts.") for d in data]
                texts = [h["text"] + " " + h["on_screen"] for h in new]
            elif section in ("script", "visuals", "onscreen"):
                assert isinstance(data, list) and len(data) == (3 if section != "onscreen" else 3)
                texts = [str(x) for x in data]
            elif section == "cta":
                new = dict(kind="llm", spoken=str(data["spoken"]), on_screen=str(data["on_screen"]), note="LLM-generated; validated.")
                texts = [new["spoken"], new["on_screen"]]
            elif section == "concept":
                new = dict(nb["concept"], title=str(data["title"]), big_idea=str(data["big_idea"]))
                texts = [new["title"], new["big_idea"]]
            else:
                return None
            bad = [f for t in texts for f in validate_text(t, allowed) if f.severity == "error"]
            if bad:
                return None
            if section == "hooks":
                nb["hooks"], nb["selected_hook"] = new, 0
                self._assemble(nb)
            elif section == "script":
                self._assemble(nb, voice=texts)
            elif section == "visuals":
                vis = [nb["scenes"][0]["visual"]] + texts + [nb["scenes"][4]["visual"]]
                self._assemble(nb, visuals=vis)
            elif section == "onscreen":
                self._assemble(nb, texts=texts)
            elif section == "cta":
                nb["cta"] = new
                self._assemble(nb)
            elif section == "concept":
                nb["concept"] = new
            return True
        except Exception:
            return None


def build_prompt(st: Studio, b: dict, section: str) -> str:
    cid, prod = b["creator_id"], b["product"]
    facts = "\n".join(f"- {f.id}: \"{f.text}\"" for f in st.facts[prod].values())
    spec = {
        "hooks": 'Return a JSON array of exactly 3 objects {"text","angle","on_screen","evidence_post"}.',
        "script": "Return a JSON array of exactly 3 strings: the spoken lines for scenes 2, 3 and 4.",
        "visuals": "Return a JSON array of exactly 3 strings: visual directions for scenes 2, 3 and 4.",
        "onscreen": "Return a JSON array of exactly 3 strings: on-screen text overlays for scenes 2, 3 and 4.",
        "cta": 'Return a JSON object {"spoken","on_screen"}.',
        "concept": 'Return a JSON object {"title","big_idea"}.',
    }[section]
    ev = "\n".join(f"- {e['id']}: {e['note']}" for e in b["concept"]["evidence"] if e["kind"] == "post")
    return (f"You write short-video campaign material for Little Joys ({b['product_name']}) in the natural voice of creator "
            f"{b['handle']} ({b['concept']['archetype']}).\nSection to write: {section}. {spec}\n"
            f"Creator style: {b['tone']['summary']} Language: {b['tone']['language']}.\nReal posts to echo:\n{ev}\n"
            f"VERIFIED PRODUCT FACTS (the only product statements allowed; quote verbatim):\n{facts}\n"
            "RULES: no health, immunity, growth or medical claims; no numbers except inside the facts above; no superlatives, "
            "competitor names, taste outcomes or endorsements; unknown details must be written as [[CONFIRM: what is needed]]. "
            "Hinglish in Roman script where the creator uses Hindi. Output JSON only.")


def anthropic_callable(model: str = "claude-sonnet-5-5"):
    """Return a prompt->text callable if the anthropic package and ANTHROPIC_API_KEY exist, else None."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except Exception:
        return None
    client = anthropic.Anthropic()

    def call(prompt: str) -> str:
        msg = client.messages.create(model=model, max_tokens=1200, messages=[{"role": "user", "content": prompt}])
        return "".join(getattr(p, "text", "") for p in msg.content)
    return call


# ---------------------------------------------------------------- export
def to_markdown(b: dict, findings: list | None = None) -> str:
    o = [f"# Campaign brief: {b['concept']['title']}",
         f"**Creator:** {b['handle']} ({b['creator_id']})  \n**Product:** {b['product_name']}  \n**Format:** {b['concept']['archetype']}  \n"
         f"**Timeline:** {b['timing']['total_s']} s (estimated speech {b['timing']['est_speech_s']} s)",
         "> Draft generated from templates and Little Joys' own ad claims. Every product statement is brand-stated and must be confirmed by Little Joys. "
         "Items in [[CONFIRM: ...]] are missing from the supplied files. Hinglish lines need native-speaker review.", "",
         "## 1. Campaign concept", b["concept"]["big_idea"], f"\n*{b['concept']['objective']}*", "", "**Why this creator**"]
    o += [f"- {x}" for x in b["concept"]["why_fit"]]
    o += ["", "**Evidence (real posts and ads)**"]
    o += [f"- {e['kind']} `{e['id']}`: {e['note']}" + (f" ({e['url']})" if e.get("url") else "") for e in b["concept"]["evidence"]]
    o += ["", "## 2. Alternative hooks"]
    for i, h in enumerate(b["hooks"]):
        sel = " (selected)" if i == b["selected_hook"] else ""
        o += [f"{i + 1}. **{h['angle']}**{sel}: \"{h['text']}\"  \n   On-screen: {h['on_screen']}  \n   Why: {h['rationale']}"]
    o += ["", f"## 3. Script ({b['timing']['total_s']} s)", "| Time | Spoken | Captions |", "|---|---|---|"]
    o += [f"| {s['start']}-{s['end']} s | {s['voice']} | {s['caption']} |" for s in b["scenes"]]
    o += ["", "## 4. Scene-by-scene visual directions"]
    o += [f"{s['n']}. **{s['start']}-{s['end']} s**: {s['visual']}" for s in b["scenes"]]
    o += ["", "## 5. On-screen text and captions"]
    o += [f"- Scene {s['n']}: {s['text']}" for s in b["scenes"]]
    o += [f"- Post caption: {b['post_caption']}", "", "## 6. Suggested CTA",
          f"- Spoken: {b['cta']['spoken']}", f"- On-screen: {b['cta']['on_screen']}", f"- Why: {b['cta']['note']}", "",
          "## 7. Tone and delivery", b["tone"]["summary"]]
    o += [f"- {x}" for x in b["tone"]["delivery"]]
    o += ["", "## 8. Claims and statements to avoid"]
    o += [f"- {a['item']} *({a['reason']})*" for a in b["avoid"]]
    o += ["", "## Verified product facts used (brand-stated, from ads.csv)"]
    o += [f"- `{f['id']}` \"{f['text']}\": ad IDs {', '.join(f['ad_ids'])}" for f in b["fact_table"]]
    o += ["", "## Placeholders to resolve"] + [f"- {p}" for p in b["placeholders"]]
    if findings is not None:
        errs = [f for f in findings if f.severity == "error"]
        o += ["", "## Validation", f"{len(errs)} claim errors; {len([f for f in findings if f.severity == 'warning'])} warnings."]
        o += [f"- {f.severity}: {f.where}: {f.message} ({f.match})" for f in findings if f.severity != "info"]
    return "\n".join(o) + "\n"


def to_json(b: dict, findings: list | None = None) -> str:
    d = dict(b)
    if findings is not None:
        d["validation"] = [f.as_dict() for f in findings]
    return json.dumps(d, indent=2, ensure_ascii=False, default=str)
