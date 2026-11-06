"""Folders: a directory tree read under one fixed rule, with its tree digest (THYM 20.1 to 20.4; MacroCOSM OES 18.4.1).

A **folder** is the list of the files its rule keeps, each `{path, sha256, size, binary}`, `path` relative to the
folder, written with forward slashes and without a leading `./`, in the order of the paths' UTF-8 bytes. The rule
(THYM 20.1) has no options: every regular file under the root, except a path one of whose parts begins with `.`, a
path one of whose parts is `__pycache__` or `node_modules`, and symbolic links, which are never followed (each link is
left out and counted in `links`). A file is **text** when its bytes are UTF-8 (a byte-order mark is tolerated), hold no
zero byte and number at most 1,000,000; any other file is binary: in the folder and counted, never read as text. No
ignore file is read, and nothing in a folder is ever executed or imported.

The **tree digest** is MacroCOSM's (its 18.4.1, "Fresh and stale, for a folder"), byte for byte the reference code's
(`tree_digest`): over the files *that* rule reads, ascending by the UTF-8 bytes of their paths, the sha256 of the
concatenation of `<path> NUL <sha256 hex> LF`. The two rules differ (MacroCOSM's skips folders such as `build` and
`venv` that Thym's keeps, and reads dotfiles such as `.github/…` that Thym's leaves out, and it leaves binary files
out), so each file the folder keeps says whether it is among the digest's (`Entry.tree`). A folder read from disk
carries the reference digest exactly; a folder made from one (`where`, `folders`) carries the digest of its own files
that are among the digest's.

What a program reads on a folder (THYM 20.1): `path`, `name`, `files`, `bytes`, `lines`, `tree`, `commit`, `origin`
(`Folder.field`); on each of its files (`member_fields`): `path`, `name`, `suffix`, `depth`, `size`, `sha256`,
`binary`, `lines`. `for each` walks the text files in path order; `where` keeps the files whose fields satisfy a
condition and gives a folder (`Folder.where`); `folders of` gives the folders directly below (`Folder.folders`).
`commit` and `origin` are read from the clone's own files (`.git/HEAD`, its ref or `packed-refs`, `.git/config`): no
`git` is run.

A run **snapshots** every folder it takes (THYM 20.3): `snapshot_text` writes the `thym/1` volume of kind `folder`
that lists every file with its digest and holds the text of each text file as a block scalar, written here by hand so
that this module needs only the standard library; `from_snapshot` reads the mapping back (the caller parses the YAML)
and checks every text against its digest. `write_tree` writes a folder's files into a directory, for landing a folder
output (THYM 20.4).

Standard library only (os, pathlib, hashlib), so that it vendors as it stands. No floats; nothing a JavaScript runtime
could not do the same way (THYM 12.6).
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

#: A text file holds at most this many bytes (THYM 20.1); MacroCOSM's digest reads no larger file either.
MAX_TEXT = 1_000_000
#: Thym's rule: parts that leave a path out wherever they stand (beside any part that begins with `.`).
SKIP_PARTS = ("__pycache__", "node_modules")

# MacroCOSM's rule for the tree digest (its 18.4.1), as the reference code (tree_digest.py) writes it.
TREE_SKIP_DIRS = frozenset((".git", ".hg", ".svn", ".bzr", "_darcs", "CVS",
                            ".venv", "venv", "__pypackages__", ".tox", ".nox", "node_modules",
                            "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis",
                            ".ipynb_checkpoints", ".cache", "htmlcov", "build", "dist", ".eggs"))
TREE_SKIP_DIR_SUFFIXES = (".egg-info",)
TREE_SKIP_FILES = frozenset((".DS_Store", "Thumbs.db", "desktop.ini", ".coverage"))
TREE_SKIP_FILE_SUFFIXES = (".pyc", ".pyo", ".so", ".pyd", ".dylib", ".dll", ".o", ".a", ".class")
TREE_SNIFF = 8192

#: The fields a program reads on a folder, with their types (THYM 20.1); `commit` and `origin` may be nothing.
FOLDER_FIELDS = {"path": "string", "name": "string", "files": "number", "bytes": "number", "lines": "number",
                 "tree": "string", "commit": "string", "origin": "string"}
#: The fields of a file of a folder (a text walked from it, or any file a `where` reads).
MEMBER_FIELDS = {"path": "string", "name": "string", "suffix": "string", "depth": "number", "size": "number",
                 "sha256": "string", "binary": "bool", "lines": "number"}


class FolderError(ValueError):
    """A folder that cannot be read, a snapshot that does not hold what it says, or a tree that cannot be written."""


# ---------------------------------------------------------------------------
# Files and folders
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Entry:
    """One file a folder keeps: its path (POSIX, relative to the folder), the sha256 of its bytes, its size, whether
    it is binary, and whether it is among the files the tree digest is over (`tree`)."""
    path: str
    sha256: str
    size: int
    binary: bool = False
    tree: bool = True

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def suffix(self) -> str:
        """The part of the name after its last `.`, without the dot; `""` for none (THYM 20.1)."""
        n = self.name
        return n.rsplit(".", 1)[1] if "." in n else ""

    @property
    def depth(self) -> int:
        """How many folders stand above it inside the folder walked (0 at the top)."""
        return self.path.count("/")


def path_key(path: str) -> bytes:
    """The order of a folder's files: ascending by the UTF-8 bytes of their paths."""
    return path.encode("utf-8")


