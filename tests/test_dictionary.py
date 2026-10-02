"""FEED, the first-party enough english dictionary: the sync filter, the build, reads, user entries, the routes.

Everything here runs against a small fixture lexicon written by the test (a few dozen rows), synced through the
real `scripts/sync_dictionary.py` into a temp `reflib/dict`, and pointed at by `ENOUGH_DICT_SOURCE`. conftest
already moved `ENOUGH_DICT_ROOT` into tmp_path. The shipped 380 MB copy is exercised only by the opt-in
`test_real_dictionary_build_and_timings` (ENOUGH_FEED_REAL=1).
"""

from __future__ import annotations

import functools
import importlib.util
import json
import os
import random
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from enough import dictionary as D
from enough import dictionary_api

REPO = Path(__file__).resolve().parent.parent
REAL_DICT = REPO / "reflib" / "dict"

_spec = importlib.util.spec_from_file_location("sync_dictionary", REPO / "scripts" / "sync_dictionary.py")
sync_dictionary = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_dictionary)

# The shipped schema, as the lexicon's exporter writes it. A minimal stand-in when the checkout has no copy yet.
SCHEMA = (REAL_DICT / "schema.sql").read_text(encoding="utf-8") if (REAL_DICT / "schema.sql").is_file() else None


def _word_columns() -> list[str]:
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    return [r[1] for r in con.execute("PRAGMA table_info(words)")]


def W(word: str, *, head: bool = True, **kw) -> dict:
    """A full words row in column order, with provenance columns set so the filter has something to null."""
    row = {c: None for c in _word_columns()}
    row.update(word=word, letter=word[0], length=len(word), is_headword=1 if head else 0,
               source="pack-001", notes="sourcing note", corrected_on="2026-09-27", status="live")
    if head:
        row.update(pronunciation=f"/{word}/", ipa=f"/{word}/", definition=f"The meaning of {word}.",
                   pos="noun", pos_primary="noun")
    row.update(kw)
    for k in ("synonyms", "related", "examples", "forms", "form_labels"):
        if isinstance(row.get(k), list):
            row[k] = json.dumps(row[k], ensure_ascii=False)
    return row


def F(head: str, form: str, pos: int, labels: list[str]) -> dict:
    return {"headword": head, "form": form, "position": pos, "pronunciation": f"/{form}/",
            "labels": json.dumps(labels), "synonyms": None}


def S(word: str, syn: str, pos: int = 1) -> dict:
    return {"word": word, "synonym": syn, "via": word, "position": pos}


WORDS = [
    W("a", pos="article; noun", pos_primary="article", first_use="Old English", frequency_rank=8,
      hyphenation="a", domain="language"),
    W("aah", pos="interjection; verb", pos_primary="interjection", first_use="17th century", frequency_rank=2,
      hyphenation="aah", forms=[{"word": "aahed", "pronunciation": "/ɑd/", "labels": ["past"], "synonyms": []}]),
    W("aahed", head=False, form_of="aah", form_labels=["past"], pronunciation="/ɑd/", status=None),
    W("aahing", head=False, form_of="aah", form_labels=["pres. part."], status=None),
    W("aardvark", first_use="late 18th century", domain="zoology", frequency_rank=2, hyphenation="aard·vark",
      related=["anteater"], synonyms=["anteater"]),
    W("anteater", first_use="mid 18th century", domain="zoology", frequency_rank=2, hyphenation="ant·eat·er"),
    W("apple", first_use="Old English", domain="food", frequency_rank=5, hyphenation="ap·ple",
      definition="A round fruit of a tree of the rose family."),
    W("apples", head=False, form_of="apple", form_labels=["pl."], status=None),
    W("bake", pos="verb; noun", pos_primary="verb", first_use="Old English", domain="food", frequency_rank=4,
      hyphenation="bake"),
    W("baked", head=False, form_of="bake", form_labels=["past"], status=None),
    W("banana", first_use="late 16th century", domain="food", frequency_rank=4, hyphenation="ba·nan·a",
      definition="A long curved fruit that grows in clusters."),
    W("blog", pos="noun; verb", first_use="1990s", domain="computing", frequency_rank=4, hyphenation="blog",
      added_on="2026-09-26"),
    W("byte", first_use="1950s", domain="computing", frequency_rank=4, hyphenation="byte"),
    W("emoji", first_use="1990s", domain="computing", frequency_rank=3, hyphenation="e·mo·ji",
      added_on="2026-09-29"),
    W("gloaming", first_use="Old English", frequency_rank=2, hyphenation="gloam·ing", usage_note="Literary"),
    W("hidden", pos="adjective", pos_primary="adjective", first_use="Middle English", frequency_rank=5,
      hyphenation="hid·den"),
    W("lantern", first_use="Middle English", frequency_rank=4, hyphenation="lan·tern",
      definition="A lamp with a transparent case protecting the flame, often carried by termites in fables."),
    W("quick", pos="adjective", pos_primary="adjective", first_use="Old English", frequency_rank=6,
      hyphenation="quick"),
    W("run", pos="verb; noun", pos_primary="verb", first_use="Old English", frequency_rank=7, hyphenation="run"),
    W("ran", head=False, form_of="run", form_labels=["past"], status=None),
    W("subitize", pos="verb", pos_primary="verb", first_use="1940s", frequency_rank=0,
      hyphenation="su·bi·tize"),
    W("termite", first_use="late 18th century", domain="zoology", frequency_rank=3, hyphenation="ter·mite"),
    W("zebra", first_use="early 17th century", domain="zoology", frequency_rank=4, hyphenation="ze·bra"),
    W("zorse", first_use="Rare; date uncertain.", domain="zoology", frequency_rank=0, hyphenation="zorse"),
    # Not public: dropped with every forms/synonyms row naming them.
    W("secret", status="withheld", first_use="Middle English", hyphenation="se·cret"),
    W("oldword", status="deprecated"),
]
FORMS = [F("aah", "aahed", 1, ["past"]), F("aah", "aahing", 2, ["pres. part."]), F("apple", "apples", 1, ["pl."]),
         F("bake", "baked", 1, ["past"]), F("run", "ran", 1, ["past"]), F("secret", "secrets", 1, ["pl."])]
