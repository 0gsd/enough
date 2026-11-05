"""enough's side of Thym: the state root, the model coprocessor, the preflight hook and the environment a trace names
(docs/THYM.md 11.2, 11.3, 12.2, 12.3, 12.5, 19).

`enough/thym/` imports nothing of enough but the reader, so it can be vendored; the engines plug in from here.

- `host_root()` is where runs live: `ENOUGH_THYM_ROOT`, else `~/enough/thym/`; nothing is created until a run writes.
- `ModelCoprocessor` is the coprocessor over `enough.llm.complete` (or any `complete(messages) -> (text, meta)`), the
  pattern of `canon_derive`'s model calls, generalised: it asks for schema'd output (YAML or markdown, as the contract's
  `schema` says), with the failed checks of the last attempt listed when the runtime asks again; it makes the narrow
  repairs the contract allows (`normalise-stance`: a stance word read against EMF's closed list; `drop-unresolved-
  spans`: an item whose span lies outside its text is dropped); one call is one attempt, and the runtime bounds them.
- `preflight_hook()` asks `enough.preflight.evaluate` whether the machine's model holds the plan's largest prompt, and
  refuses at plan time with the number and the fix when it does not (the 16 GB rule, THYM.md 12.5).
- `host_coprocessor(agent_free, rules=)` picks the implementation (refusing when agent-free or in rules mode);
  `runtime_kwargs()` is everything `enough.thym.run.run` needs from enough, read from the live switches.
- `engines()` is the mapping the moves reach as `ctx.engines` (THYM.md 11.2): `canon` (`canon_derive`'s derivation,
  outline, footer and atems, wired so that the moves stay free of engine imports), `docoes`, and `feed` (FEED's batch
  lookup, when the dictionary is built); a test passes its own.
- The prompt builders of the model-backed moves (`registry.prompt_for`): each turns a move's contract and inputs into
  the messages the model reads, on Canon's prompts where Canon has one (the atem's, the EMF passage's, the compile's
  stance words). A move whose engine wrote the messages itself (`derive`) passes them through unchanged.
"""
from __future__ import annotations

import inspect
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

from . import __version__ as ENOUGH_VERSION
from .thym import Refusal
from .thym import registry as _registry
from .thym.coprocessor import Candidate, RefusingCoprocessor, candidate, prose_problem
from .thym.run import plan_parts
from .thym.trace import default_root
from .thym.values import Value

CompleteFn = Callable[..., Any]
STANCES = ("axiom", "observed", "deduced", "opinion", "assumed", "hearsay")
CHARS_PER_TOKEN = 3                     # the estimator server.py and canon_derive use
_SPAN_LINES = re.compile(r"(\d+)(?:\s*-\s*(\d+))?")


def host_root() -> Path:
    """Where Thym's runs live, `ENOUGH_THYM_ROOT` or `~/enough/thym/`; `runs/` is made the first time it is asked."""
    root = default_root()
    return root                                       # made by a run that writes, never by a question (see run.py)


def agent_free() -> bool:
    from . import agent_free as _agent_free
    return _agent_free.enabled()


# ---------------------------------------------------------------------------
# The model coprocessor (THYM.md 12.2)
# ---------------------------------------------------------------------------

def _accepts(fn: Callable, kw: dict) -> bool:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        return True
    return all(k in params for k in kw)


def _call(complete: CompleteFn, messages: list[dict], **kw: Any) -> tuple[str, dict]:
    """`complete(messages, **kw) -> (text, meta)`, a bare text read as `(text, {})`; keywords go only to a callable that
    takes them (canon_derive's `_call`)."""
    r = complete(messages, **kw) if kw and _accepts(complete, kw) else complete(messages)
    if isinstance(r, tuple):
        text, meta = r[0], (r[1] if len(r) > 1 and isinstance(r[1], dict) else {})
    else:
        text, meta = r, {}
    return (text if isinstance(text, str) else ""), meta


def _strip_fences(text: str) -> str:
    mt = re.search(r"```[A-Za-z0-9_-]*\s*\n(.*?)(?:\n```|$)", text, re.S)
    return mt.group(1) if mt else text


def _outer_fence(text: str) -> str:
    """Markdown without the one fence a model may wrap it in; a fence inside the answer is the answer's own."""
    s = text.strip()
    if s.startswith("```") and s.endswith("```") and s.count("```") == 2:
        return s[s.index("\n") + 1:-3] if "\n" in s else s.strip("`")
    return text


def _closed_match(v: Any, allowed: tuple[str, ...]) -> str | None:
    """A model's word read against a closed list, as canon_derive reads it: exact; the one entry it begins or that
    begins it; else the one entry sharing at least five leading letters."""
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip().lower()
    if s in allowed:
        return s
    starts = [a for a in allowed if a.startswith(s)] if len(s) >= 2 else []
    for hits in (starts, [a for a in allowed if s.startswith(a)]):
        if len(hits) == 1:
            return hits[0]
    scored = [(len(os.path.commonprefix([s, a])), a) for a in allowed]
    best = max((n for n, _ in scored), default=0)
    top = [a for n, a in scored if n == best]
    return top[0] if best >= 5 and len(top) == 1 else None


def _schema_format(contract: dict) -> str:
    sch = contract.get("schema")
    fmt = sch.get("format") if isinstance(sch, dict) else sch
    return "yaml" if fmt == "yaml" else "markdown"