def lines_in(text: str) -> int:
    """How many lines a text holds: its line feeds, and one more when it does not end with one (`""` has none). A
    carriage return is never a line of its own, so a text with CRLF endings counts as with LF ones."""
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def digest_of(rows: Iterable[tuple[str, str]]) -> str:
    """The tree digest over `(relative path, sha256 hex)` rows (MacroCOSM 18.4.1): sorted by the paths' UTF-8 bytes,
    the sha256 of `<path> NUL <hex> LF` for each, concatenated."""
    h = hashlib.sha256()
    for rel, digest in sorted(rows, key=lambda r: path_key(r[0])):
        h.update(rel.encode("utf-8") + b"\0" + digest.encode("ascii") + b"\n")
    return h.hexdigest()


def is_text(data: bytes) -> bool:
    """Thym's test (THYM 20.1): UTF-8 (a byte-order mark tolerated), no zero byte, at most 1,000,000 bytes."""
    if len(data) > MAX_TEXT or b"\0" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _in_tree(name: str, data: bytes) -> bool:
    """MacroCOSM's test for a file in a folder its rule walks (the reference's, name and bytes)."""
    if (name in TREE_SKIP_FILES or name.endswith(TREE_SKIP_FILE_SUFFIXES) or name.endswith(".fabulac.cosm")
            or ".catem-" in name):
        return False
    if len(data) > MAX_TEXT or b"\0" in data[:TREE_SNIFF]:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _tree_skips_dir(d: Path) -> bool:
    n = d.name
    return (n in TREE_SKIP_DIRS or n.endswith(TREE_SKIP_DIR_SUFFIXES) or ".cshort-" in n
            or (d / "pyvenv.cfg").is_file())


def _points_to_dir(de: os.DirEntry) -> bool:
    """Whether a link names a folder (only asked to count it as the reference does; it is never followed)."""
    try:
        return de.is_dir(follow_symlinks=True)
    except OSError:
        return False


def _thym_skips(part: str) -> bool:
    return part.startswith(".") or part in SKIP_PARTS


