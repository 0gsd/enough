/* Thym's runtime in the page, part 2 of 3: the deterministic moves and the checks their contracts name.
 *
 * Each move mirrors its Python implementation (enough/thym/moves/edit.py and project.py; the checks of
 * enough/thym/checks.py and of those modules), with the calling convention of enough/thym/registry.py:
 * `fn(ctx, ...operands, mods)`, operands Values, `mods` keyed by the modifier word. A move that cannot go on throws
 * `ThymJS.MoveError` with the person's words.
 *
 * What runs here is what is a pure function of its inputs. A move that needs the server's data (the dictionary, a
 * project's files, MacroCOSM's lint, the compiler, an engine) is not registered: `NOT_HERE` says why, and the runtime
 * refuses a plan that calls it at plan time with that reason. A move that asks a model is never run in the page.
 */
(function (root) {
  'use strict';
  const T = root.ThymJS;
  const { Value, MoveError, NOTHING, get, has, isDict, entries, fold, pyStrip, pyRstrip, cps, cpSlice, utf8, sha256,
    makeLine, makeChange, CHANGE_DOES, members, folderValue, isWithheld, itemKey, ThymDate, ThymFloat, plain,
    canonical, canonicalJson, dump, pySplitWs, pyRepr, truthy } = T;

  // -------------------------------------------------------------------------------------------------------------
  // The declarations the page knows when the host sends none (thym 1's view; `since: 1` hides a move from thym 0)
  // -------------------------------------------------------------------------------------------------------------

  const DECLS = {
    atem: { asks: true, gives: ['atem'], contract: ['atem-shape', 'span-resolves', 'provenance'], scaffold: 'first-sentence' },
    band: { gives: ['word'], contract: ['banded'], modifiers: { as: ['list of word'] } },
    compile: { gives: ['text'], contract: ['byte-exact'] },
    construe: { asks: true, gives: ['fabula'], contract: ['span-resolves', 'no-invention', 'stance-kept', 'coverage', 'terms-grounded', 'nothing-lost', 'fabula-checks', 'provenance'], modifiers: { as: ['figure', 'image', 'allusion', 'voice', 'turn', 'meaning', 'ambiguity'], with: ['fabula'] }, since: 1 },
    context: { gives: ['context'], modifiers: { of: ['text', 'package'] } },
    count: { gives: ['number'] },
    cut: { gives: ['short'], contract: ['whole-sentences', 'weight-order', 'coverage', 'provenance'], modifiers: { to: ['words', 'sentences'] } },
    derive: { asks: true, gives: ['fabula'], contract: ['span-resolves', 'stance-closed', 'terms-grounded', 'coverage', 'fabula-checks', 'provenance'], scaffold: 'rules-twin', modifiers: { as: ['prose', 'verse', 'code'], with: ['fabula'] } },
    digest: { gives: ['string'] },
    drop: { gives: ['change'], since: 1 },
    edit: { gives: ['text', 'short'], contract: ['only-the-changed', 'never-source', 'provenance'], modifiers: { with: ['list of change'] }, since: 1 },
    enumerate: { gives: ['volume'], contract: ['byte-exact', 'provenance'] },
    expand: { asks: true, gives: ['short'], contract: ['coverage', 'no-invention', 'stance-kept', 'length', 'span-inside', 'provenance'], modifiers: { with: ['fabula'], to: ['words'] } },
    fabula: { gives: ['fabula'], modifiers: { of: ['package'] } },
    folders: { gives: ['list of folder'], modifiers: { of: ['folder'] }, since: 1 },
    gather: { gives: ['same-as-with'], contract: ['nothing-lost', 'ids-unique', 'fabula-checks', 'provenance'], modifiers: { with: ['fabula', 'volume'] }, since: 1 },
    graph: { gives: ['graph'], contract: ['released'], modifiers: { of: ['text', 'package'] } },
    history: { gives: ['fabula'], contract: ['history-grounded', 'fabula-checks', 'provenance'], modifiers: { with: ['fabula'] }, since: 1 },
    insert: { gives: ['change'], modifiers: { before: ['line'], after: ['line'] }, since: 1 },
    isomorph: { gives: ['morph'], modifiers: { of: ['package'] } },
    join: { gives: ['short'], contract: ['provenance'], modifiers: { with: ['string'] }, since: 1 },
    lines: { gives: ['list of line'], modifiers: { of: ['text', 'short'] }, since: 1 },
    lint: { gives: ['report'] },
    mark: { gives: ['item', 'word'], contract: ['verified-only-where-derived'], modifiers: { as: ['marking'] } },
    measure: { asks: true, gives: ['morph'], contract: ['scale-range', 'scale-evidence', 'provenance'], scaffold: 'statistics', modifiers: { against: ['short'] } },
    morph: { asks: true, gives: ['short'], contract: ['coverage', 'no-invention', 'stance-kept', 'scales-met', 'provenance'], modifiers: { with: ['morph'] } },
    null: { asks: true, gives: ['short'], contract: ['coverage', 'no-invention', 'stance-kept', 'null-pinned', 'provenance'], scaffold: 'outline', modifiers: { of: ['fabula'] } },
    package: { gives: ['package'], contract: ['digests', 'released', 'provenance'] },
    project: { gives: ['volume'], contract: ['default-deny', 'no-counts', 'banded', 'no-mark', 'verified-derived', 'standing-gate', 'epoch', 'provenance'], modifiers: { as: ['isotype', 'paratype', 'isograph'] }, code_when: [[['isograph'], 'enough.thym.moves.ascribe:isograph', 'ascribe']] },
    propose: { asks: true, gives: ['list of item'], contract: ['no-invention', 'provenance'], modifiers: { with: ['volume'] }, since: 1 },
    question: { asks: true, gives: ['list of item'], contract: ['addressed', 'no-duplicate', 'provenance'], scaffold: 'bank', since: 1 },
    read: { asks: true, gives: ['short'], contract: ['coverage', 'no-invention', 'stance-kept', 'scales-met', 'labelled', 'never-source', 'provenance'], modifiers: { with: ['morph'], in: ['context'] } },
    record: { gives: ['same-as-in'], contract: ['addressed', 'only-the-asked', 'provenance'], modifiers: { in: ['fabula', 'volume'] }, since: 1 },
    replace: { gives: ['change'], modifiers: { with: ['string', 'line', 'short'] }, since: 1 },
    reword: { asks: true, gives: ['line', 'string', 'short'], contract: ['length', 'one-line', 'nothing-added', 'provenance'], modifiers: { to: ['words'], with: ['morph'] }, since: 1 },
    say: { gives: ['string'], since: 1 },
    scan: { gives: ['fabula'], contract: ['lines-found', 'scansion-grounded', 'span-resolves', 'fabula-checks', 'provenance'], modifiers: { as: ['rhyme', 'sound', 'recurrence', 'form'], with: ['fabula'] }, since: 1 },
    settle: { asks: true, gives: ['fabula', 'volume'], contract: ['addressed', 'only-the-asked', 'fabula-checks', 'provenance'], scaffold: 'direct', since: 1 },
    survey: { gives: ['fabula'], contract: ['files-found', 'code-span', 'licence-recorded', 'fabula-checks', 'provenance'], since: 1 },
    tell: { asks: true, gives: ['short'], contract: ['coverage', 'no-invention', 'stance-kept', 'scales-met', 'footer', 'provenance'], scaffold: 'outline', modifiers: { as: ['order', 'code', 'line', 'overview', 'manual'], by: ['order'], with: ['morph'] } },
    trace: { gives: ['trace'] },
    unpack: { gives: ['text'], contract: ['digests'] },
    withhold: { gives: ['nothing'], contract: ['no-mark'], modifiers: { where: ['condition'] } },
    words: { gives: ['number'] },
  };
  // this build reads `tell` under its new name, `entail`, too: one declaration, two names
  DECLS.entail = DECLS.tell;
  for (const [n, d] of Object.entries(DECLS)) d.name = d.name || n;

  /** The declarations a program of grammar `version` sees (run._views): the host's when it sent them. */
  function declarations(version, given) {
    const src = given || DECLS;
    const out = {};
    for (const [n, d] of Object.entries(src)) {
      if (Number.isInteger(d.since) && d.since > version) continue;
      out[n] = Object.assign({ name: n }, d);
    }
    if (out.tell && !out.entail) out.entail = out.tell;
    if (out.entail && !out.tell) out.tell = out.entail;
    return out;
  }

  /** The deterministic moves the page does not run, and why: each needs something only the server holds. */
  const NOT_HERE = {
    lint: "it runs MacroCOSM's checks, which the server holds",
    enumerate: "it is the compiler's, which the server holds",
    compile: "it is the compiler's, which the server holds",
    survey: "it reads a folder's syntax through the server's syntax engine",
    history: "it reads a clone's history through the server",
    scan: "it reads a poem's stresses and rhymes through FEED's pronunciations, which the server holds",
    'file-outline': "it reads a file's syntax through the server's syntax engine",
    'uses-outline': "it reads a fabulac through the server's engines",
    package: "it writes a package folder on the server's disk",
    unpack: "it reads a package folder on the server's disk",
    fabula: "it reads a package folder on the server's disk",
    context: "it reads the surrounding volume's catalog on the server",
    graph: "it reads what the holograph released, on the server",
    isomorph: "it reads a package folder on the server's disk",
    gather: "its contract's fabula-checks run MacroCOSM's lint, which the server holds",
    record: "its contract reads the fabula through MacroCOSM's manifests, which the server holds",
    cut: "its contract's coverage check reads EMF's cover map, which the page does not have yet",
  };

  // -------------------------------------------------------------------------------------------------------------
  // Text helpers (checks.py)
  // -------------------------------------------------------------------------------------------------------------

  const WORDS = /[A-Za-z0-9\u00c0-\u024f]+(?:['\u2019][A-Za-z]+)?/gu;
  const countWords = (text) => (String(text).match(WORDS) || []).length;
  function frontMatter(text) {
    text = text.replace(/\r\n/g, '\n');
    const m = /^---\n([\s\S]*?)\n---\n?/.exec(text);
    if (!m) return [{}, text];
    return [{}, text.slice(m[0].length)];          // the page reads the body after it; the front's data is not used here
  }
  const isFooter = (line) => { const s = pyStrip(line); return cps(s).length > 2 && s.startsWith('*') && s.endsWith('*') && !s.startsWith('**'); };
  function body(text, footer) {
    let rest = pyRstrip(frontMatter(text)[1]);
    if (!footer) {
      const paras = rest.split(/\n\s*\n/);
      if (paras.length && isFooter(pySplitWs(paras[paras.length - 1]).join(' '))) paras.pop();
      rest = paras.join('\n\n');
    }
    return rest;
  }

  // -------------------------------------------------------------------------------------------------------------
  // The moves
  // -------------------------------------------------------------------------------------------------------------

  const MOVES = {};
  const implement = (name, fn) => { MOVES[name] = fn; };

  implement('count', (ctx, v) => {
    if (v.type === 'fabula') {
      const p = v.mapping() || {};
      return new Value('number', (get(p, 'nodes') || []).filter(isDict).length);
    }
    if (v.type === 'folder' && v.payload && v.payload.isFolder) return new Value('number', v.payload.texts().length);
    const rows = members(v);
    if (rows === null) throw new MoveError(`a ${v.type} has nothing to count`);
    return new Value('number', rows.length);
  });

  implement('words', (ctx, v) => {
    if (['line', 'string', 'word'].includes(v.type)) return new Value('number', countWords(v.payload === null ? '' : String(v.payload)));
    if (v.type === 'atem') {
      const a = v.mapping() || {};
      const line = typeof get(a, 'line') === 'string' ? get(a, 'line') : (typeof v.payload === 'string' ? v.payload : '');
      return new Value('number', countWords(line));
    }
    const text = v.text();
    return new Value('number', countWords(v.type === 'short' ? body(text) : frontMatter(text)[1]));
  });

  implement('digest', (ctx, v) => new Value('string', v.sha256));
  implement('trace', (ctx) => ctx.trace());

  // the editor (THYM 21)
  function splitLines(text) {
    if (!text) return [];
    const parts = text.split('\n');
    const last = parts.pop();
    const out = parts.map((p) => (p.endsWith('\r') ? [p.slice(0, -1), '\r\n'] : [p, '\n']));
    if (last) out.push([last, '']);
    return out;
  }
  const ending = (rows) => {
    const crlf = rows.filter((r) => r[1] === '\r\n').length, lf = rows.filter((r) => r[1] === '\n').length;
    return crlf > lf ? '\r\n' : '\n';
  };
  function source(v, move) {
    if (!v || !v.isThymValue || !['text', 'short'].includes(v.type)) {
      const kind = v && v.isThymValue ? v.type : 'nothing';
      throw new MoveError(`${move} reads a text or a short, and was given a ${kind}`);
    }
    return [v.sha256, splitLines(v.text())];
  }
  implement('lines', (ctx, mods) => {
    const [of, rows] = source(mods.of, 'lines');
    return new Value('list', rows.map(([t], i) => makeLine(t, i + 1, of)));
  });
  function lineOf(v, move) {
    const place = v && v.isThymValue ? (v.origin || {}).line : null;
    if (!isDict(place) || !Number.isInteger(place.number) || !place.source) {
      throw new MoveError(`${move} names a line read with lines of a text or a short; this value is no such line`);
    }
    return place;
  }
  function newLines(v, move) {
    if (!v || !v.isThymValue || v.isNothing) throw new MoveError(`${move} needs the new words, and was given nothing`);
    if (!['string', 'line', 'short', 'word', 'text'].includes(v.type)) throw new MoveError(`${move} puts in a string, a line or a short, not a ${v.type}`);
    const text = v.text();
    return text ? splitLines(text).map((r) => r[0]) : [''];
  }
  implement('replace', (ctx, l, mods) => {
    const place = lineOf(l, 'replace');
    if (mods.with === undefined || mods.with === null) throw new MoveError('replace needs what goes in the line\'s place: replace l with <a string, a line or a short>');
    return makeChange(place.number, place.sha256, place.source, 'replace', newLines(mods.with, 'replace'));
  });
  implement('drop', (ctx, l) => {
    const place = lineOf(l, 'drop');
    return makeChange(place.number, place.sha256, place.source, 'drop', []);
  });
  implement('insert', (ctx, v, mods) => {
    const places = ['before', 'after'].filter((w) => mods[w] !== undefined && mods[w] !== null);
    if (places.length !== 1) throw new MoveError('insert takes before <line> or after <line>, exactly one of the two');
    const place = lineOf(mods[places[0]], 'insert');
    return makeChange(place.number, place.sha256, place.source, `insert-${places[0]}`, newLines(v, 'insert'));
  });
  function changesOf(v) {
    if (!v || !v.isThymValue || v.type !== 'list') throw new MoveError('edit needs its changes as a list: edit s with changes');
    return (v.payload || []).map((m) => {
      const d = m && m.isThymValue ? m.payload : null;
      if (!m || !m.isThymValue || m.type !== 'change' || !isDict(d) || !CHANGE_DOES.includes(get(d, 'do'))) {
        throw new MoveError('edit takes changes made by replace, drop and insert, and only those');
      }
      return d;
    });
  }
  function changeProblems(of, rows, changes) {
    const out = [];
    for (const c of changes) {
      const at = c.at;
      if (c.of !== of) out.push(`a change names line ${at} of another text`);
      else if (!Number.isInteger(at) || !(at >= 1 && at <= rows.length)) out.push(`a change names line ${at}, and the text has ${rows.length} lines`);
      else if (c.was !== sha256(utf8(rows[at - 1][0]))) out.push(`line ${at} changed since it was read`);
    }
    const taken = new Map();
    for (const c of changes) {
      if (!['replace', 'drop'].includes(c.do) || !Number.isInteger(c.at)) continue;
      if (taken.has(c.at)) {
        const was = taken.get(c.at);
        if (was === c.do && c.do === 'replace') out.push(`line ${c.at} is replaced twice`);
        else if (was === c.do) out.push(`line ${c.at} is dropped twice`);
        else out.push(`line ${c.at} is both replaced and dropped`);
      }
      if (!taken.has(c.at)) taken.set(c.at, c.do);
    }
    return out;
  }
  function applyChanges(rows, changes) {
    const eol = ending(rows);
    const by = new Map();
    for (const c of changes) {
      if (!by.has(c.at)) by.set(c.at, {});
      const m = by.get(c.at);
      (m[c.do] = m[c.do] || []).push(c);
    }
    let out = [];
    rows.forEach(([text, end], i) => {
      const n = i + 1;
      const mine = by.get(n) || {};
      for (const c of mine['insert-before'] || []) out.push(...c.lines.map((x) => [x, eol, `change:${n}`]));
      if (mine.replace) out.push(...mine.replace[0].lines.map((x) => [x, eol, `change:${n}`]));
      else if (!mine.drop) out.push([text, end, `keep:${n}`]);
      for (const c of mine['insert-after'] || []) out.push(...c.lines.map((x) => [x, eol, `change:${n}`]));
    });
    if (rows.length && rows[rows.length - 1][1] === '' && out.length) {
      const last = out[out.length - 1];
      out = out.slice(0, -1).map(([t, e, f]) => [t, e || eol, f]).concat([[last[0], '', last[2]]]);
    }
    return out;
  }
  const unique = (xs) => Array.from(new Set(xs));
  implement('edit', (ctx, s, mods) => {
    const [of, rows] = source(s, 'edit');
    const changes = changesOf(mods.with);
    const bad = changeProblems(of, rows, changes);
    if (bad.length) throw new MoveError(unique(bad).join('; '));
    return new Value(s.type, applyChanges(rows, changes).map(([t, e]) => t + e).join(''));
  });

  implement('join', (ctx, xs, mods) => {
    if (!xs || !xs.isThymValue || xs.type !== 'list') throw new MoveError('join takes a list of strings, lines or shorts');
    const sep = mods.with;
    const by = sep === undefined || sep === null ? '\n' : (sep.isThymValue ? sep.text() : String(sep));
    const parts = (xs.payload || []).map((m) => (!m || !m.isThymValue || m.isNothing ? '' : pyRstrip(m.text(), '\r\n')));
    const text = parts.join(by);
    return new Value('short', text ? text + '\n' : '');
  });

  implement('say', (ctx, v) => {
    const p = v && v.isThymValue ? v.payload : v;
    if (typeof p === 'boolean') return new Value('string', p ? 'true' : 'false');
    if (p instanceof ThymDate) return new Value('string', p.iso);
    if (Number.isInteger(p) || typeof p === 'string') return new Value('string', String(p));
    throw new MoveError(`say gives a number, a date, a word or a bool as a string, not a ${v && v.isThymValue ? v.type : v}`);
  });

  implement('folders', (ctx, mods) => {
    const d = mods.of;
    if (!d || !d.isThymValue || !d.payload || !d.payload.isFolder) throw new MoveError('folders lists the folders of a folder: folders of d');
    return new Value('list', d.payload.folders().map((f) => folderValue(f)));
  });

  // Comprise's moves (project.py)
  const ISOTYPE = 'comprise-isotype/0', PARATYPE = 'comprise-paratype/0';
  const CADENCES = ['quarterly', 'monthly', 'weekly'];
  const OFFER_KINDS = ['suite', 'offering', 'function', 'product', 'service', 'platform'];
  const MARKET_KINDS = ['audience', 'market', 'geography'];
  const IDENTITY_KINDS = ['brand', 'entity', 'surface'];
  const SHAPE_KINDS = ['position'];
  const AIM_KINDS = ['customers', 'partners', 'suppliers', 'distribution', 'technology', 'talent', 'capital', 'other'];
  const DERIVABLE = { comprise: OFFER_KINDS.concat(MARKET_KINDS, IDENTITY_KINDS, SHAPE_KINDS) };
  const SHAPE_SLOTS = { employees: ['none', 'some'], structure: ['single', 'group'], markets: null };
  const IDENTITY_SLOTS = ['name', 'domains', 'jurisdiction', 'founded', 'kind'];
  const LIVE = [null, 'active'], AIM_LIVE = [null, 'active', 'planned'];
  const MAX_OFFERS = 50, MAX_MARKETS = 12;
  const EPOCH_RE = { quarterly: /^\d{4}-Q[1-4]$/, monthly: /^\d{4}-(0[1-9]|1[0-2])$/, weekly: /^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$/ };
  const HID_RE = /^[a-z2-7]{26}$/;
  const DIGIT = /\d/;
  const DATE = /\b\d{4}-\d{2}-\d{2}\b/;

  function isoWeek(d) {
    const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
    const day = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - day);
    const y = t.getUTCFullYear();
    const w = Math.ceil(((t - Date.UTC(y, 0, 1)) / 86400000 + 1) / 7);
    return [y, w];
  }
  function epochFor(cadence, when) {
    const y = when.getUTCFullYear(), m = when.getUTCMonth() + 1;
    if (cadence === 'monthly') return `${y}-${String(m).padStart(2, '0')}`;
    if (cadence === 'weekly') { const [iy, w] = isoWeek(when); return `${iy}-W${String(w).padStart(2, '0')}`; }
    return `${y}-Q${Math.floor((m - 1) / 3) + 1}`;
  }
  const plainStr = (v) => (typeof v === 'string' && pyStrip(v) ? fold(v) : null);
  function year(v) {
    if (v instanceof ThymDate) return v.year;
    if (Number.isInteger(v) && v >= 1000 && v <= 2999) return v;
    const m = typeof v === 'string' ? /^\s*([12]\d{3})(?:\b|-)/.exec(v) : null;
    return m ? parseInt(m[1], 10) : null;
  }
  const idOf = (v) => {
    const o = v.origin || {};
    const iid = truthy(o.id) ? o.id : get(v.mapping() || {}, 'id');
    return truthy(iid) ? String(iid) : null;
  };
  function kindOf(v) {
    const k = (v.origin || {}).kind;
    if (typeof k === 'string' && k) return k;
    const m = /^[A-Z]:([a-z][a-z0-9-]*)\//.exec(idOf(v) || '');
    return m ? m[1] : '';
  }
  function minicosmOf(v) {
    const oes = (v.origin || {}).oes;
    if (typeof oes === 'string' && oes.includes('/')) return oes.split('/')[0];
    const vol = (v.origin || {}).volume;
    if (vol && vol.isThymValue && vol.payload && vol.payload.isVolume && vol.payload.oes) return String(vol.payload.oes).split('/')[0];
    return '';
  }
  function markingOf(v) {
    let m = (v.origin || {}).marking;
    if ((m === undefined || m === null) && isDict(v.payload)) m = get(v.payload, 'marking');
    return m === 'verified' || m === 'stated' ? m : null;
  }
  const letterOf = (v) => (idOf(v) || ' ')[0];
  const isPublic = (v) => { const vis = get(v.mapping() || {}, 'visibility'); return vis === 'public' || (vis === null && letterOf(v) === 'P'); };
  function domainOf(url) {
    let s = url.includes('://') ? url : 'https://' + url;
    s = s.slice(s.indexOf('://') + 3);
    let host = s.split(/[/?#]/)[0];
    if (host.includes('@')) host = host.slice(host.lastIndexOf('@') + 1);
    if (host.startsWith('[')) host = host.slice(1, host.indexOf(']') >= 0 ? host.indexOf(']') : undefined);
    else if (host.includes(':')) host = host.slice(0, host.indexOf(':'));
    if (!host) return null;
    host = pyRstrip(host.toLowerCase(), '.');
    return host.startsWith('www.') ? host.slice(4) : host;
  }
  function identity(rows, withheld) {
    rows = rows.filter((r) => !isWithheld(withheld, r));
    const brand = rows.find((r) => kindOf(r) === 'brand' && isPublic(r)) || null;
    const entity = rows.find((r) => kindOf(r) === 'entity' && get(r.mapping() || {}, 'anchor') === true &&
      get(r.mapping() || {}, 'visibility') === 'public') || null;
    const b = (brand ? brand.mapping() : {}) || {}, e = (entity ? entity.mapping() : {}) || {};
    const out = {};
    const name = plainStr(get(b, 'name')) || plainStr(get(e, 'name'));
    if (name) out.name = name;
    const domains = new Set();
    for (const r of rows) {
      const d = r.mapping() || {};
      const own = get(d, 'kind') === 'website' && [null, 'none', 'self'].includes(get(d, 'counterparty'));
      if (kindOf(r) === 'surface' && get(d, 'visibility') === 'public' && own && plainStr(get(d, 'url'))) {
        const dom = domainOf(get(d, 'url'));
        if (dom) domains.add(dom);
      }
    }
    if (truthy(e)) {
      const listed = Array.isArray(get(e, 'domains')) ? get(e, 'domains') : [get(e, 'domain')];
      const gid = isDict(get(e, 'global-id')) ? get(e, 'global-id') : {};
      for (const x of listed.concat([get(gid, 'domain')])) {
        if (plainStr(x)) { const dom = domainOf(x); if (dom) domains.add(dom); }
      }
    }
    if (domains.size) out.domains = Array.from(domains).sort(T.cmpStr);
    if (plainStr(get(e, 'jurisdiction'))) out.jurisdiction = plainStr(get(e, 'jurisdiction'));
    const founded = year(get(e, 'since')) || year(get(b, 'since'));
    if (founded) out.founded = founded;
    if (plainStr(get(b, 'kind'))) out.kind = plainStr(get(b, 'kind'));
    return out;
  }
  function programRef(ctx) {
    let prog = {};
    try { prog = get(ctx.trace().mapping() || {}, 'program') || {}; } catch (e) { prog = {}; }
    const name = get(prog, 'name') || (ctx.program ? ctx.program.name : null);
    return { name: name === undefined ? null : name, sha256: get(prog, 'sha256') };
  }
  const asList = (v) => {
    if (v && v.isThymValue) v = v.type === 'list' ? v.plain() : [v];
    if (v === null || v === undefined) return [];
    return Array.isArray(v) ? v.slice() : [v];
  };
  const cmpKey = (a, b) => {
    for (let i = 0; i < a.length; i++) {
      const x = a[i], y = b[i];
      const c = typeof x === 'number' ? x - y : T.cmpStr(x, y);
      if (c) return c;
    }
    return 0;
  };
  const lower = (s) => s.toLowerCase();

  implement('project', (ctx, h, mods) => {
    const kind = mods.as || 'isotype';
    if (kind !== 'isotype' && kind !== 'paratype') throw new MoveError(`project gives an isotype or a paratype, not ${kind}`);
    const cat = h.mapping() || {};
    const rows = members(h) || [];
    const withheld = ctx.withheld;
    const cadence = CADENCES.includes(get(cat, 'cadence')) ? get(cat, 'cadence') : 'quarterly';
    const offers = new Map(), markets = new Set(), seeks = new Map(), openTo = new Map();
    for (const v of ctx.emitted) {
      if (!v || !v.isThymValue || isWithheld(withheld, v) || !isDict(v.payload)) continue;
      const d = v.payload, k = kindOf(v), m = markingOf(v);
      if (m === 'verified' && OFFER_KINDS.includes(k) && LIVE.includes(get(d, 'status')) && plainStr(get(d, 'name'))) {
        const name = plainStr(get(d, 'name'));
        const summary = plainStr(get(d, 'summary')) || '';
        const key = JSON.stringify([k, name]);
        if (!offers.has(key)) offers.set(key, { k: [k, name], v: { name, summary: DIGIT.test(summary) ? '' : summary, kind: k } });
      } else if (m === 'verified' && MARKET_KINDS.includes(k) && LIVE.includes(get(d, 'status')) && plainStr(get(d, 'name'))) {
        if (!DIGIT.test(get(d, 'name'))) markets.add(plainStr(get(d, 'name')));
      } else if (m === 'stated' && k === 'aim' && AIM_LIVE.includes(get(d, 'status')) && AIM_KINDS.includes(get(d, 'kind'))) {
        const summary = plainStr(get(d, 'summary'));
        const target = get(d, 'stance') === 'seeking' ? seeks : get(d, 'stance') === 'open' ? openTo : null;
        if (summary && target !== null && !DIGIT.test(summary)) {
          const key = JSON.stringify([get(d, 'kind'), summary]);
          if (!target.has(key)) target.set(key, { k: [get(d, 'kind'), summary], v: { kind: get(d, 'kind'), summary } });
        }
      }
    }
    const shape = {};
    const ident = identity(rows, withheld);
    for (const [slot, v] of ctx.slots) {
      if (!v || !v.isThymValue || markingOf(v) !== 'verified') continue;
      const word = v.plain();
      if (has(SHAPE_SLOTS, slot) && SHAPE_SLOTS[slot] && SHAPE_SLOTS[slot].includes(word)) shape[slot] = word;
      else if (slot === 'markets') for (const x of asList(word)) { if (typeof x === 'string' && !DIGIT.test(x)) markets.add(fold(x)); }
      else if (IDENTITY_SLOTS.includes(slot) && !has(ident, slot) && typeof word === 'string' && slot !== 'founded') ident[slot] = word;
    }
    if (markets.size) shape.markets = Array.from(markets).sort((a, b) => cmpKey([lower(a), a], [lower(b), b])).slice(0, MAX_MARKETS);
    const order = Object.fromEntries(OFFER_KINDS.map((k, i) => [k, i]));
    const aimOrder = Object.fromEntries(AIM_KINDS.map((k, i) => [k, i]));
    const sortRows = (m, ord) => Array.from(m.values()).sort((a, b) => cmpKey([ord[a.k[0]], lower(a.k[1]), a.k[1]], [ord[b.k[0]], lower(b.k[1]), b.k[1]])).map((r) => r.v);
    const doc = {};
    doc[kind] = kind === 'isotype' ? ISOTYPE : PARATYPE;
    const hid = get(cat, 'hid');
    Object.assign(doc, { hid: typeof hid === 'string' && HID_RE.test(hid) ? hid : null, epoch: epochFor(cadence, ctx.now),
      cadence, sample: get(cat, 'sample') === true && kind === 'isotype', identity: ident, shape,
      offers: sortRows(offers, order).slice(0, MAX_OFFERS), seeks: sortRows(seeks, aimOrder),
      open_to: sortRows(openTo, aimOrder), program: programRef(ctx) });
    if (kind === 'paratype') Object.assign(doc, { standing: 'third-party', submitter: null, of: (ident.domains || [null])[0] });
    if (ctx.stage) {
      ctx.stage.set(`${kind}.cosm`, utf8(dump(plain(doc))));
      ctx.stage.set(`${kind}.json`, canonicalJson(doc));
    }
    return new Value('volume', doc);
  });

  implement('band', (ctx, n, mods) => {
    const words = asList(mods.as).map(String);
    if (!words.length) throw new MoveError('band needs its words: band <number> as [none, some]');
    const value = n.plain();
    if (!Number.isInteger(value)) throw new MoveError(`band takes a number, not a ${n.type}`);
    let w;
    if (words.length === 2 && words[0] === 'none' && words[1] === 'some') w = value <= 0 ? 'none' : 'some';
    else w = words[Math.min(Math.floor(Math.max(value, 0) / 10), words.length - 1)];
    return new Value('word', w, { origin: { band: words } });
  });

  implement('mark', (ctx, x, mods) => {
    const m = mods.as;
    if (m !== 'verified' && m !== 'stated') throw new MoveError(`a marking is verified or stated, not ${m}`);
    if (x.type === 'word' || !isDict(x.payload)) return new Value(x.type, x.payload, { origin: Object.assign({}, x.origin || {}, { marking: m }) });
    return new Value('item', Object.assign({}, x.payload, { marking: m }), { origin: x.origin });
  });

  implement('withhold', (ctx, v, mods) => {
    const w = mods.where;
    let rows;
    if (w !== undefined && w !== null) rows = w.select(v);
    else if (['volume', 'list', 'fabula'].includes(v.type)) rows = members(v) || [];
    else rows = [v];
    ctx.withhold(rows);
    return null;
  });

  // -------------------------------------------------------------------------------------------------------------
  // The checks: fn(output, inputs, node, decl, ctx) -> [ok, why]
  // -------------------------------------------------------------------------------------------------------------

  const CHECKS = {};
  const KIND_CHECKS = {};
  const check = (name, fn) => { CHECKS[name] = fn; };
  const modsOf = (node) => (isDict((node || {}).modifiers) ? node.modifiers : {});
  function* walk(v, path) {
    if (T.isDict(v)) for (const [k, x] of entries(v)) yield* walk(x, path ? `${path}.${k}` : String(k));
    else if (Array.isArray(v)) for (let i = 0; i < v.length; i++) yield* walk(v[i], `${path}[${i}]`);
    else yield [path, v];
  }
  function* leaves(v) {
    if (T.isDict(v)) for (const [, x] of entries(v)) yield* leaves(x);
    else if (Array.isArray(v)) for (const x of v) yield* leaves(x);
    else yield v;
  }

  check('provenance', (output) => {
    const m = output.made;
    if (output.isNothing) return [false, 'the move gave nothing, so nothing carries made'];
    if (!isDict(m) || !m.move) return [false, 'the output carries no made'];
    if (m.move !== 'none' && !m.run) return [false, `made names the move ${m.move} but no run`];
    return [true, ''];
  });
  // an input given to the page cannot change on a disk while the run goes on, and no output is written over one
  check('never-source', () => [true, '']);

  check('only-the-changed', (output, inputs) => {
    const srcE = Object.entries(inputs).find(([k, v]) => k !== 'with' && v && v.isThymValue && ['text', 'short'].includes(v.type));
    if (!srcE) return [false, 'no text or short among the inputs'];
    const [name, src] = srcE;
    let changes;
    try { changes = changesOf(inputs.with); } catch (e) { if (e.isMoveError) return [false, e.message]; throw e; }
    const rows = splitLines(src.text());
    const bad = changeProblems(src.sha256, rows, changes);
    if (bad.length) return [false, unique(bad).join('; ')];
    const want = applyChanges(rows, changes);
    const got = splitLines(output.text());
    const a = want.map((r) => r[0]), b = got.map((r) => r[0]);
    if (a.length !== b.length || a.some((x, i) => x !== b[i])) {
      // difflib's first differing block, for the two cases the page can meet (a line lost, a line not given)
      let i = 0;
      while (i < a.length && i < b.length && a[i] === b[i]) i++;
      if (i < a.length) {
        const [, , frm] = want[i];
        const [kind, n] = frm.split(':');
        if (kind === 'change') return [false, `line ${n} is not what its change says`];
        return [false, `line ${n} of ${name}, which no change names, ${b.length < a.length ? 'is missing from the output' : 'differs in the output'}`];
      }
      return [false, `the output holds a line that neither ${name} nor a change gave: ${cpSlice(b[i], 0, 60)}`];
    }
    if (want.map(([t, e]) => t + e).join('') !== output.text()) return [false, `the output's line breaks are not ${name}'s`];
    return [true, ''];
  });

  check('length', (output, inputs, node) => {
    const to = modsOf(node).to;
    if (!truthy(to)) return [true, 'no length was asked'];
    const n = to.n, unit = to.unit;
    const text = output.text();
    if (unit === 'sentences') return [false, 'the page does not count sentences yet'];
    const k = countWords(body(text));
    if (k > n) return [false, `${k} words, more than ${n}`];
    if (k * 100 < 80 * n) return [false, `${k} words, fewer than 80 per hundred of ${n}`];
    return [true, ''];
  });
  check('one-line', (output) => {
    if (output.type !== 'line') return [true, ''];
    const n = pyStrip(output.text(), '\n').split('\n').length;
    return n === 1 ? [true, ''] : [false, `the reworded line is ${n} lines, not one`];
  });

  const MARK_WORDS = /\b(withheld|redacted|hidden|omitted|removed|elided)\b/i;
  const PLACEHOLDER = /^\s*(withheld|redacted|hidden|omitted|removed|elided)\s*$|[[(<{]\s*(withheld|redacted|hidden|omitted|removed|elided)\b/i;
  check('no-mark', (output, inputs, node, decl, ctx) => {
    if (output.isNothing) return [true, ''];
    const withheld = (ctx && ctx.withheld) || new Map();
    const data = output.mapping();
    const readable = data !== null || typeof output.payload === 'string';
    const text = readable ? T.decodeKeep(output.bytes()) : '';
    for (const [wid, item] of withheld) {
      const names = new Set([wid]);
      if (item && item.isThymValue && !item.isNothing) { const i = T.itemId(item); if (i) names.add(i); }
      for (const name of Array.from(names).filter(Boolean).sort(T.cmpStr)) {
        if (text.includes(name)) return [false, `the withheld item ${name} is named in the output`];
      }
    }
    if (data !== null) {
      for (const [path, v] of walk(plain(data), '')) {
        const leaf = path.includes('.') ? path.slice(path.lastIndexOf('.') + 1) : path;
        if (MARK_WORDS.test(leaf.replace(/_/g, ' ')) || (typeof v === 'string' && PLACEHOLDER.test(v))) return [false, `${path} marks something withheld`];
      }
    } else if (PLACEHOLDER.test(text)) return [false, 'the output marks something withheld'];
    return [true, ''];
  });

  check('no-counts', (output) => {
    const data = output.mapping();
    if (data === null) return [false, 'the projection is not a mapping'];
    for (const [path, v] of walk(plain(data), '')) {
      if (typeof v === 'boolean') continue;
      if ((typeof v === 'number' || v instanceof ThymFloat) && path !== 'identity.founded') return [false, `${path} holds the number ${v}`];
    }
    return [true, ''];
  });

  const ISOTYPE_KEYS = ['isotype', 'hid', 'epoch', 'cadence', 'sample', 'identity', 'shape', 'offers', 'seeks', 'open_to', 'program', 'trace'];
  const PARATYPE_KEYS = ISOTYPE_KEYS.filter((k) => k !== 'isotype').concat(['paratype', 'standing', 'submitter', 'of']);
  check('default-deny', (output, inputs, node) => {
    const data = output.mapping();
    if (data === null || Array.isArray(get(data, 'nodes'))) return [false, 'the projection is not a comprise-isotype/0 document'];
    const kind = modsOf(node).as;
    const keys = (kind === 'paratype' || has(data, 'paratype')) ? PARATYPE_KEYS : ISOTYPE_KEYS;
    const extra = entries(data).map((e) => String(e[0])).filter((k) => !keys.includes(k));
    if (extra.length) return [false, `fields the target schema does not name: ${extra.join(', ')}`];
    return [true, ''];
  });

  const NINETY = 'no earlier release is known, so the band shown stands; the 90-day rule binds from the second release';
  check('banded', (output, inputs, node, decl, ctx) => {
    if (output.type === 'word') {
      const ws = asList(modsOf(node).as).map(String);
      const words = ws.length ? ws : ((output.origin || {}).band || []);
      if (!words.includes(output.payload)) return [false, `${pyRepr(output.payload)} is not a word of the band ${pyRepr(words)}`];
      return [true, NINETY];
    }
    const data = output.mapping() || {};
    const shape = isDict(get(data, 'shape')) ? get(data, 'shape') : {};
    for (const [slot, allowed] of Object.entries(SHAPE_SLOTS)) {
      if (allowed && has(shape, slot) && !allowed.includes(get(shape, slot))) return [false, `shape.${slot} is ${pyRepr(get(shape, slot))}, not a word of ${allowed.join(', ')}`];
    }
    for (const [slot, v] of (ctx && ctx.slots) || new Map()) {
      const words = v && v.isThymValue ? (v.origin || {}).band : null;
      if (words && words.length && !words.includes(v.plain())) return [false, `${slot}: ${pyRepr(v.plain())} is not a word of its band ${pyRepr(words)}`];
    }
    return [true, NINETY];
  });

  function neither(inputs, ctx) {
    const h = Object.values(inputs).find((v) => v && v.isThymValue && v.type === 'volume');
    const withheld = (ctx && ctx.withheld) || new Map();
    const emitted = new Set(((ctx && ctx.emitted) || []).filter((v) => v && v.isThymValue).map(itemKey));
    return (h ? (members(h) || []) : []).filter((r) => !emitted.has(itemKey(r)) && !isWithheld(withheld, r)).length;
  }
  const s = (n, w) => `${n} ${w}${n !== 1 ? 's' : ''}`;
  check('verified-derived', (output, inputs, node, decl, ctx) => {
    let nv = 0, ns = 0;
    const derivable = DERIVABLE.comprise;
    const withheld = (ctx && ctx.withheld) || new Map();
    for (const v of (ctx && ctx.emitted) || []) {
      if (!v || !v.isThymValue || isWithheld(withheld, v)) continue;
      const m = markingOf(v), k = kindOf(v);
      if (m === 'verified' && !derivable.includes(k)) return [false, `${idOf(v)} is marked verified, and the schema derives no ${k}`];
      if (m === 'stated' && k !== 'aim') return [false, `${idOf(v)} is marked stated; stated is the subject's own words, its aims`];
      nv += m === 'verified' ? 1 : 0;
      ns += m === 'stated' ? 1 : 0;
    }
    let slots = 0;
    for (const [slot, v] of (ctx && ctx.slots) || new Map()) {
      if (has(SHAPE_SLOTS, slot) || IDENTITY_SLOTS.includes(slot)) {
        if (!v || !v.isThymValue || markingOf(v) !== 'verified') return [false, `${slot} is derived, and is not marked verified`];
        slots += 1;
      }
    }
    const left = neither(inputs, ctx);
    return [true, `verified on ${s(nv, 'item')} and ${s(slots, 'field')}, stated on ${s(ns, 'aim')}; ${s(left, 'item')} neither emitted nor withheld were left out by default-deny`];
  });

  check('verified-only-where-derived', (output, inputs, node) => {
    const m = modsOf(node).as || markingOf(output);
    if (m === 'stated') return [true, ''];
    if (m !== 'verified') return [false, `a marking is verified or stated, not ${m}`];
    if (output.type === 'word' || !isDict(output.payload)) {
      const slot = (node || {}).slot;
      if (has(SHAPE_SLOTS, slot) || IDENTITY_SLOTS.includes(slot) || truthy((output.origin || {}).band)) return [true, ''];
      return [false, 'a word is verified only where it fills a derived field, or where a band made it'];
    }
    const mini = minicosmOf(output), k = kindOf(output);
    if ((DERIVABLE[mini] || []).includes(k)) return [true, ''];
    return [false, `${idOf(output)}: ${mini || 'its MiniCOSM'} does not derive a ${k || 'kind'}, so it cannot be verified`];
  });

  check('standing-gate', (output, inputs, node, decl, ctx) => {
    const data = output.mapping() || {};
    if (truthy(get(data, 'paratype'))) return [true, 'a paratype speaks at third-party standing, never as the company'];
    if (get(data, 'sample') === true) return [true, 'a sample: its isotype says sample: true'];
    return [false, 'a release as the company needs first-party standing; this holotype is not a sample, and no standing says first-party'];
  });

  const sortedBy = (rows, key) => rows.every((r, i) => i === 0 || cmpKey(key(rows[i - 1]), key(r)) <= 0);
  check('epoch', (output, inputs, node, decl, ctx) => {
    const data = output.mapping() || {};
    const cad = get(data, 'cadence');
    if (!CADENCES.includes(cad)) return [false, `the cadence ${pyRepr(cad)} is not one of ${CADENCES.join(', ')}`];
    const ep = get(data, 'epoch');
    if (typeof ep !== 'string' || !EPOCH_RE[cad].test(ep)) return [false, `the epoch ${pyRepr(ep)} is not a ${cad} epoch`];
    if (ctx && ctx.now && ep !== epochFor(cad, ctx.now)) return [false, `the epoch ${ep} is not the one this run falls in (${epochFor(cad, ctx.now)})`];
    for (const [k, v] of entries(data)) {
      if (k === 'epoch') continue;
      for (const leaf of leaves(v)) {
        if (leaf instanceof ThymDate || (typeof leaf === 'string' && DATE.test(leaf))) return [false, `${k} shows a date (${T.pyStr(leaf)}); the epoch is the only date a projection shows`];
      }
    }
    const order = Object.fromEntries(OFFER_KINDS.map((x, i) => [x, i]));
    const aim = Object.fromEntries(AIM_KINDS.map((x, i) => [x, i]));
    const ordOf = (m, k) => (has(m, k) ? m[k] : 99);
    const offers = (get(data, 'offers') || []).filter(isDict);
    if (!sortedBy(offers, (o) => [ordOf(order, get(o, 'kind')), lower(T.pyStr(get(o, 'name'))), T.pyStr(get(o, 'name'))])) return [false, 'the offers are not sorted'];
    for (const sec of ['seeks', 'open_to']) {
      const rows = (get(data, sec) || []).filter(isDict);
      if (!sortedBy(rows, (a) => [ordOf(aim, get(a, 'kind')), lower(T.pyStr(get(a, 'summary'))), T.pyStr(get(a, 'summary'))])) return [false, `${sec} is not sorted`];
    }
    const ident = isDict(get(data, 'identity')) ? get(data, 'identity') : {};
    if (Array.isArray(get(ident, 'domains')) && !sortedBy(get(ident, 'domains'), (d) => [d])) return [false, 'identity.domains is not sorted'];
    const shape = isDict(get(data, 'shape')) ? get(data, 'shape') : {};
    if (Array.isArray(get(shape, 'markets')) && !sortedBy(get(shape, 'markets'), (x) => [lower(T.pyStr(x)), T.pyStr(x)])) return [false, 'shape.markets is not sorted'];
    return [true, ''];
  });

  /** One check's verdict (checks.verdict): [ok, why], or a Refusal when no check of that name is here. */
  function verdict(name, output, inputs, node, decl, ctx) {
    const kind = modsOf(node).as;
    const fn = (typeof kind === 'string' && KIND_CHECKS[`${name}/${kind}`]) || CHECKS[name];
    if (!fn) return new T.Refusal('run', name, 'check not implemented', (node || {}).line === undefined ? null : node.line);
    let r;
    try { r = fn(output, inputs || {}, node || {}, decl, ctx); } catch (e) {
      return [false, `the check raised ${e && e.name ? e.name : 'Error'}: ${e && e.message ? e.message : e}`];
    }
    if (Array.isArray(r)) return [!!r[0], r.length > 1 && r[1] !== null && r[1] !== undefined ? String(r[1]) : ''];
    return [!!r, ''];
  }

  Object.assign(T, { DECLS, declarations, NOT_HERE, MOVES, CHECKS, verdict, countWords, body, frontMatter, splitLines,
    applyChanges, changeProblems, epochFor });
  if (typeof module === 'object' && module.exports) module.exports = T;
})(typeof globalThis !== 'undefined' ? globalThis : this);
