# Finding open-source code by license → repos & libraries with verified rights

Two related missions:
- **(f)** GitHub repos that perform a requested function **and** carry a permissive
  license (the user asked specifically for **MIT or Apache-2.0**).
- **(g)** Open-source libraries doing the same thing but hosted **off** GitHub.

The deliverable is URLs **plus a verified license** — because the label a project claims
and what its LICENSE file actually says don't always match, and a wrong call here can bite
the user legally. Verify, don't trust the badge.

## (f) GitHub

Search moves:
- **GitHub search with license qualifiers**: `<functionality> language:python license:mit`,
  or `license:apache-2.0`. The `license:` qualifier filters to GitHub's detected license.
- Search **topics** (`topic:<thing>`), **awesome-lists** (`awesome <domain>` repos curate
  the good libraries), and the general web (`<function> github library`).
- **Rank candidates** on fitness *and* health: recent commits, release cadence, stars/
  forks as a weak popularity signal, open-vs-closed issue ratio, docs/tests presence,
  and maintenance status (archived? last commit years ago?). A permissively-licensed but
  abandoned lib is a real cost — flag it.

**Verify the license** with the bundled script rather than trusting the sidebar:
```
python3 rness/skills/anything-finder/scripts/verify_license.py --repo https://github.com/<owner>/<name>
```
It reads the actual license via the GitHub API + the raw LICENSE file, returns the SPDX id
(e.g., `MIT`, `Apache-2.0`), says whether it's permissive, and pulls basic health signals.
**Exclude / flag copyleft** (GPL, AGPL, LGPL, MPL) since the user asked for MIT/Apache-2 —
if the best-functioning option is copyleft, say so explicitly and let them decide.

Apache-2.0 note worth surfacing: it includes an explicit patent grant (a plus for some
users) and a NOTICE-file requirement; MIT is simpler/shorter. Mention when relevant.

## (g) Off-GitHub open-source libraries

Not all good code lives on GitHub. Look at:
- **Other forges**: GitLab (gitlab.com + self-hosted instances), **Codeberg** (codeberg.org)
  and other Forgejo/Gitea hosts, **SourceForge**, **Bitbucket**, Savannah (GNU), Launchpad.
- **Language package registries** (often the fastest way to find a library by function,
  and each exposes license metadata):
  - Python → **PyPI** (pypi.org), Rust → **crates.io**, JS → **npm** (npmjs.com),
    Ruby → RubyGems, Java/Kotlin → Maven Central, PHP → Packagist, .NET → NuGet,
    Perl → CPAN, Haskell → Hackage, Lua → LuaRocks, R → CRAN, Julia → General registry.
- **Academic / lab-hosted code**: project homepages, university lab pages, papers-with-code
  (paperswithcode.com), Zenodo (zenodo.org — DOI'd software releases), Software Heritage
  (softwareheritage.org — archives source from everywhere, findable by function/name).
- **Directories**: Libraries.io (indexes packages across registries + their licenses),
  Awesome-lists, LWN/Freecode-successors.

The same `verify_license.py` accepts a package instead of a repo:
```
python3 rness/skills/anything-finder/scripts/verify_license.py --pypi <name>
python3 rness/skills/anything-finder/scripts/verify_license.py --npm <name>
python3 rness/skills/anything-finder/scripts/verify_license.py --crate <name>
```
It reads the registry's license field/classifiers and reports SPDX + permissive/not.

## Deep-search moves

- Search by **function + ecosystem**: "sparse matrix rust crate", "wysiwyg editor apache
  license", "<algorithm> implementation MIT".
- Check the **package that a popular tool depends on** — dependencies are often the small,
  focused, well-licensed library you actually want.
- If GitHub has nothing suitable, explicitly pivot to registries + Codeberg/GitLab (that's
  the whole point of (g)) rather than concluding "nothing exists."

## Return format

Ranked best-first; permissive-and-healthy on top.

```
### <library/repo name> — <one-line: what it does>
- **URL:** <repo or package page>
- **Source:** <GitHub | Codeberg | GitLab | PyPI | crates.io | Zenodo…>
- **License:** <MIT | Apache-2.0 | …> — **verified** via verify_license.py (permissive ✓ / copyleft ⚠)
- **Health:** <last commit / release; stars; maintained? tests/docs?>
- **Fit:** <how well it matches the requested function; notable gaps>
- **Confidence:** <…>
```

Open with a one-line recommendation ("Go with #1 — MIT, actively maintained, does exactly
X; #2 is the Apache-2.0 fallback if you need the patent grant").