@dataclass(eq=False)
class Folder:
    """A folder as a value: `path` as the person gave it (POSIX), `entries` the files the rule keeps in path order,
    `tree` its tree digest, `commit` and `origin` from the clone's files (None when not known), `links` how many
    symbolic links were left out, `skipped` how many files the digest's rule skipped (MacroCOSM's `skipped`). `root`
    is where its bytes are on disk, None for a folder read from a snapshot; `_texts` holds each text file's text."""
    path: str
    entries: tuple[Entry, ...]
    tree: str
    root: Path | None = None
    commit: str | None = None
    origin: str | None = None
    links: int = 0
    skipped: int = 0
    _texts: dict[str, str] = field(default_factory=dict, repr=False)

    # -- fields (THYM 20.1) -----------------------------------------------------------------------------------------

    @property
    def name(self) -> str:
        parts = [p for p in PurePosixPath(self.path.rstrip("/") or ".").parts if p not in (".", "")]
        if parts and parts[-1] != "..":
            return parts[-1]
        return self.root.resolve().name if self.root is not None else self.path

    @property
    def files(self) -> int:
        return len(self.entries)

    @property
    def bytes(self) -> int:
        return sum(e.size for e in self.entries)

    @property
    def lines(self) -> int:
        return sum(lines_in(self.text(e.path)) for e in self.entries if not e.binary)

    def field(self, name: str) -> Any:
        """A field of the folder (`code.lines`); None for a field it does not have, or one not known (`commit`)."""
        if name in ("path", "name", "files", "bytes", "lines", "tree", "commit", "origin"):
            return getattr(self, name)
        return None

    # -- its files ----------------------------------------------------------------------------------------------------

    def texts(self) -> list[Entry]:
        """The text files, in path order: what `for each` walks (THYM 20.2) and what `count` counts."""
        return [e for e in self.entries if not e.binary]

    def entry(self, path: str) -> Entry | None:
        return next((e for e in self.entries if e.path == path), None)

    def text(self, path: str) -> str:
        """A text file's text, as its bytes say it (a byte-order mark kept, so that it encodes back to its bytes)."""
        if path in self._texts:
            return self._texts[path]
        e = self.entry(path)
        if e is None or e.binary:
            raise FolderError(f"{path} is no text file of {self.path}")
        data = self.raw(path)
        text = data.decode("utf-8")
        self._texts[path] = text
        return text

    def raw(self, path: str) -> bytes:
        """A file's bytes, checked against the digest the folder recorded: a text's from the folder's own copy, a
        binary file's from the disk (a snapshot holds none)."""
        e = self.entry(path)
        if e is None:
            raise FolderError(f"{path} is no file of {self.path}")
        if path in self._texts:
            return self._texts[path].encode("utf-8")
        if self.root is None:
            raise FolderError(f"{path} is a binary file of {self.path}, and a snapshot holds no binary file's bytes")
        p = self.root / path
        if p.is_symlink():
            raise FolderError(f"{path} became a symbolic link after {self.path} was read")
        try:
            data = p.read_bytes()
        except OSError as e2:
            raise FolderError(f"{path} could not be read: {e2.strerror or 'the system would not open it'}") from None
        if hashlib.sha256(data).hexdigest() != e.sha256:
            raise FolderError(f"{path} changed after {self.path} was read")
        return data

    def member_fields(self, e: Entry) -> dict:
        """The fields of one of its files, as a `where` over the folder reads them (THYM 20.1)."""
        return member_fields(e, None if e.binary else self.text(e.path))

    # -- folders made from it ---------------------------------------------------------------------------------------

    def where(self, keep: Callable[[Entry], bool]) -> "Folder":
        """The same root with only the files `keep` holds for (binary files too), and a tree digest of its own over
        them (THYM 20.2: `repo where suffix is py` is a folder). The clone's `commit` and `origin` stay."""
        kept = [e for e in self.entries if keep(e)]
        rows = [(e.path, e.sha256) for e in kept if e.tree]
        texts = {e.path: self._texts[e.path] for e in kept if e.path in self._texts}
        return Folder(self.path, tuple(kept), digest_of(rows), root=self.root, commit=self.commit,
                      origin=self.origin, links=0, skipped=0, _texts=texts)

    def folders(self) -> list["Folder"]:
        """The folders directly below this one that the rule keeps (those holding a file it keeps), in path order,
        each with its own files, paths relative to it, and tree digest (THYM 20.2: `folders of d`)."""
        subs: dict[str, list[Entry]] = {}
        for e in self.entries:
            if "/" in e.path:
                top, rest = e.path.split("/", 1)
                subs.setdefault(top, []).append(Entry(rest, e.sha256, e.size, e.binary, e.tree))
        out = []
        for top in sorted(subs, key=path_key):
            entries = subs[top]
            texts = {e.path: self._texts[f"{top}/{e.path}"] for e in entries if f"{top}/{e.path}" in self._texts}
            rows = [(e.path, e.sha256) for e in entries if e.tree]
            out.append(Folder(f"{self.path.rstrip('/')}/{top}" if self.path not in ("", ".") else top,
                              tuple(entries), digest_of(rows), root=self.root / top if self.root else None,
                              _texts=texts))
        return out


