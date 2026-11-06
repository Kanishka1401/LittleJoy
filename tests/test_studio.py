import copy
import hashlib
import itertools
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cip import studio as S                      # noqa: E402
from cip import studio_content as C              # noqa: E402


@pytest.fixture(scope="module")
def st():
    return S.Studio.load(ROOT)


@pytest.fixture(scope="module")
def briefs(st):
    return {c: st.new_brief(c) for c in S.SHORTLIST}


def errors(st, b):
    return [f for f in S.validate_brief(b, st.facts) if f.severity == "error"]


def test_shortlist_matches_creator_engine():
    import pandas as pd
    r = pd.read_csv(ROOT / "reports/creator/tables/creator_ranking.csv").sort_values("rank")
    assert r.creator_id.head(5).tolist() == S.SHORTLIST


def test_facts_are_verbatim_from_ads_with_ad_ids(st):
    claims = " || ".join(st.ads.claims_made.dropna())
    for prod, facts in st.facts.items():
        assert len(facts) == len(C.PRODUCTS[prod]["facts"]), "a configured fact was not found in ads.csv"
        for f in facts.values():
            assert f.text in claims
            assert f.ad_ids and set(f.ad_ids) <= st.ad_ids


def test_every_brief_has_all_eight_parts(briefs):
    for b in briefs.values():
        assert b["concept"]["title"] and b["concept"]["big_idea"]
        assert len(b["hooks"]) == 3 and len({h["text"] for h in b["hooks"]}) == 3
        assert len(b["scenes"]) == 5 and all(s["voice"] and s["visual"] and s["text"] and s["caption"] for s in b["scenes"])
        assert b["cta"]["spoken"] and b["cta"]["on_screen"] and b["post_caption"]
        assert b["tone"]["summary"] and b["tone"]["delivery"]
        assert len(b["avoid"]) >= len(C.GLOBAL_AVOID) + 2


def test_script_duration_is_30_to_45_seconds(briefs):
    for b in briefs.values():
        assert 30 <= b["timing"]["total_s"] <= 45
        assert b["timing"]["est_speech_s"] <= b["timing"]["total_s"] * 1.1
        assert b["scenes"][0]["start"] == 0 and b["scenes"][-1]["end"] == b["timing"]["total_s"]


def test_no_claim_errors_in_any_generated_variant(st):
    for cid in S.SHORTLIST:
        b = st.new_brief(cid)
        for i in range(4):
            for sec in C.SECTIONS:
                b = st.regenerate(b, sec)
                assert not errors(st, b), (cid, sec, i, errors(st, b))
            assert not errors(st, st.new_brief(cid, seed=i))


def test_numbers_trace_to_facts(st, briefs):
    for b in briefs.values():
        allowed = " ".join(f.text for f in st.facts[b["product"]].values())
        text = " ".join(t for _, t in S.brief_text_fields(b))
        for m in S.NUMERIC_RE.findall(text):
            assert m.strip() in allowed, m


def test_validator_catches_banned_claims(st):
    allowed = [f.text for f in st.facts["Nutrimix"].values()]
    bad = ["Boosts immunity!", "India's only protein mix", "Helps your child grow taller", "Contains 99g protein",
           "Better than Gritzo", "Doctor recommended", "Kids love it", "Lab tested by Eurofins", "2.5X more protein"]
    for t in bad:
        assert any(f.severity == "error" for f in S.validate_text(t, allowed)), t
    for fid, f in st.facts["Nutrimix"].items():       # verified wording is allowed
        assert not [x for x in S.validate_text(f.text, allowed) if x.severity == "error"]
    assert not [x for x in S.validate_text("Contains 23 vitamins and minerals", allowed) if x.severity == "error"]
    assert any(f.kind == "placeholder" for f in S.validate_text("[[CONFIRM: price]]", allowed))


def test_placeholders_marked_for_missing_info(briefs):
    for b in briefs.values():
        assert b["placeholders"], "age/serving/link details are not in the files and must be placeholders"
        joined = " ".join(t for _, t in S.brief_text_fields(b))
        assert "[[CONFIRM:" in joined
        for p in b["placeholders"]:
            assert p.startswith("[[CONFIRM: ")


