# Writing programs in enough: the reference

*Every way in to an authored fabulac, with an example each: the `fabulac` tool's words, the routes, the command line,
the client library, the moves and the checks. enough 0.8, API promise 1. `tests/test_api_promise.py` holds this table
to the code: a route, a word or a command missing here fails it.*

An **authored fabulac** is the fabula of a program you write in enough: `tally.fabulac.cosm`, whose `source` says
`kind: authored`. Entailing it writes the program beside it, in `tally/`. Only an authored fabulac's program is ever
run, and only in enough's sandbox: a folder of its own, no network, Python's standard library only, limits on time,
output and disk, and a stop. On macOS memory is not limited. A service is authored and entailed, and refused at run:
serving comes in a later minor.

There are three doors, and they do the same things by the same functions (`enough/fabulac_first.py`):

- the page and the readvisor's **`fabulac` tool**, with a `<do>` word;
- the **command line**, `python -m enough.fabulac`, with no enough running;
- the **client library**, `enough_client` (one file, `enough/enough_client.py`, standard library only), over the
  **routes** of a running enough.

## The starters

Three authored fabulacs to begin from, each passing its checks (`defaults/fabulac-starters/`):

| kind | name | what it is |
|---|---|---|
| tool | `tally` | a command, `tally count PATH`, and a function, `count_words(text)`; three cases |
| library | `keyval` | `split_pair(line)` and `join_pair(key, value)`; three cases, one of them an error |
| service | `greet` | `greeting(name)`; one case. Entailed, and refused at run |

Begun under another name, a starter's name is changed everywhere it is a whole word (the command, the error it
prints, the module it starts as), and the day, who authored it and the licence are yours.

## The `fabulac` tool's words

