"""cosmoes_client.py: the one sync client for the OES specifications published at cosmoes.org.

THE CANONICAL COPY of this file is cosmoes-site `client/cosmoes_client.py` (github.com/0gsd/cosmoes-site). The
applications that read the specifications (enough, Comprise, comprise-connect) vendor it as ONE file, unchanged, and
record beside their copy the cosmoes-site commit they took it from. A fix is made here and taken again; never fork it
in an app. Standard library only, Python 3.11+. It never prints (the command line at the bottom is the exception, by
design); it logs under the logger "cosmoes": INFO for an update, WARNING for an error, DEBUG otherwise.

The contract, in short
----------------------
    GET https://cosmoes.org/manifest.json
        format "docoes-export/1": a `documents` list; each document has `slug`, `name`, `version` (an `edition`,
        when present, is the version), `host` (macro.cosmoes.org, …; a document without a host is skipped: nothing is
        derived), `revised`, `source` {path, sha256}, `files` {short|atem|fabula: {path, sha256, bytes}} and `raw`
        {source, short, atem, fabula: a root-absolute path on the host; when absent, exactly DEFAULT_RAW below}.
    GET https://<host>/raw/source.md                   the markdown the fragments were built from
    GET https://<host>/raw/{short,atem,fabula}.html    the three DocOES fragments (<article class="docoes …">)

Only hosts equal to cosmoes.org or ending in .cosmoes.org are ever fetched, over HTTPS with certificates verified,
whatever a manifest says; a host outside that is an error for its document. The one allowance is a `base` of
http://127.0.0.1… or http://localhost… (the apps' tests and scratch rigs), under which loopback hosts are fetched over
HTTP too. One manifest request per sync (If-None-Match with the ETag kept in state.json; a 304 means the local
manifest stands). The timeout is per request; `max_bytes` is enforced while reading; a redirect is followed only to the
same scheme and host. Every body is checked against the manifest's sha256; a mismatch, a short or oversize read, a
redirect off-host or a failed validation rejects that file and the previous local copy is kept. A document's kinds are
written only when every wanted kind of it fetched and validated; each file is written whole (temporary file and
os.replace); state.json is written last. Nothing is raised to the caller of `sync` for a network or content fault:
it all lands in the Report.

The folder (`sync(folder, wants)`)
---------------------------------
    <folder>/<slug>/source.md, short.html, atem.html, fabula.html   as fetched, only the kinds wanted
    <folder>/manifest.json                                           the last manifest fetched, verbatim
    <folder>/state.json                                              {"checked": iso, "updated": iso|null, "etag":
                                                                     str|null, "documents": {slug: {"name", "version",
                                                                     "revised", "host", "kinds": {kind: {"sha256",
                                                                     "fetched"}}}}}
A consumer reads a document's name and version from state.json, never from the files.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import hashlib
import http.client
import json
import logging
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Callable

__all__ = ['CosmoesClient', 'Fetch', 'Report', 'ClientError', 'basic_validate', 'unsafe', 'load_state', 'main',
           'DOMAIN', 'FORMAT', 'KINDS', 'FRAGMENTS', 'DEFAULT_RAW', 'FILENAMES', 'VERSION']

VERSION = '1'                                        # the client's own, named in the User-Agent
DOMAIN = 'cosmoes.org'
FORMAT = 'docoes-export/1'
KINDS = ('source', 'short', 'atem', 'fabula')
FRAGMENTS = ('short', 'atem', 'fabula')
DEFAULT_RAW = {'source': '/raw/source.md', 'short': '/raw/short.html', 'atem': '/raw/atem.html',
               'fabula': '/raw/fabula.html'}
FILENAMES = {'source': 'source.md', 'short': 'short.html', 'atem': 'atem.html', 'fabula': 'fabula.html'}
LOOPBACK = ('127.0.0.1', 'localhost')
ALL = '*'                                            # in `wants`: every document the manifest lists
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
PATH_RE = re.compile(r'^/(?!/)[A-Za-z0-9._~%/-]*$')  # a root-absolute path: no scheme, no host, no query
CHUNK = 65536

log = logging.getLogger('cosmoes')


class ClientError(Exception):
    """A network or content fault: what `manifest()` and `fetch()` raise, and what `sync()` turns into Report.errors."""


@dataclasses.dataclass(frozen=True)
class Fetch:
    """One wanted file: where it is, what it must hash to, whether the local copy already matches. `error` is set
    when the manifest's entry cannot be fetched at all (no sha256, a refused host, an unknown kind); such a Fetch is
    reported, never fetched."""
    slug: str
    kind: str
    url: str
    sha256: str
    current: bool
    size: int | None = None
    error: str | None = None


@dataclasses.dataclass
class Report:
    """What one `sync` did. Every wanted (slug, kind) lands in exactly one of `updated`, `unchanged`, `skipped` or
    `errors`; `checked` is True when a manifest was obtained (fetched and well-formed, or confirmed by a 304)."""
    checked: bool = False
    updated: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    unchanged: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    skipped: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    errors: list[tuple[str, str, str]] = dataclasses.field(default_factory=list)
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return self.checked and not self.errors

    def lines(self) -> list[str]:
        def pairs(items):
            return ', '.join(f'{s} {k}' for s, k in items) if items else '-'
        return [f'checked: {"yes" if self.checked else "no"}',
                f'updated: {len(self.updated)} {pairs(self.updated)}',
                f'unchanged: {len(self.unchanged)} {pairs(self.unchanged)}',
                f'skipped: {len(self.skipped)} {pairs(self.skipped)}',
                f'errors: {len(self.errors)}'] + [f'  {s} {k}: {m}' for s, k, m in self.errors] + [
                f'elapsed: {self.elapsed:.2f} s']


# ----------------------------------------------------------------------------------------------------- validation

# Copied from cosmoes-site's cosmoes/specs.py (`_Unsafe`, `unsafe`); the apps' loaders carry the same list. Kept in
# step by hand: this file imports nothing of the site.
BANNED_TEXT = ('<script', '<style')                 # anywhere, in any case
BANNED_TAGS = frozenset({'script', 'style', 'iframe', 'frame', 'object', 'embed', 'base', 'link', 'meta', 'form'})
URL_ATTRS = frozenset({'href', 'src', 'action', 'formaction', 'xlink:href'})


class _Unsafe(HTMLParser):
    """What in a fragment a loader would not include as it is: a tag that loads, runs or submits, a style or on…
    attribute, a javascript: address. Attribute names come lower-cased and values unescaped from the parser."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in BANNED_TAGS:
            self.found.append(f'<{tag}>')
        for name, value in attrs:
            if name == 'style' or re.fullmatch(r'on[a-z]+', name):
                self.found.append(f'{name}= on <{tag}>')
            elif name in URL_ATTRS and re.sub(r'[\s\x00-\x1f]+', '', value or '').lower().startswith(('javascript:', 'vbscript:')):
                self.found.append(f'a script address in {name}= on <{tag}>')