def test_missing_fact_becomes_placeholder(st):
    s2 = copy.copy(st)
    s2.facts = {p: {k: v for k, v in f.items() if k != "N_SWEET"} for p, f in st.facts.items()}
    used = set()
    out = s2.resolve("Label: \"{N_SWEET}\"", "Nutrimix", used)
    assert "[[CONFIRM: product fact N_SWEET" in out


def test_creators_are_meaningfully_different(briefs):
    def words(b):
        return set(" ".join(strip for strip in (S.strip_speakers(s["voice"]).lower() for s in b["scenes"])).split())
    for a, c in itertools.combinations(briefs, 2):
        A, B = words(briefs[a]), words(briefs[c])
        assert len(A & B) / len(A | B) < 0.45, (a, c)
        assert briefs[a]["concept"]["archetype"] != briefs[c]["concept"]["archetype"]
        assert briefs[a]["concept"]["title"] != briefs[c]["concept"]["title"]
        va = " ".join(s["visual"] for s in briefs[a]["scenes"])
        vc = " ".join(s["visual"] for s in briefs[c]["scenes"])
        assert va != vc
    assert len({tuple(h["text"] for h in b["hooks"]) for b in briefs.values()}) == 5


def test_style_cues_match_each_creator(briefs):
    t = lambda c: " ".join(s["voice"] + s["visual"] for s in briefs[c]["scenes"]).lower()    # noqa: E731
    assert "label" in t("CR-03") and "stethoscope" in t("CR-03")
    assert "vlog" in t("CR-11") or "handheld" in t("CR-11")
    assert "beta" in t("CR-02") and "mummy" in t("CR-02")
    assert "voiceover (adult)" in t("CR-05")           # claims are read by an adult, not the child
    assert "split-screen" in t("CR-01") and "doctor" in t("CR-01")


def test_evidence_ids_exist_in_data(st, briefs):
    posts = {st.post_id(u) for u in st.posts.post_url}
    for cid, b in briefs.items():
        creator_posts = {st.post_id(u) for u in st.posts[st.posts.creator_id == cid].post_url}
        assert b["concept"]["evidence"]
        for e in b["concept"]["evidence"]:
            if e["kind"] == "post":
                assert e["id"] in creator_posts
            else:
                assert e["id"] in st.ad_ids
        for h in b["hooks"]:
            assert h["evidence_post"] in creator_posts
        assert set(C.CREATORS[cid]["post_evidence"]) <= creator_posts


def test_regenerate_changes_only_requested_section(st, briefs):
    b = briefs["CR-02"]
    for sec, fields in {"hooks": ["hooks"], "script": ["voice"], "visuals": ["visual"], "onscreen": ["text"], "cta": ["cta"],
                        "concept": ["concept"]}.items():
        nb = st.regenerate(b, sec)
        assert nb is not b and b["variants"][sec] + 1 == nb["variants"][sec]
        for k in ("tone", "avoid", "creator_id", "product"):
            assert nb[k] == b[k]
        if sec == "script":
            assert [s["visual"] for s in nb["scenes"]] == [s["visual"] for s in b["scenes"]]
            assert [s["text"] for s in nb["scenes"]] == [s["text"] for s in b["scenes"]]
            assert [s["voice"] for s in nb["scenes"][1:4]] != [s["voice"] for s in b["scenes"][1:4]]
            assert nb["scenes"][0]["voice"] == b["scenes"][0]["voice"] and nb["scenes"][4]["voice"] == b["scenes"][4]["voice"]
        if sec == "visuals":
            assert [s["voice"] for s in nb["scenes"]] == [s["voice"] for s in b["scenes"]]
            assert [s["visual"] for s in nb["scenes"]] != [s["visual"] for s in b["scenes"]]
        if sec == "onscreen":
            assert [s["voice"] for s in nb["scenes"]] == [s["voice"] for s in b["scenes"]]
            assert nb["hooks"] == b["hooks"]
        if sec == "hooks":
            assert [h["text"] for h in nb["hooks"]] != [h["text"] for h in b["hooks"]]
            assert nb["concept"] == b["concept"]
        if sec == "cta":
            assert nb["cta"] != b["cta"] and nb["hooks"] == b["hooks"]
            assert nb["scenes"][4]["voice"] == nb["cta"]["spoken"]
        if sec == "concept":
            assert nb["concept"]["title"] != b["concept"]["title"] and nb["scenes"] == b["scenes"]


