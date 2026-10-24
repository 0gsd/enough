"""MacroCOSM OES: the reference reader for `.cosm` volumes (MacroCOSM OES v0.0.1).

MacroCOSM is the shared grammar every MiniCOSM is written in: a domain
enumerated as a file system that is also a relational database, made to
be rendered. A MiniCOSM (Comprise OES for companies, Canon for enough's
library, EMF for one text) is declared by a manifest (`manifest:
minicosm/0`). A volume is one database of a MiniCOSM: a folder, or a
single catalog file, whose catalog's first key says which MiniCOSM it is
written in (`oes: <minicosm>/<major>`). This module reads any volume of
any MiniCOSM it holds a manifest for: it loads it, runs the generic
checks, resolves paths and references, and draws it. The prose is
docs/MACROCOSM_OES.md; the cosm viewer, Canon and the readvisor tools
all call through here.

Charter:

- **Files are the source of truth.** A volume is plain text in the COSM
  YAML subset; any index is derived and disposable. This module reads;
  it never writes a file (`dump` hands a writer the text).
- **The reader keeps what it doesn't know.** Unknown keys, fields and
  check ids are kept and reported, never dropped. Bad input never
  raises: a file that does not parse is a `Problem`, a declaration this
  reader cannot read is a `Refusal`. Only programming errors raise.
- **Manifests drive everything.** Modules, kinds, reference fields, the
  id and path grammar, required fields, closed lists, checks and lenses
  all come from the manifest; nothing below knows one MiniCOSM from
  another. Comprise's manifest is read verbatim: it is the first
  conformance test.
- **The code wins over the spec.** Where docs/MACROCOSM_OES.md and this
  module disagree, the spec is corrected.

Standalone by design: PyYAML and the standard library only, nothing
imported from enough, so the file can be vendored into another repo as
one file. Manifests come from `defaults/cosm/manifests/` beside the
package, or from folders a caller names; nothing under the user's home
is read or written.

    python -m enough.macrocosm lint     <volume> [--json]
    python -m enough.macrocosm paths    <volume> [<path or id>]
    python -m enough.macrocosm tree     <volume>
    python -m enough.macrocosm mermaid  <volume> [--lens ID] [--max-nodes N] [--around KEY [--depth N]]
    python -m enough.macrocosm identify <catalog or folder>

Two entry points beside `load_volume`: `load_volume_text(text, filename=)`
reads one catalog held in memory (a spec example, a block a viewer shows)
exactly as `load_volume` reads a file of that name, writing nothing; and
`to_mermaid(volume, lens, around=key, depth=1)` draws a local graph, the
item and what its references and links reach in or out within `depth`
steps, as one flowchart with the centre node in the class `focus`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import functools
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import yaml

MACROCOSM_VERSION = "0.0.1"
MANIFEST_FORMAT = "minicosm/0"
MANIFEST_GLOB = "*.manifest.cosm"
DEFAULT_MANIFEST_DIR = Path(__file__).resolve().parents[1] / "defaults" / "cosm" / "manifests"
# When two manifests could claim one catalog, the first in this order wins; any other MiniCOSM follows by name.
REGISTRY_ORDER = ("comprise", "cosm", "canon", "emf", "doc")
# The lens kinds `to_mermaid` draws. A manifest may declare others (DocOES's `short` and `table`): `Manifest.lenses`
# keeps them for the code that renders them; `lenses(volume)` lists only the ones drawn here.
DRAWN_LENS_KINDS = ("mermaid",)
# The keys `dump` puts first, looked for in this order: a catalog's declaration, a manifest's own format line.
DECLARATION_KEYS = ("oes", "manifest", "cosm", "opi", "comprise")
# Catalog keys any MiniCOSM accepts: kept and ignored (reserved for a version test on the grammar itself).
RESERVED_CATALOG_KEYS = ("macrocosm",)

# The generic checks this version implements. A manifest's `checks.load` + `checks.envelope` select from them;
# the ids it lists that are not here are reported as not run, never as failures.
CHECKS = ("load", "duplicate-id", "id-grammar", "id-module", "type", "type-prefix", "identity-min", "provenance",
          "status", "visibility", "ref-grammar", "ref-unresolved", "closed-list", "pending-shape", "module-none",
          "catalog-key")
SEVERITY = {**{c: "error" for c in CHECKS}, "module-none": "warning", "pending-shape": "warning"}

WHOLE_ITEM = "node"            # the field path of an open question on a whole item (Comprise's word)
SNIFF_LINES = 8                # how far `sniff_declaration` reads: the declaration is a catalog's first key
LABEL_LIMIT = 48               # merirmaid's node-char-limit
MAX_NODES = 200
_TREE_DEPTH = 200              # the text tree nests no deeper than this


# ---------------------------------------------------------------------------
# The file format: the COSM YAML subset
# ---------------------------------------------------------------------------

class Loader(yaml.SafeLoader):
    """SafeLoader with YAML 1.2 booleans: only true and false, in any case. YAML 1.1 also reads on, off, yes and
    no as booleans; in COSM they are strings (a claim's `on:` key depends on it). Comprise's loader, exactly."""


Loader.yaml_implicit_resolvers = {k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:bool"]
                                  for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()}
Loader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
                             list("tTfF"))


def yaml_load(text: str) -> Any:
    """Parse COSM text. Raises yaml.YAMLError on bad YAML, like yaml.load; the volume loader catches it."""
    return yaml.load(text, Loader=Loader)


def read_text(path) -> str:
    """utf-8 with an optional BOM; universal newlines, so CRLF and LF read the same."""
    return Path(path).read_text(encoding="utf-8-sig")


_SNIFF_RE = re.compile(r"^(oes|cosm|opi|comprise|manifest):[ \t]*['\"]?([^\s'\"#]*)")


def sniff_declaration(path, *, lines: int = SNIFF_LINES) -> str | None:
    """What a .cosm file declares, from its first lines alone and without YAML: `emf/1` for `oes: emf/1`;
    `cosm 0.3` (key and value) for a legacy key; None when none of its first `lines` lines declares anything or
    the file cannot be read. For listings that must not parse every file (an EMF twin hides behind its text)."""
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            for _ in range(lines):
                line = fh.readline()
                if not line:
                    break
                mt = _SNIFF_RE.match(line)
                if mt:
                    return mt.group(2) if mt.group(1) == "oes" else f"{mt.group(1)} {mt.group(2)}".strip()
    except OSError:
        return None
    return None


class _CheckingLoader(Loader):
    """The same loader, noting as it composes the constructs the COSM subset forbids. The data is unchanged."""

    def __init__(self, stream):
        super().__init__(stream)
        self.forbidden: list[tuple[str, int]] = []

    def compose_node(self, parent, index):
        event = self.peek_event()
        line = event.start_mark.line + 1 if event.start_mark else 0
        if isinstance(event, yaml.AliasEvent):
            self.forbidden.append((f"an alias (*{event.anchor})", line))
        else:
            if event.anchor is not None:
                self.forbidden.append((f"an anchor (&{event.anchor})", line))
            if getattr(event, "tag", None) is not None:
                self.forbidden.append((f"a tag ({event.tag})", line))
        return super().compose_node(parent, index)


def _yaml_error(e: Exception) -> str:
    if isinstance(e, yaml.composer.ComposerError) and "single document" in str(e):
        return "more than one YAML document: a .cosm file is one document"
    problem, mark = getattr(e, "problem", None), getattr(e, "problem_mark", None)
    if problem:
        return f"YAML error: {problem}" + (f" (line {mark.line + 1}, column {mark.column + 1})" if mark else "")
    first = str(e).splitlines()[0] if str(e) else type(e).__name__
    return f"YAML error: {first}"


def _parse(text: str) -> tuple[Any, list[str], str | None]:
    """(data, forbidden-construct messages, error message or None). Never raises for bad input: an impossible
    date (`2019-02-30`) or a deep nesting is an error message like any YAML error."""
    loader = _CheckingLoader(text)
    data, error = None, None
    try:
        data = loader.get_single_data()
    except (yaml.YAMLError, ValueError, TypeError, OverflowError, RecursionError) as e:
        tagged = any(what.startswith("a tag") for what, _ in loader.forbidden)
        if not (tagged and isinstance(e, yaml.constructor.ConstructorError)):
            error = _yaml_error(e)
    finally:
        loader.dispose()
    forbidden = [f"{what} at line {line}: anchors, aliases and tags are not part of the COSM subset"
                 for what, line in loader.forbidden]
    if error is None and data is None and forbidden and any(f.startswith("a tag") for f in forbidden):
        error = "a tag this reader cannot construct"
    return data, forbidden, error


class _Dumper(yaml.SafeDumper):
    """safe_dump's dumper that never writes an anchor: shared structures are refused before dumping, so the only
    repeats left are equal scalars (a date used twice), which must be written twice."""

    def ignore_aliases(self, data):
        return True


def _refuse_shared(value: Any) -> None:
    seen: set[int] = set()
    stack = [value]
    while stack:
        v = stack.pop()
        if isinstance(v, (dict, list)):
            if id(v) in seen:
                raise ValueError("dump refuses a structure that holds the same mapping or list twice: YAML would "
                                 "write an anchor and an alias, which the COSM subset forbids; copy it instead")
            seen.add(id(v))
            stack.extend(v.values() if isinstance(v, dict) else v)


def dump(mapping: dict) -> str:
    """COSM text for a mapping: `yaml.safe_dump(sort_keys=False, allow_unicode=True, width=110)` with the
    declaration key first and never an anchor. Raises ValueError for a structure that shares a mapping or a list
    (a programming error: the caller built it)."""
    if not isinstance(mapping, dict):
        raise TypeError("dump takes a mapping: a .cosm file's top level is a mapping")
    _refuse_shared(mapping)
    first = next((k for k in DECLARATION_KEYS if k in mapping), None)
    if first is not None and next(iter(mapping)) != first:
        mapping = {first: mapping[first], **{k: v for k, v in mapping.items() if k != first}}
    return yaml.dump(mapping, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110,
                     default_flow_style=False)


# ---------------------------------------------------------------------------
# Results: refusals, problems, declarations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Refusal:
    """A plain "no": a declaration this reader cannot read, a manifest that is not one, a path that is
    malformed. Falsy, so `if not result:` reads naturally; `str()` is the message."""
    message: str
    said: str | None = None          # what the file declared, when the refusal is about a declaration
    file: str | None = None

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return self.message


@dataclass
class Problem:
    """One finding of the loader or the checks. `item` is the item's key (its id, qualified with its part where
    the volume has parts) or '' for a file-level problem; `file` is relative to the volume's folder."""
    check: str
    severity: str                    # error | warning | note
    item: str
    file: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        """Comprise's string shape: `<check> <item> (<file>): <message>`, shortened when there is no item."""
        if self.item and self.file:
            return f"{self.check} {self.item} ({self.file}): {self.message}"
        where = self.item or self.file
        return f"{self.check} {where}: {self.message}" if where else f"{self.check}: {self.message}"

    def to_dict(self) -> dict:
        return {"check": self.check, "severity": self.severity, "item": self.item, "file": self.file,
                "message": self.message, "field": self.field}


@dataclass(frozen=True)
class Declaration:
    """Which MiniCOSM a catalog is written in, and how the reader knows: `oes` (the key said so), `legacy` (an
    older key the manifest still reads) or `absent` (no key, and the manifest reads that as itself)."""
    minicosm: str
    major: int
    manifest: "Manifest"
    how: str
    key: str | None = None
    said: str | None = None

    @property
    def value(self) -> str:
        return f"{self.minicosm}/{self.major}"


# ---------------------------------------------------------------------------
# Manifests (`manifest: minicosm/0`)
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_DECL_RE = re.compile(r"^([a-z][a-z0-9-]*)/([0-9]+)$")


def _list(v: Any) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _strs(v: Any) -> list[str]:
    return [str(x) for x in _list(v) if isinstance(x, (str, int, float)) and not isinstance(x, bool)]


