"""`tools.fetch_and_cache` — the broker's fetch → convert → cache → index
pipeline, on the path where everything WORKS.

This exists because of a specific bug shape. The pipeline was extracted out
of `run_fetch_url` so the composure webframe could share it, and for a while
the extracted success path raised `NameError` in shipped builds — every
refusal test still passed, because a refusal returns before it reaches the
part that was broken. A function whose only tests are its denials is a
function with no tests.

No network: `httpx.Client` is replaced with one that returns a response we
built ourselves, so the allowlist routing, the size cap and the rest of the
real gating still run.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from enough import broker, convert, tools


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(broker, "CONFIG_PATH",
                        tmp_path / "broker-config" / "broker.json")
    proj = tmp_path / "project"
    (proj / "rness" / "io" / "input").mkdir(parents=True)
    return proj


def serve(monkeypatch: pytest.MonkeyPatch, body: bytes | str,
          content_type: str = "text/html; charset=utf-8",
          status: int = 200) -> dict:
    """Replace httpx.Client with one that answers every GET with `body`.
    Returns a dict the caller can inspect for what was requested."""
    seen: dict = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url):
            seen["url"] = url
            return httpx.Response(
                status, headers={"content-type": content_type},
                content=body.encode("utf-8") if isinstance(body, str) else body,
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(tools.httpx, "Client", FakeClient)
    return seen


HTML = (
    "<html><head><title>A Real Page</title></head>"
    "<body><h1>Heading</h1><p>Body text that survives conversion.</p></body>"
    "</html>"
)


def _index(project: Path) -> str:
    f = project / "rness" / "io" / "input" / "_broker-index.md"
    return f.read_text(encoding="utf-8") if f.is_file() else ""


def test_html_is_converted_cached_and_indexed(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    if not convert.pandoc_path():
        pytest.skip("pandoc unavailable in this environment")
    seen = serve(monkeypatch, HTML)

    got = tools.fetch_and_cache(project, "https://example.com/docs/the-page")

    assert seen["url"] == "https://example.com/docs/the-page"
    assert got.status == 200
    assert got.content_type == "text/html"
    assert got.title == "A Real Page"
    assert got.converted is True
    assert got.cache_ext == "md"

    cached = project / got.cache_rel
    assert cached.is_file(), got.cache_rel
    text = cached.read_text(encoding="utf-8")
    assert "Body text that survives conversion." in text
    assert "<p>" not in text, "it is markdown, not the html we fetched"

    # The filename carries the slug from the URL's last path segment, plus
    # the timestamp and short hash that make two fetches of one URL distinct.
    assert cached.name.endswith("-the-page.md")
    assert got.short_hash in cached.name

    index = _index(project)
    assert "https://example.com/docs/the-page" in index
    assert "A Real Page" in index
    assert got.cache_rel in index


def test_conversion_off_caches_the_html_and_writes_no_index_row(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = broker.load_config()
    cfg["fetch_url_cache_and_convert"] = False
    broker.save_config(cfg)
    serve(monkeypatch, HTML)

    got = tools.fetch_and_cache(project, "https://example.com/docs/the-page")

    assert got.converted is False
    assert got.cache_ext == "html"
    cached = project / got.cache_rel
    assert "<p>Body text that survives conversion.</p>" in cached.read_text()
    assert _index(project) == "", "the index row belongs to the convert toggle"


@pytest.mark.parametrize("ctype,ext", [
    ("text/plain", "txt"),
    ("text/markdown", "md"),
    ("application/json", "txt"),
])
def test_text_content_types_are_cached_verbatim(
        project: Path, monkeypatch: pytest.MonkeyPatch, ctype: str, ext: str):
    serve(monkeypatch, "raw body, unconverted", content_type=ctype)
    got = tools.fetch_and_cache(project, "https://example.com/feed/data")
    assert got.cache_ext == ext
    assert got.converted is False
    assert (project / got.cache_rel).read_text() == "raw body, unconverted"


def test_binary_content_is_cached_as_bytes(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    blob = b"\x89PNG\r\n\x1a\n\x00\x01\x02"
    serve(monkeypatch, blob, content_type="image/png")
    got = tools.fetch_and_cache(project, "https://example.com/img/logo.png")
    assert got.cache_ext == "bin"
    assert (project / got.cache_rel).read_bytes() == blob
    assert got.raw_bytes == len(blob)


def test_slug_falls_back_to_the_host_for_a_bare_url(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    serve(monkeypatch, "hi", content_type="text/plain")
    got = tools.fetch_and_cache(project, "https://example.com/")
    assert got.host == "example.com"
    assert Path(got.cache_rel).name.endswith("-example-com.txt")


def test_the_cache_name_is_derived_from_url_plus_timestamp(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    """Pinning today's behavior, including its one sharp edge.

    The name is `<YYYY-MM-DD-HHMM>-<hash of url+timestamp>-<slug>.<ext>`,
    and the timestamp that feeds the hash has second granularity. So two
    fetches of the SAME url in the same second land on the same file — the
    second overwrites the first and the index gains a second row pointing at
    it. Harmless (the content is the same page, seconds apart) but real;
    recorded here so a change to it is a deliberate one."""
    serve(monkeypatch, "hi", content_type="text/plain")
    a = tools.fetch_and_cache(project, "https://example.com/p/same")
    b = tools.fetch_and_cache(project, "https://example.com/p/other")
    assert a.cache_rel != b.cache_rel, "different urls never collide"
    assert (project / a.cache_rel).is_file() and (project / b.cache_rel).is_file()
    assert Path(a.cache_rel).name.endswith("-same.txt")
    assert Path(b.cache_rel).name.endswith("-other.txt")


def test_off_allowlist_hosts_are_routed_through_tor(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    seen = serve(monkeypatch, "hi", content_type="text/plain")
    got = tools.fetch_and_cache(project, "https://example.com/p/x")
    assert got.used_tor is True
    assert "proxy" in seen["client_kwargs"]


def test_run_fetch_url_renders_the_success_path(
        project: Path, monkeypatch: pytest.MonkeyPatch):
    """The regression that started this file: the tool runner's own success
    path, end to end."""
    serve(monkeypatch, "the whole body", content_type="text/plain")
    call = tools.ToolCall(name="fetch_url", path=None, content=None,
                          command=None, url="https://example.com/p/thing",
                          extra={}, raw="", span=(0, 0))
    res = tools.run_fetch_url(project, call)
    assert res.ok, res.body
    assert "the whole body" in res.body
    assert "rness/io/input/" in res.body
