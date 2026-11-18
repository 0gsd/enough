"""The sidebar's switches: paradigms (`/api/paradigm*`), skills (`/api/skills*`), readvisors (`/api/roles*`, `/api/readvisors/remove`).

Moved out of `enough/server.py`'s `create_app` in 0.8 (lane W2-SV), code unchanged: `build_router` is the old
factory's closure for this group, and the names it closed over come in on `ctx`."""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from .. import agent_free as _agent_free
from .. import prompt as prompt_mod
from ..prompt import list_paradigms, list_roles, list_skills, set_active_paradigm, set_role_enabled
from .common import AppContext
from ..server import _escape_html, _readvisor_origin


def build_router(ctx: AppContext) -> APIRouter:
    router = APIRouter()
    llm_url = ctx.llm_url
    project_dir = ctx.project_dir
    session = ctx.session

    def _paradigm_list_html(refused: str | None = None) -> str:
        """The sidebar's paradigm list (0.8): one toggle per paradigm, up to
        `MAX_ACTIVE_PARADIGMS` on at once. Notes ride as rows of their own
        carrying `data-*` attributes (and an English fallback) for the page
        to translate: `data-paradigm-note="cap"` / `"empty"` for a refused
        toggle, `"composed"` when the set on has no text of its own (with
        `data-stale` naming the members a written one was set aside for)."""
        def _attr(s: str) -> str:
            return _escape_html(s).replace('"', "&quot;").replace("'", "&#39;")

        rness = project_dir / "rness"
        items = list_paradigms(rness)
        if not items:
            return '<div class="empty-note">no paradigms in rness/paradigms/</div>'
        choice = prompt_mod.choose_paradigm_text(rness)
        active = set(choice.names)
        rows = []
        for name, desc, tooltip in items:
            is_active = name in active
            cls = "on" if is_active else "off"
            marker = "●" if is_active else "○"
            # Prefer the user-facing tooltip; fall back to the agent-facing
            # description so existing paradigms don't lose their hover text
            # until each one's `enough-tooltip-text:` is populated.
            tip_text = tooltip if tooltip else desc
            tip = _escape_html(tip_text) if tip_text else ""
            vals = json.dumps({"name": name, "on": "0" if is_active else "1"})
            rows.append(
                f'<li class="paradigm-row {cls}" title="{tip}">'
                f'  <button class="paradigm-toggle" '
                f'    hx-post="/api/paradigm/toggle" '
                f"    hx-vals='{_attr(vals)}' "
                f'    hx-target="#paradigm-list" hx-swap="innerHTML">'
                f'    {marker}'
                f'  </button>'
                f'  <span class="paradigm-name">{_escape_html(name)}</span>'
                f'</li>'
            )
        if refused:
            rows.append(
                f'<li class="paradigm-note" data-paradigm-note="{_attr(refused)}" '
                f'data-limit="{prompt_mod.MAX_ACTIVE_PARADIGMS}">'
                f'{_escape_html(prompt_mod.PARADIGM_REFUSALS.get(refused, ""))}</li>')
        if choice.kind == "composed":
            stale = " ".join(choice.stale)
            rows.append(
                '<li class="paradigm-note" data-paradigm-note="composed" '
                f'data-paradigms="{_attr(" ".join(choice.names))}" '
                f'data-stale="{_attr(stale)}">'
                "These paradigms have no text of their own together: enough "
                "composes one from each.</li>")
        kind = _attr(choice.kind)
        return (f'<ul class="paradigms" data-paradigm-text="{kind}" '
                f'data-active-count="{len(choice.names)}">' + "".join(rows) + "</ul>")

    @router.get("/api/paradigm", response_class=HTMLResponse)
    async def api_paradigm() -> HTMLResponse:
        from ..skeleton import resync_globals
        resync_globals(project_dir)  # pick up globals added since launch
        return HTMLResponse(_paradigm_list_html())

    def _paradigm_name(form) -> str:
        name = (form.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "missing name")
        # Validate: only allow names that resolve to an existing paradigm file.
        valid_names = {n for n, _d, _t in list_paradigms(project_dir / "rness")}
        if name not in valid_names:
            raise HTTPException(400, f"unknown paradigm: {name}")
        return name

    @router.post("/api/paradigm/toggle", response_class=HTMLResponse)
    async def api_paradigm_toggle(request: Request) -> HTMLResponse:
        """Switch one paradigm on (`on=1`) or off (`on=0`) within the set. A
        fourth, or turning off the last, is refused: 200 with the list
        re-rendered and a note row saying why (the skills' refusal path)."""
        form = await request.form()
        name = _paradigm_name(form)
        want_on = (form.get("on") or "").strip() == "1"
        try:
            prompt_mod.toggle_paradigm(project_dir / "rness", name, want_on)
        except prompt_mod.ParadigmSetRefused as refusal:
            return HTMLResponse(_paradigm_list_html(refused=refusal.reason))
        return HTMLResponse(_paradigm_list_html())

    @router.post("/api/paradigm/set", response_class=HTMLResponse)
    async def api_paradigm_set(request: Request) -> HTMLResponse:
        """This one alone (the pre-0.8 switch, kept for old callers)."""
        form = await request.form()
        name = _paradigm_name(form)
        set_active_paradigm(project_dir / "rness", name)
        return HTMLResponse(_paradigm_list_html())

    # ------------------------------------------------------------------
    # Skills — the sidebar list, the guarded toggle, and the first-use
    # audit of untrusted skills (docs/skills-round-plan.md §3). Trusted =
    # a symlink into this install's defaults/skills; everything else gets
    # read before it's allowed into the system prompt. Audit progress
    # streams on the `skill-audit` SSE event.
    # ------------------------------------------------------------------

    from .. import skillaudit as _skillaudit

    # State labels the sidebar renders. Terse, lowercase, house voice.
    _SKILL_MARKS = {
        "unverified": ("unverified", "not shipped with enough — enabling it "
                                     "runs a first-use audit first"),
        "auditing": ("auditing…", "reading this skill before it goes into "
                                  "your readvisor's head"),
        "pass": ("audited", "audited and clean"),
        "flag": ("flagged", "the audit wants a human to look at this"),
        "fail": ("failed", "the audit says don't"),
    }

    def _skill_rows(items: list[tuple[str, bool, str]]) -> str:
        rows: list[str] = []
        for name, enabled, tooltip in items:
            st = _skillaudit.skill_state(project_dir, name)
            state = st["state"]
            cls = "on" if enabled else "off"
            next_val = "0" if enabled else "1"
            tip = _escape_html(tooltip) if tooltip else ""
            title_attr = f' title="{tip}"' if tip else ""
            esc_name = _escape_html(name)
            js_name = json.dumps(name)[1:-1].replace("'", "\\'")
            auditing = state == "auditing"
            mark = ""
            if state != "trusted":
                label, why = _SKILL_MARKS.get(state, (state, ""))
                if st.get("override"):
                    label, why = "trusted by you", "you enabled this over the audit"
                extra = f" · {st['summary']}" if st.get("summary") else ""
                mark = (f'<span class="skill-mark m-{state}" '
                        f'title="{_escape_html(why + extra)}">{_escape_html(label)}</span>')
            rows.append(
                f'<li class="skill-row {cls} st-{state}" data-skill="{esc_name}"'
                f' data-audit-state="{state}"'
                f' data-audit-report="{_escape_html(st.get("report") or "")}"'
                f'{title_attr}>'
                f'  <button class="skill-toggle" '
                + ("disabled " if auditing else
                   f'hx-post="/api/skills/toggle" '
                   f'hx-vals=\'{{"name": "{esc_name}", "enabled": "{next_val}"}}\' '
                   f'hx-target="#skills-list" hx-swap="innerHTML" ')
                + f'>{"◐" if auditing else ("●" if enabled else "○")}</button>'
                f'  <span class="skill-name">{esc_name}</span>'
                f'  {mark}'
                f'</li>'
            )
            if state in ("flag", "fail") and not enabled:
                verb = "flagged" if state == "flag" else "failed"
                report = st.get("report") or ""
                read_btn = (
                    f'<button type="button" class="skill-link" '
                    f'onclick="skillOpenReport(\'{_escape_html(report)}\')">read report</button> · '
                ) if report else ""
                rows.append(
                    f'<li class="skill-note">audit {verb} this — {read_btn}'
                    f'<button type="button" class="skill-link" '
                    f'onclick="skillEnableAnyway(\'{js_name}\')">enable anyway</button></li>'
                )
        return "".join(rows)

    @router.get("/api/skills", response_class=HTMLResponse)
    async def api_skills() -> HTMLResponse:
        from ..skeleton import resync_globals
        resync_globals(project_dir)  # pick up globals added since launch
        items = list_skills(project_dir / "rness")
        if not items:
            return HTMLResponse('<div class="empty-note">no skills in rness/skills/</div>')
        return HTMLResponse('<ul class="skills">' + _skill_rows(items) + "</ul>")

    def _schedule_skill_audit(name: str) -> bool:
        """Run the first-use audit off the request path. Claims the slot
        synchronously so a double-click can't start two scans."""
        if not _skillaudit.try_claim(project_dir, name):
            return False
        loop = asyncio.get_running_loop()

        def _emit_sync(event: str, data: dict[str, Any]) -> None:
            asyncio.run_coroutine_threadsafe(session.emit(event, data), loop)

        async def _go() -> None:
            try:
                await asyncio.to_thread(
                    _skillaudit.audit_and_enable, project_dir, name,
                    emit=_emit_sync, llm_url=llm_url)
            finally:
                _skillaudit.release(project_dir, name)

        asyncio.create_task(_go())
        return True

    @router.post("/api/skills/toggle", response_class=HTMLResponse)
    async def api_skills_toggle(request: Request) -> HTMLResponse:
        form = await request.form()
        name = (form.get("name") or "").strip()
        enabled_raw = (form.get("enabled") or "").strip()
        if not name:
            raise HTTPException(400, "missing name")
        want_on = enabled_raw == "1"
        try:
            res = _skillaudit.set_skill_enabled_guarded(project_dir, name, want_on)
        except _skillaudit.SkillAuditRefused as refusal:
            # Blocked until reviewed. Answer 200 with the re-rendered list so
            # htmx swaps in the row carrying the refusal and its affordances
            # ("read report · enable anyway"); the structured payload also
            # goes out on the event stream for anything else listening.
            await session.emit("skill-audit", {
                "skill": name, "phase": "protocol", "status": refusal.verdict,
                "report": refusal.report, "summary": refusal.summary,
                "fingerprint": refusal.fingerprint, "enabled": False,
            })
            return await api_skills()  # type: ignore[return-value]
        if res.get("state") == "needs_audit":
            if _agent_free.enabled():
                # The first-use audit asks a model; the skill stays off.
                raise HTTPException(409, _agent_free.detail(
                    f"{name} needs its first-use audit, and the audit needs a model"))
            _schedule_skill_audit(name)
        return await api_skills()  # type: ignore[return-value]

    @router.post("/api/skills/{name}/trust")
    async def api_skills_trust(name: str) -> dict[str, Any]:
        """User override: record a pass verdict for the skill as it stands
        right now and enable it. The report path is preserved — overriding a
        finding doesn't erase it. Change the skill's files afterwards and the
        fingerprint moves, so the next toggle-on audits it again."""
        try:
            record = await asyncio.to_thread(_skillaudit.trust_override,
                                             project_dir, name)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e)) from None
        await session.emit("skill-audit", {
            "skill": name, "phase": "protocol", "status": "pass",
            "report": record.get("report"), "summary": record.get("summary") or "",
            "fingerprint": record.get("fingerprint"), "enabled": True,
        })
        return {"ok": True, "skill": name, "verdict": record}

    @router.get("/api/roles", response_class=HTMLResponse)
    async def api_roles() -> HTMLResponse:
        from ..skeleton import resync_globals
        resync_globals(project_dir)  # pick up globals added since launch
        items = list_roles(project_dir / "rness")
        if not items:
            return HTMLResponse(
                '<div class="empty-note">no readvisors in rness/readvisors/</div>')
        rows = []
        for name, enabled, tooltip in items:
            cls = "on" if enabled else "off"
            next_val = "0" if enabled else "1"
            tip = _escape_html(tooltip) if tooltip else ""
            title_attr = f' title="{tip}"' if tip else ""
            origin = _readvisor_origin(project_dir, name)
            esc = _escape_html(name)
            # The remove affordance carries no hx-* of its own: removing a
            # readvisor deletes files, so it goes through the frontend's
            # confirm overlay and only then POSTs /api/readvisors/remove.
            # A shipped readvisor has no button at all — the user didn't put
            # it there and can't be given a control that would fail.
            remove_btn = "" if origin == "shipped" else (
                f'  <button class="role-remove" data-name="{esc}" '
                f'data-origin="{origin}" title="remove">×</button>'
            )
            rows.append(
                f'<li class="role-row {cls}" data-name="{esc}" '
                f'data-origin="{origin}"{title_attr}>'
                f'  <button class="role-toggle" '
                f'    hx-post="/api/roles/toggle" '
                f'    hx-vals=\'{{"name": "{esc}", "enabled": "{next_val}"}}\' '
                f'    hx-target="#roles-list" hx-swap="innerHTML">'
                f'    {"●" if enabled else "○"}'
                f'  </button>'
                f'  <span class="role-name">{esc}</span>'
                f'{remove_btn}'
                f'</li>'
            )
        return HTMLResponse('<ul class="roles">' + "".join(rows) + "</ul>")

    @router.post("/api/roles/toggle", response_class=HTMLResponse)
    async def api_roles_toggle(request: Request) -> HTMLResponse:
        form = await request.form()
        name = (form.get("name") or "").strip()
        enabled_raw = (form.get("enabled") or "").strip()
        if not name:
            raise HTTPException(400, "missing name")
        set_role_enabled(project_dir / "rness", name, enabled_raw == "1")
        return await api_roles()  # type: ignore[return-value]

    @router.post("/api/readvisors/remove")
    async def api_readvisors_remove(request: Request) -> dict[str, Any]:
        """Delete a user-made readvisor. Body: `{"name": "..."}`.

        Three outcomes by origin: a `project` one deletes the real folder
        under `rness/readvisors/`; a `global` one deletes it from
        `~/enough/readvisors/` (and the link here goes with it); a `shipped`
        one is refused, because the user cannot put back what they did not
        install. The confirm step belongs to the UI — by the time a request
        reaches here the user has said yes."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "expected json body") from None
        name = str((body or {}).get("name") or "").strip()
        if not name or "/" in name or name.startswith("."):
            raise HTTPException(400, "bad name")
        origin = _readvisor_origin(project_dir, name)
        if origin == "shipped":
            raise HTTPException(
                403, "readvisors that ship with enough cannot be removed — "
                     "switch it off instead")

        from .. import prompt as _prompt
        from .. import skeleton as _skeleton
        local = _prompt._readvisors_dir(project_dir / "rness") / name
        if origin == "project":
            if not local.is_dir() or local.is_symlink():
                raise HTTPException(404, f"no readvisor named {name!r} here")
            await asyncio.to_thread(shutil.rmtree, local)
        else:  # global
            target = _skeleton.user_readvisors_root() / name
            if not target.is_dir():
                raise HTTPException(404, f"no readvisor named {name!r} here")
            await asyncio.to_thread(shutil.rmtree, target)
            # The project's link is now dangling; the populator prunes it.
            if local.is_symlink():
                try:
                    local.unlink()
                except OSError:
                    pass
        # Leave no orphan entry behind in `.disabled`, or a later readvisor
        # of the same name would arrive switched off for no visible reason.
        try:
            set_role_enabled(project_dir / "rness", name, True)
        except OSError:
            pass
        return {"ok": True, "name": name, "origin": origin}

    return router