def member_fields(e: Entry, text: str | None) -> dict:
    """A file's fields (THYM 20.1): `lines` for a text file, nothing for a binary one."""
    return {"path": e.path, "name": e.name, "suffix": e.suffix, "depth": e.depth, "size": e.size,
            "sha256": e.sha256, "binary": e.binary, "lines": lines_in(text) if text is not None else None}


# ---------------------------------------------------------------------------
# Reading a folder from disk
# ---------------------------------------------------------------------------

def _hash_file(p: Path) -> tuple[bytes | None, str, int]:
    """(the bytes when the file could be a text, else None; its sha256; its size), read in pieces."""
    h = hashlib.sha256()
    size = 0
    keep: list[bytes] | None = []
    with open(p, "rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
            if keep is not None:
                if size > MAX_TEXT:
                    keep = None
                else:
                    keep.append(chunk)
    return (b"".join(keep) if keep is not None else None), h.hexdigest(), size


def read(root: Path | str, *, path: str | None = None) -> Folder:
    """A folder from disk, under Thym's rule, with MacroCOSM's tree digest (THYM 20.1). `path` is the folder as the
    person gave it (default: `root` as written). Raises `FolderError` when the root is not a folder, or is a symbolic
    link (a link is never followed), or a file cannot be read."""
    root = Path(root)
    label = path if path is not None else root.as_posix()
    if root.is_symlink():
        raise FolderError(f"{label} is a symbolic link, and a folder is never read through one")
    if not root.is_dir():
        raise FolderError(f"{label} is not a folder")
    entries: list[Entry] = []
    texts: dict[str, str] = {}
    tree_rows: list[tuple[str, str]] = []
    links = skipped = 0

    def walk(d: Path, rel: str, thym_ok: bool, tree_ok: bool) -> None:
        nonlocal links, skipped
        try:
            found = sorted(os.scandir(d), key=lambda x: path_key(x.name))
        except OSError as e:
            raise FolderError(f"{rel or label} could not be read: {e.strerror or 'the system would not open it'}") \
                from None
        for de in found:
            r = f"{rel}/{de.name}" if rel else de.name
            here_thym = thym_ok and not _thym_skips(de.name)
            if de.is_symlink():
                if here_thym:
                    links += 1
                if tree_ok and not _points_to_dir(de):
                    skipped += 1                          # the reference counts a link to a file, or a dangling one
                continue
            if de.is_dir(follow_symlinks=False):
                sub_tree = tree_ok and not _tree_skips_dir(Path(de.path))
                if here_thym or sub_tree:
                    walk(Path(de.path), r, here_thym, sub_tree)
                continue
            if not de.is_file(follow_symlinks=False):
                continue                                  # a fifo, a socket, a device: not a regular file
            name_tree = tree_ok and not (de.name in TREE_SKIP_FILES or de.name.endswith(TREE_SKIP_FILE_SUFFIXES)
                                         or de.name.endswith(".fabulac.cosm") or ".catem-" in de.name)
            if not here_thym and not tree_ok:
                continue
            try:
                data, sha, size = _hash_file(Path(de.path))
            except OSError as e:
                raise FolderError(f"{r} could not be read: {e.strerror or 'the system would not open it'}") from None
            in_tree = name_tree and data is not None and _in_tree(de.name, data)
            if tree_ok and not in_tree:
                skipped += 1
            if in_tree:
                tree_rows.append((r, sha))
            if here_thym:
                text = data is not None and is_text(data)
                entries.append(Entry(r, sha, size, not text, in_tree))
                if text:
                    texts[r] = data.decode("utf-8")

    walk(root, "", True, True)
    entries.sort(key=lambda e: path_key(e.path))
    commit, origin = clone_of(root)
    return Folder(label, tuple(entries), digest_of(tree_rows), root=root, commit=commit, origin=origin,
                  links=links, skipped=skipped, _texts=texts)


def tree_digest(root: Path | str) -> dict:
    """MacroCOSM's tree digest of a folder on disk, exactly as the reference code gives it: `{files, bytes, skipped,
    tree, read}`, `read` the `(path, sha256, size)` of each file it read, in path order."""
    root = Path(root)
    out: list[tuple[str, str, int]] = []
    skipped = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not (here / d).is_symlink() and not _tree_skips_dir(here / d)]
        for f in filenames:
            p = here / f
            rel = p.relative_to(root).as_posix()
            if (p.is_symlink() or f in TREE_SKIP_FILES or f.endswith(TREE_SKIP_FILE_SUFFIXES)
                    or f.endswith(".fabulac.cosm") or ".catem-" in f):
                skipped += 1
                continue
            data = p.read_bytes()
            if not _in_tree(f, data):
                skipped += 1
                continue
            out.append((rel, hashlib.sha256(data).hexdigest(), len(data)))
    out.sort(key=lambda r: path_key(r[0]))
    return {"files": len(out), "bytes": sum(s for _, _, s in out), "skipped": skipped,
            "tree": digest_of((r, d) for r, d, _ in out), "read": out}