@dataclass
class Manifest:
    """One MiniCOSM manifest, read generically: the keys Comprise's manifest uses, plus the optional keys
    MacroCOSM 0.0.1 adds (`volume.single-file`, `module-file.items`, a kind's `required`, `closed-lists`,
    `links.rels`, `renderers[].lens`, `checks.severity`). `data` is the whole mapping, kept."""
    name: str
    title: str
    version: int
    path: Path | None
    data: dict = field(repr=False)

    def _block(self, key: str) -> dict:
        v = self.data.get(key)
        return v if isinstance(v, dict) else {}

    @property
    def declaration(self) -> dict:
        return self._block("declaration")

    @property
    def volume(self) -> dict:
        return self._block("volume")

    @property
    def envelope(self) -> dict:
        return self._block("envelope")

    @property
    def single_file(self) -> bool:
        return self.volume.get("single-file") is True

    @property
    def catalog_names(self) -> list[str]:
        """What the catalog file is called: names (`holotype.cosm`) or patterns (`<text>.cosm`)."""
        return _strs(self.volume.get("catalog"))

    def matches_catalog(self, filename: str) -> bool:
        for name in self.catalog_names:
            if fnmatch.fnmatchcase(filename, re.sub(r"<[^>]*>", "*", name)):
                return True
        return False

    @property
    def sentinels(self) -> tuple[str, ...]:
        return tuple(_strs(self.envelope.get("sentinels")) or ("none", "self"))

    @property
    def link_rels(self) -> list[str] | None:
        rels = self._block("links").get("rels")
        return _strs(rels) if isinstance(rels, list) else None

    def modules(self) -> list[str]:
        return [str(k) for k in self._block("modules")]

    def module(self, letter: str | None) -> dict:
        v = self._block("modules").get(letter)
        return v if isinstance(v, dict) else {}

    def kinds(self, module: str | None) -> dict[str, dict]:
        """The module's kinds, in manifest order: {kind: its spec mapping}."""
        k = self.module(module).get("kinds")
        if not isinstance(k, dict):
            return {}
        return {str(name): (spec if isinstance(spec, dict) else {}) for name, spec in k.items()}

    def kind(self, module: str | None, kind: str | None) -> dict | None:
        return self.kinds(module).get(kind) if kind else None

    def legacy_kinds(self, module: str | None) -> dict[str, str]:
        """Old kind names the manifest still reads, {old: new} (`tree.legacy-kinds`: firm -> brand)."""
        tree = self.module(module).get("tree")
        lk = tree.get("legacy-kinds") if isinstance(tree, dict) else None
        return {str(a): str(b) for a, b in lk.items()} if isinstance(lk, dict) else {}

    def refs(self, module: str | None, kind: str | None) -> list[str]:
        """The reference fields checked on an item of this kind: the envelope's, then the kind's own (dotted
        paths walk lists and mappings; `*` is every value of a mapping, and in such a wildcard field a value is a
        reference only when it is written as an id: EMF's `roles: {actor: E:person/ada, condition: "if it
        rains"}`). Deduplicated, in that order."""
        out = _strs(self.envelope.get("references"))
        for r in _strs((self.kind(module, kind) or {}).get("refs")):
            if r not in out:
                out.append(r)
        return out

    def required_fields(self, module: str | None = None, kind: str | None = None) -> list[str]:
        """The fields an item must carry: the kind's `required`, else the envelope's `required-in-<module>`
        (Comprise's P), else the envelope's `required`."""
        spec = self.kind(module, kind) if module else None
        if spec and isinstance(spec.get("required"), list):
            return _strs(spec["required"])
        env = self.envelope
        if module and isinstance(env.get(f"required-in-{module}"), list):
            return _strs(env[f"required-in-{module}"])
        return _strs(env.get("required")) or ["id", "type"]

    def closed_lists(self) -> dict[str, list]:
        """Every closed list the manifest gives, {field path: allowed values}: the envelope's status and
        visibility, provenance's modes and states, the `closed-lists` block, and `links.rels` as `links.rel`."""
        out: dict[str, list] = {}
        env = self.envelope
        for key in ("status", "visibility"):
            if isinstance(env.get(key), list):
                out[key] = list(env[key])
        prov = env.get("provenance")
        if isinstance(prov, dict):
            if isinstance(prov.get("modes"), list):
                out["provenance.mode"] = list(prov["modes"])
            if isinstance(prov.get("states"), list):
                out["provenance.state"] = list(prov["states"])
        for key, values in self._block("closed-lists").items():
            if isinstance(values, list):
                out[str(key)] = list(values)
        if self.link_rels is not None:
            out["links.rel"] = self.link_rels
        return out

    def lenses(self) -> list[dict]:
        """The renderers that carry a `lens`: [{id, kind, diagram, include, edges, shape, class-by, ...}]."""
        out = []
        for r in self.data.get("renderers") or []:
            if isinstance(r, dict) and isinstance(r.get("lens"), dict) and isinstance(r.get("id"), str):
                out.append({**r["lens"], "id": r["id"]})
        return out

    def checks(self) -> list[str]:
        """The check ids the manifest selects (`checks.load`, then `checks.envelope`), in order."""
        c = self._block("checks")
        out: list[str] = []
        for key in ("load", "envelope"):
            for x in _strs(c.get(key)):
                if x not in out:
                    out.append(x)
        return out

    def item_sources(self, module: str | None) -> list[tuple[str, str | None, bool]]:
        """Where a file's items are: [(key, kind for items without a type, one item?)]. `module-file.items` when
        the manifest says; otherwise Comprise's reading: the `nodes:` list everywhere, and in the products module
        (`checks.products-prefix`) the products key that names its root kind, or a legacy name for it
        (`brand:`, `firm:`), holds that one item."""
        mf = self._block("module-file")
        if isinstance(mf.get("items"), list):
            out = []
            for e in mf["items"]:
                if isinstance(e, dict) and isinstance(e.get("key"), str):
                    if e.get("module") is not None and module is not None and str(e["module"]) != module:
                        continue
                    kind = e.get("kind")
                    out.append((e["key"], str(kind) if isinstance(kind, str) else None, e.get("one") is True))
            return out
        out = []
        if module is not None and module == self._block("checks").get("products-prefix"):
            kinds, legacy = self.kinds(module), self.legacy_kinds(module)
            for k in _strs(mf.get("products-keys")):
                if k in kinds:
                    out.append((k, k, True))
                elif legacy.get(k) in kinds:
                    out.append((k, legacy[k], True))
        lists = [str(s["key"]) for s in _list(mf.get("shapes"))
                 if isinstance(s, dict) and isinstance(s.get("key"), str) and "list" in str(s.get("holds", ""))]
        out += [(k, None, False) for k in (lists or ["nodes"])]
        return out

    def none_shape(self) -> tuple[str, str, str]:
        """(key, value, reason key) of a module file that says its module is empty on purpose."""
        for s in _list(self._block("module-file").get("shapes")):
            if isinstance(s, dict) and "value" in s and isinstance(s.get("key"), str):
                return s["key"], str(s["value"]), str(s.get("with") or "reason")
        return "module", "none", "reason"

    @functools.cached_property
    def grammar(self) -> "_Grammar":
        return _Grammar(self)

    @functools.cached_property
    def layout(self) -> dict:
        """Where a folder volume keeps its files, read from `volume`: the part folders (`concerns:
        atoms/<concern>/`), the catalog key that declares them (the part id's word, plural: `atoms`), the module
        folders and the module-file pattern."""
        vol, g = self.volume, self.grammar
        lay: dict[str, Any] = {"parts": None, "parts_root": None, "parts_key": None, "files": "*.cosm",
                               "recursive": False, "case_insensitive": "module-folder-case" in vol}
        if g.part_level:
            t = vol.get(g.part_level + "s")
            ph = f"<{g.part_level}>"
            if isinstance(t, str) and ph in t:
                lay["parts"] = t.rstrip("/")
                lay["parts_root"] = t.split(ph, 1)[0].rstrip("/")
                word = (g.part_template or "").split("/", 1)[0]
                lay["parts_key"] = word + "s" if word and "<" not in word else None
        mf = vol.get("module-files")
        if isinstance(mf, str):
            pat = mf.split("<module folder>/", 1)[-1]
            lay["recursive"] = "**" in pat
            lay["files"] = pat.rsplit("/", 1)[-1] or "*.cosm"
        return lay


