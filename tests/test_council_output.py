"""P9 — the composure output, charges, reconvene, the pal seam, the brief.

No LLM and no network: every completion goes through the
`council.run_council_turn` seam and every pal call through `council.PAL_CALL`.
Isolation is set explicitly (HOME, the `ENOUGH_*` seams and
`broker.CONFIG_PATH`) so this file behaves identically with or without
conftest's autouse fixture.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import broker
from enough import composure as C
from enough import council as K
from enough.council import CouncilError
from enough.server import create_app

REL = "rness/io/composure/round-table.comp"

OUTLINE = """\
# What we decided

## Premise

### Chapter four moves

It is the strongest opening we have and nothing depends on it later.

## Costs

### The reveal lands twice

Nadia's continuity point: chapter nine re-explains what four now says.

### [gap: who rewrites nine?]

Nobody in the room owns the prose.

## Ending

### Ship it in the next pass

Two days, one editor.
"""

PROSE = ("We decided to move chapter four, but the reveal in nine will have "
         "to be cut back and nobody has said who does that.")


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_runtime():
    K.reset_runtime()
    yield
    K.reset_runtime()
    K.PAL_CALL = K._pal_not_wired


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / "enough" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    assert Path.home() == home, "a test must never touch the real ~/enough"
    for var, rel in (("ENOUGH_PROJECTS_STATE", "state/projects.json"),
                     ("ENOUGH_CACHEAWL_ROOT", "cacheawl"),
                     ("ENOUGH_INFOWORLD_ROOT", "no-infoworld"),
                     ("ENOUGH_WIKISINK_CONFIG", "wikisink.json"),
                     ("ENOUGH_READVISORS_ROOT", "readvisors-global"),
                     ("ENOUGH_UI_CONFIG", "ui.json")):
        monkeypatch.setenv(var, str(tmp_path / rel))
    monkeypatch.setattr(broker, "CONFIG_PATH",
                        home / "enough" / "config" / "broker.json")
    proj = tmp_path / "project"
    (proj / "rness" / "io" / "composure").mkdir(parents=True)
    (proj / "rness" / "readvisors").mkdir(parents=True)
    (proj / "notes").mkdir(parents=True)
    return proj


@pytest.fixture()
def client(project: Path):
    app = create_app(project, "http://127.0.0.1:1/v1", supervise=False)
    with TestClient(app) as c:
        yield c


TRIO = [{"id": "chief", "kind": "chief", "name": "Ed"},
        {"id": "rv:skeptic", "kind": "readvisor", "name": "Nadia"},
        {"id": "user", "kind": "user", "name": "you"}]


def sequence(*texts: str):
    """A seam that hands out `texts` in order, then repeats the last, and
    keeps every message list it was given. The outline retry is "the same
    speaker, one more instruction", so a test of it is a test of what the
    seam was handed the second time."""
    calls: list[list[dict]] = []

    async def _run(messages, on_token=None, **kw):
        calls.append(messages)
        text = texts[min(len(calls) - 1, len(texts) - 1)]
        if on_token is not None:
            await on_token(text)
        return text
    _run.calls = calls                                   # type: ignore[attr-defined]
    return _run


@pytest.fixture(autouse=True)
def _seam(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn", sequence("A statement."))
    monkeypatch.setattr(K, "resolve_n_ctx", lambda **kw: 131072)


def setup(client: TestClient, **over) -> dict:
    body = {"path": REL, "title": "Round table",
            "input": "Should chapter four move to the front?",
            "parameters": "Two rounds.", "constraints": "No rewriting.",
            "output": {"kind": "answer"}, "participants": TRIO,
            "max_rounds": 2}
    body.update(over)
    r = client.post("/api/council/setup", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def convene(client: TestClient) -> dict:
    r = client.post("/api/council/convene", json={"path": REL})
    assert r.status_code == 200, r.text
    return r.json()


def council(project: Path, *, rows: list[dict] | None = None,
            output: dict | None = None, emit=None, session=None,
            status: str = "running") -> K.Council:
    meta = K.validate_meta({
        "input": "Should chapter four move to the front?",
        "parameters": "Two rounds.", "constraints": "No rewriting.",
        "output": output or {"kind": "answer"},
        "participants": rows if rows is not None else TRIO,
        "max_rounds": 3, "status": status,
    })
    C.apply_ops(project / REL, None, [{"op": "set_council", "council": meta}],
                source="council", create=True, form="council",
                title="Round table", project_dir=project, rel_path=REL)
    return K.Council(project / REL, project_dir=project, rel_path=REL,
                     emit=emit, llm_url="http://127.0.0.1:1", session=session)


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def __call__(self, event: str, data: dict) -> None:
        self.events.append((event, data))

    def council_events(self) -> list[dict]:
        return [d for e, d in self.events if e == K.EVENT]


# ---------------------------------------------------------------------------
# 1 · the composure output
# ---------------------------------------------------------------------------

def test_the_composure_form_is_validated_at_setup():
    meta = K.validate_meta({"output": {"kind": "composure", "form": "cards"}})
    assert meta["output"] == {"kind": "composure", "path": None,
                              "form": "cards", "overwrite": False}
    # No form at all is the scaffold, which is the layout the skill teaches.
    assert K.validate_output({"kind": "composure"})["form"] == "scaffold"
    with pytest.raises(CouncilError) as e:
        K.validate_output({"kind": "composure", "form": "blank"})
    assert "scaffold, cards" in str(e.value)
    with pytest.raises(CouncilError):
        K.validate_output({"kind": "composure", "form": "columns"})


def test_a_document_output_still_refuses_a_comp_path():
    with pytest.raises(CouncilError) as e:
        K.validate_output({"kind": "document", "path": "notes/x.comp"})
    assert "Use the 'composure' output kind" in str(e.value)


def test_the_conclusion_framing_teaches_the_outline_grammar():
    text = K.conclusion_framing({"kind": "composure", "form": "scaffold"})
    assert "a new composure" in text                     # what it is for
    for rule in ("one `# ` line", "each `## ` line is a group",
                 "each `### ` line is a card", "[gap:"):
        assert rule in text, rule
    assert "no code fence" in text


def test_outline_composure_builds_or_returns_none():
    built = K.outline_composure("Round table", "scaffold", OUTLINE)
    assert built is not None
    assert built.title == "What we decided"              # the model's own `#`
    titles = [m.title for m in built.modules]
    assert "Chapter four moves" in titles
    assert C.GAP_TITLE in titles                         # the gap card is kept
    # Prose is not an outline, however good it is.
    assert K.outline_composure("Round table", "scaffold", PROSE) is None
    assert K.outline_composure("Round table", "scaffold", "") is None
    # A title-only reply parses but has no cards, which is the same answer.
    assert K.outline_composure("t", "cards", "# Only a title") is None


def test_a_fenced_outline_still_parses():
    fenced = "```markdown\n" + OUTLINE + "```"
    assert K.strip_code_fence(fenced).startswith("# What we decided")
    assert K.outline_composure("t", "cards", fenced) is not None
    # Text that merely contains a fence is left alone.
    assert K.strip_code_fence(PROSE) == PROSE


def test_the_output_path_sits_beside_the_council(project: Path):
    rel = K.output_composure_path(project, REL, when="2026-09-18")
    assert rel == "rness/io/composure/round-table-output-2026-09-18.comp"
    (project / rel).write_text("x", encoding="utf-8")
    assert K.output_composure_path(project, REL, when="2026-09-18").endswith(
        "round-table-output-2026-09-18-2.comp")


def test_concluding_with_a_composure_writes_and_links_it(
        client: TestClient, project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn", sequence(OUTLINE))
    setup(client, output={"kind": "composure", "form": "scaffold"})
    convene(client)
    r = client.post("/api/council/conclude", json={"path": REL})
    assert r.status_code == 200, r.text
    body = r.json()
    stamp = dt.date.today().isoformat()
    rel = f"rness/io/composure/round-table-output-{stamp}.comp"
    assert body["output"] == "composure"
    assert body["composure"] == rel
    assert body["output_fallback"] is None
    assert body["retried"] is False

    made = C.load(project / rel)
    assert made.title == "What we decided"
    assert made.form == "scaffold"
    assert [m.title for m in made.modules].count(C.GAP_TITLE) == 1

    # The council records where it went, and links to it.
    meta = body["council"]
    assert meta["status"] == "concluded"
    assert meta["output"]["path"] == rel
    assert meta["output_fallback"] is None
    comp = C.load(project / REL)
    links = [m for m in comp.modules if m.type == "doc"]
    assert [m.href for m in links] == [rel]
    # …and the export names it in the header.
    export = (project / body["transcript"]).read_text(encoding="utf-8")
    assert f"**Output.** composure (scaffold) → `{rel}`" in export


def test_a_bad_outline_is_retried_once_and_then_parses(
        client: TestClient, project: Path, monkeypatch: pytest.MonkeyPatch):
    seam = sequence(PROSE, OUTLINE)
    monkeypatch.setattr(K, "run_council_turn", seam)
    setup(client, output={"kind": "composure", "form": "cards"})
    convene(client)
    body = client.post("/api/council/conclude", json={"path": REL}).json()
    assert body["retried"] is True
    assert body["output_fallback"] is None
    assert body["composure"]
    assert C.load(project / body["composure"]).form == "cards"
    # Exactly two completions, and the second one carried the retry.
    assert len(seam.calls) == 2
    assert K.OUTLINE_RETRY in seam.calls[1][-1]["content"]
    assert K.OUTLINE_RETRY not in "".join(
        m["content"] for m in seam.calls[0])
    # The conclusion module on the canvas is the outline that worked.
    comp = C.load(project / REL)
    assert comp.modules[-2].bg == K.CONCLUSION_TINT
    assert "Chapter four moves" in C.rich_to_md(comp.modules[-2].pages[0].rich)


def test_two_unparseable_outlines_fall_back_to_an_answer(
        client: TestClient, project: Path, monkeypatch: pytest.MonkeyPatch):
    seam = sequence(PROSE, "Still not an outline, sorry.")
    monkeypatch.setattr(K, "run_council_turn", seam)
    setup(client, output={"kind": "composure", "form": "scaffold"})
    convene(client)
    body = client.post("/api/council/conclude", json={"path": REL}).json()
    assert len(seam.calls) == 2                          # one retry, not two
    assert body["output_fallback"] == "answer"
    assert body["composure"] is None
    assert body["council"]["output_fallback"] == "answer"
    assert body["council"]["status"] == "concluded"
    assert "would not parse" in body["detail"]
    # Nothing was written beside the council, and the decision is not lost:
    # the second attempt's prose is the conclusion module.
    made = list((project / "rness" / "io" / "composure").glob("*.comp"))
    assert [p.name for p in made] == ["round-table.comp"]
    comp = C.load(project / REL)
    assert comp.modules[-1].bg == K.CONCLUSION_TINT
    assert "Still not an outline" in C.rich_to_md(comp.modules[-1].pages[0].rich)
    assert [m for m in comp.modules if m.type == "doc"] == []
    export = (project / body["transcript"]).read_text(encoding="utf-8")
    assert "kept as answer" in export


# ---------------------------------------------------------------------------
# 2 · charges
# ---------------------------------------------------------------------------

def test_a_charge_is_one_line_and_capped():
    meta = K.validate_meta({"participants": [
        {"id": "chief", "kind": "chief", "name": "Ed",
         "charge": "  owns\n  the decision  "},
        {"id": "user", "kind": "user", "name": "you"}]})
    assert meta["participants"][0]["charge"] == "owns the decision"
    assert meta["participants"][1]["charge"] == ""
    with pytest.raises(CouncilError) as e:
        K.validate_participants([
            {"id": "chief", "kind": "chief", "name": "Ed",
             "charge": "x" * (K.MAX_CHARGE_CHARS + 1)}])
    assert str(K.MAX_CHARGE_CHARS) in str(e.value)
    # …and exactly at the cap is fine.
    assert K.validate_participants([
        {"id": "c", "kind": "chief", "name": "Ed",
         "charge": "x" * K.MAX_CHARGE_CHARS}])[0]["charge"]


def test_a_charge_reaches_that_participants_framing_only(project: Path):
    rows = [{"id": "chief", "kind": "chief", "name": "Ed",
             "charge": "owns the decision"},
            {"id": "rv:skeptic", "kind": "readvisor", "name": "Nadia",
             "charge": "argues the reader's side"},
            {"id": "user", "kind": "user", "name": "you"}]
    meta = K.validate_meta({"participants": rows})
    chief = K.identity_for(project, meta["participants"][0], "Ed")
    nadia = K.identity_for(project, meta["participants"][1], "Ed")
    assert "Your charge in this council: owns the decision" in chief
    assert "argues the reader's side" not in chief
    assert "Your charge in this council: argues the reader's side" in nadia
    assert "owns the decision" not in nadia
    # No charge, no section.
    plain = K.identity_for(project, meta["participants"][2], "Ed")
    assert "Your charge" not in plain


def test_charges_are_in_the_transcript_header(project: Path):
    c = council(project, rows=[
        {"id": "chief", "kind": "chief", "name": "Ed",
         "charge": "owns the decision"},
        {"id": "user", "kind": "user", "name": "you"}])
    rel = c.export_transcript()
    text = (project / rel).read_text(encoding="utf-8")
    assert "- **Ed** (chief) — owns the decision" in text
    assert "- **you** (user)\n" in text


# ---------------------------------------------------------------------------
# 3 · reconvene
# ---------------------------------------------------------------------------

def test_reconvene_refuses_a_council_that_has_not_concluded(
        client: TestClient):
    setup(client)
    convene(client)
    r = client.post("/api/council/reconvene", json={"path": REL})
    assert r.status_code == 409
    assert "only a concluded council" in r.json()["detail"]


def test_reconvene_carries_the_brief_the_answer_and_the_charges(
        client: TestClient, project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn",
                        sequence("Move it. The reveal in nine is the cost."))
    rows = [dict(TRIO[0], charge="owns the decision"),
            dict(TRIO[1], charge="argues the reader's side"), TRIO[2]]
    setup(client, participants=rows)
    convene(client)
    client.post("/api/council/conclude", json={"path": REL})

    r = client.post("/api/council/reconvene", json={"path": REL})
    assert r.status_code == 200, r.text
    body = r.json()
    rel = body["path"]
    assert rel != REL and (project / rel).is_file()
    assert body["title"].endswith("· reconvened")

    meta = body["council"]
    assert meta["status"] == "ready"
    assert meta["reconvene"] is True
    assert meta["reconvened_from"] == REL
    assert meta["parameters"] == "Two rounds." and meta["constraints"]
    assert [p["charge"] for p in meta["participants"]] == [
        "owns the decision", "argues the reader's side", ""]
    assert meta["round"] == 0 and meta["turn"] == 0
    assert meta["next"] == "chief"
    # The prior brief AND the prior answer, as input.
    assert "Should chapter four move to the front?" in meta["input"]
    assert REL in meta["input"]
    assert "The reveal in nine is the cost." in meta["input"]

    # Linked both ways; the old one is still concluded and still has its
    # statements.
    fresh = C.load(project / rel)
    assert [m.href for m in fresh.modules if m.type == "doc"] == [REL]
    old = C.load(project / REL)
    assert old.council["status"] == "concluded"
    assert old.council["reconvened_to"] == rel
    assert rel in [m.href for m in old.modules if m.type == "doc"]
    assert len(K.read_statements(old)) == 1


def test_reconvene_carries_a_document_output_by_reference(
        client: TestClient, project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn",
                        sequence("# The decision\n\n" + "body. " * 800))
    setup(client, output={"kind": "document", "path": "notes/out.md"})
    convene(client)
    done = client.post("/api/council/conclude", json={"path": REL}).json()
    assert done["document"] == "notes/out.md"

    meta = client.post("/api/council/reconvene",
                       json={"path": REL}).json()["council"]
    assert "`notes/out.md`" in meta["input"]
    assert "# The decision" in meta["input"]
    assert "…(truncated)" in meta["input"]
    # The excerpt is bounded, so a reconvened council does not start full.
    assert len(meta["input"]) < K.RECONVENE_EXCERPT_CHARS + 1_000
    assert meta["output"]["path"] == "notes/out.md"       # path rides over


def test_a_reconvened_council_can_conclude_and_reconvene_again(
        client: TestClient, project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn", sequence("The second answer."))
    setup(client)
    convene(client)
    client.post("/api/council/conclude", json={"path": REL})
    second = client.post("/api/council/reconvene",
                         json={"path": REL}).json()["path"]
    r = client.post("/api/council/conclude", json={"path": second})
    assert r.status_code == 200, r.text
    third = client.post("/api/council/reconvene", json={"path": second})
    assert third.status_code == 200, third.text
    assert third.json()["council"]["reconvened_from"] == second
    assert len(list((project / "rness" / "io" / "composure").glob("*.comp"))) == 3
    # The chain is readable from either end.
    assert C.load(project / second).council["reconvened_to"] == \
        third.json()["path"]


# ---------------------------------------------------------------------------
# 4 · module.turn and the SSE turn agree
# ---------------------------------------------------------------------------

def test_the_sse_turn_is_a_string_like_the_module_turn(project: Path):
    rec = Recorder()
    c = council(project, emit=rec)
    asyncio.run(c.take_turn())
    asyncio.run(c.take_turn())
    events = [d for d in rec.council_events()
              if d["phase"] in ("start", "token", "end")]
    assert events, "no statement phases were announced"
    for d in events:
        assert isinstance(d["turn"], str), d
    assert [d["turn"] for d in events if d["phase"] == "end"] == ["1", "2"]
    # The dedupe the UI does — String(m.turn) === String(ev.turn) — now
    # compares two strings that are already equal.
    comp = C.load(project / REL)
    module_turns = [m.turn for m in comp.modules if m.speaker]
    assert module_turns == ["1", "2"]
    for d in events:
        assert any(t == d["turn"] for t in module_turns)


def test_a_status_event_still_carries_the_meta_counter_as_an_int(
        project: Path):
    rec = Recorder()
    c = council(project, emit=rec)
    asyncio.run(c.take_turn())
    status = [d for d in rec.council_events() if d["phase"] == "status"]
    assert status and isinstance(status[-1]["turn"], int)
    assert status[-1]["turn"] == c.state()["council"]["turn"]


# ---------------------------------------------------------------------------
# 5 · setup writes the brief module
# ---------------------------------------------------------------------------

def test_setup_writes_the_brief_module_from_the_four_fields(
        client: TestClient, project: Path):
    state = setup(client)
    comp = C.load(project / REL)
    brief = comp.modules[0]
    assert brief.title == "Brief"
    text = C.rich_to_md(brief.pages[0].rich)
    assert "**Input.** Should chapter four move to the front?" in text
    assert "**Parameters.** Two rounds." in text
    assert "**Constraints.** No rewriting." in text
    assert "**Desired output.** a decided answer" in text
    # The shipped placeholder is gone.
    assert "What the council is working from" not in text
    assert state["council"]["brief_module"] == brief.id


def test_the_brief_module_is_rewritten_when_the_setup_changes(
        client: TestClient, project: Path):
    setup(client)
    setup(client, input="Should chapter nine go?",
          output={"kind": "composure", "form": "cards"})
    text = C.rich_to_md(C.load(project / REL).modules[0].pages[0].rich)
    assert "Should chapter nine go?" in text
    assert "chapter four" not in text
    assert "board of cards in the cards layout" in text


def test_brief_markdown_skips_the_fields_that_are_empty():
    meta = K.validate_meta({"input": "Just this.",
                            "output": {"kind": "answer"}})
    text = K.brief_markdown(meta)
    assert text.startswith("**Input.** Just this.")
    assert "Parameters" not in text and "Constraints" not in text
    assert "**Desired output.**" in text


# ---------------------------------------------------------------------------
# 6 · the pal seam
# ---------------------------------------------------------------------------

def test_pal_call_is_unwired_by_default():
    with pytest.raises(NotImplementedError) as e:
        K.PAL_CALL("anything")
    assert "pal lane" in str(e.value)


def test_ask_pal_turn_distils_then_commits_what_left_and_what_came_back(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn",
                        sequence("Does moving a reveal earlier cost tension?"))
    sent: list[str] = []

    def fake_pal(prompt: str) -> tuple[str, str]:
        sent.append(prompt)
        return "acme/sonnet-9", "Usually yes, unless the reveal is a setup."

    monkeypatch.setattr(K, "PAL_CALL", fake_pal)
    rec = Recorder()
    council(project)                 # the file; the seam builds its own
    out = asyncio.run(K.ask_pal_turn(project / REL, "ask about the reveal",
                                     project_dir=project, rel_path=REL,
                                     emit=rec))
    # The module-level seam announced on the `council` channel like any turn.
    assert [d["phase"] for d in rec.council_events()][0] == "start"
    assert rec.council_events()[0]["speaker_kind"] == "pal"

    # The chief wrote the prompt, and the user's ask was in front of it.
    assert sent == ["Does moving a reveal earlier cost tension?"]
    assert out.speaker == "pal · acme/sonnet-9"
    assert out.speaker_kind == "pal"

    comp = C.load(project / REL)
    module = comp.module(out.module)
    assert module.bg == K.PAL_TINT == "gray"
    assert module.speaker_kind == "pal"
    assert module.turn == "1"
    text = C.rich_to_md(module.pages[0].rich)
    # What left the machine is the first block, quoted, and the reply is the
    # body under it.
    assert text.index("→ pal") < text.index("Usually yes")
    assert "Does moving a reveal earlier cost tension?" in text
    assert "Usually yes, unless the reveal is a setup." in text


def test_a_pal_answer_never_takes_a_slot_in_the_rotation(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn", sequence("A distilled ask."))
    monkeypatch.setattr(K, "PAL_CALL", lambda p: ("m", "A pal answer."))
    c = council(project)
    asyncio.run(c.take_turn())                            # Ed speaks
    before = c.state()
    asyncio.run(c.ask_pal_turn("what about the reveal?"))
    after = c.state()
    # The rotation did not move: Nadia was next and Nadia is still next.
    assert before["next_name"] == after["next_name"] == "Nadia"
    assert after["council"]["cursor"] == before["council"]["cursor"]
    assert after["council"]["round"] == before["council"]["round"]
    assert after["council"]["turn"] == before["council"]["turn"] + 1
    # …and the pal is not a participant, so the budget is unchanged.
    assert after["budget"]["speakers"] == before["budget"]["speakers"] == 2
    assert [p["id"] for p in after["council"]["participants"]] == \
        ["chief", "rv:skeptic", "user"]


def test_the_next_participant_reads_the_pal_answer(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    seam = sequence("A distilled ask.", "Nadia's reply.")
    monkeypatch.setattr(K, "run_council_turn", seam)
    monkeypatch.setattr(K, "PAL_CALL", lambda p: ("m9", "The pal's opinion."))
    c = council(project)
    asyncio.run(c.ask_pal_turn("what about the reveal?"))
    asyncio.run(c.take_turn())
    transcript = "".join(m["content"] for m in seam.calls[-1])
    assert "pal · m9: " in transcript
    assert "The pal's opinion." in transcript


def test_an_async_pal_call_is_awaited(project: Path,
                                      monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn", sequence("A distilled ask."))

    async def fake_pal(prompt: str) -> tuple[str, str]:
        return "async/model", "From a coroutine."

    monkeypatch.setattr(K, "PAL_CALL", fake_pal)
    c = council(project)
    out = asyncio.run(c.ask_pal_turn("go on then"))
    assert out.speaker == "pal · async/model"


def test_ask_pal_turn_refuses_an_empty_ask_and_surfaces_a_pal_failure(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn", sequence("A distilled ask."))
    c = council(project)
    with pytest.raises(CouncilError) as e:
        asyncio.run(c.ask_pal_turn("   "))
    assert "needs a question" in str(e.value)

    def angry(prompt: str):
        raise RuntimeError("openrouter 502")

    monkeypatch.setattr(K, "PAL_CALL", angry)
    with pytest.raises(CouncilError) as e:
        asyncio.run(c.ask_pal_turn("ask them"))
    assert "openrouter 502" in str(e.value)
    # Nothing was committed, and the unwired default still raises its own.
    assert K.read_statements(C.load(project / REL)) == []


def test_an_unwired_pal_call_reaches_the_caller(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn", sequence("A distilled ask."))
    c = council(project)
    with pytest.raises(NotImplementedError):
        asyncio.run(c.ask_pal_turn("ask them"))


def test_the_pal_distillation_carries_the_brief_and_the_ask(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    seam = sequence("A distilled ask.")
    monkeypatch.setattr(K, "run_council_turn", seam)
    monkeypatch.setattr(K, "PAL_CALL", lambda p: ("m", "ok"))
    c = council(project)
    asyncio.run(c.take_turn())
    asyncio.run(c.ask_pal_turn("what about the reveal?"))
    messages = seam.calls[-1]
    whole = "".join(m["content"] for m in messages)
    assert "Should chapter four move to the front?" in whole   # the brief
    assert "A distilled ask." in whole                         # the transcript
    last = messages[-1]
    assert last["role"] == "user"
    assert "what about the reveal?" in last["content"]
    assert "Distil one question for the pal" in last["content"]
    assert "under 300 words" in last["content"]


def test_the_pal_prompt_is_capped(project: Path,
                                  monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(K, "run_council_turn",
                        sequence("word " * 4_000))
    seen: list[str] = []
    monkeypatch.setattr(K, "PAL_CALL",
                        lambda p: (seen.append(p), ("m", "ok"))[1])
    c = council(project)
    asyncio.run(c.ask_pal_turn("go on"))
    assert len(seen[0]) == K.PAL_PROMPT_CHARS


def test_pal_statement_quotes_every_line_of_the_prompt():
    text = K.pal_statement("first line\n\nsecond line", "the reply")
    lines = text.splitlines()
    assert lines[0].startswith("> **→ pal**")
    assert "> first line" in lines and "> second line" in lines
    assert text.rstrip().endswith("the reply")
    assert K.pal_statement("p", "").endswith("(the pal said nothing)")
