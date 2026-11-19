"""The language library, as enough keeps it: the texts a fabulac's reliances cite, synced from cosmoes.org's shelf.

The shelf is cosmoes-site's `library/` (pin 7 of the 0.8 build). `scripts/sync_languages.py` copies it, verified,
into the source folder (env `ENOUGH_LANGUAGES_SOURCE`, default `reflib/languages/` in the install):

    library.json                                 the registry, byte for byte (shelves; one entry per kept or pinned text)
    <shelf>/<text>/<version>/files/...           the publisher's files as they came, never edited
    <shelf>/<text>/<version>/NOTICE|FETCHED|SHA256SUMS   the licence and notice, the fetch, the sums over files/

The index is one SQLite file built from those files alone by `enough/library_index.py` (cosmoes-site's
`client/library_index.py`, vendored byte for byte) under the state root (env `ENOUGH_LANGUAGES_ROOT`, default
`~/enough/languages/`), never committed, rebuilt whenever the shelf's digest differs from the one it records. enough
runs, imports and installs nothing it reads here: the texts are read as text.

What it gives:

- `Library.find(stated)`: a reliance's citation `{in, version, at, digest}` (with an optional `section-digest`) to
  the section it names, by the publisher's anchor (object id or title slug), else by heading path, else by the id
  the publisher's HTML build gives it, else by the section's digest; `Library.cite(stated)` says what came of it
  (`resolved`, `changed`, `unplaced`, `missing`, `not-aboard`, `unknown`). `enough.transconception.resolve_citation` is the one place a check asks.
- `Library.section(...)`: one section with its text, its page's digest and the kept text's notice (the route's).
- `Library.volume(...)`: a kept text, or one page of it, as a DocOES volume (`oes: doc/1`) built at runtime: the
  notice first, then the sections in the publisher's order, each citable by its id, its anchor and its digest.

An installed enough has no synced shelf: there the shelf is the cache of texts fetched on demand from
cosmoes.org's library (`enough/library_fetch.py`, ruled 2026-11-19), `<ENOUGH_LANGUAGES_ROOT>/shelf/`. A citation
of a text not aboard starts its fetch and reads `fetching` until it is kept (then it resolves); offline, or with the
fetch off, it reads `not-aboard`. A synced shelf, where there is one (a developer's checkout), is read instead and
nothing is fetched into it.

`in` is a shelf and text (`python/docs`), or a name a language's ground catalogue cites a text as (`cited-as:
python` in `defaults/cosm/ground/python.ground.cosm`'s head). `version` is the kept version or any patch of it
(`3.13.18` names the kept `3.13`). `at` is `<page>[.html|.txt][#<anchor or heading path>]`; a heading path is the
titles joined by ` > `.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import library_index as li

INSTALL_ROOT = Path(__file__).resolve().parents[1]
INDEX_DB = "library.sqlite"
SHELF_DIR = "reflib/languages"
COPY_LINE = ("A copy kept in enough's language library, synced from the cosmoes.org library: not the publisher's own "
             "page.")
STATES = ("resolved", "changed", "unplaced", "missing", "fetching", "not-aboard", "unknown")
PAGE_SUFFIXES = (".html", ".htm", ".xhtml", ".txt", ".rst", ".md")
PATH_SEP = " > "


class LibraryUnavailable(RuntimeError):
    """No shelf to read, or a shelf that does not verify (its index cannot be built)."""


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

def source_dir() -> Path:
    """The synced shelf: `ENOUGH_LANGUAGES_SOURCE`, else the install's `reflib/languages/`."""
    env = os.environ.get("ENOUGH_LANGUAGES_SOURCE")
    return Path(env).expanduser() if env else INSTALL_ROOT / SHELF_DIR


def state_root() -> Path:
    """Where the index is built: `ENOUGH_LANGUAGES_ROOT`, else `~/enough/languages/`."""
    env = os.environ.get("ENOUGH_LANGUAGES_ROOT")
    return Path(env).expanduser() if env else Path.home() / "enough" / "languages"


def index_path() -> Path:
    return state_root() / INDEX_DB


def cache_dir() -> Path:
    """The shelf of texts fetched on demand from cosmoes.org: `<state root>/shelf/`."""
    from . import library_fetch
    return state_root() / library_fetch.CACHE_DIR


def present(root: Path | None = None) -> bool:
    """Whether a shelf has been synced here (its registry is there)."""
    return (Path(root or source_dir()) / li.REGISTRY).is_file()