def load_manifest(path) -> Manifest | Refusal:
    """Read one `*.manifest.cosm`. A file that is not a `minicosm/0` manifest is refused, never raised."""
    p = Path(path)
    try:
        text = read_text(p)
    except (OSError, UnicodeDecodeError) as e:
        return Refusal(f"{p.name}: cannot read: {e}", file=str(p))
    data, forbidden, error = _parse(text)
    if error or forbidden:
        return Refusal(f"{p.name}: {error or forbidden[0]}", file=str(p))
    if not isinstance(data, dict):
        return Refusal(f"{p.name}: a manifest's top level is a mapping", file=str(p))
    if data.get("manifest") != MANIFEST_FORMAT:
        return Refusal(f"{p.name} is not a MiniCOSM manifest: it says manifest: {data.get('manifest')!r}; this "
                       f"reader reads {MANIFEST_FORMAT}", said=str(data.get("manifest")), file=str(p))
    name = data.get("name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        return Refusal(f"{p.name}: name must be a lowercase MiniCOSM name, not {name!r}", file=str(p))
    version = data.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        return Refusal(f"{p.name}: version must be an integer major version, not {version!r}", file=str(p))
    title = data.get("title") if isinstance(data.get("title"), str) else name
    return Manifest(name, title, version, p, data)


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

class Registry:
    """Every manifest in the given folders (default: the bundled `defaults/cosm/manifests/`), in registry order.
    A name already loaded keeps its first manifest; later duplicates and unreadable files are noted in
    `problems`, never raised."""

    def __init__(self, dirs: list[Path] | None = None):
        self.dirs = [DEFAULT_MANIFEST_DIR] if dirs is None else [Path(d) for d in dirs]
        self.problems: list[str] = []
        found: dict[str, Manifest] = {}
        for d in self.dirs:
            try:
                paths = sorted(d.glob(MANIFEST_GLOB)) if d.is_dir() else []
            except OSError as e:
                self.problems.append(f"{d}: cannot read: {e}")
                continue
            for p in paths:
                m = load_manifest(p)
                if isinstance(m, Refusal):
                    self.problems.append(m.message)
                elif m.name in found:
                    self.problems.append(f"{p}: a second manifest named {m.name}; the first ({found[m.name].path}) is kept")
                else:
                    found[m.name] = m
        order = [n for n in REGISTRY_ORDER if n in found] + sorted(n for n in found if n not in REGISTRY_ORDER)
        self.manifests: dict[str, Manifest] = {n: found[n] for n in order}

    def get(self, name: str) -> Manifest | None:
        return self.manifests.get(name)

    def known(self) -> str:
        return ", ".join(_decl_value(m) for m in self.manifests.values()) or "none (no manifests)"

    def find_catalog(self, folder: Path) -> Path | None:
        """The catalog file at a folder's root, by the names the manifests give, in registry order."""
        for m in self.manifests.values():
            for name in m.catalog_names:
                if "<" in name or "*" in name:
                    continue
                p = folder / name
                if p.is_file():
                    return p
        return None

    def identify(self, catalog: dict, *, filename: str | None = None) -> Declaration | Refusal:
        """Which MiniCOSM a catalog mapping is written in. An explicit `oes:` always decides, and an unknown
        MiniCOSM, an unknown major or an empty value is refused; otherwise the first manifest whose legacy key
        matches (registry order); otherwise the first whose `absent` rule claims a catalog with no key, among
        the manifests whose catalog name fits `filename` (all of them when no filename is given)."""
        what = filename or "the catalog"
        if not isinstance(catalog, dict):
            return Refusal(f"{what}: a catalog's top level is a mapping", file=filename)
        keys = []
        for m in self.manifests.values():
            k = str(m.declaration.get("key") or "oes")
            if k not in keys:
                keys.append(k)
        for key in keys or ["oes"]:
            if key not in catalog:
                continue
            v = catalog[key]
            said = (v.strip() or "(empty)") if isinstance(v, str) else ("(empty)" if v is None else repr(v))
            mt = _DECL_RE.match(v.strip()) if isinstance(v, str) else None
            m = self.manifests.get(mt.group(1)) if mt else None
            if m is not None and str(m.declaration.get("key") or "oes") == key and v == _decl_value(m):
                return Declaration(m.name, int(mt.group(2)), m, "oes", key, v)      # one spelling, as Comprise reads it
            if m is not None:
                why = f"this reader reads {m.title} as {_decl_value(m)} only"
            elif mt:
                why = f"it does not know the MiniCOSM {mt.group(1)!r}; it knows {self.known()}"
            else:
                why = f"a declaration is <minicosm>/<major>; this reader knows {self.known()}"
            return Refusal(f"{what} declares {key}: {said}, which this reader cannot read: {why}; nothing was "
                           "loaded", said=said, file=filename)
        for m in self.manifests.values():
            for leg in _list(m.declaration.get("legacy")):
                if not isinstance(leg, dict) or not isinstance(leg.get("key"), str) or leg["key"] not in catalog:
                    continue
                want = leg.get("value")
                got = catalog[leg["key"]]
                if want is None or _scalar_text(got) in _strs(want):
                    reads = str(leg.get("reads-as") or _decl_value(m))
                    mt = _DECL_RE.match(reads)
                    major = int(mt.group(2)) if mt else m.version
                    return Declaration(m.name, major, m, "legacy", leg["key"], _scalar_text(got))
        for m in self.manifests.values():
            absent = m.declaration.get("absent")
            if not isinstance(absent, str) or absent in ("refuse", "no", "none"):
                continue
            if filename is not None and not m.matches_catalog(filename):
                continue
            mt = _DECL_RE.match(absent)
            return Declaration(m.name, int(mt.group(2)) if mt else m.version, m, "absent")
        return Refusal(f"{what} declares no MiniCOSM: its first key should be oes: <minicosm>/<major> (this reader "
                       f"knows {self.known()}); nothing was loaded", file=filename)


def _decl_value(m: Manifest) -> str:
    v = m.declaration.get("value")
    return v if isinstance(v, str) and _DECL_RE.match(v) else f"{m.name}/{m.version}"


def _scalar_text(v: Any) -> str:
    """A legacy key's value as the manifest spells it: `cosm: 0.2` loads as a float and reads back '0.2'."""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip() if v is not None else ""


@functools.lru_cache(maxsize=1)
def default_registry() -> Registry:
    """The bundled manifests, loaded once per process."""
    return Registry()


# ---------------------------------------------------------------------------
# Ids: the grammar a manifest gives
# ---------------------------------------------------------------------------

_SEGMENT_DEFAULTS = {
    "part": r"[a-z0-9][a-z0-9.-]*",
    "kind": r"[a-z][a-z0-9-]*",
    "slug": r"[A-Za-z0-9](?:[A-Za-z0-9._@-]*[A-Za-z0-9_@-])?",
    "field": r"[A-Za-z0-9][A-Za-z0-9_-]*(?:\.[A-Za-z0-9][A-Za-z0-9_-]*|\[[0-9]+\])*",
}
_FIELD_STEP = re.compile(r"\.?([A-Za-z0-9][A-Za-z0-9_-]*)|\[([0-9]+)\]")
_RESERVED = frozenset(["con", "prn", "aux", "nul"] + [f"com{i}" for i in range(10)] + [f"lpt{i}" for i in range(10)])
_NON_ITEM_LEVELS = ("module", "kind", "item", "field")


def _compile(rx: Any, default: str) -> re.Pattern:
    if isinstance(rx, str):
        try:
            return re.compile(rx)
        except re.error:
            pass
    return re.compile(default)


@dataclass(frozen=True)
class _IdParts:
    module: str | None
    kind: str | None                 # None when the id has no kind (and no kind's own form matched)
    slug: str
    bare: str                        # the id without a part qualifier
    part: str | None = None          # the part's slug, when the id is qualified (atom/<concern>//...)
    form: str | None = None          # the kind whose own id form matched (P:<slug> -> brand)
    loose: bool = False              # only a bare `<slug>` form matched (a COSM tree's brand): any word would


class _Grammar:
    """A manifest's ids and paths, compiled once: the item form (`ids.item` when it is a regex, else
    `ids.item-form`), the kinds with an id form of their own (`P:<slug>`, `ext/<slug>`), the part ids and their
    qualifier (`atom/<concern>//`), and the path segments and levels."""

    def __init__(self, m: Manifest):
        ids, paths = m._block("ids"), m._block("paths")
        self.manifest = m
        self.modules = tuple(m.modules())
        self.levels = _strs(paths.get("levels")) or ["module", "kind", "item", "field"]
        first = self.levels[0]
        self.part_level = first if first not in _NON_ITEM_LEVELS else None
        seg = paths.get("segments") if isinstance(paths.get("segments"), dict) else {}
        mod_default = "(?:" + "|".join(map(re.escape, self.modules)) + ")" if self.modules else "[A-Z]"
        self.seg = {"module": _compile(seg.get("module"), mod_default),
                    "kind": _compile(seg.get("kind"), _SEGMENT_DEFAULTS["kind"]),
                    "slug": _compile(seg.get("slug"), _SEGMENT_DEFAULTS["slug"]),
                    "field": _compile(seg.get("field"), _SEGMENT_DEFAULTS["field"])}
        form = paths.get("form") if isinstance(paths.get("form"), str) else None
        self.path_form = (form or "/".join(f"<{lv}>" for lv in self.levels if lv != "field")).split("#", 1)[0]
        self.max_segments = len([lv for lv in self.levels if lv != "field"])

        # Parts (Comprise's concerns): their ids and the qualifier an item id may carry.
        self.part_template: str | None = None
        self.part_rx: re.Pattern | None = None
        qual = ""
        if self.part_level:
            ph = f"<{self.part_level}>"
            self.seg["part"] = _compile(seg.get(self.part_level), _SEGMENT_DEFAULTS["part"])
            for e in _list(paths.get("map")):
                if isinstance(e, dict) and e.get("path") == ph and isinstance(e.get("id"), str):
                    self.part_template = e["id"]
            self.part_template = self.part_template or f"{self.part_level}/{ph}"
            part_seg = self.seg["part"].pattern
            self.part_rx = _compile(ids.get(self.part_level),
                                    "^" + self._template(self.part_template, {ph: f"({part_seg})"}) + "$")
            qf = ids.get("qualified-form")
            prefix = qf.split("//", 1)[0] if isinstance(qf, str) and "//" in qf else self.part_template
            qual = "(?:" + self._template(prefix, {ph: f"(?P<part>{part_seg})"}) + "//)?"

        # The item form.
        self.item_form = str(ids.get("item-form") or "<module>:<kind>/<slug>")
        self.default_module = self.modules[0] if "<module>" not in self.item_form and len(self.modules) == 1 else None
        self.item_part_group: str | None = None
        given = ids.get("item")
        if isinstance(given, str) and given.startswith("^"):
            self.item_rx = _compile(given, r"^$.")
            extra = [g for g in self.item_rx.groupindex if g not in ("module", "rest", "kind", "slug")]
            self.item_part_group = extra[0] if extra else None
        else:
            tail = "<kind>/<slug>"
            head = self.item_form[:-len(tail)] if self.item_form.endswith(tail) else ""
            self.item_rx = re.compile("^" + qual + self._template(head, {"<module>": "(?P<module>[A-Z][A-Za-z0-9]*)"})
                                      + r"(?P<rest>\S+)$")
            self.item_part_group = "part" if qual else None

        # Kinds with an id form of their own, most specific first; a bare `<slug>` form last.
        custom = []
        for mod in self.modules:
            for kind, spec in m.kinds(mod).items():
                t = spec.get("id")
                if not isinstance(t, str) or "<slug>" not in t:
                    continue
                t = t.replace("<module>", mod).replace("<kind>", kind)
                literal = t.split("<slug>", 1)[0]
                slug_rx = r"(?P<slug>[^/\s:]+)" if not literal else r"(?P<slug>[^/\s]+)"
                rx = re.compile("^" + qual + self._template(t, {"<slug>": slug_rx}) + "$")
                custom.append((len(literal), rx, mod, kind))
        self.custom = [(rx, mod, kind, n == 0) for n, rx, mod, kind in sorted(custom, key=lambda c: -c[0])]

        # Other id forms the manifest names (Comprise's vendor/<domain>/<slug>): references the reader leaves alone.
        self.other_rx = [_compile(v, r"^$.") for k, v in ids.items()
                         if k not in ("item", self.part_level) and isinstance(v, str) and v.startswith("^")]

    @staticmethod
    def _template(text: str, holes: dict[str, str]) -> str:
        """A template as a regex body: literal text escaped, each named hole replaced by its pattern."""
        out, i = [], 0
        for mt in re.finditer(r"<[^>]+>", text):
            out.append(re.escape(text[i:mt.start()]))
            out.append(holes.get(mt.group(0), r"[^/\s]+"))
            i = mt.end()
        out.append(re.escape(text[i:]))
        return "".join(out)

    def parse(self, s: Any) -> _IdParts | None:
        """An id -> its parts, by spelling alone; None when it is not an id in this MiniCOSM."""
        if not isinstance(s, str) or not s:
            return None
        for rx, mod, kind, loose in self.custom:
            mt = rx.match(s)
            if mt:
                part = mt.groupdict().get("part")
                return _IdParts(mod, kind, mt.group("slug"), s.split("//", 1)[1] if part else s, part, kind, loose)
        mt = self.item_rx.match(s)
        if not mt:
            return None
        gd = mt.groupdict()
        part = gd.get(self.item_part_group) if self.item_part_group else None
        module = gd.get("module") or self.default_module
        rest = gd.get("rest")
        if rest is None:
            kind, slug = gd.get("kind"), gd.get("slug") or ""
        elif "/" in rest:
            kind, slug = rest.split("/", 1)
        else:
            kind, slug = None, rest
        return _IdParts(module, kind, slug, s.split("//", 1)[1] if part else s, part)

    def is_part_id(self, s: Any) -> bool:
        return bool(self.part_rx and isinstance(s, str) and self.part_rx.match(s))

    def part_id(self, slug: str) -> str:
        return (self.part_template or "").replace(f"<{self.part_level}>", slug)

    def part_slug(self, part_id: str | None) -> str | None:
        mt = self.part_rx.match(part_id) if (self.part_rx and isinstance(part_id, str)) else None
        if not mt:
            return None
        groups = [g for g in mt.groups() if g]
        return groups[0] if groups else None

    def item_id(self, module: str, kind: str, slug: str) -> str:
        """The id a (module, kind, slug) respells: the kind's own form when it has one, else the item form."""
        spec = self.manifest.kind(module, kind) or {}
        t = spec.get("id") if isinstance(spec.get("id"), str) and "<slug>" in spec["id"] else self.item_form
        return t.replace("<module>", module).replace("<kind>", kind).replace("<slug>", slug)


def parse_id(manifest: Manifest, s: Any) -> dict | None:
    """An id -> {module, kind, slug, part, bare} in this manifest's grammar, or None. Pure: no volume."""
    p = manifest.grammar.parse(s)
    if p is None:
        return None
    return {"module": p.module, "kind": p.form or p.kind, "slug": p.slug, "part": p.part, "bare": p.bare}


# ---------------------------------------------------------------------------
# Volumes
# ---------------------------------------------------------------------------

@dataclass
class Item:
    """A row: one mapping with a string `id`. `data` is the mapping as written, every field kept (P's brand
    gains `type: brand`, as Comprise's loader gives it). `part` is the part's id (`atom/meadow`) or None."""
    id: str
    module: str | None
    kind: str | None
    part: str | None
    file: str
    data: dict = field(repr=False)

    @property
    def key(self) -> str:
        """The item's key in `Volume.items`: its id, qualified with its part where the volume has parts."""
        return f"{self.part}//{self.id.split('//', 1)[-1]}" if self.part else self.id

    @property
    def name(self) -> str:
        n = self.data.get("name")
        return n.strip() if isinstance(n, str) and n.strip() else self.id


@dataclass
class Part:
    """One top-level part of a folder volume (Comprise: a concern, `atoms/<concern>/`)."""
    id: str
    slug: str
    folder: str
    modules: dict = field(default_factory=dict)      # letter -> module folder, relative
    none: dict = field(default_factory=dict)         # letter -> the reason a module file gives for `module: none` ('' when none given)
    none_file: dict = field(default_factory=dict)    # letter -> the file that said so
    readme: list = field(default_factory=list)       # letters whose folder holds a README


@dataclass
class Volume:
    """One loaded volume. `items` is keyed by `Item.key`, in load order (catalog, then files in path order,
    items in file order). `problems` are load problems; the checks are `lint(volume)`. A refused volume has
    `refused` set, `manifest` None and nothing loaded."""
    path: Path
    minicosm: str | None = None
    major: int | None = None
    manifest: Manifest | None = None
    catalog: dict = field(default_factory=dict)
    items: dict = field(default_factory=dict)
    parts: dict = field(default_factory=dict)
    files: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    refused: Refusal | None = None
    declaration: Declaration | None = None
    root: Path | None = None                         # the folder the volume's relative paths start from
    catalog_file: str = ""

    @property
    def oes(self) -> str | None:
        return f"{self.minicosm}/{self.major}" if self.minicosm else None

    @property
    def id(self) -> str:
        """The catalog's id, else the manifest's `catalog.id-absent` with the folder name (holotype/<folder>)."""
        cid = self.catalog.get("id")
        if isinstance(cid, str) and cid.strip():
            return cid.strip()
        folder = (self.root or self.path).name
        absent = self.manifest._block("catalog").get("id-absent") if self.manifest else None
        if isinstance(absent, str) and "<" in absent:
            return re.sub(r"<[^>]*>", folder, absent, count=1)
        return folder

    @property
    def database(self) -> str:
        """The volume's name in a qualified URI: the catalog id without the literal prefix of the manifest's
        `catalog.id` (holotype/, canon/, emf/), so a project catalog's is `~<slug>`."""
        cid = self.id
        tmpl = self.manifest._block("catalog").get("id") if self.manifest else None
        prefix = tmpl.split("<", 1)[0] if isinstance(tmpl, str) and "<" in tmpl else ""
        return cid[len(prefix):] if prefix and cid.startswith(prefix) and len(cid) > len(prefix) else cid

    @property
    def name(self) -> str:
        n = self.catalog.get("name")
        if isinstance(n, str) and n.strip():
            return n.strip()
        first = next(iter(self.items.values()), None)
        return first.name if first is not None else (self.root or self.path).name

    def item(self, ref: str) -> Item | None:
        """An item by key, or by bare id when exactly one part holds it."""
        if ref in self.items:
            return self.items[ref]
        hits = [it for it in self.items.values() if it.id == ref]
        return hits[0] if len(hits) == 1 else None

    def by_module(self) -> dict[str, dict[str, list[Item]]]:
        """{module: {kind: [items]}} in manifest order (modules and kinds with no items left out)."""
        out: dict[str, dict[str, list[Item]]] = {}
        order = self.manifest.modules() if self.manifest else []
        for it in self.items.values():
            out.setdefault(it.module or "", {}).setdefault(it.kind or "", []).append(it)
        rank = {m: i for i, m in enumerate(order)}
        return dict(sorted(out.items(), key=lambda kv: rank.get(kv[0], len(rank))))


def _read_doc(path: Path, rel: str, problems: list[Problem]) -> dict | None:
    """One .cosm file as a mapping; None (and a load problem) when it cannot be read or is not one."""
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError) as e:
        problems.append(Problem("load", "error", "", rel, f"cannot read: {e}"))
        return None
    data, forbidden, error = _parse(text)
    problems += [Problem("load", "error", "", rel, msg) for msg in forbidden]
    if error:
        problems.append(Problem("load", "error", "", rel, error))
        return None
    if data is None:
        return {}
    if not isinstance(data, dict):
        problems.append(Problem("load", "error", "", rel, "top level must be a mapping"))
        return None
    return data


