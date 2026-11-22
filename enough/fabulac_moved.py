"""The moved-parts rule: which part fabulacs a source tree has moved under (0.9: pins section 6; tracker
`enough-fabulac` step 7, "keeping in step").

A part's fabulac records the files it was made from: each `C:file` item has the file's `path` (relative to the root
of the program, `enough/macrocosm.py`) and its `sha256`, and the catalog's `source.tree` is the tree digest over them
(MacroCOSM 18.4.1, `macrocosm.tree_digest`). Given a set of fabulacs (files, or folders of `*.fabulac.cosm`; heads
and their parts) and a source tree (a checkout, read as it is on disk, or at a git ref such as a release tag),
`moved_parts` says of each part:

- **unmoved** when every file it records is in the tree with the same sha256, and no file was added to a folder it
  holds alone; else **moved**, with the files `changed` (there, different), `vanished` (not there) and `added`.
- **added** files: a folder is held by the set when the set tells that folder's `__init__.py` (a Python package the
  set tells, such as `enough/thym/`). A file in a held folder (not below it) that no fabulac of the set records is
  told by no part. When only one part has files in that folder it is that part's; when several have, it is listed
  once for the set, with the parts that share the folder. Given a `base` (the ref the set was made from), such a file
  is `added` when the base did not have it and `untold` when it did (it was never told); with no base it is
  `unclaimed`, and only `added` moves a part.
- **its questions and rulings**, how many still resolve, by 0.6's carry-over rule (MacroCOSM 18.6.3; an item carries
  while what it is about still resolves; `dialectic.carry_over`, `transconception.carry_over`): every item of an
  unmoved file resolves; an item of a vanished file does not; an item of a changed file resolves while the name it is
  about is still defined there (an id `C:interface/enough.macrocosm.Registry.identify` names the module
  `enough.macrocosm` and `Registry.identify` in it, read by `ast`), else, for an item that is `of` others (a
  behaviour) or `used-by` others (a reliance), while one of those resolves, else while its span's lines are within
  the file (0.6's `stale_reasons` rule for a span). A `C:file` resolves while its file is there. An item tied to no
  file resolves. A question resolves while the item its `about` names resolves. A head's items are read the same way
  against the files its parts record.

For a head (a catalog with `parts`), each part's own fabulac file is also checked against the sha256 the head
recorded for it (`fabulac`: in step or moved; `fabulac_head.which_moved`), and the head is moved when one of its parts
is, or when a file was `added` to a folder its parts share; when some of its parts were not given and none of those
given moved, it is `not judged`.

By rule only: no model is asked, nothing in the tree is imported or run (Python files are parsed with `ast`, as
text), and with a ref the files are read through `git ls-tree` and `git cat-file`, never checked out. Nothing is
written. `table(report)` is the report for a person; the report itself is plain data for a machine (`--json`).

    python -m enough.fabulac moved-parts docs/v080-g3 --tree . --ref v0.8.0 --base 450e4cc
"""
from __future__ import annotations

import ast
import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from . import macrocosm as mc
from .fabulac_head import FABULAC_SUFFIX, which_moved

#: Item kinds whose id names a Python definition (`<module>.<qualified name>`).
NAMED_KINDS = ("interface", "structure", "setting", "component")
#: An id the head writes for a name another program provides (`outside.enough.macrocosm.Volume`).
OUTSIDE = "outside."


class MovedError(ValueError):
    """The rule was refused: a fabulac that does not read, a tree or ref that is not there."""


# ---------------------------------------------------------------------------
# The tree: a checkout as it is on disk, or a git ref read without a checkout
# ---------------------------------------------------------------------------

