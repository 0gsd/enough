"""The Allograph Registry's routes for the page (Ascribe, https://ascribe.cosmoes.org/, sections 4.2 and 14.6 to 14.13):
Connect's sign-in, a holograph's subject, and everything about a listing after its allograph is made.

An allograph is made by `POST /api/ascribe/allograph` (`enough/dialectic_api.py`): the holder's program, `project h
as allograph`, the release recorded, the document written beside the holograph and given to the page as a preview.
Nothing is sent then. Everything here that sends is the holder's own act, one click each, through
`enough/allograph_registry.py`:

- **Connect** (`/api/connect/status|sign-in|poll|sign-out`): the device flow; the token in the keychain.
- **The subject** (`POST /api/ascribe/subject`): `person` (the default) or `character`, which makes an agent's
  allograph.
- **The listing** (`/api/allograph/...`): `listing` (what this machine knows, the tag, and whether the holograph has
  changed since the listed allograph's run; never asks the registry), `list`, `withdraw`, `proof` (the string to post
  and the addresses the faceplace accepts), `prove`, `unprove`, `waiting`, `accept`, `remove`, `attest`, `bond`,
  `unbond`; and the look-ups `search`, `entry`, `faceplaces`, which need no account (14.11).

Every route that sends a statement, or reads what only the listing's account may (`waiting`), refuses with 401 and
plain words when this machine is not signed in to Connect. A refusal of the registry's is said in its words with its
status (a 5xx, or Connect out of reach, as 502). `path` is the holograph, as the dialectic's routes name it.
"""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request

from . import allograph_registry as R


def _ascribe():
    from . import ascribe
    return ascribe


def _http(e: Exception) -> HTTPException:
    if isinstance(e, R.RegistryError):
        status = e.status if isinstance(e.status, int) and 400 <= e.status < 500 else (502 if e.status else 400)
        if e.code == "unreachable":
            status = 502
        return HTTPException(status, str(e))
    status = getattr(e, "status", None)
    return HTTPException(status if isinstance(status, int) else 400, str(e))