def test_regeneration_keeps_user_edits_in_other_sections(st, briefs):
    b = st.apply_edits(briefs["CR-11"], scenes=[{}, {"voice": "Mera apna edit."}, {}, {}, {}])
    nb = st.regenerate(b, "hooks")
    assert nb["scenes"][1]["voice"] == "Mera apna edit."
    assert "script" in b["source"] and b["source"]["script"] == "edited"


def test_select_hook_updates_scene_one(st, briefs):
    nb = st.select_hook(briefs["CR-03"], 2)
    assert nb["scenes"][0]["voice"] == nb["hooks"][2]["text"] and nb["selected_hook"] == 2


def test_edits_are_validated(st, briefs):
    nb = st.apply_edits(briefs["CR-01"], scenes=[{"voice": "Yeh protein bachon ki immunity badhata hai"}] + [{}] * 4)
    assert any(f.kind == "banned_claim" for f in S.validate_brief(nb, st.facts))


def test_llm_path_valid_output_is_used_and_validated(st, briefs):
    good = lambda prompt: json.dumps(["Line ek.", "Line do.", "Line teen."])        # noqa: E731
    nb = st.regenerate(briefs["CR-03"], "script", llm=good)
    assert nb["source"]["script"] == "llm" and nb["scenes"][2]["voice"] == "Line do."


def test_llm_path_unsafe_or_broken_output_falls_back_to_template(st, briefs):
    bad = lambda prompt: json.dumps(["Boosts immunity", "12 vitamins", "Best protein"])     # noqa: E731
    nb = st.regenerate(briefs["CR-03"], "script", llm=bad)
    assert nb["source"]["script"] == "template" and not errors(st, nb)
    broken = lambda prompt: "sorry, I cannot"                                              # noqa: E731
    assert st.regenerate(briefs["CR-03"], "hooks", llm=broken)["source"]["hooks"] == "template"

    def boom(prompt):
        raise RuntimeError("no network")
    assert st.regenerate(briefs["CR-03"], "cta", llm=boom)["source"]["cta"] == "template"


def test_prompt_contains_only_verified_facts_and_rules(st, briefs):
    p = S.build_prompt(st, briefs["CR-01"], "hooks")
    for f in st.facts["Proteinmix"].values():
        assert f.text in p
    assert "N_VITMIN" not in p and "Nutrimix" not in p.split("VERIFIED")[1]
    assert "no health, immunity" in p


def test_template_fallback_needs_no_api_key(monkeypatch, st):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert S.anthropic_callable() is None
    assert st.new_brief("CR-05")["source"]["script"] == "template"


def test_restricted_claims_are_reported_not_used(st, briefs):
    r = S.restricted_claims(st.ads)
    assert "Immunity claim" in set(r.category)
    text = " ".join(t for b in briefs.values() for _, t in S.brief_text_fields(b)).lower()
    for w in ["immunity", "boost", "gentle", "growth"]:
        assert w not in text


def test_exports(st, briefs):
    b = briefs["CR-03"]
    md = S.to_markdown(b, S.validate_brief(b, st.facts))
    for h in ["## 1. Campaign concept", "## 2. Alternative hooks", "## 3. Script", "## 4. Scene-by-scene", "## 5. On-screen",
              "## 6. Suggested CTA", "## 7. Tone", "## 8. Claims", "Verified product facts used"]:
        assert h in md
    j = json.loads(S.to_json(b, S.validate_brief(b, st.facts)))
    assert j["creator_id"] == "CR-03" and "validation" in j


def test_existing_module_outputs_untouched():
    """Studio only reads existing outputs; the earlier manifests' recorded hashes must still match."""
    for rel in ["reports/creator/json/run_manifest.json", "reports/dna/json/run_manifest.json"]:
        m = json.loads((ROOT / rel).read_text())
        base = (ROOT / rel).parent.parent
        for name, h in m["outputs_sha256"].items():
            sub = "json" if name.endswith(".json") else "tables"
            assert hashlib.sha256((base / sub / name).read_bytes()).hexdigest() == h, name
