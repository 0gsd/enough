"""Unit pass over enough/convert.py: the registry, the resolver, the state
machine, the manifest, datestamped naming — and the real pandoc round trip.

Everything below tmp_path. The one piece of global state convert.py touches
(`extras.json`) is redirected through the `ENOUGH_EXTRAS_STATE` seam by the
`scratch_state` autouse fixture, so no test can mark the developer's own
install as having an extra installed.

pandoc and typst are base dependencies, so the docx round trip and the
md → PDF export run unconditionally; docling is optional and its tests skip.
"""

from __future__ import annotations

import datetime as dt
import json
import zipfile
from pathlib import Path

import pytest

from enough import convert
from tests.conftest import FIXTURE_FOOTNOTE, FIXTURE_HEADER


@pytest.fixture(autouse=True)
def scratch_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENOUGH_EXTRAS_STATE", str(tmp_path / "state" / "extras.json"))
    monkeypatch.setenv("ENOUGH_WEIGHTS_DIR", str(tmp_path / "state" / "weights"))
    convert.reset_engines()
    yield
    convert.reset_engines()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_registry_shape():
    assert set(convert.FORMATS) == {
        ".docx", ".odt", ".rtf", ".epub", ".pdf", ".pptx", ".xlsx"}
    for ext, spec in convert.FORMATS.items():
        assert ext.startswith(".") and ext == ext.lower()
        assert spec.label and isinstance(spec.sync_ok, bool)
        assert spec.reader in ("pandoc", "docling")
        assert spec.writer in ("pandoc", "typst", None)
        # Only a format we can write back can be kept in sync.
        assert not (spec.sync_ok and spec.writer is None)
    # Images are a viewer concern, never a conversion.
    assert not (set(convert.IMAGE_EXTS) & set(convert.FORMATS))


def test_formats_view_is_the_one_source(monkeypatch: pytest.MonkeyPatch):
    view = convert.formats_view()
    assert [r["ext"] for r in view["formats"]] == list(convert.FORMATS)
    assert view["export_targets"] == convert.EXPORT_TARGETS
    assert set(view["engines"]) == {"pandoc", "typst", "docling"}
    docx = next(r for r in view["formats"] if r["ext"] == ".docx")
    assert docx["label"] == "Word document" and docx["sync_ok"] is True


def test_docling_needs_its_models_not_just_its_packages():
    # The engine is wired, but `ENOUGH_WEIGHTS_DIR` points at an empty scratch
    # dir here — and an install whose artifacts dir is empty is a conversion
    # that would stall on a 670 MB download nobody asked for, so it reports
    # unavailable and the click routes into the installer instead.
    assert convert.DOCLING_ENGINE_WIRED is True
    assert convert.docling_models_present() is False
    assert convert.docling_available() is False
    pdf = convert.FORMATS[".pdf"]
    assert convert.engine_available(pdf.reader) is False


def test_the_engine_missing_message_tells_the_two_cases_apart(
        monkeypatch: pytest.MonkeyPatch):
    pdf = convert.FORMATS[".pdf"]
    monkeypatch.setattr(convert, "docling_installed", lambda: False)
    assert "needs the PDF extra" in convert.engine_missing_message(pdf)
    # Packages in, weights absent: naming an extra the user already has would
    # read as a bug rather than as a step.
    monkeypatch.setattr(convert, "docling_installed", lambda: True)
    msg = convert.engine_missing_message(pdf)
    assert "models aren't" in msg and str(convert.weights_dir()) in msg


# ---------------------------------------------------------------------------
# pandoc_path() preference order
# ---------------------------------------------------------------------------