def _items_in(m: Manifest, module: str | None, doc: dict, rel: str,
              problems: list[Problem]) -> list[tuple[dict, str | None]]:
    """(data, kind for items without a type) for every item a file declares, in file order."""
    out: list[tuple[dict, str | None]] = []
    root_taken = False
    for key, kind, one in m.item_sources(module):
        v = doc.get(key)
        if one:
            if root_taken or not isinstance(v, dict):
                continue
            root_taken = True
            if not isinstance(v.get("id"), str):
                problems.append(Problem("load", "error", "", rel, f"{key} has no string id"))
                continue
            out.append((dict(v, type=kind) if kind else v, kind))
            continue
        if v is None:
            continue
        if not isinstance(v, list):
            problems.append(Problem("load", "error", "", rel, f"{key} must be a list"))
            continue
        for i, n in enumerate(v):
            if not isinstance(n, dict) or not isinstance(n.get("id"), str):
                problems.append(Problem("load", "error", "", rel, f"{key}[{i}] has no string id"))
                continue
            out.append((n, kind))
    return out


def _add_items(vol: Volume, m: Manifest, doc: dict, rel: str, module: str | None, part: str | None) -> None:
    g = m.grammar
    for data, implied in _items_in(m, module, doc, rel, vol.problems):
        nid = data["id"]
        p = g.parse(nid)
        mod = module or (p.module if p else None) or g.default_module
        t = data.get("type")
        kind = t if isinstance(t, str) else (implied or ((p.form or p.kind) if p else None))
        it = Item(nid, mod, kind, part, rel, data)
        first = vol.items.get(it.key)
        if first is not None:
            vol.problems.append(Problem("duplicate-id", "error", it.key, rel,
                                        f"duplicate id {nid} (first in {first.file}); the first is kept"))
            continue
        vol.items[it.key] = it


def _module_files(folder: Path, pattern: str, recursive: bool, base: Path) -> list[Path]:
    found = folder.rglob(pattern) if recursive else folder.glob(pattern)
    return sorted((p for p in found if p.is_file()), key=lambda p: p.relative_to(base).as_posix().lower())


def _load_part(vol: Volume, m: Manifest, part: Part, folder: Path) -> None:
    lay, root = m.layout, vol.root
    nkey, nvalue, nreason = m.none_shape()
    dirs: dict[str, Path] = {}
    for d in sorted(folder.iterdir(), key=lambda p: p.name):
        if d.is_dir():
            letter = d.name.upper() if lay["case_insensitive"] else d.name
            if letter in m.modules():
                dirs.setdefault(letter, d)
    for letter in m.modules():
        d = dirs.get(letter)
        if d is None:
            continue
        part.modules[letter] = d.relative_to(root).as_posix()
        for f in _module_files(d, lay["files"], lay["recursive"], d):
            rel = f.relative_to(root).as_posix()
            vol.files.append(rel)
            doc = _read_doc(f, rel, vol.problems)
            if doc is None:
                continue
            if doc.get(nkey) == nvalue:
                reason = doc.get(nreason)
                part.none[letter] = str(reason) if reason not in (None, "") else ""
                part.none_file[letter] = rel
            _add_items(vol, m, doc, rel, letter, part.id)
        if any(p.is_file() and p.name.upper().startswith("README") for p in d.iterdir()):
            part.readme.append(letter)


def _load_folder(vol: Volume, m: Manifest) -> None:
    """A folder volume: parts and module folders when the manifest has them (Comprise), else every module file
    at the root (a COSM tree), the catalog included."""
    lay, g, root = m.layout, m.grammar, vol.root
    if g.part_level and lay["parts"]:
        ph = f"<{g.part_level}>"
        declared: list[str] = []
        key = lay["parts_key"]
        for a in _list(vol.catalog.get(key)) if key else []:
            aid = a if isinstance(a, str) else (a.get("id") if isinstance(a, dict) else None)
            if not g.is_part_id(aid):
                vol.problems.append(Problem("load", "error", "", vol.catalog_file,
                                            f"{key} entry {a!r} is not a {g.part_template} id"))
                continue
            declared.append(aid)
        for aid in declared:
            slug = g.part_slug(aid) or ""
            rel = lay["parts"].replace(ph, slug)
            folder = root / rel
            if not folder.is_dir():
                vol.problems.append(Problem("load", "error", aid, "", f"folder {rel} missing"))
                continue
            part = Part(aid, slug, rel)
            vol.parts[aid] = part
            _load_part(vol, m, part, folder)
        proot = root / lay["parts_root"] if lay["parts_root"] else root
        if proot.is_dir() and lay["parts_root"]:
            for d in sorted(proot.iterdir(), key=lambda p: p.name):
                if d.is_dir() and not d.name.startswith(".") and g.part_id(d.name) not in vol.parts \
                        and g.part_id(d.name) not in declared:
                    vol.problems.append(Problem("load", "error", "", f"{lay['parts_root']}/{d.name}",
                                                f"folder present but not declared in {vol.catalog_file}"))
        return
    for f in _module_files(root, lay["files"], lay["recursive"], root):
        rel = f.relative_to(root).as_posix()
        if rel == vol.catalog_file:
            doc: dict | None = vol.catalog
        else:
            vol.files.append(rel)
            doc = _read_doc(f, rel, vol.problems)
        if doc is not None:
            _add_items(vol, m, doc, rel, None, None)


def load_volume(path, registry: Registry | None = None) -> Volume:
    """Load a volume: a folder with a catalog at its root (a Holotype, a COSM tree, a Canon volume) or a single
    catalog file (`canon.cosm`, an EMF twin, any single-file volume; or a folder volume's catalog, which loads
    its folder). Never raises on bad input: what does not load is in `problems`, a declaration this reader
    cannot read is `refused`."""
    reg = registry if registry is not None else default_registry()
    p = Path(path).absolute()
    try:
        return _load_volume(p, reg)
    except OSError as e:                            # an unreadable folder or file: a refusal, never a raise
        msg = f"{p}: cannot read: {e}"
        return Volume(p, root=p if p.suffix != ".cosm" else p.parent, refused=Refusal(msg),
                      problems=[Problem("load", "error", "", "", msg)])


def load_volume_text(text: str, *, filename: str, registry: Registry | None = None) -> Volume:
    """A volume from one catalog's text, as `load_volume` would read a file named `filename` holding it: a
    single-file MiniCOSM loads whole; a folder MiniCOSM loads the catalog alone (a flat layout reads its items from
    the catalog, as from any module file at the root; a layout with parts reports each declared part's folder as
    missing). Nothing is written to disk. `filename` matters only where the manifests let a catalog without a
    declaration be claimed by its name. Never raises on bad input."""
    reg = registry if registry is not None else default_registry()
    rel = Path(str(filename or "")).name or "inline.cosm"
    vol = Volume(Path(rel), catalog_file=rel, files=[rel])
    data, forbidden, error = _parse(text if isinstance(text, str) else "")
    vol.problems += [Problem("load", "error", "", rel, msg) for msg in forbidden]
    if error or (data is not None and not isinstance(data, dict)):
        vol.problems.append(Problem("load", "error", "", rel, error or "top level must be a mapping"))
        vol.refused = Refusal(f"{rel} could not be read, so the MiniCOSM it is written in is unknown; nothing was "
                              "loaded", file=rel)
        return vol
    doc = data or {}
    decl = reg.identify(doc, filename=rel)
    if isinstance(decl, Refusal):
        vol.catalog = {k: doc[k] for k in ("id", "name", *DECLARATION_KEYS) if k in doc}
        vol.refused = decl
        vol.problems.append(Problem("load", "error", "", rel, decl.message))
        return vol
    m = decl.manifest
    vol.manifest, vol.minicosm, vol.major, vol.declaration, vol.catalog = m, decl.minicosm, decl.major, decl, doc
    g, lay = m.grammar, m.layout
    if m.single_file:
        _add_items(vol, m, doc, rel, None, None)
    elif g.part_level and lay["parts"]:
        key = lay["parts_key"]
        for a in _list(doc.get(key)) if key else []:
            aid = a if isinstance(a, str) else (a.get("id") if isinstance(a, dict) else None)
            if g.is_part_id(aid):
                folder = lay["parts"].replace(f"<{g.part_level}>", g.part_slug(aid) or "")
                vol.problems.append(Problem("load", "error", aid, "", f"folder {folder} missing (only the catalog "
                                                                      "was given)"))
    elif fnmatch.fnmatch(rel, lay["files"]):
        _add_items(vol, m, doc, rel, None, None)
    return vol


def _load_volume(p: Path, reg: Registry) -> Volume:
    if p.is_dir():
        cat = reg.find_catalog(p)
        if cat is None:
            names = sorted({n for m in reg.manifests.values() for n in m.catalog_names if "<" not in n})
            msg = f"no catalog in {p.name}/: looked for {', '.join(names) or 'nothing (no manifests)'}"
            return Volume(p, root=p, refused=Refusal(msg), problems=[Problem("load", "error", "", "", msg)])
    elif p.is_file():
        cat = p
    else:
        msg = f"{p}: no such file or folder"
        return Volume(p, root=p.parent, refused=Refusal(msg), problems=[Problem("load", "error", "", "", msg)])
    root, rel = cat.parent, cat.name
    vol = Volume(cat, root=root, catalog_file=rel, files=[rel])
    doc = _read_doc(cat, rel, vol.problems)
    if doc is None:
        vol.refused = Refusal(f"{rel} could not be read, so the MiniCOSM it is written in is unknown; nothing was "
                              "loaded", file=rel)
        return vol
    decl = reg.identify(doc, filename=rel)
    if isinstance(decl, Refusal):
        vol.catalog = {k: doc[k] for k in ("id", "name", *DECLARATION_KEYS) if k in doc}
        vol.refused = decl
        vol.problems.append(Problem("load", "error", "", rel, decl.message))
        return vol
    m = decl.manifest
    vol.manifest, vol.minicosm, vol.major, vol.declaration, vol.catalog = m, decl.minicosm, decl.major, decl, doc
    if m.single_file:
        _add_items(vol, m, doc, rel, None, None)
    else:
        vol.path = root
        try:
            _load_folder(vol, m)
        except OSError as e:                        # keep what loaded; say what did not
            vol.problems.append(Problem("load", "error", "", "", f"cannot read part of the folder: {e}"))
    return vol