def _input_text(v: Any) -> str:
    if isinstance(v, Value):
        return v.text()
    return str(v)


class ModelCoprocessor:
    """The model behind a move's contract. `complete` is `complete(messages, **kw) -> (text, meta)`; by default a
    closure over `enough.llm.complete` at `llm_url`. Prompt builders registered for a move (`registry.prompt_for`)
    write the messages; otherwise a plain prompt names the move, the format and the checks, and gives the inputs."""

    def __init__(self, complete: CompleteFn | None = None, *, llm_url: str | None = None, model_id: str | None = None,
                 max_tokens: int | None = None, moves: _registry.Moves | None = None) -> None:
        self._complete = complete or self._llm(llm_url)
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.moves = moves if moves is not None else _registry.MOVES

    @staticmethod
    def _llm(llm_url: str | None) -> CompleteFn:
        def complete(messages: list[dict], max_tokens: int | None = None) -> tuple[str, dict]:
            from . import llm as _llm
            return _llm.complete(messages, llm_url=llm_url, max_tokens=max_tokens)
        return complete

    def messages(self, contract: dict, inputs: dict) -> list[dict]:
        builder = self.moves.prompt(str(contract.get("move")))
        if builder is not None:
            msgs = list(builder(contract, inputs))
        else:
            fmt = _schema_format(contract)
            sch = contract.get("schema")
            shape = sch.get("says") or sch.get("shape") if isinstance(sch, dict) else None
            checks = ", ".join(str(c) for c in contract.get("checks") or []) or "none"
            system = (f"You are the coprocessor of a Thym program, making one move: {contract.get('move')}. "
                      f"Answer with {'one YAML mapping' if fmt == 'yaml' else 'markdown'} only, nothing before or "
                      "after it."
                      + (f" The answer's shape: {shape}." if shape else "")
                      + f" What you give must pass these checks: {checks}.")
            body = "\n\n".join(f"## {name} ({getattr(pair[0], 'type', 'value')})\n\n{_input_text(pair[0])}"
                               for name, pair in (inputs or {}).items())
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": body or "(no inputs)"}]
        rep = contract.get("repair") if isinstance(contract.get("repair"), dict) else {}
        failed = [f for f in rep.get("failed") or [] if isinstance(f, dict)]
        if failed:
            lines = "\n".join(f"- {f.get('name')}: {f.get('why') or 'does not hold'}" for f in failed)
            only = (ONLY_THE_YAML if _schema_format(contract) == "yaml" and any(f.get("name") == "schema"
                                                                                 for f in failed) else "")
            msgs.append({"role": "user", "content": "Your last answer failed these checks. Answer again, whole, so "
                                                    f"that they hold:\n{lines}" + (f"\n{only}" if only else "")})
        return msgs

    def complete(self, contract: dict, inputs: dict, *, budget: dict) -> Candidate | Refusal:
        msgs = self.messages(contract, inputs)
        words = int((budget or {}).get("output_words") or 0)
        max_tokens = max(512, words * 3) if words else self.max_tokens
        t0 = time.monotonic()
        try:
            text, meta = _call(self._complete, msgs, **({"max_tokens": max_tokens} if max_tokens else {}))
        except Exception as e:  # noqa: BLE001 - transport, cloud gate, agent-free: the model could not be asked
            return Refusal("run", "coprocessor", f"the model could not be asked for {contract.get('move')}: "
                                                 f"{type(e).__name__}: {e}")
        seconds = int(time.monotonic() - t0)
        tokens = reported_tokens(meta)
        if tokens is None:
            tokens = (sum(len(m.get("content") or "") for m in msgs) + len(text)) // CHARS_PER_TOKEN
        engine = f"model:{meta.get('model') or self.model_id or 'unknown'}"
        checks: list = []
        if _schema_format(contract) == "yaml":
            why = prose_problem(text)
            if why:
                # THYM.md 12.2: an answer with prose around or instead of the YAML is handed on as the model wrote it,
                # so the runtime fails it as `schema` at once (and a replay fails it again) and asks for only the YAML
                output: Any = text
                checks = [{"name": "schema", "ok": False, "why": why}]
            else:
                output = self._repaired(contract, inputs, _strip_fences(text))
                sch = contract.get("schema")
                if isinstance(output, dict) and isinstance(sch, dict) and sch.get("stamp") == "engine":
                    output["engine"] = engine      # the move's footer names the model, and a replay names it again
        else:
            output = _outer_fence(text).strip("\n") + "\n"
        return candidate(output, engine=engine, attempts=1, tokens=tokens, seconds=seconds, checks=checks)

    def _repaired(self, contract: dict, inputs: dict, text: str) -> Any:
        """A YAML answer, with the narrow repairs the contract allows applied; the text itself when it is not a
        mapping (the runtime then fails it as unreadable and asks again)."""
        from .macrocosm import yaml_load
        try:
            data = yaml_load(text)
        except Exception:  # noqa: BLE001 - anything a model can write
            return text
        if not isinstance(data, dict):
            return text
        rep = contract.get("repair") if isinstance(contract.get("repair"), dict) else {}
        allowed = set(rep.get("allowed") or [])
        nodes = data.get("nodes") if isinstance(data.get("nodes"), list) else None
        if nodes is None:
            return data
        if "normalise-stance" in allowed:
            for n in nodes:
                if isinstance(n, dict) and "stance" in n:
                    fixed = _closed_match(n.get("stance"), STANCES)
                    if fixed:
                        n["stance"] = fixed
        if "drop-unresolved-spans" in allowed:
            src = next((p[0] for p in (inputs or {}).values() if getattr(p[0], "type", None) == "text"), None)
            if src is not None:
                n_lines = len(_input_text(src).splitlines())
                data["nodes"] = [n for n in nodes if not _span_outside(n, n_lines)]
        return data