def test_pandoc_path_prefers_which(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(convert.shutil, "which", lambda n: "/opt/brew/bin/pandoc")
    convert.reset_engines()
    assert convert.pandoc_path() == "/opt/brew/bin/pandoc"
    assert convert.engines()["pandoc"]["where"] == "path"


def test_pandoc_path_falls_back_to_the_bundled_wheel(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(convert.shutil, "which", lambda n: None)
    import sys
    import types
    fake = types.ModuleType("pypandoc")
    fake.get_pandoc_path = lambda: "/venv/lib/pypandoc/files/pandoc"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pypandoc", fake)
    convert.reset_engines()
    assert convert.pandoc_path() == "/venv/lib/pypandoc/files/pandoc"
    assert convert.engines()["pandoc"]["where"] == "bundled"


def test_pandoc_path_none_in_a_broken_venv(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(convert.shutil, "which", lambda n: None)
    import sys
    import types
    fake = types.ModuleType("pypandoc")

    def _boom():
        raise OSError("no pandoc anywhere")

    fake.get_pandoc_path = _boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pypandoc", fake)
    convert.reset_engines()
    assert convert.pandoc_path() is None
    assert convert.engine_available("pandoc") is False


# ---------------------------------------------------------------------------
# Naming + pairing
# ---------------------------------------------------------------------------

def test_naming(tmp_path: Path):
    orig = tmp_path / "report.pdf"
    assert convert.twin_path(orig).name == "report.pdf.md"
    assert convert.assets_dir(orig).name == "report.pdf.assets"
    assert convert.manifest_path(orig).name == ".report.pdf.convert.json"
    # Pairing is by name, so a real report.md can never be mistaken for a twin.
    assert convert.original_for_twin(tmp_path / "report.md") is None
    assert convert.original_for_twin(tmp_path / "report.pdf.md") == orig


def test_pair_for_accepts_either_end(tmp_path: Path):
    orig = tmp_path / "memo.docx"
    assert convert.pair_for(orig) == (orig, tmp_path / "memo.docx.md")
    assert convert.pair_for(tmp_path / "memo.docx.md") == (orig, tmp_path / "memo.docx.md")
    # Plain markdown: exportable, but nobody's twin.
    assert convert.pair_for(tmp_path / "notes.md") == (None, tmp_path / "notes.md")
    with pytest.raises(convert.ConvertError):
        convert.pair_for(tmp_path / "data.csv")


def test_datestamped_naming_and_collisions(tmp_path: Path):
    when = dt.datetime(2026, 8, 19, 14, 32)
    orig = tmp_path / "report.pdf"
    first = convert.datestamped_path(orig, ".docx", when)
    assert first.name == "report-2026-08-19-1432.docx"
    first.write_text("x")
    second = convert.datestamped_path(orig, ".docx", when)
    assert second.name == "report-2026-08-19-1432-2.docx"
    second.write_text("x")
    assert convert.datestamped_path(orig, ".docx", when).name == \
        "report-2026-08-19-1432-3.docx"


def test_export_targets_include_the_originals_own_format(tmp_path: Path):
    # .rtf isn't on the universal menu, but an .rtf original must be
    # overwritable — it is sync_ok, and sync IS export-overwrite.
    assert ".rtf" not in convert.EXPORT_TARGETS
    assert ".rtf" in convert.export_targets_for(tmp_path / "letter.rtf")
    assert convert.export_targets_for(None) == convert.EXPORT_TARGETS


# ---------------------------------------------------------------------------
# The state machine, on planted files + manifests (no engine needed)
# ---------------------------------------------------------------------------

def plant(tmp_path: Path, *, original=b"ORIGINAL BYTES", twin="# twin\n",
          name="doc.docx") -> Path:
    """A converted pair on disk, in the `fresh` state."""
    orig = tmp_path / name
    orig.write_bytes(original)
    convert.twin_path(orig).write_text(twin, encoding="utf-8")
    convert.write_manifest(orig, convert.new_manifest(
        orig, engine={"name": "pandoc", "version": "3.9", "ocr": None}, assets=None))
    return orig


def test_state_unconverted_and_engine_missing(tmp_path: Path):
    docx = tmp_path / "memo.docx"
    docx.write_bytes(b"x")
    assert convert.state(docx) == "unconverted"
    # docling isn't wired, so a PDF with no twin reports engine-missing.
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    assert convert.state(pdf) == "engine-missing"
    with pytest.raises(convert.ConvertError):
        convert.state(tmp_path / "notes.txt")


def test_state_fresh_edited_stale_conflict(tmp_path: Path):
    orig = plant(tmp_path)
    assert convert.state(orig) == "fresh"

    convert.twin_path(orig).write_text("# twin\n\nedited by the user\n")
    assert convert.state(orig) == "edited"

    # Re-plant, then change only the original.
    orig = plant(tmp_path, name="two.docx")
    orig.write_bytes(b"CHANGED IN WORD")
    assert convert.state(orig) == "stale"

    orig = plant(tmp_path, name="three.docx")
    orig.write_bytes(b"CHANGED IN WORD")
    convert.twin_path(orig).write_text("# twin\n\nedited too\n")
    assert convert.state(orig) == "conflict"


def test_a_finder_touch_is_not_a_change(tmp_path: Path):
    orig = plant(tmp_path)
    before = convert.read_manifest(orig)["source"]["mtime_ns"]
    # Same bytes, new mtime — a `touch`, a cloud-sync re-stat, a `cp -p`.
    import os
    os.utime(orig, ns=(before + 10 ** 9, before + 10 ** 9))
    assert convert.state(orig) == "fresh"
    # ...and the manifest healed itself, so the next build doesn't re-hash.
    assert convert.read_manifest(orig)["source"]["mtime_ns"] != before


def test_manifest_missing_twin_is_garbage_collected(tmp_path: Path):
    orig = plant(tmp_path)
    convert.twin_path(orig).unlink()
    assert convert.state(orig) == "unconverted"
    assert not convert.manifest_path(orig).exists()


def test_manifest_schema(tmp_path: Path):
    orig = plant(tmp_path)
    man = json.loads(convert.manifest_path(orig).read_text())
    assert man["schema"] == 1
    assert set(man) == {"schema", "original", "twin", "assets", "engine",
                        "converted_at", "source", "twin_sha256", "twin_size",
                        "twin_mtime_ns", "sync", "last_export"}
    assert man["original"] == "doc.docx" and man["twin"] == "doc.docx.md"
    assert set(man["source"]) == {"sha256", "size", "mtime_ns"}
    assert man["sync"] is False and man["last_export"] is None
    assert man["converted_at"].endswith("Z")
    # A future schema reads as "not converted" rather than blowing up.
    man["schema"] = 99
    convert.manifest_path(orig).write_text(json.dumps(man))
    assert convert.read_manifest(orig) is None


def test_has_twin_needs_the_manifest_too(tmp_path: Path):
    # A hand-written `notes.pdf.md` is somebody's markdown file, not a twin;
    # hiding it from the tree would make it unreachable.
    stray = tmp_path / "notes.pdf"
    stray.write_bytes(b"%PDF")
    convert.twin_path(stray).write_text("mine\n")
    assert convert.has_twin(stray) is False
    assert convert.has_twin(plant(tmp_path)) is True


def test_sync_toggle_refuses_pdf(tmp_path: Path):
    orig = plant(tmp_path, name="paper.pdf", original=b"%PDF-1.7")
    with pytest.raises(convert.ConvertError) as e:
        convert.set_sync(orig, True)
    assert e.value.status == 400
    docx = plant(tmp_path, name="ok.docx")
    assert convert.set_sync(docx, True)["sync"] is True
    assert convert.read_manifest(docx)["sync"] is True


def test_accept_external_change_clears_stale(tmp_path: Path):
    orig = plant(tmp_path)
    orig.write_bytes(b"CHANGED IN WORD")
    convert.twin_path(orig).write_text("# twin\n\nmine\n")
    assert convert.state(orig) == "conflict"
    convert.accept_external_change(orig)
    assert convert.state(orig) == "edited"     # my twin still has my edits


# ---------------------------------------------------------------------------
# extras.json
# ---------------------------------------------------------------------------

def test_extras_state_honours_the_seam(tmp_path: Path):
    assert convert.extras_state_path() == tmp_path / "state" / "extras.json"
    assert convert.installed_extras() == []
    rec = convert.record_extra("pdf")
    assert rec["installed_at"].endswith("Z")
    assert convert.installed_extras() == ["pdf"]
    convert.forget_extra("pdf")
    assert convert.installed_extras() == []


def test_sync_argv_re_asks_for_every_recorded_extra(monkeypatch: pytest.MonkeyPatch):
    # The whole reason extras.json exists: `uv sync` is exact and would
    # otherwise uninstall the group on the next update.
    monkeypatch.setattr(convert.shutil, "which", lambda n: "/usr/local/bin/uv")
    monkeypatch.delenv("ENOUGH_DESKTOP", raising=False)
    convert.record_extra("pdf")
    argv = convert.ExtraInstaller().sync_argv("pdf")
    assert argv[:2] == ["/usr/local/bin/uv", "sync"]
    assert argv.count("--extra") == 1 and "pdf" in argv
    assert "--frozen" not in argv
    monkeypatch.setenv("ENOUGH_DESKTOP", "1")
    assert "--frozen" in convert.ExtraInstaller().sync_argv("pdf")


def test_the_install_prefetches_the_models_in_the_worker(
        monkeypatch: pytest.MonkeyPatch):
    """The tail of the install is a worker job, not an import.

    Doing it in-process would mean importing docling — which means importing
    torch — into the server, which is the one thing the worker exists to
    prevent (plan §1 decision 6)."""
    seen: dict = {}

    def fake_run_worker(job, **kw):
        seen.update(job)
        kw["on_progress"]({"pct": 40, "message": "fetching document models"})
        return {"artifacts_dir": job["artifacts_dir"], "bytes": 700_000_000}

    monkeypatch.setattr(convert, "run_worker", fake_run_worker)
    installer = convert.ExtraInstaller()
    result = installer._prefetch_models()
    assert seen["op"] == "prefetch"
    assert seen["artifacts_dir"] == str(convert.weights_dir())
    assert result["bytes"] == 700_000_000
    # The worker's line is what the convert-install SSE carries.
    assert installer._snap["message"] == "fetching document models"


def test_a_missing_extra_still_routes_into_the_install_modal(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The engine-missing path, simulated at the probe rather than by
    uninstalling: a machine that has the packages must still be able to prove
    the modal path works for a machine that doesn't."""
    monkeypatch.setattr(convert, "docling_installed", lambda: False)
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    assert convert.docling_available() is False
    assert convert.state(pdf) == "engine-missing"
    with pytest.raises(convert.ConvertError) as e:
        convert.convert_job(pdf)
    assert e.value.status == 503
    assert "PDF extra" in str(e.value)


# ---------------------------------------------------------------------------
# The real round trip (pandoc + typst are base dependencies)
# ---------------------------------------------------------------------------

def test_docx_round_trip(tmp_path: Path, make_docx):
    orig = make_docx(tmp_path / "memo.docx")
    result = convert.run_convert(orig)
    twin = convert.twin_path(orig)
    text = twin.read_text(encoding="utf-8")

    # The twin is plain markdown: no front matter, no HTML comment header.
    assert text.lstrip().startswith("# Fixture")
    # Footnote survived as gfm+footnotes syntax.
    assert "[^1]" in text and FIXTURE_FOOTNOTE in text
    # The image is a markdown image (not pandoc's raw <img>), pointing at a
    # flat path relative to the twin.
    assert result["images"] == 1
    assert "<img" not in text
    assert "](memo.docx.assets/" in text
    asset = next(convert.assets_dir(orig).iterdir())
    assert asset.parent.name == "memo.docx.assets"
    assert convert.state(orig) == "fresh"

    man = convert.read_manifest(orig)
    assert man["assets"] == "memo.docx.assets"
    assert man["engine"]["name"] == "pandoc"

    # Edit the twin, then overwrite the original.
    twin.write_text(text + "\n\nA sentence the user added.\n", encoding="utf-8")
    assert convert.state(orig) == "edited"
    out = convert.export(twin=twin, original=orig, target=".docx", mode="overwrite")
    assert out["written"] == "memo.docx" and out["undo"] is True
    assert out["reference_doc"] is True

    parts = zipfile.ZipFile(orig).namelist()
    # Decision 4: the running header can only be here because --reference-doc
    # carried it over — markdown has no way to express one.
    assert "word/header1.xml" in parts
    assert FIXTURE_HEADER in zipfile.ZipFile(orig).read("word/header1.xml").decode()
    # And the user's new sentence made it into the document.
    from enough import convert_worker  # noqa: F401 — pandoc round trip only
    import subprocess
    plain = subprocess.run([convert.pandoc_path(), "-f", "docx", "-t", "plain",
                            str(orig)], capture_output=True, text=True, check=True)
    assert "A sentence the user added." in plain.stdout
    # Export re-baselines both sides.
    assert convert.state(orig) == "fresh"
    assert convert.read_manifest(orig)["last_export"]["mode"] == "overwrite"


def test_export_copy_is_datestamped_and_leaves_the_original_alone(
        tmp_path: Path, make_docx):
    orig = make_docx(tmp_path / "memo.docx")
    before = orig.read_bytes()
    convert.run_convert(orig)
    out = convert.export(twin=convert.twin_path(orig), original=orig,
                         target=".odt", mode="copy")
    assert out["written"].startswith("memo-") and out["written"].endswith(".odt")
    assert Path(out["path"]).is_file()
    assert orig.read_bytes() == before
    assert out["undo"] is False


def test_pdf_export_via_typst(tmp_path: Path):
    # md → PDF works for ANY markdown file, twin or not (plan decision 5).
    notes = tmp_path / "notes.md"
    notes.write_text("# Notes\n\nSome prose, and a list:\n\n- one\n- two\n",
                     encoding="utf-8")
    out = convert.export(twin=notes, original=None, target=".pdf", mode="copy")
    pdf = Path(out["path"])
    assert pdf.name.startswith("notes-") and pdf.suffix == ".pdf"
    data = pdf.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"/Page" in data                 # at least one page object
    assert len(data) > 1000


def test_export_refusals(tmp_path: Path, make_docx):
    orig = make_docx(tmp_path / "memo.docx")
    convert.run_convert(orig)
    twin = convert.twin_path(orig)

    # Overwrite with a different format is a datestamped-copy job.
    with pytest.raises(convert.ConvertError) as e:
        convert.export(twin=twin, original=orig, target=".odt", mode="overwrite")
    assert e.value.status == 400

    # A plain markdown file has nothing to overwrite.
    plain = tmp_path / "notes.md"
    plain.write_text("# hi\n", encoding="utf-8")
    with pytest.raises(convert.ConvertError) as e:
        convert.export(twin=plain, original=None, target=".pdf", mode="overwrite")
    assert e.value.status == 400

    # A writer-less format (deck/workbook) is never overwritten.
    deck = plant(tmp_path, name="slides.pptx", original=b"PK\x03\x04")
    with pytest.raises(convert.ConvertError) as e:
        convert.export(twin=convert.twin_path(deck), original=deck,
                       target=".pptx", mode="overwrite")
    assert e.value.status == 400

    # And a stale original refuses until the conflict is resolved.
    orig.write_bytes(orig.read_bytes() + b"\x00")
    with pytest.raises(convert.ConvertError) as e:
        convert.export(twin=twin, original=orig, target=".docx", mode="overwrite")
    assert e.value.status == 409
    assert "changed outside enough" in str(e.value)
    # ...unless the user explicitly chose "export mine over it".
    out = convert.export(twin=twin, original=orig, target=".docx",
                         mode="overwrite", allow_stale=True)
    assert out["written"] == "memo.docx"


def test_convert_refuses_to_clobber_a_twin(tmp_path: Path, make_docx):
    orig = make_docx(tmp_path / "memo.docx")
    convert.run_convert(orig)
    with pytest.raises(convert.ConvertError) as e:
        convert.run_convert(orig)
    assert e.value.status == 409
    # force re-converts, stashing the twin so the user can undo.
    convert.twin_path(orig).write_text("# mine\n", encoding="utf-8")
    convert.run_convert(orig, force=True)
    stash = convert.twin_path(orig).parent / f".{convert.twin_path(orig).name}.undo"
    assert stash.read_text(encoding="utf-8") == "# mine\n"


def test_sync_after_save(tmp_path: Path, make_docx):
    orig = make_docx(tmp_path / "memo.docx")
    convert.run_convert(orig)
    twin = convert.twin_path(orig)
    # Not opted in → the hook is a no-op.
    assert convert.sync_after_save(twin) is None
    convert.set_sync(orig, True)
    twin.write_text(twin.read_text() + "\n\nSynced sentence.\n", encoding="utf-8")
    res = convert.sync_after_save(twin)
    assert res["state"] == "synced" and res["original"] == "memo.docx"
    assert convert.state(orig) == "fresh"
    # A stale original refuses — and says so, rather than clobbering.
    orig.write_bytes(orig.read_bytes() + b"\x00")
    twin.write_text(twin.read_text() + "\n\nAnd another.\n", encoding="utf-8")
    res = convert.sync_after_save(twin)
    assert res["state"] == "conflict"
    assert "changed outside enough" in res["detail"]


def test_a_plain_md_file_is_not_a_twin(tmp_path: Path):
    notes = tmp_path / "notes.md"
    notes.write_text("# hi\n", encoding="utf-8")
    assert convert.sync_after_save(notes) is None


def test_a_pdf_with_no_models_refuses_before_it_starts(tmp_path: Path):
    # The modal path: no weights in the scratch dir, so the job is refused
    # with a 503 the UI turns into "install the PDF reader" — never a
    # conversion that silently downloads.
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    with pytest.raises(convert.ConvertError) as e:
        convert.convert_job(pdf)
    assert e.value.status == 503


def test_reconvert_keeps_asset_names_stable(tmp_path: Path, make_docx):
    """A force re-convert clears the assets dir before extracting, so the
    same image lands under the same name instead of accumulating -2/-3
    collision suffixes (and orphaned files) on every re-convert."""
    memo = tmp_path / "memo.docx"
    make_docx(memo)
    convert.run_convert(memo)
    assets = tmp_path / "memo.docx.assets"
    first = sorted(f.name for f in assets.iterdir())
    convert.run_convert(memo, force=True)
    second = sorted(f.name for f in assets.iterdir())
    assert first == second
    twin = (tmp_path / "memo.docx.md").read_text(encoding="utf-8")
    for name in second:
        assert f"-2{Path(name).suffix}" not in twin
