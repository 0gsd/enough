"""Markdown report builder for wikisink runs.

Two renderings from the same data: a *bounded* report (section caps,
≤ ~6k chars) that goes into the agent's tool result / chat for clipboard
copying, and the *full* uncapped report written to the run dir. Nothing
is saved into the project unless the user asks.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

BOUNDED_LIMIT = 6000
CAP_WATCHED = 20
CAP_SPIKES = 10
CAP_MOVERS = 15
CAP_DELETIONS = 20


def _fmt_watched_updates(data: dict[str, Any], cap: int | None) -> list[str]:
    revs = (data.get("revisions") or {})
    latest = revs.get("latest") or {}
    stamps = revs.get("edit_stamps") or {}
    refreshed = {r["title"]: r for r in (data.get("refreshed") or [])}
    changed = [(t, stamps.get(t, [])) for t in latest if t in stamps or t in refreshed]
    changed.sort(key=lambda kv: -len(kv[1]))
    if cap:
        changed = changed[:cap]
    lines = []
    for title, st in changed:
        info = latest.get(title) or {}
        bits = [f"**{title}**"]
        if st:
            bits.append(f"{len(st)} edit{'s' if len(st) != 1 else ''} since last wikisink")
        if title in refreshed:
            bits.append(f"local copy refreshed → revision {refreshed[title]['revid']}")
        lines.append("- " + " — ".join(bits))
        if info.get("comment"):
            lines.append(f"  - latest edit summary: “{info['comment'][:110]}” ({info.get('user', '?')})")
    return lines or ["- no watched articles changed since the last run."]


def _fmt_spikes(data: dict[str, Any], cap: int | None) -> list[str]:
    lines = []
    watched = data.get("spikes_watched") or []
    if cap:
        watched = watched[:cap]
    for s in watched:
        lines.append(
            f"- **{s['title']}** (watched): {s['total_edits']} edits, "
            f"peak {s['peak_edits']} on {s['peak_day']} "
            f"(avg {s['avg_per_day']}/day)")
    glob = data.get("spikes_global") or []
    if cap:
        glob = glob[:cap]
    for s in glob:
        local = "in your local archive" if s.get("local") else "not in your local archive"
        lines.append(f"- {s['title']}: {s['edits']} edits ({local})")
    return lines or ["- no notable edit activity detected."]


def _fmt_movers(data: dict[str, Any], cap: int | None) -> list[str]:
    rank = data.get("rankings") or {}
    diff = rank.get("diff")
    lines = []
    if diff:
        lines.append(f"_top-1000 pageview rankings, {diff['old_day']} → {diff['new_day']}_")
        for c in (diff.get("climbers") or [])[:cap or None]:
            lines.append(f"- ▲ {c['article'].replace('_', ' ')}: #{c['from']} → #{c['to']} (+{c['delta']})")
        for f in (diff.get("fallers") or [])[:cap or None]:
            lines.append(f"- ▼ {f['article'].replace('_', ' ')}: #{f['from']} → #{f['to']} ({f['delta']})")
        for e in (diff.get("new_entries") or [])[:cap or None]:
            lines.append(f"- ✳ new to the top 1000: {e['article'].replace('_', ' ')} (#{e['rank']})")
        for d in (diff.get("dropouts") or [])[:cap or None]:
            lines.append(f"- ✕ dropped out: {d['article'].replace('_', ' ')} (was #{d['was']})")
    trends = rank.get("watched_trends") or []
    if trends:
        lines.append("_watched-article pageviews since last run:_")
        for t in trends[:cap or None]:
            lines.append(f"- {t['title']}: {t['total']:,} views over {t['days']} days "
                         f"(peak {t['peak']:,}/day)")
    if not lines:
        lines = ["- first run: rankings snapshot taken; movers appear from the next run on."]
    return lines


def _fmt_deletions(data: dict[str, Any], cap: int | None) -> list[str]:
    dels = data.get("deletions") or []
    if cap:
        dels = dels[:cap]
    lines = []
    for d in dels:
        flag = "🔴" if d["score"] >= 50 else ("🟡" if d["score"] >= 25 else "⚪")
        lines.append(f"- {flag} **{d['title']}** — suspicion {d['score']}/100"
                     + (f", deleted {d['when'][:10]}" if d.get("when") else ""))
        if d.get("reason"):
            lines.append(f"  - log: “{d['reason'][:140]}”")
        if d.get("score_reasons"):
            lines.append("  - " + "; ".join(d["score_reasons"]))
        if d.get("still_local"):
            lines.append("  - your local copy still exists — open the article in the "
                         "wikisink browser and click 🛡 to **override** the deletion "
                         "and preserve it permanently.")
    return lines or ["- no watched or recently-viewed articles were deleted."]


def _fmt_base(data: dict[str, Any]) -> list[str]:
    ns = data.get("newer_snapshot")
    if ns:
        return [f"- a newer base archive is available: snapshot {ns['date']} "
                f"({ns['size_human']}). replace it via 🚰 → ⚙ (multi-GB download, "
                "user-confirmed — this run did not download it)."]
    return ["- base archive is the newest published snapshot."]


def _assemble(data: dict[str, Any], *, capped: bool) -> str:
    cap = {"watched": CAP_WATCHED, "spikes": CAP_SPIKES,
           "movers": CAP_MOVERS, "deletions": CAP_DELETIONS} if capped else \
          {"watched": None, "spikes": None, "movers": None, "deletions": None}
    today = dt.date.today().isoformat()
    head = [f"# wikisink report — {today}"]
    meta = [f"watched articles: {data.get('watched_count', 0)}"
            + (f" · last run {data['last_run'][:10]}" if data.get("last_run") else " · first run")
            + (" · resumed an interrupted run" if data.get("resumed") else "")]
    if data.get("note_offline"):
        meta.append(data["note_offline"])
    if data.get("scope") == "report-only":
        meta.append("scope: report-only (no overlay refresh)")
    parts = head + [" \n".join(meta), ""]
    parts += ["## watched article updates", *_fmt_watched_updates(data, cap["watched"]), ""]
    parts += ["## edit spikes", *_fmt_spikes(data, cap["spikes"]), ""]
    parts += ["## movers & losers (pageviews)", *_fmt_movers(data, cap["movers"]), ""]
    parts += ["## deletions", *_fmt_deletions(data, cap["deletions"]), ""]
    parts += ["## base archive", *_fmt_base(data), ""]
    if data.get("overrides"):
        names = ", ".join(o["title"] for o in data["overrides"])
        parts += [f"_preserved by deletion override (never refreshed): {names}_", ""]
    parts += [f"_full report: {data.get('run_dir')}/report.md_"]
    return "\n".join(parts)


def build_report(data: dict[str, Any]) -> tuple[str, str]:
    """(bounded, full)."""
    full = _assemble(data, capped=False)
    bounded = _assemble(data, capped=True)
    if len(bounded) > BOUNDED_LIMIT:
        bounded = bounded[:BOUNDED_LIMIT - 80].rsplit("\n", 1)[0] + \
            f"\n\n_(truncated — full report: {data.get('run_dir')}/report.md)_"
    return bounded, full