#: What a re-ask adds when the last answer was not only YAML (checkpoint A, lesson 1).
ONLY_THE_YAML = ("Answer with only the YAML mapping, nothing before or after it: no reasoning, no heading, no note, "
                 "no second block.")


def reported_tokens(meta: dict) -> int | None:
    """The tokens a completion cost, when the engine reports them (`usage.total_tokens`, or its prompt and completion
    tokens, or `tokens`); None when it does not, and the coprocessor estimates (THYM.md 12.3)."""
    if not isinstance(meta, dict):
        return None
    usage = meta.get("usage")
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        if isinstance(total, int) and not isinstance(total, bool):
            return total
        parts = [usage.get(k) for k in ("prompt_tokens", "completion_tokens")]
        if all(isinstance(x, int) and not isinstance(x, bool) for x in parts):
            return int(parts[0]) + int(parts[1])
    t = meta.get("tokens")
    return t if isinstance(t, int) and not isinstance(t, bool) else None


def _span_outside(item: Any, n_lines: int) -> bool:
    span = item.get("span") if isinstance(item, dict) else None
    if not isinstance(span, dict) or span.get("lines") is None:
        return False
    mt = _SPAN_LINES.search(str(span.get("lines")))
    if not mt:
        return True
    a, b = int(mt.group(1)), int(mt.group(2) or mt.group(1))
    return a < 1 or b < a or b > n_lines


# ---------------------------------------------------------------------------
# The plan-time size check (THYM.md 12.5)
# ---------------------------------------------------------------------------

def _read_n_ctx(llm_url: str | None) -> int | None:
    try:
        import httpx
        from .llm import DEFAULT_LLM_URL
        r = httpx.get(f"{(llm_url or DEFAULT_LLM_URL).rstrip('/')}/props", timeout=5.0)
        if r.status_code == 200:
            n = (r.json().get("default_generation_settings") or {}).get("n_ctx")
            return int(n) if n else None
    except Exception:  # noqa: BLE001 - no model, an old build: the size is unknown, and unknown never refuses
        return None
    return None


def preflight_hook(n_ctx: int | Callable[[], int | None] | None = None, *,
                   llm_url: str | None = None) -> Callable[[dict], Refusal | None]:
    """A `preflight(plan)` for `run`: the plan's largest prompt against the model's window (`n_ctx`, a number or a
    callable; else read from llama-server's `/props`), by `enough.preflight.evaluate`. Unknown sizes never refuse."""
    def hook(plan: dict) -> Refusal | None:
        from . import preflight as _preflight
        head, _ = plan_parts(plan)
        est = plan.get("estimate") if isinstance(plan.get("estimate"), dict) else {}
        need = int(head.get("largest_prompt") or est.get("largest_prompt") or 0)
        if need <= 0:
            return None
        ctx = n_ctx() if callable(n_ctx) else (n_ctx if n_ctx is not None else _read_n_ctx(llm_url))
        if not ctx:
            return None
        v = _preflight.evaluate(need, int(ctx))
        if v["fits"]:
            return None
        fix = (f"; a {v['suggest_ctx']:,}-token window would hold it" if v.get("suggest_ctx")
               else "; no window this model supports holds it")
        return Refusal("plan", "preflight", f"the plan's largest prompt is {need:,} tokens and the model's window is "
                                            f"{int(ctx):,} with {v['reserve']:,} kept free{fix}")
    return hook


# ---------------------------------------------------------------------------
# Choosing, and the environment a trace names
# ---------------------------------------------------------------------------

def host_coprocessor(agent_free: bool, *, rules: bool, complete: CompleteFn | None = None,
                     llm_url: str | None = None) -> Any:
    """The coprocessor for a run: refusing when agent-free or in rules mode (no model runs), else the model."""
    if agent_free or rules:
        return RefusingCoprocessor()
    return ModelCoprocessor(complete, llm_url=llm_url)


def memory_band() -> str:
    try:
        from .models import total_ram_gb
        ram = int(total_ram_gb())
    except Exception:  # noqa: BLE001
        return "unknown"
    band = 8
    while band * 2 <= ram:
        band *= 2
    return f"{band} GB"


def current_model() -> str:
    """The model slot the user runs, read without seeding the live state file."""
    try:
        from . import models as _models
        if not Path(_models.LIVE_STATE).exists():
            return "none"
        return str(_models.load_state().get("current") or "none")
    except Exception:  # noqa: BLE001
        return "none"


class Window:
    """The model's window, read once and only when asked (`n_ctx`, else llama-server's `/props`): the preflight and the
    trace's `environment.context` share one reading, and a run that asks the model nothing never asks for its size
    (the runtime reads a callable environment value only when a model runs, THYM.md 12.3)."""

    def __init__(self, n_ctx: int | None = None, *, llm_url: str | None = None) -> None:
        self._n = n_ctx
        self._read = n_ctx is not None
        self.llm_url = llm_url

    def __call__(self) -> int | None:
        if not self._read:
            self._n = _read_n_ctx(self.llm_url)
            self._read = True
        return self._n


