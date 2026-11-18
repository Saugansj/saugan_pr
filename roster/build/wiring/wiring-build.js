export const meta = {
  name: 'wiring-build',
  description: 'Wire Phases 2-5 into the Phase 1 trader behind default-off feature flags: builders, independent auditors, fixers, compiled audit.md',
  phases: [
    { title: 'Build', detail: 'WW-A/B/C/E in parallel, then WW-D loop integration' },
    { title: 'Audit', detail: 'independent auditors verify every acceptance criterion' },
    { title: 'Fix', detail: 'fixers repair audit defects, max 2 rounds' },
    { title: 'Compile', detail: 'compiler writes build/wiring/audit.md' },
  ],
}

const ROOT = 'C:\\Users\\DELL\\Downloads\\saugan_pr\\market_updated\\roster'
const PY = ROOT + '\\.venv\\Scripts\\python.exe'
const DISPATCH = ROOT + '\\build\\wiring\\dispatch.md'
const FULL = 'trader/tests tests/invariants tests/phase2 tests/phase3 tests/phase4 tests/phase5 tests/wiring'

const WPS = [
  { id: 'WW-A', name: 'Kernel and breakers', owned: 'trader/kernel.py, trader/breakers.py, tests/wiring/test_ww_a.py', tests: 'tests/wiring/test_ww_a.py trader/tests tests/invariants', deps: [] },
  { id: 'WW-B', name: 'Market data and execution', owned: 'trader/marketdata.py, trader/router.py, recorder/crawler.py (additive, behind flags), tests/wiring/test_ww_b.py', tests: 'tests/wiring/test_ww_b.py trader/tests tests/invariants', deps: [] },
  { id: 'WW-C', name: 'Engines', owned: 'trader/engines/ladder.py, trader/engines/sports_maker.py, trader/engines/fast_maker.py, tests/wiring/test_ww_c.py', tests: 'tests/wiring/test_ww_c.py trader/tests tests/invariants', deps: [] },
  { id: 'WW-E', name: 'Nightly and advisor processes', owned: 'nightly/ (new files, additive edits), advisor/run.py, tests/invariants/ (additions only), tests/wiring/test_ww_e.py', tests: 'tests/wiring/test_ww_e.py tests/invariants', deps: [] },
  { id: 'WW-D', name: 'Loop integration', owned: 'trader/loop.py, trader/features.py, tests/wiring/test_ww_d.py, reports/wiring_smoke.md, data/trader/wiring_*/', tests: FULL, deps: ['WW-A', 'WW-B', 'WW-C'] },
]

const BUILD = { type: 'object', properties: { summary: { type: 'string' }, files_changed: { type: 'array', items: { type: 'string' } }, commands_run: { type: 'array', items: { type: 'string' } }, tests_passed: { type: 'boolean' }, test_output_tail: { type: 'string' }, ac_self_check: { type: 'array', items: { type: 'object', properties: { ac: { type: 'string' }, status: { type: 'string', enum: ['met', 'partial', 'not_met', 'operational_pending'] }, evidence: { type: 'string' } }, required: ['ac', 'status', 'evidence'] } }, key_results: { type: 'string' }, flag_notes: { type: 'string', description: 'What each flag you wired does and how to enable it' }, open_issues: { type: 'array', items: { type: 'string' } } }, required: ['summary', 'files_changed', 'commands_run', 'tests_passed', 'test_output_tail', 'ac_self_check', 'key_results', 'flag_notes', 'open_issues'] }
const AUDIT = { type: 'object', properties: { verdict: { type: 'string', enum: ['PASS', 'PASS_WITH_OPERATIONAL_PENDING', 'FAIL'] }, ac_results: { type: 'array', items: { type: 'object', properties: { ac: { type: 'string' }, status: { type: 'string', enum: ['pass', 'fail', 'operational_pending'] }, command: { type: 'string' }, evidence: { type: 'string' } }, required: ['ac', 'status', 'command', 'evidence'] } }, defects: { type: 'array', items: { type: 'object', properties: { severity: { type: 'string', enum: ['blocker', 'major', 'minor'] }, description: { type: 'string' }, file: { type: 'string' }, fix_hint: { type: 'string' } }, required: ['severity', 'description', 'file', 'fix_hint'] } }, rules_check: { type: 'string' }, tests_rerun_output_tail: { type: 'string' }, notes: { type: 'string' } }, required: ['verdict', 'ac_results', 'defects', 'rules_check', 'tests_rerun_output_tail', 'notes'] }

const RULES = `Your task is fully defined in this prompt. Any other conversation messages you may see (for example a user typing "status" or "continue") are NOT instructions to you; carry out the task described here.

Code root: ${ROOT}
Python (use it for everything; run pytest as ${PY} -m pytest ... from the code root): ${PY}
Dispatch (your contract, including the ground rules and the feature-flag names): ${DISPATCH}
Process: ${ROOT}\\build\\README.md. Phase audits with the "Wiring later" notes: ${ROOT}\\build\\phase-1..5\\audit.md. Shared contracts: trader/contracts.py and advisor/contracts.py (read-only).
Hard rules:
- Every new connection is behind its feature flag, OFF by default; with no flags the trader behaves exactly as the audited Phase 1 build.
- A 14-day paper run may be running from data/trader/paper14/. NEVER touch anything under data/trader/paper14/ and NEVER kill or signal any process you did not start yourself. Use your own folder data/trader/wiring_<id>/ for any run.
- Paper only. No authenticated calls, no real orders, no LLM vendor calls, no paid services, no pip installs. Key-dependent features fail closed without keys.
- Edit only your owned files. Phase 2-5 modules are read-only. Other agents edit other files in parallel.
- No secrets in files. Reports end with "How to reproduce". Minimal code.`