_LOCAL: dict[tuple[str, str], "Library"] = {}
_LOCAL_GUARD = threading.Lock()


def local() -> "Library | None":
    """The library on this machine: the synced shelf when there is one (no fetch into it); else the cache of texts
    fetched on demand, with its fetcher when a fetch may run (the first use in a launch fetches the registry again
    in the background); None when there is neither a shelf nor a cache nor a fetch allowed. One object per (shelf,
    index) pair; its index is built on first use."""
    from . import library_fetch
    root, db, fetcher = source_dir(), index_path(), None
    if not present(root):
        root = cache_dir()
        fetcher = library_fetch.shared(root)
        if fetcher is None and not present(root):
            return None
    key = (str(root), str(db))
    with _LOCAL_GUARD:
        lib = _LOCAL.get(key)
        if lib is None:
            lib = _LOCAL[key] = Library(root, db)
        lib.fetcher = fetcher
    if fetcher is not None and present(root):
        fetcher.refresh_once()
    return lib


# ---------------------------------------------------------------------------
# The cited-as names of the ground catalogues
# ---------------------------------------------------------------------------

def catalogue_texts() -> dict[str, dict]:
    """`{cited-as: head text}` from every language's ground catalogue (its head's `texts`): how a `stated.in` such as
    `python` names a shelf, text and version."""
    out: dict[str, dict] = {}
    try:
        from . import languages
    except ImportError:                                   # pragma: no cover - a vendored copy without the registry
        return out
    for name, lang in languages.LANGUAGES.items():
        if getattr(lang, "ground_path", None) is None:
            continue
        try:
            doc = languages.catalogue(name)
        except (KeyError, OSError, ValueError):
            continue
        for t in doc.get("texts") or []:
            if isinstance(t, dict) and t.get("cited-as") and t.get("shelf") and t.get("text"):
                out.setdefault(str(t["cited-as"]), t)
    return out


def _minor_of(version: str, kept: str) -> bool:
    """Whether `version` is `kept` or a patch of it (`3.13.18` of `3.13`)."""
    v, k = str(version), str(kept)
    return v == k or v.startswith(k + ".")


def split_at(at: str) -> tuple[str, str]:
    """`<page>[.suffix][#fragment]` as (page without its suffix, fragment)."""
    page, _, frag = str(at).partition("#")
    for suf in PAGE_SUFFIXES:
        if page.endswith(suf):
            page = page[: -len(suf)]
            break
    return page.strip("/"), frag


# ---------------------------------------------------------------------------
# A section found
# ---------------------------------------------------------------------------

@dataclass
class Hit:
    """One section of a kept text. `digest` is its page's sha256 (what a `stated.digest` prefixes); `section_digest`
    the section's own (what a `stated.section-digest` prefixes); `by` says how it was found."""
    shelf: str
    text: str
    version: str
    text_id: int
    section_id: int
    file: str
    page: str | None
    anchor: str | None
    heading: str
    path: list
    kind: str
    level: int
    line_from: int
    line_to: int
    digest: str
    section_digest: str
    parent: int | None
    by: str
    entry: dict = field(default_factory=dict, repr=False)

    @property
    def key(self) -> str:
        return f"{self.shelf}/{self.text}/{self.version}"

    def at(self) -> str:
        """The citation's `at` for this section: the page and its anchor (or heading path)."""
        frag = self.anchor or PATH_SEP.join(str(p) for p in self.path)
        return f"{self.page or self.file}" + (f"#{frag}" if frag else "")


# ---------------------------------------------------------------------------
# The library
# ---------------------------------------------------------------------------