def environment(*, agent_free: bool, n_ctx: int | Callable[[], int | None] | None = None) -> dict:
    """The environment a trace names (THYM.md 12.3); `n_ctx` may be a `Window`, read by the runtime when a model runs."""
    return {"enough": ENOUGH_VERSION, "model": "none" if agent_free else current_model(),
            "context": n_ctx if callable(n_ctx) else int(n_ctx or 0), "agent_free": bool(agent_free),
            "memory_band": memory_band()}


def runtime_kwargs(*, rules: bool = False, complete: CompleteFn | None = None, llm_url: str | None = None,
                   n_ctx: int | None = None, catalog: Callable | None = None) -> dict:
    """What `enough.thym.run.run` needs from enough, read from the live switches: the coprocessor, agent-free, the
    preflight hook, the environment, the root (made on first use) and the engines. The model's window (`n_ctx`, else
    llama-server's `/props`) is a `Window`, read once and only when a plan asks a model, for both the preflight and the
    trace's `environment.context` (THYM.md 12.3): a deterministic, agent-free or rules run asks no model anything, not
    even its size. `catalog` is the surrounding catalog engine `context of` reads (`catalog_engine(project_dir)`)."""
    af = agent_free()
    model = not (af or rules)
    window = Window(n_ctx, llm_url=llm_url)
    return {"coprocessor": host_coprocessor(af, rules=rules, complete=complete, llm_url=llm_url),
            "agent_free": af, "preflight": preflight_hook(window, llm_url=llm_url) if model else None,
            "environment": environment(agent_free=af, n_ctx=window if model else None), "root": host_root(),
            "engines": engines(catalog=catalog)}


# ---------------------------------------------------------------------------
# The engines the moves reach through `ctx.engines` (THYM.md 11.2)
# ---------------------------------------------------------------------------

def _no_feed(words: list) -> dict:
    """FEED's lookup when there is no FEED: every word unknown, so terms say `{pending: "not in FEED"}`."""
    return {}


#: The fields of a FEED entry that anything a run reaches reads, and so all the feed engine answers with. A recorded run
#: writes every answer into its trace (`candidates/<node>-e<k>.1.cosm`), so a whole entry (rhymes, forms, six
#: languages' definitions) would make the record many times the run. The readers, all of them:
#: - `moves/morph.py` `statistics` (measure, and `null-pinned`'s and `scales-met`'s count of a telling): `frequency_rank`;
#: - `moves/emf.py` `_term_problem` (`terms-grounded`): only whether a word has an entry (any mapping);
#: - `canon_derive` through the `canon` engine (`derive_passages`, `derive_rules`, `derive_gaps`, `derive_finish`):
#:   `_term_table` reads `word` and `frequency_rank`, `_passage_terms` `definition`, `pos_primary` and `pos`,
#:   `_feed_block` `word`, `pos_primary`, `pos` and `origin`, `_ground_terms` and the rules scaffold `definition`.
#: A new reader of a field adds it here, or it reads nothing in a run.
FEED_FIELDS = ("word", "frequency_rank", "definition", "pos_primary", "pos", "origin")


def feed_fields(lookup: Callable[[list], dict]) -> Callable[[list], dict]:
    """A batch lookup that answers what `lookup` does, each entry cut to `FEED_FIELDS` (a word it does not know stays
    None, so a term still says `{pending: "not in FEED"}`)."""
    def feed(words: list) -> dict:
        found = lookup(words) or {}
        return {k: ({f: e[f] for f in FEED_FIELDS if f in e} if isinstance(e, dict) else e) for k, e in found.items()}
    feed.__name__ = getattr(lookup, "__name__", "feed")
    return feed


def _feed() -> Callable | None:
    """FEED's batch lookup (`dictionary.lookup_many`, cut to `FEED_FIELDS`) when the dictionary is built here; None
    otherwise, so that a machine without FEED grounds nothing rather than everything as unknown."""
    try:
        from . import dictionary
        return feed_fields(dictionary.lookup_many) if dictionary.feed_path().is_file() else None
    except Exception:  # noqa: BLE001 - no FEED: the moves say so
        return None


def _utc_naive(now: Any) -> Any:
    """A moment as Canon's `_local_day` reads it without a zone: the run's UTC day, the same on every machine."""
    import datetime as _dt
    if isinstance(now, _dt.datetime) and now.tzinfo is not None:
        return now.astimezone(_dt.timezone.utc).replace(tzinfo=None)
    return now