def build_router(*, project_dir: Path, jobs: Any = None, catalog_after: Callable[[str], None] | None = None
                 ) -> APIRouter:
    router = APIRouter()
    project_dir = Path(project_dir)

    async def body_of(request: Request) -> dict:
        try:
            body = await request.json()
        except ValueError:
            body = None
        return body if isinstance(body, dict) else {}

    async def run(fn: Callable[[], Any]) -> Any:
        try:
            return await asyncio.to_thread(fn)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 - a refusal of any of ours is said in its words
            from . import ascribe as a
            if isinstance(e, (R.RegistryError, a.AscribeError)) or isinstance(getattr(e, "status", None), int):
                raise _http(e) from None
            raise

    def holograph(rel: Any) -> Any:
        from .dialectic_api import DialecticRouteError, target
        t = target(project_dir, str(rel or ""))
        if not t.holograph:
            raise DialecticRouteError(f"{t.rel} is not a holograph; a listing is a holograph's")
        return t

    def signed_in() -> R.Session:
        sess = R.session()
        if sess is None:
            raise R.RegistryError("not signed in to Connect: the Allograph Registry takes a statement only from a "
                                  "signed-in account; sign in first", 401, "signed_out")
        return sess

    def key_of(t: Any, *, create: bool = False) -> R.ListingKey:
        key = R.listing_key(R.hid_of(t.path), create=create)
        if key is None:
            raise R.RegistryError("this holograph has no listing key yet: list its allograph first", 409)
        return key

    def person_only(t: Any, what: str) -> None:
        if _ascribe().subject_of(t.path) == "character":
            raise R.RegistryError(f"an agent's listing does not {what} (Ascribe 14.9, 14.10)", 403, "not_allowed")

    # ---------- Connect ----------

    @router.get("/api/connect/status")
    async def connect_status() -> dict:
        def go() -> dict:
            url = R.connect_url()
            sess = R.session(url)
            return {"url": url, "signed_in": sess is not None, "account": sess.account if sess else None}
        return await run(go)

    @router.post("/api/connect/sign-in")
    async def connect_sign_in() -> dict:
        """Begin the device flow: `{user_code, verification_uri, verification_uri_complete, interval, expires_in}`."""
        return await run(lambda: R.start_sign_in())

    @router.post("/api/connect/poll")
    async def connect_poll() -> dict:
        """`{state: pending, interval}` until the person approves the code; then `{state: signed_in, account}`."""
        return await run(lambda: R.poll_sign_in())

    @router.post("/api/connect/sign-out")
    async def connect_sign_out() -> dict:
        return await run(lambda: {"signed_out": R.sign_out()})

    # ---------- The subject (Ascribe 4.2) ----------

    @router.post("/api/ascribe/subject")
    async def ascribe_subject(request: Request) -> dict:
        """`{path, subject: person | character}` → `{path, subject, kind}`: the catalog's subject written (person as
        its absence), every other byte of the catalog kept."""
        body = await body_of(request)

        def go() -> dict:
            a = _ascribe()
            t = holograph(body.get("path"))
            subject = str(body.get("subject") or "")

            def write() -> str:
                return a.set_subject(t.path, subject)
            if jobs is not None:
                with jobs.holding(t.key, t.rel):
                    got = write()
            else:
                got = write()
            if catalog_after is not None:
                catalog_after(t.rel)
            return {"path": t.rel, "subject": got, "kind": a.SUBJECT_KIND[got]}
        return await run(go)

    # ---------- The listing ----------

    @router.get("/api/allograph/listing")
    async def allograph_listing(path: str = "") -> dict:
        """What this machine knows of the holograph's listing (`listing_status`), with `signed_in` and the registry's
        address. Asks the registry nothing."""
        def go() -> dict:
            t = holograph(path)
            out = R.listing_status(t.path)
            out.update(path=t.rel, signed_in=R.session() is not None, connect=R.connect_url())
            return out
        return await run(go)

    @router.post("/api/allograph/list")
    async def allograph_list(request: Request) -> dict:
        """`{path, allograph, name, dangler?, show?, owner?}`: the allograph file `project h as allograph` wrote,
        listed under the holograph's listing key (made and kept in the keychain the first time). Refused when not
        signed in, when the file is no allograph this holograph released, or when its kind is not the holograph's.
        Returns `{listing, entry}`: what this machine now keeps, and the entry as the registry shows it."""
        body = await body_of(request)

        def go() -> dict:
            a = _ascribe()
            from . import canon_tools
            t = holograph(body.get("path"))
            sess = signed_in()
            rel = canon_tools.tidy_rel(str(body.get("allograph") or ""))
            if not rel:
                raise R.RegistryError("name the allograph to list: the file its run wrote beside the holograph")
            p = canon_tools.resolve(project_dir, rel)
            if p.is_symlink() or p.parent.resolve() != t.path.parent.resolve():
                raise R.RegistryError("the allograph to list is the file its run wrote beside the holograph")
            doc, data = R.load_allograph(p)
            R.released_allograph(t.path, data)
            want = a.SUBJECT_KIND[a.subject_of(t.path)]
            if doc.get("kind") != want:
                raise R.RegistryError(f"this allograph is a {doc.get('kind')}'s and the holograph is now a {want}'s: "
                                      "make it again")
            hid = R.hid_of(t.path)
            key = R.listing_key(hid, create=True)
            show = body.get("show")
            dangler = body.get("dangler")
            got = R.list_allograph(sess, key, name=str(body.get("name") or ""), allograph=doc,
                                   dangler=str(dangler) if dangler not in (None, "") else None,
                                   owner=str(body["owner"]) if body.get("owner") else None,
                                   show=show if isinstance(show, dict) else None)
            rec = {"registry": sess.url, "tag": key.tag, "name": str(body.get("name")),
                   "dangler": str(dangler) if dangler not in (None, "") else None, "kind": doc.get("kind"),
                   "allograph": rel, "run": doc.get("run"), "sha256": hashlib.sha256(data).hexdigest(),
                   "holograph": R.run_state(str(doc.get("run")))}
            R.record_listing(hid, rec)
            out = R.listing_status(t.path)
            out.update(path=t.rel)
            return {"listing": out, "entry": (got or {}).get("entry") if isinstance(got, dict) else None}
        return await run(go)

    @router.post("/api/allograph/withdraw")
    async def allograph_withdraw(request: Request) -> dict:
        """`{path}`: the listing withdrawn by a `withdraw` statement under its key, or, with no key on this machine,
        by the account its tag is tied to; what this machine kept of it forgotten. The key stays in the keychain, so
        listing again keeps the tag."""
        body = await body_of(request)

        def go() -> dict:
            t = holograph(body.get("path"))
            sess = signed_in()
            hid = R.hid_of(t.path)
            key = R.listing_key(hid)
            rec = R.listing_record(hid)
            if key is not None:
                R.withdraw(sess, key)
                tag = key.tag
            elif rec and rec.get("tag"):
                R.withdraw_by_account(sess, rec["tag"])
                tag = rec["tag"]
            else:
                raise R.RegistryError("nothing of this holograph is listed from this machine", 409)
            R.forget_listing(hid)
            return {"path": t.rel, "withdrawn": True, "tag": tag}
        return await run(go)

    @router.post("/api/allograph/proof")
    async def allograph_proof(request: Request) -> dict:
        """`{path, faceplace, handle}` → `{proof, faceplace, handle, addresses}`: the exact string to post in a public
        place of the account, and the addresses the faceplace's entry accepts for the handle (`{any}` for the holder
        to fill). Needs the listing's tag; asks the registry only for its list of faceplaces, which needs no
        account."""
        body = await body_of(request)

        def go() -> dict:
            t = holograph(body.get("path"))
            person_only(t, "take faceplace proofs")
            key = key_of(t)
            fp = str(body.get("faceplace") or "")
            handle = R.normal_handle(body.get("handle"))
            entry = next((f for f in R.faceplaces(R.connect_url()) if isinstance(f, dict)
                          and f.get("faceplace") == fp), None)
            if entry is None:
                raise R.RegistryError(R.PLAIN["unknown_faceplace"], 400, "unknown_faceplace")
            return {"proof": R.proof_string(key.tag, fp, handle), "faceplace": entry, "handle": handle,
                    "addresses": R.addresses_for(entry, handle)}
        return await run(go)

    @router.post("/api/allograph/prove")
    async def allograph_prove(request: Request) -> dict:
        """`{path, faceplace, handle, address}`: ask the registry to read the address for the proof string."""
        body = await body_of(request)

        def go() -> dict:
            t = holograph(body.get("path"))
            person_only(t, "take faceplace proofs")
            sess = signed_in()
            return R.prove(sess, key_of(t), str(body.get("faceplace") or ""), str(body.get("handle") or ""),
                           str(body.get("address") or ""))
        return await run(go)

    @router.post("/api/allograph/unprove")
    async def allograph_unprove(request: Request) -> dict:
        body = await body_of(request)

        def go() -> dict:
            t = holograph(body.get("path"))
            sess = signed_in()
            return R.unprove(sess, key_of(t), str(body.get("faceplace") or ""), str(body.get("handle") or ""))
        return await run(go)

    @router.get("/api/allograph/waiting")
    async def allograph_waiting(path: str = "") -> dict:
        """The attestations waiting for the holder's word, each with its `digest` beside it (what `accept` and
        `remove` name)."""
        def go() -> dict:
            t = holograph(path)
            sess = signed_in()
            rows = R.waiting(sess, key_of(t).tag)
            for r in rows:
                if isinstance(r, dict) and isinstance(r.get("statement"), dict) and "attestation" not in r:
                    r["attestation"] = R.attestation_digest(r["statement"])
            return {"path": t.rel, "attestations": rows}
        return await run(go)

    def _digest_route(says: str) -> Callable:
        async def handler(request: Request) -> dict:
            body = await body_of(request)

            def go() -> dict:
                t = holograph(body.get("path"))
                sess = signed_in()
                fn = R.accept if says == "accept" else R.remove
                return fn(sess, key_of(t), str(body.get("attestation") or ""))
            return await run(go)
        return handler

    router.add_api_route("/api/allograph/accept", _digest_route("accept"), methods=["POST"])
    router.add_api_route("/api/allograph/remove", _digest_route("remove"), methods=["POST"])

    @router.post("/api/allograph/attest")
    async def allograph_attest(request: Request) -> dict:
        """`{path, of, as, claims, epoch, named}`: this holograph's listing attests work the listing `of` did for or
        with its holder. An agent never attests."""
        body = await body_of(request)

        def go() -> dict:
            t = holograph(body.get("path"))
            person_only(t, "attest")
            sess = signed_in()
            claims = body.get("claims")
            return R.attest(sess, key_of(t), of=str(body.get("of") or ""), as_=str(body.get("as") or ""),
                            claims=claims if isinstance(claims, list) else [], epoch=str(body.get("epoch") or ""),
                            named=bool(body.get("named")))
        return await run(go)

    def _bond_route(says: str) -> Callable:
        async def handler(request: Request) -> dict:
            body = await body_of(request)

            def go() -> dict:
                t = holograph(body.get("path"))
                person_only(t, "own an agent")
                sess = signed_in()
                fn = R.bond if says == "bond" else R.unbond
                return fn(sess, key_of(t), str(body.get("agent") or ""))
            return await run(go)
        return handler

    router.add_api_route("/api/allograph/bond", _bond_route("bond"), methods=["POST"])
    router.add_api_route("/api/allograph/unbond", _bond_route("unbond"), methods=["POST"])

    # ---------- Look-ups (14.11): no account needed ----------

    @router.post("/api/allograph/search")
    async def allograph_search(request: Request) -> dict:
        """`{needs: [{about, value}], kind?, plus?, attested?, next?}` → `{entries, next}`."""
        body = await body_of(request)

        def go() -> dict:
            needs = body.get("needs")
            return R.search(R.connect_url(), needs if isinstance(needs, list) else [],
                            kind=body.get("kind") or None,
                            plus=True if body.get("plus") is True else None,
                            attested=True if body.get("attested") is True else None,
                            next=str(body["next"]) if body.get("next") else None)
        return await run(go)

    @router.get("/api/allograph/entry")
    async def allograph_entry(tag: str = "", name: str = "") -> dict:
        """`?tag=` → `{entry}` (null when nothing is listed under it), `?name=` → `{entries}`; each entry's `signed`
        checked here (`verified`)."""
        def go() -> dict:
            base = R.connect_url()
            if tag:
                e = R.entry(base, tag)
                if isinstance(e, dict):
                    e = {**e, "verified": R.verify(e.get("signed"))}
                return {"entry": e}
            return {"entries": [{**e, "verified": R.verify(e.get("signed"))} if isinstance(e, dict) else e
                                for e in R.by_name(base, name)]}
        return await run(go)

    @router.get("/api/allograph/faceplaces")
    async def allograph_faceplaces() -> dict:
        return await run(lambda: {"faceplaces": R.faceplaces(R.connect_url())})

    return router


__all__ = ["build_router"]