SYNONYMS = [S("aardvark", "anteater"), S("hidden", "secret"), S("secret", "hidden"), S("hidden", "oldword", 2)]
META = [{"key": "dictionary_version", "value": "1.1"}, {"key": "imported_at", "value": "2026-09-25T15:09"},
        {"key": "importer", "value": "scripts/import_dictionary.py"}, {"key": "languages", "value": "en,fr"},
        {"key": "schema_version", "value": "2"}, {"key": "title", "value": "Enough Dictionary 1.1"}]
LABELS = [{"label": "pl.", "meaning": "plural", "position": 1},
          {"label": "pres. part.", "meaning": "present participle", "position": 3},
          {"label": "past", "meaning": "past tense and past participle", "position": 4}]
BANDS = [{"band": b, "name": n, "examples": None} for b, n in enumerate(
    ["Unrecorded", "Very rare", "Rare", "Uncommon", "Occasional", "Familiar", "Common", "Very common",
     "Extremely common"])]
PUBLIC_HEADWORDS = sorted(w["word"] for w in WORDS if w["is_headword"] == 1 and w["status"] in (None, "live"))

pytestmark = pytest.mark.skipif(SCHEMA is None, reason="reflib/dict/schema.sql not synced yet")


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def write_lexicon(root: Path, words=WORDS) -> Path:
    d = root / "dictionary"
    d.mkdir(parents=True, exist_ok=True)
    (d / "schema.sql").write_text(SCHEMA, encoding="utf-8")
    _jsonl(d / "meta.jsonl", META)
    _jsonl(d / "labels.jsonl", LABELS)
    _jsonl(d / "frequency_bands.jsonl", BANDS)
    for sub, rows, key in (("words", words, "word"), ("forms", FORMS, "headword"), ("synonyms", SYNONYMS, "word")):
        for f in (d / sub).glob("*.jsonl") if (d / sub).is_dir() else []:
            f.unlink()
        by: dict[str, list] = {}
        for r in sorted(rows, key=lambda r: r[key]):
            by.setdefault(r[key][0], []).append(r)
        for letter, rs in by.items():
            _jsonl(d / sub / f"{letter}.jsonl", rs)
    return root


