/* Thym's runtime in the page, part 3 of 3: the statement reader, the program reader and the walk.
 *
 * A port of enough/thym/run.py and trace.py, run as Python runs a plan in agent-free mode: every deterministic node
 * runs here, and a plan with a node that asks a model is refused at plan time with the words Python gives
 * ("3 steps ask a model on the local route, the first `\u2026` (line 13); agent-free is on"). Nothing is written to a
 * disk: what would land under `outputs/` is returned as bytes, with the trace.
 *
 *   ThymJS.run({plan, program, inputs, decls, manifests, version, runId, now, environment}) ->
 *     {ok, outcome, refusal, runId, trace, traceText, files, outputs, readings}
 *
 * `plan` is the plan volume as JSON (POST /api/thym/plan's `plan`), `program` the program's source text (GET
 * /api/thym/program's `source`) or its program volume, `inputs` each input as enough/thym/bundle.py reads it. The
 * other keys are optional. See docs/v070-j1-runtime.md.
 */
(function (root) {
  'use strict';
  const T = root.ThymJS;
  const { Value, NOTHING, Refusal, MoveError, get, has, isDict, entries, wrap, members, plain, stamp, digestRow,
    filterFolder, itemId, itemKey, ThymDate, cps, cpLen, cpSlice, pyStrip, pyRstrip, pySplitWs, canonical, dump, sha256,
    truthy } = T;

  const MODIFIERS = ['as', 'by', 'with', 'to', 'against', 'of', 'in', 'where', 'marked', 'before', 'after'];
  const UNITS = ['words', 'sentences'];
  const COND_WORDS = ['is', 'in', 'has', 'covers', 'and', 'or', 'not', 'then', 'else', 'where', 'marked'];
  const KEYWORDS = new Set(['thym', 'use', 'program', 'move', 'morph', 'context', 'end', 'why', 'must', 'decided',
    'takes', 'gives', 'let', 'assert', 'if', 'then', 'else', 'for', 'each', 'in', 'where', 'emit', 'give', 'withhold',
    'as', 'by', 'with', 'to', 'against', 'of', 'marked', 'is', 'not', 'and', 'or', 'has', 'covers', 'keep', 'keeps',
    'contract', 'depth', 'before', 'after']);
  const ENGINE_RANK = { skipped: 0, code: 1, rules: 2 };
  const RUNTIME_FAULT = 'a fault of the runtime, not of the program';
  /** How many operands each move the page runs takes (Python raises on another count; so does the page). */
  const ARITY = { count: 1, words: 1, digest: 1, trace: 0, lines: 0, replace: 1, drop: 1, insert: 1, edit: 1, join: 1,
    say: 1, folders: 0, project: 1, band: 1, mark: 1, withhold: 1 };

  // -------------------------------------------------------------------------------------------------------------
  // The reader: one statement, as a node's name or a step's text holds it
  // -------------------------------------------------------------------------------------------------------------

  class ReadError extends Error {}

  function stripComment(line) {
    let inStr = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (c === '\\' && inStr) { i += 1; continue; }
      if (c === '"') inStr = !inStr;
      else if (!inStr && line.startsWith('--', i)) return line.slice(0, i);
    }
    return line;
  }

  const TOKEN = /(\s+)|("(?:[^"\\\n]|\\[^\n])*")|(oes:[^\s,\])]+)|(\d{4}-\d{2}-\d{2}(?![\w-]))|(\d+)|([A-Za-z_][A-Za-z0-9_-]*)|([()[\],.:=<>])/y;
  const KINDS = [null, 'ws', 'string', 'uri', 'date', 'int', 'name', 'punct'];
  function tokenize(text) {
    const out = [];
    text = stripComment(text);
    let pos = 0;
    while (pos < text.length) {
      TOKEN.lastIndex = pos;
      const m = TOKEN.exec(text);
      if (!m) throw new ReadError(`cannot read ${T.pyRepr(text.slice(pos, pos + 12))}`);
      let kind = '';
      for (let g = 1; g < KINDS.length; g++) if (m[g] !== undefined) { kind = KINDS[g]; break; }
      if (kind !== 'ws') out.push([kind, m[0]]);
      pos = TOKEN.lastIndex;
    }
    out.push(['end', '']);
    return out;
  }
  const unquote = (s) => s.slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, '\\');
  const nameOf = (e) => (e && e.k === 'Name' ? e.name : String(e));
  class Amount {
    constructor(n, unit) { this.n = n; this.unit = unit; this.isAmount = true; }
    toDict() { return { n: this.n, unit: this.unit }; }
  }

  class Reader {
    constructor(text, moves, inMoves, whereMoves) {
      this.text = text; this.toks = tokenize(text); this.i = 0;
      this.moves = moves; this.inMoves = inMoves || new Set(); this.whereMoves = whereMoves || new Set();
    }
    peek(k) { return this.toks[Math.min(this.i + (k || 0), this.toks.length - 1)]; }
    take() { const t = this.toks[this.i]; if (t[0] !== 'end') this.i += 1; return t; }
    at(text, k) { const t = this.peek(k); return (t[0] === 'name' || t[0] === 'punct') && t[1] === text; }
    expect(text) {
      if (!this.at(text)) throw new ReadError(`expected ${T.pyRepr(text)}, found ${T.pyRepr(this.peek()[1] || 'the end')}`);
      this.take();
    }
    name() {
      const t = this.take();
      if (t[0] !== 'name') throw new ReadError(`expected a name, found ${T.pyRepr(t[1] || 'the end')}`);
      return t[1];
    }
    atEnd() { return this.peek()[0] === 'end'; }
    atTrailer() { return this.at(',') && this.at('for', 1) && this.at('each', 2); }
    atMemberTrailer() { return this.at(',') && this.at('for', 1) && this.peek(2)[0] === 'name' && this.at('=', 3); }
    atSideCall() {
      if (!this.atMove()) return false;
      const [kind, text] = this.peek(1);
      if (['string', 'int', 'date', 'uri'].includes(kind)) return true;
      if (kind === 'punct') return text === '(' || text === '[';
      if (kind !== 'name') return false;
      if (MODIFIERS.includes(text)) return !['in', 'where', 'marked'].includes(text);
      return !KEYWORDS.has(text) || ['true', 'false', 'nothing'].includes(text);
    }
    atModifier() { const t = this.peek(); return t[0] === 'name' && MODIFIERS.includes(t[1]); }
    atMove() { const t = this.peek(); return t[0] === 'name' && this.moves.has(t[1]) && !this.at('.', 1); }
    span(a, b) { return this.toks.slice(a, b).filter((t) => t[0] !== 'end').map((t) => t[1]).join(' '); }

    statement() {
      const st = this.stmt();
      if (this.atTrailer()) { this.take(); st.loop = this.forHeader(); } else if (this.atMemberTrailer()) {
        this.take(); this.take();
        const v = this.name();
        this.expect('=');
        st.member = [v, this.primary()];
      }
      if (!this.atEnd()) throw new ReadError(`unexpected ${T.pyRepr(this.peek()[1])}`);
      st.text = this.text;
      return st;
    }
    stmt() {
      const S = (form, o) => Object.assign({ k: 'Stmt', form, expr: null, cond: null, name: null, slot: null, message: null,
        loop: null, text: '', member: null }, o || {});
      if (this.at('emit')) {
        this.take();
        let slot = null;
        if (this.peek()[0] === 'name' && this.at(':', 1)) { slot = this.name(); this.take(); }
        return S('emit', { expr: this.expr(), slot });
      }
      if (this.at('give')) {
        this.take();
        let label = null;
        if (this.peek()[0] === 'name' && this.at(':', 1)) { label = this.name(); this.take(); }
        return S('give', { expr: this.expr(), slot: label });
      }
      if (this.at('let')) {
        this.take();
        const nm = this.name();
        this.expect('=');
        if (this.at('for') && this.at('each', 1)) return S('for', { loop: this.forHeader(), name: nm });
        return S('let', { expr: this.expr(), name: nm });
      }
      if (this.at('keep') && !this.atMove()) { this.take(); return S('keep', { expr: this.expr() }); }
      if (this.at('assert')) {
        this.take();
        const cond = this.cond();
        let msg = null;
        if (this.at('else')) {
          this.take();
          const t = this.take();
          if (t[0] !== 'string') throw new ReadError('assert ... else takes a string');
          msg = unquote(t[1]);
        }
        return S('assert', { cond, message: msg });
      }
      if (this.at('if')) {
        this.take();
        const cond = this.cond();
        if (this.at('then')) this.take();
        return S('if', { cond });
      }
      if (this.at('for') && this.at('each', 1)) return S('for', { loop: this.forHeader() });
      return S('effect', { expr: this.expr() });
    }
    forHeader() {
      this.expect('for'); this.expect('each');
      const v = this.name();
      this.expect('in');
      const coll = this.atMove() ? this.call(false, true) : this.primary();
      let cond = null;
      if (this.at('where')) { this.take(); cond = this.cond(); }
      return { k: 'Loop', var: v, coll, cond };
    }
    expr() {
      if (this.atMove()) return this.call();
      const a = this.i;
      let p = this.primary();
      if (this.at('where')) {
        this.take();
        const c0 = this.i;
        const cond = this.cond();
        p = { k: 'Filter', base: p, cond, text: this.span(c0, this.i) || this.span(a, this.i) };
      }
      if (this.at('marked')) { this.take(); p = { k: 'Call', move: 'mark', operands: [p], mods: { as: this.name() } }; }
      return p;
    }
    call(side, loop) {
      const move = this.name();
      const operands = [];
      if (!(this.atEnd() || this.atModifier() || this.at(')') || this.at(']') || this.at(',') || this.at('then') ||
        this.at('else') || (side && (COND_WORDS.includes(this.peek()[1]) || ['<', '>', '='].includes(this.peek()[1]))))) {
        operands.push(this.primary());
        while (this.at(',') && !this.atTrailer() && !this.atMemberTrailer()) { this.take(); operands.push(this.primary()); }
      }
      const mods = {};
      while (this.atModifier()) {
        if (side && this.at('in') && !this.inMoves.has(move)) break;
        if (loop && this.at('where') && !this.whereMoves.has(move)) break;
        const w = this.take()[1];
        if (w === 'as') mods.as = this.wordOrList();
        else if (w === 'by' || w === 'marked') mods[w] = this.name();
        else if (w === 'to') {
          const t = this.take();
          if (t[0] !== 'int') throw new ReadError('to takes a number and a unit: to 300 words');
          const unit = this.name();
          if (!UNITS.includes(unit)) throw new ReadError(`to takes words or sentences, not ${unit}`);
          mods.to = new Amount(parseInt(t[1], 10), unit);
        } else if (w === 'where') {
          const c0 = this.i;
          const cond = this.cond();
          mods.where = [cond, this.span(c0, this.i)];
        } else mods[w] = this.atMove() ? this.call(false, loop) : this.primary();
      }
      return { k: 'Call', move, operands, mods };
    }
    wordOrList() {
      if (this.at('[')) {
        const lst = this.primary(true);
        return lst.items.map((m) => (m.k === 'Lit' ? m.value.payload : nameOf(m)));
      }
      const t = this.take();
      if (t[0] === 'string') return unquote(t[1]);
      if (t[0] !== 'name') throw new ReadError(`as takes a word or a list of words, not ${T.pyRepr(t[1])}`);
      return t[1];
    }
    primary() {
      const [kind, text] = this.take();
      let p;
      if (kind === 'punct' && text === '(') { p = this.expr(); this.expect(')'); } else if (kind === 'punct' && text === '[') {
        const items = [];
        while (!this.at(']')) {
          if (this.atEnd()) throw new ReadError('a list is not closed');
          items.push(this.listMember());
          if (this.at(',')) this.take();
        }
        this.take();
        p = { k: 'ListLit', items };
      } else if (kind === 'string') p = { k: 'Lit', value: new Value('string', unquote(text)) };
      else if (kind === 'int') p = { k: 'Lit', value: new Value('number', parseInt(text, 10)) };
      else if (kind === 'date') p = { k: 'Lit', value: new Value('date', new ThymDate('date', text, text)) };
      else if (kind === 'uri') p = { k: 'Lit', value: new Value('string', text) };
      else if (kind === 'name') {
        if (text === 'true' || text === 'false') p = { k: 'Lit', value: new Value('bool', text === 'true') };
        else if (text === 'nothing') p = { k: 'Lit', value: NOTHING };
        else p = { k: 'Name', name: text };
      } else throw new ReadError(`expected a value, found ${T.pyRepr(text || 'the end')}`);
      while (this.at('.') && this.peek(1)[0] === 'name') { this.take(); p = { k: 'FieldRead', base: p, name: this.name() }; }
      return p;
    }
    listMember() {
      if (this.peek()[0] === 'name' && !this.at('.', 1) && !['true', 'false', 'nothing'].includes(this.peek()[1])) {
        return { k: 'Lit', value: new Value('word', this.take()[1]) };
      }
      return this.primary();
    }
    cond() {
      const items = [this.and()];
      while (this.at('or')) { this.take(); items.push(this.and()); }
      return items.length === 1 ? items[0] : { k: 'BoolOp', op: 'or', items };
    }
    and() {
      const items = [this.not()];
      while (this.at('and')) { this.take(); items.push(this.not()); }
      return items.length === 1 ? items[0] : { k: 'BoolOp', op: 'and', items };
    }
    not() {
      if (this.at('not')) { this.take(); return { k: 'Not', item: this.not() }; }
      return this.term();
    }
    side() { return this.atSideCall() ? this.call(true) : this.primary(); }
    term() {
      const left = this.side();
      if (this.at('is')) {
        this.take();
        let neg = false;
        if (this.at('not')) { this.take(); neg = true; }
        return { k: 'Cmp', op: neg ? 'is not' : 'is', left, right: this.rhsWord() };
      }
      if (this.at('in')) { this.take(); return { k: 'Cmp', op: 'in', left, right: this.side() }; }
      for (const op of ['<', '>', '=']) if (this.at(op)) { this.take(); return { k: 'Cmp', op, left, right: this.side() }; }
      if (this.at('has')) { this.take(); return { k: 'Has', base: left, name: this.name() }; }
      if (this.at('covers')) { this.take(); return { k: 'Covers', left, right: this.side() }; }
      return { k: 'Bare', expr: left };
    }
    rhsWord() {
      if (this.atSideCall()) return this.call(true);
      const t = this.peek();
      if (t[0] === 'name' && !this.at('.', 1) && !['true', 'false', 'nothing'].includes(t[1])) {
        this.take();
        return { k: 'Lit', value: new Value('word', t[1]) };
      }
      return this.primary();
    }
  }

  const readStatement = (text, moves, inMoves, whereMoves) => new Reader(text, moves, inMoves, whereMoves).statement();
  function readExpression(text, moves) {
    const r = new Reader(text, moves);
    const e = r.expr();
    if (!r.atEnd()) throw new ReadError(`unexpected ${T.pyRepr(r.peek()[1])}`);
    return e;
  }

  function condText(c) {
    if (c.k === 'BoolOp') return c.items.map(condText).join(` ${c.op} `);
    if (c.k === 'Not') return `not ${condText(c.item)}`;
    if (c.k === 'Cmp') return `${exprText(c.left, true)} ${c.op} ${exprText(c.right, true)}`;
    if (c.k === 'Has') return `${exprText(c.base, true)} has ${c.name}`;
    if (c.k === 'Covers') return `${exprText(c.left, true)} covers ${exprText(c.right, true)}`;
    if (c.k === 'Bare') return exprText(c.expr);
    return String(c);
  }
  function exprText(e, nested) {
    if (!e) return 'the value';
    if (e.k === 'Name') return e.name;
    if (e.k === 'Lit') {
      const v = e.value;
      if (v.type === 'string') return `"${v.payload}"`;
      if (v.type === 'bool') return v.payload ? 'true' : 'false';
      if (v.type === 'date' && v.payload instanceof ThymDate) return v.payload.iso;
      return v.isNothing ? 'nothing' : String(v.payload);
    }
    if (e.k === 'FieldRead') return `${exprText(e.base, true)}.${e.name}`;
    if (e.k === 'ListLit') return '[' + e.items.map((x) => exprText(x)).join(', ') + ']';
    if (e.k === 'Call') {
      let out = e.move + (e.operands.length ? ' ' + e.operands.map((o) => exprText(o, true)).join(', ') : '');
      for (const [w, a] of Object.entries(e.mods)) {
        if (w === 'where') out += ` where ${a[1]}`;
        else if (Array.isArray(a)) out += ` ${w} [` + a.map(String).join(', ') + ']';
        else if (a && a.isAmount) out += ` ${w} ${a.n} ${a.unit}`;
        else if (typeof a === 'string') out += ` ${w} ${a}`;
        else out += ` ${w} ${exprText(a, true)}`;
      }
      return nested ? `(${out})` : out;
    }
    if (e.k === 'Filter') { const out = `${exprText(e.base, true)} where ${e.text}`; return nested ? `(${out})` : out; }
    return 'the value';
  }

  function callsIn(x) {
    const out = [];
    if (!x) return out;
    if (x.k === 'Stmt') { for (const p of [x.expr, x.cond, x.loop]) out.push(...callsIn(p)); } else if (x.k === 'Loop') {
      out.push(...callsIn(x.coll), ...callsIn(x.cond));
    } else if (x.k === 'Call') {
      out.push(x.move);
      for (const o of x.operands) out.push(...callsIn(o));
      for (const [w, a] of Object.entries(x.mods)) {
        if (w === 'marked') out.push('mark');
        else if (w === 'where') out.push(...callsIn(a[0]));
        else if (!(typeof a === 'string' || Array.isArray(a) || (a && a.isAmount))) out.push(...callsIn(a));
      }
    } else out.push(...childrenOf(x).flatMap(callsIn));
    return out;
  }
  function callObjects(x) {
    const out = [];
    if (!x) return out;
    if (x.k === 'Stmt') { for (const p of [x.expr, x.cond, x.loop]) out.push(...callObjects(p)); } else if (x.k === 'Loop') {
      out.push(...callObjects(x.coll), ...callObjects(x.cond));
    } else if (x.k === 'Call') {
      out.push(x);
      for (const o of x.operands) out.push(...callObjects(o));
      for (const [w, a] of Object.entries(x.mods)) {
        if (w === 'where') out.push(...callObjects(a[0]));
        else if (w !== 'marked' && !(typeof a === 'string' || Array.isArray(a) || (a && a.isAmount))) out.push(...callObjects(a));
      }
    } else out.push(...childrenOf(x).flatMap(callObjects));
    return out;
  }
  function childrenOf(x) {
    switch (x.k) {
      case 'Filter': return [x.base, x.cond];
      case 'Cmp': return [x.left, x.right];
      case 'Covers': return [x.left, x.right];
      case 'BoolOp': return x.items;
      case 'Not': return [x.item];
      case 'Bare': return [x.expr];
      case 'Has': return [x.base];
      case 'FieldRead': return [x.base];
      case 'ListLit': return x.items;
      default: return [];
    }
  }
  const hasCovers = (c) => !!c && (c.k === 'Covers' || (c.k === 'BoolOp' && c.items.some(hasCovers)) || (c.k === 'Not' && hasCovers(c.item)));

  // -------------------------------------------------------------------------------------------------------------
  // What the plan does not carry: the program (run.ProgramInfo)
  // -------------------------------------------------------------------------------------------------------------

  const LET = /^let\s+([a-z][a-z0-9-]*)\s*=\s*(.+)$/;
  const COLLECT = /^let\s+[a-z][a-z0-9-]*\s*=\s*for\s+each\b/;
  const CONTRACT_HEAD = /^contract\s+([a-z][a-z0-9-]*)\s*\((.*)\)\s*$/;
  const KEEPS = /^keeps\s+([a-z][a-z0-9-]*)(?:\s+of\s+([a-z][a-z0-9-]*))?(?:\s+against\s+(.+))?$/;
  const DEPTH = /^depth\s*:\s*(\d+)$/;
  const WRITTEN = /^(?:let\s+[a-z][a-z0-9-]*\s*=\s*)?for\s+each\s+[a-z][a-z0-9-]*\s+in\s+\[[^\]]*\]$/;
  const ELSE_MSG = /\belse\s+"((?:[^"\\]|\\.)*)"\s*$/;
  const HEAD = /^(?:(?:why|must)\s*:|decided\b)/;
  const MOVE_HEAD = /^move\s+([a-z][a-z0-9-]*)\s*\((.*)\)\s*:\s*(.+)$/;

  function params(text) {
    const out = [];
    for (const part of text.split(',')) {
      const i = part.indexOf(':');
      if (i >= 0) out.push([pyStrip(part.slice(0, i)), pyStrip(part.slice(i + 1))]);
    }
    return out;
  }
  function versionOf(text) {
    for (const raw of text.replace(/\r\n/g, '\n').split('\n')) {
      const s = pyStrip(stripComment(raw)).replace(/^\ufeff+/, '');
      if (!s) continue;
      const m = /^thym\s+(\d+)$/.exec(s);
      return m ? parseInt(m[1], 10) : null;
    }
    return null;
  }
  const userMove = (name, ps, gives, body) => ({ name, params: ps, gives, body, keeps: [], depth: null });

  class ProgramInfo {
    constructor() {
      this.name = null; this.takes = []; this.gives = null; this.lets = new Map(); this.moves = new Map();
      this.messages = new Map(); this.statements = new Map(); this.version = null; this.outputs = [];
      this.loops = new Map(); this.spans = []; this.contracts = new Map(); this.keeps = [];
    }
    static fromAny(program, name) {
      if (program === null || program === undefined) return new ProgramInfo();
      if (program instanceof ProgramInfo) return program;
      if (isDict(program)) return ProgramInfo.fromItems(program, name);
      if (typeof program === 'string') return ProgramInfo.fromSource(program, name);
      return new ProgramInfo();
    }
    static fromItems(vol, name) {
      const info = new ProgramInfo();
      info.version = versionOf(String(get(vol, 'front') || ''));
      const nodes = (get(vol, 'nodes') || []).filter(isDict);
      const byId = new Map(nodes.map((n) => [get(n, 'id'), n]));
      const progs = nodes.filter((n) => get(n, 'type') === 'program');
      let prog = name ? (progs.find((n) => get(n, 'name') === name) || null) : null;
      prog = prog || (progs.length ? progs[0] : null);
      if (prog) {
        info.name = get(prog, 'name');
        info.takes = (get(prog, 'takes') || []).filter(isDict).map((t) => [get(t, 'name'), get(t, 'type')]);
        const gv = (get(prog, 'gives') || []).filter(isDict);
        info.gives = gv.length ? [get(gv[0], 'name'), get(gv[0], 'type')] : null;
        info.outputs = gv.map((g) => [get(g, 'name'), get(g, 'type')]);
      }
      for (const st of nodes) {
        if (get(st, 'type') !== 'step') continue;
        const line = get(st, 'line');
        if (Number.isInteger(line)) {
          const said = get(st, 'name') || String(get(st, 'text') || '').split('\n').map((x) => pyStrip(stripComment(x))).join(' ');
          if (!info.statements.has(line)) info.statements.set(line, pyStrip(String(said)));
        }
        const text = pyStrip(stripComment(String(get(st, 'text') || '')));
        if (get(st, 'form') === 'let' && !truthy(get(st, 'calls')) && !String(get(st, 'of') || '').startsWith('P:move/')) {
          const m = LET.exec(text);
          if (m && !info.lets.has(m[1])) info.lets.set(m[1], pyStrip(m[2]));
        }
        if (get(st, 'form') === 'assert') {
          const m = ELSE_MSG.exec(text);
          if (m && Number.isInteger(line)) info.messages.set(line, unquote(`"${m[1]}"`));
        }
      }
      const tree = (refs) => {
        const out = [];
        for (const ref of refs || []) {
          const st = byId.get(ref);
          if (!isDict(st)) continue;
          const text = pyStrip(stripComment(String(get(st, 'text') || '')));
          const form = get(st, 'form');
          if (form === 'if') {
            const br = get(st, 'branches') || {};
            out.push(['if', get(st, 'line'), text, tree(get(br, 'then')), tree(get(br, 'else'))]);
          } else if (form === 'for') out.push(['for', get(st, 'line'), text, tree(get(st, 'steps'))]);
          else out.push(['stmt', get(st, 'line'), text]);
        }
        return out;
      };
      for (const mv of nodes) {
        if (get(mv, 'type') !== 'move' || !get(mv, 'name')) continue;
        const ps = (get(mv, 'params') || []).filter(isDict).map((p) => [get(p, 'name'), get(p, 'type')]);
        const gv = (get(mv, 'gives') || []).filter(isDict);
        info.moves.set(get(mv, 'name'), userMove(get(mv, 'name'), ps, gv.length ? get(gv[0], 'type') : null, tree(get(mv, 'steps'))));
      }
      if (typeof get(vol, 'front') === 'string') {
        const tops = nodes.filter((n) => Number.isInteger(get(n, 'order')) && typeof get(n, 'body') === 'string')
          .sort((a, b) => get(a, 'order') - get(b, 'order'));
        const src = ProgramInfo.fromSource(get(vol, 'front') + tops.map((n) => get(n, 'body')).join(''), info.name);
        info.loops = src.loops; info.spans = src.spans; info.contracts = src.contracts; info.keeps = src.keeps;
        for (const [n, um] of info.moves) {
          if (src.moves.has(n)) { um.keeps = src.moves.get(n).keeps; um.depth = src.moves.get(n).depth; }
        }
      }
      return info;
    }
    static fromSource(text, name) {
      const info = new ProgramInfo();
      info.version = versionOf(text);
      const thym1 = (info.version || 0) >= 1;
      const stack = [];
      let prose = false;
      const contractFrame = (s) => {
        const m = CONTRACT_HEAD.exec(s);
        return { kind: 'contract', body: [], contract: m ? { name: m[1], params: params(m[2]), body: [] } : null };
      };
      const owner = () => { for (let i = stack.length - 1; i >= 0; i--) if (['program', 'move', 'contract'].includes(stack[i].kind)) return stack[i]; return null; };
      const inProgram = () => stack.length > 0 && stack[0].kind === 'program' && !stack.some((f) => f.kind === 'move' || f.kind === 'contract');
      const chosen = () => stack.length > 0 && stack[0].kind === 'program' && stack[0].named !== false;
      const current = (f) => (f.kind === 'if' ? (f.inElse ? f.else : f.then) : f.body);
      const lines = text.replace(/\r\n/g, '\n').split('\n');
      lines.forEach((raw, idx) => {
        const ln = idx + 1;
        const s = pyStrip(stripComment(raw));
        if (!s) { prose = false; return; }
        const words = pySplitWs(s);
        const first = words[0];
        if (!stack.length) {
          if (first === 'program' && words.length > 1) {
            const mine = info.name === null && (name === undefined || name === null || words[1] === name);
            if (mine) info.name = words[1];
            stack.push({ kind: 'program', body: [], named: mine });
          } else if (first === 'move') {
            const m = MOVE_HEAD.exec(s);
            stack.push({ kind: 'move', body: [], move: m ? userMove(m[1], params(m[2]), pyStrip(m[3]), []) : null });
          } else if (first === 'contract' && thym1) stack.push(contractFrame(s));
          else if (first === 'morph' || first === 'context') stack.push({ kind: 'skip' });
          prose = false;
          return;
        }
        const top = stack[stack.length - 1];
        if (top.kind === 'skip') { if (s === 'end') stack.pop(); return; }
        if (HEAD.test(s)) { prose = true; return; }
        if (prose && !['takes', 'gives', 'end'].includes(first) && !(thym1 && ['keeps', 'depth'].includes(first))) return;
        prose = false;
        if (thym1 && first === 'keeps' && KEEPS.test(s)) {
          const m = KEEPS.exec(s);
          const kept = [m[1], (m[3] || '').split(',').map((a) => pyStrip(a)).filter(Boolean), m[2] === undefined ? null : m[2]];
          const f = owner();
          if (f && f.kind === 'program' && f.named !== false) info.keeps.push(kept);
          else if (f && f.kind === 'move' && f.move) f.move.keeps.push(kept);
          return;
        }
        if (thym1 && DEPTH.test(s)) {
          const f = owner();
          if (f && f.kind === 'move' && f.move) f.move.depth = parseInt(DEPTH.exec(s)[1], 10);
          return;
        }
        if (thym1 && first === 'contract' && CONTRACT_HEAD.test(s)) { stack.push(contractFrame(s)); return; }
        if (first === 'takes') { if (top.kind === 'program' && chosen()) info.takes = params(s.slice(5)); return; }
        if (first === 'gives') {
          if (top.kind === 'program' && chosen()) { const g = params(s.slice(5)); info.gives = g.length ? g[0] : null; info.outputs = g.slice(); }
          return;
        }
        if (first === 'move') {
          const m = MOVE_HEAD.exec(s);
          stack.push({ kind: 'move', body: [], move: m ? userMove(m[1], params(m[2]), pyStrip(m[3]), []) : null });
          return;
        }
        if (s === 'end') {
          const f = stack.pop();
          if (f.kind === 'move' && f.move) { f.move.body = f.body; info.moves.set(f.move.name, f.move); } else if (f.kind === 'contract' && f.contract) {
            f.contract.body = f.body; info.contracts.set(f.contract.name, f.contract);
          } else if (f.kind === 'if' && stack.length) current(stack[stack.length - 1]).push(['if', f.line, f.text, f.then, f.else]);
          else if (f.kind === 'for' && stack.length) {
            const part = ['for', f.line, f.text, f.body];
            current(stack[stack.length - 1]).push(part);
            if (f.program) { info.loops.set(f.line, part); info.spans.push([f.line, ln, !WRITTEN.test(f.text)]); }
          }
          return;
        }
        if (s === 'else' && top.kind === 'if') { top.inElse = true; return; }
        if (!info.statements.has(ln)) info.statements.set(ln, s);
        if (first === 'if') { stack.push({ kind: 'if', line: ln, text: s, then: [], else: [], inElse: false }); return; }
        if (first === 'for' || (thym1 && COLLECT.test(s))) { stack.push({ kind: 'for', line: ln, text: s, body: [], program: inProgram() }); return; }
        current(top).push(['stmt', ln, s]);
        const m = LET.exec(s);
        if (m && inProgram() && chosen() && !info.lets.has(m[1])) info.lets.set(m[1], pyStrip(m[2]));
        if (first === 'assert') { const mm = ELSE_MSG.exec(s); if (mm) info.messages.set(ln, unquote(`"${mm[1]}"`)); }
      });
      return info;
    }
  }

  // -------------------------------------------------------------------------------------------------------------
  // The person's words (THYM 9)
  // -------------------------------------------------------------------------------------------------------------

  const TRAILER = /, for (?:each [a-z][a-z0-9-]* in .*|[a-z][a-z0-9-]* = .*)$/;
  const TEMP = /\bt(\d+)\b/g;
  const ORDINALS = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth',
    'eleventh', 'twelfth', 'thirteenth', 'fourteenth', 'fifteenth', 'sixteenth', 'seventeenth', 'eighteenth',
    'nineteenth', 'twentieth'];
  function cut(text, n) {
    n = n === undefined ? 60 : n;
    text = pySplitWs(String(text)).join(' ');
    return cpLen(text) <= n ? text : pyRstrip(cpSlice(text, 0, n - 1)) + '\u2026';
  }
  const ordinal = (k) => (k >= 1 && k <= ORDINALS.length ? `the ${ORDINALS[k - 1]} member` : `member ${k}`);
  function describe(v) {
    if (!v || !v.isThymValue) return 'a value';
    if (v.isNothing) return 'nothing';
    if (v.type === 'bool') return v.payload ? 'true' : 'false';
    if (v.type === 'number' || v.type === 'word') return String(v.payload);
    if (v.type === 'date' && v.payload instanceof ThymDate) return v.payload.iso;
    if (v.type === 'string' && typeof v.payload === 'string') return '"' + cut(v.payload, 40) + '"';
    if (v.type === 'list') { const n = (v.payload || []).length; return n !== 1 ? `a list of ${n}` : 'a list of one'; }
    if (v.type === 'item') return itemId(v) || 'an item';
    return `${'aeiou'.includes(v.type[0]) ? 'an' : 'a'} ${v.type}`;
  }
  const nodeNumber = (id) => { const s = String(id === null || id === undefined ? '' : id); return s.includes('/') ? s.slice(s.lastIndexOf('/') + 1) : s; };

  /** Python's `==` on what a condition compares (`_eq`): a value by its digest, a bool by identity. */
  function pyEq(a, b) {
    if ((a && a.isThymValue) || (b && b.isThymValue)) return !!(a && a.isThymValue && b && b.isThymValue && a.sha256 === b.sha256);
    if (typeof a === 'boolean' || typeof b === 'boolean') return a === b;
    return looseEq(a, b);
  }
  function looseEq(a, b) {
    if (a === b) return true;
    if (a === null || b === null || a === undefined || b === undefined) return false;
    if ((typeof a === 'boolean' && typeof b === 'number') || (typeof a === 'number' && typeof b === 'boolean')) return Number(a) === Number(b);
    if (a instanceof ThymDate || b instanceof ThymDate) return a instanceof ThymDate && b instanceof ThymDate && a.kind === b.kind && a.iso === b.iso;
    if (a instanceof T.ThymFloat || b instanceof T.ThymFloat) return String(a) === String(b) && typeof a !== 'string' && typeof b !== 'string';
    if (Array.isArray(a) || Array.isArray(b)) return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((x, i) => looseEq(x, b[i]));
    if (isDict(a) && isDict(b)) {
      const ea = entries(a), eb = entries(b);
      return ea.length === eb.length && ea.every(([k, v]) => has(b, k) && looseEq(v, get(b, k)));
    }
    return false;
  }
  const basename = (p) => { const parts = String(p).replace(/\/+$/, '').split('/'); return parts[parts.length - 1]; };
  function utc(d) {
    if (!d) return null;
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}T${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}Z`;
  }

  // -------------------------------------------------------------------------------------------------------------
  // Traces (trace.py)
  // -------------------------------------------------------------------------------------------------------------

  function record(node, o) {
    const n = nodeNumber(node.id);
    const checks = (o.checks || []).slice();
    const failed = checks.filter((c) => !c.ok);
    let summary;
    if (o.engine === 'skipped') summary = 'Not run: the other branch was taken.';
    else if (o.refusal) summary = pyRstrip(`Refused: ${o.refusal.check}, ${o.refusal.message}`, '.') + '.';
    else if (failed.length) summary = `Refused: ${failed[0].name} does not hold (${failed[0].why || 'no reason given'}).`;
    else summary = `${o.engine}, ${o.attempts} attempt${o.attempts !== 1 ? 's' : ''}, ${checks.length} check${checks.length !== 1 ? 's' : ''} green.`;
    const rec = { id: `R:record/${n}`, type: 'record', name: String(node.name || node.move || n), summary,
      node: String(node.id), move: String(o.move || node.move || ''), inputs: (o.inputs || []).slice(),
      outputs: (o.outputs || []).slice(), engine: o.engine, attempts: o.attempts | 0, tokens: o.tokens | 0,
      seconds: o.seconds | 0, checks };
    if (o.state) rec.state = o.state;
    if (o.tries && o.tries.length) rec.tries = o.tries.map((x) => Object.assign({}, x));
    if (o.passes !== null && o.passes !== undefined) rec.passes = o.passes | 0;
    rec.provenance = { mode: 'derived', sources: [`${o.runId}.plan.cosm#${node.id}`], confidence: 1 };
    return rec;
  }

  class Trace {
    constructor(o) {
      Object.assign(this, { ended: null, outcome: 'refused', records: [], stoppedAt: null, refusal: null,
        outputs: {}, values: {}, extra: {} }, o);
    }
    get landed() { return this.outcome === 'landed'; }
    seconds() { return this.ended ? Math.max(0, Math.floor((this.ended - this.started) / 1000)) : 0; }
    engine() {
      const models = Array.from(new Set(this.records.map((r) => String(r.engine || '')).filter((e) => e.startsWith('model:')).map((e) => e.slice(6)))).sort();
      if (models.length) return models.join(', ');
      if (this.records.some((r) => r.engine === 'rules')) return 'rules';
      return 'code';
    }
    atem() {
      const prog = this.program.name || 'the program';
      const names = this.inputs.length ? this.inputs.map((i) => basename(String(i.path || i.name))) : ['nothing'];
      const ran = this.records.filter((r) => r.engine !== 'skipped');
      const head = `ran ${prog} on ${names.join(', ')}`;
      if (this.outcome === 'landed') return `${head} in ${this.seconds()} s on ${this.engine()}: ${ran.length} step${ran.length !== 1 ? 's' : ''}, all checks green`;
      const r = this.refusal;
      const where = this.stoppedAt ? `; refused at node ${nodeNumber(this.stoppedAt)}` : '; refused';
      const why = r ? `: ${r.check}, ${r.message}` : '';
      return `${head}${where} after ${this.seconds()} s${why}`;
    }
    toVolume() {
      const rid = this.runId;
      const prog = this.program.name || 'program';
      const rootItem = { id: `R:trace/${rid}`, type: 'trace', name: `${prog} run ${rid}`, summary: this.atem(),
        records: this.records.map((r) => r.id), outcome: this.outcome };
      if (this.stoppedAt) rootItem.stopped_at = this.stoppedAt;
      if (this.refusal) {
        const r = this.refusal;
        rootItem.refusal = Object.assign({ stage: r.stage, check: r.check, message: r.message }, r.line ? { line: r.line } : {});
      }
      for (const k of ['replay_of', 'inputs_root', 'rules', 'made_run', 'engines']) {
        const v = this.extra[k];
        if (!(v === null || v === undefined || v === false || v === '')) rootItem[k] = v;
      }
      rootItem.provenance = { mode: 'derived', sources: [`${rid}.plan.cosm`], confidence: 1 };
      return { oes: 'thym/1', kind: 'trace', id: `thym/${rid}`, name: `${prog} run ${rid}`,
        program: { name: this.program.name === undefined ? null : this.program.name, sha256: this.program.sha256 === undefined ? null : this.program.sha256 },
        plan: { sha256: this.planSha256 }, environment: Object.assign({}, this.environment),
        started: utc(this.started), ended: utc(this.ended), outcome: this.outcome,
        nodes: [rootItem].concat(plain(this.records), plain(this.nodes)) };
    }
  }

  // -------------------------------------------------------------------------------------------------------------
  // The walk (run._Run)
  // -------------------------------------------------------------------------------------------------------------

  class Stop extends Error {
    constructor(refusal, o) { super(String(refusal)); this.refusal = refusal; this.worded = !!(o && o.worded); this.fault = (o && o.fault) || null; }
  }
  class Scope {
    constructor(maps, program) { this.maps = maps; this.program = program === undefined ? true : program; }
    has(n) { return this.maps.some((m) => m.has(n)); }
    get(n) { for (const m of this.maps) if (m.has(n)) return m.get(n); return undefined; }
    set(n, v) { this.maps[0].set(n, v); }
    child(names) { return new Scope([new Map(Object.entries(names))].concat(this.maps), this.program); }
  }
  class NodeState {
    constructor(node) {
      Object.assign(this, { node, engine: 'code', attempts: 0, tokens: 0, checks: [], outputs: [], state: null, tries: [],
        passing: null, fault: null, passes: null });
    }
  }

  function planParts(plan) {
    const rows = (get(plan, 'nodes') || []).filter(isDict);
    return [rows.find((n) => n.type === 'plan') || {}, rows.filter((n) => n.type === 'node')];
  }
  function topoOrder(nodes) {
    const idx = new Map(nodes.map((n, i) => [n.id, i]));
    const givers = new Map();
    for (const n of nodes) if (typeof n.gives === 'string') { if (!givers.has(n.gives)) givers.set(n.gives, []); givers.get(n.gives).push(n.id); }
    const waiting = new Map();
    for (const n of nodes) {
      const d = new Set((n.after || []).filter((a) => idx.has(a)));
      for (const t of n.takes || []) for (const g of givers.get(t) || []) if (g !== n.id) d.add(g);
      waiting.set(n.id, d);
    }
    let ready = Array.from(waiting.entries()).filter(([, v]) => !v.size).map(([k]) => idx.get(k));
    const out = [];
    while (ready.length) {
      ready.sort((a, b) => a - b);
      const i = ready.shift();
      const nid = nodes[i].id;
      out.push(nodes[i]);
      for (const [k, v] of waiting) if (v.has(nid)) { v.delete(nid); if (!v.size) ready.push(idx.get(k)); }
    }
    if (out.length !== nodes.length) {
      const done = new Set(out.map((o) => o.id));
      const lines = Array.from(new Set(nodes.filter((n) => !done.has(n.id) && Number.isInteger(n.line)).map((n) => n.line))).sort((a, b) => a - b);
      const where = lines.length ? ` (the statements at lines ${lines.join(', ')})` : '';
      return new Refusal('plan', 'plan-acyclic', `the plan's steps wait on each other${where}, so none of them can run first: plan the program again`);
    }
    return out;
  }
  const alternatives = (x) => {
    if (x === null || x === undefined) return [];
    const parts = typeof x === 'string' ? [x] : Array.isArray(x) ? x.map(String) : [String(x)];
    return parts.flatMap((p) => p.split('|')).map((a) => pyStrip(a)).filter(Boolean);
  };
  function newRunId(now) {
    const t = now || new Date();
    const p = (n) => String(n).padStart(2, '0');
    const hex = Math.floor(Math.random() * 0x10000).toString(16).padStart(4, '0');
    return `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}-${p(t.getHours())}${p(t.getMinutes())}-${hex}`;
  }

  class Run {
    constructor(o) {
      this.plan = T.revive(o.plan);
      this.program = o.program === undefined ? null : (isDict(o.program) ? T.revive(o.program) : o.program);
      this.bundles = o.inputs || {};
      this.givenDecls = o.decls || null;
      this.environment = o.environment || {};
      this.runId = o.runId || null;
      this.madeRun = o.madeRun || null;
      this.now = o.now ? new Date(o.now) : null;
      this.inputsRoot = o.inputsRoot || null;
      this.agentFree = true;
      this.rules = false;
      this.route = o.route || null;
      this.env = new Map(); this.inputs = new Map(); this.inputPaths = new Map(); this.memberPaths = new Map();
      this.emitted = []; this.slots = new Map(); this.withheld = new Map(); this.ifResults = new Map(); this.skipped = new Set();
      this.records = []; this.cur = null; this.letBusy = new Set(); this.moveStack = []; this.sides = [];
      this.inMoves = new Set(); this.whereMoves = new Set(); this.keeping = []; this.passes = []; this.repairs = [];
      this.emitK = 0; this.stage = new Map();
      if (o.manifests) Object.assign(T.manifests, o.manifests);
    }

    // -- plan time ----------------------------------------------------------------------------------------------
    prepare() {
      const [head, nodes] = planParts(this.plan);
      this.head = head;
      if (!nodes.length) return new Refusal('plan', 'plan', 'not a plan: it holds no R:node items');
      const order = topoOrder(nodes);
      if (order instanceof Refusal) return order;
      this.nodes = nodes; this.order = order;
      this.byId = new Map(nodes.map((n) => [n.id, n]));
      const want = isDict(this.plan.program) ? this.plan.program.name : null;
      this.info = ProgramInfo.fromAny(this.program, want);
      const version = this.info.version !== null ? this.info.version : 1;
      this.decls = T.declarations(version, this.givenDecls);
      for (const [n, d] of Object.entries(this.decls)) {
        if (d.modifiers && has(d.modifiers, 'in')) this.inMoves.add(n);
        if (d.modifiers && has(d.modifiers, 'where')) this.whereMoves.add(n);
      }
      this.moveNames = new Set(Object.keys(this.decls).concat(Array.from(this.info.moves.keys())));
      const est = isDict(this.plan.estimate) ? this.plan.estimate : {};
      this.largestPrompt = parseInt(head.largest_prompt || est.largest_prompt || 0, 10);
      return this.environmentCheck();
    }
    bodyMoves(name, seen) {
      seen = seen || new Set();
      const um = this.info.moves.get(name);
      if (!um || seen.has(name)) return new Set();
      return this.partMoves(um.body, new Set([...seen, name]));
    }
    partMoves(body, seen) {
      seen = seen || new Set();
      const out = new Set();
      for (const part of body) {
        let st;
        try { st = readStatement(part[2], this.moveNames, this.inMoves, this.whereMoves); } catch (e) { if (e instanceof ReadError) continue; throw e; }
        for (const m of callsIn(st)) {
          if (this.info.moves.has(m)) for (const x of this.bodyMoves(m, seen)) out.add(x);
          else out.add(m);
        }
        for (const sub of part.slice(3)) if (Array.isArray(sub)) for (const x of this.partMoves(sub, seen)) out.add(x);
      }
      return out;
    }
    movesOf(node) {
      const m = node.move;
      if (m === 'for') {
        const part = this.info.loops.get(node.line);
        return part ? Array.from(this.partMoves([part])).sort(T.cmpStr) : [];
      }
      return this.info.moves.has(m) ? Array.from(this.bodyMoves(m)).sort(T.cmpStr) : [m];
    }
    environmentCheck() {
      const asks = this.nodes.filter((n) => n.asks === true);
      if (asks.length) {
        const k = asks.length;
        let many = `${k} step${k !== 1 ? 's' : ''} ask${k !== 1 ? '' : 's'} a model`;
        many += ` on the ${this.route === 'cloud' ? 'cloud' : 'local'} route`;
        const line = asks[0].line;
        const stmt = Number.isInteger(line) ? this.info.statements.get(line) : null;
        const named = stmt ? `\`${cut(stmt)}\`` : this.said(asks[0]);
        const where = Number.isInteger(line) ? ` (line ${line})` : '';
        return new Refusal('plan', 'agent-free', `${many}, the first ${named}${where}; agent-free is on`, line);
      }
      for (const spec of this.plan.inputs || []) {
        if (!isDict(spec)) continue;
        const name = String(spec.name);
        const b = this.bundles[name];
        if (!b) return new Refusal('plan', 'input', `input ${name}: the page was not given it; read it on the server (bundle.py)`);
        if (b.refusal) return new Refusal(b.refusal.stage, b.refusal.check, b.refusal.message, b.refusal.line);
        if (b.type === 'list' && Array.isArray(b.members)) {
          const v = new Value('list', b.members.map((m) => T.fromBundle(m)));
          this.inputs.set(name, v);
          this.memberPaths.set(name, (b.paths || []).slice());
          continue;
        }
        this.inputs.set(name, T.fromBundle(b));
        this.inputPaths.set(name, String(spec.path === undefined || spec.path === null ? '' : spec.path));
      }
      for (const n of this.nodes) {
        if (['if', 'assert', 'emit', 'give', 'let'].includes(n.move)) continue;
        const line = n.line === undefined ? null : n.line;
        for (const m of this.movesOf(n)) {
          const decl = this.decls[m];
          if (!decl) {
            if (this.program === null) {
              const prog = `${(this.plan.program || {}).name || this.info.name || 'its program'}.thym`;
              return new Refusal('plan', 'unknown-move', `${this.at(n)}: ${m} is no declared move, so it is a move of ${prog}, and this run has only the plan; run it with the program beside the plan (--program ${prog})`, line);
            }
            return new Refusal('plan', 'unknown-move', `${this.at(n)}: the move ${m} is not declared, and the program defines no move of that name`, line);
          }
          if (!T.MOVES[m]) {
            const why = T.NOT_HERE[m] || (decl.asks ? 'it asks a model, and the page asks none' : 'the page does not run it yet');
            return new Refusal('plan', 'move', `${this.at(n)}: the move ${m} has no implementation here (${why}; run it on the server)`, line);
          }
        }
      }
      return null;
    }

    // -- the run --------------------------------------------------------------------------------------------------
    traceInputs() {
      const out = [];
      for (const spec of this.plan.inputs || []) {
        const name = isDict(spec) ? String(spec.name) : '';
        if (this.memberPaths.has(name)) this.memberPaths.get(name).forEach((p, i) => out.push({ name: `${name}[${i + 1}]`, path: p }));
        else if (this.inputPaths.has(name)) out.push({ name, path: this.inputPaths.get(name) });
      }
      return out;
    }
    go() {
      const r = this.prepare();
      if (r) return { refusal: r };
      const start = new Date(Math.floor(Date.now() / 1000) * 1000);
      this.started = this.now || start;
      const rid = this.runId || newRunId();
      this.runId = rid;
      this.madeRun = this.madeRun || rid;
      const planBytes = canonical(this.plan);
      const env = { enough: 'unknown', model: 'none', context: 0, agent_free: true, memory_band: 'unknown' };
      for (const [k, v] of Object.entries(this.environment)) if (v !== null && v !== undefined && typeof v !== 'function') env[k] = v;
      const prog = isDict(this.plan.program) ? this.plan.program : {};
      this.trace = new Trace({ runId: rid, program: { name: prog.name || this.info.name, sha256: prog.sha256 === undefined ? null : prog.sha256 },
        planSha256: sha256(planBytes), environment: env, started: this.started, nodes: this.nodes.slice(),
        inputs: this.traceInputs(), extra: { inputs_root: this.inputsRoot, rules: false, replay_of: null,
          made_run: this.madeRun !== rid ? this.madeRun : null, engines: null } });
      for (const [k, v] of this.inputs) this.env.set(k, v);
      this.outputNames = this.outputNamesOf();
      let refusal = null, stopped = null;
      for (const node of this.order) {
        try { refusal = this.runNode(node); } catch (e) {
          if (e instanceof Stop) refusal = e.refusal;
          else {
            refusal = new Refusal('run', 'runtime', `${this.at(node)}: the runtime failed while running this statement, ${RUNTIME_FAULT}; nothing landed`, node.line);
            if (this.cur) this.cur.fault = `${e && e.name ? e.name : 'Error'}: ${e && e.message ? e.message : e}`;
            this.record(node, refusal);
          }
        }
        if (refusal) { stopped = `R:record/${nodeNumber(node.id)}`; break; }
      }
      let files = new Map();
      if (!refusal) {
        const landed = this.land();
        if (landed instanceof Refusal) { refusal = landed; stopped = this.records.length ? this.records[this.records.length - 1].id : null; } else files = landed;
      }
      this.trace.records = this.records;
      this.trace.ended = new Date(Math.floor(Date.now() / 1000) * 1000);
      if (!refusal) this.trace.outcome = 'landed';
      else { this.trace.outcome = 'refused'; this.trace.refusal = refusal; this.trace.stoppedAt = stopped; files = new Map(); }
      return { trace: this.trace, files };
    }
    outputNamesOf() {
      const names = this.info.outputs.filter((o) => o && o[0]).map((o) => String(o[0]));
      if (names.length) return names;
      const one = this.outputName();
      return one ? [one] : [];
    }
    outputName() {
      if (this.info.gives && this.info.gives[0]) return String(this.info.gives[0]);
      const taken = new Set(this.nodes.flatMap((n) => n.takes || []));
      const given = this.nodes.map((n) => n.gives).filter((g) => typeof g === 'string');
      const cands = given.filter((g) => !/^t\d+$/.test(g) && !taken.has(g));
      return cands.length ? cands[cands.length - 1] : null;
    }

    // -- one node -------------------------------------------------------------------------------------------------
    governingIf(node) {
      const seen = new Set(), queue = (node.after || []).slice();
      while (queue.length) {
        const nid = queue.shift();
        if (seen.has(nid) || !this.byId.has(nid)) continue;
        seen.add(nid);
        const n = this.byId.get(nid);
        if (n.move === 'if') return nid;
        queue.push(...(n.after || []));
      }
      return null;
    }
    branchTaken(node) {
      const g = this.governingIf(node);
      if (g === null) return true;
      if (this.skipped.has(g) || !this.ifResults.has(g)) return false;
      return (node.branch === 'then') === this.ifResults.get(g);
    }
    runNode(node) {
      const nid = node.id;
      this.cur = new NodeState(node);
      this.t0 = Date.now();
      if ((node.branch === 'then' || node.branch === 'else') && !this.branchTaken(node)) {
        this.skipped.add(nid);
        this.cur.engine = 'skipped';
        this.record(node);
        return null;
      }
      const nested = this.nestedInRuntime(node);
      if (nested) {
        const [inner, outer] = nested;
        const r = new Refusal('run', 'loop', `${this.at(node)}: this statement stands in the for each at line ${inner}, inside the for each at line ${outer}, and ${this.loopReason()}, so the inner loop does not run once for each pass of the outer one; ${this.loopFix()}`, node.line);
        this.record(node, r);
        return r;
      }
      if (node.move === 'for') return this.loopNode(node);
      const text = pyStrip(String(node.name || '')) || [String(node.move)].concat(node.takes || []).join(' ');
      let st;
      try { st = readStatement(text, this.moveNames, this.inMoves, this.whereMoves); } catch (e) {
        if (!(e instanceof ReadError)) throw e;
        this.cur.fault = `${text}: ${e.message}`;
        const r = new Refusal('run', 'parse', `${this.at(node)}: the runtime could not read this statement; that is ${RUNTIME_FAULT}`, node.line);
        this.record(node, r);
        return r;
      }
      let scope = new Scope([this.env], true);
      try {
        if (st.member) {
          const [v, member] = st.member;
          this.cur.passing = `for ${v} = ${this.memberLabel(node)}`;
          scope = scope.child({ [v]: this.member(member, scope) });
        }
        if (st.form === 'if') this.ifResults.set(nid, this.ifNode(st, scope, node));
        else if (st.loop) this.repeat(st, scope);
        else if (st.form === 'assert') this.assert(st, scope);
        else this.deliver(st, this.evalE(st.expr, scope), node);
      } catch (e) {
        if (!(e instanceof Stop)) throw e;
        let r = e.worded ? e.refusal : this.worded(e.refusal, node, this.cur.passing);
        r = r.line ? r : new Refusal(r.stage, r.check, r.message, node.line, r.file);
        if (e.fault) this.cur.fault = e.fault;
        this.record(node, r);
        return r;
      }
      if (!st.loop) this.cur.attempts = Math.max(this.cur.attempts, 1);
      this.record(node);
      return null;
    }
    nestedInRuntime(node) {
      const line = node.line;
      if (this.version() >= 1 || !Number.isInteger(line)) return null;
      const around = this.info.spans.filter((sp) => sp[0] < line && line <= sp[1]).sort((a, b) => a[0] - b[0]);
      const outer = around.slice(0, -1).find((sp) => sp[2]);
      return outer ? [around[around.length - 1][0], outer[0]] : null;
    }
    loopNode(node) {
      const line = node.line;
      const part = Number.isInteger(line) ? this.info.loops.get(line) : undefined;
      try {
        if (!part) throw new Stop(new Refusal('run', 'program', `${this.at(node)}: this loop's body is read from the program, and this run has only the plan: run it with the program beside the plan (--program)`), { worded: true });
        let scope = new Scope([this.env], true);
        const st = this.readStmt(String(node.name || part[2]));
        if (st.member) {
          const [v, member] = st.member;
          this.cur.passing = `for ${v} = ${this.memberLabel(node)}`;
          scope = scope.child({ [v]: this.member(member, scope) });
        }
        const header = this.readStmt(part[2]);
        this.emitK = 0;
        const [kept, passes] = this.loop(header, part[3], scope, true);
        this.cur.passes = passes;
        if (header.name) {
          const v = new Value('list', kept);
          this.env.set(header.name, v);
          this.cur.outputs.push(digestRow(header.name, v, ''));
          kept.forEach((x, k) => this.cur.outputs.push(digestRow(`${header.name}.${k + 1}`, x, '')));
        }
      } catch (e) {
        if (!(e instanceof Stop)) throw e;
        let r = e.worded ? e.refusal : this.worded(e.refusal, node, this.cur.passing);
        r = r.line ? r : new Refusal(r.stage, r.check, r.message, line, r.file);
        if (e.fault) this.cur.fault = e.fault;
        this.record(node, r);
        return r;
      }
      this.cur.attempts = Math.max(this.cur.attempts, 1);
      this.record(node);
      return null;
    }
    loop(header, body, scope, worded) {
      const lp = header.loop;
      const coll = this.evalE(lp.coll, scope);
      let rows = members(coll);
      if (rows === null) throw new Stop(new Refusal('run', 'type', `a for each goes through a volume, a fabula, a folder, a short or a list, and ${this.words(exprText(lp.coll))} is a ${coll.type}`));
      if (lp.cond) rows = rows.filter((r) => this.cond(lp.cond, scope.child({ [lp.var]: r }), r));
      if (header.name) this.keeping.push([]);
      let kept = [];
      try {
        rows.forEach((r, i) => {
          if (worded) this.passes.push(this.passOf(lp.var, r, i + 1, coll));
          try { this.body(body, scope.child({ [lp.var]: r }), worded); } finally { if (worded) this.passes.pop(); }
        });
      } finally { kept = header.name ? this.keeping.pop() : []; }
      return [kept, rows.length];
    }
    record(node, refusal) {
      const cur = this.cur || new NodeState(node);
      const ins = [];
      for (const t of node.takes || []) {
        const v = this.env.get(t);
        if (v && v.isThymValue) {
          ins.push(digestRow(t, v, this.inputPaths.has(t) ? this.inputPaths.get(t) : ''));
          if (this.memberPaths.has(t) && v.type === 'list') {
            v.payload.forEach((m, i) => { if (i < this.memberPaths.get(t).length) ins.push(digestRow(`${t}[${i + 1}]`, m, this.memberPaths.get(t)[i])); });
          }
        }
      }
      const seconds = Math.floor((Date.now() - (this.t0 || Date.now())) / 1000);
      const rec = record(node, { runId: this.runId, move: String(node.move || ''), engine: cur.engine, inputs: ins,
        outputs: cur.outputs, attempts: cur.engine !== 'skipped' ? cur.attempts : 0, tokens: cur.tokens, seconds,
        checks: cur.checks, state: cur.state, refusal, tries: cur.tries, passes: cur.passes });
      if (cur.fault) rec.fault = cur.fault;
      this.records = this.records.filter((r) => r.id !== rec.id).concat([rec]);
    }
    deliver(st, v, node, k) {
      const suffix = k !== undefined && k !== null ? `.${k}` : '';
      if (st.form === 'emit') {
        if (st.slot) { this.slots.set(st.slot, v); this.cur.outputs.push(digestRow(`${st.slot}${suffix}`, v, '')); } else {
          this.emitted.push(v); this.cur.outputs.push(digestRow(`emit${suffix}`, v, ''));
        }
        return;
      }
      let target = (k === undefined || k === null) ? node.gives : null;
      if (st.form === 'let' && st.name && (k === undefined || k === null)) target = target || st.name;
      if (typeof target === 'string') { this.env.set(target, v); this.cur.outputs.push(digestRow(target, v, '')); } else if (!v.isNothing) {
        this.cur.outputs.push(digestRow(`value${suffix}`, v, ''));
      }
    }
    repeat(st, scope) {
      const lp = st.loop;
      const node = this.cur.node;
      const found = this.sameLoopLet(node);
      if (found) {
        const [name, giver] = found;
        throw new Stop(new Refusal('run', 'loop', `${this.at(node)}: ${name} is bound by ${this.at(giver)} inside this for each, and ${this.loopReason()}, so here ${name} would hold every pass's value at once; ${this.loopFix()}`), { worded: true });
      }
      const coll = this.evalE(lp.coll, scope);
      let rows = members(coll);
      if (rows === null) {
        const [head, at] = this.loopStatement(node);
        throw new Stop(new Refusal('run', 'type', `${head} (line ${at}): a for each goes through a volume, a fabula, a short or a list, and ${exprText(lp.coll)} is a ${coll.type}`), { worded: true });
      }
      if (lp.cond) rows = rows.filter((r) => this.cond(lp.cond, scope.child({ [lp.var]: r }), r));
      const outs = [];
      rows.forEach((r, i) => {
        const k = i + 1;
        this.cur.passing = this.passOf(lp.var, r, k, coll);
        const inner = scope.child({ [lp.var]: r });
        if (st.form === 'assert') { this.assert(st, inner); return; }
        const v = this.evalE(st.expr, inner);
        this.deliver(st, v, this.cur.node, k);
        outs.push(v);
      });
      this.cur.passing = null;
      const g = this.cur.node.gives;
      if (typeof g === 'string') this.env.set(g, new Value('list', outs));
    }
    ifNode(st, scope, node) {
      if (!st.loop) return this.cond(st.cond, scope);
      try { return this.cond(st.cond, scope); } catch (e) {
        if (!(e instanceof Stop)) throw e;
        throw new Stop(new Refusal('run', e.refusal.check, `${this.at(node)}: ${e.refusal.message}: in thym ${this.version()} an if inside a for each over a collection known only at run time is evaluated once, before the loop, and not for each member; ${this.loopFix()}`), { worded: true });
      }
    }
    version() { return this.info.version !== null ? this.info.version : 0; }
    loopReason() { return `in thym ${this.version()} each statement of a for each over a collection known only at run time runs over every member before the next statement starts`; }
    loopFix() { return 'inside a for each, write thym 1, where a loop\'s body runs member by member'; }
    sameLoopLet(node) {
      const mine = TRAILER.exec(String(node.name || ''));
      if (!mine) return null;
      for (const t of node.takes || []) {
        for (const g of this.nodes) {
          if (g === node || g.gives !== t || !g.repeats) continue;
          const theirs = TRAILER.exec(String(g.name || ''));
          if (theirs && theirs[0] === mine[0] && looseEq(g.provenance === undefined ? null : g.provenance, node.provenance === undefined ? null : node.provenance)) return [String(t), g];
        }
      }
      return null;
    }
    loopStatement(node) {
      const mt = TRAILER.exec(String(node.name || ''));
      const head = mt ? mt[0].slice(2) : 'for each';
      const line = node.line;
      const found = Array.from(this.info.statements.entries()).filter(([ln, text]) => text === head && Number.isInteger(line) && ln <= line).map(([ln]) => ln);
      return [cut(head), found.length ? Math.max(...found) : line];
    }
    passOf(v, row, k, coll) {
      let label;
      if (row && row.isThymValue && isDict((row.origin || {}).member)) label = String((row.origin.member.path) || ordinal(k));
      else if (row && row.isThymValue && row.type === 'line' && Number.isInteger(row.field('number'))) label = `line ${row.field('number')}`;
      else if (row && row.isThymValue && row.type === 'item') label = itemId(row) || ordinal(k);
      else if (coll.type === 'short' || coll.type === 'text') label = `line ${k}`;
      else label = ordinal(k);
      return `for ${v} = ${label}`;
    }
    member(e, scope) {
      if (e.k === 'Name') {
        if (scope.has(e.name) || (scope.program && this.info.lets.has(e.name))) return this.lookup(e.name, scope, null);
        return new Value('word', e.name);
      }
      return this.evalE(e, scope);
    }
    memberLabel(node) {
      const same = this.nodes.filter((n) => looseEq(n.step === undefined ? null : n.step, node.step === undefined ? null : node.step) && n.line === node.line);
      const k = same.indexOf(node);
      return ordinal(k >= 0 ? k + 1 : 1);
    }

    // -- the person's words ---------------------------------------------------------------------------------------
    words(text, depth) {
      depth = depth || 0;
      return text.replace(TEMP, (m0, n) => {
        const giver = this.byId.get(`R:node/${n}`);
        if (!isDict(giver) || giver.gives !== m0 || depth > 32) return m0;
        return '(' + this.words(String(giver.name || '').replace(TRAILER, ''), depth + 1) + ')';
      });
    }
    said(node) {
      const line = node.line;
      let text = Number.isInteger(line) ? this.info.statements.get(line) : null;
      if (!text) text = this.words(String(node.name || node.move || '').replace(TRAILER, ''));
      return cut(text);
    }
    at(node, passing) {
      const line = node.line;
      const where = Number.isInteger(line) ? `line ${line}` : 'a line the plan does not give';
      return `${this.said(node)} (${where}${passing ? ', ' + passing : ''})`;
    }
    worded(r, node, passing) {
      return new Refusal(r.stage, r.check, `${this.at(node, passing)}: ${r.message}`, r.line || node.line, r.file);
    }
    assert(st, scope) {
      this.sides = [];
      const ok = this.cond(st.cond, scope);
      const check = hasCovers(st.cond) ? 'coverage' : 'assert';
      const line = this.moveStack.length === 0 ? this.cur.node.line : null;
      let msg = st.message || (line ? this.info.messages.get(line) : null) || null;
      if (msg === null && !ok) msg = `${this.conditionSaid(st, line)} does not hold` + this.sides.map(([text, v]) => `; ${text} is ${describe(v)}`).join('');
      msg = msg || '';
      if (check === 'coverage') {
        const c = this.cur.checks.find((x) => x.name === 'coverage' && !x.ok && x.why);
        if (c) msg = `${msg} (${c.why})`;
      } else this.cur.checks.push({ name: 'assert', ok, why: ok ? '' : msg });
      if (!ok) throw new Stop(new Refusal('run', check, msg));
    }
    conditionSaid(st, line) {
      const said = Number.isInteger(line) ? this.info.statements.get(line) : null;
      if (said && said.startsWith('assert ')) return cut(pyStrip(said.slice(7).replace(ELSE_MSG, '')));
      return cut(this.words(condText(st.cond)));
    }

    // -- values ---------------------------------------------------------------------------------------------------
    lookup(name, scope, item) {
      if (scope.has(name)) return scope.get(name);
      if (scope.program && this.info.lets.has(name) && !this.letBusy.has(name)) {
        let e;
        try { e = readExpression(this.info.lets.get(name), this.moveNames); } catch (err) {
          if (!(err instanceof ReadError)) throw err;
          throw new Stop(new Refusal('run', 'parse', `the runtime could not read let ${name} = ${cut(this.info.lets.get(name), 40)}; that is ${RUNTIME_FAULT}`), { fault: `let ${name} = ${this.info.lets.get(name)}: ${err.message}` });
        }
        if (e.k !== 'Call') {
          this.letBusy.add(name);
          let v;
          try { v = this.evalE(e, new Scope([this.env], true)); } finally { this.letBusy.delete(name); }
          this.env.set(name, v);
          return v;
        }
      }
      if (item) return wrap(item.field(name));
      const hint = (this.program === null && scope.program) ? '; it is bound by a let whose value the plan does not hold (a filter folds into the node that reads it), and this run has only the plan: run it with the program beside the plan (--program)' : '';
      throw new Stop(new Refusal('run', 'unbound', `${name} is not bound${hint}`));
    }
    evalE(e, scope, item) {
      item = item || null;
      switch (e.k) {
        case 'Name': return this.lookup(e.name, scope, item);
        case 'Lit': return e.value;
        case 'ListLit': return new Value('list', e.items.map((x) => (x.k === 'Lit' && x.value.type === 'word' ? this.member({ k: 'Name', name: x.value.payload }, scope) : this.evalE(x, scope, item))));
        case 'FieldRead': return wrap(this.evalE(e.base, scope, item).field(e.name));
        case 'Filter': {
          const base = this.evalE(e.base, scope, item);
          if (base.type === 'folder') return filterFolder(base, (it) => this.cond(e.cond, scope, it));
          const rows = members(base);
          if (rows === null) throw new Stop(new Refusal('run', 'type', `where filters a volume, a fabula, a short or a list, and ${this.words(exprText(e.base))} is a ${base.type}`));
          return new Value('list', rows.filter((r) => this.cond(e.cond, scope, r)));
        }
        case 'Call': return this.call(e, scope, item);
        default:
          throw new Stop(new Refusal('run', 'runtime', `the runtime cannot evaluate a part of this statement; that is ${RUNTIME_FAULT}`), { fault: `cannot evaluate ${JSON.stringify(e)}` });
      }
    }
    cond(c, scope, item) {
      item = item || null;
      switch (c.k) {
        case 'BoolOp': return c.op === 'and' ? c.items.every((x) => this.cond(x, scope, item)) : c.items.some((x) => this.cond(x, scope, item));
        case 'Not': return !this.cond(c.item, scope, item);
        case 'Bare': return this.evalE(c.expr, scope, item).plain() === true;
        case 'Has': return this.evalE(c.base, scope, item).field(c.name) !== null;
        case 'Covers': {
          this.evalE(c.left, scope, item);
          this.evalE(c.right, scope, item);
          throw new Stop(new Refusal('run', 'coverage', 'check not implemented in the page: coverage reads EMF\'s cover map, which the server holds'));
        }
        case 'Cmp': {
          const av = this.evalE(c.left, scope, item);
          const bv = this.evalE(c.right, scope, item);
          if (item === null && c.op !== 'in') {
            this.sides = [[c.left, av], [c.right, bv]].filter(([x]) => x.k !== 'Lit').map(([x, v]) => [this.words(exprText(x, true)), v]);
          }
          const a = av.plain(), b = bv.plain();
          if (c.op === 'is') return pyEq(a, b);
          if (c.op === 'is not') return !pyEq(a, b);
          if (c.op === 'in') {
            if (Array.isArray(b)) return b.some((x) => pyEq(a, x));
            if (['text', 'short', 'string', 'line'].includes(bv.type)) {
              const needle = typeof a === 'string' ? a : av.text();
              return bv.text().includes(needle);
            }
            return false;
          }
          if (c.op === '=') return pyEq(a, b);
          if (typeof a === 'boolean' || typeof b === 'boolean' || !Number.isInteger(a) || !Number.isInteger(b)) return false;
          return c.op === '<' ? a < b : a > b;
        }
        default:
          throw new Stop(new Refusal('run', 'runtime', `the runtime cannot evaluate a condition of this statement; that is ${RUNTIME_FAULT}`), { fault: `cannot evaluate the condition ${JSON.stringify(c)}` });
      }
    }

    // -- calls ----------------------------------------------------------------------------------------------------
    ctx() {
      const self = this;
      return { run: this.madeRun, node: Object.assign({}, this.cur.node), decls: this.decls, rules: this.rules,
        now: this.started, emitted: this.emitted, slots: this.slots, withheld: this.withheld, stage: this.stage,
        program: this.info, engines: {}, trace: () => new Value('trace', this.traceSoFar()),
        withhold(...items) {
          for (const x of items) {
            if (Array.isArray(x)) this.withhold(...x);
            else if (x && x.isThymValue && x.type === 'list') this.withhold(...(x.payload || []));
            else if (x && x.isThymValue) { const key = itemKey(x); if (key) self.withheld.set(key, x); } else if (typeof x === 'string' && x) self.withheld.set(x, NOTHING);
          }
        } };
    }
    traceSoFar() { this.trace.records = this.records.slice(); return this.trace.toVolume(); }
    made(move, engine) {
      const step = this.cur.node.step;
      const n = isDict(step) && step.n !== undefined ? step.n : null;
      return { move, run: this.madeRun, step: n, node: nodeNumber(this.cur.node.id), engine };
    }
    engine(e) {
      const rank = (x) => (x.startsWith('model:') || x.startsWith('replay') ? 3 : (has(ENGINE_RANK, x) ? ENGINE_RANK[x] : 1));
      if (rank(e) >= rank(this.cur.engine)) this.cur.engine = e;
    }
    mergeChecks(verdicts) {
      for (const v of verdicts) {
        const old = this.cur.checks.find((c) => c.name === v.name);
        if (!old) this.cur.checks.push(Object.assign({}, v));
        else if (old.ok && !v.ok) Object.assign(old, v);
      }
    }
    call(e, scope, item) {
      const operands = e.operands.map((o) => this.evalE(o, scope, item));
      const names = e.operands.map((o, k) => (o.k === 'Name' ? o.name : `operand${k + 1}`));
      const mods = {};
      for (const [w, a] of Object.entries(e.mods)) {
        if (w === 'as' || w === 'by' || w === 'to') mods[w] = a;
        else if (w === 'where') {
          const [cond, text] = a;
          mods.where = { isWhere: true, text, test: (r) => this.cond(cond, scope, r),
            select(value) { return (members(value) || []).filter((r) => this.test(r)); } };
        } else if (w !== 'marked') mods[w] = this.evalE(a, scope, item);
      }
      let v = this.apply(e.move, operands, mods, names);
      if (has(e.mods, 'marked')) v = this.apply('mark', [v], { as: e.mods.marked }, ['marked']);
      return v;
    }
    apply(move, operands, mods, names) {
      if (this.info.moves.has(move)) return this.userMoveCall(move, operands);
      const decl = this.decls[move];
      if (!decl) throw new Stop(new Refusal('run', 'unknown-move', `the move ${move} is not declared`));
      const declared = decl.modifiers || {};
      if (has(mods, 'where') && !has(declared, 'where') && operands.length) {
        const w = mods.where;
        delete mods.where;
        operands = [new Value('list', w.select(operands[0]))].concat(operands.slice(1));
      }
      const inputs = {};
      operands.forEach((v, k) => { inputs[k < names.length ? names[k] : `operand${k + 1}`] = v; });
      for (const [w, v] of Object.entries(mods)) if (v && v.isThymValue) inputs[w] = v;
      const plainMods = {};
      for (const [k, v] of Object.entries(mods)) plainMods[k] = v && v.isAmount ? v.toDict() : (v && v.isWhere ? v.text : v);
      const checkNode = Object.assign({}, this.cur.node, { modifiers: plainMods });
      if (decl.asks === true) throw new Stop(new Refusal('run', 'agent-free', `${move} asks a model; agent-free is on`));
      for (const [words, code] of decl.code_when || []) {
        if (typeof mods.as === 'string' && words.includes(mods.as)) {
          throw new Stop(new Refusal('run', 'move', `the ${mods.as} kind of ${decl.name || move} (${code}) has no implementation here`));
        }
      }
      const fn = T.MOVES[move];
      if (!fn) throw new Stop(new Refusal('run', 'move', `the move ${move} has no implementation here`));
      const r = this.invoke(move, fn, this.ctx(), operands, mods);
      const pending = Object.values(inputs).some((x) => x && x.isThymValue && x.state === 'pending');
      const v = stamp(this.asValue(r, decl), this.made(move, 'code'), pending);
      if (pending) this.cur.state = 'pending';
      this.settle(move, decl, v, inputs, checkNode, 'code');
      return v;
    }
    invoke(move, fn, ctx, operands, mods) {
      try {
        if (has(ARITY, move) && ARITY[move] !== operands.length) {
          throw new TypeError(`${move}() takes ${ARITY[move] + 1} positional argument${ARITY[move] ? 's' : ''} but ${operands.length + 1} were given`);
        }
        return fn(ctx, ...operands, mods);
      } catch (e) {
        if (e instanceof Stop) throw e;
        if (e && e.isMoveError) throw new Stop(new Refusal('run', 'move', e.message || `${move} cannot go on with what it was given`));
        throw new Stop(new Refusal('run', 'move', `${move} failed inside its implementation; that is ${RUNTIME_FAULT}`), { fault: `${move}: ${e && e.name ? e.name : 'Error'}: ${e && e.message ? e.message : e}` });
      }
    }
    asValue(r, decl) {
      if (r && r.isThymValue) return r;
      if (r === null || r === undefined) return NOTHING;
      const alts = alternatives(decl.gives);
      if (alts.length > 1) {
        if (typeof r === 'string' && alts.includes('word')) return new Value('word', r);
        if (isDict(r) && alts.includes('item')) return new Value('item', r);
      }
      if (alts.length && alts[0] !== 'nothing') return new Value(alts[0], r);
      return wrap(r);
    }
    verdicts(decl, v, inputs, node) {
      const out = [];
      for (const name of decl.contract || []) {
        const r = T.verdict(String(name), v, inputs, node, decl, this.ctx());
        if (r instanceof Refusal) { this.mergeChecks(out); throw new Stop(r); }
        out.push({ name: String(name), ok: r[0], why: r[1] });
      }
      return out;
    }
    settle(move, decl, v, inputs, node, engine) {
      const verdicts = this.verdicts(decl, v, inputs, node);
      this.engine(engine);
      this.cur.attempts += 1;
      this.mergeChecks(verdicts);
      const bad = verdicts.find((x) => !x.ok);
      if (bad) throw new Stop(new Refusal('run', bad.name, bad.why || `${move}'s check ${bad.name} does not hold`));
    }

    // -- user moves ---------------------------------------------------------------------------------------------
    userMoveCall(name, operands) {
      const um = this.info.moves.get(name);
      if (operands.length !== um.params.length) throw new Stop(new Refusal('run', 'type', `${name} takes ${um.params.length} operand(s); it was given ${operands.length}`));
      const deep = this.moveStack.filter((m) => m === name).length;
      if (deep && um.depth === null) throw new Stop(new Refusal('run', 'recursion', `${name} calls itself`));
      if (deep && deep >= um.depth) throw new Stop(new Refusal('run', 'recursion', `${name} went ${deep + 1} deep; its depth is ${um.depth}`));
      const args = new Map(um.params.map((p, i) => [p[0], operands[i]]));
      const asks = um.keeps.length > 0 && Array.from(this.bodyMoves(name)).some((m) => (this.decls[m] || {}).asks === true);
      const nb = isDict(this.cur.node.budget) ? this.cur.node.budget : {};
      const budget = asks ? Math.max(1, parseInt(nb.attempts || 3, 10)) : 1;
      let repair = [];
      let attempt = 0;
      for (;;) {
        attempt += 1;
        this.moveStack.push(name);
        this.repairs.push(repair);
        let out;
        try { out = this.body(um.body, new Scope([new Map(args)], false)); } finally { this.repairs.pop(); this.moveStack.pop(); }
        if (out === null) throw new Stop(new Refusal('run', 'no-give', `${name} reached its end without a give`));
        if (!um.keeps.length) return out;
        const verdicts = um.keeps.map((k) => this.kept(k, out, args));
        const bad = verdicts.filter((v) => !v.ok);
        if (!bad.length) { this.mergeChecks(verdicts); return out; }
        this.cur.tries.push({ attempt, failed: bad.map((v) => ({ name: v.name, why: cpSlice(String(v.why), 0, 400) })) });
        const why = bad[0].why ? `: ${bad[0].why}` : '';
        if (!asks) { this.mergeChecks(verdicts); throw new Stop(new Refusal('run', bad[0].name, `${name} fails ${bad[0].name}${why}`)); }
        if (attempt >= budget) {
          this.mergeChecks(verdicts);
          throw new Stop(new Refusal('run', bad[0].name, `${name} still fails ${bad[0].name} after ${attempt} attempt${attempt !== 1 ? 's' : ''}${why}`));
        }
        repair = bad.map((v) => Object.assign({}, v));
      }
    }
    kept(k, value, given) {
      const [cname, against] = [k[0], (k[1] || []).slice()];
      const values = against.filter((a) => given.has(a)).map((a) => [a, given.get(a)]);
      const cb = this.info.contracts.get(cname);
      if (cb) {
        const why = this.holds(cb, [value].concat(values.map((x) => x[1])));
        return { name: cname, ok: why === null, why: why || '' };
      }
      const node = Object.assign({}, this.cur.node, { modifiers: {} });
      const r = T.verdict(cname, value, Object.fromEntries(values), node, null, this.ctx());
      if (r instanceof Refusal) throw new Stop(r);
      return { name: cname, ok: r[0], why: r[1] };
    }
    holds(cb, values) {
      const cur = this.cur;
      const saved = [cur.attempts, cur.checks.map((c) => Object.assign({}, c)), cur.state, cur.engine, this.sides.slice()];
      const run = (body, scope) => {
        for (const part of body) {
          const st = this.readStmt(part[2]);
          if (part[0] === 'for') {
            const coll = this.evalE(st.loop.coll, scope);
            let rows = members(coll) || [];
            if (st.loop.cond) rows = rows.filter((r) => this.cond(st.loop.cond, scope.child({ [st.loop.var]: r }), r));
            for (const r of rows) { const why = run(part[3], scope.child({ [st.loop.var]: r })); if (why !== null) return why; }
          } else if (st.form === 'let') scope.set(st.name, this.evalE(st.expr, scope));
          else if (st.form === 'assert') {
            this.sides = [];
            if (!this.cond(st.cond, scope)) {
              return st.message || (`${cut(this.words(condText(st.cond)))} does not hold` + this.sides.map(([text, v]) => `; ${text} is ${describe(v)}`).join(''));
            }
          }
        }
        return null;
      };
      try { return run(cb.body, new Scope([new Map(cb.params.map((p, i) => [p[0], values[i]]))], false)); } finally {
        [cur.attempts, cur.checks, cur.state, cur.engine, this.sides] = saved;
      }
    }
    body(body, scope, worded) {
      for (const part of body) {
        let out;
        try { out = this.part(part, scope, worded); } catch (e) {
          if (!(e instanceof Stop) || !worded || e.worded) throw e;
          const said = this.info.statements.get(part[1]) || pyStrip(stripComment(part[2]));
          const where = `line ${part[1]}` + (this.passes.length ? `, ${this.passes[this.passes.length - 1]}` : '');
          const r = e.refusal;
          throw new Stop(new Refusal(r.stage, r.check, `${cut(said)} (${where}): ${r.message}`, part[1], r.file), { worded: true, fault: e.fault });
        }
        if (out !== null && out !== undefined) return out;
      }
      return null;
    }
    part(part, scope, worded) {
      if (part[0] === 'if') {
        const st = this.readStmt(part[2]);
        return this.body(this.cond(st.cond, scope) ? part[3] : part[4], scope.child({}), worded);
      }
      if (part[0] === 'for') {
        const st = this.readStmt(part[2]);
        if (!st.loop) throw new Stop(new Refusal('run', 'parse', `the runtime could not read ${cut(part[2])} as a for each; that is ${RUNTIME_FAULT}`));
        const [kept] = this.loop(st, part[3], scope, worded);
        if (st.name) scope.set(st.name, new Value('list', kept));
        return null;
      }
      const st = this.readStmt(part[2]);
      if (st.form === 'give') return this.evalE(st.expr, scope);
      if (st.form === 'let') scope.set(st.name, this.evalE(st.expr, scope));
      else if (st.form === 'keep') {
        if (!this.keeping.length) throw new Stop(new Refusal('run', 'runtime', `a keep stands in no loop that collects; that is ${RUNTIME_FAULT}`));
        this.keeping[this.keeping.length - 1].push(this.evalE(st.expr, scope));
      } else if (st.form === 'assert') this.assert(st, scope);
      else if (st.form === 'emit') {
        const v = this.evalE(st.expr, scope);
        if (st.slot) this.slots.set(st.slot, v); else this.emitted.push(v);
        if (worded) { this.emitK += 1; this.cur.outputs.push(digestRow(`${st.slot || 'emit'}.${this.emitK}`, v, '')); }
      } else if (st.expr) this.evalE(st.expr, scope);
      return null;
    }
    readStmt(text) {
      try { return readStatement(text, this.moveNames, this.inMoves, this.whereMoves); } catch (e) {
        if (!(e instanceof ReadError)) throw e;
        throw new Stop(new Refusal('run', 'parse', `the runtime could not read ${cut(text)}; that is ${RUNTIME_FAULT}`), { fault: `${text}: ${e.message}` });
      }
    }

    // -- landing: every output or none ----------------------------------------------------------------------------
    land() {
      const landed = new Map();
      const prog = this.info.name || (this.plan.program || {}).name || 'the program';
      const r = this.programKeeps(prog);
      if (r) return r;
      const files = new Map(this.stage);
      for (const name of this.outputNames) {
        const v = this.env.get(name);
        if (!v) {
          const missed = this.nodes.filter((n) => n.gives === name && this.skipped.has(n.id));
          const why = missed.length ? `: the give at line ${missed[0].line} is on the branch not taken` : '';
          return new Refusal('run', 'no-give', `program ${prog} gives ${name}, and no give reached it${why}; nothing landed`);
        }
        if (v.payload && v.payload.isFolder) {
          let tree;
          try {
            if (Array.from(files.keys()).some((k) => k === name || k.startsWith(name + '/'))) throw new T.FolderError(`${name} is already there`);
            tree = v.payload.tree_files();
          } catch (e) {
            if (e instanceof T.FolderError) return new Refusal('run', 'output', `program ${prog} gives ${name}, a folder, and it could not be written: ${e.message}; nothing landed`);
            throw e;
          }
          for (const [p, data] of Object.entries(tree)) files.set(`${name}/${p}`, data);
          landed.set(name, `outputs/${name}`);
        } else {
          if (v.payload && v.payload.isVolume) {
            return new Refusal('run', 'output', `program ${prog} gives ${name}, a volume read from its folder, and the page cannot copy a folder; run it on the server; nothing landed`);
          }
          const fname = `${name}.${v.ext}`;
          files.set(fname, v.writeBytes());
          landed.set(name, `outputs/${fname}`);
        }
        this.trace.values[name] = v;
      }
      for (const rec of this.records) {
        for (const row of rec.outputs || []) {
          if (landed.has(row.name)) {
            const folder = !!(this.trace.values[row.name].payload && this.trace.values[row.name].payload.isFolder);
            row.path = landed.get(row.name) + (folder ? '/' : '');
          }
        }
      }
      for (const [n, rel] of landed) this.trace.outputs[n] = rel;
      return files;
    }
    programKeeps(prog) {
      for (const k of this.info.keeps) {
        const out = k[2] || (this.outputNames.length ? this.outputNames[0] : null);
        const v = out ? this.env.get(out) : undefined;
        if (!v) continue;
        let giver = null;
        for (let i = this.nodes.length - 1; i >= 0; i--) if (this.nodes[i].gives === out) { giver = this.nodes[i]; break; }
        giver = giver || this.nodes[this.nodes.length - 1];
        this.cur = new NodeState(giver);
        let verdict;
        try { verdict = this.kept(k, v, new Map(this.inputs)); } catch (e) {
          if (!(e instanceof Stop)) throw e;
          return new Refusal('run', e.refusal.check, `program ${prog} gives ${out}: ${e.refusal.message}; nothing landed`);
        }
        const rec = this.records.find((x) => x.node === giver.id);
        if (rec) rec.checks = (rec.checks || []).filter((c) => c.name !== verdict.name).concat([verdict]);
        if (!verdict.ok) {
          const why = verdict.why ? `: ${verdict.why}` : '';
          return new Refusal('run', verdict.name, `program ${prog} gives ${out}, and it fails ${verdict.name}${why}; nothing landed`);
        }
      }
      return null;
    }
  }

  /** What each step produced, for a readings panel: one row per record, its outputs with a short look at each. */
  function readings(trace, run) {
    return trace.records.map((r) => ({
      id: r.id, node: r.node, line: (run.byId.get(r.node) || {}).line === undefined ? null : run.byId.get(r.node).line,
      statement: run.byId.has(r.node) ? run.said(run.byId.get(r.node)) : r.name, move: r.move, engine: r.engine,
      summary: r.summary, passes: r.passes === undefined ? null : r.passes, checks: r.checks,
      outputs: (r.outputs || []).map((o) => Object.assign({}, o)),
    }));
  }

  /** Run a plan in the page (the module's docstring). Never throws for a program's fault: a refusal is a value. */
  function run(o) {
    const r = new Run(o || {});
    let out;
    try { out = r.go(); } catch (e) {
      return { ok: false, outcome: 'refused', refusal: new Refusal('run', 'runtime', `the page's runtime failed: ${e && e.message ? e.message : e}`), runId: r.runId, trace: null, traceText: null, files: {}, outputs: {}, readings: [] };
    }
    if (out.refusal) {
      return { ok: false, outcome: 'refused', refusal: out.refusal, runId: null, trace: null, traceText: null, files: {}, outputs: {}, readings: [] };
    }
    const vol = out.trace.toVolume();
    const files = {};
    for (const [k, v] of out.files) files[`outputs/${k}`] = v;
    const outputs = {};
    for (const [name, v] of Object.entries(out.trace.values)) {
      outputs[name] = { type: v.type, sha256: v.sha256, path: out.trace.outputs[name],
        text: v.payload && v.payload.isFolder ? null : T.decodeKeep(v.payload && v.payload.isFolder ? new Uint8Array(0) : v.writeBytes()) };
    }
    return { ok: out.trace.outcome === 'landed', outcome: out.trace.outcome, refusal: out.trace.refusal, runId: r.runId,
      trace: vol, traceText: dump(vol), files, outputs, readings: readings(out.trace, r) };
  }

  Object.assign(T, { run, Run, ProgramInfo, readStatement, readExpression, tokenize, stripComment, ReadError, cut,
    describe, exprText, condText, Trace, versionOf });
  if (typeof module === 'object' && module.exports) module.exports = T;
})(typeof globalThis !== 'undefined' ? globalThis : this);