# ---------------------------------------------------------------------------
# The clone: commit and origin, read from its files (no git is run)
# ---------------------------------------------------------------------------

def _read_small(p: Path) -> str | None:
    try:
        if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_TEXT:
            return None
        return p.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None


def _git_dir(root: Path) -> Path | None:
    g = root / ".git"
    if g.is_symlink():
        return None
    if g.is_dir():
        return g
    said = _read_small(g)                                 # a worktree's `.git` file: `gitdir: <path>`
    if said and said.startswith("gitdir:"):
        p = Path(said[len("gitdir:"):].strip())
        p = p if p.is_absolute() else root / p
        return p if p.is_dir() and not p.is_symlink() else None
    return None


def _is_sha(s: str) -> bool:
    return len(s) in (40, 64) and all(c in "0123456789abcdef" for c in s)


def clone_of(root: Path) -> tuple[str | None, str | None]:
    """The clone's `HEAD` commit and its `origin` remote's url, read from `.git/HEAD`, the ref it names (a loose ref
    or `packed-refs`) and `.git/config`; (None, None) for a folder that is not a clone."""
    g = _git_dir(root)
    if g is None:
        return None, None
    common = g
    said = _read_small(g / "commondir")
    if said and said.strip():
        c = Path(said.strip())
        c = c if c.is_absolute() else g / c
        if c.is_dir():
            common = c
    commit = None
    head = (_read_small(g / "HEAD") or "").strip()
    if head.startswith("ref:"):
        ref = head[4:].strip()
        if ref and ".." not in PurePosixPath(ref).parts:
            for base in (g, common):
                loose = (_read_small(base / ref) or "").strip()
                if _is_sha(loose):
                    commit = loose
                    break
            if commit is None:
                for line in (_read_small(common / "packed-refs") or "").splitlines():
                    parts = line.strip().split(" ")
                    if len(parts) == 2 and parts[1] == ref and _is_sha(parts[0]):
                        commit = parts[0]
                        break
    elif _is_sha(head):
        commit = head
    origin = None
    section = None
    for line in (_read_small(common / "config") or "").splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = " ".join(s[1:-1].split())
            continue
        if section == 'remote "origin"' and "=" in s:
            k, v = s.split("=", 1)
            if k.strip() == "url" and v.strip():
                origin = v.strip()
                break
    return commit, origin