# ---------------------------------------------------------------------------
# Paths and URIs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Address:
    """What a path names, from its spelling alone. `level` is `volume`, the part level (Comprise: `concern`),
    `module`, `kind`, `item`, `field`, or another form the manifest maps (`vendor`). `id` is the id the path
    respells (a part's, or an item's, bare), None for a module or a kind: the path is their only name."""
    level: str
    path: str
    id: str | None = None
    part: str = ""                   # the part's slug
    module: str = ""
    kind: str = ""
    slug: str = ""
    field: str = ""
    database: str = ""               # set by a qualified form

    @property
    def item_path(self) -> str:
        return self.path.split("#", 1)[0]


class _Refused(Exception):
    pass


def _segment_why(seg: str, what: str, rx: re.Pattern) -> str | None:
    if seg == "":
        return "an empty segment (two slashes together)"
    if seg in (".", ".."):
        return f"a segment {seg!r} is not allowed: a path never climbs or stays where it is"
    if seg.endswith("."):
        return f"the segment {seg!r} ends in a dot, which Windows drops"
    if seg.lower() in _RESERVED or seg.split(".", 1)[0].lower() in _RESERVED:
        return f"the segment {seg!r} is a reserved name on Windows" + (", alone or before a dot" if "." in seg else "")
    if not rx.fullmatch(seg):
        return f"{seg!r} is not a {what}"
    return None


def _text_why(s: str) -> str | None:
    if not s:
        return "it is empty"
    if not s.isascii():
        return "only ASCII characters are allowed"
    if "%" in s:
        return "percent-encoding is not allowed: write the path as it is spelled"
    if "\\" in s:
        return "a backslash is not allowed: the only separator is /"
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in s):
        return "whitespace and control characters are not allowed"
    if ":" in s:
        return "a path never has a colon (an id may have one)"
    if s.startswith("/"):
        return "a leading slash is not allowed: a path is always absolute within its volume"
    if s.endswith("/") or s.split("#", 1)[0].endswith("/"):
        return "a trailing slash is not allowed"
    return None


def _parse_path(m: Manifest, s: str) -> Address:
    g = m.grammar

    def refuse(why: str):
        raise _Refused(f"refused {s!r}: {why}")

    why = _text_why(s)
    if why:
        refuse(why)
    body, fld = s, ""
    if "#" in s:
        body, fld = s.split("#", 1)
        if "#" in fld:
            refuse("more than one #")
        if not fld:
            refuse("nothing after #: name a field, or leave the # out")
        if not g.seg["field"].fullmatch(fld):
            refuse(f'{fld!r} is not a field path (keys joined by ".", list positions as [n])')
    segs = body.split("/")
    # Another form the manifest maps under a literal first segment (Comprise's vendor/<domain>/<slug>).
    for e in _list(m._block("paths").get("map")):
        tp = e.get("path") if isinstance(e, dict) else None
        if not isinstance(tp, str) or tp.startswith("<"):
            continue
        tsegs = tp.split("/")
        if tsegs[0] in g.modules or segs[0] != tsegs[0] or (len(segs) > 1 and segs[1] in g.modules) \
                or not any("<" in t for t in tsegs):
            continue
        if fld:
            refuse(f"a {tsegs[0]} path names a whole: nothing follows {tp}")
        if len(segs) != len(tsegs):
            refuse(f"a {tsegs[0]} path is {tp}, and nothing below it")
        for sg, t in zip(segs[1:], tsegs[1:]):
            w = _segment_why(sg, f"{t} segment", g.seg.get("part", re.compile(_SEGMENT_DEFAULTS["part"])))
            if w:
                refuse(w)
        return Address(tsegs[0], body, body)
    for sg in segs:
        if sg == "" or sg in (".", ".."):
            refuse(_segment_why(sg, "segment", g.seg["slug"]) or "")
    if len(segs) > g.max_segments:
        refuse(f"too many segments: a path is {g.path_form}")
    vals: dict[str, str] = {}
    levels = [lv for lv in g.levels if lv != "field"]
    for level, sg in zip(levels, segs):
        if level == g.part_level:
            w = _segment_why(sg, f"{level} (lowercase letters, digits, dots and hyphens)", g.seg["part"])
        elif level == "module":
            w = None if sg in g.modules else (f"{sg!r} is not a module: the modules are {', '.join(g.modules)}, "
                                               "as written")
        elif level == "kind":
            w = _segment_why(sg, "kind", g.seg["kind"])
            if w is None and sg not in m.kinds(vals.get("module", g.default_module)):
                mod = vals.get("module", g.default_module)
                w = (f"{sg!r} is not a kind of {mod} ({m.module(mod).get('name', mod)}); its kinds are "
                     f"{', '.join(m.kinds(mod))}")
        else:
            w = _segment_why(sg, 'slug (ASCII letters, digits, ".", "_", "@" and "-", never ending in ".")',
                             g.seg["slug"])
        if w:
            refuse(w)
        vals[level] = sg
    reached = levels[len(segs) - 1]
    if fld and reached != "item":
        refuse("a field follows only an item")
    module = vals.get("module", g.default_module or "")
    if reached == g.part_level:
        return Address(reached, body, g.part_id(vals[reached]), part=vals[reached])
    if reached in ("module", "kind"):
        return Address(reached, body, None, vals.get(g.part_level or "", ""), module, vals.get("kind", ""))
    nid = g.item_id(module, vals["kind"], vals["item"])
    return Address("field" if fld else "item", s, nid, vals.get(g.part_level or "", ""), module, vals["kind"],
                   vals["item"], fld)


def parse_path(volume: Volume, path: Any) -> Address | Refusal:
    """A path, or a qualified URI (`oes:<minicosm>/<database>/<path>`), -> its Address, from its spelling alone;
    a Refusal saying why when it is malformed (the manifest's refused set: a leading or trailing slash, `.`,
    `..`, percent-encoding, a backslash, whitespace, a colon, non-ASCII, a dot at a segment's end, a second `#`,
    an undeclared module or kind, too many segments, a Windows reserved name)."""
    m = volume.manifest
    if m is None:
        return Refusal(f"refused {path!r}: the volume was not loaded")
    if not isinstance(path, str):
        return Refusal(f"refused {path!r}: a path is text")
    database = ""
    s = path
    if s.startswith("oes:"):
        head = f"oes:{volume.minicosm}/"
        if not s.startswith(head):
            other = s[4:].split("/", 1)[0]
            return Refusal(f"refused {path!r}: it names the MiniCOSM {other!r}; this volume is {volume.oes}")
        database, _, s = s[len(head):].partition("/")
        if database != volume.database:
            return Refusal(f"refused {path!r}: it names the database {database!r}; this one is {volume.database!r}")
        if not s:
            if path.endswith("/"):
                return Refusal(f"refused {path!r}: a trailing slash is not allowed")
            return Address("volume", "", volume.id, database=database)
    try:
        a = _parse_path(m, s)
    except _Refused as e:
        return Refusal(str(e), said=path)
    return Address(a.level, a.path, a.id, a.part, a.module, a.kind, a.slug, a.field, database) if database else a


def item_path(volume: Volume, item: Item) -> str:
    """An item's path: its id respelled through the manifest's levels (`meadow/P/brand/meadow`,
    `V/file/notes-md`); '' when the id has no path (a slug outside the path set, a kind the module does not
    declare). Pure: no lookup beyond the manifest."""
    m = volume.manifest
    if m is None:
        return ""
    g = m.grammar
    p = g.parse(item.id)
    if p is None:
        return ""
    module = p.module or item.module
    kind = p.form or p.kind
    spec = m.kind(module, kind) if module in g.modules else None
    if spec is None or (isinstance(spec.get("id"), str) and p.form != kind):
        return ""
    segs = []
    if g.part_level:
        if p.part and item.part and g.part_id(p.part) != item.part:
            return ""                               # an id qualified with another part names no item here
        slug = p.part or g.part_slug(item.part)
        if not slug or _segment_why(slug, "", g.seg["part"]):
            return ""
        segs.append(slug)
    if "module" in g.levels:
        segs.append(module)
    if _segment_why(kind, "", g.seg["kind"]) or _segment_why(p.slug, "", g.seg["slug"]):
        return ""
    return "/".join(segs + [kind, p.slug])


def field_value(data: Any, fpath: str) -> tuple[bool, Any]:
    """(found, value) at a field path inside an item's data: keys by ".", list positions by [n] from zero."""
    v = data
    for mt in _FIELD_STEP.finditer(fpath):
        key, idx = mt.group(1), mt.group(2)
        if key is not None:
            if not isinstance(v, dict):
                return False, None
            if key in v:
                v = v[key]
            elif key.isdigit() and int(key) in v:
                v = v[int(key)]
            else:
                return False, None
        else:
            i = int(idx)
            if not isinstance(v, list) or i >= len(v):
                return False, None
            v = v[i]
    return True, v


def _key_for(volume: Volume, a: Address) -> str | None:
    g = volume.manifest.grammar
    if a.id is None:
        return None
    return f"{g.part_id(a.part)}//{a.id}" if g.part_level else a.id


def resolve_path(volume: Volume, path: Any) -> Item | tuple[Item, Any] | None:
    """A path (or qualified URI) -> the Item it names, or (Item, value) for a field; None when it is
    malformed, names nothing there, or names a level that is not an item (see `items_under`)."""
    a = parse_path(volume, path)
    if isinstance(a, Refusal) or a.level not in ("item", "field"):
        return None
    it = volume.items.get(_key_for(volume, a) or "")
    if it is None:
        return None
    if a.level == "item":
        return it
    found, v = field_value(it.data, a.field)
    return (it, v) if found else None


def items_under(volume: Volume, path: Any) -> list[Item]:
    """Every item a path names or holds: a part's, a module's, a kind's items in load order, or [the item]."""
    a = parse_path(volume, path)
    if isinstance(a, Refusal):
        return []
    if a.level in ("item", "field"):
        it = volume.items.get(_key_for(volume, a) or "")
        return [it] if it is not None else []
    if a.level == "volume":
        return list(volume.items.values())
    prefix = a.item_path + "/"
    return [it for it in volume.items.values() if item_path(volume, it).startswith(prefix)]


def qualified_uri(volume: Volume, item: Item | None = None) -> str:
    """`oes:<minicosm>/<database>/<path>` for an item, `oes:<minicosm>/<database>` for the volume; '' when the
    item has no path. The database is the catalog id without its prefix (Comprise: holotype/<x> -> x; Canon:
    canon/<volume> -> <volume>, a project's ~<slug>; EMF: emf/<x> -> x)."""
    if volume.manifest is None:
        return ""
    base = f"oes:{volume.minicosm}/{volume.database}"
    if item is None:
        return base
    p = item_path(volume, item)
    return f"{base}/{p}" if p else ""


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------

def walk_path(value: Any, fpath: str) -> Iterator[Any]:
    """Every value at a dotted field path, descending into lists at each step; `*` is every value of a
    mapping (`roles.*`). A list at the end yields its elements."""
    for _, v in _walk_labelled(value, fpath):
        yield v


def _walk_labelled(value: Any, fpath: str, label: str | None = None) -> Iterator[tuple[str, Any]]:
    """(label, value) pairs for walk_path: the label is the path, or the key `*` matched."""
    head, _, tail = fpath.partition(".")
    if isinstance(value, list):
        for v in value:
            yield from _walk_labelled(v, fpath, label)
        return
    if not isinstance(value, dict):
        return
    if head == "*":
        pairs = [(str(k), v) for k, v in value.items()]
    elif head in value:
        pairs = [(label or "", value[head])]
    else:
        return
    for lab, v in pairs:
        lab = lab or label or ""
        if tail:
            yield from _walk_labelled(v, tail, lab or None)
        elif isinstance(v, list):
            for x in v:
                yield (lab, x)
        else:
            yield (lab, v)