def _read(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


@pytest.fixture()
def lexicon(tmp_path: Path) -> Path:
    return write_lexicon(tmp_path / "lexicon")


@pytest.fixture()
def source(tmp_path: Path, lexicon: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    out = tmp_path / "reflib-dict"
    sync_dictionary.sync(lexicon, out)
    monkeypatch.setenv("ENOUGH_DICT_SOURCE", str(out))
    return out


@pytest.fixture()
def built(source: Path) -> Path:
    st = D.ensure_built()
    assert st["ready"] and not st["building"], st
    return source


def _root_is_scratch(tmp_path: Path) -> None:
    assert str(D.state_root()).startswith(str(tmp_path)), D.state_root()
    assert str(Path.home()).startswith(str(tmp_path))


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------

def test_sync_applies_the_public_edition_filter(tmp_path: Path, lexicon: Path):
    out = tmp_path / "out"
    r = sync_dictionary.sync(lexicon, out)
    assert r["withheld"] == 2
    words = [row for f in sorted((out / "words").glob("*.jsonl")) for row in _read(f)]
    assert {w["word"] for w in words} == {w["word"] for w in WORDS} - {"secret", "oldword"}
    assert all(w["notes"] is None and w["source"] is None and w["corrected_on"] is None for w in words)
    assert all(list(w) == _word_columns() for w in words), "key order is preserved"
    forms = [row for f in (out / "forms").glob("*.jsonl") for row in _read(f)]
    assert ("secret", "secrets") not in {(f["headword"], f["form"]) for f in forms}
    assert len(forms) == len(FORMS) - 1
    syns = [row for f in (out / "synonyms").glob("*.jsonl") for row in _read(f)]
    assert syns == [S("aardvark", "anteater")]
    assert [m["key"] for m in _read(out / "meta.jsonl")] == ["dictionary_version", "languages", "schema_version",
                                                            "title"]
    assert (out / "schema.sql").read_text(encoding="utf-8") == SCHEMA
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert man["headwords"] == len(PUBLIC_HEADWORDS) and man["words"] == len(words)
    assert man["dictionary_version"] == "1.1" and man["schema_version"] == "2"
    assert set(man["files"]) == {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()} - {"manifest.json"}
    assert man["digest"] == r["digest"]


def test_sync_rerun_is_byte_stable_and_check_reports(tmp_path: Path, lexicon: Path, capsys):
    out = tmp_path / "out"
    sync_dictionary.sync(lexicon, out)
    (out / "NOTICE.md").write_text("hand-written\n")
    snap = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in out.rglob("*") if p.is_file()}
    r = sync_dictionary.sync(lexicon, out)
    assert not (r["added"] or r["changed"] or r["removed"])
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in out.rglob("*") if p.is_file()} == snap
    argv = ["--lexicon", str(lexicon), "--out", str(out), "--check"]
    assert sync_dictionary.main(argv) == 0

    # a changed row, a removed source file, a stray file in the copy
    words = [dict(w) for w in WORDS if w["word"] != "zorse"]
    next(w for w in words if w["word"] == "apple")["definition"] = "A crisp fruit."
    write_lexicon(lexicon, words)
    (out / "words" / "x.jsonl").write_text("{}\n")
    capsys.readouterr()
    assert sync_dictionary.main(argv) == 1
    said = capsys.readouterr().out
    assert "changed  words/a.jsonl" in said and "removed  words/z.jsonl" not in said
    assert "removed  words/x.jsonl" in said and "changed  manifest.json" in said
    assert (out / "words" / "x.jsonl").is_file(), "--check writes nothing"
    r = sync_dictionary.sync(lexicon, out)
    assert r["words_changed"] == 1 and r["words_removed"] == 2  # zorse, and the stray row
    assert not (out / "words" / "x.jsonl").exists()
    assert (out / "NOTICE.md").read_text() == "hand-written\n"
    assert sync_dictionary.main(argv) == 0


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def test_missing_source_is_unavailable_not_an_error(tmp_path: Path):
    _root_is_scratch(tmp_path)
    st = D.ensure_built(background=True)
    assert st["available"] is False and st["ready"] is False and st["building"] is False
    assert D.status()["available"] is False
    with pytest.raises(D.DictionaryUnavailable):
        D.entries()
    assert not D.feed_path().exists() and not D.user_path().exists()


def test_build_and_rebuild_on_digest_change(tmp_path: Path, lexicon: Path, source: Path):
    _root_is_scratch(tmp_path)
    st = D.status()
    assert st["available"] and not st["ready"]
    st = D.ensure_built()
    assert st["ready"] and st["headwords"] == len(PUBLIC_HEADWORDS) and st["version"] == "1.1"
    feed = D.feed_path()
    con = sqlite3.connect(feed)
    assert con.execute("SELECT count(*) FROM words").fetchone()[0] == st["words"]
    assert con.execute("SELECT count(*) FROM words_fts").fetchone()[0] == st["words"]
    assert con.execute("PRAGMA user_version").fetchone()[0] == 2
    con.close()
    before = feed.stat().st_mtime_ns
    D.ensure_built()
    assert feed.stat().st_mtime_ns == before, "an up-to-date build is left alone"
    assert not list(feed.parent.glob(".feed-*")), "no temp file left behind"

    write_lexicon(lexicon, WORDS + [W("zyzzyva", first_use="20th century", hyphenation="zyz·zy·va")])
    sync_dictionary.sync(lexicon, source)
    assert D.status()["stale"] is True
    st = D.ensure_built(background=True)
    deadline = time.monotonic() + 30
    while D.status()["building"] and time.monotonic() < deadline:
        time.sleep(0.02)
    st = D.status()
    assert st["ready"] and not st["stale"] and st["headwords"] == len(PUBLIC_HEADWORDS) + 1
    assert D.lookup("zyzzyva")["found"]


