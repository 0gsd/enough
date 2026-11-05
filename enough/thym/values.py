"""Values: the documents a Thym program moves, each knowing its type and where it came from (docs/THYM.md 5, 12.6, 15).

A value is what one node of a plan gives another: a text, a fabula, a short, an atem, an item, a volume, a morph, a
context, a graph, a package, or a plain value (a number, a word, a list). This module holds the `Value` the runtime
passes between moves; the digest rule of section 12.6 (a text's sha256 over its bytes, a volume's over its catalog file,
a `.cosm` mapping's over its canonical dump: keys in insertion order, LF newlines, UTF-8); the members a `for each`
walks (section 8.1: a volume's items in told order, a short's lines, a list's members); the field reads of section 4.5
(`now.medium`, a bare field name inside a `where`); the stamping of `made` (section 5.3) on what a move gives; and the
loading of a plan's inputs from disk: a file, a volume folder or a package folder (section 15), each checked against the
sha256 the plan recorded (a file's bytes, a volume's or a package's catalog file, as the suite's README says).

Standalone like the rest of the package: the standard library, PyYAML and `enough.macrocosm`.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any

from enough import macrocosm as mc
from enough.thym import Refusal

#: The types whose values carry provenance (THYM.md 5.1); `context` is one too when it is an occasional context item.
MEANING_TYPES = ("text", "fabula", "short", "atem", "item", "volume", "morph", "context", "graph", "package")
#: The plain types, which carry none.
PLAIN_TYPES = ("number", "string", "bool", "date", "word", "list", "nothing", "report", "plan", "trace")
#: The file extension a value is written with, by type, when its payload is a mapping (THYM.md 17.1).
COSM_EXT = {"package": "package.cosm", "morph": "morph.cosm", "context": "context.cosm", "plan": "plan.cosm",
            "trace": "trace.cosm"}
#: A value a person wrote by hand, or one read from disk without `made` (THYM.md 5.3).
HAND_MADE = {"move": "none"}

_WORD = re.compile(r"^[a-z][a-z0-9-]*$")
_ID = re.compile(r"^(?:(?P<part>[^/]+(?:/[^/]+)?)//)?(?P<module>[A-Z]):(?P<kind>[a-z][a-z0-9-]*)/")
_FIRST_INT = re.compile(r"\d+")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plain(value: Any) -> Any:
    """A deep copy that shares no mapping or list and holds no `Value` (a value inside becomes its payload), so that
    `macrocosm.dump` never meets an alias it would refuse."""
    if isinstance(value, Value):
        return plain(value.payload)
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def canonical(mapping: dict) -> bytes:
    """A `.cosm` mapping in canonical form (THYM.md 12.6): `macrocosm.dump`, keys in insertion order (the declaration
    key first), LF newlines, UTF-8."""
    return mc.dump(plain(mapping)).encode("utf-8")


@dataclass(eq=False)
class Value:
    """One value of a run. `type` is the Thym type (a text's type is its density); `payload` is what it holds: text
    as a `str`, a `.cosm` document as a mapping, a folder volume as a loaded `macrocosm.Volume`, a number as an `int`,
    a list as a list of values. `path` is the file or folder it was read from; `raw` its bytes as read, kept so that a
    value read from disk keeps the digest the plan recorded; `made` its provenance (`{move, run, step, node,
    engine}`, or `{move: none}` when hand-made); `origin` an item's place (its volume, id, module and kind); and
    `state` is `pending` for what a scaffold gave (THYM.md 19)."""
    type: str
    payload: Any = None
    path: Path | None = None
    raw: bytes | None = None
    made: dict | None = None
    origin: dict | None = None
    state: str | None = None

    # -- bytes and digests ------------------------------------------------------------------------------------------

    def bytes(self) -> bytes:
        """The value's canonical bytes: what is written for it and what its digest is over (THYM.md 12.6)."""
        if self.raw is not None:
            return self.raw
        p = self.payload
        if self.type == "nothing" or p is None:
            return b""
        if isinstance(p, bytes):
            return p
        if isinstance(p, str):
            return p.encode("utf-8")
        if isinstance(p, mc.Volume):
            return catalog_path(p).read_bytes()
        if isinstance(p, dict):
            return canonical(p)
        if isinstance(p, (list, tuple)):
            return "\n".join(m.sha256 if isinstance(m, Value) else sha256_bytes(_scalar_bytes(m))
                             for m in p).encode("utf-8")
        return _scalar_bytes(p)

    @property
    def sha256(self) -> str:
        return sha256_bytes(self.bytes())

    @property
    def ext(self) -> str:
        """The extension the value is written with: `md` for a text or a short, `<kind>.cosm` or `cosm` for a mapping
        or a volume, `txt` for a plain value."""
        p = self.payload
        if self.type in ("text", "short") or (self.type == "atem" and isinstance(p, str)):
            return "md"
        if isinstance(p, (dict, mc.Volume)) or self.type in ("list",):
            return COSM_EXT.get(self.type, "cosm")
        return "txt"

    def write_bytes(self) -> bytes:
        """What lands on disk: the canonical bytes, except that a list is written as a mapping of its members."""
        if self.type == "list" and self.raw is None:
            return canonical({"members": [plain(m) for m in (self.payload or [])]})
        return self.bytes()

    # -- reading ----------------------------------------------------------------------------------------------------

    @property
    def is_nothing(self) -> bool:
        return self.type == "nothing"

    def text(self) -> str:
        """The value as text: a text's or a short's characters, an atem's line, a mapping's canonical dump."""
        if isinstance(self.payload, str):
            return self.payload
        if self.raw is not None:
            return self.raw.decode("utf-8-sig", errors="replace")
        if self.type == "atem" and isinstance(self.payload, dict) and isinstance(self.payload.get("line"), str):
            return self.payload["line"]
        return self.bytes().decode("utf-8", errors="replace")

    def mapping(self) -> dict | None:
        """The value's mapping: a `.cosm` document, an item, a folder volume's catalog; None for anything else."""
        if isinstance(self.payload, dict):
            return self.payload
        if isinstance(self.payload, mc.Volume):
            return self.payload.catalog
        return None

    def plain(self) -> Any:
        """The value as a condition compares it (THYM.md 4.5): a word or a string as `str`, a number as `int`, a
        bool, a date, None for nothing, a list of those for a list; any other value stands for itself."""
        if self.type == "nothing":
            return None
        if self.type in ("word", "string", "number", "bool", "date"):
            return self.payload
        if self.type == "list":
            return [m.plain() if isinstance(m, Value) else m for m in (self.payload or [])]
        return self

    def field(self, name: str) -> Any:
        """A field read (`now.medium`, or a bare field name in a `where` over items): an item's field; a volume's
        catalog key; else the field of a volume's one item (a context volume holds one context item). `kind` and
        `module` fall back to what the item's id says, `module` as the module's name (`employees`) where the
        MiniCOSM names it. None when there is no such field."""
        p = self.payload
        if self.origin and "item" in self.origin and isinstance(p, dict):
            return item_field(p, name, self.origin)
        if isinstance(p, mc.Volume):
            if name in p.catalog:
                return p.catalog[name]
            items = list(p.items.values())
            return items[0].data.get(name) if len(items) == 1 else None
        if isinstance(p, dict):
            nodes = p.get("nodes")
            if name != "nodes" and name in p:
                return p[name]
            if isinstance(nodes, list):
                rows = [n for n in nodes if isinstance(n, dict)]
                if len(rows) == 1:
                    return item_field(rows[0], name, {"item": True, "oes": p.get("oes")})
            elif "id" in p:
                return item_field(p, name, {"item": True})
        return None

    def copy(self, **changes: Any) -> "Value":
        return dataclasses.replace(self, **changes)

    def __repr__(self) -> str:            # short: payloads can be whole volumes
        where = f" {self.path}" if self.path else ""
        return f"<Value {self.type}{where} {self.sha256[:12]}>"


NOTHING = Value("nothing")


def _scalar_bytes(x: Any) -> bytes:
    if isinstance(x, bool):
        return b"true" if x else b"false"
    if isinstance(x, (_dt.date, _dt.datetime)):
        return x.isoformat().encode("utf-8")
    if x is None:
        return b""
    return str(x).encode("utf-8")


def catalog_path(volume: mc.Volume) -> Path:
    root = volume.root or volume.path
    return Path(root) / volume.catalog_file if volume.catalog_file else Path(volume.path)


def wrap(x: Any) -> Value:
    """A plain Python value as a Thym value: None is nothing, a bool a bool, an int a number, a lowercase single
    word a word, any other string a string, a date a date, a list a list, a mapping an item (or a volume, when it
    holds `nodes`)."""
    if isinstance(x, Value):
        return x
    if x is None:
        return NOTHING
    if isinstance(x, bool):
        return Value("bool", x)
    if isinstance(x, int):
        return Value("number", x)
    if isinstance(x, str):
        return Value("word" if _WORD.match(x) else "string", x)
    if isinstance(x, (_dt.date, _dt.datetime)):
        return Value("date", x)
    if isinstance(x, (list, tuple)):
        return Value("list", [wrap(m) for m in x])
    if isinstance(x, dict):
        return Value("volume" if isinstance(x.get("nodes"), list) else "item", x)
    return Value("string", str(x))


# ---------------------------------------------------------------------------
# Items: the members of a volume (THYM.md 8.1) and their fields (4.5)
# ---------------------------------------------------------------------------

def _manifest_for(oes: Any) -> mc.Manifest | None:
    if not isinstance(oes, str) or "/" not in oes:
        return None
    return mc.default_registry().get(oes.split("/", 1)[0])


def _module_name(manifest: mc.Manifest | None, letter: str | None) -> str | None:
    if manifest is None or not letter:
        return letter
    name = manifest.module(letter).get("name") if manifest.module(letter) else None
    return name.strip().lower() if isinstance(name, str) and name.strip() else letter


def item_field(data: dict, name: str, origin: dict | None = None) -> Any:
    """One field of an item mapping. `kind` and `module` are the item's place, read from its id (`P:product/x` is of
    kind `product` in the module whose name is `products`), not a field of that name: a Comprise aim's own `kind`
    (`seek`) would otherwise hide that it is an `aim` (THYM.md 18, `h where kind is aim`)."""
    origin = origin or {}
    if name in ("kind", "module"):
        if origin.get(name) is not None:
            return origin[name]
        mt = _ID.match(str(data.get("id") or ""))
        if mt:
            if name == "kind":
                return mt.group("kind")
            return _module_name(_manifest_for(origin.get("oes")), mt.group("module"))
    return data.get(name)


def _told_key(data: dict) -> tuple[int, str]:
    span = data.get("span")
    line = 10 ** 9
    if isinstance(span, dict):
        mt = _FIRST_INT.search(str(span.get("lines") or ""))
        if mt:
            line = int(mt.group(0))
    return line, str(data.get("id") or "")


def members(value: Value) -> list[Value] | None:
    """What a `for each` walks (THYM.md 8.1): the items of a volume or a fabula in told order (by span, then by id),
    the lines of a short or a text, the members of a list. None when the value is not a collection."""
    p = value.payload
    if value.type == "list":
        return [m if isinstance(m, Value) else wrap(m) for m in (p or [])]
    if isinstance(p, mc.Volume):
        man = p.manifest
        rows = []
        for it in p.items.values():
            rows.append(Value("item", dict(it.data), origin={
                "item": True, "volume": value, "id": it.id, "key": it.key, "kind": it.kind, "oes": p.oes,
                "module": _module_name(man, it.module), "letter": it.module}))
        return sorted(rows, key=lambda v: _told_key(v.payload))
    if isinstance(p, dict) and isinstance(p.get("nodes"), list):
        oes = p.get("oes")
        rows = [Value("item", dict(n), origin={"item": True, "volume": value, "id": n.get("id"), "oes": oes})
                for n in p["nodes"] if isinstance(n, dict)]
        return sorted(rows, key=lambda v: _told_key(v.payload))
    if value.type in ("short", "text") and isinstance(p, str):
        return [Value("short", line) for line in p.splitlines() if line.strip()]
    return None


def posix_path(path: Any) -> str:
    """A path as a plan or a trace writes it: with forward slashes whatever system made it (`outputs/out.package.cosm`,
    never `outputs\\out.package.cosm`), so that a run recorded on Windows replays anywhere. A text given on Windows is
    read as a Windows path; elsewhere a text stands as it is, since a backslash is a letter of a POSIX name."""
    if isinstance(path, PurePath):
        return path.as_posix()
    text = str(path)
    return PureWindowsPath(text).as_posix() if os.sep == "\\" else text


def item_id(value: Value) -> str | None:
    """An item's bare id (`P:service/reconcile`): its origin's, else its mapping's."""
    iid = (value.origin or {}).get("id") or (value.mapping() or {}).get("id")
    return str(iid) if iid else None


def item_key(value: Value) -> str | None:
    """An item's own key (`atom/meadow//C:entity/meadow-software-inc`): its id qualified with its part where the volume
    has parts (`Item.key`), else its bare id. Ids repeat across a holotype's parts (two concerns may each hold an
    `M:audience/donors`), so what is withheld is told apart by key (THYM.md 18)."""
    key = (value.origin or {}).get("key")
    return str(key) if key else item_id(value)


def is_withheld(withheld: Any, value: Value) -> bool:
    """Whether `withhold` took this item (`MoveContext.withheld`): an item it was given is held by its key, so its
    twin in another part stays; an id it was given as a word (`ctx.withhold("C:entity/x")`) takes every item of that
    id, since a word names no part."""
    if not withheld:
        return False
    key = item_key(value)
    if key is not None and key in withheld:
        return True
    iid = item_id(value)
    held = withheld.get(iid) if iid is not None and hasattr(withheld, "get") else None
    return isinstance(held, Value) and held.is_nothing


# ---------------------------------------------------------------------------
# Provenance: `made` on what a move gives (THYM.md 5.3, 19)
# ---------------------------------------------------------------------------

def stamp(value: Value, made: dict, *, pending: bool = False) -> Value:
    """The value as a move gives it: `made` set on the value, and, when the move made new content (not bytes read
    verbatim from disk), written into the content too: on an item mapping (replacing what it carried) and on every
    item of a volume mapping that carries none. With `pending` (a scaffold's output, THYM.md 19) the value's state is
    `pending` and so is each written item's `provenance.state`. Nothing carries nothing."""
    if value.type == "nothing":
        return value
    out = value.copy(made=dict(made), state="pending" if pending else value.state)
    if value.raw is None and isinstance(value.payload, dict):
        p = plain(value.payload)
        if isinstance(p.get("nodes"), list):
            for n in p["nodes"]:
                if isinstance(n, dict):
                    n.setdefault("made", dict(made))
                    _pend(n, pending)
        elif "id" in p and "type" in p:
            p["made"] = dict(made)
            _pend(p, pending)
        out.payload = p
    return out


def _pend(item: dict, pending: bool) -> None:
    if pending and isinstance(item.get("provenance"), dict):
        item["provenance"]["state"] = "pending"


# ---------------------------------------------------------------------------
# Inputs: what a plan runs on (THYM.md 12.1, 15; the suite's digest rule)
# ---------------------------------------------------------------------------

def folder_catalog(folder: Path) -> Path | None:
    """The catalog file of a volume or package folder: `package.cosm` for a package, else the catalog the
    registry's manifests name."""
    pkg = folder / "package.cosm"
    if pkg.is_file():
        return pkg
    return mc.default_registry().find_catalog(folder)


def digest_path(path: Path) -> str | None:
    """An input's sha256 as a plan records it: a file's over its bytes, a volume's or a package's over its catalog
    file. None when a folder holds no catalog."""
    path = Path(path)
    if path.is_dir():
        cat = folder_catalog(path)
        return sha256_bytes(cat.read_bytes()) if cat is not None else None
    return sha256_bytes(path.read_bytes())


def guess_type(path: Path) -> str:
    """A path's Thym type when the plan does not say: a folder with `package.cosm` is a package, any other folder a
    volume; a `.md` file a text; a `.cosm` file by what it declares (an `emf/1` twin is a fabula, a `thym/1` file is
    its kind)."""
    path = Path(path)
    if path.is_dir():
        return "package" if (path / "package.cosm").is_file() else "volume"
    if path.suffix == ".cosm":
        said = mc.sniff_declaration(path) or ""
        if said.startswith("emf/"):
            return "fabula"
        if said.startswith("thym/"):
            try:
                kind = (mc.yaml_load(mc.read_text(path)) or {}).get("kind")
            except Exception:  # noqa: BLE001 - an unreadable file is just a volume here; loading says why
                kind = None
            return kind if kind in ("morph", "context", "package", "plan", "trace") else "volume"
        return "volume"
    return "text"


def load_input(spec: dict, inputs_root: Path) -> Value | Refusal:
    """One input of a plan (`{name, type, path, sha256}`) as a value, read from `path` (relative to `inputs_root`),
    or a plan-time refusal when it is missing or its digest differs from the plan's (THYM.md 9: "a missing or changed
    input")."""
    name = str(spec.get("name") or "?")
    raw_path = spec.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        return Refusal("plan", "input", f"input {name} has no path in the plan")
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(inputs_root) / path
    if not path.exists():
        return Refusal("plan", "input", f"input {name}: {raw_path} is not there, and the plan needs it; give its path "
                                        "or plan again")
    got = digest_path(path)
    if got is None:
        return Refusal("plan", "input", f"input {name}: {raw_path} is a folder with no catalog")
    want = spec.get("sha256")
    if isinstance(want, str) and want and got != want:
        return Refusal("plan", "input", f"input {name} changed since it was planned: {raw_path} has sha256 {got[:12]}, "
                                        f"the plan recorded {want[:12]}; plan it again")
    typ = str(spec.get("type") or guess_type(path))
    try:
        return read_value(path, typ)
    except (OSError, ValueError) as e:
        return Refusal("plan", "input", f"input {name}: {raw_path} could not be read: {e}")


def read_value(path: Path, typ: str) -> Value:
    """A file or folder as a value of type `typ`, hand-made, its bytes kept. Raises ValueError for a `.cosm` file
    that is not one mapping, or a volume the reader refuses."""
    path = Path(path).absolute()
    if path.is_dir():
        cat = folder_catalog(path)
        if cat is None:
            raise ValueError("a folder with no catalog")
        raw = cat.read_bytes()
        if typ == "package" or cat.name == "package.cosm":
            data = mc.yaml_load(raw.decode("utf-8-sig"))
            if not isinstance(data, dict):
                raise ValueError("package.cosm is not a mapping")
            return Value("package", data, path=path, raw=raw, made=dict(HAND_MADE))
        vol = mc.load_volume(path)
        if vol.refused is not None:
            raise ValueError(str(vol.refused))
        return Value(typ, vol, path=path, raw=raw, made=dict(HAND_MADE))
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    if path.suffix == ".cosm":
        data = mc.yaml_load(text)
        if not isinstance(data, dict):
            raise ValueError("a .cosm file's top level is a mapping")
        return Value(typ, data, path=path, raw=raw, made=dict(HAND_MADE))
    return Value(typ, text, path=path, raw=raw, made=dict(HAND_MADE))
