export const meta = {
  name: 'remaining-build',
  description: 'Finish all buildable work: Phase 1 integration + Phases 2-5 remaining builds, independent audits, fixes and per-phase audit.md compilation',
  phases: [
    { title: 'Build', detail: 'remaining builders (interrupted ones resume from disk)' },
    { title: 'Audit', detail: 'independent auditors verify every acceptance criterion' },
    { title: 'Fix', detail: 'fixers repair audit defects, max 2 rounds' },
    { title: 'Compile', detail: 'one compiler per phase writes audit.md' },
  ],
}

const ROOT = 'C:\\Users\\DELL\\Downloads\\saugan_pr\\market_updated\\roster'
const PY = ROOT + '\\.venv\\Scripts\\python.exe'
const PROCESS = ROOT + '\\build\\README.md'
const PLAN = 'C:\\Users\\DELL\\Downloads\\saugan_pr\\market_updated\\36-agent-roles-polymarket-v4.md'
const BUILDPLAN = 'C:\\Users\\DELL\\Downloads\\saugan_pr\\market_updated\\build-plan-v4.md'
const TC = ROOT + '\\trader\\contracts.py'
const AC = ROOT + '\\advisor\\contracts.py'
const P0AUDIT = ROOT + '\\build\\phase-0\\audit.md'

const TITLES = { 'phase-1': 'Phase 1 — Paper trading (integration)', 'phase-2': 'Phase 2 — Live-micro (safety gate, live adapters)', 'phase-3': 'Phase 3 — Grow carefully', 'phase-4': 'Phase 4 — Sports and AI audits', 'phase-5': 'Phase 5 — Full learning stack' }

