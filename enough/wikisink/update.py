"""The wikisink run: refresh watched articles, gather intelligence,
produce a report.

Hybrid overlay model: the multi-GB base ZIM is only replaced when the
user confirms a newer snapshot in the setup modal; between snapshots,
every wikisink run refreshes the *watched* set (articles the user saved
or commented on) live from Wikipedia into the overlay store, so the
things the user actually cares about are always current.

Phases (each persisted to the run dir as it completes, so an
interrupted run < 24h old resumes instead of refetching):

  1 revisions  — current revid + edit counts for the watched set
  2 refresh    — Parsoid HTML → overlay for changed watched articles
  3 spikes     — watched-set edit spikes (>30/day or >10/day avg)
  4 global     — AQS top-by-edits candidates, cross-checked locally
  5 rankings   — pageview top-1000 snapshot + movers/losers
  6 deletions  — watched + recently-viewed titles gone from live
                 Wikipedia, with suspicion scoring
  7 snapshot   — is a newer base ZIM available?

All network work is gated by the `wikisink_live_updates` broker toggle;
with it off the run reports from local state only. HTTP etiquette: one
descriptive UA, batched title queries, gentle pacing, 429-aware backoff.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from .. import __version__, broker
from . import comments as wcomments
from . import config as wconfig
from . import download as wdownload
from . import overlay as woverlay
from . import rankings as wrankings
from . import report as wreport
from . import zim as wzim

log = logging.getLogger("enough.wikisink")

USER_AGENT = f"enough-wikisink/{__version__} (personal offline reader)"
ACTION_API = "https://en.wikipedia.org/w/api.php"
REST_HTML = "https://en.wikipedia.org/api/rest_v1/page/html/{title}"
AQS_TOP_EDITS = ("https://wikimedia.org/api/rest_v1/metrics/edited-pages/"
                 "top-by-edits/en.wikipedia.org/all-editor-types/content/"
                 "{y}/{m:02d}/{d:02d}")

BATCH_TITLES = 50
PACE_SECONDS = 0.2
SPIKE_DAY_THRESHOLD = 30
SPIKE_AVG_THRESHOLD = 10
MAX_GLOBAL_SPIKE_DAYS = 7
MAX_DELETION_CHECKS = 250
MAX_REVISION_DETAIL = 40      # per-article revision-history queries per run
RESUME_WINDOW_H = 24

# The server sets this to fan wiki_sink progress events out over SSE;
# calls arrive from a worker thread, so the hook must be thread-safe.
PROGRESS_EMITTER: Callable[[dict[str, Any]], None] | None = None


def _progress(phase: str, done: int, total: int) -> None:
    if PROGRESS_EMITTER is not None:
        try:
            PROGRESS_EMITTER({"phase": phase, "done": done, "total": total})
        except Exception:  # noqa: BLE001 — progress must never kill a run
            log.exception("wiki_sink progress emit failed")


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT},
                        timeout=30, follow_redirects=True)


def _get_with_backoff(client: httpx.Client, url: str,
                      params: dict[str, Any] | None = None,
                      tries: int = 4) -> httpx.Response:
    delay = 1.0
    for attempt in range(tries):
        resp = client.get(url, params=params)
        if resp.status_code != 429:
            return resp
        time.sleep(delay)
        delay *= 2
    return resp


# ---------------------------------------------------------------------------
# Watched set
# ---------------------------------------------------------------------------

def build_watched_set(cfg: dict[str, Any]) -> dict[str, Any]:
    """{'watched': [{path,title,overridden}], 'deletion_only': [titles]}"""
    seen: dict[str, dict[str, Any]] = {}
    for w in cfg.get("watched", []):
        seen[w["path"]] = {"path": w["path"], "title": w.get("title") or w["path"],
                           "overridden": wconfig.is_overridden(w["path"], cfg)}
    for c in wcomments.commented_articles():
        if c["path"] and c["path"] not in seen:
            seen[c["path"]] = {"path": c["path"], "title": c["title"] or c["path"],
                               "overridden": wconfig.is_overridden(c["path"], cfg)}
    for o in cfg.get("overrides", []):
        seen.setdefault(o["path"], {"path": o["path"], "title": o.get("title") or o["path"],
                                    "overridden": True})
    watched = list(seen.values())
    ring = [e for e in cfg.get("viewed_ring", []) if e.get("path") not in seen]
    deletion_only = [e.get("title") or e.get("path") for e in ring]
    budget = MAX_DELETION_CHECKS - len(watched)
    return {"watched": watched, "deletion_only": deletion_only[-max(budget, 0):]}


# ---------------------------------------------------------------------------
# Phase 1: existence + revisions
# ---------------------------------------------------------------------------

def _title_of(entry: dict[str, Any]) -> str:
    return (entry.get("title") or entry["path"]).replace("_", " ")

def check_revisions(client: httpx.Client, titles: list[str],
                    since_iso: str | None) -> dict[str, Any]:
    """Batched action-API existence + latest-revision check, plus edit
    counts since the last run for changed pages (bounded)."""
    latest: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for i in range(0, len(titles), BATCH_TITLES):
        batch = titles[i:i + BATCH_TITLES]
        resp = _get_with_backoff(client, ACTION_API, params={
            "action": "query", "format": "json", "formatversion": "2",
            "prop": "revisions", "rvprop": "ids|timestamp|user|comment",
            "titles": "|".join(batch), "redirects": "1",
        })
        resp.raise_for_status()
        pages = (resp.json().get("query") or {}).get("pages") or []
        for page in pages:
            title = page.get("title", "")
            if page.get("missing"):
                missing.append(title)
                continue
            revs = page.get("revisions") or [{}]
            latest[title] = {
                "revid": revs[0].get("revid"),
                "timestamp": revs[0].get("timestamp"),
                "comment": revs[0].get("comment", ""),
                "user": revs[0].get("user", ""),
            }
        _progress("revisions", min(i + BATCH_TITLES, len(titles)), len(titles))
        time.sleep(PACE_SECONDS)
    edit_counts: dict[str, list[str]] = {}
    if since_iso:
        detail = list(latest.items())[:MAX_REVISION_DETAIL]
        for title, info in detail:
            resp = _get_with_backoff(client, ACTION_API, params={
                "action": "query", "format": "json", "formatversion": "2",
                "prop": "revisions", "rvprop": "timestamp", "rvlimit": "500",
                "rvend": since_iso,  # rvend = older bound when going newest→oldest
                "titles": title,
            })
            if resp.status_code != 200:
                continue
            pages = (resp.json().get("query") or {}).get("pages") or []
            stamps = [r.get("timestamp", "") for p in pages
                      for r in (p.get("revisions") or [])]
            if stamps:
                edit_counts[title] = stamps
            time.sleep(PACE_SECONDS)
    return {"latest": latest, "missing": missing, "edit_stamps": edit_counts}


# ---------------------------------------------------------------------------
# Phase 2: overlay refresh
# ---------------------------------------------------------------------------

def refresh_overlays(client: httpx.Client, watched: list[dict[str, Any]],
                     latest: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    refreshed = []
    todo = []
    for entry in watched:
        if entry.get("overridden"):
            continue
        title = _title_of(entry)
        info = latest.get(title)
        if not info or not info.get("revid"):
            continue
        # Skip when the overlay already holds this exact revision.
        key = wconfig.article_key(entry["path"])
        meta_path = wconfig.overlay_dir() / f"{key}.meta.json"
        if meta_path.is_file():
            try:
                if json.loads(meta_path.read_text())["revid"] == info["revid"]:
                    continue
            except (OSError, json.JSONDecodeError, KeyError):
                pass
        todo.append((entry, title, info))
    for n, (entry, title, info) in enumerate(todo, start=1):
        url = REST_HTML.format(title=title.replace(" ", "_"))
        try:
            resp = _get_with_backoff(client, url)
            resp.raise_for_status()
        except (httpx.HTTPError, OSError) as e:
            log.warning("overlay refresh failed for %s (%s)", title, e)
            continue
        woverlay.put_overlay(entry["path"], title, resp.text, {
            "revid": info["revid"], "fetched_at": wconfig._now_iso(),
            "source_url": url,
        })
        refreshed.append({"path": entry["path"], "title": title,
                          "revid": info["revid"]})
        _progress("refresh", n, len(todo))
        time.sleep(PACE_SECONDS)
    return refreshed


# ---------------------------------------------------------------------------
# Phase 3 + 4: edit spikes
# ---------------------------------------------------------------------------

def find_spikes(edit_stamps: dict[str, list[str]],
                since_iso: str | None) -> list[dict[str, Any]]:
    spikes = []
    for title, stamps in edit_stamps.items():
        per_day: dict[str, int] = {}
        for s in stamps:
            per_day[s[:10]] = per_day.get(s[:10], 0) + 1
        if not per_day:
            continue
        peak_day, peak = max(per_day.items(), key=lambda kv: kv[1])
        days_window = 1
        if since_iso:
            try:
                start = dt.datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
                days_window = max((dt.datetime.now(dt.timezone.utc) - start).days, 1)
            except ValueError:
                pass
        avg = len(stamps) / days_window
        if peak > SPIKE_DAY_THRESHOLD or avg > SPIKE_AVG_THRESHOLD:
            spikes.append({"title": title, "total_edits": len(stamps),
                           "peak_day": peak_day, "peak_edits": peak,
                           "avg_per_day": round(avg, 1)})
    spikes.sort(key=lambda s: -s["total_edits"])
    return spikes


def global_spike_candidates(client: httpx.Client,
                            since: dt.date | None) -> list[dict[str, Any]]:
    yesterday = dt.date.today() - dt.timedelta(days=1)
    start = since or (yesterday - dt.timedelta(days=2))
    days = min((yesterday - start).days + 1, MAX_GLOBAL_SPIKE_DAYS)
    agg: dict[str, int] = {}
    for n in range(days):
        day = yesterday - dt.timedelta(days=n)
        url = AQS_TOP_EDITS.format(y=day.year, m=day.month, d=day.day)
        try:
            resp = _get_with_backoff(client, url)
            if resp.status_code != 200:
                continue
            results = ((resp.json().get("items") or [{}])[0]
                       .get("results") or [{}])[0].get("top") or []
        except (httpx.HTTPError, OSError, IndexError):
            continue
        for it in results:
            title = it.get("page_title") or ""
            if title.startswith(("Wikipedia:", "User:", "Talk:", "Template:")):
                continue
            agg[title] = agg.get(title, 0) + int(it.get("edits") or 0)
        _progress("global-spikes", n + 1, days)
        time.sleep(PACE_SECONDS)
    top = sorted(agg.items(), key=lambda kv: -kv[1])[:15]
    out = []
    for title, edits in top:
        out.append({"title": title.replace("_", " "), "edits": edits,
                    "local": wzim.has_article(title=title.replace("_", " "))})
    return out


# ---------------------------------------------------------------------------
# Phase 6: deletions + suspicion scoring
# ---------------------------------------------------------------------------

_BENIGN_MARKERS = ("g7", "author request", "copyvio", "copyright", "vandal",
                   "spam", "g10", "attack page", "test page", "g2",
                   "redirect", "housekeeping", "duplicate")
_SUSPICIOUS_MARKERS = ("articles for deletion", "afd", "notability",
                       "wp:n", "prod", "proposed deletion", "not notable")


def score_deletion(log_comment: str, *, watched: bool,
                   commented: bool) -> tuple[int, list[str]]:
    """0–100 suspicion score with human-readable reasons. High = smells
    like a policy deletion of useful material (the Odin-language case),
    low = routine cleanup."""
    c = (log_comment or "").lower()
    score, reasons = 0, []
    if any(m in c for m in _SUSPICIOUS_MARKERS):
        score += 45
        reasons.append("deleted via AfD/PROD/notability rationale")
    if not any(m in c for m in _BENIGN_MARKERS) and not reasons:
        score += 20
        reasons.append("rationale doesn't match routine-cleanup patterns")
    if any(m in c for m in _BENIGN_MARKERS):
        score -= 40
        reasons.append("rationale looks like routine cleanup (copyvio/vandalism/author request)")
    if watched:
        score += 20
        reasons.append("you saved this article")
    if commented:
        score += 15
        reasons.append("you commented on this article")
    return max(0, min(100, score)), reasons


def check_deletions(client: httpx.Client, missing_titles: list[str],
                    cfg: dict[str, Any]) -> list[dict[str, Any]]:
    watched_titles = {(w.get("title") or "").lower() for w in cfg.get("watched", [])}
    commented_titles = {c["title"].lower() for c in wcomments.commented_articles()}
    out = []
    for n, title in enumerate(missing_titles, start=1):
        resp = _get_with_backoff(client, ACTION_API, params={
            "action": "query", "format": "json", "formatversion": "2",
            "list": "logevents", "letype": "delete", "letitle": title,
            "lelimit": "5",
        })
        if resp.status_code != 200:
            continue
        events = (resp.json().get("query") or {}).get("logevents") or []
        if not events:
            # Missing but no deletion log — likely renamed/merged.
            out.append({"title": title, "reason": "(no deletion log — possibly moved/merged)",
                        "when": None, "score": 10,
                        "score_reasons": ["missing from live Wikipedia without a deletion log"],
                        "still_local": wzim.has_article(title=title)})
            continue
        ev = events[0]
        comment = ev.get("comment") or ev.get("parsedcomment") or ""
        score, reasons = score_deletion(
            comment,
            watched=title.lower() in watched_titles,
            commented=title.lower() in commented_titles)
        out.append({"title": title, "reason": comment[:300],
                    "when": ev.get("timestamp"), "score": score,
                    "score_reasons": reasons,
                    "still_local": wzim.has_article(title=title)})
        _progress("deletions", n, len(missing_titles))
        time.sleep(PACE_SECONDS)
    out.sort(key=lambda d: -d["score"])
    return out


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def _find_resumable(now: dt.datetime) -> Path | None:
    """Most recent incomplete (no report.md) run dir younger than the
    resume window."""
    candidates = sorted(wconfig.state_dir().glob("run-*"), reverse=True)
    for c in candidates:
        if (c / "report.md").exists():
            continue
        try:
            started = dt.datetime.strptime(c.name[4:], "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            continue
        if (now - started).total_seconds() < RESUME_WINDOW_H * 3600:
            return c
    return None


def _load_phase(run_dir: Path, name: str) -> Any | None:
    p = run_dir / f"{name}.json"
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
    return None


def _store_phase(run_dir: Path, name: str, data: Any) -> Any:
    (run_dir / f"{name}.json").write_text(
        json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return data


def run_wikisink(project_dir: Path, scope: str = "watched") -> str:
    """Execute a wikisink run; returns the bounded markdown report."""
    cfg = wconfig.load_config()
    if not wconfig.installed(cfg):
        raise wzim.WikisinkUnavailable(
            wconfig.unavailable_reason(cfg)
            or "the wikipedia archive isn't reachable right now.")
    live = broker.is_enabled("wikisink_live_updates")
    now = dt.datetime.now()
    run_dir = _find_resumable(now)
    resumed = run_dir is not None
    if run_dir is None:
        run_dir = wconfig.state_dir() / f"run-{now.strftime('%Y-%m-%d_%H-%M-%S')}"
        run_dir.mkdir(parents=True, exist_ok=True)

    last_run_iso = cfg.get("last_wikisink_at")
    last_run_date = None
    if last_run_iso:
        try:
            last_run_date = dt.date.fromisoformat(last_run_iso[:10])
        except ValueError:
            pass

    ws = build_watched_set(cfg)
    watched = ws["watched"]
    data: dict[str, Any] = {
        "run_dir": str(run_dir),
        "resumed": resumed,
        "scope": scope,
        "live": live,
        "last_run": last_run_iso,
        "watched_count": len(watched),
        "overrides": cfg.get("overrides", []),
    }

    if live:
        with _client() as client:
            titles = [_title_of(w) for w in watched]
            revs = _load_phase(run_dir, "revisions")
            if revs is None:
                _progress("revisions", 0, max(len(titles), 1))
                revs = _store_phase(run_dir, "revisions",
                                    check_revisions(client, titles, last_run_iso))
            data["revisions"] = revs

            if scope != "report-only":
                refreshed = _load_phase(run_dir, "refreshed")
                if refreshed is None:
                    refreshed = _store_phase(
                        run_dir, "refreshed",
                        refresh_overlays(client, watched, revs["latest"]))
                data["refreshed"] = refreshed

            data["spikes_watched"] = find_spikes(revs.get("edit_stamps") or {},
                                                 last_run_iso)

            gspikes = _load_phase(run_dir, "global_spikes")
            if gspikes is None:
                gspikes = _store_phase(run_dir, "global_spikes",
                                       global_spike_candidates(client, last_run_date))
            data["spikes_global"] = gspikes

            rank = _load_phase(run_dir, "rankings")
            if rank is None:
                _progress("rankings", 0, 1)
                rank = _store_phase(run_dir, "rankings",
                                    wrankings.rankings_phase(
                                        client, last_run_date,
                                        [_title_of(w) for w in watched]))
                _progress("rankings", 1, 1)
            data["rankings"] = rank

            deletions = _load_phase(run_dir, "deletions")
            if deletions is None:
                missing = list(revs.get("missing") or [])
                # Recently-viewed (but unwatched) titles get an existence
                # check too — cheap batched query.
                extra = ws["deletion_only"]
                if extra:
                    extra_revs = check_revisions(client, extra, None)
                    missing += extra_revs["missing"]
                deletions = _store_phase(run_dir, "deletions",
                                         check_deletions(client, missing, cfg))
            data["deletions"] = deletions
    else:
        data["note_offline"] = ("live updates are off (broker toggle "
                                "`wikisink_live_updates`) — nothing was fetched; "
                                "this is a local-state report.")

    data["newer_snapshot"] = wdownload.newer_snapshot_available(cfg) if live else None

    bounded, full = wreport.build_report(data)
    (run_dir / "report.md").write_text(full, encoding="utf-8")

    cfg = wconfig.load_config()
    cfg["last_wikisink_at"] = wconfig._now_iso()
    wconfig.save_config(cfg)
    _progress("done", 1, 1)
    return bounded
