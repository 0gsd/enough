# the enough developers' manual

> Writing programs fabulac-first in enough: a worked example from an idea to a running tool, a cookbook of short recipes, tips, and the full reference. Written against enough **0.8.0**, in English.

This part of the manual is for people who write programs. It is in English in 0.8; the help center says so in its own languages, and the translations follow in a later minor.

**Fabulac-first** is a way to write a program in enough. You do not write the code first. You write what the program is for, how a person reaches it, what it needs, what it leaves out, and the cases it must get right. That is the program's fabulac. Then you entail it: enough writes the program from the fabulac, writes its tests from the cases, and runs the tests in a sandbox. When you want the program to change, you change the fabulac and entail again. Only what moved is written again.

The help center tells the other way round, a folder of code taken apart into its fabulac, in its section 12.7. Everything here is about a fabulac you author.

---

## 1. Before you start

### 1.1 The words

- **authored fabulac**: the fabula of a program you write in enough, `tally.fabulac.cosm`. Its `source` says `kind: authored`, with the language, the licence you offer it under, who authored it and when. Every item in it is an axiom: your words, not a reading of someone else's code.
- **program kind**: what the program is, in the catalog's `program` block: a `tool` (a command a person types), a `library` (functions another program calls), or a `service` (a program that serves on a port). The kind decides what enough can start.
- **case**: one example the program must get right, written as what is given and what is expected. A case written as data becomes a test, by rules. Cases are the judge: a program is right when its cases pass.
- **entailment**: what entailing the fabulac writes, the folder `tally/` beside `tally.fabulac.cosm`. It holds the sources, the tests, `pyproject.toml`, `RUNNING.md` and `ENTAILED.md`, the record of where every file came from.
- **the sandbox**: where enough runs an entailment's tests and its tool. A copy of the folder, with no network, Python's standard library only, limits, and a stop (section 6.10).
- **hand edit**: a file in the entailment whose bytes are not the ones the last entailment wrote. enough names it, file by file, and you choose what happens to it (section 2.12).
- **head fabulac**: a fabulac over parts. Each part is a fabulac of its own; the head names them and states the interfaces between them once.
- **starter**: an authored fabulac to begin from. There are three, one per kind.

### 1.2 The three doors

Everything here can be done three ways. All three call the same functions, so they give the same answers.

1. **The page and your readvisor.** With the transcognition paradigm on and the macrocosm-oes skill on, say what you want: "begin a tool called tally from the starter". The readvisor uses the `fabulac` tool with a `<do>` word. The page calls the same routes.
2. **The command line.** `python -m enough.fabulac`, in your project folder. It needs no enough running. In a checkout of enough, run it with enough's own environment: `uv run python -m enough.fabulac …`.
3. **The client library.** `enough_client`, one Python file with the standard library only, over the routes of a running enough. Copy `enough/enough_client.py` beside your script and `import enough_client`.

Every recipe in section 4 gives all three.

### 1.3 What 0.8 does not do

Say no more than enough does. In 0.8:

- **Serving is specified, not on.** A service is authored and entailed. Its port, its stop and what it may reach are in its fabulac (`program.serve`). enough refuses to test or run it: "serving comes in a later minor". Its source is entailed and can run elsewhere.
- **Packages beyond the standard library are named and pinned, not run here.** A fabulac may need `requests`. Entailing it pins the package in `pyproject.toml` (`requests==2.32.3` when a version is given). enough will not test or run that program: it says the program needs a package outside the standard library, and which.
- **Code you did not author is read, never run.** A cshort, the code entailed from a fabulac decompiled from someone else's folder, is read in enough and never run there. Only the entailment of a fabulac you authored runs, and only in the sandbox.
- **Memory is not limited on macOS.** The sandbox limits time, processor time, output, disk and file size. On macOS it cannot limit memory, and it promises nothing about memory.
- **Linux needs bubblewrap.** Without `bwrap`, enough refuses to run, and says why. Other systems are refused.
- **The language is Python.** You author Python tools, libraries and services. Go and Rust are languages enough can carry a program into by transconception; you do not author in them yet.
- **Only a model writes sources.** Entailing asks a model for each source file. With no model running, or agent free, entailing is refused. Everything else (beginning from a starter or a brief, adding, checking, testing, running, keeping in step) runs by rules.

### 1.4 What you need

- enough 0.8, with a project open.
- For the readvisor door: the transcognition paradigm on, and the macrocosm-oes skill on (the help center, its section 20.5).
- For entailing: a model, on this machine or on the cloud.
- For the client door: enough running. It listens on `http://127.0.0.1:3456` unless `ENOUGH_URL` says another address.
- For the sandbox: macOS with `/usr/bin/sandbox-exec`, or Linux with bubblewrap.

### 1.5 The page

The page's door is the fabulac card. It calls the routes of section 6.3, and every POST it makes carries the header `X-Enough-Api: 1`.