Each is `<tool name="fabulac">` with a `<path>` (the program's name, or its `.fabulac.cosm`) and a `<do>`.

| word | what it does | example |
|---|---|---|
| `<do>starters</do>` | lists the starters | `<tool name="fabulac"><path>.</path><do>starters</do></tool>` |
| `<do>begin</do>` | begins an authored fabulac (a job), or from a `<starter>`; again, takes the interview up: settles answers, raises the next stage. Tags `<kind>`, `<licence>`, `<brief>`, `<by>`, `<starter>` | `<path>tally</path><do>begin</do><starter>tool</starter><licence>MIT</licence>` |
| `<do>status</do>` | where it stands: the interview's stage and the questions waiting, the entailment file by file, the last test or run | `<path>tally</path><do>status</do>` |
| `<do>add</do>` | adds the person's sentence as a requirement, decision, case or interface (`<as>`, `<says>`) | `<path>tally</path><do>add</do><as>requirement</as><says>It never writes.</says>` |
| `<do>check</do>` | the fabulac's checks, and the requirements of force *must* no case shows | `<path>tally</path><do>check</do>` |
| `<do>entail</do>` | entails it as its program (a job; only a model writes sources); `<overwrite>` names hand edits to write over | `<path>tally</path><do>entail</do>` |
| `<do>test</do>` | runs the entailed tests in the sandbox (a job) | `<path>tally</path><do>test</do>` |
| `<do>run</do>` | runs the tool in the sandbox (a job): `<args>` its arguments, `<input>` its input, `<hand>` project files handed over read-only | `<path>tally</path><do>run</do><args>count notes.md</args><hand>notes.md</hand>` |
| `<do>stop</do>` | stops what of it is running: a test, a run, a job | `<path>tally</path><do>stop</do>` |
| `<do>moved</do>` | what moved since the last entailment, and every file changed by hand | `<path>tally</path><do>moved</do>` |
| `<do>keep</do>` | keeps a file changed by hand (`<file>`, `<because>`): a recorded decision | `<path>tally</path><do>keep</do><file>tally/__main__.py</file>` |
| `<do>let-go</do>` | lets a kept file go: the next entailment tells it again | `<path>tally</path><do>let-go</do><file>tally/__main__.py</file>` |
| `<do>take-back</do>` | takes a hand edit back into the fabulac as questions (a job; a model reads the file) | `<path>tally</path><do>take-back</do><file>tally/__main__.py</file>` |
| `<do>head</do>` | makes a head fabulac over parts (`<parts>`, comma-separated) | `<path>counter</path><do>head</do><parts>counter-core, counter-cli</parts>` |
| `<do>parts-moved</do>` | which parts of a head moved | `<path>counter</path><do>parts-moved</do>` |

For a folder of Python decompiled into its fabulac (not authored), the words are the 0.6 ones:
`<do>build</do>`, `<do>status</do>`, `<do>compile</do>` (with `<what>`), `<do>cancel</do>`. Its code is read, never
run.

## The routes (API promise 1)

Every route that starts a run or writes (each POST here) needs the header `X-Enough-Api: 1`, or it answers 403 with
a sentence. The page and the client send it. A job route answers `{"job": {...}}`; poll
`GET /api/canon/job/{job_id}` until `state` is `done` (its `result`), `failed` or `cancelled`. A refusal is a 4xx
with `{"detail": "<the sentence>"}`.

| route | takes | gives | example |
|---|---|---|---|
| `GET /api/fabulac/promise` | | `name version header routes` | `curl 127.0.0.1:3456/api/fabulac/promise` |
| `GET /api/fabulac/starters` | | `starters` | `curl 127.0.0.1:3456/api/fabulac/starters` |
| `POST /api/fabulac/begin` | `path kind? licence? brief? by? starter? mode? route?` | a job, or from a starter `fabulac state waiting message` | `{"path": "tally", "starter": "tool", "licence": "MIT"}` |
| `POST /api/fabulac/answer` | `path answers` | `path recorded refused` | `{"path": "tally", "answers": [{"question": "D:question/…", "says": "Ada"}]}` |
| `GET /api/fabulac/status` | `path` | `fabulac program interview entailment last_run jobs` | `/api/fabulac/status?path=tally` |
| `POST /api/fabulac/add` | `path as says fields?` | `fabulac added item` | `{"path": "tally", "as": "case", "says": "Two words count 2.", "fields": {"given": {"calls": "C:interface/count-words", "arguments": {"text": "a b"}}, "expect": {"value": 2}}}` |
| `GET /api/fabulac/check` | `path` | `ok errors warnings uncovered source entailment` | `/api/fabulac/check?path=tally` |
| `POST /api/fabulac/entail` | `path overwrite? route? model? calls?` | a job; its result `fabulac entailed files told removed` | `{"path": "tally"}` |
| `GET /api/fabulac/moved` | `path` | `folder entailed files moved edited gone kept new tell` | `/api/fabulac/moved?path=tally` |
| `POST /api/fabulac/keep` | `path files because?` | `kept` | `{"path": "tally", "files": ["tally/__main__.py"]}` |
| `POST /api/fabulac/let-go` | `path files` | `released` | `{"path": "tally", "files": ["tally/__main__.py"]}` |
| `POST /api/fabulac/take-back` | `path file route? model?` | a job; its result `path questions refused` | `{"path": "tally", "file": "tally/__main__.py"}` |
| `POST /api/fabulac/test` | `path` | a job and `run`; its result the sandbox's: `ok ran exit_code stdout stderr stopped_by enforced guarantees` | `{"path": "tally"}` |
| `POST /api/fabulac/run` | `path args? stdin? hand_over?` | a job and `run`; its result as for test, `ok` the tool's exit 0 | `{"path": "tally", "args": ["count", "notes.md"], "hand_over": ["notes.md"]}` |
| `POST /api/fabulac/stop` | `path?` or `run?` | `stopped message` | `{"path": "tally"}` |
| `POST /api/fabulac/head` | `path parts name? licence? by?` | `head uri parts` | `{"path": "counter", "parts": ["counter-core", "counter-cli"]}` |
| `GET /api/fabulac/parts-moved` | `path` | `head parts moved` | `/api/fabulac/parts-moved?path=counter` |
| `GET /api/canon/job/{job_id}` | | `id kind state message result error` | `/api/canon/job/cn7` |

With curl, a gated route: `curl -H 'X-Enough-Api: 1' -H 'Content-Type: application/json' -d '{"path": "tally"}'
127.0.0.1:3456/api/fabulac/test`.

## The command line

`python -m enough.fabulac [--project DIR] [--json] <command> …`, in the project (or with `--project`), no server
running. Exit 0 done; 1 done and failed (a test, a check, the tool's own status); 2 refused, nothing written.

| command | example |
|---|---|
| `python -m enough.fabulac starters` | lists the starters |
| `python -m enough.fabulac begin PATH` | `begin tally --starter tool --licence MIT --by Ada`, or `begin tally --kind library --brief brief.md` |
| `python -m enough.fabulac answer PATH QUESTION SAYS` | `answer tally D:question/aim "It counts words."` (or `--unknown`, `--declined`, `--skip`) |
| `python -m enough.fabulac status PATH` | `status tally` |
| `python -m enough.fabulac add PATH AS SAYS` | `add tally requirement "It never writes." --field force='"must"'` |
| `python -m enough.fabulac check PATH` | `check tally` |
| `python -m enough.fabulac entail PATH` | `entail tally --model local` (only a model writes sources); `--overwrite tally/__main__.py` |
| `python -m enough.fabulac moved PATH` | `moved tally` |
| `python -m enough.fabulac test PATH` | `test tally` |
| `python -m enough.fabulac run PATH -- ARGS` | `run tally --hand notes.md -- count notes.md` (Ctrl-C stops it) |
| `python -m enough.fabulac keep PATH FILE` | `keep tally tally/__main__.py --because "my own wording"` |
| `python -m enough.fabulac let-go PATH FILE` | `let-go tally tally/__main__.py` |
| `python -m enough.fabulac take-back PATH FILE` | `take-back tally tally/__main__.py --model local` |
| `python -m enough.fabulac head PATH PART…` | `head counter counter-core counter-cli` |
| `python -m enough.fabulac parts-moved PATH` | `parts-moved counter` |

## The client library

```python
import enough_client                  # copy enough/enough_client.py beside your program
e = enough_client.Enough()            # http://127.0.0.1:3456, or ENOUGH_URL
```

| call | example |
|---|---|
| `e.check_promise()` | refuses an enough that keeps another promise |
| `e.starters()` | `[s["name"] for s in e.starters()]` |
| `e.begin(path, …)` | `e.begin("tally", starter="tool", licence="MIT")`; waits for the job unless `wait=False` |
| `e.answer(path, answers)` | `e.answer("tally", [{"question": "D:question/aim", "says": "It counts words."}])` |
| `e.status(path)` | `e.status("tally")["interview"]["shown"]` |
| `e.add(path, as_, says, fields=…)` | `e.add("tally", "requirement", "It never writes.", fields={"force": "must"})` |
| `e.check(path)` | `e.check("tally")["ok"]` |
| `e.entail(path, overwrite=…)` | `e.entail("tally")` |
| `e.moved(path)` | `e.moved("tally")["edited"]` |
| `e.keep(path, files, because=…)` | `e.keep("tally", ["tally/__main__.py"])` |
| `e.let_go(path, files)` | `e.let_go("tally", ["tally/__main__.py"])` |
| `e.take_back(path, file)` | `e.take_back("tally", "tally/__main__.py")` |
| `e.test(path)` | `e.test("tally")["ok"]` |
| `e.run(path, args, stdin=…, hand_over=…)` | `e.run("tally", ["count", "notes.md"], hand_over=["notes.md"])["stdout"]` |
| `e.stop(path)` | `e.stop("tally")`, or `e.stop(run="<run id>")` |
| `e.head(path, parts)` | `e.head("counter", ["counter-core", "counter-cli"])` |
| `e.parts_moved(path)` | `e.parts_moved("counter")["moved"]` |
| `e.job(job_id)`, `e.wait(answer)` | a job's snapshot; its result once done |

A refusal raises `enough_client.EnoughError` (`status`, `detail`: enough's sentence).

## The moves (Thym)

| move | what it does | example |
|---|---|---|
| `author` | begins an authored fabulac's catalog, from a brief or from nothing (`as tool`, `library`, `service`) | `give author brief as tool` |
| `add` | the person's sentence as a new item | `add said as requirement with f` |
| `compare` | what differs between two fabulacs, item by item | `compare f with g` |
| `uncovered` | the requirements of force *must* no case shows | `uncovered f` |
| `entail … as code` | an authored fabulac's entailment (`entail-authored-python.thym`) | `entail f as code` |

## The checks

| check | of | holds when | example of a failure |
|---|---|---|---|
| `authored-source` | `author`, `add` | the source is the authored form, `program` names a kind, every new item is an axiom in the person's words | "N:aim/x is not an axiom" |
| `cases-entailed` | `entail … as code`, the fabulac | the tests file is the one the cases give, by rules; each case entailed or named with why | "P:case/huge-file: its given is still a question" |
| `requirement-cased` | the fabulac (a warning) | every requirement of force *must* names a case in `checked-by` | "N:requirement/never-writes has no case" |
| `files-present` | `entail … as code` | every planned source and every rules file is there, as recorded | "tally/__main__.py is missing" |
| `interfaces-present` | `entail … as code` | each function is defined in its file with its parameters; a command's file defines `main` | "count_words is not defined in tally/__init__.py" |
| `footer` | `entail … as code` | `ENTAILED.md` ends with its footer and the licence line | "ENTAILED.md has no footer" |
| `parts-resolve` | a head and its parts | each part is there, of its URI, naming this head; every `told-in` and `stated-in` resolves | "oes:fabula/counter-cli is not known" |
| `interfaces-agree` | a head and its parts | an interface stated in the head and kept in a part agree (name, surface, signature, parameters) | "count-lines: signature differs" |
