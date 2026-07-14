"""Saving articles out of the archive, and reading/unsaving them.

A saved article is a *folder* (both destinations):

- `project`   — `{project}/wiki/<slug>/`
- `cacheawl`  — `~/enough/cacheawl/wiki/<slug>/` (the global wiki cachebox;
                the legacy destination name `infoworld` is accepted as an
                alias during the transition)

containing:

- `article.html`  — the article HTML **verbatim** as the archive/overlay
  had it, plus a leading attribution comment. Never edited, never
  converted: the wikisink reader renders it through the same sanitize
  pipeline as live browsing, so a saved article looks identical to the
  archive copy — infoboxes and all. (Markdown conversion loses complex
  tables, and an inviting .md file begs for hand-edits that drift out
  of sync with the archive; see git history for that earlier design.)
- `_manifest.md`  — human-readable attribution (source URL, CC BY-SA
  license, retrieval date, origin), so every folder in the commons is
  self-describing.
- `.meta.json`    — machine sidecar (ZIM path, title, origin, …) read
  by the saved-article endpoint and the unsave flow. Dot-prefixed, so
  the file tree hides it.

Every save also lands the article in the watch registry, which is what
the wikisink update engine refreshes. Unsaving removes the folder and
the registry tag.

Wikipedia text is CC BY-SA 4.0 — the manifest and the attribution
comment carry what downstream reuse needs.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import posixpath
import re
import shutil
import urllib.parse
from pathlib import Path
from typing import Any

from . import config as wconfig
from . import overlay as woverlay
from . import zim as wzim

log = logging.getLogger("enough.wikisink")

META_NAME = ".meta.json"
ARTICLE_NAME = "article.html"


def _cacheawl_wiki_dir() -> Path:
    """The global wiki cachebox: ``~/enough/cacheawl/wiki/`` (honoring the
    ENOUGH_CACHEAWL_ROOT test override). Resolved lazily so tests never
    touch the real store."""
    from .. import cacheawl as _cacheawl
    return _cacheawl.root() / "wiki"


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


# ---------------------------------------------------------------------------
# HTML → markdown for the *agent's* consumption (read_wiki_article cache).
# Saved files stay HTML; markdown is only for LLM-readable text.
# ---------------------------------------------------------------------------

def _rewrite_save_href(tag_head: str, quoted: str, base_dir: str) -> str:
    """Internal ZIM links → absolute en.wikipedia.org URLs, so exported
    markdown works anywhere (editors, publishing, other machines).
    External links pass through; javascript:/data: get neutered."""
    href = quoted[1:-1]
    unescaped = href.replace("&amp;", "&")
    low = unescaped.lower()
    if low.startswith("//"):
        # Protocol-relative resolves against the *viewer's* origin in a
        # saved file (github.com//en.wikipedia.org/… is a 404) — pin it.
        return f'{tag_head} href="https:{href}"'
    if low.startswith(("http://", "https://")):
        return f'{tag_head} href="{href}"'
    if low.startswith(("mailto:", "javascript:", "data:")):
        return f'{tag_head} href="#"'
    if unescaped.startswith("#"):
        return f'{tag_head} href="{href}"'
    if unescaped.startswith("/"):
        # Site-root-relative (live/overlay HTML): /wiki/X, /w/index.php?…
        return f'{tag_head} href="https://en.wikipedia.org{href}"'
    target, _, frag = unescaped.partition("#")
    resolved = posixpath.normpath(posixpath.join(base_dir, urllib.parse.unquote(target)))
    resolved = resolved.lstrip("./")
    if resolved.startswith("A/"):
        resolved = resolved[2:]
    url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
        resolved.replace(" ", "_"), safe="()_,-/:!$&'*+;=@~")
    if frag:
        url += "#" + frag
    return f'{tag_head} href="{url}"'


_CONTENT_ANCHOR = 'id="mw-content-text"'


def _extract_content_div(html: str) -> str | None:
    """The subtree of <div id="mw-content-text">, found by div-depth
    counting (regex alone can't match the closing tag of a nested div).
    Present in both Kiwix ZIM scrapes and live MediaWiki HTML; when it's
    there, everything outside it is navigation chrome we don't want in
    exported text. None when absent (minimal/overlay HTML)."""
    anchor = html.find(_CONTENT_ANCHOR)
    if anchor == -1:
        return None
    start = html.rfind("<div", 0, anchor)
    if start == -1:
        return None
    depth = 0
    for m in re.finditer(r"<div\b[^>]*>|</div\s*>", html[start:], re.IGNORECASE):
        depth += 1 if m.group(0)[1] != "/" else -1
        if depth == 0:
            return html[start:start + m.end()]
    return None


def _strip_class_blocks(html: str, tag: str, class_re: str) -> str:
    """Remove whole elements of `tag` whose class matches, tracking
    nesting depth of same-name tags (regex alone can't find the right
    closing tag). Used to drop wiki chrome that survives inside the
    content div: [edit]-section links, navboxes, category footers."""
    open_pat = re.compile(
        rf'<{tag}\b[^>]*class="[^"]*(?:{class_re})[^"]*"[^>]*>', re.IGNORECASE)
    tok_pat = re.compile(rf"<{tag}\b[^>]*>|</{tag}\s*>", re.IGNORECASE)
    while True:
        m = open_pat.search(html)
        if not m:
            return html
        depth, end = 0, None
        for t in tok_pat.finditer(html, m.start()):
            depth += 1 if t.group(0)[1] != "/" else -1
            if depth == 0:
                end = t.end()
                break
        if end is None:
            return html  # unbalanced markup — leave it rather than loop
        html = html[:m.start()] + html[end:]


def _clean_article_html(html: str, article_path: str) -> str:
    """ZIM/Parsoid page HTML → clean article HTML for markdown
    conversion: article-content extraction (dropping nav/header/footer
    chrome), script/style/media stripping (the same regexes the
    reader's sanitizer uses), internal links rewritten to absolute
    Wikipedia URLs. Without this, pandoc receives the full MediaWiki
    page skeleton and the text fills up with mw-body divs,
    title-wrapper spans, and menu link lists."""
    m = wzim._BODY_RE.search(html)
    body = m.group(1) if m else html
    body = _extract_content_div(body) or body
    body = _strip_class_blocks(body, "span", "mw-editsection")
    body = _strip_class_blocks(body, "div", "navbox|catlinks|printfooter|mw-hidden-catlinks")
    body = _strip_class_blocks(body, "table", "navbox")
    body = wzim._STRIP_BLOCKS_RE.sub("", body)
    body = wzim._STRIP_VOID_RE.sub("", body)
    body = wzim._ON_ATTR_RE.sub("", body)
    body = wzim._STYLE_ATTR_RE.sub("", body)
    base_dir = posixpath.dirname(article_path)
    body = wzim._HREF_RE.sub(
        lambda mm: _rewrite_save_href(mm.group(1), mm.group(2), base_dir), body)
    return body


def article_markdown(art: dict[str, Any]) -> tuple[str, bool]:
    """(markdown, converted_ok) — clean, chrome-free markdown of an
    article for LLM/text consumption. Falls back to cleaned HTML when
    pandoc is missing (converted_ok False)."""
    from ..tools import _markdownify_via_pandoc

    cleaned = _clean_article_html(art["html"], art["path"])
    md, ok = _markdownify_via_pandoc(cleaned, strip_raw_html=True)
    if ok:
        md = md.strip()
        # The page <h1> lives outside the extracted content div; give the
        # text a proper title heading unless one somehow survived.
        if not md.startswith("# "):
            md = f"# {art['title']}\n\n{md}"
        return md + "\n", True
    return cleaned, False


# ---------------------------------------------------------------------------
# Save / read / unsave
# ---------------------------------------------------------------------------

def _attribution_comment(art: dict[str, Any], cfg: dict[str, Any], today: str) -> str:
    return (
        "<!--\n"
        f"saved by enough wikisink — do not edit; re-save from the reader instead.\n"
        f"title: {art['title']}\n"
        f"source: {source_url(art['title'])}\n"
        "license: CC BY-SA 4.0\n"
        f"retrieved: {today}\n"
        f"origin: {_origin_line(art, cfg)}\n"
        "-->\n"
    )


def _manifest_body(art: dict[str, Any], cfg: dict[str, Any], today: str) -> str:
    return (
        f"# manifest — {art['title']}\n\n"
        f"- **source:** {source_url(art['title'])}\n"
        "- **license:** CC BY-SA 4.0 (with legacy CC BY-SA 3.0 + GFDL content)\n"
        f"- **retrieved:** {today}\n"
        f"- **origin:** {_origin_line(art, cfg)}\n\n"
        f"`{ARTICLE_NAME}` is the article exactly as the archive had it — "
        "click it in the file tree to read it in the wikisink viewer. "
        "it isn't meant to be edited (re-save from the reader to refresh it).\n"
    )


def save_article_to_dir(base_dir: Path, art: dict[str, Any],
                        cfg: dict[str, Any] | None = None,
                        dest: str = "cacheawl") -> Path:
    """Write a resolved article as a self-describing folder under
    ``base_dir`` (``base_dir/<slug>/`` with article.html + _manifest.md +
    .meta.json). The reusable core shared by ``save_article`` and the
    cacheawl wikisink ingest. Returns the folder path."""
    cfg = cfg or wconfig.load_config()
    slug = _slug(art["title"])
    today = dt.date.today().isoformat()
    art_dir = base_dir / slug
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / ARTICLE_NAME).write_text(
        _attribution_comment(art, cfg, today) + art["html"], encoding="utf-8")
    (art_dir / "_manifest.md").write_text(_manifest_body(art, cfg, today),
                                          encoding="utf-8")
    (art_dir / META_NAME).write_text(json.dumps({
        "zim_path": art["path"],
        "title": art["title"],
        "source_url": source_url(art["title"]),
        "license": "CC BY-SA 4.0",
        "retrieved": today,
        "origin": _origin_line(art, cfg),
        "saved_from": art["source"],
        "dest": dest,
    }, indent=2) + "\n", encoding="utf-8")
    # Replace any pre-folder-era flat saves of the same article.
    for legacy in (base_dir / f"{slug}.md", base_dir / f"{slug}.html",
                   art_dir / "article.md"):
        legacy.unlink(missing_ok=True)
    return art_dir


def save_article(project_dir: Path, path: str, dest: str) -> dict[str, Any]:
    """Save an article as a self-describing folder. `dest` is "project" or
    "cacheawl" ("infoworld" accepted as a legacy alias for cacheawl).
    Returns {saved_path, dest, title}; raises KeyError / WikisinkUnavailable
    / ValueError on bad dest."""
    if dest == "infoworld":  # legacy alias — the frontend still sends this
        dest = "cacheawl"
    if dest not in ("project", "cacheawl"):
        raise ValueError(f"unknown save destination {dest!r}")
    cfg = wconfig.load_config()
    art = woverlay.resolve_article(path=path)

    base = (project_dir / "wiki") if dest == "project" else _cacheawl_wiki_dir()
    art_dir = save_article_to_dir(base, art, cfg, dest=dest)

    if dest == "project":
        saved_display = str(art_dir.relative_to(project_dir)) + f"/{ARTICLE_NAME}"
        watched_tag = f"project:{project_dir.resolve()}"
    else:
        saved_display = str(art_dir / ARTICLE_NAME)
        watched_tag = "cacheawl"

    wconfig.upsert_watched(art["path"], art["title"], saved_to=watched_tag)
    log.info("wikisink saved %s -> %s", art["title"], art_dir)
    return {"saved_path": saved_display, "dest": dest, "title": art["title"]}


def _resolve_saved_dir(project_dir: Path, ref: str) -> Path:
    """Resolve a tree path (or absolute path) to a saved-article folder,
    validating shape and containment. `ref` may point at the folder or
    at any file inside it. Raises ValueError with a user-facing message
    when it isn't a saved-article folder we're allowed to touch."""
    p = Path(ref)
    if not p.is_absolute():
        p = project_dir / p
    try:
        p = p.resolve()
    except OSError as e:
        raise ValueError(f"can't resolve {ref!r}: {e}") from None
    d = p if p.is_dir() else p.parent
    if not (d / META_NAME).is_file() or not (d / ARTICLE_NAME).is_file():
        raise ValueError(f"{ref!r} is not a saved wikisink article folder")
    roots = (project_dir.resolve(), _cacheawl_wiki_dir().resolve())
    if not any(d == r or r in d.parents for r in roots):
        raise ValueError(f"{ref!r} is outside the project and cacheawl wiki")
    return d


def read_saved(project_dir: Path, ref: str) -> dict[str, Any]:
    """Load a saved article folder for the reader. Returns
    {path, title, html (raw, unsanitized), source: "saved", meta}."""
    d = _resolve_saved_dir(project_dir, ref)
    try:
        meta = json.loads((d / META_NAME).read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            meta = {}
    except (OSError, json.JSONDecodeError):
        meta = {}
    html = (d / ARTICLE_NAME).read_text(encoding="utf-8")
    return {
        "path": meta.get("zim_path") or "",
        "title": meta.get("title") or d.name,
        "html": html,
        "source": "saved",
        "meta": {**meta, "folder": str(d)},
    }


def unsave_article(project_dir: Path, ref: str) -> dict[str, Any]:
    """Delete a saved-article folder and drop its watch-registry tag.
    The article itself (archive copy, comments, overrides) is untouched.
    Returns {removed, title, dest}."""
    d = _resolve_saved_dir(project_dir, ref)
    try:
        meta = json.loads((d / META_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        meta = {}
    title = meta.get("title") or d.name
    zim_path = meta.get("zim_path") or ""
    under_cacheawl = _cacheawl_wiki_dir().resolve() in d.parents
    tag = "cacheawl" if under_cacheawl else f"project:{project_dir.resolve()}"
    shutil.rmtree(d)
    if zim_path:
        wconfig.remove_saved_to(zim_path, tag)
        # Legacy tag cleanup so pre-transition saves fully unwatch.
        if under_cacheawl:
            wconfig.remove_saved_to(zim_path, "infoworld")
    log.info("wikisink unsaved %s (%s)", title, d)
    return {"removed": str(d), "title": title,
            "dest": "cacheawl" if under_cacheawl else "project"}