def canon_engine() -> Any:
    """`canon_derive` as the moves use it, every model call made through the `complete` they pass in:

    - `derive_passages(text, *, source_name, complete, lookup)`: the derivation up to its last call (chunked, every
      passage read, normalized, repaired once, merged, grounded in FEED over the lexicon floor), as `{nodes, messages,
      model, chunks, dropped, normalized, continued}`, `messages` being the whole text's atem request;
    - `derive_finish(text, *, nodes, atem_reply, source_name, sha256, size, model, chunks, dropped, now)`: the twin's
      catalog around those items and that atem (`derived.by: thym`; `source` without the file's mtime, which differs
      from machine to machine);
    - `derive_gaps(text, *, nodes, spans, source_name, complete, lookup)`: the items with the lines no item covers
      read once more, as one passage (the narrow repair of `coverage`);
    - `derive_rules(...)`: the rules-mode twin; `compile_rules(fabula, *, order, source_name, now)`: the rules-mode
      short with its footer; `outline`, `short_footer`, `rules_atem`, `read_atem`: Canon's own."""
    import tempfile
    from types import SimpleNamespace

    from . import canon_derive as CD
    from . import canon_prompts as P

    def catalog(text: str, *, source_name: str, sha256: str, size: int, nodes: list, atem: dict, mode: str,
                model: str | None, chunks: int, dropped: int, now: Any) -> dict:
        derived = CD._derived(now=now, by="thym", model=model, mode=mode, completeness="full", chunks=chunks,
                              dropped=dropped)
        cat = CD._catalog(rel_path=source_name, source_name=source_name, source_stat={"sha256": sha256, "size": size},
                          name=CD.text_title(text, source_name), derived=derived, atem=atem, nodes=nodes)
        if isinstance(cat.get("source"), dict) and cat["source"].get("mtime_ns") is None:
            cat["source"].pop("mtime_ns", None)
        return CD._plain(cat)

    def derive_passages(text: str, *, source_name: str, complete: Callable, lookup: Callable | None = None) -> dict:
        lookup = lookup or _no_feed
        parts = CD.chunk(text)
        table = CD._term_table(text, lookup)
        meta: dict = {"normalized": 0, "continued": 0}
        merged: dict = {}
        remap: dict = {}
        dropped = 0
        with tempfile.TemporaryDirectory(prefix="enough-emf-") as tmp:
            work = Path(tmp)
            for c in parts:
                items, rm, lost = CD._read_passage(c, complete=complete, source=source_name, table=table,
                                                   workdir=work, stats=meta, on_progress=None, chunks=len(parts))
                dropped += lost
                for k, v in rm.items():
                    remap.setdefault(k, v)
                for it in items:
                    if it["id"] in merged:
                        CD._merge_into(merged[it["id"]], it)
                    else:
                        merged[it["id"]] = it
            items = list(merged.values())
            passage_atems = [it for it in items if it.get("type") == "atem"]
            items = [it for it in items if it.get("type") != "atem"]
            CD._ground_terms(items, lookup)
            items = CD._with_floor(items, CD._term_nodes(table, source_name, pending=CD.PENDING_FLOOR), remap)
            items, lost = CD._final_clean(CD._order(items), work, remap)
            dropped += lost
        lines = []
        for a in passage_atems:
            line = a.get("line")
            if isinstance(line, str) and line.strip():
                lines.append(f"- lines {(a.get('span') or {}).get('lines', '?')}: {' '.join(line.split())}")
        user = P.ATEM_WHOLE_USER.format(name=source_name, atems="\n".join(lines) or "- (none)", body=CD._edges(text))
        return {"nodes": items, "messages": [{"role": "system", "content": P.ATEM_SYSTEM},
                                             {"role": "user", "content": user}],
                "model": meta.get("model"), "chunks": len(parts), "dropped": dropped,
                "normalized": meta["normalized"], "continued": meta["continued"]}

    def derive_finish(text: str, *, nodes: list, atem_reply: str, source_name: str, sha256: str, size: int,
                      model: str | None, chunks: int, dropped: int, now: Any) -> dict:
        return catalog(text, source_name=source_name, sha256=sha256, size=size, nodes=nodes,
                       atem=CD.atem_block(CD._read_atem(atem_reply)), mode="model", model=model, chunks=chunks,
                       dropped=dropped, now=now)

    def derive_rules(text: str, *, source_name: str, sha256: str, size: int, lookup: Callable | None = None,
                     now: Any = None) -> dict:
        table = CD._term_table(text, lookup or _no_feed)
        return catalog(text, source_name=source_name, sha256=sha256, size=size,
                       nodes=CD._rules_nodes(text, table, source_name), atem=CD.atem_block(CD.rules_atem(text)),
                       mode="rules", model=None, chunks=len(CD.chunk(text)), dropped=0, now=now)

    def derive_gaps(text: str, *, nodes: list, spans: list, source_name: str, complete: Callable,
                    lookup: Callable | None = None) -> list:
        """The twin's items with the lines no item covers read once more, as one passage (`spans`: the uncovered
        sentences' line ranges): the new items merged in, references re-resolved, what fails dropped."""
        lookup = lookup or _no_feed
        lines = CD._lines(text)
        a = max(1, min(x for x, _y in spans))
        b = min(len(lines), max(y for _x, y in spans))
        c = CD.Chunk(len(CD.chunk(text)) + 1, a, b, CD._numbered(lines, a, b))
        table = CD._term_table(text, lookup)
        meta: dict = {"normalized": 0, "continued": 0}
        have = {it.get("id") for it in nodes}
        with tempfile.TemporaryDirectory(prefix="enough-emf-") as tmp:
            work = Path(tmp)
            items, remap, _lost = CD._read_passage(c, complete=complete, source=source_name, table=table,
                                                   workdir=work, stats=meta, on_progress=None, chunks=c.id)
            new = [it for it in items if it.get("type") != "atem" and it.get("id") not in have]
            CD._ground_terms(new, lookup)
            merged, _dropped = CD._final_clean(CD._order(CD._plain(nodes) + new), work, remap)
        return merged

    def compile_rules(fabula: dict, *, order: str, source_name: str | None = None, now: Any = None) -> str:
        md, _info = CD.compile_short(fabula, complete=None, source_name=source_name, order=order,
                                     now=_utc_naive(now))
        return md

    return SimpleNamespace(derive_passages=derive_passages, derive_finish=derive_finish, derive_rules=derive_rules,
                           derive_gaps=derive_gaps, compile_rules=compile_rules, outline=CD.outline, short_footer=CD.short_footer,
                           rules_atem=CD.rules_atem, read_atem=CD._read_atem)