class Library:
    """A synced shelf and its index. `root` holds `library.json` and the version folders; `db` is where the index
    is built (rebuilt when stale, under a lock). `cited` maps extra `stated.in` names to head texts (tests); the
    ground catalogues' `cited-as` names are always known."""

    def __init__(self, root: Path, db: Path, *, cited: dict[str, dict] | None = None, fetcher: Any = None):
        self.root, self.db = Path(root), Path(db)
        #: `enough.library_fetch.Fetcher` filling this shelf on demand, or None (a synced shelf; the fetch off)
        self.fetcher = fetcher
        self._cited_extra = dict(cited or {})
        self._cited: dict[str, dict] | None = None
        self._lock = threading.Lock()
        self._checked: tuple | None = None

    # ------------------------------------------------------------------ the shelf
    def registry(self) -> dict:
        try:
            return li.load_registry(self.root)
        except (OSError, ValueError) as e:
            raise LibraryUnavailable(f"no language library at {self.root}: {e}") from None

    def entry(self, shelf: str, text: str, version: str) -> dict | None:
        for e in self.registry().get("texts") or []:
            if (e.get("shelf"), e.get("text"), e.get("version")) == (shelf, text, version):
                return e
        return None

    def folder(self, entry: dict) -> Path:
        return li.text_dir(self.root, entry)

    def kept(self) -> list[dict]:
        """The registry's entries aboard (kept), whose folder is here."""
        return [e for e in self.registry().get("texts") or [] if e.get("aboard") and self.folder(e).is_dir()]

    def cited_names(self) -> dict[str, dict]:
        if self._cited is None:
            self._cited = {**catalogue_texts(), **self._cited_extra}
        return self._cited

    # ------------------------------------------------------------------ the index
    def _stamp(self) -> tuple:
        """What changes when the shelf changes: library.json's and each kept SHA256SUMS's size and mtime."""
        parts = []
        reg = self.root / li.REGISTRY
        for p in [reg] + sorted(self.root.glob("*/*/*/SHA256SUMS")):
            try:
                st = p.stat()
                parts.append((str(p), st.st_size, st.st_mtime_ns))
            except OSError:
                parts.append((str(p), None, None))
        return tuple(parts)

    def ensure(self) -> Path:
        """The index, built first when it is missing or stale. LibraryUnavailable when there is no shelf or it does
        not verify."""
        if not present(self.root):
            raise LibraryUnavailable(f"no language library at {self.root} (run scripts/sync_languages.py)")
        stamp = self._stamp()
        if self._checked == stamp and self.db.is_file():
            return self.db
        with self._lock:
            if not li.is_current(self.root, self.db):
                try:
                    li.build(self.root, self.db)
                except ValueError as e:
                    raise LibraryUnavailable(str(e)) from None
            self._checked = stamp
        return self.db

    def rebuild(self) -> dict:
        """Build the index again from the files alone, whatever it records. Returns the builder's counts."""
        with self._lock:
            try:
                counts = li.build(self.root, self.db)
            except ValueError as e:
                raise LibraryUnavailable(str(e)) from None
            self._checked = self._stamp()
        return counts

    def _connect(self) -> sqlite3.Connection:
        db = self.ensure()
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con

    # ------------------------------------------------------------------ naming a text
    def text_for(self, name: str, version: str) -> tuple[dict | None, str]:
        """The registry entry a `stated` names by `in` and `version`, and why not when it names none. The entry may
        be one not aboard (a pin, or a text not synced): the caller tells."""
        name, version = str(name or ""), str(version or "")
        reg = self.registry().get("texts") or []
        if "/" in name:
            shelf, _, text = name.partition("/")
        else:
            head = self.cited_names().get(name)
            if head is not None:
                shelf, text = str(head["shelf"]), str(head["text"])
                kept = str(head.get("version") or "")
                if kept and not _minor_of(version, kept):
                    return None, f"{name} {version} is not a patch of the {kept} the catalogue cites"
            else:
                shelf, text = name, ""
        cands = [e for e in reg if e.get("shelf") == shelf and (not text or e.get("text") == text)
                 and _minor_of(version, str(e.get("version")))]
        if not text:
            cands = [e for e in cands if e.get("what") in ("text", "standard")]
        if not cands:
            return None, f"{name} {version} is not in the language library's registry"
        cands.sort(key=lambda e: (not e.get("aboard"), -len(str(e.get("version")))))
        return cands[0], ""

    # ------------------------------------------------------------------ finding a section
    def find(self, stated: dict) -> Hit | None:
        """The section a citation names, or None. Raises nothing for a text that is not aboard: `cite` tells."""
        out = self._find(stated)
        return out if isinstance(out, Hit) else None

    def _find(self, stated: dict) -> Hit | str:
        try:
            entry, why = self.text_for(stated.get("in"), stated.get("version"))
        except LibraryUnavailable as e:
            return self._absent(stated, None) or f"not-aboard:{e}"
        if entry is None:
            return self._absent(stated, None) or f"unknown:{why}"
        key = f"{entry['shelf']}/{entry['text']}/{entry['version']}"
        if not entry.get("aboard") or not self.folder(entry).is_dir():
            got = self._absent(stated, entry)
            if got:
                return got
            if not entry.get("aboard") and not (self.fetcher is not None and (
                    self.fetcher.remote_entry(entry["shelf"], entry["text"], entry["version"]) or {}).get("aboard")):
                return f"not-aboard:{key} is pinned, not kept: it is not aboard the language library"
            return f"not-aboard:{key} is not aboard the language library here (run scripts/sync_languages.py)"
        try:
            con = self._connect()
        except LibraryUnavailable as e:
            return f"not-aboard:{e}"
        try:
            row = con.execute("SELECT id FROM texts WHERE shelf=? AND text=? AND version=?",
                              (entry["shelf"], entry["text"], entry["version"])).fetchone()
            if row is None:
                return f"not-aboard:{key} is not in the index"
            tid = row["id"]
            page, frag = split_at(stated.get("at") or "")
            files = [r["path"] for r in con.execute("SELECT path FROM files WHERE text_id=? AND page=?", (tid, page))]
            if not files:
                files = [r["path"] for r in con.execute("SELECT path FROM files WHERE text_id=? AND path=?",
                                                        (tid, f"{li.FILES}/{page}"))]
            sid, by = None, ""
            if files:
                f = files[0]
                if not frag:
                    r = con.execute("SELECT id FROM sections WHERE text_id=? AND file=? AND kind='file'",
                                    (tid, f)).fetchone()
                    sid, by = (r["id"], "page") if r else (None, "")
                else:
                    r = con.execute("SELECT section_id FROM anchors WHERE text_id=? AND file=? AND anchor=?",
                                    (tid, f, frag)).fetchone()
                    if r:
                        sid, by = r["section_id"], "anchor"
                    else:
                        sid = self._by_path(con, tid, f, frag)
                        by = "heading path" if sid else ""
                        if sid is None:
                            sid = self._by_publisher_id(con, tid, f, frag)
                            by = "publisher's id" if sid else ""
            sd = stated.get("section-digest")
            if sid is None and sd:
                r = con.execute("SELECT id FROM sections WHERE text_id=? AND sha256 LIKE ? ORDER BY id",
                                (tid, f"{_hex(sd)}%")).fetchone()
                if r:
                    sid, by = r["id"], "section digest"
            if sid is None and files:
                return (f"unplaced:{stated.get('in')} {stated.get('version')}: the page {page} is there, but no "
                        f"section of it is named {frag!r} (the kept build has no such id; cite a heading path or "
                        f"add a section-digest)")
            if sid is None:
                return f"missing:{stated.get('in')} {stated.get('version')} has no page {page} ({stated.get('at')})"
            return self._hit(con, sid, entry, by)
        finally:
            con.close()

    def _absent(self, stated: dict, entry: dict | None) -> str | None:
        """A text not here, with a fetcher: start its fetch (or the registry's first, when the name is not known
        here) and say `fetching:…`, or `not-aboard:…` when a fetch failed a moment ago (offline, refused). None when
        nothing can be fetched (no fetcher; the site's shelf does not keep it either)."""
        f = self.fetcher
        if f is None:
            return None

        def then() -> None:                     # after the registry: the text's own fetch, if it names one
            self._find(stated)
        if entry is None:
            got = f.demand_registry(then=then)
        else:
            got = f.demand(entry["shelf"], entry["text"], entry["version"], then=then)
        return f"{got[0]}:{got[1]}" if got else None

    def _waiting(self, ask, wait: float):
        """`ask()` again while it says `fetching` and the fetch runs, up to `wait` seconds."""
        out = ask()
        if wait <= 0 or self.fetcher is None:
            return out
        deadline = time.monotonic() + wait
        while isinstance(out, str) and out.startswith("fetching:"):
            left = deadline - time.monotonic()
            if left <= 0:
                break
            self.fetcher.wait(left)
            out = ask()
        return out

    def fetch_for(self, shelf: str, text: str, version: str, wait: float = 0.0) -> dict | None:
        """For a viewer asking for a kept text by name: None when it is here or nothing can be fetched; else `{state,
        why}` with state `fetching` or `not-aboard` (after waiting up to `wait` seconds for a fetch to end)."""
        f = self.fetcher
        if f is None:
            return None

        def ask():
            try:
                e = self.entry(shelf, text, version)
            except LibraryUnavailable:
                e = None
            if e is not None and e.get("aboard") and self.folder(e).is_dir():
                return None
            got = f.demand(shelf, text, version, then=lambda: f.demand(shelf, text, version))
            return f"{got[0]}:{got[1]}" if got else None
        out = self._waiting(ask, wait)
        if out is None:
            return None
        state, _, why = out.partition(":")
        return {"state": state, "why": why}

    @staticmethod
    def _by_path(con: sqlite3.Connection, tid: int, f: str, frag: str) -> int | None:
        want = [p.strip() for p in re.split(r"\s*>\s*", frag) if p.strip()]
        if not want:
            return None
        rows = con.execute("SELECT id, path FROM sections WHERE text_id=? AND file=? AND kind!='file' ORDER BY id",
                           (tid, f)).fetchall()
        for exact in (True, False):
            for r in rows:
                path = [str(x) for x in json.loads(r["path"])]
                if exact and path == want:
                    return r["id"]
                if not exact and len(path) >= len(want) and \
                        [li.slug(x) for x in path[-len(want):]] == [li.slug(x) for x in want]:
                    return r["id"]
        return None

    @staticmethod
    def _by_publisher_id(con: sqlite3.Connection, tid: int, f: str, frag: str) -> int | None:
        """A section named by the id the publisher's HTML build gives it, where the plain-text build's index names it
        otherwise: a title's id is its words without the section number (`yield-expressions` for "6.2.9. Yield
        expressions", `add-help` for "add_help"); a definition's id carries its module (`pathlib.Path.home` for
        `Path.home`, the longest such tail); `module-<name>` is the module's page, at its first title."""
        rows = con.execute("SELECT id, anchor, heading, kind FROM sections WHERE text_id=? AND file=? AND "
                           "kind!='file' ORDER BY id", (tid, f)).fetchall()
        want = _norm(frag)
        for r in rows:
            if r["kind"] == "heading" and _norm(_SEC_NUMBER.sub("", r["heading"] or "")) == want:
                return r["id"]
        tails = [r for r in rows if r["kind"] == "sig" and r["anchor"] and frag.endswith("." + r["anchor"])]
        if tails:
            return max(tails, key=lambda r: len(r["anchor"]))["id"]
        if frag.startswith("module-"):
            first = next((r for r in rows if r["kind"] == "heading"), None)
            if first is not None:
                return first["id"]
        return None

    def _hit(self, con: sqlite3.Connection, sid: int, entry: dict, by: str) -> Hit:
        s = con.execute("SELECT * FROM sections WHERE id=?", (sid,)).fetchone()
        f = con.execute("SELECT sha256 FROM files WHERE text_id=? AND path=?", (s["text_id"], s["file"])).fetchone()
        return Hit(entry["shelf"], entry["text"], entry["version"], s["text_id"], sid, s["file"], s["page"],
                   s["anchor"], s["heading"] or "", json.loads(s["path"]), s["kind"], s["level"], s["line_from"],
                   s["line_to"], f["sha256"] if f else "", s["sha256"], s["parent"], by, entry)

    def cite(self, stated: dict, wait: float = 0.0) -> dict:
        """What came of a citation: `{state, why, hit}`. `resolved` (the section is there and its digest, or its
        page's when no section digest is cited, agrees); `changed` (found, but the cited section digest differs, or
        the page differs and no section digest says whether the section did); `unplaced` (the page is there but no
        section of it carries the cited id: the kept build names it otherwise); `missing` (the text is aboard, the
        page is not); `not-aboard` (the text is not synced here, or only pinned); `unknown` (the registry has no
        such text); `fetching` (not here, being fetched from cosmoes.org now: ask again). With `wait`, a citation
        whose text is being fetched is asked again when the fetch ends, up to `wait` seconds."""
        out = self._waiting(lambda: self._find(stated), wait)
        if isinstance(out, str):
            state, _, why = out.partition(":")
            return {"state": state, "why": why, "hit": None}
        want_sec = stated.get("section-digest")
        want_page = stated.get("digest")
        if want_sec and not out.section_digest.startswith(_hex(want_sec)):
            return {"state": "changed", "hit": out,
                    "why": f"{stated.get('at')}: the section's digest is {out.section_digest[:12]}, not {want_sec}"}
        if want_page and not out.digest.startswith(_hex(want_page)):
            if want_sec:
                return {"state": "resolved", "hit": out,
                        "why": f"{stated.get('at')}: the page changed since it was cited; the section did not"}
            return {"state": "changed", "hit": out,
                    "why": f"{stated.get('at')}: the page's digest is {out.digest[:12]}, not {want_page}, and no "
                           f"section-digest says whether the cited section changed"}
        return {"state": "resolved", "why": "", "hit": out}

    # ------------------------------------------------------------------ a section for the viewer
    def text_info(self, entry: dict) -> dict:
        """What every view of a kept text shows with it: names, licence, copyright, the change of form, the NOTICE
        whole, FETCHED, and the line that this is a copy kept here."""
        folder = self.folder(entry)

        def _read(name: str) -> str | None:
            try:
                return (folder / name).read_text(encoding="utf-8")
            except OSError:
                return None
        lic = entry.get("licence") or {}
        form = entry.get("form")
        return {"shelf": entry.get("shelf"), "text": entry.get("text"), "version": entry.get("version"),
                "name": entry.get("name"), "publisher": entry.get("publisher"), "what": entry.get("what"),
                "form": form, "lane": entry.get("lane"), "aboard": bool(entry.get("aboard")),
                "here": bool(entry.get("aboard")) and folder.is_dir(),
                "licence": {"name": lic.get("name"), "url": lic.get("url")},
                "copyright": entry.get("copyright"), "publisher_page": entry.get("publisher_page"),
                "from": entry.get("from"), "obtained": entry.get("obtained"), "digest": entry.get("digest"),
                "address": entry.get("address") or (li.address(entry) if entry.get("aboard") else None),
                "changed": (li.FORMS.get(form) or {}).get("changed"), "copy": COPY_LINE,
                "notice": _read("NOTICE"), "fetched": _read("FETCHED")}

    def section(self, stated: dict, wait: float = 0.0) -> dict:
        """The route's payload for a citation: `{cited, state, why, text, section}`. `text` is the kept text's
        notice block (None when the registry has no such text); `section` is None unless the section was found."""
        c = self.cite(stated, wait=wait)
        hit: Hit | None = c["hit"]
        entry = hit.entry if hit else None
        if entry is None:
            try:
                entry, _ = self.text_for(stated.get("in"), stated.get("version"))
            except LibraryUnavailable:
                entry = None
        out = {"cited": {k: stated.get(k) for k in ("in", "version", "at", "digest", "section-digest")
                         if stated.get(k) is not None},
               "state": c["state"], "why": c["why"],
               "text": self.text_info(entry) if entry else None, "section": None}
        if hit is not None:
            out["section"] = self._section_payload(hit)
        return out

    def _section_payload(self, hit: Hit) -> dict:
        data = (self.folder(hit.entry) / hit.file).read_bytes()
        body = li.section_bytes(data, hit.line_from, hit.line_to).decode("utf-8", "replace")
        con = self._connect()
        try:
            parent = None
            if hit.parent is not None:
                p = con.execute("SELECT id, anchor, heading, kind FROM sections WHERE id=?", (hit.parent,)).fetchone()
                if p:
                    parent = {"id": _item_id(p["anchor"], p["id"], p["kind"]), "anchor": p["anchor"],
                              "heading": p["heading"]}
            kids = [{"id": _item_id(r["anchor"], r["id"], r["kind"]), "anchor": r["anchor"], "heading": r["heading"],
                     "kind": r["kind"]}
                    for r in con.execute("SELECT id, anchor, heading, kind FROM sections WHERE parent=? ORDER BY id",
                                         (hit.section_id,))]
        finally:
            con.close()
        return {"id": _item_id(hit.anchor, hit.section_id, hit.kind), "page": hit.page, "file": hit.file,
                "anchor": hit.anchor, "heading": hit.heading, "path": hit.path, "kind": hit.kind,
                "level": hit.level, "lines": [hit.line_from, hit.line_to], "sha256": hit.section_digest,
                "page_sha256": hit.digest, "found_by": hit.by, "at": hit.at(), "contents": volume_id(hit.entry),
                "volume": volume_id(hit.entry, hit.page) if hit.page else None, "body": body, "parent": parent, "parts": kids}

    # ------------------------------------------------------------------ DocOES
    def volume(self, shelf: str, text: str, version: str, page: str | None = None) -> dict:
        """A kept text as a DocOES catalog (`oes: doc/1`), built at runtime from the synced files and the index. With
        `page`, that page's sections, bodies verbatim (each section's own lines, so the bodies in order give the
        page back); without, the text's contents: one section per page, no bodies. The first node is always
        `S:section/notice`: the copy line, the licence, the copyright, the change of form and the NOTICE whole."""
        from . import macrocosm as mc
        entry = self.entry(shelf, text, version)
        if entry is None or not entry.get("aboard"):
            raise KeyError(f"{shelf}/{text}/{version} is not a kept text of the language library")
        if not self.folder(entry).is_dir():
            raise LibraryUnavailable(f"{shelf}/{text}/{version} is not aboard the language library here")
        info = self.text_info(entry)
        nodes = [self._notice_node(info)]
        con = self._connect()
        try:
            tid = con.execute("SELECT id FROM texts WHERE shelf=? AND text=? AND version=?",
                              (shelf, text, version)).fetchone()["id"]
            if page is None:
                order = 1
                for r in con.execute("SELECT f.page, f.path, f.sha256, s.heading, s.line_to FROM files f JOIN sections"
                                     " s ON s.text_id=f.text_id AND s.file=f.path AND s.kind='file' WHERE f.text_id=?"
                                     " AND f.page IS NOT NULL ORDER BY f.page", (tid,)):
                    order += 1
                    title = self._page_title(con, tid, r["path"]) or r["page"]
                    nodes.append({"id": f"S:section/{_slug_id('p-' + r['page'].replace('/', '.'))}",
                                  "type": "section", "name": title, "summary": f"The page {r['page']}.",
                                  "atem": f"The page {r['page']}", "level": 1, "order": order,
                                  "lines": f"1-{r['line_to']}", "page": r["page"], "file": r["path"],
                                  "sha256": r["sha256"], "cite": {"in": f"{shelf}/{text}", "version": version,
                                                                  "at": r["page"]},
                                  "provenance": _prov(r["path"], 1, r["line_to"], r["sha256"])})
            else:
                page = split_at(page)[0]
                frow = con.execute("SELECT path, sha256 FROM files WHERE text_id=? AND page=?", (tid, page)).fetchone()
                if frow is None:
                    raise KeyError(f"{shelf}/{text}/{version} has no page {page}")
                data = (self.folder(entry) / frow["path"]).read_bytes()
                raw = data.split(b"\n")
                rows = con.execute("SELECT * FROM sections WHERE text_id=? AND file=? ORDER BY id",
                                   (tid, frow["path"])).fetchall()
                ids: dict[int, str] = {}
                for r in rows:
                    iid = _item_id(r["anchor"], r["id"], r["kind"])
                    ids[r["id"]] = iid if iid not in ids.values() else f"S:section/s{r['id']}"
                kids: dict[int, list[str]] = {}
                for r in rows:
                    if r["parent"] is not None and r["parent"] in ids:
                        kids.setdefault(r["parent"], []).append(ids[r["id"]])
                for n, r in enumerate(rows):
                    # the section's own lines, up to the next section's start (the page's own: its lines before the
                    # first section), so the bodies in order are the publisher's file byte for byte
                    first = 1 if r["kind"] == "file" else r["line_from"]
                    last = rows[n + 1]["line_from"] - 1 if n + 1 < len(rows) else len(raw)
                    body = li.section_bytes(raw, first, last).decode("utf-8", "replace") if last >= first else ""
                    summary = _first_line(body, r["heading"] or page)
                    item = {"id": ids[r["id"]], "type": "section",
                            "name": r["heading"] or page if r["kind"] != "file" else (
                                self._page_title(con, tid, frow["path"]) or page),
                            "summary": summary, "atem": _atem(summary), "level": r["level"],
                            **({"parent": ids.get(r["parent"])} if r["parent"] in ids else {}),
                            **({"parts": kids[r["id"]]} if kids.get(r["id"]) else {}),
                            "order": n + 2, "lines": f"{r['line_from']}-{r['line_to']}",
                            **({"anchor": r["anchor"]} if r["anchor"] else {}),
                            "kind-of-section": r["kind"], "path": json.loads(r["path"]), "sha256": r["sha256"],
                            "cite": {"in": f"{shelf}/{text}", "version": version,
                                     "at": f"{page}#{r['anchor']}" if r["anchor"] else (
                                         page if r["kind"] == "file" else
                                         f"{page}#{PATH_SEP.join(json.loads(r['path']))}"),
                                     "digest": frow["sha256"][:12], "section-digest": r["sha256"][:12]},
                            "provenance": _prov(frow["path"], r["line_from"], r["line_to"], r["sha256"]),
                            "body": body}
                    nodes.append(item)
        finally:
            con.close()
        name = f"{entry.get('name')} {version}" + (f", {page}" if page else "")
        return {"oes": "doc/1", "macrocosm": mc.MACROCOSM_VERSION, "id": volume_id(entry, page), "name": name,
                "document": {"path": info["address"], "sha256": entry.get("digest"), "version": version,
                             "source": "library", "home": entry.get("publisher_page"),
                             "publisher": entry.get("publisher"), "licence": dict(info["licence"]),
                             "copyright": entry.get("copyright"), "changed": info["changed"], "copy": COPY_LINE,
                             **({"page": page} if page else {})},
                "telling": {"lang": "en"}, "nodes": nodes}

    @staticmethod
    def _page_title(con: sqlite3.Connection, tid: int, path: str) -> str | None:
        r = con.execute("SELECT heading FROM sections WHERE text_id=? AND file=? AND kind='heading' ORDER BY id "
                        "LIMIT 1", (tid, path)).fetchone()
        return r["heading"] if r else None

    @staticmethod
    def _notice_node(info: dict) -> dict:
        lic = info["licence"]
        body = "\n\n".join(x for x in (
            info["copy"],
            f"Licence: {lic.get('name')} ({lic.get('url')})" if lic.get("name") else None,
            f"Copyright, as the publisher states it:\n{info['copyright']}" if info.get("copyright") else None,
            f"Changed in form: {info['changed']}" if info.get("changed") else None,
            f"The publisher's own page: {info['publisher_page']}" if info.get("publisher_page") else None,
            info.get("notice")) if x) + "\n"
        return {"id": "S:section/notice", "type": "section", "name": "Notice",
                "summary": COPY_LINE, "atem": "A copy kept here, not the publisher's page", "level": 1, "order": 1,
                "licence": dict(lic), "copyright": info.get("copyright"), "changed": info.get("changed"),
                "provenance": {"mode": "catalogue", "sources": ["NOTICE"], "confidence": 1, "state": "known"},
                "body": body}

    def status(self) -> dict:
        """The shelf at a glance: where it is, whether its index is current, and every text with `here`."""
        out: dict[str, Any] = {"source": str(self.root), "index": str(self.db), "present": present(self.root)}
        if not out["present"]:
            out.update(current=False, texts=[])
            return out
        try:
            reg = self.registry()
        except LibraryUnavailable as e:
            out.update(current=False, texts=[], error=str(e))
            return out
        out["current"] = li.is_current(self.root, self.db)
        out["problems"] = li.validate_registry(reg)
        out["texts"] = [{"shelf": e.get("shelf"), "text": e.get("text"), "version": e.get("version"),
                         "name": e.get("name"), "what": e.get("what"), "aboard": bool(e.get("aboard")),
                         "here": bool(e.get("aboard")) and self.folder(e).is_dir(),
                         "volume": volume_id(e) if e.get("aboard") else None}
                        for e in reg.get("texts") or []]
        return out


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_SEC_NUMBER = re.compile(r"^\s*(?:\d+\.)*\d+\.?\s+")


