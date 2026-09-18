"""The council engine, with no LLM and no network.

Every completion in this file goes through the module-level seam
`council.run_council_turn`, replaced by `fake_turn` below. If a test in here
ever needs a model, the seam has been bypassed and that is the bug.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from enough import composure as C
from enough import council as K
from enough.council import CouncilError

REL = "rness/io/composure/round-table.comp"


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_runtime():
    K.reset_runtime()
    yield
    K.reset_runtime()


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    (proj / "rness" / "io" / "composure").mkdir(parents=True)
    (proj / "rness" / "readvisors").mkdir(parents=True)
    return proj


def readvisor(project: Path, folder: str, display: str, body: str = "") -> None:
    d = project / "rness" / "readvisors" / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / "AGENT.md").write_text(
        f"# {display}\n\n## Core orientation\n\n{body or 'Reads slowly.'}\n\n"
        f"---\nenough-tooltip-text: \"{display}\"\n", encoding="utf-8")
    (d / "MOTIVATION.md").write_text(
        f"## What this readvisor cares about\n\nGetting {display} right.\n",
        encoding="utf-8")


def participants(*rows: tuple[str, str, str]) -> list[dict]:
    return [{"id": pid, "kind": kind, "name": name}
            for pid, kind, name in rows]


TRIO = participants(("chief", "chief", "Ed"),
                    ("rv:skeptic", "readvisor", "Nadia"),
                    ("user", "user", "you"))


def council(project: Path, *, rel: str = REL, rows: list[dict] | None = None,
            output: dict | None = None, emit=None, session=None,
            max_rounds: int = 3, status: str = "running") -> K.Council:
    """A council on disk, already convened, with no statements yet."""
    target = project / rel
    meta = K.validate_meta({
        "input": "Should chapter four move to the front?",
        "parameters": "Two rounds, then decide.",
        "constraints": "Do not rewrite the prose.",
        "output": output or {"kind": "answer"},
        "participants": rows if rows is not None else TRIO,
        "max_rounds": max_rounds,
        "status": status,
    })
    C.apply_ops(target, None, [{"op": "set_council", "council": meta}],
                source="council", create=True, form="council",
                title="Round table", project_dir=project, rel_path=rel)
    return K.Council(target, project_dir=project, rel_path=rel, emit=emit,
                     llm_url="http://127.0.0.1:1", session=session)


class Recorder:
    """Stands in for `session.emit`."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def __call__(self, event: str, data: dict) -> None:
        self.events.append((event, data))

    def phases(self) -> list[str]:
        return [d.get("phase") for e, d in self.events if e == K.EVENT]


class FakeSupervisor:
    """A roomy window, so the file-level tests exercise the rotation rather
    than the fold. The fold has its own tests, with explicit shares."""
    current_ctx = 131072


class FakeSession:
    def __init__(self) -> None:
        self.generation_lock = asyncio.Lock()
        self.client = None
        self.supervisor = FakeSupervisor()


