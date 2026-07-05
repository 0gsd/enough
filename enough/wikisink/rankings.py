"""Pageview rankings: top-1000 snapshots + movers/losers.

Kiwix bakes its "top 1M" selection at ZIM build time, but the underlying
popularity data — Wikimedia's AQS pageviews API — updates daily. Each
wikisink run snapshots the daily top-1000 into `{storage}/rankings/` so
successive runs can be diffed: new entries, big climbers, dropouts.
Watched articles get exact per-article daily view counts regardless of
rank.

AQS endpoints (public, no auth; ~24h data lag):
  /metrics/pageviews/top/en.wikipedia/all-access/{y}/{m}/{d}
  /metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/
      {title}/daily/{start}/{end}
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any

import httpx

from . import config as wconfig

log = logging.getLogger("enough.wikisink")

AQS_TOP = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
           "en.wikipedia/all-access/{y}/{m:02d}/{d:02d}")
AQS_ARTICLE = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
               "en.wikipedia/all-access/all-agents/{title}/daily/{start}/{end}")

# Skip non-article chrome that always tops the raw list.
_SKIP_PREFIXES = ("Special:", "Wikipedia:", "File:", "Portal:", "Help:",
                  "Talk:", "User:", "Template:", "Category:", "Draft:")
_SKIP_EXACT = {"Main_Page", "Wikipedia", "-"}


def _clean_top(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for it in items:
        art = it.get("article") or ""
        if art in _SKIP_EXACT or art.startswith(_SKIP_PREFIXES):
            continue
        out.append({"article": art, "views": it.get("views", 0)})
    for rank, it in enumerate(out, start=1):
        it["rank"] = rank
    return out


def fetch_top_day(client: httpx.Client, day: dt.date) -> list[dict[str, Any]]:
    url = AQS_TOP.format(y=day.year, m=day.month, d=day.day)
    resp = client.get(url)
    resp.raise_for_status()
    items = (resp.json().get("items") or [{}])[0].get("articles") or []
    return _clean_top(items)


def snapshot_path(day: dt.date) -> Any:
    return wconfig.rankings_dir() / f"{day.isoformat()}-daily.json"


def take_snapshot(client: httpx.Client, day: dt.date) -> bool:
    """Fetch + persist one day's top list (skip if already stored).
    Returns True if a snapshot exists afterwards."""
    p = snapshot_path(day)
    if p.is_file():
        return True
    try:
        top = fetch_top_day(client, day)
    except (httpx.HTTPError, OSError) as e:
        log.warning("rankings snapshot for %s failed (%s)", day, e)
        return False
    if not top:
        return False
    p.write_text(json.dumps({"date": day.isoformat(), "top": top}) + "\n",
                 encoding="utf-8")
    return True


def stored_snapshots() -> list[dt.date]:
    days = []
    for p in sorted(wconfig.rankings_dir().glob("*-daily.json")):
        try:
            days.append(dt.date.fromisoformat(p.name[:10]))
        except ValueError:
            continue
    return days


def _load(day: dt.date) -> dict[str, int]:
    """{article: rank} for a stored day."""
    try:
        doc = json.loads(snapshot_path(day).read_text(encoding="utf-8"))
        return {it["article"]: it["rank"] for it in doc.get("top", [])}
    except (OSError, json.JSONDecodeError, KeyError):
        return {}


def diff_snapshots(old_day: dt.date, new_day: dt.date,
                   top_n: int = 15) -> dict[str, Any]:
    """Movers & losers between two stored snapshots."""
    old, new = _load(old_day), _load(new_day)
    if not old or not new:
        return {"old_day": old_day.isoformat(), "new_day": new_day.isoformat(),
                "climbers": [], "fallers": [], "new_entries": [], "dropouts": []}
    climbers, fallers, entries, dropouts = [], [], [], []
    for art, rank in new.items():
        if art in old:
            delta = old[art] - rank
            if delta > 0:
                climbers.append({"article": art, "from": old[art], "to": rank, "delta": delta})
            elif delta < 0:
                fallers.append({"article": art, "from": old[art], "to": rank, "delta": delta})
        else:
            entries.append({"article": art, "rank": rank})
    for art, rank in old.items():
        if art not in new:
            dropouts.append({"article": art, "was": rank})
    climbers.sort(key=lambda x: -x["delta"])
    fallers.sort(key=lambda x: x["delta"])
    entries.sort(key=lambda x: x["rank"])
    dropouts.sort(key=lambda x: x["was"])
    return {
        "old_day": old_day.isoformat(), "new_day": new_day.isoformat(),
        "climbers": climbers[:top_n], "fallers": fallers[:top_n],
        "new_entries": entries[:top_n], "dropouts": dropouts[:top_n],
    }


def watched_trends(client: httpx.Client, titles: list[str],
                   since: dt.date, until: dt.date) -> list[dict[str, Any]]:
    """Daily pageview series (summed + peak) per watched title."""
    out = []
    for title in titles:
        url = AQS_ARTICLE.format(
            title=title.replace(" ", "_"),
            start=since.strftime("%Y%m%d"), end=until.strftime("%Y%m%d"))
        try:
            resp = client.get(url)
            if resp.status_code == 404:  # no data for the window
                continue
            resp.raise_for_status()
            items = resp.json().get("items") or []
        except (httpx.HTTPError, OSError):
            continue
        views = [it.get("views", 0) for it in items]
        if views:
            out.append({"title": title, "total": sum(views),
                        "peak": max(views), "days": len(views)})
    out.sort(key=lambda x: -x["total"])
    return out


def rankings_phase(client: httpx.Client, last_run: dt.date | None,
                   watched_titles: list[str]) -> dict[str, Any]:
    """The wikisink run's rankings phase: snapshot yesterday (AQS lags a
    day), diff against the oldest snapshot since the last run, and pull
    watched-article trends."""
    yesterday = dt.date.today() - dt.timedelta(days=1)
    take_snapshot(client, yesterday)
    stored = stored_snapshots()
    result: dict[str, Any] = {"snapshot_days": [d.isoformat() for d in stored[-8:]]}
    if len(stored) >= 2:
        # Compare the newest against the snapshot closest to (but not
        # after) the previous run — or just the previous snapshot.
        base = stored[0]
        if last_run:
            candidates = [d for d in stored if d <= last_run]
            base = candidates[-1] if candidates else stored[0]
        if base == stored[-1] and len(stored) >= 2:
            base = stored[-2]
        result["diff"] = diff_snapshots(base, stored[-1])
    since = last_run or (yesterday - dt.timedelta(days=7))
    if watched_titles:
        result["watched_trends"] = watched_trends(
            client, watched_titles[:25], since, yesterday)
    return result