def unsafe(html: str) -> list[str]:
    """Why `html` cannot be included as it is: an empty list when it can."""
    low = html.lower()
    found = [t for t in BANNED_TEXT if t in low]
    p = _Unsafe()
    p.feed(html)
    p.close()
    return found + p.found


def basic_validate(slug: str, kind: str, data: bytes) -> str | None:
    """The built-in validation hook: None when `data` passes, else why not. Markdown (`source`) must be UTF-8 and not
    empty; a fragment must be UTF-8, contain `<article`, and carry nothing a loader refuses (see `unsafe`). The apps
    pass their own hook to `sync` when they can do better (enough builds the markdown; Comprise and Connect run the
    check their loaders already have)."""
    if not isinstance(data, (bytes, bytearray)):
        return 'not bytes'
    try:
        text = bytes(data).decode('utf-8')
    except UnicodeDecodeError as e:
        return f'not UTF-8 ({e.reason} at byte {e.start})'
    if kind == 'source':
        return None if text.strip() else 'empty markdown'
    if kind not in FRAGMENTS:
        return f'unknown kind {kind!r}'
    if '<article' not in text.lower():
        return 'no <article in the fragment'
    found = unsafe(text)
    if found:
        return 'unsafe: ' + ', '.join(found[:4]) + (f' (+{len(found) - 4})' if len(found) > 4 else '')
    return None