def test_user_db_survives_a_rebuild(built: Path, lexicon: Path):
    assert D.user_update("apple", {"definition": "Mine."})["ok"]
    D.feed_path().unlink()
    D.ensure_built()
    assert D.entry("apple")["definition"] == "Mine."


# ---------------------------------------------------------------------------
# era and syllables
# ---------------------------------------------------------------------------

# A representative slice of the 76 distinct first_use strings in the lexicon, in the order they must sort.
ERA_ORDER = [
    "Old English", "Late Old English", "Middle English", "late Middle English", "13th century",
    "14th century", "late 14th century", "early 15th century", "16th century", "by the 16th century",
    "mid-16th century", "late 16th century", "17th century", "By the 17th century", "early 17th century",
    "by the early 17th century", "mid 17th century", "late 17th century", "mid 18th century", "1750s",
    "late 18th century", "1790s", "19th century", "1830s", "mid-19th century", "1880s", "1890s",
    "20th century", "1900s", "1920s", "mid 20th century", "by the mid 20th century", "1960s", "1990s",
    "21st century", "2000s", "2020s",
]


def test_era_orders_first_use_strings():
    shuffled = ERA_ORDER[:]
    random.Random(7).shuffle(shuffled)
    assert sorted(shuffled, key=D.era_ord) == ERA_ORDER
    assert D.era_ord("late Middle English") == D.era_ord("Late Middle English")
    assert D.era_ord("by the 17th century") == D.era_ord("By the 17th century")
    assert D.era_ord("mid-17th century") == D.era_ord("mid 17th century")
    assert D.era_ord("Not well attested") is None and D.era_ord("Rare; date uncertain.") is None
    assert D.era_ord(None) is None
    assert D.syllable_count("ba·nan·a") == 3 and D.syllable_count("run") == 1 and D.syllable_count(None) is None


LEXICON_DB = Path("/Users/m3u/METMcloud/enough-lexicon/db/dictionary-1.1.sqlite")


@pytest.mark.skipif(not LEXICON_DB.is_file(), reason="the lexicon DB is only on the owner's machine")
def test_era_handles_every_first_use_in_the_lexicon():
    con = sqlite3.connect(f"file:{LEXICON_DB}?mode=ro", uri=True)
    try:
        values = [r[0] for r in con.execute("SELECT DISTINCT first_use FROM words WHERE first_use IS NOT NULL")]
    finally:
        con.close()
    undated = {v for v in values if D.era_ord(v) is None}
    assert undated <= {"Not well attested", "Rare; date uncertain."}, undated


# ---------------------------------------------------------------------------
# lookup
# ---------------------------------------------------------------------------

def test_lookup_headword_form_normalisation_and_miss(built: Path):
    r = D.lookup("aardvark")
    assert r["found"] and r["entry"]["word"] == "aardvark" and r["matched_form"] is None
    e = r["entry"]
    assert e["origin"] == "feed" and e["related"] == ["anteater"] and e["synonyms"] == ["anteater"]
    assert e["frequency_band"]["name"] == "Rare" and e["syllables"] == 2 and e["era"] == "18th century"
    assert e["notes"] is None and e["source"] is None

    r = D.lookup("aahed")
    assert r["found"] and r["entry"]["word"] == "aah" and r["matched_form"] == "aahed"
    assert r["entry"]["forms"][0]["label_meanings"] == ["past tense and past participle"]

    for typed in ("Apple", "“apple,”", "apple's", "Apple’s", "(apple)", "apple."):
        r = D.lookup(typed)
        assert r["found"] and r["entry"]["word"] == "apple", typed
    assert D.lookup("Ran!")["matched_form"] == "ran"

    r = D.lookup("aardvarks")
    assert not r["found"] and r["entry"] is None
    assert "aardvark" in r["suggestions"]
    assert "termite" in D.lookup("termites")["suggestions"] or "lantern" in D.lookup("termites")["suggestions"]
    assert D.lookup("secret")["found"] is False, "withheld words never ship"
    assert D.lookup("   ")["found"] is False

    full = D.entry("aahed")
    assert full["form_of"] == "aah" and full["form_label_meanings"] == ["past tense and past participle"]
    assert D.entry("nope") is None


# ---------------------------------------------------------------------------
# entries and index
# ---------------------------------------------------------------------------