# ---------------------------------------------------------------------------
# Writing a folder out (a folder output lands as a directory, THYM 20.4)
# ---------------------------------------------------------------------------

def write_tree(folder: Folder, dest: Path | str) -> None:
    """Write exactly the folder's files under `dest` (which must not exist yet), each checked against its digest.
    Raises `FolderError` for a file whose bytes are not at hand (a binary file of a snapshot) or not as recorded."""
    dest = Path(dest)
    if dest.exists():
        raise FolderError(f"{dest.name} is already there")
    dest.mkdir(parents=True)
    for e in folder.entries:
        parts = PurePosixPath(e.path).parts
        if not parts or any(p in ("", ".", "..") for p in parts) or PurePosixPath(e.path).is_absolute():
            raise FolderError(f"{e.path} is not a path inside the folder")
        data = folder.raw(e.path)
        if hashlib.sha256(data).hexdigest() != e.sha256:
            raise FolderError(f"{e.path} is not the file the folder recorded")
        target = dest.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


# ---------------------------------------------------------------------------
# The snapshot (THYM 20.3): a thym/1 volume of kind folder, written by hand
# ---------------------------------------------------------------------------

_BREAKS = frozenset("\r\x85\u2028\u2029")     # the line breaks YAML knows beside the line feed


def _needs_escape(ch: str) -> bool:
    o = ord(ch)
    return (o < 0x20 and ch not in "\t\n") or o == 0x7F or 0x80 <= o <= 0x9F or ch in _BREAKS or o == 0xFEFF \
        or 0xD800 <= o <= 0xDFFF or o in (0xFFFE, 0xFFFF)