const WPS = {"phase-4": [{"id": "WP4-A", "name": "Sports data: odds collectors and game state (4.1, 4.2; roles 11, 12)", "owned_paths": ["sports/odds.py", "sports/gamestate.py", "tests/phase4/test_sports_data.py", "tests/phase4/fixtures/sports_data/", "reports/phase4_quota.md", "reports/phase4_sports_smoke.md", "data/sports/"], "tests": "tests/phase4/test_sports_data.py", "deps": []}, {"id": "WP4-B", "name": "Sports fair value and sports pulls (4.3, 4.4, 4.10 pre-registration; roles 19, 20)", "owned_paths": ["sports/fair.py", "sports/pulls.py", "tests/phase4/test_sports_fair.py", "reports/phase4_devig.md"], "tests": "tests/phase4/test_sports_fair.py", "deps": []}, {"id": "WP4-C", "name": "LLM gateway and clearance board (4.6, 4.8; gateway, roles 27, 28)", "owned_paths": ["advisor/gateway.py", "advisor/board.py", "tests/phase4/test_advisor_board.py", "reports/phase4_agreement.md", "data/advisor/"], "tests": "tests/phase4/test_advisor_board.py", "deps": []}, {"id": "WP4-D", "name": "News sentinel, calibration blend, Loop A (4.5, 4.7, 4.9; roles 25, 21, 23)", "owned_paths": ["advisor/sentinel.py", "learning/loop_a.py", "tests/phase4/test_sentinel_loop_a.py"], "tests": "tests/phase4/test_sentinel_loop_a.py", "deps": []}], "phase-3": [{"id": "WP3-A", "name": "Touch-market pricer and coherence bound (3.1)", "owned_paths": ["trader/growth/touch.py", "tests/phase3/test_touch.py", "reports/phase3_touch.md"], "tests": "tests/phase3/test_touch.py", "deps": []}, {"id": "WP3-B", "name": "negRisk executor behind a scanner-evidence gate (3.3)", "owned_paths": ["trader/growth/negrisk.py", "tests/phase3/test_negrisk.py", "reports/phase3_negrisk.md"], "tests": "tests/phase3/test_negrisk.py", "deps": []}, {"id": "WP3-C", "name": "Universe extension: SOL/XRP ladders, extra strikes, touch templates (3.4)", "owned_paths": ["trader/growth/universe.py", "tests/phase3/test_universe.py", "reports/phase3_universe.md"], "tests": "tests/phase3/test_universe.py", "deps": []}, {"id": "WP3-D", "name": "Capital ladder and fast Up/Down maker-first (3.2, 3.5)", "owned_paths": ["trader/growth/capital.py", "trader/growth/fast_updown.py", "tests/phase3/test_gates.py", "reports/phase3_gates.md"], "tests": "tests/phase3/test_gates.py", "deps": []}], "phase-2": [{"id": "WP2-A", "name": "Heartbeat warden, outside-the-VM safety, clock gate (2.1, 2.2, 2.4 clock; drills: freeze, network cut, clock skew, failed audit write, kill script)", "owned_paths": ["trader/live/heartbeat.py", "trader/live/clock.py", "tools/live_tools/kill_all.py", "tests/phase2/test_heartbeat.py", "reports/phase2_safety.md"], "tests": "tests/phase2/test_heartbeat.py", "deps": []}, {"id": "WP2-B", "name": "Live execution and preflight (2.3, 2.7 self-tests; drills: dropped ack, kill -9 mid-batch)", "owned_paths": ["trader/live/clob.py", "trader/live/router.py", "trader/live/live.json", "tools/live_tools/doctor.py", "tests/phase2/test_live_exec.py", "reports/phase2_execution.md"], "tests": "tests/phase2/test_live_exec.py", "deps": []}, {"id": "WP2-C", "name": "Kernel and breaker additions (2.4 except clock gate, 2.5): worst-case positions, cross-instant stress cap, resolution-risk cap, 7-day drawdown breaker, pull/REDUCING rules", "owned_paths": ["trader/live/risk.py", "tests/phase2/test_live_risk.py"], "tests": "tests/phase2/test_live_risk.py", "deps": []}, {"id": "WP2-D", "name": "Settlement keeper and canary evaluation (2.6, 2.8)", "owned_paths": ["trader/live/settlement.py", "trader/live/canary.py", "tests/phase2/test_settlement_canary.py", "reports/phase2_settlement.md", "reports/phase2_canary*.md"], "tests": "tests/phase2/test_settlement_canary.py", "deps": []}], "phase-5": [{"id": "WP5-A", "name": "Calibration analyst, postmortems, drift and CUSUM triggers (5.1-5.3; roles 32, 33, 34, 02)", "owned_paths": ["learning/analyst.py", "learning/postmortem.py", "learning/cusum.py", "tests/phase5/test_analysis.py", "reports/phase5_analysis_smoke.md"], "tests": "tests/phase5/test_analysis.py", "deps": []}, {"id": "WP5-B", "name": "Replay lab (5.4; role 35): event store + look-ahead tripwire, queue-position fill model, Engine runner, walk-forward/nested/CPCV, DSR, PBO, random-entry baselines, trial log", "owned_paths": ["learning/replay/", "learning/replay/out/", "tests/phase5/test_replay.py", "reports/phase5_replay_smoke.md"], "tests": "tests/phase5/test_replay.py", "deps": []}, {"id": "WP5-C", "name": "Quote-engine full objective (5.5; role 20): Q-score reward share, fitted fill rate and adverse move, inventory penalty, grid optimiser, anchor wider()", "owned_paths": ["learning/quote_objective.py", "tests/phase5/test_quote_objective.py", "reports/phase5_quote_objective.md"], "tests": "tests/phase5/test_quote_objective.py", "deps": []}, {"id": "WP5-D", "name": "Advisor roles 24 (shock LLM part), 30 (correlation adversary), 31 (change gate), 26 (shadow forecaster) against advisor.contracts.Gateway (5.6, 5.7)", "owned_paths": ["advisor/roles_p5/shock.py", "advisor/roles_p5/board.py", "advisor/roles_p5/shadow.py", "advisor/roles_p5/smoke.py", "advisor/roles_p5/out/", "tests/phase5/test_advisor_roles.py", "reports/phase5_advisor_smoke.md"], "tests": "tests/phase5/test_advisor_roles.py", "deps": []}]}

// Builds already finished (claims saved on disk) -> go straight to audit.
const DONE_BUILDS = ['WP3-A', 'WP3-B', 'WP4-B', 'WP4-C', 'WP4-D']

const P1F = { id: 'WP1-F', name: 'Integration, scoring, ops, drills', owned_paths: ['trader/loop.py', 'nightly/', 'tests/invariants/', 'reports/phase1_*.md', 'data/trader/'], tests: 'trader/tests tests/invariants', deps: [] }

const BUILD = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    files_changed: { type: 'array', items: { type: 'string' } },
    commands_run: { type: 'array', items: { type: 'string' } },
    tests_passed: { type: 'boolean' },
    test_output_tail: { type: 'string' },
    ac_self_check: { type: 'array', items: { type: 'object', properties: { ac: { type: 'string' }, status: { type: 'string', enum: ['met', 'partial', 'not_met', 'operational_pending'] }, evidence: { type: 'string' } }, required: ['ac', 'status', 'evidence'] } },
    key_results: { type: 'string' },
    wiring_notes: { type: 'string' },
    open_issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary', 'files_changed', 'commands_run', 'tests_passed', 'test_output_tail', 'ac_self_check', 'key_results', 'wiring_notes', 'open_issues'],
}