def docoes_engine() -> Any:
    """DocOES as `enumerate` and `compile` use it: a markdown document into a `doc/1` volume mapping, and back."""
    from types import SimpleNamespace

    from . import docoes

    def enumerate_(text: str, *, path: str) -> dict:
        stem = re.sub(r"[^a-z0-9]+", "-", Path(path).stem.lower()).strip("-") or "doc"
        return docoes.enumerate_markdown(text, doc_id=f"doc/{stem}", source_path=path)

    return SimpleNamespace(enumerate=enumerate_, compile=docoes.compile_doc)


def catalog_engine(project_dir: Path | None) -> Callable[[Path], dict | None]:
    """The surrounding catalog `context of` reads (THYM.md 16.1), as `ctx.engines["catalog"]`: a text's path -> the
    excerpt of its Canon volume's catalog, or of the project's, around it (`canon.catalog_excerpt`), or None."""
    def catalog(path: Path) -> dict | None:
        from . import canon as _canon
        return _canon.catalog_excerpt(Path(path), project_dir)
    return catalog


def engines(*, feed: Any = True, standing: Callable | None = None, catalog: Callable | None = None) -> dict:
    """The engines a run's moves reach as `ctx.engines`: `canon`, `docoes`, and `feed` (FEED's batch lookup when the
    dictionary is built, or the one given; `feed=None` for none). `standing` (a holotype value -> its standing, such as
    `first-party`) and `catalog` (a text's path -> the surrounding catalog excerpt) join when the host has them."""
    out: dict = {"canon": canon_engine(), "docoes": docoes_engine()}
    lookup = _feed() if feed is True else feed
    if lookup:
        out["feed"] = lookup
    if standing is not None:
        out["standing"] = standing
    if catalog is not None:
        out["catalog"] = catalog
    return out


# ---------------------------------------------------------------------------
# The prompt builders of the model-backed moves (THYM.md 12.2)
# ---------------------------------------------------------------------------

def _in(inputs: dict, name: str) -> str:
    pair = (inputs or {}).get(name)
    return _input_text(pair[0]) if pair else ""


def _passthrough(inputs: dict) -> list[dict] | None:
    """The messages an engine wrote itself, handed to the model unchanged (`EngineAdapter`, `derive`)."""
    import json
    raw = _in(inputs, "messages")
    if not raw:
        return None
    msgs = json.loads(raw)
    return [m for m in msgs if isinstance(m, dict)] if isinstance(msgs, list) else None


_STANCES_SAID = ('Say each claim at its stance or more weakly, never more strongly: axiom and observed plainly; '
                 'deduced with "it follows that"; opinion with "<the holder> holds that"; assumed with "it is assumed '
                 'that"; hearsay with "reportedly", or "<the source> says".')
_SENTENCES_FORM = """Return only a YAML mapping:
sentences:
  - say: <one sentence>
    cites: [<the id of every item this sentence says>]
  - say: <the next sentence>
    cites: [<ids>]
    paragraph: true
Put `paragraph: true` only on a sentence that starts a new paragraph. Every sentence cites at least one id from the
list, and never an id the list does not have. Use only the names, numbers and words the items give."""
_ORDER_SAID = {"told": "Tell the items in the order given: the order the author told them.",
               "weight": "Tell the claims in the order given, the weightiest first; then the events; then the terms."}


def _tell_messages(contract: dict, inputs: dict) -> list[dict]:
    if (msgs := _passthrough(inputs)) is not None:
        return msgs
    order = _in(inputs, "order") or "told"
    asks = _in(inputs, "asks")
    system = ("You tell a text again from its fabula: the items listed, each with its id. Write a short in plain "
              f"English that says nothing the items do not hold. {_ORDER_SAID.get(order, _ORDER_SAID['told'])}\n"
              f"{_STANCES_SAID}\nName every participant the first time; no pronoun without its noun.\n"
              + (f"Tell it in this morph, keeping each scale near its number:\n{asks}\n" if asks else "")
              + _SENTENCES_FORM)
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"The fabula's items:\n\n{_in(inputs, 'outline')}"}]