- **Begin.** Option-click a folder in the project tree and choose **begin a fabulac here…**. Say what it is (a tool, a library or a service), its name, and how to begin: from a starter (at once), from a brief (its path from the project's top folder), or from nothing (the interview asks). The licence and the author are optional; the interview asks for a licence left out.
- **Open it again.** On a fabulac you authored, **entail and run…** opens the card: in the tree's menu, or in the cosm viewer's toolbar. On the folder it entailed, the menu offers **entail again…**, **test and run…** and **what moved…**, and never **build its fabulac…**: that folder is an entailment, not a program to decompile. The tree tags the folder **entailment**.
- **The interview.** The card shows the stages and the one or two questions asked now. Answer a text question on the card and **send these answers**; **go on** settles them and asks the next stage. Every question, of any kind, can be answered in the questions card.
- **Add and check.** Add a requirement, a decision, a case or an interface in your own words. A case's `given` and `expect` may be data (section 6.8). **check it** shows the checks and the requirements no case shows yet.
- **Entail.** **entail** (or **entail again**) starts the job; the model line says where the model runs. The card lists every file that moved, is new, is gone, or was changed by hand. A file changed by hand has its three choices on its row: **write over it**, **keep it** (and later **let it go**), **take it back**. Entailing waits until each one is chosen.
- **Test and run.** **run its tests**; for a tool, **its arguments**, **files handed over** (paths from the project's top folder, separated by commas) and **its input**, then **run it**. **stop** ends a run. The output is shown as the sandbox kept it, the first 20,000 characters on the card. Under each result, the card says whether the box held the run, and lists what it promised for that run and what not. A service is refused with the sentence of section 1.3.
- **A head.** Name a head and its other parts, and the card makes it over this fabulac and them. On a head, the card lists its parts and which moved.

The page offers nothing that runs a cshort.

---

## 2. A worked example: tally

From an idea to a running tool, then a change, then a hand edit. The output under each command is what it printed on a scratch project, in this order, with run ids and dates shortened. Where a model is asked, one that always writes the same tally stood in.

### 2.1 The idea

You want a small command that counts the words in a text file: `tally count notes.md` prints `4`. A file that is not there is an error, with exit status 2. It needs nothing but Python.

That is close to the tool starter, so begin from it.

### 2.2 Begin from the starter

List the starters:

```
$ python -m enough.fabulac starters
tool: tally: tally counts the words of a text file, from a terminal.
library: keyval: keyval reads and writes lines of key=value.
service: greet: greet answers a greeting on a port of this machine.
```

Begin yours from the tool starter, under the licence you offer it on, with your name as its author:

```
$ python -m enough.fabulac begin tally --starter tool --licence MIT --by Ada
tally.fabulac.cosm begun from the tool starter: change it to say your program, then entail
```

Begun under another name (`begin wordcount --starter tool`), the starter's name is changed everywhere it is a whole word: the command, the error it prints, the module it starts as. The day, the author and the licence are yours.

To your readvisor: "begin a tool called tally from the tool starter, MIT licence, by Ada". The call:

```
<tool name="fabulac"><path>tally</path><do>begin</do><starter>tool</starter><licence>MIT</licence><by>Ada</by></tool>
```

From a script:

```python
import enough_client
e = enough_client.Enough()
e.begin("tally", starter="tool", licence="MIT", by="Ada")
```

### 2.3 Or begin from a brief

A brief is a markdown text you write. Its headings say what each part answers. The paragraphs under the title say what it is for.

```
# linecount

linecount says how many lines a text file holds.

## For whom

People who keep notes in plain text files.

## Ways in

- the command `linecount PATH`

## Leaves out

- It does not count words.

## Must

- It never writes a file.
```

```
$ python -m enough.fabulac begin linecount --kind tool --brief brief.md --licence MIT --by Ada
linecount.fabulac.cosm: 4 questions wait for you; agent-free: no model was asked; the brief was read by rules alone
  D:question/the-command-linecount-path-surface: What should the surface of "the command `linecount PATH`" say?
  D:question/ada-unsure: Is this right, and if not, what is? "Ada authored linecount."
```

Each list item, or paragraph, under a heading the interview knows becomes one item, in your words. What the brief did not say is asked. The headings it reads are in section 6.12. With a model, the model only places the passages under headings the rules do not know; the items still hold your words.

### 2.4 Or begin with the interview

```
$ python -m enough.fabulac begin dicey --kind tool
dicey.fabulac.cosm: 8 questions wait for you (stage: for); agent-free: no model was asked
  D:question/aim: What should dicey do, in a sentence or two: what does a person have once it has run?
  D:question/audience: Who is dicey for, and what do they already know?
```

The interview asks in six stages, one stage at a time, one or two questions at a time: what it is for and for whom; the ways in; what it needs and the settings it reads; what it leaves out; the cases; the open questions. Answer, then `begin` again to settle the answers and raise what follows:

```
$ python -m enough.fabulac answer dicey D:question/aim "dicey rolls dice: dicey roll 2d6 prints the sum."
$ python -m enough.fabulac answer dicey D:question/audience "People who play board games at a terminal."
$ python -m enough.fabulac answer dicey D:question/use --skip
$ python -m enough.fabulac begin dicey
dicey.fabulac.cosm: 6 questions wait for you (stage: for)
  D:question/use: Name one thing a person will do with dicey, from start to end.
  D:question/occasion: What set you to make dicey: a problem, a moment, a need?
```

`--unknown` says you don't know, `--declined` says you won't say, `--skip` leaves it for later. Each answer is written in a sitting file beside the fabulac (`dicey.fabulac.answers-….cosm`), so nothing you say is lost before it is settled.

### 2.5 Read what you have

```
$ python -m enough.fabulac status tally
tally.fabulac.cosm: an authored tool; interview next raise, stage for
not entailed yet
```

The fabulac is a plain text file. Open it in the cosm viewer, or read it as text. The tool starter holds:

- the catalog: `source: {kind: authored, language: python, licence, by, at}` and `program: {kind: tool, start: [-m, tally]}`;
- `R:maker/…`, the author; `R:licence/licence`, the licence; `C:dependency/python`, Python 3.11 and its standard library;
- `N:aim/count-words`, what it is for; `N:use/count-a-file`, one use;
- two requirements of force *must*, each naming the case that shows it in `checked-by`;
- two interfaces: `C:interface/command-count` (`tally count PATH`, a command) and `C:interface/count-words` (`count_words(text: str) -> int`, a function);
- three cases: `P:case/three-words`, `P:case/missing-file`, `P:case/count-function`.

You may change it by hand. It is your file, and it is the program's source now.

### 2.6 Cases are the judge

Here is the first case, as the fabulac holds it:

```yaml
- id: P:case/three-words
  type: case
  name: Three words
  summary: A file holding three words counts 3.
  of: [C:interface/command-count]
  given:
    files: {notes.md: "one two three\n"}
    steps:
      - arguments: [count, notes.md]
  expect:
    steps:
      - {exit: 0, output: "3\n", error-output: ""}
```

`given` and `expect` are data for one surface: a command (files, environment, steps of arguments and input; each step's exit, output and error output, and the files after) or a function (the interface it calls and its arguments; the value it returns or the error it raises). Section 6.8 has both shapes whole.

A case in data becomes a test, by rules, never by the model that writes the code. A case told only in words is still valid: a model writes its test, and the test says so. A case whose `given` is still a question is not entailed, and the checks say why.

Add one more case, that an empty file counts 0:

```
$ python -m enough.fabulac add tally case "An empty file counts 0." \
    --field 'of=["C:interface/command-count"]' \
    --field 'given={"files": {"empty.md": ""}, "steps": [{"arguments": ["count", "empty.md"]}]}' \
    --field 'expect={"steps": [{"exit": 0, "output": "0\n", "error-output": ""}]}'
added P:case/an-empty-file-counts-0 to tally.fabulac.cosm
```

Each `--field` is a name and a value in JSON. A value that is not JSON is taken as words.

### 2.7 Check it

```
$ python -m enough.fabulac check tally
tally.fabulac.cosm: no errors, 0 warning(s)
```

`check` runs the fabulac's checks and lists every requirement of force *must* that no case shows. Exit 0 means no error; 1 means an error. A warning does not stop you. Check before you entail, and after every change.

### 2.8 Entail it

Entailing asks a model for each source file. Everything else in the folder is written by rules.

```
$ python -m enough.fabulac entail tally --model local
wrote tally/ (7 files), tally.catem-2026-11-19-0136.md
```

`--model local` asks this machine's model; `--model cloud` goes through enough's gate to the cloud. With no `--model`, the command line refuses: "only a model writes sources: entail with --model local (or cloud)".

The folder beside the fabulac:

```
tally/
  ENTAILED.md          where every file came from, with its fingerprint
  RUNNING.md           how to run its tests and start it, and what enough runs here
  pyproject.toml       its name, version, Python, entry point, dependencies, [tool.enough]
  tally/__init__.py    count_words (from C:interface/count-words and its case)
  tally/__main__.py    the command, main(argv=None) -> int
  tests/__init__.py
  tests/test_cases.py  one test per case in data, written by rules
```

`ENTAILED.md` starts with its footer, *an entailment of tally.fabulac.cosm, in Python, entailed on 2026-11-19 by …*, then a table: each file, what it was told from (`rules`, or the item ids), its sha256, and a digest of what it was told from. It ends with the licence of the source. The fabulac records the same, in its `entailed` block. That is how enough knows, later, what moved and what was changed by hand.

Entailing also writes a catem beside the fabulac, `tally.catem-….md`: what a person can do with the program, in a page.

### 2.9 Test it in the sandbox

```
$ python -m enough.fabulac test tally
the tests passed (run 20261118-…, 0.2s)
test_an_empty_file_counts_0 (tests.test_cases.Cases.test_an_empty_file_counts_0)
P:case/an-empty-file-counts-0: An empty file counts 0. ... ok
test_count_function (tests.test_cases.Cases.test_count_function)
P:case/count-function: count_words counts runs between white space. ... ok
test_missing_file (tests.test_cases.Cases.test_missing_file)
P:case/missing-file: A file that is not there is an error, exit 2. ... ok
test_three_words (tests.test_cases.Cases.test_three_words)
P:case/three-words: A file holding three words counts 3. ... ok

Ran 4 tests in 0.071s

OK
```

The tests run in a copy of the folder, in the sandbox. Each test says the case it came from. Exit 0 means they passed; 1 means one failed, and its output says which case and how.

### 2.10 Run it

The tool runs in the sandbox too. It sees nothing of your project unless you hand a file over. A handed-over file is a copy it can read and cannot write, and an argument equal to its path is pointed at the copy.

```
$ python -m enough.fabulac run tally --hand notes.md -- count notes.md
the tool exited with 0 (run 20261118-…, 0.1s)
4
$ python -m enough.fabulac run tally -- count gone.md
the tool exited with 2 (run 20261118-…, 0.1s)
tally: gone.md: no such file
```

Everything after `--` is the tool's own arguments. The command's exit status is 0 when the tool exited 0, and 1 when it did not. Ctrl-C stops the run.

### 2.11 Change the fabulac, entail again

Add a requirement:

```
$ python -m enough.fabulac add tally requirement "It never writes a file." --field 'force="must"'
added N:requirement/it-never-writes-a-file to tally.fabulac.cosm
```

`check` now warns that no case shows it (`requirement-cased`), and lists it under *requirements no case shows*. Give it a case, or name one in its `checked-by`. A case added after an entailment also makes `check` report an error, `cases-entailed`: the tests file no longer holds every case. Entailing again puts that right.

Ask what moved since the last entailment:

```
$ python -m enough.fabulac moved tally
ENTAILED.md: in step
RUNNING.md: moved
pyproject.toml: in step
tally/__init__.py: moved
tally/__main__.py: moved
tests/__init__.py: in step
tests/test_cases.py: moved
```

A file *moved* when what it was told from changed. Entail again, and only the moved files are told again; the files in step are kept as they are, byte for byte:

```
$ python -m enough.fabulac entail tally --model local
wrote tally/ (7 files), tally.catem-2026-11-19-0137.md
```

The answer's `told` (with `--json`) lists the files whose bytes changed. Here a model was asked for the two sources again and wrote the same bytes, so `told` named `ENTAILED.md`, `RUNNING.md` and `tests/test_cases.py`. `moved` says *in step* for every file again.

### 2.12 A hand edit, and its three choices

You change one word in `tally/tally/__main__.py` by hand: the error now says *not found*. enough sees it:

```
$ python -m enough.fabulac moved tally
…
tally/__main__.py: edited by hand
…
```

The tests say what the edit broke, since the case still expects *no such file*:

```
$ python -m enough.fabulac test tally
the tests failed (run 20261118-…, 0.2s)
…
AssertionError: 'tally: gone.md: not found\n' != 'tally: gone.md: no such file\n'
```

Entailing again is refused, and nothing is written:

```
refused: tally/ holds files the fabulac did not write as they are: tally/__main__.py. Nothing was written: keep them, write over them, or take them back first
```

You have three choices, file by file.

1. **Keep it.** The file stays as you wrote it, and a decision says so in the fabulac (`N:decision/kept-by-hand-…`, with your reason). It is never asked again or written over, until you let it go.

   ```
   $ python -m enough.fabulac keep tally tally/__main__.py --because "my own wording of the error"
   kept tally/__main__.py as changed by hand
   $ python -m enough.fabulac let-go tally tally/__main__.py
   let go of tally/__main__.py: the next entailment tells it again
   ```

2. **Write over it.** Name the file, and the next entailment tells it again from the fabulac:

   ```
   $ python -m enough.fabulac entail tally --model local --overwrite tally/__main__.py
   wrote tally/ (7 files), tally.catem-2026-11-19-0137-2.md
   ```

   `told` names `tally/__main__.py`; the tests pass again.

3. **Take it back.** A model reads the file against the fabulac and raises a question for each thing it says that the fabulac does not: *take it back*, or *leave it out*. Answer them like any question; what you take back enters the fabulac, and the next entailment tells the file from it.

   ```
   $ python -m enough.fabulac take-back tally tally/__main__.py --model local
   ```

Keep is right for a change the fabulac has no words for. Take back is right when the change is something the program should say. Write over is right when the edit was a mistake.

### 2.13 What you have now

- `tally.fabulac.cosm`: the program's source, in your words, with four cases and its record of what was entailed;
- `tally/`: a Python package you can read, install (`pip install .` in the folder) and run anywhere Python 3.11 runs;
- `tally.catem-….md`: what a person can do with it;
- runs in `~/enough/thym/sandbox/`, one folder each, with the result in `out/result.json`.

From here on, change the fabulac, not the code.

---

## 3. A second worked example: a program of the owner's

<!-- F8: the owner's own program, written fabulac-first from start to end (the tracker entry fabulac-first, F8). This section is filled once that program is authored, entailed and its core's cases pass in the sandbox. -->

*This place is kept for the second worked example: a real program, larger than tally, written fabulac-first in enough by the person who makes enough. It will go from an inventory of what the program should do, through its fabulac and its cases, to its entailment, and will show a head fabulac over its parts. It is written when that program is.*

---

## 4. Cookbook

Each recipe is a goal, then the same thing at each door: what to say to your readvisor (and the call it makes), the command line, and the client. `tally` is the program's name throughout; put yours.

### 4.1 Begin from a starter

- Readvisor: "begin a library called keyval from the starter". `<tool name="fabulac"><path>keyval</path><do>begin</do><starter>library</starter></tool>`
- Command line: `python -m enough.fabulac begin keyval --starter library --licence MIT --by Ada`
- Client: `e.begin("keyval", starter="library", licence="MIT", by="Ada")`

A starter begins at once; it is not a job. A name already taken is refused: "tally.fabulac.cosm is there already; take it up again, or choose another name".

### 4.2 Begin from a brief

- Readvisor: "begin a tool called linecount from brief.md". `<tool name="fabulac"><path>linecount</path><do>begin</do><kind>tool</kind><brief>brief.md</brief></tool>`
- Command line: `python -m enough.fabulac begin linecount --kind tool --brief brief.md --licence MIT`
- Client: `e.begin("linecount", kind="tool", brief="brief.md", licence="MIT")`

The brief's path is relative to the project. Agent free, or with no model, the brief is read by rules alone, and the answer says so.

### 4.3 Answer the interview

- Readvisor: "what does tally still ask?", then answer in your own words. The readvisor puts the questions with the `dialectic` tool, one or two at a time.
- Command line: `python -m enough.fabulac answer tally D:question/aim "It counts words."`, then `python -m enough.fabulac begin tally` to settle and raise the next stage.
- Client: `e.answer("tally", [{"question": "D:question/aim", "says": "It counts words."}])`, then `e.begin("tally")`.

An answer about a case's `given` or `expect` may be data: a JSON object in the shape of section 6.8 is checked and written as data; bad data is refused with what it lacks.

### 4.4 Add a requirement

- Readvisor: "add a requirement to tally: it never writes a file". `<tool name="fabulac"><path>tally</path><do>add</do><as>requirement</as><says>It never writes a file.</says></tool>`
- Command line: `python -m enough.fabulac add tally requirement "It never writes a file." --field 'force="must"'`
- Client: `e.add("tally", "requirement", "It never writes a file.", fields={"force": "must"})`

What `add` needs and is not given is left as a question for the interview. The readvisor's `add` writes the sentence only; the rest is asked.

### 4.5 Add a command case

- Readvisor: "add a case to tally: two files on one line count separately" (its given and expect are then asked).
- Command line:

  ```
  python -m enough.fabulac add tally case "Tabs count as spaces." \
    --field 'of=["C:interface/command-count"]' \
    --field 'given={"files": {"t.md": "a\tb\n"}, "steps": [{"arguments": ["count", "t.md"]}]}' \
    --field 'expect={"steps": [{"exit": 0, "output": "2\n", "error-output": ""}]}'
  ```

- Client:

  ```python
  e.add("tally", "case", "Tabs count as spaces.", fields={
      "of": ["C:interface/command-count"],
      "given": {"files": {"t.md": "a\tb\n"}, "steps": [{"arguments": ["count", "t.md"]}]},
      "expect": {"steps": [{"exit": 0, "output": "2\n", "error-output": ""}]},
  })
  ```

### 4.6 Add a function case, and one that raises

- Command line:

  ```
  python -m enough.fabulac add tally case "No text counts 0." \
    --field 'given={"calls": "C:interface/count-words", "arguments": {"text": ""}}' \
    --field 'expect={"value": 0}'
  python -m enough.fabulac add keyval case "A line with no = is an error." \
    --field 'given={"calls": "C:interface/split-pair", "arguments": {"line": "nothing"}}' \
    --field 'expect={"raises": {"error": "ValueError", "message": "no '"'"'='"'"' in the line"}}'
  ```

- Client: `e.add("tally", "case", "No text counts 0.", fields={"given": {"calls": "C:interface/count-words", "arguments": {"text": ""}}, "expect": {"value": 0}})`

A function is called by keyword. An error matches by its class name or a base class's, and its message exactly.

### 4.7 Add an interface

- Readvisor: "add a way in to tally: tally lines PATH counts lines". `<tool name="fabulac"><path>tally</path><do>add</do><as>interface</as><says>tally lines PATH prints the number of lines.</says></tool>`
- Command line: `python -m enough.fabulac add tally interface "tally lines PATH prints the number of lines." --field 'surface="command"' --field 'signature="tally lines PATH"'`
- Client: `e.add("tally", "interface", "tally lines PATH prints the number of lines.", fields={"surface": "command", "signature": "tally lines PATH"})`

A function interface needs its Python signature: `--field 'signature="count_lines(text: str) -> int"'`.

### 4.8 Find the requirements no case shows

- Readvisor: "which of tally's requirements has no case?". `<tool name="fabulac"><path>tally</path><do>check</do></tool>`
- Command line: `python -m enough.fabulac check tally` (the last line), or `--json check tally` and read `uncovered`.
- Client: `e.check("tally")["uncovered"]`
- In a Thym program: `uncovered f`.

### 4.9 Check before entailing

- Readvisor: "check tally". `<tool name="fabulac"><path>tally</path><do>check</do></tool>`
- Command line: `python -m enough.fabulac check tally` (exit 1 on an error)
- Client: `assert e.check("tally")["ok"]`

### 4.10 Entail

- Readvisor: "entail tally". `<tool name="fabulac"><path>tally</path><do>entail</do></tool>`. It runs after the turn; `<do>status</do>` says what it wrote.
- Command line: `python -m enough.fabulac entail tally --model local` (or `--model cloud`, or `--model cloud:<model id>`; `--calls N` caps the model calls; `--llm-url` names the local model's address)
- Client: `e.entail("tally")` waits for the job; `e.entail("tally", wait=False)` gives the job at once.

### 4.11 See what moved

- Readvisor: "what moved in tally?". `<tool name="fabulac"><path>tally</path><do>moved</do></tool>`
- Command line: `python -m enough.fabulac moved tally`
- Client: `m = e.moved("tally"); m["tell"], m["edited"]`

The states are *in step*, *moved*, *edited by hand*, *gone*, *kept* and *new*. `tell` lists what the next entailment will tell: the moved, gone and new files.

### 4.12 Run the tests

- Readvisor: "run tally's tests". `<tool name="fabulac"><path>tally</path><do>test</do></tool>`
- Command line: `python -m enough.fabulac test tally`
- Client: `r = e.test("tally"); r["ok"], r["stdout"], r["stderr"]`

### 4.13 Run the tool with a file handed over

- Readvisor: "run tally count notes.md". `<tool name="fabulac"><path>tally</path><do>run</do><args>count notes.md</args><hand>notes.md</hand></tool>`
- Command line: `python -m enough.fabulac run tally --hand notes.md -- count notes.md`
- Client: `e.run("tally", ["count", "notes.md"], hand_over=["notes.md"])["stdout"]`

### 4.14 Give the tool its input

For a tool that reads its standard input. tally from the starter reads only files: to make it read its input, add a case whose step gives `input` (`tally count -`, say), and entail again.

- Readvisor: `<tool name="fabulac"><path>tally</path><do>run</do><args>count -</args><input>one two</input></tool>`
- Command line: `python -m enough.fabulac run tally --stdin-file words.txt -- count -`
- Client: `e.run("tally", ["count", "-"], stdin="one two")`

### 4.15 Stop a run

- Readvisor: "stop tally". `<tool name="fabulac"><path>tally</path><do>stop</do></tool>`
- Command line: Ctrl-C.
- Client: `e.stop("tally")`, or `e.stop(run="<run id>")`.

Stop stops everything of that program that is running: a test, a run, an entailment. With nothing running it is refused (409).

### 4.16 Keep a hand edit, and let it go

- Readvisor: "keep my change to tally/__main__.py". `<tool name="fabulac"><path>tally</path><do>keep</do><file>tally/__main__.py</file><because>my wording</because></tool>`; "let it go": `<do>let-go</do>`.
- Command line: `python -m enough.fabulac keep tally tally/__main__.py --because "my wording"`; `python -m enough.fabulac let-go tally tally/__main__.py`
- Client: `e.keep("tally", ["tally/__main__.py"], because="my wording")`; `e.let_go("tally", ["tally/__main__.py"])`

`ENTAILED.md` cannot be kept. A kept file is no source's brief, so keeping one file moves no other.

### 4.17 Write over a hand edit

- Readvisor: "entail tally and write over my change to tally/__main__.py". `<tool name="fabulac"><path>tally</path><do>entail</do><overwrite>tally/__main__.py</overwrite></tool>`
- Command line: `python -m enough.fabulac entail tally --model local --overwrite tally/__main__.py`
- Client: `e.entail("tally", overwrite=["tally/__main__.py"])`

Every edited file must be named; one left out is named in the refusal.

### 4.18 Take a hand edit back

- Readvisor: "take my change to tally/__main__.py back into the fabulac". `<tool name="fabulac"><path>tally</path><do>take-back</do><file>tally/__main__.py</file></tool>`
- Command line: `python -m enough.fabulac take-back tally tally/__main__.py --model local`
- Client: `e.take_back("tally", "tally/__main__.py")`

It needs a model, and it reads Python only. Its questions are choices, *take it back* or *leave it out*; answer them as in section 4.3.

### 4.19 Make a program of parts

- Readvisor: "make a head called kit over tally and keyval". `<tool name="fabulac"><path>kit</path><do>head</do><parts>tally, keyval</parts></tool>`
- Command line: `python -m enough.fabulac head kit tally keyval --licence MIT`
- Client: `e.head("kit", ["tally", "keyval"], licence="MIT")`

The head names each part (`parts`) with one `C:component` per part, and each part names its head. State an interface between parts once, in the head; a part that keeps it says `stated-in` with the head's item. The checks `parts-resolve` and `interfaces-agree` hold them together.

### 4.20 See which parts moved

- Readvisor: "which parts of kit moved?". `<tool name="fabulac"><path>kit</path><do>parts-moved</do></tool>`
- Command line: `python -m enough.fabulac parts-moved kit`
- Client: `e.parts_moved("kit")["moved"]`

`parts-moved` reads a head beside its parts' folders. When the parts were made over copies of the files (as enough's
own are), compare them with the tree they came from instead: `python -m enough.fabulac moved-parts <part fabulacs or
a folder of them> --tree <checkout> [--ref <tag>]` lists each part as moved or not, file by file, with how many of its
rulings and questions still resolve.

### 4.21 The whole loop in one script

```python
"""Begin, check, entail, test and run tally against a running enough."""
import enough_client

e = enough_client.Enough()
e.check_promise()                                   # refuses an enough that keeps another promise
if not any(s["name"] == "tally" for s in e.starters()):
    raise SystemExit("no tally starter here")
e.begin("tally", starter="tool", licence="MIT", by="Ada")
e.add("tally", "case", "An empty file counts 0.", fields={
    "of": ["C:interface/command-count"],
    "given": {"files": {"empty.md": ""}, "steps": [{"arguments": ["count", "empty.md"]}]},
    "expect": {"steps": [{"exit": 0, "output": "0\n", "error-output": ""}]},
})
report = e.check("tally")
if not report["ok"]:
    raise SystemExit("\n".join(report["errors"]))
e.entail("tally")                                   # waits for the job
tests = e.test("tally")
print(tests["stdout"] if tests["ok"] else tests["stderr"])
print(e.run("tally", ["count", "notes.md"], hand_over=["notes.md"])["stdout"])
```

A refusal raises `enough_client.EnoughError`, with `status` and `detail`, enough's sentence:

```python
try:
    e.run("keyval", ["anything"])
except enough_client.EnoughError as err:
    print(err.status, err.detail)   # 409 keyval is a library, not a tool: there is nothing to start; run its tests instead
```

### 4.22 The whole loop in a shell

The command line's exit status is 0 done, 1 done and failed, 2 refused with nothing written:

```sh
set -e
python -m enough.fabulac begin tally --starter tool --licence MIT
python -m enough.fabulac check tally
python -m enough.fabulac entail tally --model local
if python -m enough.fabulac test tally; then
  python -m enough.fabulac run tally --hand notes.md -- count notes.md
else
  echo "a case failed"
fi
```

With `--json`, every command prints its whole answer as JSON, for `python -c` or any tool that reads JSON.

### 4.23 Drive enough with curl

A route that writes or starts a run needs the header `X-Enough-Api: 1`:

```sh
curl 127.0.0.1:3456/api/fabulac/promise
curl '127.0.0.1:3456/api/fabulac/status?path=tally'
curl -H 'X-Enough-Api: 1' -H 'Content-Type: application/json' \
  -d '{"path": "tally"}' 127.0.0.1:3456/api/fabulac/test
curl 127.0.0.1:3456/api/canon/job/cn7          # poll until state is done, failed or cancelled
```

Without the header it answers 403: "this route is part of enough's API promise and starts a run or writes: send the header X-Enough-Api: 1 (the page and enough_client do)".

### 4.24 Begin a library, or a service

- A library: `begin keyval --starter library`. Its tests run in the sandbox; `run` is refused, since there is nothing to start.
- A service: `begin greet --starter service`. It is authored and entailed, with `program.serve` (`port`, `reach`). `test` and `run` are refused in 0.8 with the sentence of section 1.3.

### 4.25 Use the moves in a Thym program

The moves that work on an authored fabulac are Thym moves too (section 6.6), so a program can call them. This one comes with enough, in `defaults/thym/author-python.thym`:

```
program state-a-requirement
  why: a requirement the person states goes into the fabulac they authored, in their own words.

  takes f: fabula, said: string
  gives g: fabula

  give add said as requirement with f
end
```

Copy the file into your project to change it, and run it with **run with…** or `thym_run`, as any program (the help center, its sections 13.4 and 13.6).

---

## 5. Tips

### 5.1 Writing cases

- Write the cases before you think about the code. A case you cannot write as data is a sign the interface is not settled yet.
- One case, one thing. Three small cases say more than one large one, and a failure names the one that broke.
- Give every requirement of force *must* a case, and name it in `checked-by`. `check` lists the ones that have none.
- Write the error cases too: a missing file, an empty input, a line with no `=`. They are where programs differ.
- Match output exactly, newline included: `"3\n"`, not `"3"`.
- A case's own folder is `<CASE>` in an argument or a variable; output that holds the folder's path is compared with `<CASE>` in its place.
- A case told in words is fine while you think. Turn it into data before you rely on it: a model writes the test of a case in words, and the test is marked so.

### 5.2 Keeping the fabulac the source

- Change the fabulac, then entail. Change the code only when you mean to keep the change or take it back.
- Run `moved` before `entail`. It says what will be told again, and what you changed by hand.
- `told` is what changed bytes. A moved file the model writes the same again is told and unchanged.
- Entailing the same fabulac twice gives the same files: everything written by rules is byte-stable, and files in step are never asked again.
- The fabulac is text. Change a field by hand when no word does it (a requirement's `checked-by`, say), then `check`.
- Keep a hand edit with a reason. The reason is in the fabulac, for whoever reads it next.

### 5.3 The sandbox

- Hand over only what the tool needs. It reads a copy and cannot write it.
- The limits: 120 seconds of wall time, 60 of processor time, 1,000,000 bytes of output, 200,000,000 of disk, 50,000,000 for one file, 256 open files. Past one, the run stops and the result says which (`stopped_by`).
- Every run keeps its own folder under `~/enough/thym/sandbox/<run id>/`, with `out/result.json`. They are not swept away yet; delete old ones by hand.
- `--json run` shows `enforced`, `mechanism` and `guarantees`: what the box held, in its own words.
- A Homebrew Python whose extension modules link libraries outside its own folder (OpenSSL, say) cannot import those modules in the box. uv's and conda's Pythons are self-contained.

### 5.4 Models

- Begin, add, check, test, run and keeping in step need no model. Entail and take back do.
- With the cloud, `--calls` caps how many model calls an entailment may make.
- A file the model wrote that fails its checks (it does not parse, an interface is missing) is asked again alone; nothing is kept until every file holds.

### 5.5 Scripting

- Call `e.check_promise()` first. A future enough that keeps another promise is refused at once, not halfway.
- `wait=False` gives you the job; `e.wait(answer)` waits for it later; `e.job(id)` reads it.
- The command line runs in its own process and needs no server; the client needs enough running. Use the command line in CI.
- Paths are relative to the project, and may name the program (`tally`) or its file (`tally.fabulac.cosm`).

### 5.6 When something is refused

| what it says | what to do |
|---|---|
| only a model writes sources | entail with `--model local` or `cloud`; turn agent free off |
| … holds files the fabulac did not write as they are | keep, write over, or take back the files it names (section 2.12) |
| … is read, never run | it is a decompiled fabulac: its code is read only; author your own |
| … is a library, not a tool | run its tests instead |
| … is a service … serving comes in a later minor | its source is entailed; serving comes later |
| … is there already | take it up again with `begin`, or choose another name |
| it needs … outside the standard library | 0.8 runs the standard library only; the package is pinned in `pyproject.toml` |
| this route is part of enough's API promise … | send `X-Enough-Api: 1` |
| this enough keeps API promise 1; the request speaks 2 | use the client that came with this enough |

---

## 6. Reference

Every way in to an authored fabulac, with an example each: the starters, the `fabulac` tool's words, the routes, the command line, the client library, the moves and the checks. enough 0.8, API promise 1. `tests/test_api_promise.py` holds this reference to the code: a route, a word or a command missing here fails it.

There are three doors, and they do the same things by the same functions (`enough/fabulac_first.py`): the page and the readvisor's **`fabulac` tool**, with a `<do>` word; the **command line**, `python -m enough.fabulac`, with no enough running; the **client library**, `enough_client` (one file, `enough/enough_client.py`, standard library only), over the **routes** of a running enough.

### 6.1 The starters

Three authored fabulacs to begin from, each passing its checks (`defaults/fabulac-starters/`):

| kind | name | what it is |
|---|---|---|
| tool | `tally` | a command, `tally count PATH`, and a function, `count_words(text)`; three cases |
| library | `keyval` | `split_pair(line)` and `join_pair(key, value)`; three cases, one of them an error |
| service | `greet` | `greeting(name)`; one case. Entailed, and refused at run |

Begun under another name, a starter's name is changed everywhere it is a whole word (the command, the error it prints, the module it starts as), and the day, who authored it and the licence are yours.

### 6.2 The `fabulac` tool's words

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

For a folder of Python decompiled into its fabulac (not authored), the words are the 0.6 ones: `<do>build</do>`, `<do>status</do>`, `<do>compile</do>` (with `<what>`), `<do>cancel</do>`. Its code is read, never run.

A Lean proof has a tool of its own, `fabulam` (0.9), with a `<path>` (a `.lean` file, a folder of them, or a `.fabulam.cosm`) and a `<do>`: `<do>build</do>` (`<target>` names the final theorem to tell, when a file ends in more than three), `<do>resume</do>`, `<do>status</do>` (the default), `<do>cancel</do>`, and `<do>entail</do>`, which takes `<density>` `expert`, `student` or `everyone`. It starts the jobs of the routes below, and nothing of Lean is ever run. Example: `<tool name="fabulam"><path>PrimesCongruentOne.lean</path><do>build</do></tool>`.

### 6.3 The routes (API promise 1)

Every route that starts a run or writes (each POST here) needs the header `X-Enough-Api: 1`, or it answers 403 with a sentence. The page and the client send it. A job route answers `{"job": {...}}`; poll `GET /api/canon/job/{job_id}` until `state` is `done` (its `result`), `failed` or `cancelled`. A refusal is a 4xx with `{"detail": "<the sentence>"}`: 400 a bad body, 404 no such fabulac, 409 refused (not authored, not entailed, a service, a library run as a tool, a hand edit, no model), 403 the gate.

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

With curl, a gated route: `curl -H 'X-Enough-Api: 1' -H 'Content-Type: application/json' -d '{"path": "tally"}' 127.0.0.1:3456/api/fabulac/test`.

The jobs these routes start are of kind `fabulac-author`, `fabulac-entail` and `sandbox`; a sandbox job's snapshot also carries `run` (the run id) and `what` (`tests` or `tool`).

**Two gates, before any route (0.9).** The first is the Origin gate (`enough/origin_gate.py`). Every POST, PUT, PATCH and DELETE, and `GET /api/reset`, `GET /api/update-enough` and `GET /api/reveal`, passes only with no `Origin` header (curl, a script, the client) or with one of enough's own: `http://127.0.0.1`, `http://localhost` or `http://[::1]` on enough's own port, or the desktop shell's (`tauri://localhost`, `http://tauri.localhost`, `https://tauri.localhost`). Anything else, `null` among it, answers 403 with a sentence, and so does a request with no `Origin` that the browser marks `Sec-Fetch-Site: cross-site` or `same-site`. Reads, `GET /api/stream` and `/static` are never held. The second is the header `X-Enough-Api: 1`: every promised POST above, and since 0.9 the older routes that start a model run too, which are not promised (their shape may change without a new `VERSION`): `/api/chat`, `/api/cloud/health-check`, `/api/transcribe`, `/api/canon/read`, `/api/canon/atem`, `/api/thym/run`, `/api/fabula/derive`, `/api/fabula/build`, `/api/fabula/resume`, `/api/fabula/compile`, `/api/fabula/verse/build`, `/api/fabula/verse/resume`, `/api/dialectic/settle`, `/api/composure/scaffold/check`, every POST under `/api/council/` but `/api/council/pause`, and every POST under `/api/fabulam/`. Without it they answer 403 with a sentence. The page sends the header on every call it makes. `POST /api/model` takes no header (it loads a model and runs none); the Origin gate holds it.

**The fabulam's routes (0.9, not promised).** They take the header on every POST and pass the Origin gate. A body's `path` is a `.lean` file, a folder holding `.lean` files, or a `.fabulam.cosm`, from the project's top folder. A refusal is a 4xx with `{"detail": "<the sentence>"}` before any job starts: 400 no path, not Lean, or the Canon store; 404 not there, or gone; 409 a part (it is built with its head), nothing to take up again, already built (pass `restart`), an outline or no model for `entail`, nothing running for `cancel`; 413 past sixty files or twelve thousand lines under one head.

| route | takes | gives | example |
|---|---|---|---|
| `GET /api/fabulam/state` | `path` | `state job`; `state` is the card's: `source fabulam name exists state line stages landed of next complete moved targets wording said said_by said_at checking pshorts` | `/api/fabulam/state?path=PrimesCongruentOne.lean` |
| `POST /api/fabulam/build` | `path target? restart? wording? said? said_by? said_at? name? route? model? calls? job_calls? mode?` | a job and `state`, or the pick answer | `{"path": "PrimesCongruentOne.lean"}` |
| `POST /api/fabulam/resume` | `path route? model? calls? job_calls?` | a job and `state`, from the stage after the last that landed | `{"path": "PrimesCongruentOne.lean"}` |
| `POST /api/fabulam/entail` | `path density? route? model? calls?` | a job and `state`; its result names the pshorts written (all three when `density` is left out) | `{"path": "primes-congruent-one.fabulam.cosm", "density": "student"}` |
| `POST /api/fabulam/cancel` | `path` | `job` | `{"path": "PrimesCongruentOne.lean"}` |

**The pick answer.** A file that ends in more than three final theorems, built with no `target`, is not refused and builds nothing: the answer is 200, `{"job": null, "targets": ["…", "…"], "state": {"state": "pick", "line": "this file ends in 5 results: choose the one to tell", …}, "refusal": {"check": "pick", …}, "message": "nothing was built; …"}`. Build again with `"target"` naming one of `targets`, or a list of them for a folder. A folder answers the same when its head names no target and the rule finds more than three across its files. The job's kind is `fabulam`; `checking` is the sentence of `P:claim/checking`, in full, and nothing more is said about checking anywhere.

### 6.4 The command line

`python -m enough.fabulac [--project DIR] [--json] <command> …`, in the project (or with `--project`), no server running. Exit 0 done; 1 done and failed (a test, a check, the tool's own status); 2 refused, nothing written.

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
| `python -m enough.fabulac moved-parts FABULACS… --tree DIR [--ref TAG] [--base REF]` | `moved-parts docs/parts --tree . --ref v0.9.0` |

The options that ask a model, on `begin`, `entail` and `take-back`: `--model local`, `cloud` or `cloud:<model id>`; `--llm-url` the local model's address (else `ENOUGH_LLM_URL`, else enough's own); `--calls N` a ceiling on model calls. `run` also takes `--stdin-file FILE`, a project file whose text is the tool's input.

### 6.5 The client library

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

A refusal raises `enough_client.EnoughError` (`status`, `detail`: enough's sentence). `Enough(url, timeout=60.0, transport=…)`: `transport` is a function `(method, url, headers, body) -> (status, bytes)`, for a test that sends the requests somewhere other than the network.

### 6.6 The moves (Thym)

| move | what it does | example |
|---|---|---|
| `author` | begins an authored fabulac's catalog, from a brief or from nothing (`as tool`, `library`, `service`) | `give author brief as tool` |
| `add` | the person's sentence as a new item | `add said as requirement with f` |
| `compare` | what differs between two fabulacs, item by item | `compare f with g` |
| `uncovered` | the requirements of force *must* no case shows | `uncovered f` |
| `entail … as code` | an authored fabulac's entailment (`entail-authored-python.thym`) | `entail f as code` |

The programs that come with enough for this are `defaults/thym/author-python.thym` (begin-from-a-brief, begin-by-interview, state-a-requirement, ready-to-entail) and `defaults/thym/entail-authored-python.thym`. Read them in the docs viewer, or copy one into your project to change it (the help center, its section 13.6).

### 6.7 The checks

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

`check` also runs every check a fabula is held to (MacroCOSM OES, its section 18), such as `licence-recorded` and `interface-signature`.

### 6.8 The case shapes

A command:

```yaml
given:
  files: {notes.md: "one two three\n"}       # the files the case starts with
  env: {NAME: value}                         # variables set (null: not set)
  cwd: sub                                   # a folder of the case's own to start in
  steps:
    - arguments: [count, notes.md]
      input: ""                              # the step's standard input
expect:
  steps:
    - {exit: 0, output: "3\n", error-output: ""}
  files: {out.txt: "…"}                      # the files after (null: not there)
```

A function:

```yaml
given: {calls: C:interface/count-words, arguments: {text: "a b  c\n"}}
expect: {value: 3}
# or
expect: {raises: {error: ValueError, message: "no '=' in the line"}}
```

A string `given` or `expect` is a case in words. A `{pending: …}` field, or data no surface knows, is not entailed, with why.

A command case needs a program of kind `tool` or `service` with a `start`. A function case needs `calls` to name a `C:interface` of surface `function` with a Python name. Steps run in a fresh folder per case, 60 seconds a step, with `HOME` set to that folder.

### 6.9 The entailed folder

| file | written by | what it holds |
|---|---|---|
| `ENTAILED.md` | rules | the footer, every file with what it was told from, its sha256 and its brief digest, the cases not entailed and why, the licence of the source |
| `RUNNING.md` | rules | its tests, starting it, what it needs, what enough runs here |
| `pyproject.toml` | rules | name, version (`0.0.0` until an `R:release` names one), `requires-python`, dependencies pinned `name==version`, `[project.scripts]`, `[tool.enough] kind, start, serve` |
| `<name>/__init__.py` | a model | the functions without a `defined-in` |
| `<name>/<sub>.py` | a model | a function with a dotted name (`pairs.joining.join_pair` goes in `pairs/joining.py`) |
| `<name>/__main__.py` | a model | a tool's or a service's command: `main(argv=None) -> int` |
| `tests/__init__.py` | rules | the package mark `unittest discover` needs |
| `tests/test_cases.py` | rules | one `unittest` test per case in data |
| `tests/test_prose_cases.py` | a model | one test per case in words, each marked as a model's |

If the fabulac names its own Python `C:file`s, those are the sources instead. The fabulac records the entailment in its catalog: `entailed: {path, at, run, files: [{path, sha256, from, brief}], kept}`.

### 6.10 The sandbox: what it holds, and what not

| | macOS (`sandbox-exec`) | Linux (bubblewrap) | other |
|---|---|---|---|
| network | denied | a namespace of its own, loopback only | refused |
| writes | the run's work, home and temporary folders only | the run's folder | |
| reads | the run's folder, the system's libraries, the interpreter's own files; that a file exists stays readable elsewhere | the same | |
| processes | only the interpreter can be started | anything under `/usr`, inside the box | |
| memory | not limited; nothing promised | limited | |
| time, processor time, output, file size | limited | limited | |
| disk | measured as it runs, and stopped past the limit | the same | |

The interpreter is enough's own, started with `-I -S`, with an environment of its own (`PATH=/usr/bin:/bin`, `HOME` and `TMPDIR` the run's), nothing of yours. Packages come only from the standard library (`PACKAGE_SOURCE = "standard-library"`). Not promised anywhere: a limit on processes per run; on macOS, that a file's existence is hidden. Linux's path has been tested with bubblewrap stood in, not on a Linux machine.

### 6.11 Where things live

| what | where |
|---|---|
| the fabulac | `<name>.fabulac.cosm`, in the project |
| its entailment | `<name>/`, beside it |
| answers not yet settled | `<name>.fabulac.answers-….cosm`, beside it |
| catems | `<name>.catem-….md`, beside it |
| runs in the sandbox | `~/enough/thym/sandbox/<run id>/` (`ENOUGH_THYM_ROOT` moves it), with `out/result.json` |
| Thym's traces of each entailment | `~/enough/thym/runs/` |
| the starters | `defaults/fabulac-starters/<kind>/<name>.fabulac.cosm` |
| the client | `enough/enough_client.py` |

### 6.12 The headings a brief may use

| answers | headings |
|---|---|
| what it is for | what it is for, what it does, aim, aims, purpose; and the paragraphs under the title |
| for whom | for whom, who it is for, audience, who |
| a use | uses, use, what a person does with it |
| what prompted it | why, occasion, what prompted it |
| ways in | ways in, way in, commands, interface, interfaces |
| what it needs | needs, what it needs, dependencies, requires |
| settings | settings, setting, options, configuration |
| what it leaves out | leaves out, left out, what it leaves out, not doing, out of scope, exclusions, non-goals |
| what it must do | requirements, must, always, never, must never |
| cases | cases, case, examples, example |
| open questions | open questions, undecided, questions |

Headings are matched without regard to case, and a heading that holds one of these words whole counts too. A passage under any other heading is left unplaced; with a model, the model may place it, and the item still holds your words.
