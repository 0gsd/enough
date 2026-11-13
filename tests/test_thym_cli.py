"""The command line's new arguments (THYM.md 11.3, 23): `--model local|cloud[:<id>]`, `--calls N`, the bare path for a
program of one input, folder inputs, several outputs listed as they land, refusals in the person's words.

No model and no broker: the conftest seams put HOME and every `ENOUGH_*` path in tmp_path; llama-server's id and
window read as unknown; the cloud's gate and completion are stood in for where a test needs them, and anything else
that would reach the cloud fails the test.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from enough import cloud, models
from enough import thym_host as H
from enough.thym import Refusal, cli

REPO = Path(__file__).resolve().parent.parent
SUITE = REPO / "tests" / "fixtures" / "thym"
INPUTS = SUITE / "inputs"
PUBLISH = SUITE / "programs" / "publish-story.thym"
SPLIT = SUITE / "programs" / "split-a-folder.thym"
COUNT = "thym 0\n\nprogram count-words\n  why: how long a text is.\n\n  takes story: text\n  gives n: number\n\n" \
        "  give words story\nend\n"
TWO = "thym 0\n\nprogram tidy\n  takes story: text, voice: morph\n  gives n: number\n\n  give words story\nend\n"


@pytest.fixture(autouse=True)
def offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = tmp_path / "live-models.json"
    state.write_text(json.dumps({"current": "g40-04"}), encoding="utf-8")
    monkeypatch.setattr(models, "LIVE_STATE", state)
    monkeypatch.setattr(H, "local_model_id", lambda url=None: None)
    monkeypatch.setattr(H, "_read_n_ctx", lambda url=None: None)

    def no_cloud(*a, **kw):
        raise AssertionError("the cloud was asked")
    monkeypatch.setattr(cloud, "chat_completion", no_cloud)
    monkeypatch.setattr(cloud, "gate_status", lambda: (_ for _ in ()).throw(AssertionError("the gate was asked")))


def gate(monkeypatch: pytest.MonkeyPatch, open_: bool) -> None:
    monkeypatch.setattr(cloud, "gate_status", lambda: {
        "open": open_, "reason": None if open_ else "'local models only' is on in the broker",
        "denial": None, "model_id": "vendor/large-model" if open_ else None})


def write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def lines(capsys: pytest.CaptureFixture) -> list[str]:
    return capsys.readouterr().out.strip().splitlines()


def test_parse_model():
    assert cli.parse_model(None) == ("local", None) and cli.parse_model("local") == ("local", None)
    assert cli.parse_model("cloud") == ("cloud", None)
    assert cli.parse_model("cloud:vendor/large-model") == ("cloud", "vendor/large-model")
    for bad in ("sky", "cloud:", "local:g40"):
        r = cli.parse_model(bad)
        assert isinstance(r, Refusal) and r.check == "model" and "local, cloud or cloud:<model id>" in r.message


def test_inputs_name_path_or_a_bare_path(tmp_path: Path):
    one = write(tmp_path, "count.thym", COUNT)
    assert cli._pairs(["notes.md"], one) == {"story": "notes.md"}
    assert cli._pairs(["story=notes.md"], one) == {"story": "notes.md"}
    assert cli._pairs(["a=b.md"], None, names=["a"]) == {"a": "b.md"}
    two = write(tmp_path, "tidy.thym", TWO)
    r = cli._pairs(["notes.md"], two)
    assert isinstance(r, Refusal) and r.message == "tidy takes story and voice; give each as name=path"
    r = cli._pairs(["nope=notes.md"], one)
    assert r.message == "count-words takes no nope; it takes story"
    assert cli._pairs(["notes.md", "other.md"], one).message == "count-words takes one input, story; give it once"
    assert "given twice" in cli._pairs(["story=a.md", "story=b.md"], one).message
    weird = tmp_path / "x=y.md"                                    # a path with an = in it is a bare path
    weird.write_text("x", encoding="utf-8")
    assert cli._pairs([str(weird)], one) == {"story": str(weird)}


def test_run_takes_a_bare_path_and_lists_its_output(tmp_path: Path, capsys):
    prog = write(tmp_path, "count.thym", COUNT)
    assert cli.main(["run", str(prog), str(INPUTS / "notes.md")]) == 0
    out = lines(capsys)
    assert out[0].startswith("ran count-words on notes.md")
    assert out[1].startswith("n: ") and out[1].endswith("n.txt") and out[-1].startswith("trace: ")


def test_plan_of_several_inputs_refuses_a_bare_path(tmp_path: Path, capsys):
    prog = write(tmp_path, "tidy.thym", TWO)
    assert cli.main(["plan", str(prog), str(INPUTS / "notes.md")]) == 2
    assert lines(capsys) == [f"{prog}: refused at plan (input): tidy takes story and voice; give each as name=path"]


def test_a_folder_input_and_several_outputs_land_and_are_listed(capsys):
    assert cli.main(["run", str(SPLIT), f"repo={INPUTS / 'little-tool'}"]) == 0
    out = lines(capsys)
    assert out[0].startswith("ran split-a-folder on little-tool")
    named = {ln.split(": ", 1)[0]: ln.split(": ", 1)[1] for ln in out[1:-1]}
    assert list(named) == ["code", "prose", "size"]
    assert named["code"].endswith("outputs/code/ (a folder of 3 files)")
    assert named["prose"].endswith("outputs/prose/ (a folder of 2 files)")
    assert named["size"].endswith("size.txt")
    assert cli.main(["run", str(SPLIT), str(INPUTS / "little-tool")]) == 0, "the bare path holds for a folder too"


def test_plan_prints_the_models_line_on_this_machine(capsys):
    assert cli.main(["plan", str(PUBLISH), str(INPUTS / "notes.md")]) == 0
    assert lines(capsys) == ["publish-story: 7 nodes, 3 ask a model; largest prompt 307 tokens, output budget 0 words",
                             "3 model calls, at most 9, on this machine (g40-04)"]


def test_plan_on_the_cloud_says_so_plainly(monkeypatch, capsys):
    gate(monkeypatch, True)
    assert cli.main(["plan", str(PUBLISH), str(INPUTS / "notes.md"), "--model", "cloud"]) == 0
    assert lines(capsys)[1] == "3 model calls, at most 9, on the cloud (openrouter: vendor/large-model)"
    assert cli.main(["plan", str(PUBLISH), str(INPUTS / "notes.md"), "--model", "cloud:vendor/other",
                     "--calls", "20"]) == 0
    assert lines(capsys)[1] == "3 model calls, at most 9, on the cloud (openrouter: vendor/other); ceiling 20"


def test_a_shut_gate_refuses_plan_and_run_before_anything_is_asked(monkeypatch, capsys):
    gate(monkeypatch, False)
    assert cli.main(["plan", str(PUBLISH), str(INPUTS / "notes.md"), "--model", "cloud"]) == 2
    said = lines(capsys)[-1]
    assert said == (f"{PUBLISH}:12: refused at plan (cloud): the cloud is not open for this run: 'local models only' "
                    "is on in the broker")
    assert cli.main(["run", str(PUBLISH), str(INPUTS / "notes.md"), "--model", "cloud"]) == 2
    out = lines(capsys)
    assert any("refused at plan (cloud): the cloud is not open for this run" in ln for ln in out), out
    assert not (Path(os.environ["ENOUGH_THYM_ROOT"]) / "runs").exists() or not any(
        (Path(os.environ["ENOUGH_THYM_ROOT"]) / "runs").glob("*/outputs/*")), "nothing landed"


def test_the_cloud_needs_a_ceiling_when_its_count_is_open(tmp_path: Path, monkeypatch, capsys):
    from test_thym_host import TREE
    gate(monkeypatch, True)
    prog = write(tmp_path, "tree.thym", TREE)
    assert cli.main(["plan", str(prog), str(INPUTS / "notes.md"), "--model", "cloud"]) == 2
    out = lines(capsys)
    assert out[1].startswith("2 model calls, at most 6, on the cloud (openrouter: vendor/large-model); and more that "
                             "cannot be counted before it runs")
    assert out[2].endswith("(again calls itself and asks); give a ceiling with --calls")
    assert cli.main(["plan", str(prog), str(INPUTS / "notes.md"), "--model", "cloud", "--calls", "40"]) == 0
    assert cli.main(["plan", str(prog), str(INPUTS / "notes.md")]) == 0, "a local plan needs no ceiling"


def test_bad_route_arguments_are_refused_in_words(capsys):
    assert cli.main(["plan", str(PUBLISH), str(INPUTS / "notes.md"), "--model", "sky"]) == 2
    assert "--model is local, cloud or cloud:<model id>, not 'sky'" in lines(capsys)[0]
    assert cli.main(["run", str(PUBLISH), str(INPUTS / "notes.md"), "--calls", "0"]) == 2
    assert "--calls is a ceiling of at least 1 model call, not 0" in lines(capsys)[0]


def test_the_host_gets_the_route_model_and_ceiling(tmp_path: Path, monkeypatch, capsys):
    seen: list = []
    original = H.runtime_kwargs

    def spy(**kw):
        seen.append(kw)
        return original(**kw)
    monkeypatch.setattr(H, "runtime_kwargs", spy)
    gate(monkeypatch, True)
    prog = write(tmp_path, "count.thym", COUNT)
    assert cli.main(["run", str(prog), str(INPUTS / "notes.md"), "--model", "cloud:vendor/x", "--calls", "7"]) == 0
    (kw,) = seen
    assert (kw["route"], kw["model"], kw["calls"], kw["ceiling"]) == ("cloud", "vendor/x", 7, "--calls")


def test_the_vendored_file_names_no_app_path():
    """cli.py is copied text-exactly into another product: what it adds names no app seam or install path (the lines
    it already had are the audit's)."""
    import subprocess
    diff = subprocess.run(["git", "diff", "HEAD", "--", "enough/thym/cli.py", "enough/thym/moves/doc.py"],
                          cwd=REPO, capture_output=True, text=True).stdout
    added = [ln for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    for ln in added:
        assert "ENOUGH_" not in ln and "~/enough" not in ln and "defaults/cosm" not in ln, ln


# --- --manifests DIR: an application's own moves, known alongside the bundled ones ---------------------------------

SHOUT = "thym 0\n\nprogram loud\n  why: a text, shouted.\n\n  takes story: text\n  gives n: text\n\n  give shoutout story\nend\n"


@pytest.fixture
def clean_manifests():
    from enough import macrocosm as mc
    from enough.thym import declarations
    yield
    mc.use_extra_manifest_dirs(())
    declarations._default.cache_clear()


def app_folder(tmp_path: Path, name: str = "shoutout", code: str | None = None) -> Path:
    d = tmp_path / "app-manifests"
    d.mkdir(exist_ok=True)
    extra = f", code: {code}" if code else ""
    (d / "shouty.moves.cosm").write_text(
        f"moves-of: shouty/1\nmoves:\n  - {{name: {name}, takes: [text], gives: text{extra}, says: a text, shouted}}\n",
        encoding="utf-8")
    return d


def test_without_manifests_an_outside_move_is_unknown(tmp_path: Path, capsys, clean_manifests):
    prog = write(tmp_path, "loud.thym", SHOUT)
    assert cli.main(["check", str(prog)]) == 2
    assert "shoutout" in lines(capsys)[-1]


def test_manifests_make_an_outside_move_known_to_check_plan_and_enumerate(tmp_path: Path, capsys, clean_manifests):
    prog = write(tmp_path, "loud.thym", SHOUT)
    folder = app_folder(tmp_path)
    assert cli.main(["check", str(prog), "--manifests", str(folder)]) == 0
    assert lines(capsys) == ["ok"]
    assert cli.main(["plan", str(prog), str(INPUTS / "notes.md"), "--manifests", str(folder)]) == 0
    assert "loud" in lines(capsys)[0]
    assert cli.main(["enumerate", str(prog), "--manifests", str(folder)]) == 0
    assert (tmp_path / "loud.thym.cosm").is_file()


def test_run_refuses_an_outside_move_whose_code_is_not_installed(tmp_path: Path, capsys, clean_manifests):
    prog = write(tmp_path, "loud.thym", SHOUT)
    folder = app_folder(tmp_path, code="not_an_installed_app.moves:shoutout")
    assert cli.main(["run", str(prog), str(INPUTS / "notes.md"), "--manifests", str(folder)]) == 2
    out = " ".join(lines(capsys))
    assert "shoutout" in out and "not_an_installed_app.moves:shoutout" in out and "installed" in out


def test_a_move_named_as_a_bundled_move_is_refused_and_nothing_changes(tmp_path: Path, capsys, clean_manifests):
    prog = write(tmp_path, "count.thym", COUNT)
    folder = app_folder(tmp_path, name="words")
    assert cli.main(["check", str(prog), "--manifests", str(folder)]) == 2
    out = lines(capsys)
    assert "the move words" in out[0] and "never overridden" in out[0]
    from enough import macrocosm as mc
    assert mc._EXTRA_MANIFEST_DIRS == ()


def test_a_manifests_folder_that_is_not_one_is_refused(tmp_path: Path, capsys, clean_manifests):
    prog = write(tmp_path, "count.thym", COUNT)
    assert cli.main(["check", str(prog), "--manifests", str(tmp_path / "nope")]) == 2
    assert "not a folder" in lines(capsys)[0]