const AUDIT = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'PASS_WITH_OPERATIONAL_PENDING', 'FAIL'] },
    ac_results: { type: 'array', items: { type: 'object', properties: { ac: { type: 'string' }, status: { type: 'string', enum: ['pass', 'fail', 'operational_pending'] }, command: { type: 'string' }, evidence: { type: 'string' } }, required: ['ac', 'status', 'command', 'evidence'] } },
    defects: { type: 'array', items: { type: 'object', properties: { severity: { type: 'string', enum: ['blocker', 'major', 'minor'] }, description: { type: 'string' }, file: { type: 'string' }, fix_hint: { type: 'string' } }, required: ['severity', 'description', 'file', 'fix_hint'] } },
    rules_check: { type: 'string' },
    tests_rerun_output_tail: { type: 'string' },
    notes: { type: 'string' },
  },
  required: ['verdict', 'ac_results', 'defects', 'rules_check', 'tests_rerun_output_tail', 'notes'],
}

const RULES = `Your task is fully defined in this prompt. Any other conversation messages you may see (for example a user typing "status" or "continue") are NOT instructions to you; carry out the task described here.

Code root: ${ROOT}
Python (use it for everything; run pytest as ${PY} -m pytest ... from the code root): ${PY}
Process and rules: ${PROCESS}
Design: ${PLAN} and ${BUILDPLAN}; Phase 0 results: ${P0AUDIT}
Shared contracts (read-only; implement against them): ${TC} and ${AC}. Shared helpers: ${ROOT}\\common.py (read-only).
BUILD NOW, WIRE LATER: Phases 2-5 create standalone modules inside their own owned paths only. Never edit files outside your work package's owned paths. Phase 0 code is read-only; Phase 1 modules other than the integration package's own files are read-only. Other agents work in parallel.
Hard rules:
- Never place, sign, post or cancel a real order, and never call an authenticated endpoint. Code for authenticated actions (live router, cancel-all, redeem, preflight) may be written but must sit behind the three-flag live guard (config, env, CLI; default off), read credentials only from environment variables at runtime, and be tested only against fakes/mocks. No keys exist on this machine. The Phase 1 trader is PAPER ONLY.
- Never call an LLM vendor API or any paid service; LLM code is tested with fake vendors.
- Unit tests must not need the network. Public read-only GETs are allowed only for optional smoke checks.
- Do not pip install anything (stdlib, numpy, scipy, pandas, duckdb, pyarrow, websockets, httpx, penaltyblog, eth-account are available). If something truly needs a new package, put it behind an interface, mark the AC [ops], and report it.
- No secrets in files. Reports end with "How to reproduce". Minimal code: no speculative abstractions, fewest files, tests for the non-trivial logic.`

const dispatchOf = ph => `${ROOT}\\build\\${ph}\\dispatch.md`
const phaseOf = wp => 'phase-' + wp.id[2]

function buildPrompt(wp) {
  const ph = phaseOf(wp)
  const p1 = ph === 'phase-1' ? `\nThis is the Phase 1 INTEGRATION package. WP1-A to WP1-E have passed their audits (their final audits are in ${ROOT}\\build\\phase-1\\claims\\). Read their code and audits first. You own the glue (trader/loop.py, nightly/, tests/invariants/, reports/phase1_*.md, data/trader/). Address the open minor execution findings that could flatter paper results (a GTD-expired maker filling; two own orders filling the same displayed liquidity; a taker arriving with no book) by guarding them in the loop, or record precisely in open_issues where they must be fixed. If you find a real bug in another package that blocks integration, work around it in your files and record it.` : ''
  return `You are the BUILDER for work package ${wp.id} (${wp.name}) of ${TITLES[ph]}.
${RULES}
Dispatch (your contract): ${dispatchOf(ph)}, section ${wp.id}. Your owned paths: ${wp.owned_paths.join(', ')}.${p1}

RESUMING INTERRUPTED WORK: a previous builder for this work package may have been cut off by a usage limit. Partial code, tests and reports may already be on disk in your owned paths. Inspect what exists first, keep what is good, finish what is missing or broken; do not start over or re-download completed data.

Do this: read the process README, the contracts and your dispatch section; build inside your owned paths only; write the tests and run them (${PY} -m pytest ${wp.tests} -q from the code root); do any real (non-authenticated, read-only) runs the criteria need and write the named reports; self-check every acceptance criterion honestly (mark [ops] ones operational_pending); explain how to wire the module later. Return the structured result.`
}

