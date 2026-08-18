#!/usr/bin/env python3
"""
verify_license.py — Verify the actual license (and basic health) of an open-source
project, so a "MIT / Apache-2.0 only" find is trustworthy rather than badge-deep.

Works on:
  - GitHub repos      --repo https://github.com/OWNER/NAME   (or OWNER/NAME)
  - GitLab repos      --gitlab https://gitlab.com/OWNER/NAME
  - PyPI packages     --pypi PACKAGE
  - npm packages      --npm PACKAGE
  - crates.io crates  --crate CRATE

Reads the real license metadata (GitHub's license API + raw LICENSE, or the registry's
license field/classifiers), reports the SPDX id, whether it's PERMISSIVE
(MIT/Apache-2.0/BSD/ISC/…) vs COPYLEFT/other, and light health signals where available.

Uses only the Python standard library and a normal browser User-Agent. If a host is
blocked by the environment's network policy, it says so — allowlist that host and retry.

Examples:
  python3 rness/skills/anything-finder/scripts/verify_license.py --repo psf/requests
  python3 rness/skills/anything-finder/scripts/verify_license.py --pypi numpy
  python3 rness/skills/anything-finder/scripts/verify_license.py --npm left-pad
  python3 rness/skills/anything-finder/scripts/verify_license.py --crate serde
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/122.0 Safari/537.36 anything-finder/1.0")

PERMISSIVE = {
    "MIT", "MIT-0", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "BSD",
    "ISC", "ZLIB", "UNLICENSE", "0BSD", "BSL-1.0", "MPL-1.1-PERMISSIVE",
    "CC0-1.0", "WTFPL", "PYTHON-2.0", "POSTGRESQL",
}
COPYLEFT = {
    "GPL-2.0", "GPL-3.0", "GPL-2.0-ONLY", "GPL-3.0-ONLY", "GPL-2.0-OR-LATER",
    "GPL-3.0-OR-LATER", "AGPL-3.0", "AGPL-3.0-ONLY", "AGPL-3.0-OR-LATER",
    "LGPL-2.1", "LGPL-3.0", "LGPL-2.1-ONLY", "LGPL-3.0-ONLY", "MPL-2.0",
    "EPL-1.0", "EPL-2.0", "CDDL-1.0", "OSL-3.0",
}


def classify(spdx):
    if not spdx:
        return "UNKNOWN"
    key = spdx.strip().upper()
    if key in PERMISSIVE:
        return "PERMISSIVE"
    if key in COPYLEFT:
        return "COPYLEFT/RECIPROCAL"
    # Heuristics for odd strings
    up = key
    if "APACHE" in up or up.startswith("MIT") or "BSD" in up or "ISC" in up:
        return "PERMISSIVE (likely)"
    if "GPL" in up or "MPL" in up or "EPL" in up:
        return "COPYLEFT/RECIPROCAL (likely)"
    return "OTHER — read the license text manually"


def get(url, accept=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    if accept:
        req.add_header("Accept", accept)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace") if e.fp else ""
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        raise SystemExit(
            f"[network] Could not reach {url}: {reason}\n"
            f"If this host is blocked by the environment, ask the user to allowlist it."
        )


def report(name, spdx, extra=None):
    cls = classify(spdx)
    print(f"  project : {name}")
    print(f"  license : {spdx or 'UNKNOWN'}")
    print(f"  type    : {cls}")
    if spdx and cls.startswith("PERMISSIVE"):
        print("  verdict : ✓ permissive — matches an MIT/Apache-2-style requirement")
    elif cls.startswith("COPYLEFT"):
        print("  verdict : ⚠ copyleft/reciprocal — does NOT match 'MIT/Apache-2 only'")
    else:
        print("  verdict : ? verify by reading the LICENSE file directly")
    for k, v in (extra or {}).items():
        if v is not None and v != "":
            print(f"  {k:<8}: {v}")


def norm_repo(s):
    s = s.strip().rstrip("/")
    for p in ("https://github.com/", "http://github.com/", "github.com/"):
        if s.startswith(p):
            s = s[len(p):]
    return s.removesuffix(".git")


def do_github(repo):
    slug = norm_repo(repo)
    status, body = get(f"https://api.github.com/repos/{slug}",
                       accept="application/vnd.github+json")
    if status == 404:
        raise SystemExit(f"GitHub repo not found: {slug}")
    if status == 403:
        print("  note    : GitHub API rate-limited (unauthenticated). "
              "Try again later or read the LICENSE file in the browser.")
    data = json.loads(body) if body else {}
    lic = (data.get("license") or {})
    spdx = lic.get("spdx_id") if lic.get("spdx_id") not in (None, "NOASSERTION") else None
    extra = {
        "url": data.get("html_url"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "archived": data.get("archived"),
        "pushed": data.get("pushed_at"),
        "issues": data.get("open_issues_count"),
        "lang": data.get("language"),
    }
    report(slug, spdx, extra)
    if not spdx:
        # fall back to raw LICENSE probe
        for br in ("HEAD", "main", "master"):
            for fn in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
                st, txt = get(f"https://raw.githubusercontent.com/{slug}/{br}/{fn}")
                if st == 200 and txt.strip():
                    print(f"  raw     : found {fn} on {br}; first line: "
                          f"{txt.strip().splitlines()[0][:80]!r}")
                    return
        print("  raw     : no LICENSE file found at repo root — treat license as UNKNOWN.")


def do_gitlab(url):
    slug = url.strip().rstrip("/")
    for p in ("https://gitlab.com/", "http://gitlab.com/", "gitlab.com/"):
        if slug.startswith(p):
            slug = slug[len(p):]
    import urllib.parse
    enc = urllib.parse.quote(slug, safe="")
    status, body = get(f"https://gitlab.com/api/v4/projects/{enc}?license=true")
    if status != 200:
        raise SystemExit(f"GitLab project not found or API error ({status}): {slug}")
    data = json.loads(body)
    lic = (data.get("license") or {})
    spdx = lic.get("key", "").upper() or lic.get("nickname")
    report(slug, spdx, {"url": data.get("web_url"),
                        "stars": data.get("star_count"),
                        "updated": data.get("last_activity_at")})


def do_pypi(name):
    status, body = get(f"https://pypi.org/pypi/{name}/json")
    if status != 200:
        raise SystemExit(f"PyPI package not found: {name}")
    info = json.loads(body).get("info", {})
    spdx = info.get("license_expression")
    if not spdx:
        # classifiers like "License :: OSI Approved :: MIT License"
        for c in info.get("classifiers", []):
            if c.startswith("License :: OSI Approved ::"):
                spdx = c.split("::")[-1].strip()
                break
    if not spdx:
        spdx = (info.get("license") or "").strip() or None
    report(name, spdx, {"url": info.get("project_url") or info.get("home_page"),
                        "version": info.get("version"),
                        "summary": (info.get("summary") or "")[:80]})


def do_npm(name):
    status, body = get(f"https://registry.npmjs.org/{name}")
    if status != 200:
        raise SystemExit(f"npm package not found: {name}")
    data = json.loads(body)
    latest = (data.get("dist-tags") or {}).get("latest")
    ver = (data.get("versions") or {}).get(latest, {})
    spdx = ver.get("license") or data.get("license")
    if isinstance(spdx, dict):
        spdx = spdx.get("type")
    report(name, spdx, {"url": data.get("homepage") or
                        f"https://www.npmjs.com/package/{name}",
                        "version": latest,
                        "modified": (data.get("time") or {}).get("modified")})


def do_crate(name):
    status, body = get(f"https://crates.io/api/v1/crates/{name}")
    if status != 200:
        raise SystemExit(f"crate not found: {name}")
    data = json.loads(body)
    versions = data.get("versions") or []
    spdx = versions[0].get("license") if versions else None
    crate = data.get("crate", {})
    report(name, spdx, {"url": f"https://crates.io/crates/{name}",
                        "downloads": crate.get("downloads"),
                        "updated": crate.get("updated_at")})


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--repo", help="GitHub repo (URL or OWNER/NAME)")
    g.add_argument("--gitlab", help="GitLab repo URL")
    g.add_argument("--pypi", help="PyPI package name")
    g.add_argument("--npm", help="npm package name")
    g.add_argument("--crate", help="crates.io crate name")
    a = ap.parse_args()
    print("license check —")
    if a.repo:
        do_github(a.repo)
    elif a.gitlab:
        do_gitlab(a.gitlab)
    elif a.pypi:
        do_pypi(a.pypi)
    elif a.npm:
        do_npm(a.npm)
    elif a.crate:
        do_crate(a.crate)


if __name__ == "__main__":
    main()