def is_pending(v: Any) -> bool:
    return isinstance(v, dict) and "pending" in v


def walk_pending(o: Any, fpath: str = "") -> Iterator[tuple[str, Any]]:
    """(field path, question) for every open question in an item: `{pending: "..."}` where a value would go,
    or `pending:` on the item itself (field path `node`)."""
    if isinstance(o, dict):
        if "pending" in o:
            yield (fpath or WHOLE_ITEM, o["pending"])
        for k, v in o.items():
            if k != "pending":
                yield from walk_pending(v, f"{fpath}.{k}" if fpath else str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk_pending(v, f"{fpath}[{i}]")


def _resolve(volume: Volume, from_item: Item | None, ref: Any) -> Item | Part | None:
    if isinstance(ref, dict):
        ref = ref.get("to") or ref.get("id")
    m = volume.manifest
    if m is None or not isinstance(ref, str) or ref in m.sentinels:
        return None
    g = m.grammar
    if g.is_part_id(ref):
        return volume.parts.get(ref)
    p = g.parse(ref)
    if p is None:
        return None
    if g.part_level:
        part = g.part_id(p.part) if p.part else (from_item.part if from_item else None)
        return volume.items.get(f"{part}//{p.bare}") if part else None
    return volume.items.get(p.bare)


def resolve_ref(volume: Volume, from_item: Item | None, ref: Any) -> Item | None:
    """The item a reference names, read from `from_item` (a bare id resolves in its part): an id string or a
    typed link `{rel, to}`. None for a sentinel, an open question, a part, or nothing there."""
    hit = _resolve(volume, from_item, ref)
    return hit if isinstance(hit, Item) else None


# ---------------------------------------------------------------------------
# The generic checks
# ---------------------------------------------------------------------------

@dataclass
class Report:
    """What `lint` found. `pending` is (item key, field path, question) for every open question; `not_run` the
    check ids the manifest lists that this version does not implement (Comprise's own rules need Comprise);
    `checks` the ids that ran. `ok` is no error."""
    volume: Volume = field(repr=False)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    pending: list = field(default_factory=list)
    not_run: list = field(default_factory=list)
    checks: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def problems(self) -> list[Problem]:
        return self.errors + self.warnings + self.notes

    def add(self, p: Problem) -> None:
        {"error": self.errors, "warning": self.warnings}.get(p.severity, self.notes).append(p)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "minicosm": self.volume.oes,
                "refused": str(self.volume.refused) if self.volume.refused is not None else None,
                "errors": [p.to_dict() for p in self.errors], "warnings": [p.to_dict() for p in self.warnings],
                "notes": [p.to_dict() for p in self.notes],
                "pending": [{"item": i, "field": f, "question": jsonable(q)} for i, f, q in self.pending],
                "not_run": list(self.not_run), "checks": list(self.checks)}


_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _is_date(v: Any) -> bool:
    """A date where a reference may be written (Comprise's `at:` on a filing): not a reference."""
    if isinstance(v, (_dt.date, _dt.datetime)):
        return True
    if isinstance(v, str) and _DATE_PREFIX.match(v):
        try:
            _dt.date.fromisoformat(v[:10])
            return True
        except ValueError:
            return False
    return False


def _not_run(m: Manifest) -> list[str]:
    c = m._block("checks")
    out = [x for x in m.checks() if x not in CHECKS]
    prefix = c.get("products-prefix")
    for key in ("products", "equilibrium"):
        for x in _strs(c.get(key)):
            name = f"{prefix} {x}" if isinstance(prefix, str) else x
            if name not in out:
                out.append(name)
    for r in _list(c.get("rules")):
        if isinstance(r, dict) and "id" in r:
            out.append(f"rule {r['id']}")
    return out


class _Lint:
    def __init__(self, volume: Volume, rep: Report):
        self.v, self.rep = volume, rep
        self.m: Manifest = volume.manifest
        self.g = self.m.grammar
        self.sel = set(rep.checks)
        override = self.m._block("checks").get("severity")
        self.sev = dict(SEVERITY, **({str(k): str(v) for k, v in override.items()} if isinstance(override, dict) else {}))
        self.closed = self.m.closed_lists()
        prov = self.m.envelope.get("provenance")
        self.state_default = str(prov.get("state-default") or "known") if isinstance(prov, dict) else "known"

    def add(self, check: str, item: Item | None, msg: str, fld: str | None = None, severity: str | None = None,
            file: str | None = None) -> None:
        if check in self.sel:
            self.rep.add(Problem(check, severity or self.sev.get(check, "error"), item.key if item else "",
                                 file if file is not None else (item.file if item else ""), msg, fld))

    def item(self, it: Item) -> None:
        m, g, d = self.m, self.g, it.data
        for fpath, q in walk_pending(d):
            self.rep.pending.append((it.key, fpath, q))
            if not (isinstance(q, str) and q.strip()):
                self.add("pending-shape", it, f'{fpath}: an open question is {{pending: "<the question>"}}, not '
                                              f"{q!r}", fpath)
        p = g.parse(it.id)
        if p is None:
            self.add("id-grammar", it, f"not {g.item_form}")
            return
        if p.module and it.module and p.module != it.module:
            self.add("id-module", it, f"id says {p.module} but the file is under {it.module}/")
            return
        if it.module not in g.modules:
            self.add("id-module", it, f"{it.module!r} is not a module of {m.title}: its modules are "
                                      f"{', '.join(g.modules)}")
            return
        kinds = m.kinds(it.module)
        kind = it.kind
        if kind not in kinds:
            legacy = m.legacy_kinds(it.module)
            if kind in legacy and legacy[kind] in kinds:
                self.add("type", it, f"{kind} is read as {legacy[kind]} (a legacy kind); rename the type and the id "
                                     "when convenient", severity="note")
                kind = legacy[kind]
            else:
                self.add("type", it, f"{kind!r} is not a {it.module} kind ({', '.join(kinds)})", "type")
                return
        own = kinds[kind].get("id")
        if isinstance(own, str) and "<slug>" in own:
            if p.form != kind:
                self.add("type-prefix", it, f"the {kind} item is written {own}", "id")
        elif (p.form or p.kind) != it.kind:
            self.add("type-prefix", it, f"type is {it.kind}", "type")
        req = m.required_fields(it.module, kind)
        skip = {"id", "type"} | ({"provenance"} if "provenance" in self.sel else set())
        for k in req:
            if k not in skip and k not in d:
                self.add("identity-min", it, f"missing {k}", k)
        if "provenance" in req:
            self.provenance(it)
        for key in ("status", "visibility"):
            allowed = self.closed.get(key)
            if allowed is not None and key in d and not is_pending(d[key]) and d[key] not in allowed:
                self.add(key, it, f"must be one of {', '.join(map(str, allowed))}", key)
        for fpath in m.refs(it.module, kind):
            for v in walk_path(d, fpath):
                self.ref(it, fpath, v, soft="*" in fpath)
        for fpath, allowed in self.closed.items():
            if fpath in ("status", "visibility") and fpath in self.sel:
                continue
            if fpath.startswith("provenance.") and "provenance" in self.sel and "provenance" in req:
                continue
            for v in walk_path(d, fpath):
                if v is None or is_pending(v):
                    continue
                if isinstance(v, (dict, list)) or v not in allowed:
                    self.add("closed-list", it, f"{fpath} = {v!r}: must be one of {', '.join(map(str, allowed))}",
                             fpath)

    def provenance(self, it: Item) -> None:
        prov = it.data.get("provenance")
        if not isinstance(prov, dict):
            self.add("provenance", it, "missing provenance (mode, sources, confidence)", "provenance")
            return
        modes = self.closed.get("provenance.mode")
        if modes is not None and prov.get("mode") not in modes:
            self.add("provenance", it, f"mode must be one of {', '.join(map(str, modes))}", "provenance.mode")
        srcs = prov.get("sources")
        if not isinstance(srcs, list) or not srcs:
            self.add("provenance", it, "sources or it didn't happen", "provenance.sources")
        c = prov.get("confidence")
        if not isinstance(c, (int, float)) or isinstance(c, bool) or not 0 <= c <= 1:
            self.add("provenance", it, "confidence must be a number from 0 to 1", "provenance.confidence")
        states = self.closed.get("provenance.state")
        if states is not None and prov.get("state", self.state_default) not in states:
            self.add("provenance", it, f"state must be one of {', '.join(map(str, states))}", "provenance.state")

    def ref(self, it: Item, fpath: str, v: Any, *, soft: bool) -> None:
        g = self.g
        if v is None or is_pending(v) or (isinstance(v, str) and v in self.m.sentinels):
            return
        if isinstance(v, dict):
            v = v.get("to") or v.get("id")
            if v is None:
                return
        if _is_date(v):
            return
        if not isinstance(v, str):
            if not soft:
                self.add("ref-grammar", it, f"{fpath} must be an id string", fpath)
            return
        if any(rx.match(v) for rx in g.other_rx):
            return                                  # another id form (a vendor): not checked in this version
        if _resolve(self.v, it, v) is not None:
            return
        p = g.parse(v)
        if soft and not (p is not None and p.module in g.modules and not p.loose):
            return                                  # a literal in a wildcard field: text, not a reference
        if p is None and not g.is_part_id(v):
            self.add("ref-grammar", it, f"{fpath} = {v!r} is not an id", fpath)
            return
        self.add("ref-unresolved", it, f"{fpath} -> {v} does not exist", fpath)

    def volume_checks(self) -> None:
        v, m = self.v, self.m
        for part in v.parts.values():
            for letter, reason in part.none.items():
                if not reason and "module-none" in self.sel:
                    self.rep.add(Problem("module-none", self.sev["module-none"], f"{part.id} {letter}",
                                         part.none_file.get(letter, ""), "module: none without a reason"))
        if "catalog-key" in self.sel:
            cat = m._block("catalog")
            known = set(_strs(cat.get("keys"))) | set(RESERVED_CATALOG_KEYS)
            if known - set(RESERVED_CATALOG_KEYS):
                for k in v.catalog:
                    if str(k) not in known:
                        self.add("catalog-key", None, f"{k} is not a catalog key of {m.title} (kept, ignored)", str(k),
                                 severity="note", file=v.catalog_file)
            tmpl = cat.get("id")
            cid = v.catalog.get("id")
            if isinstance(tmpl, str) and "<" in tmpl:
                rx = re.compile("^" + _Grammar._template(tmpl, {}) + "$")
                if cid is None:
                    self.add("catalog-key", None, f"no id: a catalog's id is {tmpl}", "id", file=v.catalog_file)
                elif not isinstance(cid, str) or not rx.match(cid):
                    self.add("catalog-key", None, f"id {cid!r} is not {tmpl}", "id", file=v.catalog_file)
            for k in _strs(cat.get("keys")):
                allowed = cat.get(k)
                if k == "keys" or not isinstance(allowed, list) or k not in v.catalog:
                    continue
                val = v.catalog[k]
                if not is_pending(val) and (isinstance(val, (dict, list)) or val not in allowed):
                    self.add("catalog-key", None, f"{k}: {val!r} must be one of {', '.join(map(str, allowed))}", k,
                             file=v.catalog_file)


def lint(volume: Volume) -> Report:
    """Run the generic checks the volume's manifest selects. Load problems are always errors (a duplicate id
    under `duplicate-id` when the manifest selects it, under `load` otherwise); a refused volume reports only its
    refusal."""
    rep = Report(volume)
    m = volume.manifest
    selected = m.checks() if m is not None else []
    for p in volume.problems:
        if p.check == "duplicate-id" and "duplicate-id" not in selected:
            p = Problem("load", p.severity, p.item, p.file, p.message, p.field)      # how Comprise reports it
        rep.add(p)
    if m is None:
        rep.checks = ["load"]
        return rep
    rep.checks = ["load"] + [c for c in selected if c in CHECKS and c != "load"]
    rep.not_run = _not_run(m)
    ctx = _Lint(volume, rep)
    for it in volume.items.values():
        ctx.item(it)
    ctx.volume_checks()
    return rep


def jsonable(value: Any) -> Any:
    """A loaded value made JSON-safe: dates and timestamps as ISO strings, other non-JSON scalars as text."""
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