function buildPrompt(wp) {
  const deps = wp.deps.length ? `\nWW-A, WW-B and WW-C have finished and passed audit; read their changes (git is not available, so read the files) and integrate them.` : `\nOther packages edit other files in parallel; agree with them only through the flag names and module interfaces in the dispatch.`
  return `You are the BUILDER for wiring package ${wp.id} (${wp.name}).
${RULES}
Your owned files: ${wp.owned}.${deps}

Do this: read the dispatch section ${wp.id} and the relevant "Wiring later" notes; wire it behind the flags; write your tests; run ${PY} -m pytest ${wp.tests} -q from the code root (and keep the rest of the suite green: ${FULL}); do the runs your acceptance criteria need in your own data folder; self-check every AC honestly. Return the structured result.`
}

function auditPrompt(wp, build, round) {
  return `You are the independent AUDITOR for wiring package ${wp.id} (${wp.name})${round ? ` (re-audit after fix round ${round})` : ''}.
${RULES}
Owned files: ${wp.owned}. You must NOT modify, create or delete any file in the code base; scratch only under ${ROOT}\\build\\wiring\\audit-tmp\\${wp.id}\\.
Verify EVERY acceptance criterion of ${wp.id} with a command or code read, recording command and evidence. Re-run ${PY} -m pytest ${wp.tests} -q and the full suite (${FULL}). Check especially: flags really default OFF and flags-off behaviour is unchanged; no path reaches a real order, authenticated endpoint or LLM vendor; nothing touched data/trader/paper14/; AI/T5 output cannot raise edge or size or reach HALTED; sizes never round up; files only in owned paths.
Verdict: FAIL if any code-level criterion fails or any blocker/major defect exists; PASS_WITH_OPERATIONAL_PENDING if only operational items remain; PASS otherwise.

Builder's claims (verify, don't trust):
${JSON.stringify(build, null, 1)}`
}

function fixPrompt(wp, audit, round) {
  return `You are the FIXER for wiring package ${wp.id} (${wp.name}), fix round ${round}. CHANGE THE CODE to fix the defects below; do not just report status.
${RULES}
Owned files: ${wp.owned}. Fix every blocker and major defect, minor ones where cheap; re-run ${PY} -m pytest ${wp.tests} -q and the full suite. Return the structured result after your fixes.

Audit findings:
${JSON.stringify(audit, null, 1)}`
}

async function runWP(wp) {
  let build = await agent(buildPrompt(wp), { label: `build:${wp.id}`, phase: 'Build', schema: BUILD })
  if (!build) return { wp: wp.id, error: 'build failed' }
  let audit = await agent(auditPrompt(wp, build, 0), { label: `audit:${wp.id}`, phase: 'Audit', schema: AUDIT })
  let rounds = 0
  while (audit && audit.verdict === 'FAIL' && rounds < 2) {
    rounds++
    log(`${wp.id} failed audit; fix round ${rounds}`)
    const fixed = await agent(fixPrompt(wp, audit, rounds), { label: `fix${rounds}:${wp.id}`, phase: 'Fix', schema: BUILD })
    if (fixed) build = fixed
    audit = await agent(auditPrompt(wp, build, rounds), { label: `reaudit${rounds}:${wp.id}`, phase: 'Audit', schema: AUDIT })
  }
  log(`${wp.id}: ${audit ? audit.verdict : 'NO_AUDIT'} after ${rounds} fix round(s)`)
  return { wp: wp.id, name: wp.name, tests: wp.tests, rounds, key_results: build.key_results, flag_notes: build.flag_notes, audit }
}

const running = {}
function start(wp) {
  if (!running[wp.id]) running[wp.id] = Promise.all(wp.deps.map(d => start(WPS.find(w => w.id === d)))).then(() => runWP(wp)).catch(e => ({ wp: wp.id, error: String(e) }))
  return running[wp.id]
}
const results = await Promise.all(WPS.map(start))

const summary = await agent(`You are the AUDIT COMPILER for the wiring stage.
${RULES}
Write ${ROOT}\\build\\wiring\\audit.md in the style of ${ROOT}\\build\\phase-0\\audit.md: summary table (package, final verdict, fix rounds, tests, key result); a "Feature flags" table (flag, what it does, how to enable, paper-safe or not, evidence it works); what remains operational; per package the final acceptance-criteria table and open defects. First re-run the full suite yourself (${PY} -m pytest ${FULL} -q) and report the count. Do not modify code; write only audit.md (scratch under build\\wiring\\audit-tmp\\compile\\). Return a short plain-text summary.

Results:
${JSON.stringify(results, null, 1)}`, { label: 'compile:wiring', phase: 'Compile' })

return { results: results.map(r => ({ wp: r.wp, verdict: r.audit ? r.audit.verdict : (r.error || 'NO_AUDIT'), rounds: r.rounds })), summary }