def _null_messages(contract: dict, inputs: dict) -> list[dict]:
    if (msgs := _passthrough(inputs)) is not None:
        return msgs
    system = ("You write the null telling of a fabula: the plainest telling that keeps every item, the reference "
              "every other telling is measured against.\n"
              "- Tell the items in the order given, one claim per sentence.\n"
              "- Use the commonest words that still say it; keep the items' own names and terms.\n"
              "- Short sentences: ten words or fewer on average. Split a long claim into two sentences.\n"
              "- Say observed and axiom claims plainly; a deduced claim with \"it follows that\"; an opinion with "
              "\"the author holds that\" (or \"<the holder> holds that\"); an assumed claim with \"it is assumed "
              "that\"; hearsay with \"reportedly\", or \"<the source> says\".\n"
              "- No figure of speech, no joke or irony, no allusion, no contraction, no hedge word (maybe, perhaps, "
              "might, could, probably, likely, seems), no I, we or you: the third person throughout.\n"
              "- One paragraph.\n" + _SENTENCES_FORM)
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"The fabula's items, in told order:\n\n{_in(inputs, 'outline')}"}]


def _expand_messages(contract: dict, inputs: dict) -> list[dict]:
    if (msgs := _passthrough(inputs)) is not None:
        return msgs
    words = int(_in(inputs, "words") or 300)
    pair = (inputs or {}).get("atem")
    a = pair[0].mapping() if pair and hasattr(pair[0], "mapping") else None
    a = a or {}
    of = ", ".join(str(i) for i in a.get("of") or []) or "the claims the atem names"
    atem = "\n".join(f"{k}: {a.get(k)}" for k in ("line", "focus", "push", "pull") if isinstance(a.get(k), str))
    system = (f"You open an atem out into a short of about {words} words: no more than {words}, and no fewer than "
              f"{words * 4 // 5}. Tell it from the fabula's items listed, each with its id, in the order given. Keep "
              f"the atem's line and its push, and say the claims it centres on ({of}). Say nothing the items do not "
              f"hold.\n{_STANCES_SAID}\nName every participant the first time; no pronoun without its noun.\n"
              + _SENTENCES_FORM)
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"The atem:\n{atem}\n\nThe fabula's items:\n\n{_in(inputs, 'outline')}"}]


def _atem_messages(contract: dict, inputs: dict) -> list[dict]:
    if (msgs := _passthrough(inputs)) is not None:
        return msgs
    from . import canon_prompts as P
    system = P.ATEM_SYSTEM
    if (inputs or {}).get("fabula"):
        system += ("of: a list of the ids of the items the atem centres on, from the list (the ids are in square "
                   "brackets).\n")
    return [{"role": "system", "content": system},
            {"role": "user", "content": P.ATEM_USER.format(context="", text=_in(inputs, "text"))}]


def _measure_messages(contract: dict, inputs: dict) -> list[dict]:
    if (msgs := _passthrough(inputs)) is not None:
        return msgs
    system = ("You judge three things about a text, sentence by sentence; the sentences are numbered.\n"
              "- figurative: the numbers of the sentences that use a figure of speech: a metaphor (\"the orchard "
              "woke\"), a simile (\"tidy as a ledger\"), personification (\"the strip feeds the bees\" is literal; "
              "\"the strip begs to be left alone\" is not).\n"
              "- humour: the numbers of the sentences that make a joke or an ironic turn (\"the parish's timing, as "
              "ever, impeccable\").\n"
              "- allusion: each reference to a work, a saying or a figure outside the text's subject (\"a Garden of "
              "Eden\", \"as Keats had it\"), as {sentence: <number>, to: <what it alludes to>}.\n"
              "A plain, literal sentence is none of these. Return only a YAML mapping:\n"
              "figurative: [<numbers>]\nhumour: [<numbers>]\nallusion: [{sentence: <number>, to: <work, saying or "
              "figure>}]\nUse an empty list where there is nothing.")
    user = (f"The text's sentences:\n{_in(inputs, 'sentences')}\n\nNames the text's fabula holds, which an allusion "
            f"may point past: {_in(inputs, 'candidates')}")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _morph_messages(contract: dict, inputs: dict) -> list[dict]:
    if (msgs := _passthrough(inputs)) is not None:
        return msgs
    system = ("You tell a short again in a morph. Keep its items: each sentence of the new telling cites the ids it "
              "says, from the ids the numbered sentences carry in square brackets. Say nothing they do not hold, and "
              f"say no claim more strongly than it was said.\n{_in(inputs, 'asks')}\n{_STANCES_SAID}\n"
              + _SENTENCES_FORM)
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"The short, sentence by sentence:\n{_in(inputs, 'sentences')}"}]


def _read_messages(contract: dict, inputs: dict) -> list[dict]:
    if (msgs := _passthrough(inputs)) is not None:
        return msgs
    words = _in(inputs, "words")
    system = ("You make a reading: someone else's fabula told in the reader's own morph, for the reader's occasion. "
              "It is the reader's telling, never the author's text: say nothing the items do not hold.\n"
              f"Tell it in this morph, keeping each scale near its number:\n{_in(inputs, 'asks')}\n"
              f"The occasion:\n{_in(inputs, 'occasion')}\n"
              + (f"About {words} words.\n" if words else "") + f"{_STANCES_SAID}\n"
              "Name every participant the first time; no pronoun without its noun.\n" + _SENTENCES_FORM)
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"The fabula's items, in told order:\n\n{_in(inputs, 'outline')}"}]