# ---------------------------------------------------------------------------
# Renderers: Mermaid lenses and the text tree
# ---------------------------------------------------------------------------

# Default node shapes by kind (open, close), around a quoted label: the product tree's from cosm.py, Canon's
# from its manifest; any other kind is a rectangle. A lens's `shape:` map wins.
_SHAPES = {"brand": ("((", "))"), "suite": ("{{", "}}"), "offering": ("([", "])"), "function": ("[[", "]]"),
           "product": ("[", "]"), "service": ("(", ")"), "role": (">", "]"), "external": ("[/", "/]"),
           "folder": ("[[", "]]"), "file": ("[", "]"), "article": ("([", "])")}
_SHAPE_PAIRS = {("[", "]"), ("(", ")"), ("([", "])"), ("[[", "]]"), ("[(", ")]"), ("((", "))"), (">", "]"),
                ("{", "}"), ("{{", "}}"), ("[/", "/]"), ("[\\", "\\]"), ("[/", "\\]"), ("[\\", "/]"),
                ("(((", ")))")}
_MINDMAP_SHAPES = {("[", "]"), ("(", ")"), ("((", "))"), ("{{", "}}")}
# Theme-neutral strokes for class-by (fills stay the theme's), in closed-list order.
_PALETTE = ("#2e7d32", "#1565c0", "#6a1b9a", "#ef6c00", "#00838f", "#c62828", "#5d4037", "#455a64")
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\U00002300-\U000023FF"
                       "\U0000FE00-\U0000FE0F\U0000200D\U000E0000-\U000E007F]")


def _mm_text(text: Any, limit: int = LABEL_LIMIT) -> str:
    """Label text by merirmaid's rules: emoji-free, one line, at most `limit` characters (… marks a cut), never
    the bare word `end`, and safe inside a quoted Mermaid label (`#`, `"`, `<`, `>` as entity codes)."""
    s = " ".join(_EMOJI_RE.sub("", str(text)).split()) or "(unnamed)"
    if limit > 0 and len(s) > limit:
        s = s[:limit - 1].rstrip() + "…"
    if s == "end":
        s = "End"
    return (s.replace("#", "#35;").replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")
            .replace("`", "'"))


def _slug(s: str, n: int = 40) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]", "_", s.lower())).strip("_")[:n] or "x"


def _node_id(key: str, prefix: str = "n") -> str:
    """A Mermaid node id that is stable across runs: a readable slug plus a short hash of the full key."""
    return f"{prefix}_{_slug(key)}_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:6]}"


def _shape(spec: dict, kind: str | None, mindmap: bool = False) -> tuple[str, str]:
    lens_shapes = spec.get("shape") if isinstance(spec.get("shape"), dict) else {}
    raw = lens_shapes.get(kind)
    pair = tuple(raw.split()) if isinstance(raw, str) and len(raw.split()) == 2 else _SHAPES.get(kind or "", ("[", "]"))
    if pair not in _SHAPE_PAIRS:
        pair = ("[", "]")
    if mindmap and pair not in _MINDMAP_SHAPES:
        pair = ("(", ")") if pair[0].startswith("(") else ("[", "]")
    return pair


def _has_tree(volume: Volume) -> bool:
    return any(isinstance(it.data.get("parts"), list) or isinstance(it.data.get("parent"), str)
               for it in volume.items.values())


def _drawn(spec: dict) -> bool:
    """A lens `to_mermaid` can draw: kind `mermaid`, or no kind given."""
    return spec.get("kind", "mermaid") in DRAWN_LENS_KINDS


def lenses(volume: Volume) -> list[str]:
    """The lens ids for a volume: the manifest's Mermaid lenses, then the generic `map` always, then a generic
    `tree` when items carry `parts` or `parent`. A lens of another kind (DocOES's `manual`, a short; its
    `inventory`, a table) is the manifest's to declare and another renderer's to draw: it is not listed here."""
    if volume.manifest is None:
        return []
    out = [spec["id"] for spec in volume.manifest.lenses() if _drawn(spec)]
    if "map" not in out:
        out.append("map")
    if "tree" not in out and _has_tree(volume):
        out.append("tree")
    return out


def _lens_spec(volume: Volume, lens: str) -> dict:
    for spec in volume.manifest.lenses():
        if spec["id"] == lens:
            if not _drawn(spec):
                raise ValueError(f"lens {lens!r} is a {spec.get('kind')}, not a Mermaid drawing; this reader draws "
                                 f"{', '.join(lenses(volume))}")
            return spec
    if lens == "map":
        return {"id": "map", "diagram": "flowchart"}
    if lens == "tree" and _has_tree(volume):
        return {"id": "tree", "diagram": "flowchart", "edges": ["parts", "parent"], "tree": True}
    raise ValueError(f"no lens {lens!r} for this volume; its lenses are {', '.join(lenses(volume))}")


def _edges(volume: Volume, spec: dict, it: Item) -> Iterator[tuple[Item, Item, str, str]]:
    """(from, to, label, style) for one item: reference fields (`ref`), typed links (`link`), and `parts` /
    `parent` (`tree`, always drawn parent to part). A lens's `edges:` list narrows them: field paths, `links`,
    a link rel, `parts`, `parent`."""
    m = volume.manifest
    want = spec.get("edges") if isinstance(spec.get("edges"), list) else None
    want = [str(w) for w in want] if want is not None else None

    def wanted(name: str) -> bool:
        return want is None or name in want

    for fpath in m.refs(it.module, it.kind):
        if fpath in ("links", "parts", "parent") or not wanted(fpath):
            continue
        for label, v in _walk_labelled(it.data, fpath):
            t = resolve_ref(volume, it, v)
            if t is not None:
                yield it, t, label or fpath, "ref"
    for link in _list(it.data.get("links")):
        rel = str(link.get("rel") or "") if isinstance(link, dict) else ""
        if want is not None and "links" not in want and rel not in want:
            continue
        t = resolve_ref(volume, it, link)
        if t is not None:
            yield it, t, rel, "link"
    if wanted("parts"):
        for v in _list(it.data.get("parts")):
            t = resolve_ref(volume, it, v)
            if t is not None:
                yield it, t, "", "tree"
    if wanted("parent") and it.data.get("parent") is not None:
        t = resolve_ref(volume, it, it.data.get("parent"))
        if t is not None:
            yield t, it, "", "tree"


def _tree_keys(volume: Volume) -> set[str]:
    keys = set()
    for it in volume.items.values():
        for v in _list(it.data.get("parts")):
            t = resolve_ref(volume, it, v)
            if t is not None:
                keys |= {it.key, t.key}
        t = resolve_ref(volume, it, it.data.get("parent")) if it.data.get("parent") is not None else None
        if t is not None:
            keys |= {it.key, t.key}
    return keys


def _groups(volume: Volume, items: list[Item], modules: list[str]) -> list[tuple[str | None, str, list[Item]]]:
    """(part id or None, module, items) in part order then manifest module order; empty groups left out."""
    by: dict[tuple[str | None, str], list[Item]] = {}
    for it in items:
        by.setdefault((it.part, it.module or ""), []).append(it)
    parts = list(volume.parts) if volume.parts else [None]
    out = []
    for part in parts + ([None] if volume.parts else []):
        for mod in modules:
            its = by.get((part, mod))
            if its:
                out.append((part, mod, its))
    return out


def _module_label(m: Manifest, letter: str) -> str:
    name = m.module(letter).get("name")
    return f"{letter} · {name}" if isinstance(name, str) else letter


def to_mermaid(volume: Volume, lens: str = "map", *, include: list[str] | None = None, max_nodes: int = MAX_NODES,
               clicks: bool = False, around: str | None = None, depth: int = 1) -> tuple[str, dict]:
    """A plain Mermaid body (no frontmatter) for one lens, and its node_map {mermaid node id: {"id": item key,
    "path": item path, "file": the item's file, "fs_path": the item's `path` field}}. Modules are subgraphs
    (inside a subgraph per part where the volume has parts); past `max_nodes` items, the rest of each subgraph
    collapses into one "… N more" node (node_map: id None, `more`: N). `clicks` adds a `click` line carrying
    each item's path. Raises ValueError for a lens the volume does not have (see `lenses`).

    `around` (an item's key, id or path) draws a local graph instead: that item and the items the lens's edges
    reach from it or to it within `depth` steps (1 by default), among the lens's included modules, as one
    flowchart with no subgraphs (a mindmap lens too), the centre node in the class `focus` and marked `focus:
    true` in node_map; past `max_nodes` the nearest are kept and the rest become one "… N more" node. Raises
    ValueError when no item answers to `around`."""
    if volume.manifest is None:
        why = str(volume.refused) if volume.refused is not None else "not loaded"
        return f'flowchart TB\n  refused["{_mm_text(why)}"]\n', {}
    m = volume.manifest
    spec = _lens_spec(volume, lens)
    modules = [str(x) for x in (include or spec.get("include") or m.modules())]
    items = [it for it in volume.items.values() if (it.module or "") in modules]
    if around is not None:
        return _local_graph(volume, spec, items, around, depth=depth, max_nodes=max_nodes, clicks=clicks)
    if spec.get("tree"):
        keep = _tree_keys(volume)
        items = [it for it in items if it.key in keep]
    drawn = {it.key for it in items[:max(int(max_nodes), 0)]}
    groups = _groups(volume, items, modules)
    if spec.get("diagram") == "mindmap":
        return _mindmap(volume, spec, groups, drawn)
    node_map: dict[str, dict] = {}
    ids: dict[str, str] = {}
    lines = [f"flowchart {spec.get('direction') or 'TB'}"]
    open_part: str | None = None
    for part, mod, its in groups:
        if part != open_part:
            if open_part is not None:
                lines.append("  end")
            if part is not None:
                lines.append(f'  subgraph {_node_id(part, "p")} ["{_mm_text(volume.parts[part].slug)}"]')
            open_part = part
        ind = "    " if part is not None else "  "
        gkey = f"{part or ''}//{mod}"
        lines.append(f'{ind}subgraph {_node_id(gkey, "g")} ["{_mm_text(_module_label(m, mod))}"]')
        hidden = [it for it in its if it.key not in drawn]
        for it in its:
            if it.key not in drawn:
                continue
            nid = _node_id(it.key)
            o, c = _shape(spec, it.kind)
            lines.append(f'{ind}  {nid}{o}"{_mm_text(it.name)}"{c}')
            ids[it.key] = nid
            node_map[nid] = {"id": it.key, "path": item_path(volume, it), "file": it.file,
                             "fs_path": it.data.get("path") if isinstance(it.data.get("path"), str) else None}
        if hidden:
            mid = _node_id(gkey, "more")
            lines.append(f'{ind}  {mid}["… {len(hidden)} more"]')
            first = item_path(volume, hidden[0])
            node_map[mid] = {"id": None, "path": first.rsplit("/", 2)[0] if first.count("/") >= 2 else "",
                             "file": None, "fs_path": None, "more": len(hidden)}
            for it in hidden:
                ids[it.key] = mid
        lines.append(f"{ind}end")
    if open_part is not None:
        lines.append("  end")
    seen: set[tuple] = set()
    arrows = {"ref": "-->", "link": "-.->", "tree": "-->"}
    for it in items:
        for a, b, label, style in _edges(volume, spec, it):
            x, y = ids.get(a.key), ids.get(b.key)
            if not x or not y or x == y:
                continue
            k = (x, y, style) if style == "tree" else (x, y, style, label)
            if k in seen:
                continue
            seen.add(k)
            lab = f'|"{_mm_text(label, 32)}"|' if label else ""
            lines.append(f"  {x} {arrows[style]}{lab} {y}")
    cls = spec.get("class-by")
    if isinstance(cls, str):
        order = [str(v) for v in m.closed_lists().get(cls, [])]
        by: dict[str, list[str]] = {}
        for it in items:
            val = it.data.get(cls)
            if isinstance(val, str) and it.key in drawn:
                by.setdefault(val, []).append(ids[it.key])
                if val not in order:
                    order.append(val)
        for i, val in enumerate(order):
            if val in by:
                cname = f"c_{_slug(cls, 16)}_{_slug(val, 24)}"
                lines.append(f"  classDef {cname} stroke:{_PALETTE[i % len(_PALETTE)]},stroke-width:2px;")
                lines.append(f"  class {','.join(by[val])} {cname};")
    if clicks:
        for nid, entry in node_map.items():
            if entry["id"] is not None and entry["path"]:
                lines.append(f'  click {nid} "{_mm_text(entry["path"], 0)}"')
    return "\n".join(lines) + "\n", node_map