# ----------------------------------------------------------------------------------------------------- helpers

def _iso(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _hostname(netloc: str) -> tuple[str, int | None]:
    """('thym.cosmoes.org', None) or ('127.0.0.1', 8791) from a netloc; ('', None) when it cannot be read."""
    try:
        parts = urllib.parse.urlsplit('//' + netloc)
        return (parts.hostname or '').lower(), parts.port
    except ValueError:
        return '', None


def _is_cosmoes(hostname: str) -> bool:
    return hostname == DOMAIN or hostname.endswith('.' + DOMAIN)


def _check_base(base: str) -> tuple[str, bool]:
    """The base without a trailing slash and whether it is a loopback rig; ValueError for anything else, since a wrong
    base is a programming error, not a network fault."""
    parts = urllib.parse.urlsplit(str(base).strip())
    hostname, _ = _hostname(parts.netloc)
    if parts.path not in ('', '/') or parts.query or parts.fragment:
        raise ValueError(f'base must be an origin, not {base!r}')
    if parts.scheme == 'https' and _is_cosmoes(hostname) and _hostname(parts.netloc)[1] is None:
        return f'https://{parts.netloc}', False
    if parts.scheme == 'http' and hostname in LOOPBACK:
        return f'http://{parts.netloc}', True
    raise ValueError(f'base must be https://{DOMAIN} (or a .{DOMAIN} host), or http://127.0.0.1… / http://localhost… '
                     f'for a scratch rig; not {base!r}')


def _describe(e: BaseException) -> str:
    if isinstance(e, urllib.error.URLError) and not isinstance(e, urllib.error.HTTPError):
        r = e.reason
        return _describe(r) if isinstance(r, BaseException) else str(r)
    if isinstance(e, TimeoutError):
        return 'timed out'
    return str(e) or type(e).__name__


def _atomic_write(path: str, data: bytes) -> None:
    """Write `data` whole: a temporary file beside `path`, fsync, os.replace. Never a partial file at `path`."""
    folder = os.path.dirname(path) or '.'
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.', suffix='.tmp', dir=folder)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_file(path: str) -> bytes | None:
    try:
        with open(path, 'rb') as f:
            return f.read()
    except OSError:
        return None


def _parse_manifest(body: bytes) -> dict:
    """The manifest as a dict, checked for shape; ClientError when it is not one."""
    try:
        m = json.loads(body)
    except (ValueError, UnicodeDecodeError) as e:
        raise ClientError(f'manifest: not JSON ({_describe(e)[:80]})') from None
    if not isinstance(m, dict):
        raise ClientError('manifest: not an object')
    if m.get('format') != FORMAT:
        raise ClientError(f'manifest: format {m.get("format")!r}, not {FORMAT!r}')
    if not isinstance(m.get('documents'), list):
        raise ClientError('manifest: no documents list')
    return m


def _empty_state() -> dict:
    return {'checked': None, 'updated': None, 'etag': None, 'documents': {}}


def load_state(folder: str | os.PathLike) -> dict:
    """<folder>/state.json as a dict with at least the keys of `_empty_state`; an empty state when the file is missing
    or unreadable (which only means everything is fetched again)."""
    state = _empty_state()
    path = os.path.join(os.fspath(folder), 'state.json')
    try:
        with open(path, 'rb') as f:
            got = json.load(f)
    except FileNotFoundError:
        return state
    except (OSError, ValueError) as e:
        log.warning('cosmoes: state.json unreadable, starting over: %s', _describe(e))
        return state
    if isinstance(got, dict) and isinstance(got.get('documents'), dict):
        state.update(got)
        if not isinstance(state.get('etag'), str):
            state['etag'] = None
    else:
        log.warning('cosmoes: state.json has the wrong shape, starting over')
    return state


def _load_local_manifest(folder: str) -> dict | None:
    try:
        with open(os.path.join(folder, 'manifest.json'), 'rb') as f:
            return _parse_manifest(f.read())
    except (OSError, ClientError):
        return None


def _targets(manifest: dict, wants: dict) -> dict[str, list[str]]:
    """{slug: kinds} for the wants, with ALL expanded against the manifest; explicit slugs win over ALL."""
    def kinds_of(v) -> list[str]:
        if isinstance(v, str):
            v = [v]
        out: list[str] = []
        for k in v or ():
            if isinstance(k, str) and k not in out:
                out.append(k)
        return out
    out: dict[str, list[str]] = {}
    if ALL in wants:
        for d in manifest.get('documents') or ():
            if isinstance(d, dict) and isinstance(d.get('slug'), str):
                out[d['slug']] = kinds_of(wants[ALL])
    for slug, v in wants.items():
        if slug != ALL and isinstance(slug, str):
            out[slug] = kinds_of(v)
    return out


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to the same scheme and host (netloc); anything else is a ClientError."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if (new.scheme, new.netloc.lower()) != (old.scheme, old.netloc.lower()):
            try:
                fp.close()
            except Exception:
                pass
            raise ClientError(f'redirect off-host refused ({code} to {new.netloc or newurl!r})')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# ----------------------------------------------------------------------------------------------------- the client

class CosmoesClient:
    """The sync client. `opener` is anything with `.open(request, timeout=…)` returning a response (status, headers,
    read(n), context manager): urllib's by default, a fake in the apps' tests. `clock` is `time.time` by default."""

    def __init__(self, base: str = f'https://{DOMAIN}', timeout: float = 3.0, max_bytes: int = 5_000_000,
                 user_agent: str = f'cosmoes-client/{VERSION} (unnamed app)', opener=None,
                 clock: Callable[[], float] | None = None):
        self.base, self.loopback = _check_base(base)
        self.timeout = float(timeout)
        self.max_bytes = int(max_bytes)
        self.user_agent = str(user_agent)
        self.opener = opener if opener is not None else urllib.request.build_opener(_SameHostRedirects())
        self.clock = clock if clock is not None else time.time

    # -- hosts and addresses

    def scheme_for(self, host: str) -> str | None:
        """'https' for a cosmoes.org host, 'http' for a loopback host under a loopback base, None when refused."""
        hostname, port = _hostname(str(host).strip())
        if not hostname:
            return None
        if _is_cosmoes(hostname) and port is None:
            return 'https'
        if self.loopback and hostname in LOOPBACK:
            return 'http'
        return None

    def _check_url(self, url: str) -> None:
        parts = urllib.parse.urlsplit(url)
        expected = self.scheme_for(parts.netloc)
        if expected is None or parts.scheme != expected:
            raise ClientError(f'address refused: {url!r} is not on {DOMAIN}')

    # -- requests

    def _get(self, url: str, what: str, headers: dict | None = None):
        """(status, body, headers) for a GET of `url`; the body capped at max_bytes while reading. A 304 is returned
        (with an empty body) only when If-None-Match was sent; everything else that is not a 200 is a ClientError."""
        hdrs = {'User-Agent': self.user_agent}
        hdrs.update(headers or {})
        req = urllib.request.Request(url, headers=hdrs, method='GET')
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                status = getattr(resp, 'status', None) or resp.getcode()
                body = self._read(resp, what)
                return status, body, resp.headers
        except urllib.error.HTTPError as e:
            if e.code == 304 and 'If-None-Match' in hdrs:
                return 304, b'', e.headers
            raise ClientError(f'{what}: HTTP {e.code}') from None
        except ClientError:
            raise
        except (OSError, http.client.HTTPException) as e:          # URLError, timeouts, resets, incomplete reads
            raise ClientError(f'{what}: {_describe(e)}') from None

    def _read(self, resp, what: str) -> bytes:
        declared = (resp.headers.get('Content-Length') or '').strip()
        if declared.isdigit() and int(declared) > self.max_bytes:
            raise ClientError(f'{what}: {declared} bytes declared, over the cap of {self.max_bytes}')
        buf = bytearray()
        while True:
            chunk = resp.read(min(CHUNK, self.max_bytes + 1 - len(buf)))
            if not chunk:
                return bytes(buf)
            buf += chunk
            if len(buf) > self.max_bytes:
                raise ClientError(f'{what}: over the cap of {self.max_bytes} bytes, reading stopped')

    def manifest(self) -> dict:
        """GET base/manifest.json, checked for shape. Raises ClientError."""
        status, body, _ = self._get(self.base + '/manifest.json', 'manifest')
        if status != 200:
            raise ClientError(f'manifest: HTTP {status}')
        return _parse_manifest(body)

    # -- planning

    def plan(self, state: dict, manifest: dict, wants: dict[str, list[str]]) -> list[Fetch]:
        """One Fetch per wanted (slug, kind) the manifest can name: its address on the document's host, the expected
        sha256, and whether `state` already holds that sha256. A wanted document the manifest lacks, a host outside
        the allowance, a missing sha256 or an unknown kind come back as Fetches with `error` set. A document without a
        host is skipped: no Fetch for it at all."""
        docs: dict[str, dict] = {}
        for d in manifest.get('documents') or ():
            if isinstance(d, dict) and isinstance(d.get('slug'), str):
                docs.setdefault(d['slug'], d)
        held = (state or {}).get('documents') or {}
        out: list[Fetch] = []
        for slug, kinds in _targets(manifest, wants).items():
            def err(kind: str, message: str) -> None:
                out.append(Fetch(slug, kind, '', '', False, error=message))
            doc = docs.get(slug)
            if doc is None:
                for k in kinds:
                    err(k, 'not in the manifest')
                continue
            if not SLUG_RE.match(slug):
                for k in kinds:
                    err(k, f'slug refused: {slug!r}')
                continue
            host = doc.get('host')
            if host is None:
                log.debug('cosmoes: %s has no host in the manifest, skipped', slug)
                continue
            scheme = self.scheme_for(host) if isinstance(host, str) else None
            if scheme is None:
                for k in kinds:
                    err(k, f'host refused: {host!r} is not on {DOMAIN}')
                continue
            raw = doc.get('raw') if isinstance(doc.get('raw'), dict) else {}
            kinds_held = (held.get(slug) or {}).get('kinds') or {}
            for k in kinds:
                if k not in KINDS:
                    err(k, f'unknown kind {k!r}')
                    continue
                path = raw.get(k) if isinstance(raw.get(k), str) else DEFAULT_RAW[k]
                if not PATH_RE.match(path):
                    err(k, f'raw path refused: {path!r}')
                    continue
                if k == 'source':
                    entry = doc.get('source')
                else:
                    entry = (doc.get('files') or {}).get(k) if isinstance(doc.get('files'), dict) else None
                sha = entry.get('sha256') if isinstance(entry, dict) else None
                if not (isinstance(sha, str) and SHA_RE.match(sha)):
                    err(k, 'no sha256 in the manifest')
                    continue
                size = entry.get('bytes') if isinstance(entry, dict) else None
                size = size if isinstance(size, int) and not isinstance(size, bool) and size >= 0 else None
                current = (kinds_held.get(k) or {}).get('sha256') == sha
                out.append(Fetch(slug, k, f'{scheme}://{host.strip()}{path}', sha, current, size))
        return out

    # -- fetching

    def fetch(self, f: Fetch) -> bytes:
        """The bytes of one Fetch, verified against its sha256; size-capped; no redirect off-host. Raises ClientError."""
        if f.error:
            raise ClientError(f.error)
        self._check_url(f.url)
        if f.size is not None and f.size > self.max_bytes:
            raise ClientError(f'{f.size} bytes in the manifest, over the cap of {self.max_bytes}')
        status, body, _ = self._get(f.url, f'{f.slug} {f.kind}')
        if status != 200:
            raise ClientError(f'HTTP {status}')
        got = hashlib.sha256(body).hexdigest()
        if got != f.sha256:
            raise ClientError(f'sha256 mismatch: the manifest says {f.sha256[:12]}…, the bytes are {got[:12]}…')
        return body

    # -- the whole thing

    def sync(self, folder: str | os.PathLike, wants: dict[str, list[str]],
             validate: Callable[[str, str, bytes], str | None] | None = None) -> Report:
        """manifest → plan → fetch only what differs → validate → write whole → state.json → Report. `validate(slug,
        kind, data)` returns None or an error string; `basic_validate` when none is given. Never raises for a network
        or content fault; a folder that cannot be written is an error in the report too."""
        t0 = self.clock()
        validate = basic_validate if validate is None else validate
        report = Report()
        folder = os.fspath(folder)
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            report.errors.append((ALL, 'folder', f'cannot create {folder}: {_describe(e)}'))
            log.warning('cosmoes: %s', report.errors[-1][2])
            report.elapsed = self.clock() - t0
            return report

        state = load_state(folder)
        local = _load_local_manifest(folder)
        etag = state.get('etag') if local is not None else None
        try:
            status, body, hdrs = self._get(self.base + '/manifest.json', 'manifest',
                                           {'If-None-Match': etag} if etag else None)
            if status == 304:
                manifest, raw_manifest, new_etag = local, None, etag
                log.debug('cosmoes: manifest unchanged (304)')
            elif status == 200:
                manifest, raw_manifest = _parse_manifest(body), body
                new_etag = hdrs.get('ETag') if isinstance(hdrs.get('ETag'), str) else None
            else:
                raise ClientError(f'manifest: HTTP {status}')
        except ClientError as e:
            report.errors.append((ALL, 'manifest', str(e)))
            log.warning('cosmoes: %s', e)
            report.elapsed = self.clock() - t0
            return report
        report.checked = True

        targets = _targets(manifest, wants)
        fetches = self.plan(state, manifest, wants)
        planned = {(f.slug, f.kind) for f in fetches}
        for slug, kinds in targets.items():
            for k in kinds:
                if (slug, k) not in planned:
                    report.skipped.append((slug, k))
        by_slug: dict[str, list[Fetch]] = {}
        for f in fetches:
            by_slug.setdefault(f.slug, []).append(f)

        documents = dict(state.get('documents') or {})
        now = _iso(self.clock())
        for slug, group in by_slug.items():
            doc = next((d for d in manifest['documents'] if isinstance(d, dict) and d.get('slug') == slug), None)
            new: dict[str, bytes] = {}
            kept: list[str] = []
            failed = False
            for f in group:
                target = os.path.join(folder, slug, FILENAMES.get(f.kind, f.kind))
                if f.error:
                    report.errors.append((slug, f.kind, f.error))
                    log.warning('cosmoes: %s %s: %s', slug, f.kind, f.error)
                    failed = True
                    continue
                if f.current and os.path.isfile(target):
                    kept.append(f.kind)
                    continue
                try:
                    data = self.fetch(f)
                    try:
                        problem = validate(slug, f.kind, data)
                    except Exception as e:                 # a hook that raises is a failed validation
                        problem = f'{type(e).__name__}: {e}'
                    if problem:
                        raise ClientError(f'validation: {problem}')
                    new[f.kind] = data
                except ClientError as e:
                    report.errors.append((slug, f.kind, str(e)))
                    log.warning('cosmoes: %s %s: %s', slug, f.kind, e)
                    failed = True
            if failed or doc is None:
                for k in new:
                    report.errors.append((slug, k, f'held back: another kind of {slug} failed'))
                report.unchanged.extend((slug, k) for k in kept)
                continue
            writing = ''
            try:
                for writing, data in new.items():
                    _atomic_write(os.path.join(folder, slug, FILENAMES[writing]), data)
            except OSError as e:
                report.errors.append((slug, writing, f'write: {_describe(e)}'))
                log.warning('cosmoes: %s %s: write: %s', slug, writing, _describe(e))
                continue
            entry = dict(documents.get(slug) or {})
            kinds_state = dict(entry.get('kinds') or {})
            for f in group:
                if f.kind in new:
                    kinds_state[f.kind] = {'sha256': f.sha256, 'fetched': now}
                    report.updated.append((slug, f.kind))
                    log.info('cosmoes: updated %s %s (%s)', slug, f.kind, f.sha256[:12])
                else:
                    report.unchanged.append((slug, f.kind))
                    log.debug('cosmoes: %s %s unchanged', slug, f.kind)
            version = doc.get('edition') if isinstance(doc.get('edition'), str) else doc.get('version')
            documents[slug] = {'name': doc.get('name') if isinstance(doc.get('name'), str) else slug,
                               'version': version if isinstance(version, str) else None,
                               'revised': doc.get('revised') if isinstance(doc.get('revised'), str) else None,
                               'host': str(doc.get('host')).strip(),
                               'kinds': kinds_state}

        try:
            if raw_manifest is not None and raw_manifest != _read_file(os.path.join(folder, 'manifest.json')):
                _atomic_write(os.path.join(folder, 'manifest.json'), raw_manifest)
            state = {'checked': now, 'updated': now if report.updated else state.get('updated'),
                     'etag': new_etag, 'documents': documents}
            _atomic_write(os.path.join(folder, 'state.json'), json.dumps(state, indent=1).encode('utf-8') + b'\n')
        except OSError as e:
            report.errors.append((ALL, 'state', f'write: {_describe(e)}'))
            log.warning('cosmoes: state: write: %s', _describe(e))
        report.elapsed = self.clock() - t0
        return report


# ----------------------------------------------------------------------------------------------------- command line

def _parse_wants(items: list[str], all_kinds: bool) -> dict[str, list[str]]:
    wants: dict[str, list[str]] = {}
    for item in items:
        slug, _, kinds = item.partition('=')
        slug = slug.strip()
        if not slug:
            raise argparse.ArgumentTypeError(f'--wants needs slug=kind,kind; got {item!r}')
        wants[slug] = list(KINDS) if all_kinds or not kinds.strip() else [k.strip() for k in kinds.split(',') if k.strip()]
    if not wants:
        wants[ALL] = list(KINDS) if all_kinds else ['source']
    return wants


def main(argv: list[str] | None = None) -> int:
    """`sync <folder> [--base URL] [--wants slug=source,short …] [--all-kinds]`: run a sync and print the report; exit
    1 when the manifest was not reached or anything errored. `status <folder>`: print state.json's documents."""
    p = argparse.ArgumentParser(prog='cosmoes_client.py', description='Sync the OES specifications from cosmoes.org.')
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('sync', help='fetch what differs into <folder> and print the report')
    s.add_argument('folder')
    s.add_argument('--base', default=f'https://{DOMAIN}', help='https://cosmoes.org, or http://127.0.0.1:PORT for a rig')
    s.add_argument('--wants', action='append', default=[], metavar='SLUG=KIND,KIND',
                   help='a document and its kinds (source, short, atem, fabula); repeatable; default: every document, source')
    s.add_argument('--all-kinds', action='store_true', help='every kind, for the --wants given or for every document')
    s.add_argument('--timeout', type=float, default=3.0)
    s.add_argument('--max-bytes', type=int, default=5_000_000)
    s.add_argument('--app', default='cli', help='the app named in the User-Agent')
    s.add_argument('-v', '--verbose', action='store_true', help='log INFO and up to stderr')
    t = sub.add_parser('status', help="print <folder>/state.json's documents")
    t.add_argument('folder')
    args = p.parse_args(argv)

    if args.command == 'sync':
        if args.verbose:
            logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stderr)
        try:
            wants = _parse_wants(args.wants, args.all_kinds)
            client = CosmoesClient(base=args.base, timeout=args.timeout, max_bytes=args.max_bytes,
                                   user_agent=f'cosmoes-client/{VERSION} ({args.app})')
        except (argparse.ArgumentTypeError, ValueError) as e:
            print(f'error: {e}')
            return 2
        report = client.sync(args.folder, wants)
        print('\n'.join(report.lines()))
        return 0 if report.ok else 1

    folder = args.folder
    if not os.path.isfile(os.path.join(folder, 'state.json')):
        print(f'no state.json in {folder}')
        return 1
    state = load_state(folder)
    print(f'checked: {state.get("checked") or "-"}   updated: {state.get("updated") or "-"}   etag: {state.get("etag") or "-"}')
    for slug, d in sorted((state.get('documents') or {}).items()):
        d = d if isinstance(d, dict) else {}
        print(f'{slug}: {d.get("name") or "?"} {d.get("version") or "?"}  revised {d.get("revised") or "-"}  host {d.get("host") or "-"}')
        for kind, k in sorted((d.get('kinds') or {}).items()):
            k = k if isinstance(k, dict) else {}
            print(f'  {kind:7} {str(k.get("sha256") or "")[:12]}  fetched {k.get("fetched") or "-"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