def _norm(text: str) -> str:
    """A title or an id compared as the HTML build writes ids: slugged, underscores as hyphens."""
    return re.sub(r"-+", "-", li.slug(text).replace("_", "-")).strip("-")


_SLUG_OK = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._@-]*[A-Za-z0-9_@-])?$")


def _slug_id(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._@-]+", "-", str(s)).strip("-.")
    return s if _SLUG_OK.match(s or "") else "x"


def _item_id(anchor: str | None, sid: int, kind: str) -> str:
    """A section's item id in its page's volume: its anchor when that is a valid slug (`S:section/str.splitlines`),
    `root` for the whole page, else `s<index id>`."""
    if kind == "file":
        return "S:section/root"
    if anchor and _SLUG_OK.match(anchor) and anchor not in ("root", "notice") and not anchor.startswith("p-"):
        return f"S:section/{anchor}"
    return f"S:section/s{sid}"


def volume_id(entry: dict, page: str | None = None) -> str:
    base = f"doc/library-{entry['shelf']}-{entry['text']}-{_slug_id(entry['version'])}"
    return base + (f"-{_slug_id(page.replace('/', '.'))}" if page else "")


def _hex(d: Any) -> str:
    return str(d).removeprefix("sha256:").lower()


def _prov(path: str, a: int, b: int, sha: str) -> dict:
    return {"mode": "derived", "sources": [f"{path}#L{a}-L{b}"], "confidence": 1, "state": "known",
            "hash": f"sha256:{sha}"}


def _first_line(body: str, fallback: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if s and not re.fullmatch(r"([=\-~^\"#*+`':.<>_])\1{2,}", s):
            return s[:200]
    return str(fallback)


def _atem(summary: str) -> str:
    words = summary.split()
    return " ".join(words[:15]).rstrip(".:;,") or "A section"