def _all(sort, then=None, dir="asc", then_dir="asc", **kw) -> list[dict]:
    rows, offset = [], 0
    while True:
        page = D.entries(sort=sort, then=then, dir=dir, then_dir=then_dir, offset=offset, limit=4, **kw)
        rows += page["rows"]
        offset += 4
        if offset >= page["total"]:
            return rows


def test_entries_paging_alpha(built: Path):
    page = D.entries(limit=5)
    assert page["total"] == len(PUBLIC_HEADWORDS)
    assert [r["word"] for r in page["rows"]] == PUBLIC_HEADWORDS[:5]
    assert set(page["rows"][0]) == set(D.SHORT_COLUMNS) | {"origin"}
    assert page["groups"] == [{"key": "a", "label": "a", "count": 5, "offset": 0}]
    assert D.entries(offset=3, limit=4)["groups"] == [{"key": "a", "label": "a", "count": 5, "offset": 0},
                                                      {"key": "b", "label": "b", "count": 4, "offset": 5}]
    assert [r["word"] for r in _all("alpha")] == PUBLIC_HEADWORDS
    assert [r["word"] for r in _all("alpha", dir="desc")] == PUBLIC_HEADWORDS[::-1]
    deep = D.entries(offset=len(PUBLIC_HEADWORDS) - 2, limit=10)
    assert [r["word"] for r in deep["rows"]] == PUBLIC_HEADWORDS[-2:]
    assert D.entries(offset=999)["rows"] == []
    assert [r["word"] for r in D.entries(letter="b")["rows"]] == ["bake", "banana", "blog", "byte"]


def _key(sort: str, r: dict, full: dict):
    return {
        "alpha": r["word"], "length": r["length"], "domain": r["domain"], "era": D.era_ord(r["first_use"]),
        "pos": full["pos_primary"], "frequency": r["frequency_rank"],
        "syllables": D.syllable_count(full["hyphenation"]), "added": full["added_on"], "origin": r["origin"],
    }[sort]


@pytest.mark.parametrize("sort", D.SORT_KEYS)
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_every_sort_key_with_a_sub_sort(built: Path, sort: str, direction: str):
    then = "length" if sort != "length" else "alpha"
    rows = _all(sort, then=then, dir=direction, then_dir="desc")
    assert sorted(r["word"] for r in rows) == PUBLIC_HEADWORDS
    full = {r["word"]: D.entry(r["word"]) for r in rows}
    prim = [_key(sort, r, full[r["word"]]) for r in rows]
    present = [k for k in prim if k is not None]
    # nulls always last, whatever the direction
    assert prim == present + [None] * (len(prim) - len(present))
    assert present == sorted(present, reverse=(direction == "desc"))
    def cmp(a: dict, b: dict) -> int:
        for k, d in ((sort, direction), (then, "desc")):
            va, vb = _key(k, a, full[a["word"]]), _key(k, b, full[b["word"]])
            if va == vb:
                continue
            if va is None or vb is None:
                return 1 if va is None else -1
            return (-1 if va < vb else 1) * (1 if d == "asc" else -1)
        return -1 if a["word"] < b["word"] else (a["word"] > b["word"])
    assert [r["word"] for r in rows] == [r["word"] for r in sorted(rows, key=functools.cmp_to_key(cmp))]
    rail = D.index(sort=sort, dir=direction)
    assert sum(g["count"] for g in rail) == len(rows)
    for g in rail:
        assert g["offset"] == sum(x["count"] for x in rail if x["offset"] < g["offset"])


def test_index_groups_and_filters(built: Path):
    era = D.index(sort="era")
    assert [g["label"] for g in era] == ["old english", "middle english", "16th century", "17th century",
                                         "18th century", "20th century", "undated"]
    assert era[-1]["count"] == 1  # zorse: "Rare; date uncertain."
    dom = D.index(sort="domain", filters={"domain": ["food", "zoology"]})
    assert [(g["key"], g["count"]) for g in dom] == [("food", 3), ("zoology", 5)]
    freq = D.index(sort="frequency", dir="desc")
    assert freq[0]["label"] == "extremely common"
    assert D.entries(filters={"band": "0"})["total"] == 2
    assert D.entries(filters={"pos": "verb"})["total"] == 3
    with pytest.raises(ValueError):
        D.entries(sort="vibes")
    with pytest.raises(ValueError):
        D.entries(filters={"colour": "red"})
    q = D.entries(q="fruit")
    assert sorted(r["word"] for r in q["rows"]) == ["apple", "banana"]
    assert D.entries(q="termites")["total"] == 1  # lantern's definition
    assert D.entries(q="!!!")["total"] == 0
    f = D.facets()
    assert {"domain": "zoology", "count": 5} in f["domains"] and f["sort_keys"] == list(D.SORT_KEYS)
    assert f["bands"][0] == {"band": 0, "name": "Unrecorded", "examples": None, "count": 2}


