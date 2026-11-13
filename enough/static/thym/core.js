/* Thym's runtime in the page, part 1 of 3: bytes, digests, the canonical dump, values and folders.
 *
 * The Python reference is enough/thym/values.py, folder.py and macrocosm.dump; this file mirrors them (THYM 12.6:
 * "a JavaScript runtime that passes the conformance suite is a conforming runtime"). A classic script with no
 * dependencies: in the page it is loaded before moves.js and runtime.js and fills `globalThis.ThymJS`; under node
 * `require` gives the same object.
 *
 * Numbers are integers, as Thym's are. What JSON cannot carry (a date, a float inside a loaded volume, a mapping
 * whose keys are not plain strings) arrives tagged from the host (enough/thym/bundle.py) and is revived here into
 * ThymDate, ThymFloat and Map, so the dump, and so every digest, comes out as Python's does.
 */
(function (root) {
  'use strict';
  const T = root.ThymJS = root.ThymJS || {};

  // ---------------------------------------------------------------------------------------------------------------
  // Text and bytes
  // ---------------------------------------------------------------------------------------------------------------

  const ENC = new TextEncoder();
  const utf8 = (s) => ENC.encode(String(s));
  const decodeSig = (b) => new TextDecoder('utf-8', { fatal: false, ignoreBOM: false }).decode(b);   // utf-8-sig
  const decodeKeep = (b) => new TextDecoder('utf-8', { fatal: false, ignoreBOM: true }).decode(b);   // utf-8
  const isUtf8 = (b) => { try { new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(b); return true; } catch (e) { return false; } };

  function concatBytes(parts) {
    let n = 0;
    for (const p of parts) n += p.length;
    const out = new Uint8Array(n);
    let at = 0;
    for (const p of parts) { out.set(p, at); at += p.length; }
    return out;
  }

  const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  function fromBase64(s) {
    const clean = String(s || '').replace(/[^A-Za-z0-9+/]/g, '');
    const out = new Uint8Array(Math.floor(clean.length * 3 / 4));
    let buf = 0, bits = 0, at = 0;
    for (const c of clean) {
      buf = (buf << 6) | B64.indexOf(c);
      bits += 6;
      if (bits >= 8) { bits -= 8; out[at++] = (buf >> bits) & 0xff; }
    }
    return out.subarray(0, at);
  }
  function toBase64(b) {
    let out = '';
    for (let i = 0; i < b.length; i += 3) {
      const n = (b[i] << 16) | ((b[i + 1] || 0) << 8) | (b[i + 2] || 0);
      out += B64[(n >> 18) & 63] + B64[(n >> 12) & 63] + (i + 1 < b.length ? B64[(n >> 6) & 63] : '=') +
        (i + 2 < b.length ? B64[n & 63] : '=');
    }
    return out;
  }

  // sha256, synchronous, over bytes (FIPS 180-4)
  const K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98,
    0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8,
    0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819,
    0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
    0xc67178f2]);
  function sha256(bytes) {
    if (typeof bytes === 'string') bytes = utf8(bytes);
    const len = bytes.length;
    const padded = new Uint8Array(((len + 9 + 63) >> 6) << 6);
    padded.set(bytes);
    padded[len] = 0x80;
    const bitsHi = Math.floor(len / 0x20000000), bitsLo = (len << 3) >>> 0;
    const dv = new DataView(padded.buffer);
    dv.setUint32(padded.length - 8, bitsHi);
    dv.setUint32(padded.length - 4, bitsLo);
    const H = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
      0x5be0cd19]);
    const W = new Uint32Array(64);
    for (let off = 0; off < padded.length; off += 64) {
      for (let i = 0; i < 16; i++) W[i] = dv.getUint32(off + i * 4);
      for (let i = 16; i < 64; i++) {
        const a = W[i - 15], b = W[i - 2];
        const s0 = ((a >>> 7) | (a << 25)) ^ ((a >>> 18) | (a << 14)) ^ (a >>> 3);
        const s1 = ((b >>> 17) | (b << 15)) ^ ((b >>> 19) | (b << 13)) ^ (b >>> 10);
        W[i] = (W[i - 16] + s0 + W[i - 7] + s1) >>> 0;
      }
      let a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (let i = 0; i < 64; i++) {
        const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
        const ch = (e & f) ^ (~e & g);
        const t1 = (h + S1 + ch + K[i] + W[i]) >>> 0;
        const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
        const mj = (a & b) ^ (a & c) ^ (b & c);
        const t2 = (S0 + mj) >>> 0;
        h = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      H[0] += a; H[1] += b; H[2] += c; H[3] += d; H[4] += e; H[5] += f; H[6] += g; H[7] += h;
    }
    let hex = '';
    for (const x of H) hex += x.toString(16).padStart(8, '0');
    return hex;
  }

  // Python's string helpers, over code points where Python counts them
  const cps = (s) => Array.from(String(s));
  const cpLen = (s) => cps(s).length;
  const cpSlice = (s, a, b) => cps(s).slice(a, b).join('');
  const PY_WS = ' \t\n\r\x0b\x0c\x1c\x1d\x1e\x1f\x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008' +
    '\u2009\u200a\u2028\u2029\u202f\u205f\u3000';
  const isPyWs = (c) => PY_WS.includes(c);
  function pyStrip(s, chars) {
    const set = chars === undefined ? PY_WS : chars;
    const a = cps(s);
    let i = 0, j = a.length;
    while (i < j && set.includes(a[i])) i++;
    while (j > i && set.includes(a[j - 1])) j--;
    return a.slice(i, j).join('');
  }
  function pyRstrip(s, chars) {
    const set = chars === undefined ? PY_WS : chars;
    const a = cps(s);
    let j = a.length;
    while (j > 0 && set.includes(a[j - 1])) j--;
    return a.slice(0, j).join('');
  }
  function pyLstrip(s, chars) {
    const set = chars === undefined ? PY_WS : chars;
    const a = cps(s);
    let i = 0;
    while (i < a.length && set.includes(a[i])) i++;
    return a.slice(i).join('');
  }
  /** `str.split()` with no argument: runs of whitespace, no empty pieces. */
  function pySplitWs(s) {
    const out = [];
    let cur = '';
    for (const c of cps(s)) {
      if (isPyWs(c)) { if (cur) { out.push(cur); cur = ''; } } else cur += c;
    }
    if (cur) out.push(cur);
    return out;
  }
  /** `str.splitlines()`. */
  function pySplitlines(s) {
    const out = [];
    const re = /\r\n|[\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]/g;
    let last = 0, m;
    while ((m = re.exec(s)) !== null) { out.push(s.slice(last, m.index)); last = m.index + m[0].length; }
    if (last < s.length) out.push(s.slice(last));
    return out;
  }
  const fold = (s) => pySplitWs(String(s)).join(' ');
  /** Bytes compared as Python compares them, for sorting paths by their UTF-8 bytes. */
  function cmpBytes(a, b) {
    const x = utf8(a), y = utf8(b);
    for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] - y[i];
    return x.length - y.length;
  }
  /** Strings compared by code point, as Python's `<` does. */
  function cmpStr(a, b) {
    const x = cps(a), y = cps(b);
    for (let i = 0; i < Math.min(x.length, y.length); i++) {
      const p = x[i].codePointAt(0), q = y[i].codePointAt(0);
      if (p !== q) return p - q;
    }
    return x.length - y.length;
  }

  // ---------------------------------------------------------------------------------------------------------------
  // The loaded data JSON cannot carry
  // ---------------------------------------------------------------------------------------------------------------

  class ThymDate {
    /** A date (`kind` date, `yaml` its isoformat) or a datetime (`yaml` isoformat with a space, `iso` with a T). */
    constructor(kind, yaml, iso) { this.kind = kind; this.yaml = yaml; this.iso = iso || yaml; }
    isoformat() { return this.iso; }
    get year() { return parseInt(this.iso.slice(0, 4), 10); }
    toString() { return this.iso; }
  }
  ThymDate.fromDate = (d) => {
    const iso = d.toISOString().slice(0, 10);
    return new ThymDate('date', iso, iso);
  };
  class ThymFloat {
    constructor(text) { this.text = text; }
    toString() { return this.text; }
  }

  /** Tagged JSON from the host back into values the dump spells as Python does. */
  function revive(x) {
    if (Array.isArray(x)) return x.map(revive);
    if (x && typeof x === 'object') {
      if (typeof x.$date === 'string') return new ThymDate('date', x.$date, x.$date);
      if (typeof x.$datetime === 'string') return new ThymDate('datetime', x.$datetime, x.iso || x.$datetime);
      if (typeof x.$float === 'string') return new ThymFloat(x.$float);
      if (Array.isArray(x.$map)) {
        const m = new Map();
        for (const [k, v] of x.$map) m.set(revive(k), revive(v));
        return m;
      }
      const out = {};
      for (const k of Object.keys(x)) out[k] = revive(x[k]);
      return out;
    }
    return x;
  }

  const isMap = (x) => x instanceof Map;
  const isDict = (x) => x !== null && typeof x === 'object' && !Array.isArray(x) && !(x instanceof ThymDate) &&
    !(x instanceof ThymFloat) && !(x instanceof Uint8Array) && (isMap(x) || Object.getPrototypeOf(x) === Object.prototype);
  const entries = (d) => (isMap(d) ? Array.from(d.entries()) : Object.entries(d));
  const has = (d, k) => (isMap(d) ? d.has(k) : Object.prototype.hasOwnProperty.call(d, k));
  /** `dict.get(k)`: undefined is None. */
  const get = (d, k) => {
    if (!isDict(d)) return null;
    const v = isMap(d) ? d.get(k) : (Object.prototype.hasOwnProperty.call(d, k) ? d[k] : undefined);
    return v === undefined ? null : v;
  };
  const isInt = (x) => typeof x === 'number' && Number.isInteger(x);

  // ---------------------------------------------------------------------------------------------------------------
  // The canonical dump: macrocosm.dump, which is PyYAML's safe_dump(sort_keys=False, allow_unicode=True,
  // width=110, default_flow_style=False) with the declaration key first. Ported from PyYAML 6's representer,
  // serializer (implicit resolution) and emitter, for block style, so a digest is the same in both languages.
  // ---------------------------------------------------------------------------------------------------------------

  const DECLARATION_KEYS = ['oes', 'manifest', 'cosm', 'opi', 'comprise'];
  const RESOLVERS = [
    ['bool', /^(?:yes|Yes|YES|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF)$/, 'yYnNtTfFoO'],
    ['float', /^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+][0-9]+)?|\.[0-9][0-9_]*(?:[eE][-+][0-9]+)?|[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$/, '-+0123456789.'],
    ['int', /^(?:[-+]?0b[0-1_]+|[-+]?0[0-7_]+|[-+]?(?:0|[1-9][0-9_]*)|[-+]?0x[0-9a-fA-F_]+|[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+)$/, '-+0123456789'],
    ['merge', /^(?:<<)$/, '<'],
    ['null', /^(?:~|null|Null|NULL|)$/, '~nN'],
    ['timestamp', /^(?:[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]|[0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?(?:[Tt]|[ \t]+)[0-9][0-9]?:[0-9][0-9]:[0-9][0-9](?:\.[0-9]*)?(?:[ \t]*(?:Z|[-+][0-9][0-9]?(?::[0-9][0-9])?))?)$/, '0123456789'],
    ['value', /^(?:=)$/, '='],
    ['yaml', /^(?:!|&|\*)$/, '!&*'],
  ];
  /** The tag a plain scalar resolves to (Python's `re.match` with `$`, which also matches before a final LF). */
  function resolvePlain(value) {
    for (const [tag, rx, first] of RESOLVERS) {
      if (value === '' ? tag !== 'null' : !first.includes(value[0])) continue;
      if (rx.test(value) || (value.endsWith('\n') && rx.test(value.slice(0, -1)))) return tag;
    }
    return 'str';
  }

  function events(data) {
    const out = [{ t: 'StreamStart' }, { t: 'DocumentStart' }];
    const node = (x) => {
      if (x === null || x === undefined) out.push({ t: 'Scalar', value: 'null', implicit: [true, false] });
      else if (typeof x === 'boolean') out.push({ t: 'Scalar', value: x ? 'true' : 'false', implicit: [true, false] });
      else if (typeof x === 'number') {
        if (!Number.isInteger(x)) throw new Error('the dump takes no floats but those it was given tagged');
        out.push({ t: 'Scalar', value: String(x), implicit: [true, false] });
      } else if (typeof x === 'string') {
        out.push({ t: 'Scalar', value: x, implicit: [resolvePlain(x) === 'str', true] });
      } else if (x instanceof ThymDate) out.push({ t: 'Scalar', value: x.yaml, implicit: [true, false] });
      else if (x instanceof ThymFloat) out.push({ t: 'Scalar', value: x.text, implicit: [true, false] });
      else if (Array.isArray(x)) {
        out.push({ t: 'SequenceStart' });
        for (const m of x) node(m);
        out.push({ t: 'SequenceEnd' });
      } else if (isDict(x)) {
        out.push({ t: 'MappingStart' });
        for (const [k, v] of entries(x)) { node(k); node(v); }
        out.push({ t: 'MappingEnd' });
      } else if (x && x.isThymValue) node(plain(x));
      else throw new Error('the dump cannot represent ' + Object.prototype.toString.call(x));
    };
    node(data);
    out.push({ t: 'DocumentEnd' }, { t: 'StreamEnd' });
    return out;
  }

  const BREAKS = '\n\x85\u2028\u2029';
  const WS0 = '\0 \t\r\n\x85\u2028\u2029';

  function analyze(scalar) {
    const s = cps(scalar);
    if (!s.length) {
      return { scalar: s, empty: true, multiline: false, allowFlowPlain: false, allowBlockPlain: true,
        allowSingle: true, allowDouble: true, allowBlock: false };
    }
    let blockInd = false, flowInd = false, lineBreaks = false, special = false;
    let leadingSpace = false, leadingBreak = false, trailingSpace = false, trailingBreak = false;
    let breakSpace = false, spaceBreak = false;
    if (scalar.startsWith('---') || scalar.startsWith('...')) { blockInd = true; flowInd = true; }
    let preceded = true;
    let followed = s.length === 1 || WS0.includes(s[1]);
    let prevSpace = false, prevBreak = false;
    for (let i = 0; i < s.length;) {
      const ch = s[i];
      if (i === 0) {
        if ('#,[]{}&*!|>\'"%@`'.includes(ch)) { flowInd = true; blockInd = true; }
        if ('?:'.includes(ch)) { flowInd = true; if (followed) blockInd = true; }
        if (ch === '-' && followed) { flowInd = true; blockInd = true; }
      } else {
        if (',?[]{}'.includes(ch)) flowInd = true;
        if (ch === ':') { flowInd = true; if (followed) blockInd = true; }
        if (ch === '#' && preceded) { flowInd = true; blockInd = true; }
      }
      if (BREAKS.includes(ch)) lineBreaks = true;
      const o = ch.codePointAt(0);
      if (!(ch === '\n' || (o >= 0x20 && o <= 0x7e))) {
        const uni = (o === 0x85 || (o >= 0xa0 && o <= 0xd7ff) || (o >= 0xe000 && o <= 0xfffd) ||
          (o >= 0x10000 && o < 0x10ffff)) && o !== 0xfeff;
        if (!uni) special = true;
      }
      if (ch === ' ') {
        if (i === 0) leadingSpace = true;
        if (i === s.length - 1) trailingSpace = true;
        if (prevBreak) breakSpace = true;
        prevSpace = true; prevBreak = false;
      } else if (BREAKS.includes(ch)) {
        if (i === 0) leadingBreak = true;
        if (i === s.length - 1) trailingBreak = true;
        if (prevSpace) spaceBreak = true;
        prevSpace = false; prevBreak = true;
      } else { prevSpace = false; prevBreak = false; }
      i += 1;
      preceded = WS0.includes(ch);
      followed = i + 1 >= s.length || WS0.includes(s[i + 1]);
    }
    let fp = true, bp = true, sq = true, blk = true;
    if (leadingSpace || leadingBreak || trailingSpace || trailingBreak) { fp = false; bp = false; }
    if (trailingSpace) blk = false;
    if (breakSpace) { fp = false; bp = false; sq = false; }
    if (spaceBreak || special) { fp = false; bp = false; sq = false; blk = false; }
    if (lineBreaks) { fp = false; bp = false; }
    if (flowInd) fp = false;
    if (blockInd) bp = false;
    return { scalar: s, empty: false, multiline: lineBreaks, allowFlowPlain: fp, allowBlockPlain: bp,
      allowSingle: sq, allowDouble: true, allowBlock: blk };
  }

  const ESC = { '\0': '0', '\x07': 'a', '\x08': 'b', '\x09': 't', '\x0a': 'n', '\x0b': 'v', '\x0c': 'f', '\x0d': 'r',
    '\x1b': 'e', '"': '"', '\\': '\\', '\x85': 'N', '\xa0': '_', '\u2028': 'L', '\u2029': 'P' };

  class Emitter {
    constructor(evs) {
      this.events = evs; this.pos = 0; this.out = [];
      this.states = []; this.state = this.expectStreamStart;
      this.indents = []; this.indent = null; this.flowLevel = 0;
      this.rootContext = false; this.sequenceContext = false; this.mappingContext = false; this.simpleKeyContext = false;
      this.line = 0; this.column = 0; this.whitespace = true; this.indention = true; this.openEnded = false;
      this.bestIndent = 2; this.bestWidth = 110; this.analysis = null; this.style = null;
    }
    run() {
      while (this.pos < this.events.length) {
        this.event = this.events[this.pos++];
        this.state();
        this.event = null;
      }
      return this.out.join('');
    }
    next() { return this.events[this.pos]; }
    write(s) { this.out.push(s); }
    increaseIndent(flow, indentless) {
      this.indents.push(this.indent);
      if (this.indent === null) this.indent = flow ? this.bestIndent : 0;
      else if (!indentless) this.indent += this.bestIndent;
    }
    expectStreamStart() { this.state = this.expectFirstDocumentStart; }
    expectNothing() { throw new Error('expected nothing'); }
    expectFirstDocumentStart() { this.expectDocumentStart(true); }
    expectDocumentStart(first) {
      if (this.event.t === 'DocumentStart') {
        const implicit = first && !this.checkEmptyDocument();
        if (!implicit) { this.writeIndent(); this.writeIndicator('---', true); }
        this.state = this.expectDocumentRoot;
      } else if (this.event.t === 'StreamEnd') {
        if (this.openEnded) { this.writeIndicator('...', true); this.writeIndent(); }
        this.state = this.expectNothing;
      }
    }
    expectDocumentEnd() { this.writeIndent(); this.state = (f) => this.expectDocumentStart(false); }
    expectDocumentRoot() { this.states.push(this.expectDocumentEnd); this.expectNode(true, false, false, false); }
    expectNode(root, sequence, mapping, simpleKey) {
      this.rootContext = root; this.sequenceContext = sequence; this.mappingContext = mapping;
      this.simpleKeyContext = simpleKey;
      const t = this.event.t;
      if (t === 'Scalar') this.expectScalar();
      else if (t === 'SequenceStart') {
        if (this.flowLevel || this.checkEmptySequence()) this.expectFlowSequence(); else this.expectBlockSequence();
      } else if (t === 'MappingStart') {
        if (this.flowLevel || this.checkEmptyMapping()) this.expectFlowMapping(); else this.expectBlockMapping();
      } else throw new Error('expected a node, got ' + t);
    }
    expectScalar() {
      this.increaseIndent(true, false);
      this.processScalar();
      this.indent = this.indents.pop();
      this.state = this.states.pop();
    }
    expectFlowSequence() {
      this.writeIndicator('[', true, true);
      this.flowLevel += 1; this.increaseIndent(true, false);
      this.state = this.expectFirstFlowSequenceItem;
    }
    expectFirstFlowSequenceItem() {
      if (this.event.t === 'SequenceEnd') {
        this.indent = this.indents.pop(); this.flowLevel -= 1;
        this.writeIndicator(']', false); this.state = this.states.pop();
      } else {
        if (this.column > this.bestWidth) this.writeIndent();
        this.states.push(this.expectFlowSequenceItem); this.expectNode(false, true, false, false);
      }
    }
    expectFlowSequenceItem() {
      if (this.event.t === 'SequenceEnd') {
        this.indent = this.indents.pop(); this.flowLevel -= 1;
        this.writeIndicator(']', false); this.state = this.states.pop();
      } else {
        this.writeIndicator(',', false);
        if (this.column > this.bestWidth) this.writeIndent();
        this.states.push(this.expectFlowSequenceItem); this.expectNode(false, true, false, false);
      }
    }
    expectFlowMapping() {
      this.writeIndicator('{', true, true);
      this.flowLevel += 1; this.increaseIndent(true, false);
      this.state = this.expectFirstFlowMappingKey;
    }
    expectFirstFlowMappingKey() {
      if (this.event.t === 'MappingEnd') {
        this.indent = this.indents.pop(); this.flowLevel -= 1;
        this.writeIndicator('}', false); this.state = this.states.pop();
      } else this.flowMappingKey();
    }
    expectFlowMappingKey() {
      if (this.event.t === 'MappingEnd') {
        this.indent = this.indents.pop(); this.flowLevel -= 1;
        this.writeIndicator('}', false); this.state = this.states.pop();
      } else { this.writeIndicator(',', false); this.flowMappingKey(); }
    }
    flowMappingKey() {
      if (this.column > this.bestWidth) this.writeIndent();
      if (this.checkSimpleKey()) {
        this.states.push(this.expectFlowMappingSimpleValue); this.expectNode(false, false, true, true);
      } else {
        this.writeIndicator('?', true);
        this.states.push(this.expectFlowMappingValue); this.expectNode(false, false, true, false);
      }
    }
    expectFlowMappingSimpleValue() {
      this.writeIndicator(':', false);
      this.states.push(this.expectFlowMappingKey); this.expectNode(false, false, true, false);
    }
    expectFlowMappingValue() {
      if (this.column > this.bestWidth) this.writeIndent();
      this.writeIndicator(':', true);
      this.states.push(this.expectFlowMappingKey); this.expectNode(false, false, true, false);
    }
    expectBlockSequence() {
      const indentless = this.mappingContext && !this.indention;
      this.increaseIndent(false, indentless);
      this.state = () => this.expectBlockSequenceItem(true);
    }
    expectBlockSequenceItem(first) {
      if (!first && this.event.t === 'SequenceEnd') {
        this.indent = this.indents.pop(); this.state = this.states.pop();
      } else {
        this.writeIndent(); this.writeIndicator('-', true, false, true);
        this.states.push(() => this.expectBlockSequenceItem(false)); this.expectNode(false, true, false, false);
      }
    }
    expectBlockMapping() {
      this.increaseIndent(false, false);
      this.state = () => this.expectBlockMappingKey(true);
    }
    expectBlockMappingKey(first) {
      if (!first && this.event.t === 'MappingEnd') {
        this.indent = this.indents.pop(); this.state = this.states.pop();
      } else {
        this.writeIndent();
        if (this.checkSimpleKey()) {
          this.states.push(this.expectBlockMappingSimpleValue); this.expectNode(false, false, true, true);
        } else {
          this.writeIndicator('?', true, false, true);
          this.states.push(this.expectBlockMappingValue); this.expectNode(false, false, true, false);
        }
      }
    }
    expectBlockMappingSimpleValue() {
      this.writeIndicator(':', false);
      this.states.push(() => this.expectBlockMappingKey(false)); this.expectNode(false, false, true, false);
    }
    expectBlockMappingValue() {
      this.writeIndent(); this.writeIndicator(':', true, false, true);
      this.states.push(() => this.expectBlockMappingKey(false)); this.expectNode(false, false, true, false);
    }
    checkEmptySequence() { return this.event.t === 'SequenceStart' && this.next() && this.next().t === 'SequenceEnd'; }
    checkEmptyMapping() { return this.event.t === 'MappingStart' && this.next() && this.next().t === 'MappingEnd'; }
    checkEmptyDocument() {
      const e = this.next();
      return this.event.t === 'DocumentStart' && !!e && e.t === 'Scalar' && e.implicit && e.value === '' && false;
    }
    checkSimpleKey() {
      let length = 0;
      if (this.event.t === 'Scalar') {
        if (this.analysis === null) this.analysis = analyze(this.event.value);
        length += this.analysis.scalar.length;
      }
      return length < 128 && ((this.event.t === 'Scalar' && !this.analysis.empty && !this.analysis.multiline) ||
        this.checkEmptySequence() || this.checkEmptyMapping());
    }
    chooseScalarStyle() {
      if (this.analysis === null) this.analysis = analyze(this.event.value);
      const a = this.analysis;
      if (this.event.implicit[0]) {
        if (!(this.simpleKeyContext && (a.empty || a.multiline)) &&
          ((this.flowLevel && a.allowFlowPlain) || (!this.flowLevel && a.allowBlockPlain))) return '';
      }
      if (a.allowSingle && !(this.simpleKeyContext && a.multiline)) return "'";
      return '"';
    }
    processScalar() {
      if (this.analysis === null) this.analysis = analyze(this.event.value);
      if (this.style === null) this.style = this.chooseScalarStyle();
      const split = !this.simpleKeyContext;
      if (this.style === '"') this.writeDoubleQuoted(this.analysis.scalar, split);
      else if (this.style === "'") this.writeSingleQuoted(this.analysis.scalar, split);
      else this.writePlain(this.analysis.scalar, split);
      this.analysis = null; this.style = null;
    }
    writeIndicator(indicator, needWhitespace, whitespace, indention) {
      const data = (this.whitespace || !needWhitespace) ? indicator : ' ' + indicator;
      this.whitespace = !!whitespace;
      this.indention = this.indention && !!indention;
      this.column += data.length;
      this.openEnded = false;
      this.write(data);
    }
    writeIndent() {
      const indent = this.indent || 0;
      if (!this.indention || this.column > indent || (this.column === indent && !this.whitespace)) this.writeLineBreak();
      if (this.column < indent) {
        this.whitespace = true;
        this.write(' '.repeat(indent - this.column));
        this.column = indent;
      }
    }
    writeLineBreak(data) {
      this.whitespace = true; this.indention = true; this.line += 1; this.column = 0;
      this.write(data === undefined ? '\n' : data);
    }
    writeSingleQuoted(text, split) {
      this.writeIndicator("'", true);
      let spaces = false, breaks = false, start = 0, end = 0;
      while (end <= text.length) {
        const ch = end < text.length ? text[end] : null;
        if (spaces) {
          if (ch === null || ch !== ' ') {
            if (start + 1 === end && this.column > this.bestWidth && split && start !== 0 && end !== text.length) {
              this.writeIndent();
            } else {
              const data = text.slice(start, end).join('');
              this.column += end - start; this.write(data);
            }
            start = end;
          }
        } else if (breaks) {
          if (ch === null || !BREAKS.includes(ch)) {
            if (text[start] === '\n') this.writeLineBreak();
            for (const br of text.slice(start, end)) {
              if (br === '\n') this.writeLineBreak(); else this.writeLineBreak(br);
            }
            this.writeIndent();
            start = end;
          }
        } else if (ch === null || (' ' + BREAKS).includes(ch) || ch === "'") {
          if (start < end) {
            this.column += end - start; this.write(text.slice(start, end).join(''));
            start = end;
          }
        }
        if (ch === "'") { this.column += 2; this.write("''"); start = end + 1; }
        if (ch !== null) { spaces = ch === ' '; breaks = BREAKS.includes(ch); }
        end += 1;
      }
      this.writeIndicator("'", false);
    }
    writeDoubleQuoted(text, split) {
      this.writeIndicator('"', true);
      let start = 0, end = 0;
      while (end <= text.length) {
        const ch = end < text.length ? text[end] : null;
        const o = ch === null ? 0 : ch.codePointAt(0);
        if (ch === null || '"\\\x85\u2028\u2029\ufeff'.includes(ch) ||
          !((o >= 0x20 && o <= 0x7e) || (o >= 0xa0 && o <= 0xd7ff) || (o >= 0xe000 && o <= 0xfffd))) {
          if (start < end) { this.column += end - start; this.write(text.slice(start, end).join('')); start = end; }
          if (ch !== null) {
            let data;
            if (Object.prototype.hasOwnProperty.call(ESC, ch)) data = '\\' + ESC[ch];
            else if (o <= 0xff) data = '\\x' + o.toString(16).toUpperCase().padStart(2, '0');
            else if (o <= 0xffff) data = '\\u' + o.toString(16).toUpperCase().padStart(4, '0');
            else data = '\\U' + o.toString(16).toUpperCase().padStart(8, '0');
            this.column += data.length; this.write(data);
            start = end + 1;
          }
        }
        if (end > 0 && end < text.length - 1 && (ch === ' ' || start >= end) &&
          this.column + (end - start) > this.bestWidth && split) {
          const data = text.slice(start, end).join('') + '\\';
          if (start < end) start = end;
          this.column += data.length; this.write(data);
          this.writeIndent();
          this.whitespace = false; this.indention = false;
          if (text[start] === ' ') { this.column += 1; this.write('\\'); }
        }
        end += 1;
      }
      this.writeIndicator('"', false);
    }
    writePlain(text, split) {
      if (this.rootContext) this.openEnded = true;
      if (!text.length) return;
      if (!this.whitespace) { this.column += 1; this.write(' '); }
      this.whitespace = false; this.indention = false;
      let spaces = false, breaks = false, start = 0, end = 0;
      while (end <= text.length) {
        const ch = end < text.length ? text[end] : null;
        if (spaces) {
          if (ch !== ' ') {
            if (start + 1 === end && this.column > this.bestWidth && split) {
              this.writeIndent(); this.whitespace = false; this.indention = false;
            } else { this.column += end - start; this.write(text.slice(start, end).join('')); }
            start = end;
          }
        } else if (breaks) {
          if (ch === null || !BREAKS.includes(ch)) {
            if (text[start] === '\n') this.writeLineBreak();
            for (const br of text.slice(start, end)) {
              if (br === '\n') this.writeLineBreak(); else this.writeLineBreak(br);
            }
            this.writeIndent(); this.whitespace = false; this.indention = false;
            start = end;
          }
        } else if (ch === null || (' ' + BREAKS).includes(ch)) {
          this.column += end - start; this.write(text.slice(start, end).join(''));
          start = end;
        }
        if (ch !== null) { spaces = ch === ' '; breaks = BREAKS.includes(ch); }
        end += 1;
      }
    }
  }

  /** `macrocosm.dump`: COSM text for a mapping, the declaration key first. */
  function dump(mapping) {
    if (!isDict(mapping)) throw new TypeError('dump takes a mapping');
    let m = mapping;
    const ks = entries(m).map((e) => e[0]);
    const first = DECLARATION_KEYS.find((k) => ks.includes(k));
    if (first !== undefined && ks[0] !== first) {
      const out = {};
      out[first] = get(m, first);
      for (const [k, v] of entries(m)) if (k !== first) out[k] = v;
      m = out;
    }
    return new Emitter(events(m)).run();
  }
  /** `values.canonical`: the canonical bytes of a mapping. */
  const canonical = (mapping) => utf8(dump(plain(mapping)));

  /** `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`. */
  function canonicalJson(x) {
    const enc = (v) => {
      if (v === null || v === undefined) return 'null';
      if (typeof v === 'boolean') return v ? 'true' : 'false';
      if (typeof v === 'number') return String(v);
      if (typeof v === 'string') return jsonStr(v);
      if (v instanceof ThymDate) throw new TypeError('Object of type date is not JSON serializable');
      if (v instanceof ThymFloat) return v.text;
      if (Array.isArray(v)) return '[' + v.map(enc).join(',') + ']';
      const es = entries(v).map(([k, w]) => [String(k), w]).sort((a, b) => cmpStr(a[0], b[0]));
      return '{' + es.map(([k, w]) => jsonStr(k) + ':' + enc(w)).join(',') + '}';
    };
    return utf8(enc(plain(x)));
  }
  function jsonStr(s) {
    let out = '"';
    for (const c of s) {
      const o = c.codePointAt(0);
      if (c === '"') out += '\\"';
      else if (c === '\\') out += '\\\\';
      else if (c === '\n') out += '\\n';
      else if (c === '\r') out += '\\r';
      else if (c === '\t') out += '\\t';
      else if (c === '\b') out += '\\b';
      else if (c === '\f') out += '\\f';
      else if (o < 0x20) out += '\\u' + o.toString(16).padStart(4, '0');
      else out += c;
    }
    return out + '"';
  }

  // ---------------------------------------------------------------------------------------------------------------
  // Refusals
  // ---------------------------------------------------------------------------------------------------------------

  class Refusal {
    constructor(stage, check, message, line, file) {
      this.stage = stage; this.check = check; this.message = message;
      this.line = line === undefined ? null : line; this.file = file === undefined ? null : file;
      this.isRefusal = true;
    }
    toString() {
      const where = this.line ? `${this.file || '<program>'}:${this.line}` : (this.file || '<program>');
      return `${where}: refused at ${this.stage} (${this.check}): ${this.message}`;
    }
    toJSON() { return { stage: this.stage, check: this.check, message: this.message, line: this.line }; }
  }
  class MoveError extends Error {
    constructor(msg) { super(msg); this.isMoveError = true; }
  }

  // ---------------------------------------------------------------------------------------------------------------
  // Folders (folder.py)
  // ---------------------------------------------------------------------------------------------------------------

  function linesIn(text) {
    if (!text) return 0;
    return (text.split('\n').length - 1) + (text.endsWith('\n') ? 0 : 1);
  }
  function digestOf(rows) {
    const sorted = rows.slice().sort((a, b) => cmpBytes(a[0], b[0]));
    return sha256(concatBytes(sorted.map(([p, d]) => concatBytes([utf8(p), new Uint8Array([0]), utf8(d), new Uint8Array([10])]))));
  }
  class FolderError extends Error {}
  const entryName = (e) => e.path.split('/').pop();
  const entrySuffix = (e) => { const n = entryName(e); const i = n.lastIndexOf('.'); return i >= 0 ? n.slice(i + 1) : ''; };
  const entryDepth = (e) => e.path.split('/').length - 1;
  function memberFields(e, text) {
    return { path: e.path, name: entryName(e), suffix: entrySuffix(e), depth: entryDepth(e), size: e.size,
      sha256: e.sha256, binary: e.binary, lines: text !== null && text !== undefined ? linesIn(text) : null };
  }

  class Folder {
    constructor(path, entries, tree, opts) {
      opts = opts || {};
      this.path = path; this.entries = entries; this.tree = tree;
      this.commit = opts.commit || null; this.origin = opts.origin || null;
      this.texts_ = opts.texts || {}; this.binaries = opts.binaries || {}; this.fallbackName = opts.name || null;
      this.isFolder = true;
    }
    static fromBundle(b) {
      const binaries = {};
      for (const [p, s] of Object.entries(b.binaries || {})) binaries[p] = fromBase64(s);
      const es = (b.entries || []).map((e) => ({ path: e.path, sha256: e.sha256, size: e.size, binary: !!e.binary,
        tree: e.tree === undefined ? !e.binary : !!e.tree })).sort((x, y) => cmpBytes(x.path, y.path));
      return new Folder(b.path, es, b.tree, { commit: b.commit, origin: b.origin, texts: Object.assign({}, b.texts || {}),
        binaries, name: b.name });
    }
    get name() {
      const parts = pyRstrip(this.path, '/').split('/').filter((p) => p !== '.' && p !== '');
      if (parts.length && parts[parts.length - 1] !== '..') return parts[parts.length - 1];
      return this.fallbackName || this.path;
    }
    get files() { return this.entries.length; }
    get bytes() { return this.entries.reduce((n, e) => n + e.size, 0); }
    get lines() { return this.entries.filter((e) => !e.binary).reduce((n, e) => n + linesIn(this.text(e.path)), 0); }
    field(name) {
      if (['path', 'name', 'files', 'bytes', 'lines', 'tree', 'commit', 'origin'].includes(name)) {
        const v = this[name];
        return v === undefined ? null : v;
      }
      return null;
    }
    texts() { return this.entries.filter((e) => !e.binary); }
    entry(path) { return this.entries.find((e) => e.path === path) || null; }
    text(path) {
      if (Object.prototype.hasOwnProperty.call(this.texts_, path)) return this.texts_[path];
      const e = this.entry(path);
      if (e === null || e.binary) throw new FolderError(`${path} is no text file of ${this.path}`);
      throw new FolderError(`${path}: the page holds no text for it`);
    }
    raw(path) {
      const e = this.entry(path);
      if (e === null) throw new FolderError(`${path} is no file of ${this.path}`);
      if (Object.prototype.hasOwnProperty.call(this.texts_, path)) return utf8(this.texts_[path]);
      if (this.binaries[path]) {
        if (sha256(this.binaries[path]) !== e.sha256) throw new FolderError(`${path} changed after ${this.path} was read`);
        return this.binaries[path];
      }
      throw new FolderError(`${path} is a binary file of ${this.path}, and a snapshot holds no binary file's bytes`);
    }
    memberFields(e) { return memberFields(e, e.binary ? null : this.text(e.path)); }
    where(keep) {
      const kept = this.entries.filter((e) => keep(e));
      const rows = kept.filter((e) => e.tree).map((e) => [e.path, e.sha256]);
      const texts = {}, bins = {};
      for (const e of kept) {
        if (Object.prototype.hasOwnProperty.call(this.texts_, e.path)) texts[e.path] = this.texts_[e.path];
        if (this.binaries[e.path]) bins[e.path] = this.binaries[e.path];
      }
      return new Folder(this.path, kept, digestOf(rows), { commit: this.commit, origin: this.origin, texts,
        binaries: bins, name: this.fallbackName });
    }
    folders() {
      const subs = new Map();
      for (const e of this.entries) {
        const i = e.path.indexOf('/');
        if (i < 0) continue;
        const top = e.path.slice(0, i);
        if (!subs.has(top)) subs.set(top, []);
        subs.get(top).push({ path: e.path.slice(i + 1), sha256: e.sha256, size: e.size, binary: e.binary, tree: e.tree, full: e.path });
      }
      const out = [];
      for (const top of Array.from(subs.keys()).sort(cmpBytes)) {
        const es = subs.get(top);
        const texts = {}, bins = {};
        for (const e of es) {
          if (Object.prototype.hasOwnProperty.call(this.texts_, e.full)) texts[e.path] = this.texts_[e.full];
          if (this.binaries[e.full]) bins[e.path] = this.binaries[e.full];
        }
        const rows = es.filter((e) => e.tree).map((e) => [e.path, e.sha256]);
        const clean = es.map((e) => ({ path: e.path, sha256: e.sha256, size: e.size, binary: e.binary, tree: e.tree }));
        const path = (this.path !== '' && this.path !== '.') ? `${pyRstrip(this.path, '/')}/${top}` : top;
        out.push(new Folder(path, clean, digestOf(rows), { texts, binaries: bins }));
      }
      return out;
    }
    /** Every file's bytes, by path: what lands for a folder output (folder.write_tree). */
    tree_files() {
      const out = {};
      for (const e of this.entries) {
        const parts = e.path.split('/');
        if (!parts.length || parts.some((p) => p === '' || p === '.' || p === '..') || e.path.startsWith('/')) {
          throw new FolderError(`${e.path} is not a path inside the folder`);
        }
        const data = this.raw(e.path);
        if (sha256(data) !== e.sha256) throw new FolderError(`${e.path} is not the file the folder recorded`);
        out[e.path] = data;
      }
      return out;
    }
  }

  // ---------------------------------------------------------------------------------------------------------------
  // Volumes read by the host (a folder volume: its catalog and its items)
  // ---------------------------------------------------------------------------------------------------------------

  class Volume {
    constructor(b) {
      this.oes = b.oes || null;
      this.catalog = revive(b.catalog || {});
      this.items = (b.items || []).map((it) => ({ id: it.id, key: it.key, kind: it.kind, module: it.module,
        letter: it.letter, data: revive(it.data || {}) }));
      this.isVolume = true;
    }
  }

  // ---------------------------------------------------------------------------------------------------------------
  // Values (values.py)
  // ---------------------------------------------------------------------------------------------------------------

  const COSM_EXT = { package: 'package.cosm', morph: 'morph.cosm', context: 'context.cosm', plan: 'plan.cosm', trace: 'trace.cosm' };
  const HAND_MADE = () => ({ move: 'none' });
  const WORD = /^[a-z][a-z0-9-]*$/;
  const ID = /^(?:([^/]+(?:\/[^/]+)?)\/\/)?([A-Z]):([a-z][a-z0-9-]*)\//;
  T.manifests = T.manifests || {};               // minicosm -> {letter: module name}, from the host

  class Value {
    constructor(type, payload, opts) {
      opts = opts || {};
      this.type = type;
      this.payload = payload === undefined ? null : payload;
      this.path = opts.path === undefined ? null : opts.path;
      this.raw = opts.raw === undefined ? null : opts.raw;
      this.made = opts.made === undefined ? null : opts.made;
      this.origin = opts.origin === undefined ? null : opts.origin;
      this.state = opts.state === undefined ? null : opts.state;
      this.isThymValue = true;
    }
    copy(changes) {
      const v = new Value(this.type, this.payload, this);
      Object.assign(v, changes || {});
      return v;
    }
    bytes() {
      if (this.raw !== null) return this.raw;
      const p = this.payload;
      if (this.type === 'nothing' || p === null) return new Uint8Array(0);
      if (p instanceof Folder) return utf8(p.entries.map((e) => `${e.path}\0${e.sha256}\n`).join(''));
      if (p instanceof Uint8Array) return p;
      if (typeof p === 'string') return utf8(p);
      if (p instanceof Volume) throw new Error('a volume read by the host carries its catalog bytes');
      if (isDict(p)) return canonical(p);
      if (Array.isArray(p)) return utf8(p.map((m) => (m && m.isThymValue ? m.sha256 : sha256(scalarBytes(m)))).join('\n'));
      return scalarBytes(p);
    }
    get sha256() {
      if (this.payload instanceof Folder) return this.payload.tree;
      if (this._sha === undefined || this._shaOf !== this.payload) { this._sha = sha256(this.bytes()); this._shaOf = this.payload; }
      return this._sha;
    }
    get ext() {
      const p = this.payload;
      if (p instanceof Folder) return '';
      if (this.type === 'text' || this.type === 'short' || (this.type === 'atem' && typeof p === 'string')) return 'md';
      if (isDict(p) || p instanceof Volume || this.type === 'list') return COSM_EXT[this.type] || 'cosm';
      return 'txt';
    }
    writeBytes() {
      if (this.type === 'list' && this.raw === null) return canonical({ members: (this.payload || []).map((m) => plain(m)) });
      return this.bytes();
    }
    get isNothing() { return this.type === 'nothing'; }
    text() {
      if (typeof this.payload === 'string') return this.payload;
      if (this.raw !== null) return decodeSig(this.raw);
      if (this.type === 'atem' && isDict(this.payload) && typeof get(this.payload, 'line') === 'string') return get(this.payload, 'line');
      return decodeKeep(this.bytes());
    }
    mapping() {
      if (isDict(this.payload)) return this.payload;
      if (this.payload instanceof Volume) return this.payload.catalog;
      return null;
    }
    plain() {
      if (this.type === 'nothing') return null;
      if (['word', 'string', 'number', 'bool', 'date'].includes(this.type)) return this.payload;
      if (this.type === 'line' && typeof this.payload === 'string') return this.payload;
      if (this.type === 'list') return (this.payload || []).map((m) => (m && m.isThymValue ? m.plain() : m));
      return this;
    }
    field(name) {
      const p = this.payload;
      const o = this.origin;
      if (p instanceof Folder) return p.field(name);
      if (o && isDict(o.member)) return get(o.member, name);
      if (o && isDict(o.line)) return get(o.line, name);
      if (o && Object.prototype.hasOwnProperty.call(o, 'item') && isDict(p)) return itemField(p, name, o);
      if (p instanceof Volume) {
        if (has(p.catalog, name)) return get(p.catalog, name);
        return p.items.length === 1 ? get(p.items[0].data, name) : null;
      }
      if (isDict(p)) {
        const nodes = get(p, 'nodes');
        if (name !== 'nodes' && has(p, name)) return get(p, name);
        if (Array.isArray(nodes)) {
          const rows = nodes.filter(isDict);
          if (rows.length === 1) return itemField(rows[0], name, { item: true, oes: get(p, 'oes') });
        } else if (has(p, 'id')) return itemField(p, name, { item: true });
      }
      return null;
    }
  }
  const NOTHING = new Value('nothing');

  function scalarBytes(x) {
    if (typeof x === 'boolean') return utf8(x ? 'true' : 'false');
    if (x instanceof ThymDate) return utf8(x.iso);
    if (x === null || x === undefined) return new Uint8Array(0);
    return utf8(String(x));
  }

  /** `values.plain`: a deep copy that holds no Value. */
  function plain(v) {
    if (v && v.isThymValue) return plain(v.payload);
    if (v instanceof Folder || v instanceof Volume) return v;
    if (isMap(v)) { const m = new Map(); for (const [k, x] of v.entries()) m.set(k, plain(x)); return m; }
    if (isDict(v)) { const o = {}; for (const k of Object.keys(v)) o[k] = plain(v[k]); return o; }
    if (Array.isArray(v)) return v.map(plain);
    return v;
  }

  function wrap(x) {
    if (x && x.isThymValue) return x;
    if (x === null || x === undefined) return NOTHING;
    if (typeof x === 'boolean') return new Value('bool', x);
    if (isInt(x)) return new Value('number', x);
    if (typeof x === 'string') return new Value(WORD.test(x) ? 'word' : 'string', x);
    if (x instanceof ThymDate) return new Value('date', x);
    if (Array.isArray(x)) return new Value('list', x.map(wrap));
    if (isDict(x)) return new Value(Array.isArray(get(x, 'nodes')) ? 'volume' : 'item', x);
    return new Value('string', String(x));
  }

  function moduleName(minicosm, letter) {
    if (!letter) return letter === undefined ? null : letter;
    const names = minicosm ? T.manifests[minicosm] : null;
    if (!names) return letter;
    return names[letter] || letter;
  }
  function itemField(data, name, origin) {
    origin = origin || {};
    if (name === 'kind' || name === 'module') {
      if (origin[name] !== undefined && origin[name] !== null) return origin[name];
      const mt = ID.exec(String(get(data, 'id') || ''));
      if (mt) {
        if (name === 'kind') return mt[3];
        const oes = origin.oes;
        return moduleName(typeof oes === 'string' && oes.includes('/') ? oes.split('/')[0] : null, mt[2]);
      }
    }
    return get(data, name);
  }
  /** Python's truth of a value. */
  function truthy(x) {
    if (x === null || x === undefined || x === false || x === 0 || x === '') return false;
    if (Array.isArray(x)) return x.length > 0;
    if (isMap(x)) return x.size > 0;
    if (isDict(x)) return Object.keys(x).length > 0;
    return true;
  }
  function toldKey(data) {
    const span = get(data, 'span');
    let line = 1e9;
    if (isDict(span)) {
      const m = /\d+/.exec(truthy(get(span, 'lines')) ? pyStr(get(span, 'lines')) : '');
      if (m) line = parseInt(m[0], 10);
    }
    return [line, truthy(get(data, 'id')) ? pyStr(get(data, 'id')) : ''];
  }
  function sortTold(rows) {
    const keyed = rows.map((v, i) => [toldKey(v.payload), i, v]);
    keyed.sort((a, b) => (a[0][0] - b[0][0]) || cmpStr(a[0][1], b[0][1]) || (a[1] - b[1]));
    return keyed.map((k) => k[2]);
  }
  /** `str(x)` for the scalars a field holds. */
  function pyStr(x) {
    if (x === null || x === undefined) return 'None';
    if (typeof x === 'boolean') return x ? 'True' : 'False';
    if (x instanceof ThymDate) return x.kind === 'date' ? x.iso : x.yaml;
    if (x instanceof ThymFloat) return x.text;
    if (Array.isArray(x) || isDict(x)) return pyRepr(x);
    return String(x);
  }
  /** `repr(x)` for plain data, as a message may quote it. */
  function pyRepr(x) {
    if (x === null || x === undefined) return 'None';
    if (typeof x === 'boolean') return x ? 'True' : 'False';
    if (typeof x === 'number') return String(x);
    if (typeof x === 'string') {
      const q = x.includes("'") && !x.includes('"') ? '"' : "'";
      let out = q;
      for (const c of x) {
        if (c === q || c === '\\') out += '\\' + c;
        else if (c === '\n') out += '\\n';
        else if (c === '\r') out += '\\r';
        else if (c === '\t') out += '\\t';
        else if (c.codePointAt(0) < 0x20 || c.codePointAt(0) === 0x7f) out += '\\x' + c.codePointAt(0).toString(16).padStart(2, '0');
        else out += c;
      }
      return out + q;
    }
    if (x instanceof ThymDate) return x.kind === 'date' ? `datetime.date(${x.iso.split('-').map((n) => parseInt(n, 10)).join(', ')})` : x.yaml;
    if (x instanceof ThymFloat) return x.text;
    if (Array.isArray(x)) return '[' + x.map(pyRepr).join(', ') + ']';
    if (isDict(x)) return '{' + entries(x).map(([k, v]) => pyRepr(k) + ': ' + pyRepr(v)).join(', ') + '}';
    return String(x);
  }

  function folderMember(f, e) {
    const raw = f.raw(e.path);
    const text = decodeSig(raw);
    return new Value('text', text, { raw, made: { move: 'none', source: { folder: f.tree, path: e.path } },
      origin: { member: memberFields(e, f.text(e.path)), folder: f.tree } });
  }
  const folderValue = (f, path) => new Value('folder', f, { path: path === undefined ? null : path, made: HAND_MADE() });
  const entryItem = (f, e) => new Value('item', f.memberFields(e), { origin: { item: true, member: f.memberFields(e) } });
  const filterFolder = (value, keep) => {
    const f = value.payload;
    return folderValue(f.where((e) => !!keep(entryItem(f, e))), value.path);
  };

  function heading(text) {
    const s = pyLstrip(text, ' ');
    if (cpLen(text) - cpLen(s) > 3 || !s.startsWith('#')) return [0, null];
    const level = cpLen(s) - cpLen(pyLstrip(s, '#'));
    const rest = cpSlice(s, level);
    if (level > 6 || (rest && !(rest.startsWith(' ') || rest.startsWith('\t')))) return [0, null];
    let words = pyStrip(rest);
    while (words.endsWith('#') && (pyRstrip(words, '#') === '' || pyRstrip(words, '#').endsWith(' ') || pyRstrip(words, '#').endsWith('\t'))) {
      words = pyStrip(pyRstrip(words, '#'));
    }
    const i = words.indexOf(' ');
    const head = i >= 0 ? [words.slice(0, i), words.slice(i + 1)] : [words];
    if (head.length && /^\d+(?:\.\d+)*\.?$/.test(head[0])) words = head.length > 1 ? pyStrip(head[1]) : '';
    return [level, words];
  }
  function makeLine(text, number, source) {
    const [level, title] = heading(text);
    return new Value('line', text, { origin: { line: { number, level, title, blank: pyStrip(text) === '', source,
      sha256: sha256(utf8(text)) } } });
  }
  const CHANGE_DOES = ['replace', 'drop', 'insert-before', 'insert-after'];
  function makeChange(at, was, of, doWhat, lines) {
    if (!CHANGE_DOES.includes(doWhat)) throw new Error(`a change does one of ${CHANGE_DOES.join(', ')}, not ${doWhat}`);
    return new Value('change', { at, was: String(was), of: String(of), do: doWhat, lines: (lines || []).map(String) });
  }

  function members(value) {
    const p = value.payload;
    if (value.type === 'list') return (p || []).map((m) => (m && m.isThymValue ? m : wrap(m)));
    if (p instanceof Folder) return p.texts().map((e) => folderMember(p, e));
    if (p instanceof Volume) {
      const rows = p.items.map((it) => new Value('item', Object.assign({}, it.data), { origin: { item: true, volume: value,
        id: it.id, key: it.key, kind: it.kind, oes: p.oes, module: it.module, letter: it.letter } }));
      return sortTold(rows);
    }
    if (isDict(p) && Array.isArray(get(p, 'nodes'))) {
      const oes = get(p, 'oes');
      const rows = get(p, 'nodes').filter(isDict).map((n) => new Value('item', Object.assign({}, n),
        { origin: { item: true, volume: value, id: get(n, 'id'), oes } }));
      return sortTold(rows);
    }
    if ((value.type === 'short' || value.type === 'text') && typeof p === 'string') {
      return pySplitlines(p).filter((l) => pyStrip(l)).map((l) => new Value('short', l));
    }
    return null;
  }

  const itemId = (v) => {
    const o = v.origin || {};
    const iid = (o.id !== undefined && o.id !== null && o.id !== '') ? o.id : get(v.mapping() || {}, 'id');
    return iid ? String(iid) : null;
  };
  const itemKey = (v) => { const k = (v.origin || {}).key; return k ? String(k) : itemId(v); };
  function isWithheld(withheld, v) {
    if (!withheld || !withheld.size) return false;
    const key = itemKey(v);
    if (key !== null && withheld.has(key)) return true;
    const iid = itemId(v);
    const held = iid !== null ? withheld.get(iid) : null;
    return !!(held && held.isThymValue && held.isNothing);
  }

  function stamp(value, made, pending) {
    if (value.type === 'nothing') return value;
    const out = value.copy({ made: Object.assign({}, made), state: pending ? 'pending' : value.state });
    if (value.raw === null && isDict(value.payload)) {
      const p = plain(value.payload);
      const pend = (it) => { if (pending && isDict(get(it, 'provenance'))) get(it, 'provenance').state = 'pending'; };
      if (Array.isArray(get(p, 'nodes'))) {
        for (const n of get(p, 'nodes')) {
          if (isDict(n)) { if (!has(n, 'made')) n.made = Object.assign({}, made); pend(n); }
        }
      } else if (has(p, 'id') && has(p, 'type')) { p.made = Object.assign({}, made); pend(p); }
      out.payload = p;
    }
    return out;
  }

  function digestRow(name, value, path) {
    const row = { name: String(name), sha256: value.sha256 };
    const p = path !== undefined && path !== null ? path : (value.path !== null ? value.path : null);
    if (p) row.path = p;
    return row;
  }

  /** One input as the host read it (bundle.py's `value_bundle`). */
  function fromBundle(b) {
    const raw = b.raw ? fromBase64(b.raw) : null;
    if (b.folder) return folderValue(Folder.fromBundle(b.folder), b.path || null);
    if (b.volume) return new Value(b.type, new Volume(b.volume), { raw, made: HAND_MADE() });
    if (b.data !== undefined) return new Value(b.type, revive(b.data), { raw, made: HAND_MADE() });
    if (typeof b.text === 'string') return new Value(b.type, b.text, { raw, made: HAND_MADE() });
    throw new Error('an input the page cannot read');
  }

  Object.assign(T, {
    utf8, decodeSig, decodeKeep, isUtf8, concatBytes, fromBase64, toBase64, sha256, cps, cpLen, cpSlice, pyStrip,
    pyRstrip, pyLstrip, pySplitWs, pySplitlines, fold, cmpBytes, cmpStr, isPyWs, ThymDate, ThymFloat, revive, isDict,
    isMap, entries, has, get, isInt, dump, canonical, canonicalJson, resolvePlain, Refusal, MoveError, Folder,
    FolderError, Volume, Value, NOTHING, plain, wrap, itemField, members, itemId, itemKey, isWithheld, stamp,
    digestRow, fromBundle, folderMember, folderValue, filterFolder, makeLine, makeChange, CHANGE_DOES, linesIn,
    pyStr, pyRepr, HAND_MADE, moduleName, truthy,
  });
  if (typeof module === 'object' && module.exports) module.exports = T;
})(typeof globalThis !== 'undefined' ? globalThis : this);