class Tree:
    """Files of a source tree by relative posix path: `sha256(path)`, `text(path)`, `folder(path)` (the names of the
    regular files directly in a folder, by the tree digest's skip rules)."""

    def __init__(self, root: Path, ref: str | None = None) -> None:
        self.root = Path(root)
        self.ref = ref
        self.commit: str | None = None
        self._blobs: dict[str, str] = {}
        self._cache: dict[str, bytes | None] = {}
        if not self.root.is_dir():
            raise MovedError(f"there is no folder {self.root}")
        if ref is not None:
            self.commit = self._git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").decode().strip()
            if not self.commit:
                raise MovedError(f"{ref} is not a commit of {self.root}")
            out = self._git("ls-tree", "-r", "-z", self.commit)
            for rec in out.split(b"\0"):
                if not rec:
                    continue
                meta, _, path = rec.partition(b"\t")
                mode, kind, blob = meta.decode().split()
                if kind == "blob" and mode in ("100644", "100755"):     # symbolic links and submodules are not read
                    self._blobs[path.decode("utf-8", "surrogateescape")] = blob

    def _git(self, *args: str) -> bytes:
        try:
            r = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, check=False)
        except OSError as e:
            raise MovedError(f"git could not be started: {e}") from e
        if r.returncode != 0 and args[0] != "rev-parse":
            raise MovedError(f"git {args[0]} failed in {self.root}: {r.stderr.decode(errors='replace').strip()}")
        return r.stdout

    def data(self, path: str) -> bytes | None:
        if path in self._cache:
            return self._cache[path]
        got: bytes | None = None
        if self.ref is not None:
            blob = self._blobs.get(path)
            if blob is not None:
                got = self._git("cat-file", "blob", blob)
        else:
            p = self.root / path
            if p.is_file() and not p.is_symlink():
                got = p.read_bytes()
        self._cache[path] = got
        return got

    def sha256(self, path: str) -> str | None:
        d = self.data(path)
        return hashlib.sha256(d).hexdigest() if d is not None else None

    def text(self, path: str) -> str | None:
        d = self.data(path)
        if d is None:
            return None
        try:
            return d.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def folder(self, folder: str) -> list[str]:
        """The posix paths of the files directly in `folder` (not below it)."""
        def kept(name: str) -> bool:
            return not (name in mc.TREE_SKIP_FILES or name.endswith(mc.TREE_SKIP_FILE_SUFFIXES)
                        or name.endswith(FABULAC_SUFFIX))
        pre = f"{folder}/" if folder else ""
        if self.ref is not None:
            return sorted(p for p in self._blobs if p.startswith(pre) and "/" not in p[len(pre):]
                          and kept(p[len(pre):]))
        d = self.root / folder
        if not d.is_dir():
            return []
        return sorted(f"{pre}{c.name}" for c in d.iterdir() if c.is_file() and not c.is_symlink() and kept(c.name))

    def where(self) -> dict:
        return {"root": str(self.root), "ref": self.ref, "commit": self.commit}


def tree_of(entries: Iterable[tuple[str, str]]) -> str:
    """The tree digest (`macrocosm.tree_digest`'s sum) over (relative path, sha256) pairs."""
    h = hashlib.sha256()
    for rel, digest in sorted(entries, key=lambda e: e[0].encode("utf-8")):
        h.update(rel.encode("utf-8") + b"\0" + digest.encode("ascii") + b"\n")
    return h.hexdigest()


# ---------------------------------------------------------------------------
# The set of fabulacs
# ---------------------------------------------------------------------------

@dataclass
class Fab:
    path: Path
    doc: dict
    uri: str
    head: str | None = None
    parts: list = field(default_factory=list)
    nodes: list = field(default_factory=list)

    @property
    def is_head(self) -> bool:
        return bool(self.parts)

    def files(self) -> dict[str, str | None]:
        out: dict[str, str | None] = {}
        for n in self.nodes:
            if n.get("type") == "file" and isinstance(n.get("path"), str):
                sha = n.get("sha256")
                out[n["path"]] = sha if isinstance(sha, str) else None
        return out


def _uri(doc: dict) -> str | None:
    i = doc.get("id")
    return f"oes:{i}" if isinstance(i, str) and i else None


