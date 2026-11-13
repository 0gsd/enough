// Runs Thym's in-page runtime (enough/static/thym/) under node for tests/test_thym_js_runtime.py.
// Reads one JSON request on stdin: {bundle: <bundle.page_bundle>, runId, now, inputsRoot}, or {dump: <tagged JSON>}
// to dump a mapping as the runtime does, or {planCheck: {plan, program}} for the page's check before it reads inputs. Writes one JSON answer on stdout: the run's outcome, refusal, trace volume,
// trace text and landed files (base64), or the dump's text.
'use strict';
const path = require('path');
const dir = path.join(__dirname, '..', 'enough', 'static', 'thym');
require(path.join(dir, 'core.js'));
require(path.join(dir, 'moves.js'));
const T = require(path.join(dir, 'runtime.js'));

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => { input += c; });
process.stdin.on('end', () => {
  const req = JSON.parse(input);
  if (req.dump !== undefined) {
    process.stdout.write(JSON.stringify({ text: T.dump(T.revive(req.dump)) }));
    return;
  }
  if (req.planCheck !== undefined) {
    const r = T.planCheck(req.planCheck);
    process.stdout.write(JSON.stringify({ refusal: r ? r.toJSON() : null }));
    return;
  }
  const b = req.bundle;
  const out = T.run({ plan: b.plan, program: b.program, inputs: b.inputs, decls: b.decls, manifests: b.manifests,
    runId: req.runId, now: req.now, inputsRoot: req.inputsRoot });
  const files = {};
  for (const [k, v] of Object.entries(out.files)) files[k] = T.toBase64(v);
  process.stdout.write(JSON.stringify({
    outcome: out.outcome, refusal: out.refusal ? out.refusal.toJSON() : null, trace: out.trace, traceText: out.traceText,
    files, readings: out.readings,
  }, (k, v) => (v instanceof T.ThymDate ? { $date: v.yaml } : v instanceof Map ? { $map: Array.from(v.entries()) } : v)));
});
