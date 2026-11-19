"""The allograph card's 0.8 pieces in the page (lane W4-RP; tracker `allograph-registry-0-8`): the holder's every
proof, and the look-up by name or tag.

- The proofs list reads `GET /api/allograph/proofs` (enough's route over Connect's holder-only
  `GET /api/v0/allographs/{tag}/proofs`) and posts nothing but `unprove`, and that only from the "yes, remove it" of
  the question its row asks; not the holder (409), nothing listed (404) and signed out are each said in words.
- The look-up reads `GET /api/allograph/entry?name=` and `?tag=` (no account), and opens one entry in place.
- Every string they draw is a `t()` key in all six catalogs, and the manual's 13.9 and the allograph bubble name the
  two in all six languages.

The routes and the client are held in tests/test_allograph_api.py and tests/test_allograph_registry.py; the screens
and the `allograph-proofs` scenario drive the page against the stand-in Connect (scripts/uicheck/connect.py).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HTML = (REPO / "enough" / "static" / "index.html").read_text(encoding="utf-8")
I18N = REPO / "enough" / "static" / "i18n"
LANGS = ("en", "fr", "es", "de", "zh", "ja")


def _fn(name: str) -> str:
    m = re.search(r"\n    (?:async )?function " + re.escape(name) + r"\(", HTML)
    assert m, name
    end = HTML.index("\n    }\n", m.end())
    return HTML[m.start():end]


def _act(name: str) -> str:
    """One `if (act === '<name>')` branch of `dlgAlloAct`."""
    body = _fn("dlgAlloAct")
    i = body.index(f"if (act === '{name}')")
    j = body.find("\n      if (act ", i + 10)
    return body[i:j if j > 0 else len(body)]


NEW_FUNCTIONS = ("dlgAlloHeldWanted", "dlgAlloHeldLoad", "dlgAlloHeldHTML", "dlgAlloLookHTML")


def test_the_proofs_list_reads_the_holder_route_and_removes_only_after_asking():
    load = _fn("dlgAlloHeldLoad")
    assert "canonJSON('/api/allograph/proofs?path='" in load
    assert "r.status === 409" in load and "allo.held.notHolder" in load
    assert "r.status === 404" in load and "allo.held.notListed" in load
    assert "dlgAlloErr(r)" in load                                # 401: the sign-in strip, as everywhere
    for name in NEW_FUNCTIONS:
        assert "canonPost" not in _fn(name), name
    html = _fn("dlgAlloHeldHTML")
    for field in ("p.faceplace", "p.handle", "p.address", "p.checked", "p.since", "p.state"):
        assert field in html, field
    assert "allo.held.signedOut" in html
    # remove… only asks; the yes sits in an alertdialog on the row; only the yes sends, and it sends unprove
    assert "canonPost" not in _act("allo-held-rm") and "canonPost" not in _act("allo-held-no")
    assert 'role="alertdialog"' in html and html.index("allo-held-yes") > html.index('role="alertdialog"')
    yes = _act("allo-held-yes")
    assert "canonPost('/api/allograph/unprove', { path, faceplace: String(p.faceplace), handle: String(p.handle) })" in yes
    assert "dlgAlloHeldLoad()" in yes
    # every post the panel makes from the list is that one
    posts = re.findall(r"canonPost\('([^']+)'", "".join(_act(a) for a in ("allo-held", "allo-held-rm", "allo-held-no",
                                                                        "allo-held-yes")))
    assert posts == ["/api/allograph/unprove"]
    # read once listed and signed in, a person's only; cleared on signing out
    assert "dlgAlloSubject() === 'person'" in _fn("dlgAlloHeldWanted")
    assert "held: null" in _act("allo-signout")


def test_the_look_up_asks_by_name_and_by_tag_and_opens_one():
    look = _act("allo-look")
    assert "canonJSON('/api/allograph/entry?tag='" in look and "canonJSON('/api/allograph/entry?name='" in look
    assert "canonPost" not in look
    assert "/^[a-z2-7]{12}$/" in look                                      # the registry's tag (TAG_RE)
    assert "/^[a-z](?:[.-]?[a-z0-9])*$/" in look                           # and its user name (NAME_RE)
    from enough import allograph_registry as R
    assert R.TAG_RE.pattern == "^[a-z2-7]{12}$" and R.NAME_RE.pattern == "^[a-z](?:[.-]?[a-z0-9])*$"
    html = _fn("dlgAlloLookHTML")
    assert "dlgAlloEntryHTML(e)" in html and "allo-look-open" in html
    assert "dlgAlloLookHTML()" in _fn("dlgAlloSearchHTML")
    # return in the field looks it up
    assert "e.target.id !== 'allo-look'" in HTML and "void dlgAlloAct('allo-look', b)" in HTML


def _keys(*names: str) -> set:
    out = set()
    for n in names:
        out |= set(re.findall(r"\bt\('([a-zA-Z0-9_.]+)'", _fn(n)))
    return out


@pytest.mark.parametrize("lang", LANGS)
def test_every_string_is_in_the_six_catalogs(lang):
    keys = _keys(*NEW_FUNCTIONS)
    keys |= {k for a in ("allo-held-yes", "allo-look") for k in re.findall(r"\bt\('([a-zA-Z.]+)'", _act(a))}
    assert {"allo.held.head", "allo.held.q", "allo.state.lapsed", "allo.look.head", "allo.look.bad"} <= keys
    cat = json.loads((I18N / lang / "ui.json").read_text(encoding="utf-8"))["strings"]
    missing = sorted(k for k in keys if not cat.get(k))
    assert not missing, missing
    if lang != "en":
        en = json.loads((I18N / "en" / "ui.json").read_text(encoding="utf-8"))["strings"]
        for k in ("allo.held.q", "allo.held.removeAria"):
            assert "{handle}" in cat[k] and "{faceplace}" in cat[k], (lang, k)
        same = [k for k in keys if k.startswith(("allo.held.", "allo.look.", "allo.state.")) and cat[k] == en[k]]
        assert not same, same


@pytest.mark.parametrize("lang", LANGS)
def test_the_manual_and_the_bubble_name_both(lang):
    cat = json.loads((I18N / lang / "ui.json").read_text(encoding="utf-8"))["strings"]
    hc = (REPO / "docs" / "HELP_CENTER.md") if lang == "en" else (I18N / lang / "help-center.md")
    hd = (REPO / "enough" / "static" / "help-docs.md") if lang == "en" else (I18N / lang / "help-docs.md")
    text = hc.read_text(encoding="utf-8")
    sec = text[text.index("### 13.9"):text.index("\n---\n", text.index("### 13.9"))]
    bubble = hd.read_text(encoding="utf-8").split("\n## allograph\n", 1)[1].split("\n## ", 1)[0]
    for key in ("allo.held.head", "allo.held.remove", "allo.look.head"):
        assert f"**{cat[key]}**" in sec, (lang, key)
        assert f"<strong>{cat[key]}</strong>" in bubble, (lang, key)