def load_set(paths: Iterable[Path | str]) -> tuple[list[Fab], list[str]]:
    """The fabulacs named (files, or folders read at their top level for `*.fabulac.cosm`), each once by its catalog
    id: a later one of the same id replaces an earlier one (named in the notes)."""
    found: dict[str, Fab] = {}
    notes: list[str] = []
    files: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files += sorted(c for c in p.iterdir() if c.name.endswith(FABULAC_SUFFIX) and c.is_file())
        elif p.is_file():
            files.append(p)
        else:
            raise MovedError(f"there is no {p}")
    for f in files:
        try:
            doc = mc.yaml_load(mc.read_text(f))
        except Exception as e:  # noqa: BLE001 - YAML errors and unreadable files alike
            raise MovedError(f"{f} does not read as a fabulac: {e}") from e
        if not isinstance(doc, dict) or not _uri(doc):
            raise MovedError(f"{f} does not read as a fabulac (no catalog id)")
        uri = _uri(doc)
        if uri in found:
            notes.append(f"{uri}: {found[uri].path} replaced by {f}")
        nodes = [n for n in (doc.get("nodes") or []) if isinstance(n, dict)]
        parts = [p for p in (doc.get("parts") or []) if isinstance(p, dict) and isinstance(p.get("uri"), str)]
        head = doc.get("head") if isinstance(doc.get("head"), str) else None
        found[uri] = Fab(path=f, doc=doc, uri=uri, head=head, parts=parts, nodes=nodes)
    return list(found.values()), notes


# ---------------------------------------------------------------------------
# Whether an item still resolves (0.6's carry-over rule, read against the tree)
# ---------------------------------------------------------------------------

def _defined(text: str) -> set[str] | None:
    """The qualified names a module defines at its top level and in its classes (`f`, `C`, `C.m`, `C.D.x`, `X`), by
    `ast`; None when it does not parse."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    out: set[str] = set()

    def targets(t: ast.AST) -> Iterable[str]:
        if isinstance(t, ast.Name):
            yield t.id
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                yield from targets(e)

    def walk(body: list, pre: str) -> None:
        for s in body:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.add(pre + s.name)
            elif isinstance(s, ast.ClassDef):
                out.add(pre + s.name)
                walk(s.body, f"{pre}{s.name}.")
            elif isinstance(s, ast.Assign):
                for t in s.targets:
                    out.update(pre + n for n in targets(t))
            elif isinstance(s, (ast.AnnAssign, ast.AugAssign)):
                out.update(pre + n for n in targets(s.target))
            elif isinstance(s, (ast.If, ast.Try, ast.With)) or type(s).__name__ == "TryStar":
                for blk in ("body", "orelse", "finalbody"):
                    walk(getattr(s, blk, []) or [], pre)
                for h in getattr(s, "handlers", []) or []:
                    walk(h.body, pre)
            elif isinstance(s, (ast.Import, ast.ImportFrom)):
                for a in s.names:
                    if a.name != "*":
                        out.add(pre + (a.asname or a.name).split(".")[0])
    walk(tree.body, "")
    return out


def _span_lines(text: str) -> tuple[int, int] | None:
    import re
    m = re.match(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*$", str(text))
    if not m:
        return None
    a = int(m.group(1))
    return a, int(m.group(2) or a)


class Resolver:
    """Whether an item of a fabulac still resolves in the tree, given the files the set records (`state`: path to
    in-step, moved or gone)."""

    def __init__(self, tree: Tree, state: Mapping[str, str]) -> None:
        self.tree = tree
        self.state = dict(state)
        self._defs: dict[str, set[str] | None] = {}
        self._modules: dict[str, str] = {}
        for p in self.state:
            pp = PurePosixPath(p)
            if pp.suffix == ".py":
                parts = list(pp.with_suffix("").parts)
                if parts and parts[-1] == "__init__":
                    parts = parts[:-1]
                if parts:
                    self._modules[".".join(parts)] = p

    def defs(self, path: str) -> set[str] | None:
        if path not in self._defs:
            t = self.tree.text(path)
            self._defs[path] = _defined(t) if t is not None else None
        return self._defs[path]

    def named(self, item: Mapping[str, Any]) -> tuple[str, str] | None:
        """(file, qualified name) an item's id names: the longest module prefix the set records, and the rest."""
        iid = str(item.get("id") or "")
        kind, _, rest = iid.partition("/")
        if kind.split(":")[-1] not in NAMED_KINDS or not rest:
            return None
        if rest.startswith(OUTSIDE):
            rest = rest[len(OUTSIDE):]
        bits = rest.split(".")
        for i in range(len(bits), 0, -1):
            mod = ".".join(bits[:i])
            if mod in self._modules:
                return self._modules[mod], ".".join(bits[i:])
        return None

    def file_of(self, item: Mapping[str, Any], by_id: Mapping[str, Mapping]) -> str | None:
        sp = item.get("span")
        if isinstance(sp, dict) and isinstance(sp.get("file"), str):
            return sp["file"]
        if item.get("type") == "file" and isinstance(item.get("path"), str):
            return item["path"]
        d = item.get("defined-in")
        if isinstance(d, str) and d in by_id:
            f = by_id[d]
            return f.get("path") if isinstance(f.get("path"), str) else None
        n = self.named(item)
        return n[0] if n else None

    def resolves(self, item: Mapping[str, Any], by_id: Mapping[str, Mapping], seen: set | None = None) -> bool:
        seen = set() if seen is None else seen
        iid = str(item.get("id") or "")
        if iid in seen:
            return True
        seen.add(iid)
        path = self.file_of(item, by_id)
        if path is None:
            return True                                   # tied to no file
        st = self.state.get(path)
        if st is None:
            st = "in-step" if self.tree.sha256(path) is not None else "gone"
        if st == "in-step":
            return True
        if st == "gone":
            return False
        if item.get("type") == "file":
            return True
        named = self.named(item)
        if named is not None and named[0] == path:
            defs = self.defs(path)
            if defs is not None and (not named[1] or named[1] in defs):
                return True
            if item.get("type") == "interface":
                return False
        for fld in ("of", "used-by"):
            refs = item.get(fld)
            refs = [refs] if isinstance(refs, str) else refs
            refs = [r for r in (refs or []) if isinstance(r, str) and r in by_id]
            if fld == "of":
                refs = [r for r in refs if self.file_of(by_id[r], by_id) is not None]
            if refs:
                return any(self.resolves(by_id[r], by_id, seen) for r in refs)
        sp = item.get("span") if isinstance(item.get("span"), dict) else {}
        rng = _span_lines(sp.get("lines")) if sp.get("lines") is not None else None
        if rng is None:
            return named is None                          # named, and the name is gone
        text = self.tree.text(path)
        return text is not None and rng[1] <= len(text.splitlines())

    def about(self, q: Mapping[str, Any], by_id: Mapping[str, Mapping]) -> bool:
        ab = q.get("about")
        if isinstance(ab, dict):
            return self.resolves({"id": str(q.get("id")), "span": ab}, by_id)
        if not isinstance(ab, str):
            return True
        target = ab.split("#", 1)[0]
        if target in by_id:
            return self.resolves(by_id[target], by_id)
        return True                                       # the whole, or an item outside this fabulac