# ---------------------------------------------------------------------------
# user entries
# ---------------------------------------------------------------------------

def test_user_add_update_delete(built: Path, tmp_path: Path):
    assert not D.user_path().exists(), "created lazily"
    r = D.user_add({"word": "Smoko", "definition": "A short break from work.", "pos": "noun",
                    "pronunciation": "/ˈsmoʊkoʊ/", "examples": ["We stopped for smoko."], "domain": "work",
                    "forms": [{"word": "smokos", "pronunciation": "/ˈsmoʊkoʊz/", "labels": ["pl."]}]})
    assert r["ok"] and r["word"] == "smoko" and not r["overrides_feed"]
    assert "etymology" in r["missing"] and "definition" not in r["missing"] and "examples" not in r["missing"]
    assert D.user_path().is_file()
    e = D.entry("smoko")
    assert e["origin"] == "user" and e["source"] == "user" and e["status"] == "live"
    assert e["letter"] == "s" and e["length"] == 5 and e["pos_primary"] == "noun" and e["ipa"] == "/ˈsmoʊkoʊ/"
    assert e["examples"] == ["We stopped for smoko."] and e["added_on"] == e["updated_on"]
    assert D.lookup("smokos")["entry"]["word"] == "smoko"
    assert D.status()["user_words"] == 1

    bad = D.user_add({"word": "Smoko2", "definition": "x", "pos": "noun", "pronunciation": "/x/"})
    assert not bad["ok"] and "a-z" in bad["error"]
    bad = D.user_add({"word": "zyx", "definition": "x"})
    assert not bad["ok"] and set(bad["missing"]) == {"pos", "pronunciation"}
    assert not D.user_add({"word": "apple", "definition": "x", "pos": "noun", "pronunciation": "/x/"})["ok"]
    assert not D.user_add({"word": "smoko", "definition": "x", "pos": "noun", "pronunciation": "/x/"})["ok"]
    assert not D.user_add({"word": "qat", "definition": "x", "pos": "noun", "pronunciation": "/x/",
                           "frequency_rank": 11})["ok"]
    assert not D.user_add({"word": "qat", "definition": "x", "pos": "noun", "pronunciation": "/x/",
                           "colour": "red"})["ok"]

    r = D.user_update("smoko", {"etymology": "Australian, from smoke.", "frequency_rank": "1",
                                "related": "break\nsmoke"})
    assert r["ok"] and "etymology" not in r["missing"]
    e = D.entry("smoko")
    assert e["related"] == ["break", "smoke"] and e["frequency_rank"] == 1 and e["etymology"]
    assert not D.user_update("smoko", {"definition": ""})["ok"], "required stays required"
    assert not D.user_update("nonesuch", {"definition": "x"})["ok"]

    assert D.user_delete("smoko")["ok"]
    assert D.entry("smoko") is None and not D.user_delete("smoko")["ok"]
    assert D.user_path().is_file(), "the user DB is never deleted"


def test_user_row_overrides_feed_and_interleaves(built: Path):
    r = D.user_update("apple", {"definition": "My own apple.", "domain": "botany"})
    assert r["ok"] and r["overrides_feed"]
    e = D.lookup("apples")["entry"]
    assert e["word"] == "apple" and e["origin"] == "user" and e["definition"] == "My own apple."
    assert e["overrides_feed"] and e["first_use"] == "Old English", "seeded from the feed row"
    assert D.user_add({"word": "bambi", "definition": "A young deer.", "pos": "noun",
                       "pronunciation": "/ˈbæmbi/"})["ok"]
    rows = _all("alpha")
    words = [r["word"] for r in rows]
    assert words == sorted(PUBLIC_HEADWORDS + ["bambi"]) and words.count("apple") == 1
    origins = {r["word"]: r["origin"] for r in rows}
    assert origins["apple"] == origins["bambi"] == "user" and origins["banana"] == "feed"
    assert D.entries(filters={"origin": "user"})["total"] == 2
    assert [g["key"] for g in D.index(sort="origin")] == ["feed", "user"]
    assert D.entries(q="deer")["rows"][0]["word"] == "bambi"
    assert D.entries(q="rose")["total"] == 0, "the feed definition is shadowed"
    assert D.facets()["origins"] == [{"origin": "feed", "count": len(PUBLIC_HEADWORDS) - 1},
                                     {"origin": "user", "count": 2}]
    r = D.user_delete("apple")
    assert r["ok"] and r["restored_feed"]
    assert D.entry("apple")["origin"] == "feed"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