def fake_turn(reply: str = "A statement.", *, seen: list | None = None):
    """Replace `council.run_council_turn`. Records the messages it was given
    and streams the canned reply in three chunks, so the token phase is
    exercised rather than asserted away."""
    async def _run(messages, on_token=None, **kw):
        if seen is not None:
            seen.append(messages)
        text = reply(messages) if callable(reply) else reply
        size = max(1, len(text) // 3)
        for i in range(0, len(text), size):
            chunk = text[i:i + size]
            if on_token is not None:
                await on_token(chunk)
        return text
    return _run


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def test_the_schema_normalizes_and_names_every_refusal():
    meta = K.validate_meta({"participants": TRIO})
    assert meta["status"] == "setup"
    assert meta["order"] == "round-robin"
    assert meta["max_rounds"] == 3
    assert meta["output"] == {"kind": "answer", "path": None, "form": None,
                              "overwrite": False}
    with pytest.raises(CouncilError, match="unknown council status"):
        K.validate_meta({"status": "thinking", "participants": TRIO})
    with pytest.raises(CouncilError, match="max_rounds must be between"):
        K.validate_meta({"max_rounds": 99, "participants": TRIO})
    with pytest.raises(CouncilError, match="unknown participant kind"):
        K.validate_meta({"participants": [{"id": "x", "kind": "cat",
                                           "name": "Tom"}]})
    with pytest.raises(CouncilError, match="both called"):
        K.validate_meta({"participants": participants(
            ("a", "chief", "Ed"), ("b", "readvisor", "ed"))})
    with pytest.raises(CouncilError, match="one chief"):
        K.validate_meta({"participants": participants(
            ("a", "chief", "Ed"), ("b", "chief", "Mo"))})
    with pytest.raises(CouncilError, match="at least one readvisor"):
        K.validate_meta({"participants": participants(("u", "user", "you"))})


def test_a_document_output_needs_a_path_and_refuses_a_comp():
    with pytest.raises(CouncilError, match="needs a path"):
        K.validate_output({"kind": "document"})
    with pytest.raises(CouncilError, match="writes markdown"):
        K.validate_output({"kind": "document", "path": "x.comp"})
    assert K.validate_output({"kind": "composure"})["kind"] == "composure"
    with pytest.raises(CouncilError, match="unknown council output kind"):
        K.validate_output({"kind": "podcast"})


def test_pal_is_validated_and_then_ignored_everywhere():
    """0.3.5 reserves the kind so a 0.4.0 council opens here. It must never
    speak, never count toward the budget and never appear in the rotation."""
    meta = K.validate_meta({"participants": participants(
        ("chief", "chief", "Ed"), ("pal", "pal", "sonnet"),
        ("user", "user", "you"))})
    assert [p["kind"] for p in meta["participants"]] == ["chief", "pal", "user"]
    assert [p["id"] for p in K.speakers(meta)] == ["chief"]
    assert K.next_speaker(meta)["id"] == "chief"
    K.advance(meta, meta["participants"][0])
    assert K.next_speaker(meta)["id"] == "chief"       # wrapped past the pal
    assert meta["round"] == 1
    assert "sonnet" not in K.brief_text(meta)          # not "in the room"


def test_charge_and_reconvene_round_trip_for_p9():
    meta = K.validate_meta({"reconvene": True, "participants": [
        {"id": "chief", "kind": "chief", "name": "Ed",
         "charge": "owns the decision"},
        {"id": "u", "kind": "user", "name": "you"},
        {"id": "rv:c", "kind": "readvisor", "name": "Nadia",
         "charge": "owns continuity"}]})
    assert meta["reconvene"] is True
    assert meta["participants"][2]["charge"] == "owns continuity"
    again = K.validate_meta(json.loads(json.dumps(meta)))
    assert again == meta


# ---------------------------------------------------------------------------
# Tints
# ---------------------------------------------------------------------------

def test_tints_are_assigned_once_and_cycle_the_swatches():
    rows = participants(("chief", "chief", "Ed"), ("u", "user", "you"),
                        *[(f"rv{i}", "readvisor", f"R{i}") for i in range(7)])
    meta = K.validate_meta({"participants": rows})
    by_kind = {p["kind"]: p["tint"] for p in meta["participants"]
               if p["kind"] in ("chief", "user")}
    assert by_kind == {"chief": K.CHIEF_TINT, "user": K.USER_TINT}
    tints = [p["tint"] for p in meta["participants"] if p["kind"] == "readvisor"]
    assert tints[:5] == list(K.READVISOR_TINTS)
    assert tints[5:] == list(K.READVISOR_TINTS[:2])   # cycles, stably
    assert K.validate_meta(meta)["participants"] == meta["participants"]


# ---------------------------------------------------------------------------
# The budget
# ---------------------------------------------------------------------------

def test_the_share_is_an_even_split_with_a_floor():
    assert K.share_for(8192, 4) == 2048
    assert K.share_for(8192, 1) == 8192          # N=1: the whole window
    assert K.share_for(8192, 3) == 2730          # floor, not round
    assert K.share_for(512, 8) == K.MIN_SHARE    # tiny n_ctx still runs
    assert K.share_for(0, 3) == K.MIN_SHARE
    assert K.share_for(8192, 0) == 8192          # never divides by zero


def test_n_ctx_prefers_the_supervisor_then_props_then_the_fallback(monkeypatch):
    class Sup:
        current_ctx = 16384
    monkeypatch.setattr(K, "probe_n_ctx", lambda url: None)
    assert K.resolve_n_ctx(supervisor=Sup(), llm_url="x") == 16384
    assert K.resolve_n_ctx(supervisor=None, llm_url="x") == K.CTX_FALLBACK
    monkeypatch.setattr(K, "probe_n_ctx", lambda url: 4096)
    assert K.resolve_n_ctx(supervisor=None, llm_url="x") == 4096
    # The cloud slot has no /props; the documented constant stands in.
    assert K.resolve_n_ctx(supervisor=Sup(), llm_url="x",
                           active_model="opro-api") == K.CTX_CLOUD


# ---------------------------------------------------------------------------
# Message lists
# ---------------------------------------------------------------------------

def statements(*rows: tuple[str, str, str]) -> list[K.Statement]:
    return [K.Statement(module=f"m{i}", speaker=s, speaker_kind=k, turn=i,
                        text=t)
            for i, (s, k, t) in enumerate(rows, start=1)]


def test_the_message_list_flips_perspective():
    meta = K.validate_meta({"input": "the question", "participants": TRIO})
    said = statements(("Ed", "chief", "Ed's first."),
                      ("Nadia", "readvisor", "Nadia disagrees."),
                      ("you", "user", "The user chimes in."))
    mine = K.build_messages(meta, said, "I am Nadia.", "Nadia", share=8192)
    assert mine[0] == {"role": "system", "content": "I am Nadia."}
    assert mine[1]["role"] == "user" and "the question" in mine[1]["content"]
    assert mine[2] == {"role": "user", "content": "Ed: Ed's first."}
    assert mine[3] == {"role": "assistant", "content": "Nadia disagrees."}
    assert mine[4] == {"role": "user", "content": "you: The user chimes in."}
    # The same transcript, read by the chief, flips the other way.
    theirs = K.build_messages(meta, said, "I am Ed.", "Ed", share=8192)
    assert theirs[2] == {"role": "assistant", "content": "Ed's first."}
    assert theirs[3] == {"role": "user", "content": "Nadia: Nadia disagrees."}


def test_folding_keeps_the_brief_and_is_idempotent():
    meta = K.validate_meta({"input": "PINNED-BRIEF-TOKEN",
                            "participants": TRIO})
    said = statements(*[(f"R{i}", "readvisor",
                         f"Point number {i}. " + "padding " * 300)
                        for i in range(1, 9)])
    small = K.build_messages(meta, said, "sys", "R1", share=900)
    big = K.build_messages(meta, said, "sys", "R1", share=100_000)
    assert len(small) < len(big)
    # The brief survives every fold.
    assert any("PINNED-BRIEF-TOKEN" in m["content"] for m in small)
    fold = [m for m in small if m["content"].startswith("Earlier in this")]
    assert len(fold) == 1
    assert "Point number 1." in fold[0]["content"]
    assert "padding padding" not in fold[0]["content"]   # first sentence only
    # Deterministic: same inputs, same messages.
    assert K.build_messages(meta, said, "sys", "R1", share=900) == small
    # The most recent statement is never folded away.
    assert small[-1]["content"].endswith("padding ")
    tiny = K.build_messages(meta, said, "sys", "R1", share=K.MIN_SHARE)
    assert len([m for m in tiny if m["role"] in ("user", "assistant")]) >= 3
    # The fold reports itself, so the UI can say "raise ctx" the moment it
    # starts costing the council its memory.
    stats: dict = {}
    K.build_messages(meta, said, "sys", "R1", share=900, stats=stats)
    assert stats["folded"] >= 1 and stats["budget"] == 720
    assert stats["head"] > 0 and stats["total"] > stats["head"]


def test_the_fold_stops_when_the_system_prompt_is_what_is_over_budget():
    """An unfoldable head must not eat the transcript. The chief carries the
    project's whole assembled prompt — around 20 000 tokens on a stock
    project — so on a small window folding to nothing would cost the council
    its memory and save not one token."""
    meta = K.validate_meta({"input": "q", "participants": TRIO})
    said = statements(*[(f"R{i}", "readvisor", f"Point {i}. " + "pad " * 40)
                        for i in range(1, 9)])
    huge = "x" * (60_000 * K.CHARS_PER_TOKEN)
    stats: dict = {}
    msgs = K.build_messages(meta, said, huge, "R1", share=8192, stats=stats)
    kept = [m for m in msgs[2:] if not m["content"].startswith("Earlier in")]
    assert len(kept) >= 2                       # not folded down to one
    assert stats["head"] > stats["budget"]      # the head is what is over
    assert stats["total"] - stats["head"] <= K.MIN_TRANSCRIPT_TOKENS + 400


def test_first_sentence_is_mechanical():
    assert K.first_sentence("One. Two. Three.") == "One."
    assert K.first_sentence("No terminator here") == "No terminator here"
    assert K.first_sentence("  spaced\nout.  more") == "spaced out."
    assert K.first_sentence("") == ""


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------

def test_round_robin_and_the_queued_user_statement_taking_the_next_slot():
    meta = K.validate_meta({"participants": participants(
        ("chief", "chief", "Ed"), ("a", "readvisor", "Nadia"),
        ("b", "readvisor", "Sam"), ("user", "user", "you"))})
    order = []
    for _ in range(6):
        who = K.next_speaker(meta)
        order.append(who["name"])
        K.advance(meta, who)
    assert order == ["Ed", "Nadia", "Sam", "Ed", "Nadia", "Sam"]
    assert meta["round"] == 2

    # A queued statement jumps the queue without consuming the rotation: the
    # participant whose turn it was still speaks next.
    meta["queue"] = [{"text": "wait, one thing"}]
    assert K.next_speaker(meta)["kind"] == "user"
    K.advance(meta, K.user_participant(meta))
    meta["queue"] = []
    assert K.next_speaker(meta)["name"] == "Ed"
    assert meta["round"] == 2           # the interjection closed no round
    assert meta["turn"] == 7


def test_a_council_with_no_user_participant_never_stalls():
    meta = K.validate_meta({"participants": participants(
        ("chief", "chief", "Ed"), ("a", "readvisor", "Nadia"))})
    meta["queue"] = [{"text": "orphaned"}]
    assert K.next_speaker(meta)["kind"] == "chief"


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

def test_tool_xml_is_stripped_not_refused():
    body, n = K.strip_tool_calls(
        "Before.\n<tool name=\"write_file\"><path>x</path></tool>\nAfter.")
    assert n == 1 and "<tool" not in body
    assert "Before." in body and "After." in body
    # A dangling open tag at the end of a truncated stream goes too.
    body, n = K.strip_tool_calls("Said a thing.\n<tool name=\"shell\">\n<comm")
    assert n == 1 and body.strip() == "Said a thing."
    assert K.strip_tool_calls("no tools here")[1] == 0


def test_a_model_that_signs_its_own_statement_is_unsigned():
    assert K.clean_statement("Ed: the point is this.", "Ed") == \
        "the point is this."
    assert K.clean_statement("Nadia: hello", "Ed") == "Nadia: hello"
    assert K.clean_statement("  spaced  ", "Ed") == "spaced"


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------

def test_the_framings_say_the_things_the_spec_requires():
    chief = K.chief_framing("Ed")
    rv = K.readvisor_framing("Nadia", "Ed")
    for text in (chief, rv):
        assert "I'd defer to <name> on that" in text
        assert str(K.STATEMENT_WORD_CAP) in text
        assert "Do not write a tool call" in text
        assert "under your own name" in text or "Speak as yourself" in text
        assert "Do not write your own name at the start" in text
    assert "You are Ed, the chief readvisor" in chief
    assert "You are Nadia" in rv
    assert "never write a statement on their behalf" in rv
    assert "never write their statement for them" in chief
    concl = K.conclusion_framing({"kind": "document", "path": "notes/out.md"})
    assert "`notes/out.md`" in concl and "a written document" in concl
    assert "a decided answer" in K.conclusion_framing({"kind": "answer"})


def test_identity_for_a_readvisor_is_its_two_documents_plus_the_framing(
        project: Path):
    readvisor(project, "open-skeptic", "Nadia the Skeptic")
    p = {"id": "rv:open-skeptic", "kind": "readvisor",
         "name": "Nadia the Skeptic", "folder": "open-skeptic",
         "charge": "owns the counter-case"}
    text = K.identity_for(project, p, "Ed")
    assert "Nadia the Skeptic" in text
    assert "## Readvisor:" in text and "### Motivation" in text
    assert "This is a council" in text
    assert "owns the counter-case" in text          # P9's charge rides now
    # A participant with no folder on disk still gets an honest identity.
    missing = K.identity_for(project, {"kind": "readvisor", "name": "Ghost"},
                             "Ed")
    assert "No profile was found" in missing


# ---------------------------------------------------------------------------
# The transcript is the state
# ---------------------------------------------------------------------------

def test_a_turn_commits_a_locked_tinted_packed_statement(project: Path):
    rec, sess = Recorder(), FakeSession()
    c = council(project, emit=rec, session=sess)
    import enough.council as mod
    mod.run_council_turn = fake_turn("Ed says the thing.")
    out = run(c.take_turn())
    assert out.speaker == "Ed" and out.turn == 1
    comp = C.load(project / REL)
    m = comp.module(out.module)
    assert m.locked and m.speaker == "Ed" and m.speaker_kind == "chief"
    assert m.bg == K.CHIEF_TINT and m.title == "Ed · turn 1"
    assert m.w == C.FULLPORT[0]
    # Single column, packed: the statement sits under the brief with the
    # gutter, using the brief's own height rather than a uniform row.
    brief = comp.modules[0]
    assert m.x == brief.x
    assert m.y == pytest.approx(brief.y + brief.h + K.COLUMN_GUTTER)
    assert rec.phases()[:2] == ["start", "token"]
    assert "end" in rec.phases() and "status" in rec.phases()
    assert any(e == C.EVENT for e, _ in rec.events)


def test_a_restart_mid_council_continues_from_the_file(project: Path):
    """A brand-new engine over the same path must behave identically — the
    `.comp` is the whole of a council's memory."""
    import enough.council as mod
    mod.run_council_turn = fake_turn("first")
    c = council(project, session=FakeSession())
    run(c.take_turn())
    run(c.take_turn())
    del c
    fresh = K.Council(project / REL, project_dir=project, rel_path=REL,
                      session=FakeSession(), llm_url="http://127.0.0.1:1")
    state = fresh.state()
    assert state["council"]["turn"] == 2
    assert [s["speaker"] for s in state["statements"]] == ["Ed", "Nadia"]
    assert state["next_name"] == "Ed"          # wrapped, round closed
    assert state["council"]["round"] == 1
    seen: list = []
    mod.run_council_turn = fake_turn("third", seen=seen)
    out = run(fresh.take_turn())
    assert out.turn == 3 and out.speaker == "Ed"
    # Its message list was rebuilt from the transcript, not from memory.
    roles = [m["role"] for m in seen[0]]
    assert roles == ["system", "user", "assistant", "user"]
    assert seen[0][2]["content"] == "first"
    assert seen[0][3]["content"] == "Nadia: first"


def test_a_queued_user_statement_is_committed_without_a_completion(
        project: Path):
    import enough.council as mod
    called: list = []

    async def boom(*a, **k):
        called.append(1)
        return "should not run"
    mod.run_council_turn = boom
    c = council(project, session=FakeSession())
    comp, meta = c.load()
    meta["queue"] = [{"text": "I want the shorter version."}]
    c._commit([{"op": "set_meta"}], meta)
    out = run(c.take_turn())
    assert not called
    assert out.speaker_kind == "user" and out.text.startswith("I want")
    m = C.load(project / REL).module(out.module)
    assert m.bg == K.USER_TINT and m.locked
    assert c.load()[1]["queue"] == []


def test_statements_are_read_back_in_turn_order(project: Path):
    import enough.council as mod
    mod.run_council_turn = fake_turn("x")
    c = council(project, session=FakeSession())
    for _ in range(3):
        run(c.take_turn())
    comp, _meta = c.load()
    said = K.read_statements(comp)
    assert [s.turn for s in said] == [1, 2, 3]
    assert [s.speaker for s in said] == ["Ed", "Nadia", "Ed"]


def test_a_tool_call_in_a_statement_never_reaches_the_card(project: Path):
    import enough.council as mod
    mod.run_council_turn = fake_turn(
        "My view.\n<tool name=\"shell\"><command>rm -rf /</command></tool>")
    c = council(project, session=FakeSession())
    out = run(c.take_turn())
    assert "<tool" not in out.text and "rm -rf" not in out.text
    assert out.stripped == 1
    md = C.rich_to_md(C.load(project / REL).module(out.module).pages[0].rich)
    assert "rm -rf" not in md


# ---------------------------------------------------------------------------
# Locks
# ---------------------------------------------------------------------------

def test_a_council_turn_holds_the_generation_lock_both_ways(project: Path):
    """The exclusion in both directions: while the council streams, the lock
    is held (so a chat turn cannot start) and `turn_in_flight()` is true (so
    `/api/chat` can refuse politely rather than queue)."""
    import enough.council as mod
    sess = FakeSession()
    seen: dict = {}

    async def watching(messages, on_token=None, **kw):
        seen["locked"] = sess.generation_lock.locked()
        seen["in_flight"] = K.turn_in_flight()
        return "held"
    mod.run_council_turn = watching
    c = council(project, session=sess)
    run(c.take_turn())
    assert seen == {"locked": True, "in_flight": True}
    assert not sess.generation_lock.locked()
    assert not K.turn_in_flight()


def test_a_failed_turn_releases_everything_and_says_so(project: Path):
    import enough.council as mod
    sess, rec = FakeSession(), Recorder()

    async def blow_up(*a, **k):
        raise RuntimeError("llama-server went away")
    mod.run_council_turn = blow_up
    c = council(project, emit=rec, session=sess)
    with pytest.raises(RuntimeError):
        run(c.take_turn())
    assert not K.turn_in_flight()
    assert not sess.generation_lock.locked()
    assert "error" in rec.phases()
    assert C.load(project / REL).council["turn"] == 0     # nothing committed


def test_the_composure_write_door_still_owns_council_statements(project: Path):
    import enough.council as mod
    mod.run_council_turn = fake_turn("engine-owned")
    c = council(project, session=FakeSession())
    out = run(c.take_turn())
    from enough.composure import ComposureError
    with pytest.raises(ComposureError, match="council engine owns"):
        C.apply_ops(project / REL, None,
                    [{"op": "set_page", "module": out.module, "n": 1,
                      "markdown": "forged"}], source="ui", rel_path=REL)
    # Geometry from the UI is fine — that is how auto-height lands.
    C.apply_ops(project / REL, None,
                [{"op": "update_module", "id": out.module, "h": 999}],
                source="ui", rel_path=REL)
    assert C.load(project / REL).module(out.module).h == 999
    # ...but unlocking one to rewrite it is not.
    with pytest.raises(ComposureError, match="council field"):
        C.apply_ops(project / REL, None,
                    [{"op": "update_module", "id": out.module, "speaker": ""}],
                    source="ui", rel_path=REL)


def test_set_council_is_the_engines_op(project: Path):
    from enough.composure import ComposureError
    council(project)
    with pytest.raises(ComposureError, match="council engine's op"):
        C.apply_ops(project / REL, None,
                    [{"op": "set_council", "council": {"status": "concluded"}}],
                    source="readvisor", rel_path=REL)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def test_the_transcript_export_carries_a_header_block(project: Path):
    import enough.council as mod
    mod.run_council_turn = fake_turn("Said something worth keeping.")
    c = council(project, session=FakeSession(),
                output={"kind": "document", "path": "notes/out.md"})
    run(c.take_turn())
    run(c.take_turn())
    rel = c.export_transcript(output_path="notes/out.md")
    assert rel.startswith("rness/knowledge/councils/")
    text = (project / rel).read_text(encoding="utf-8")
    assert "## The brief" in text
    assert "Should chapter four move to the front?" in text
    assert "Do not rewrite the prose." in text
    assert "## Participants" in text
    assert "**Ed** (chief)" in text and "**you** (user)" in text
    assert "`notes/out.md`" in text
    assert text.count("Said something worth keeping.") == 2
    # A second export the same day does not clobber the first.
    again = c.export_transcript()
    assert again != rel and (project / again).is_file()


def test_the_brief_names_the_room_and_the_wanted_output():
    meta = K.validate_meta({"input": "the input", "constraints": "no poems",
                            "output": {"kind": "document",
                                       "path": "notes/x.md"},
                            "participants": TRIO})
    text = K.brief_text(meta)
    assert "**Input.** the input" in text
    assert "**Constraints.** no poems" in text
    assert "notes/x.md" in text
    assert "Ed (chief), Nadia (readvisor), you (user)" in text


# ---------------------------------------------------------------------------
# Heights
# ---------------------------------------------------------------------------

def test_the_height_heuristic_is_monotone_and_on_grid():
    short = C.estimate_height("one line", 816)
    long = C.estimate_height("word " * 2000, 816)
    # 2 x 72 units of fullport padding plus one 24-unit line box.
    assert short == 168.0
    assert C.estimate_height("one line", 320) == C.HEIGHT_MIN
    assert long > short
    assert C.estimate_height("word " * 200000, 816) == C.HEIGHT_MAX
    for text in ("", "a", "para\n\npara\n\npara", "word " * 500):
        h = C.estimate_height(text, 816)
        assert h % C.GRID == 0
    # Narrower module, same text, taller box.
    body = "word " * 200
    assert C.estimate_height(body, 320) > C.estimate_height(body, 816)