def standing(fab: Fab, res: Resolver, *, moved: bool) -> dict:
    """`{rulings: {total, resolve, gone}, questions: {total, resolve, gone}}` for one fabulac: the items with a
    `ruling`, and the `D:question` items."""
    by_id = {str(n.get("id")): n for n in fab.nodes}
    ruled = [n for n in fab.nodes if n.get("ruling")]
    questions = [n for n in fab.nodes if n.get("type") == "question"]
    if not moved:
        gone_r, gone_q = [], []
    else:
        gone_r = [str(n["id"]) for n in ruled if not res.resolves(n, by_id)]
        gone_q = [str(n["id"]) for n in questions if not res.about(n, by_id)]
    return {"rulings": {"total": len(ruled), "resolve": len(ruled) - len(gone_r), "gone": gone_r},
            "questions": {"total": len(questions), "resolve": len(questions) - len(gone_q), "gone": gone_q}}


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------

def moved_parts(fabulacs: Iterable[Path | str], tree: Path | str, *, ref: str | None = None,
                base: str | None = None) -> dict:
    """The moved-parts rule (see the module's text). `fabulacs`: files or folders; `tree`: a checkout; `ref`: read
    the tree at this git ref instead of as it is on disk; `base`: the ref the set was made from, to tell a file
    added since from one never told. Returns `{tree, base, parts: [...], heads: [...], unclaimed: [...], moved: [uri],
    notes}`; raises MovedError when it cannot be run."""
    fabs, notes = load_set(fabulacs)
    if not fabs:
        raise MovedError("no fabulac was given")
    t = Tree(Path(tree), ref)
    b = Tree(Path(tree), base) if base is not None else None
    by_uri = {f.uri: f for f in fabs}
    parts = [f for f in fabs if not f.is_head]
    heads = [f for f in fabs if f.is_head]

    recorded: dict[str, str | None] = {}
    owner: dict[str, list[str]] = {}
    for f in parts:
        for p, sha in f.files().items():
            recorded.setdefault(p, sha)
            owner.setdefault(p, []).append(f.uri)
    now = {p: t.sha256(p) for p in recorded}
    states = which_moved(recorded, now)
    state = {p: s for s, ps in states.items() for p in ps}
    res = Resolver(t, state)

    # Folders the set holds: a package whose __init__.py the set tells.
    def parent(p: str) -> str:
        s = str(PurePosixPath(p).parent)
        return "" if s == "." else s

    held: dict[str, list[str]] = {}
    for p in recorded:
        if PurePosixPath(p).name == "__init__.py":
            folder = parent(p)
            held[folder] = sorted({u for q, us in owner.items() if parent(q) == folder for u in us})
    unclaimed, part_added = [], {}
    for folder, sharers in sorted(held.items()):
        rows = []
        for p in t.folder(folder):
            if p in recorded:
                continue
            since = None if b is None else ("untold" if b.sha256(p) is not None else "added")
            rows.append({"path": p, "state": since or "unclaimed"})
        if not rows:
            continue
        if len(sharers) == 1:
            part_added.setdefault(sharers[0], []).extend(rows)
        else:
            unclaimed.append({"folder": folder, "parts": sharers, "files": rows})

    out_parts = []
    for f in parts:
        files = f.files()
        changed = [p for p in files if state.get(p) == "moved"]
        vanished = [p for p in files if state.get(p) == "gone"]
        unread = [p for p in files if state.get(p) == "unread"]
        mine = part_added.get(f.uri, [])
        added = [r["path"] for r in mine if r["state"] == "added"]
        is_moved = bool(changed or vanished or added)
        src = f.doc.get("source") if isinstance(f.doc.get("source"), dict) else {}
        rec_tree = src.get("tree") if isinstance(src.get("tree"), str) else None
        from_record = tree_of((p, s) for p, s in files.items() if s) if all(files.values()) and files else None
        now_tree = tree_of((p, now[p]) for p in files) if files and all(now.get(p) for p in files) else None
        out_parts.append({
            "uri": f.uri, "fabulac": str(f.path), "head": f.head,
            "state": "moved" if is_moved else "unmoved",
            "files": {"total": len(files), "in-step": len(files) - len(changed) - len(vanished) - len(unread),
                      "changed": changed, "vanished": vanished, "unread": unread},
            "added": added, "untold": [r["path"] for r in mine if r["state"] in ("untold", "unclaimed")],
            "tree": {"recorded": rec_tree, "from-files": from_record, "now": now_tree,
                     "consistent": rec_tree is not None and rec_tree == from_record},
            **standing(f, res, moved=is_moved),
        })
    moved_uris = {r["uri"] for r in out_parts if r["state"] == "moved"}

    out_heads = []
    for h in heads:
        rows = []
        for p in h.parts:
            uri = p["uri"]
            part = by_uri.get(uri)
            cand = h.path.parent / str(p.get("path") or "")
            fpath = part.path if part is not None else (cand if cand.is_file() else None)
            sha_now = hashlib.sha256(fpath.read_bytes()).hexdigest() if fpath is not None else None
            fstate = which_moved({uri: p.get("sha256") if isinstance(p.get("sha256"), str) else None},
                                 {uri: sha_now})
            rows.append({"uri": uri, "given": part is not None,
                         "state": "moved" if uri in moved_uris else ("unmoved" if part is not None else "not given"),
                         "fabulac": next(s for s, names in fstate.items() if names)})
        mine = {r["uri"] for r in rows}
        shared_added = [r["path"] for u in unclaimed if set(u["parts"]) & mine
                        for r in u["files"] if r["state"] == "added"]
        is_moved = any(r["state"] == "moved" for r in rows) or bool(shared_added)
        hstate = "moved" if is_moved else ("not judged" if any(not r["given"] for r in rows) else "unmoved")
        out_heads.append({"uri": h.uri, "fabulac": str(h.path), "state": hstate,
                          "parts": rows, "added": shared_added, **standing(h, res, moved=is_moved)})
        if is_moved:
            moved_uris.add(h.uri)

    return {"tree": t.where(), "base": b.where() if b is not None else None,
            "parts": out_parts, "heads": out_heads, "unclaimed": unclaimed,
            "moved": sorted(moved_uris), "notes": notes}