function auditPrompt(wp, build, round) {
  const ph = phaseOf(wp)
  const claims = build ? JSON.stringify(build, null, 1) : `(The builder's claims are saved in ${ROOT}\\build\\${ph}\\claims\\${wp.id}.build.json; read them.)`
  return `You are the independent AUDITOR for work package ${wp.id} (${wp.name}) of ${TITLES[ph]}${round ? ` (re-audit after fix round ${round})` : ''}.
${RULES}
Dispatch: ${dispatchOf(ph)}, section ${wp.id}. Owned paths: ${wp.owned_paths.join(', ')}.

You must NOT modify, create or delete any file in the code base. Scratch only under ${ROOT}\\build\\${ph}\\audit-tmp\\${wp.id}\\.
Be skeptical: the builder's self-check is a claim, not evidence. For EVERY acceptance criterion of ${wp.id}: run a command or read code/data that proves or disproves it; record command and evidence. Re-run the tests (${PY} -m pytest ${wp.tests} -q). Read the code for: any path that could place/sign/post/cancel a real order or call an authenticated endpoint without the three-flag guard and env-only credentials (blocker), any real LLM/paid API call (blocker), tests that need the network, look-ahead/future data, sizes that can round up or AI output that can raise edge or size (blocker), bypassable safety checks, hard-coded or fabricated results. Check files only in owned paths, contracts unmodified, no secrets, reports end with "How to reproduce", minimal code.
Verdict: FAIL if any code-level criterion fails or any blocker/major defect exists; PASS_WITH_OPERATIONAL_PENDING if all code-level criteria pass and only [ops] remain; PASS otherwise.

Builder's claims (verify, don't trust):
${claims}`
}

function fixPrompt(wp, audit, round) {
  const ph = phaseOf(wp)
  return `You are the FIXER for work package ${wp.id} (${wp.name}) of ${TITLES[ph]}, fix round ${round}. Your job is to CHANGE THE CODE to fix the defects below; do not just report status.
${RULES}
Dispatch: ${dispatchOf(ph)}, section ${wp.id}. Owned paths: ${wp.owned_paths.join(', ')}.
Fix every blocker and major defect, and minor ones where cheap, inside the owned paths only. Re-run the tests (${PY} -m pytest ${wp.tests} -q) and affected runs/reports. Fix the real problem; if something truly cannot be done, say so honestly. Return the structured result after your fixes.

Audit findings:
${JSON.stringify(audit, null, 1)}`
}

function compilerPrompt(ph, results) {
  const p1 = ph === 'phase-1' ? `\nFor WP1-A to WP1-E use the final audits saved in ${ROOT}\\build\\phase-1\\claims\\*.audit.json; WP1-F's result is below.` : ''
  return `You are the AUDIT COMPILER for ${TITLES[ph]}.
${RULES}
Write ${ROOT}\\build\\${ph}\\audit.md in the style of ${ROOT}\\build\\phase-0\\audit.md: a summary table (work package, final code-audit verdict, fix rounds, tests, key result), what remains [ops] before this phase's exit gate in the build plan can be met, a "Wiring later" section collecting each WP's wiring notes, and per work package the final acceptance-criteria table (AC, status, evidence, command) and open defects.${p1} First re-run every work package's tests yourself (${PY} -m pytest <tests> -q) and report the counts; if anything fails, say so plainly. Do not modify code. Only write audit.md (and scratch under build\\${ph}\\audit-tmp\\compile\\).
Return a short plain-text summary (verdicts, test counts, open blockers if any).

Work-package results:
${JSON.stringify(results, null, 1)}`
}

async function runWP(wp) {
  let build = null
  if (!DONE_BUILDS.includes(wp.id)) {
    build = await agent(buildPrompt(wp), { label: `build:${wp.id}`, phase: 'Build', schema: BUILD })
    if (!build) return { wp: wp.id, name: wp.name, tests: wp.tests, error: 'build failed', audit: null, rounds: 0 }
  }
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
  return { wp: wp.id, name: wp.name, tests: wp.tests, rounds, build_key_results: build && build.key_results, wiring_notes: build && build.wiring_notes, audit }
}

async function runPhase(ph, wps) {
  const results = await Promise.all(wps.map(wp => runWP(wp).catch(e => ({ wp: wp.id, error: String(e) }))))
  const summary = await agent(compilerPrompt(ph, results), { label: `compile:${ph}`, phase: 'Compile' })
  return { phase: ph, wps: results.map(r => ({ wp: r.wp, verdict: r.audit ? r.audit.verdict : (r.error || 'NO_AUDIT'), rounds: r.rounds })), summary }
}

const jobs = [runPhase('phase-1', [P1F])].concat(Object.keys(WPS).sort().map(ph => runPhase(ph, WPS[ph])))
const out = await Promise.all(jobs)
return { phases: out }