def _centre(volume: Volume, around: Any) -> Item:
    ref = str(around).strip()
    hit: Any = volume.item(ref)
    if hit is None:
        hit = resolve_path(volume, ref)
        if isinstance(hit, tuple):
            hit = hit[0]
    if not isinstance(hit, Item):
        raise ValueError(f"no item {ref!r} in this volume to draw around")
    return hit


def _local_graph(volume: Volume, spec: dict, items: list[Item], around: Any, *, depth: int, max_nodes: int,
                 clicks: bool) -> tuple[str, dict]:
    """`to_mermaid(..., around=)`: the neighbourhood of one item, breadth first, as one flowchart."""
    centre = _centre(volume, around)
    allowed = {it.key for it in items} | {centre.key}
    rank = {k: i for i, k in enumerate(volume.items)}
    adj: dict[str, set[str]] = {}
    edges: list[tuple[Item, Item, str, str]] = []
    for it in volume.items.values():
        if it.key not in allowed:
            continue
        for a, b, label, style in _edges(volume, spec, it):
            if a.key in allowed and b.key in allowed and a.key != b.key:
                edges.append((a, b, label, style))
                adj.setdefault(a.key, set()).add(b.key)
                adj.setdefault(b.key, set()).add(a.key)
    order, seen, frontier = [centre.key], {centre.key}, [centre.key]
    for _ in range(max(int(depth), 0)):
        nxt: list[str] = []
        for k in frontier:
            for n in sorted(adj.get(k, ()), key=lambda x: rank.get(x, 0)):
                if n not in seen:
                    seen.add(n)
                    order.append(n)
                    nxt.append(n)
        frontier = nxt
    keep = order[:max(int(max_nodes), 1)]
    hidden = order[len(keep):]
    lines = [f"flowchart {spec.get('direction') or 'LR'}"]
    node_map: dict[str, dict] = {}
    ids: dict[str, str] = {}
    for key in keep:
        it = volume.items[key]
        nid = _node_id(key)
        o, c = _shape(spec, it.kind)
        lines.append(f'  {nid}{o}"{_mm_text(it.name)}"{c}')
        ids[key] = nid
        node_map[nid] = {"id": key, "path": item_path(volume, it), "file": it.file,
                         "fs_path": it.data.get("path") if isinstance(it.data.get("path"), str) else None}
    node_map[ids[centre.key]]["focus"] = True
    if hidden:
        mid = _node_id(centre.key, "more")
        lines.append(f'  {mid}["… {len(hidden)} more"]')
        node_map[mid] = {"id": None, "path": "", "file": None, "fs_path": None, "more": len(hidden)}
        for key in hidden:
            ids[key] = mid
    seen_edges: set[tuple] = set()
    arrows = {"ref": "-->", "link": "-.->", "tree": "-->"}
    for a, b, label, style in edges:
        x, y = ids.get(a.key), ids.get(b.key)
        if not x or not y or x == y:
            continue
        k = (x, y, style) if style == "tree" else (x, y, style, label)
        if k in seen_edges:
            continue
        seen_edges.add(k)
        lab = f'|"{_mm_text(label, 32)}"|' if label else ""
        lines.append(f"  {x} {arrows[style]}{lab} {y}")
    lines.append("  classDef focus stroke-width:3px,font-weight:bold;")
    lines.append(f"  class {ids[centre.key]} focus;")
    if clicks:
        for nid, entry in node_map.items():
            if entry["id"] is not None and entry["path"]:
                lines.append(f'  click {nid} "{_mm_text(entry["path"], 0)}"')
    return "\n".join(lines) + "\n", node_map


def _mindmap(volume: Volume, spec: dict, groups: list, drawn: set[str]) -> tuple[str, dict]:
    m = volume.manifest
    lines = ["mindmap", f'  root(("{_mm_text(volume.name)}"))']
    node_map: dict[str, dict] = {"root": {"id": None, "path": "", "file": volume.catalog_file, "fs_path": None}}
    open_part: str | None = None
    for part, mod, its in groups:
        depth = 2
        if part is not None:
            if part != open_part:
                lines.append(f'    {_node_id(part, "p")}["{_mm_text(volume.parts[part].slug)}"]')
                open_part = part
            depth = 3
        gkey = f"{part or ''}//{mod}"
        lines.append("  " * depth + f'{_node_id(gkey, "g")}("{_mm_text(_module_label(m, mod))}")')
        hidden = 0
        for it in its:
            if it.key not in drawn:
                hidden += 1
                continue
            nid = _node_id(it.key)
            o, c = _shape(spec, it.kind, mindmap=True)
            lines.append("  " * (depth + 1) + f'{nid}{o}"{_mm_text(it.name)}"{c}')
            node_map[nid] = {"id": it.key, "path": item_path(volume, it), "file": it.file,
                             "fs_path": it.data.get("path") if isinstance(it.data.get("path"), str) else None}
        if hidden:
            mid = _node_id(gkey, "more")
            lines.append("  " * (depth + 1) + f'{mid}["… {hidden} more"]')
            node_map[mid] = {"id": None, "path": "", "file": None, "fs_path": None, "more": hidden}
    return "\n".join(lines) + "\n", node_map


def _children(volume: Volume, items: list[Item]) -> tuple[list[Item], dict[str, list[Item]]]:
    """(roots, children by key) for one group: `parts` lists and `parent` fields, first claim wins."""
    keys = {it.key for it in items}
    kids: dict[str, list[Item]] = {it.key: [] for it in items}
    claimed: set[str] = set()
    for it in items:
        for v in _list(it.data.get("parts")):
            t = resolve_ref(volume, it, v)
            if t is not None and t.key in keys and t.key != it.key and t.key not in claimed:
                kids[it.key].append(t)
                claimed.add(t.key)
    for it in items:
        if it.data.get("parent") is None or it.key in claimed:
            continue
        t = resolve_ref(volume, it, it.data.get("parent"))
        if t is not None and t.key in keys and t.key != it.key:
            kids[t.key].append(it)
            claimed.add(it.key)
    return [it for it in items if it.key not in claimed], kids


def to_text_tree(volume: Volume, *, summaries: bool = True) -> str:
    """The volume as an indented plain-text tree (like `cosm.py ascii`): catalog, parts, modules, then items
    nested by `parts` / `parent`, each `name  [id · kind]  (N open)  — summary`, where N counts its open
    questions."""
    if volume.manifest is None:
        return f"(refused) {volume.refused}"
    m = volume.manifest
    lines = [f"{volume.name}  [{volume.id} · {volume.oes}]"]

    def label(it: Item) -> str:
        s = f"{it.name}  [{it.id} · {it.kind}]"
        n_open = sum(1 for _ in walk_pending(it.data))
        if n_open:
            s += f"  ({n_open} open)"
        summ = it.data.get("summary")
        if summaries and isinstance(summ, str) and summ.strip():
            summ = " ".join(summ.split())
            s += "  — " + (summ if len(summ) <= 80 else summ[:79].rstrip() + "…")
        return s

    def branch(nodes: list, prefix: str) -> None:
        for i, (text, sub) in enumerate(nodes):
            last = i == len(nodes) - 1
            lines.append(prefix + ("└── " if last else "├── ") + text)
            branch(sub, prefix + ("    " if last else "│   "))

    def item_nodes(items: list[Item]) -> list:
        roots, kids = _children(volume, items)
        seen: set[str] = set()

        def build(it: Item, depth: int = 0) -> tuple:
            seen.add(it.key)
            if depth >= _TREE_DEPTH:                                 # a pathological chain: the rest shows flat
                return (label(it), [])
            return (label(it), [build(k, depth + 1) for k in kids[it.key] if k.key not in seen])

        out = [build(r) for r in roots]
        out += [build(it) for it in items if it.key not in seen]       # a cycle has no root: show it anyway
        return out

    modules = m.modules()
    tree: list = []
    groups = _groups(volume, list(volume.items.values()), modules)
    if volume.parts:
        for pid, part in volume.parts.items():
            mods = [(f"{_module_label(m, mod)}", item_nodes(its)) for p, mod, its in groups if p == pid]
            mods += [(f"{_module_label(m, mod)}  (none: {part.none[mod] or 'no reason given'})", [])
                     for mod in modules if mod in part.none and not any(p == pid and x == mod for p, x, _ in groups)]
            tree.append((f"{part.slug}  [{part.id}]", mods))
    else:
        tree = [(_module_label(m, mod), item_nodes(its)) for _, mod, its in groups]
    branch(tree, "")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI: python -m enough.macrocosm {lint,paths,tree,mermaid,identify} <path>
# ---------------------------------------------------------------------------

def _cli_registry(args) -> Registry:
    return Registry(args.manifests) if args.manifests else default_registry()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m enough.macrocosm",
                                 description="MacroCOSM OES v0.0.1: read, check and draw .cosm volumes.")
    ap.add_argument("command", choices=["lint", "paths", "tree", "mermaid", "identify"])
    ap.add_argument("path", help="a volume folder or a catalog file")
    ap.add_argument("target", nargs="?", help="paths: a path, qualified URI or id to resolve")
    ap.add_argument("--lens", default="map", help="mermaid: the lens id (default map)")
    ap.add_argument("--max-nodes", type=int, default=MAX_NODES, help="mermaid: collapse past this many items")
    ap.add_argument("--around", help="mermaid: draw the local graph around this item (key, id or path)")
    ap.add_argument("--depth", type=int, default=1, help="mermaid --around: steps out from the item (default 1)")
    ap.add_argument("--json", action="store_true", help="lint, identify: JSON output")
    ap.add_argument("--manifests", action="append", type=Path, help="read manifests from this folder (repeatable)")
    args = ap.parse_args(argv)
    reg = _cli_registry(args)

    if args.command == "identify":
        p = Path(args.path)
        cat = reg.find_catalog(p) if p.is_dir() else p
        if cat is None or not cat.is_file():
            print(f"identify: no catalog at {p}", file=sys.stderr)
            return 1
        problems: list[Problem] = []
        doc = _read_doc(cat, cat.name, problems)
        res = reg.identify(doc, filename=cat.name) if doc is not None else Refusal("; ".join(map(str, problems)))
        if args.json:
            out = {"refused": res.message} if isinstance(res, Refusal) else \
                {"minicosm": res.minicosm, "major": res.major, "how": res.how, "key": res.key, "said": res.said}
            print(json.dumps(out, ensure_ascii=False))
        else:
            print(res.message if isinstance(res, Refusal) else
                  f"{res.value} ({res.manifest.title}; {res.how}" + (f" {res.key}: {res.said}" if res.key else "") + ")")
        return 1 if isinstance(res, Refusal) else 0

    vol = load_volume(args.path, reg)
    if args.command == "lint":
        rep = lint(vol)
        if args.json:
            print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
        else:
            for p in rep.problems():
                print(f"{p.severity:7} {p}")
            print(f"{vol.oes or 'refused'}: {len(vol.items)} items, {len(rep.errors)} errors, {len(rep.warnings)} "
                  f"warnings, {len(rep.notes)} notes, {len(rep.pending)} open questions"
                  + (f"; not run: {len(rep.not_run)} checks this reader leaves to {vol.minicosm}'s own tools"
                     if rep.not_run else ""))
        return 0 if rep.ok else 1
    if vol.manifest is None:
        print(f"refused: {vol.refused}", file=sys.stderr)
        return 1
    if args.command == "paths":
        if args.target:
            hit = resolve_path(vol, args.target) or vol.item(args.target)
            if hit is None:
                print(f"nothing at {args.target}", file=sys.stderr)
                return 1
            it, val = hit if isinstance(hit, tuple) else (hit, None)
            print(f"{item_path(vol, it)}\t{it.id}\t{it.file}\t{qualified_uri(vol, it)}")
            if isinstance(hit, tuple):
                print(json.dumps(jsonable(val), ensure_ascii=False))
            return 0
        for it in vol.items.values():
            print(f"{item_path(vol, it) or '(no path)'}\t{it.key}")
        return 0
    if args.command == "tree":
        sys.stdout.write(to_text_tree(vol))
        return 0
    try:
        body, _ = to_mermaid(vol, args.lens, max_nodes=args.max_nodes, around=args.around, depth=args.depth)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