def _derive_messages(contract: dict, inputs: dict) -> list[dict]:
    """`derive`'s requests carry the messages Canon's derivation wrote, and pass through. A request that carries a
    text instead is asked as Canon asks one passage: the whole text, its lines numbered."""
    if (msgs := _passthrough(inputs)) is not None:
        return msgs
    from . import canon_prompts as P
    text = next((_input_text(pair[0]) for pair in (inputs or {}).values()
                 if getattr(pair[0], "type", None) in ("text", "short")), "")
    lines = text.replace("\r\n", "\n").split("\n")
    numbered = "\n".join(f"{n}| {ln}" for n, ln in enumerate(lines, 1))
    return [{"role": "system", "content": P.EMF_SYSTEM.format(source="text")},
            {"role": "user", "content": P.EMF_USER.format(terms="- (none)", source="text", start=1, end=len(lines),
                                                          passage=numbered)}]


PROMPTS = {"derive": _derive_messages, "tell": _tell_messages, "null": _null_messages, "expand": _expand_messages,
           "atem": _atem_messages, "measure": _measure_messages, "morph": _morph_messages, "read": _read_messages}
for _move, _builder in PROMPTS.items():
    _registry.prompt_for(_move)(_builder)


# ---------------------------------------------------------------------------
# The programs a run may pick (wave 2: the routes, the viewers and the readvisor tools share this one rule)
# ---------------------------------------------------------------------------

#: The programs enough ships: `defaults/thym/<name>.thym`, byte for byte the conformance suite's three
#: (`tests/fixtures/thym/programs/`; `tests/test_thym_host.py` pins the equality).
SHIPPED_PROGRAMS = Path(__file__).resolve().parent.parent / "defaults" / "thym"
PROGRAM_SUFFIX = ".thym"
_SKIP_DIRS = frozenset({".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "rness"})
_WALK_CAP = 2000                        # directories visited per root; a library is listed, never exhausted


def program_name(path: Path) -> tuple[str | None, str | None]:
    """`(name, problem)`: the name a `.thym` file declares (`program <name>`), read by the parser; the problem
    instead when it does not parse or declares no program."""
    from .thym import parse as _parse
    try:
        text = Path(path).read_bytes().decode("utf-8")
    except OSError as e:
        return None, f"cannot be read: {e.strerror or e}"
    except UnicodeDecodeError:
        return None, "is not UTF-8"
    module = _parse.parse(text, path=str(path))
    if isinstance(module, Refusal):
        return None, module.message
    for b in module.blocks:
        if b.kind == "program":
            return b.name, None
    return None, "declares no program"


def _walk(root: Path) -> list[Path]:
    """Every `*.thym` under `root`, the harness folders and hidden ones skipped, sorted by relative path."""
    out: list[Path] = []
    for seen, (dirpath, dirnames, filenames) in enumerate(os.walk(root)):
        if seen >= _WALK_CAP:
            break
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS and not d.startswith("."))
        for f in sorted(filenames):
            if f.endswith(PROGRAM_SUFFIX) and not f.startswith("."):
                out.append(Path(dirpath) / f)
    return out


def list_programs(project_dir: Path | None = None, *, canon: bool = True, shipped: bool = True) -> list[dict]:
    """Every program a run may pick, in the order a bare name resolves: the project's own `*.thym` files, the Canon
    store's volumes' (`canon:<volume>/<rel>`), then the shipped ones (`defaults/thym/`). Each is `{name, where, path,
    rel, problem}`: `where` is project, canon or shipped; `path` the file; `rel` what the app shows and the tools
    accept (a project-relative path, a `canon:` path, or the shipped file's name); `problem` is set, and `name`
    None, for a file that does not parse. A missing root lists nothing."""
    out: list[dict] = []

    def add(where: str, root: Path, prefix: str) -> None:
        if not root.is_dir():
            return
        for p in _walk(root):
            name, problem = program_name(p)
            rel = prefix + p.relative_to(root).as_posix()
            out.append({"name": name, "where": where, "path": str(p), "rel": rel, "problem": problem})

    if project_dir is not None:
        add("project", Path(project_dir), "")
    if canon:
        try:
            from . import canon as _canon
            store = _canon.root()
            for v in _canon.list_volumes():
                add("canon", store / v["name"], f"canon:{v['name']}/")
        except Exception:  # noqa: BLE001, S110 — a store that cannot be read lists no programs
            pass
    if shipped:
        add("shipped", SHIPPED_PROGRAMS, "")
    return out


def find_program(ref: str, project_dir: Path | None = None) -> Path | None:
    """The file a program reference names, or None. `ref` is a path when it ends in `.thym` or holds a slash (a
    project-relative path, or a `canon:` store path), else a program's declared name, resolved in
    `list_programs`' order: the project's first, then the store's, then the shipped one."""
    ref = (ref or "").strip()
    if not ref:
        return None
    if ref.endswith(PROGRAM_SUFFIX) or "/" in ref:
        from . import canon_tools as _ct
        try:
            if _ct.store_prefix(ref):
                p = _ct.resolve(Path("."), ref)            # a store path never reads the project
            elif project_dir is not None:
                p = _ct.resolve(Path(project_dir), ref)
            else:
                p = Path(ref)
        except _ct.TextTargetError:                        # absolute, or `..`: no program
            return None
        if p.is_file():
            return p
        if "/" not in ref and not _ct.store_prefix(ref) and (SHIPPED_PROGRAMS / ref).is_file():
            return SHIPPED_PROGRAMS / ref                   # a shipped file's name, when the project has no such file
        return None
    for entry in list_programs(project_dir):
        if entry["name"] == ref:
            return Path(entry["path"])
    return None