def quoted(s: str) -> str:
    """A string as a YAML double-quoted scalar on one line: `"`, `\\`, line feeds, tabs and every character YAML
    would not keep as it is, escaped."""
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif _needs_escape(ch):
            out.append(f"\\x{o:02x}" if o <= 0xFF else f"\\u{o:04x}" if o <= 0xFFFF else f"\\U{o:08x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _literal_ok(text: str) -> bool:
    return "\n" in text and text.strip() != "" and not any(_needs_escape(c) for c in text)


def block(text: str, indent: int) -> str:
    """A text as a value at mapping indentation `indent`: a literal block scalar with an explicit indentation
    indicator and the chomping its trailing line feeds need, or, for a text a literal block cannot hold exactly,
    a double-quoted scalar."""
    if not _literal_ok(text):
        return quoted(text)
    body = text.rstrip("\n")
    trailing = len(text) - len(body)
    chomp = "-" if trailing == 0 else ("" if trailing == 1 else "+")
    pad = " " * (indent + 2)
    lines = [(pad + ln) if ln else "" for ln in body.split("\n")]
    if trailing > 1:
        lines += [""] * (trailing - 1)
    return f"|2{chomp}\n" + "\n".join(lines)


def _digest_scalar(s: str) -> str:
    return s if s and any(c.isalpha() for c in s) and all(c.isalnum() for c in s) else quoted(s)


def snapshot_text(folder: Folder, *, id: str, name: str | None = None) -> str:
    """The snapshot of a folder a run took (THYM 20.3): its catalog (`oes: thym/1`, `kind: folder`, `id`, `name`,
    `path`, `tree`, and `commit` and `origin` when known), every file with its digest and size (`binary: true` for a
    binary file; `digested: false` for a text file the tree digest is not over, `digested: true` for a binary one it
    is over: a text is in the digest and a binary file is not, unless the row says otherwise), and the text of every
    text file as a block scalar. Binary files cost one row each; their bytes are not kept."""
    out = ["oes: thym/1", "kind: folder", f"id: {quoted(id)}", f"name: {quoted(name or folder.path)}",
           f"path: {quoted(folder.path)}", f"tree: {_digest_scalar(folder.tree)}"]
    if folder.commit:
        out.append(f"commit: {quoted(folder.commit)}")
    if folder.origin:
        out.append(f"origin: {quoted(folder.origin)}")
    out.append("files:" if folder.entries else "files: []")
    for e in folder.entries:
        row = f"  - {{path: {quoted(e.path)}, sha256: {_digest_scalar(e.sha256)}, size: {e.size}"
        if e.binary:
            row += ", binary: true"
        if e.tree == e.binary:                     # said only where it is not the rule: text in it, binary not
            row += f", digested: {'true' if e.tree else 'false'}"
        out.append(row + "}")
    texts = folder.texts()
    out.append("texts:" if texts else "texts: []")
    for e in texts:
        out.append(f"  - path: {quoted(e.path)}")
        out.append(f"    text: {block(folder.text(e.path), 4)}")
    out.append("nodes: []")
    return "\n".join(out) + "\n"


def from_snapshot(mapping: Any, *, path: str | None = None) -> Folder:
    """A folder from its snapshot's mapping (the caller reads the YAML). Every text must match its file's digest,
    and the files the digest is over must give the recorded tree; raises `FolderError` otherwise."""
    if not isinstance(mapping, dict) or mapping.get("kind") != "folder":
        raise FolderError("the snapshot is not a thym/1 volume of kind folder")
    label = str(path if path is not None else mapping.get("path") or mapping.get("name") or "")
    entries: list[Entry] = []
    for row in mapping.get("files") or []:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str):
            raise FolderError("a file row of the snapshot names no path or no sha256")
        size = row.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise FolderError(f"{row['path']}: the snapshot gives no size")
        binary = row.get("binary") is True
        digested = row.get("digested")
        entries.append(Entry(row["path"], row["sha256"], size, binary,
                             digested if isinstance(digested, bool) else not binary))
    entries.sort(key=lambda e: path_key(e.path))
    by_path = {e.path: e for e in entries}
    texts: dict[str, str] = {}
    for row in mapping.get("texts") or []:
        p = row.get("path") if isinstance(row, dict) else None
        t = row.get("text") if isinstance(row, dict) else None
        e = by_path.get(p) if isinstance(p, str) else None
        if e is None or e.binary or not isinstance(t, str):
            raise FolderError(f"the snapshot holds a text for {p!r}, which it lists as no text file")
        if hashlib.sha256(t.encode("utf-8")).hexdigest() != e.sha256:
            raise FolderError(f"{p}: the snapshot's text does not match its digest")
        texts[p] = t
    missing = [e.path for e in entries if not e.binary and e.path not in texts]
    if missing:
        raise FolderError(f"the snapshot holds no text for {missing[0]}")
    tree = mapping.get("tree")
    if not isinstance(tree, str) or not tree:
        raise FolderError("the snapshot gives no tree digest")
    commit = mapping.get("commit") if isinstance(mapping.get("commit"), str) else None
    origin = mapping.get("origin") if isinstance(mapping.get("origin"), str) else None
    return Folder(label, tuple(entries), tree, root=None, commit=commit, origin=origin, _texts=texts)


__all__ = ["Entry", "Folder", "FolderError", "FOLDER_FIELDS", "MEMBER_FIELDS", "MAX_TEXT", "block", "clone_of",
           "digest_of", "from_snapshot", "is_text", "lines_in", "member_fields", "path_key", "quoted", "read",
           "snapshot_text", "tree_digest", "write_tree"]