@pytest.fixture()
def api() -> TestClient:
    app = FastAPI()
    app.include_router(dictionary_api.build_router())
    return TestClient(app)


def test_routes(built: Path, api: TestClient):
    st = api.get("/api/dict/status").json()
    assert st["available"] and st["ready"] and st["headwords"] == len(PUBLIC_HEADWORDS)
    r = api.get("/api/dict/lookup", params={"word": "Baked"}).json()
    assert r["found"] and r["entry"]["word"] == "bake" and r["matched_form"] == "baked"
    page = api.get("/api/dict/entries", params={"sort": "era", "then": "alpha", "dir": "desc", "limit": 3,
                                                "offset": 1, "domain": "zoology,food"}).json()
    assert page["total"] == 8 and len(page["rows"]) == 3 and page["offset"] == 1
    assert isinstance(page["rows"][0]["related"], (list, type(None)))
    idx = api.get("/api/dict/index", params={"sort": "domain"}).json()
    assert idx["groups"][0]["key"] == "computing"
    assert api.get("/api/dict/entry/aardvark").json()["synonyms"] == ["anteater"]
    assert api.get("/api/dict/entry/nonesuch").status_code == 404
    assert api.get("/api/dict/entries", params={"sort": "vibes"}).status_code == 400
    assert api.get("/api/dict/entries", params={"limit": 0}).status_code == 422
    assert {"domains", "pos", "bands", "sort_keys"} <= set(api.get("/api/dict/facets").json())
    assert D.user_add({"word": "qat", "definition": "A shrub.", "pos": "noun", "pronunciation": "/kɑt/"})["ok"]
    assert api.delete("/api/dict/user/qat").json()["ok"]
    assert api.delete("/api/dict/user/qat").status_code == 404


def test_position_of_a_word_in_a_view(built: Path, api: TestClient):
    # The dictionary page opens at a word: its offset under the sort the reader has on, forms resolved.
    p = D.position("banana")
    assert p["found"] and p["offset"] == PUBLIC_HEADWORDS.index("banana") and p["total"] == len(PUBLIC_HEADWORDS)
    for sort in D.SORT_KEYS:
        for direction in ("asc", "desc"):
            words = [r["word"] for r in _all(sort, then="length", dir=direction, then_dir="desc")]
            got = D.position("Zebra's", sort=sort, then="length", dir=direction, then_dir="desc")
            assert got["found"] and words[got["offset"]] == "zebra", (sort, direction)
    f = D.position("Baked", sort="era")
    assert f["headword"] == "bake" and f["matched_form"] == "baked" and f["found"]
    assert [r["word"] for r in _all("era")][f["offset"]] == "bake"
    # Left out of this view by a filter: not found, no offset outside alphabetical order.
    assert not D.position("apple", sort="domain", filters={"domain": "zoology"})["found"]
    # A miss under alphabetical order says where it would fall.
    miss = D.position("bamboozle")
    assert not miss["found"] and miss["headword"] is None
    assert (miss["before"], miss["after"]) == ("bake", "banana")
    assert miss["offset"] == PUBLIC_HEADWORDS.index("banana")
    back = D.position("bamboozle", dir="desc")
    assert (back["before"], back["after"]) == ("banana", "bake")
    assert D.position("zzzz")["after"] is None
    r = api.get("/api/dict/position", params={"word": "termite", "sort": "frequency", "dir": "desc"}).json()
    assert r["found"] and r["headword"] == "termite"
    assert api.get("/api/dict/position", params={"word": "x", "sort": "vibes"}).status_code == 400
    g = api.get("/api/dict/entries", params={"then": "length", "then_dir": "desc", "grouped": "true",
                                             "limit": 500}).json()
    assert [r["word"] for r in g["rows"]] == [r["word"] for r in _all("alpha", then="length", then_dir="desc",
                                                                       grouped=True)]
    # The short rows carry what the page draws.
    row = D.entries(limit=1)["rows"][0]
    assert {"hyphenation", "pos_primary", "added_on"} <= set(row)


