"""Saving articles out of the archive as attributed markdown.

Two destinations:

- `project` — `{project}/wiki/<slug>.md`. The folder is created on the
  first save and shows up in the file tree like any user content.
- `infoworld` — `~/enough/infoworld/wiki/<slug>/article.md` plus a
  sibling `_manifest.md` (source URL + license + retrieval date +
  origin), so each article folder in the shared commons is
  self-describing.

Every save also lands the article in the watch registry, which is what
the wikisink update engine refreshes.

Wikipedia text is CC BY-SA 4.0 — the frontmatter/manifest carry the
attribution so downstream reuse stays honest.
"""

from __future__ import annotations

import datetime as dt
import logging
import urllib.parse
from pathlib import Path
from typing import Any

from . import config as wconfig
from . import overlay as woverlay

log = logging.getLogger("enough.wikisink")

INFOWORLD_WIKI = Path.home() / "enough" / "infoworld" / "wiki"


def _slug(title: str) -> str:
    from ..tools import _slugify  # late import: keeps module import-light

    return _slugify(title, max_len=60)


def source_url(title: str) -> str:
    return "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
        title.replace(" ", "_"), safe="()_,-"
    )


def _origin_line(art: dict[str, Any], cfg: dict[str, Any]) -> str:
    zim = wconfig.active_zim_meta(cfg)
    if art["source"] == "overlay":
        revid = (art.get("meta") or {}).get("revid")
        return f"wikisink overlay (live Wikipedia{f', revision {revid}' if revid else ''})"
    if art["source"] == "preserved":
        return "wikisink preserved copy (deletion override)"
    return f"wikisink ({zim.get('flavor')}, snapshot {zim.get('snapshot')})"


def _to_markdown(html: str) -> tuple[str, bool]:
    from ..tools import _markdownify_via_pandoc

    return _markdownify_via_pandoc(html)


def render_saved_article(art: dict[str, Any], cfg: dict[str, Any]) -> tuple[str, str]:
    """(file body, extension) — markdown with YAML attribution
    frontmatter, or raw HTML with an explanatory comment when pandoc
    isn't available (same fallback contract as fetch_url)."""
    today = dt.date.today().isoformat()
    md, converted = _to_markdown(art["html"])
    fm = (
        "---\n"
        f'title: "{art["title"]}"\n'
        f"source: {source_url(art['title'])}\n"
        "license: CC BY-SA 4.0\n"
        f"retrieved: {today}\n"
        f"origin: {_origin_line(art, cfg)}\n"
        "---\n\n"
    )
    if converted:
        return fm + md.strip() + "\n", "md"
    return (
        "<!--\n" + fm.strip() + "\n(raw HTML: pandoc not installed, "
        "markdown conversion skipped)\n-->\n" + art["html"], "html"
    )


def _manifest_body(art: dict[str, Any], cfg: dict[str, Any]) -> str:
    today = dt.date.today().isoformat()
    return (
        f"# manifest — {art['title']}\n\n"
        f"- **source:** {source_url(art['title'])}\n"
        "- **license:** CC BY-SA 4.0 (with legacy CC BY-SA 3.0 + GFDL content)\n"
        f"- **retrieved:** {today}\n"
        f"- **origin:** {_origin_line(art, cfg)}\n"
    )


def save_article(project_dir: Path, path: str, dest: str) -> dict[str, Any]:
    """Save an article. `dest` is "project" or "infoworld". Returns
    {saved_path, dest, title}; raises KeyError / WikisinkUnavailable /
    ValueError on bad dest."""
    if dest not in ("project", "infoworld"):
        raise ValueError(f"unknown save destination {dest!r}")
    cfg = wconfig.load_config()
    art = woverlay.resolve_article(path=path)
    body, ext = render_saved_article(art, cfg)
    slug = _slug(art["title"])

    if dest == "project":
        wiki_dir = project_dir / "wiki"
        wiki_dir.mkdir(parents=True, exist_ok=True)
        target = wiki_dir / f"{slug}.{ext}"
        target.write_text(body, encoding="utf-8")
        saved_display = str(target.relative_to(project_dir))
        watched_tag = f"project:{project_dir.resolve()}"
    else:
        art_dir = INFOWORLD_WIKI / slug
        art_dir.mkdir(parents=True, exist_ok=True)
        target = art_dir / f"article.{ext}"
        target.write_text(body, encoding="utf-8")
        (art_dir / "_manifest.md").write_text(_manifest_body(art, cfg), encoding="utf-8")
        saved_display = str(target)
        watched_tag = "infoworld"

    wconfig.upsert_watched(art["path"], art["title"], saved_to=watched_tag)
    log.info("wikisink saved %s -> %s", art["title"], target)
    return {"saved_path": saved_display, "dest": dest, "title": art["title"]}