def _short(uri: str) -> str:
    return uri[len("oes:fabula/"):] if uri.startswith("oes:fabula/") else uri


def table(report: Mapping[str, Any]) -> str:
    """The report for a person: one row per part and head, then what moved, file by file."""
    t = report["tree"]
    where = f"{t['root']} at {t['ref']} ({t['commit'][:12]})" if t.get("ref") else f"{t['root']} as it is on disk"
    lines = [f"Parts against {where}" + (f", base {report['base']['ref']}" if report.get("base") else "") + ":", ""]
    head = ("part", "state", "files", "changed", "vanished", "added", "rulings resolve", "questions resolve")
    rows = [head]
    for r in report["parts"]:
        f = r["files"]
        rows.append((_short(r["uri"]), r["state"], str(f["total"]), str(len(f["changed"])), str(len(f["vanished"])),
                     str(len(r["added"])), f"{r['rulings']['resolve']}/{r['rulings']['total']}",
                     f"{r['questions']['resolve']}/{r['questions']['total']}"))
    for h in report["heads"]:
        rows.append((_short(h["uri"]) + " (head)", h["state"], f"{len(h['parts'])} parts", "", "",
                     str(len(h["added"])), f"{h['rulings']['resolve']}/{h['rulings']['total']}",
                     f"{h['questions']['resolve']}/{h['questions']['total']}"))
    widths = [max(len(row[i]) for row in rows) for i in range(len(head))]
    for i, row in enumerate(rows):
        lines.append("  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip())
        if i == 0:
            lines.append("  ".join("-" * w for w in widths))
    detail = []
    for r in report["parts"]:
        if not r["tree"]["consistent"]:
            detail.append(f"{_short(r['uri'])}: its source.tree is not the digest of the files it records")
        if r["state"] != "moved":
            continue
        detail.append(f"{_short(r['uri'])} moved:")
        detail += [f"  changed   {p}" for p in r["files"]["changed"]]
        detail += [f"  vanished  {p}" for p in r["files"]["vanished"]]
        detail += [f"  added     {p}" for p in r["added"]]
        for what in ("rulings", "questions"):
            gone = r[what]["gone"]
            if gone:
                detail.append(f"  {len(gone)} {what} no longer resolve: " + ", ".join(gone[:8])
                              + (f" and {len(gone) - 8} more" if len(gone) > 8 else ""))
    for h in report["heads"]:
        for p in h["parts"]:
            if p["state"] == "not given":
                detail.append(f"{_short(h['uri'])}: its part {_short(p['uri'])} was not given")
            elif p["fabulac"] not in ("in-step", "unread"):
                detail.append(f"{_short(h['uri'])}: the fabulac of {_short(p['uri'])} is {p['fabulac']} since the "
                              "head recorded its sha256")
        for what in ("rulings", "questions"):
            gone = h[what]["gone"]
            if gone:
                detail.append(f"{_short(h['uri'])}: {len(gone)} {what} no longer resolve: " + ", ".join(gone[:8])
                              + (f" and {len(gone) - 8} more" if len(gone) > 8 else ""))
    for u in report["unclaimed"]:
        detail.append(f"{u['folder']}/ (shared by {', '.join(_short(x) for x in u['parts'])}) holds files no part "
                      "tells:")
        detail += [f"  {r['state']:<9} {r['path']}" for r in u["files"]]
    for r in report["parts"]:
        if r["untold"]:
            detail.append(f"{_short(r['uri'])}: its folder holds files it never told: " + ", ".join(r["untold"]))
    detail += [f"note: {n}" for n in report.get("notes") or []]
    lines += [""] + (detail or ["Nothing moved."])
    lines += ["", "moved: " + (", ".join(_short(u) for u in report["moved"]) if report["moved"] else "none")]
    return "\n".join(lines)


__all__ = ["MovedError", "Tree", "Resolver", "load_set", "moved_parts", "table", "tree_of"]