@pytest.mark.parametrize("sort", ["alpha", "era"])
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_grouped_sub_sort_orders_inside_each_group(built: Path, sort: str, direction: str):
    # Under alpha a sub-sort only broke exact ties (there are none): `grouped` makes it order the words inside
    # each letter / era group, with the groups themselves where the primary sort puts them.
    rows = _all(sort, then="length", dir=direction, then_dir="desc", grouped=True)
    assert sorted(r["word"] for r in rows) == PUBLIC_HEADWORDS
    rail = D.index(sort=sort, dir=direction)
    seen = 0
    for g in rail:
        part = rows[g["offset"]:g["offset"] + g["count"]]
        seen += len(part)
        assert [(-r["length"], r["word"]) for r in part] == sorted((-r["length"], r["word"]) for r in part), g
        if sort == "alpha":
            assert {r["word"][0] for r in part} == {g["key"]}
        else:
            assert {D._era_parts(r["first_use"])[1] if D._era_parts(r["first_use"]) else "undated"
                    for r in part} == {g["key"]}
    assert seen == len(rows)
    # "then alphabetical" is a real order once it works inside groups.
    era_alpha = [r["word"] for r in _all("era", then="alpha", grouped=True)]
    old = D.index(sort="era")[0]
    assert old["key"] == "old-english"
    assert era_alpha[:old["count"]] == sorted(era_alpha[:old["count"]])
    assert era_alpha != [r["word"] for r in _all("era")]
    # Positions agree with the grouped view; without `grouped`, alpha ignores the sub-sort as before.
    p = D.position("blog", sort=sort, then="length", dir=direction, then_dir="desc", grouped=True)
    assert rows[p["offset"]]["word"] == "blog"
    assert [r["word"] for r in _all("alpha", then="length")] == PUBLIC_HEADWORDS


def test_routes_without_a_dictionary(api: TestClient):
    st = api.get("/api/dict/status")
    assert st.status_code == 200 and st.json()["available"] is False
    assert api.get("/api/dict/entries").status_code == 503
    assert api.get("/api/dict/lookup", params={"word": "a"}).status_code == 503


def test_server_mounts_routes_and_builds_in_the_background(tmp_path: Path, source: Path,
                                                          monkeypatch: pytest.MonkeyPatch):
    from enough import broker
    from enough.server import create_app
    monkeypatch.setattr(broker, "CONFIG_PATH", tmp_path / "home" / "enough" / "config" / "broker.json")
    _root_is_scratch(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    app = create_app(project, "http://127.0.0.1:1/v1", supervise=False)
    with TestClient(app) as c:
        deadline = time.monotonic() + 30
        while not c.get("/api/dict/status").json()["ready"] and time.monotonic() < deadline:
            time.sleep(0.02)
        assert c.get("/api/dict/status").json()["ready"]
        assert c.get("/api/dict/lookup", params={"word": "zebra"}).json()["found"]
    assert D.feed_path().is_file() and str(D.feed_path()).startswith(str(tmp_path))


# ---------------------------------------------------------------------------
# the real thing, opt-in
# ---------------------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("ENOUGH_FEED_REAL") != "1" or not (REAL_DICT / "manifest.json").is_file(),
                    reason="set ENOUGH_FEED_REAL=1 to build the shipped reflib/dict (~10 s, ~400 MB in tmp) "
                           "and print timings (run with -s)")
def test_real_dictionary_build_and_timings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENOUGH_DICT_SOURCE", str(REAL_DICT))
    _root_is_scratch(tmp_path)
    timings: dict[str, float] = {}

    def tm(label, fn):
        t = time.perf_counter()
        out = fn()
        timings[label] = round((time.perf_counter() - t) * 1000, 1)
        return out

    st = tm("build", D.ensure_built)
    assert st["ready"], st
    man = json.loads((REAL_DICT / "manifest.json").read_text())
    assert st["headwords"] == man["headwords"]
    timings["db_mb"] = round(D.feed_path().stat().st_size / 1e6, 1)
    assert tm("lookup", lambda: D.lookup("aardvark"))["found"]
    assert tm("lookup form", lambda: D.lookup("Running"))["found"]
    tm("lookup miss", lambda: D.lookup("aardvarkz"))
    assert D.user_add({"word": "zzzfeedtest", "definition": "A test word.", "pos": "noun",
                       "pronunciation": "/z/"})["ok"]
    for s in D.SORT_KEYS:
        page = tm(f"entries {s}", lambda: D.entries(sort=s, then="alpha" if s != "alpha" else None))
        assert page["total"] == man["headwords"] + 1
        tm(f"entries {s} @60000", lambda: D.entries(sort=s, offset=60000))
        tm(f"index {s}", lambda: D.index(sort=s))
    tm("entries era>syllables desc @60000 cold",
       lambda: D.entries(sort="era", then="syllables", then_dir="desc", offset=60000))
    tm("fts entries q=termites", lambda: D.entries(q="termites"))
    tm("facets", D.facets)
    print("\nFEED real-data timings (ms):", json.dumps(timings, indent=1))
    slow = {k: v for k, v in timings.items() if k.startswith(("entries", "index")) and v > 300}
    assert not slow, slow
