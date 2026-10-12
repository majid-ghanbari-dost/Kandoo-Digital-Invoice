# Issue #4 — replacement reference pipeline implementation and bounded handoff

Date: 2026-10-12. Owner: primary implementation agent (Agent 1).
Branch: `arena/61fdaf1b-kandoo-digital-invoice`.
Verified main baseline: `b6c3e08b49bad97429d50dcf135095a0cb6be536`.
Starting branch HEAD: `9f5557d91a84235c837ad76e294b4f9ab9d1cda0` (diagnostic only).
Status: **IMPLEMENTED + EXECUTED TEST EVIDENCE**, not PO acceptance or merge.
Exact source/publication commits and archive hashes: delivery README in this PR.

## Authorization and bounded artifact check

The Product Owner's current **SINGLE-PASS EXECUTION MISSION — KANDOO MVP GAP
IMPLEMENTATION** explicitly authorizes replacement: the original workspaces were
deleted and the original package could not be retrieved. This supersedes the old
Issue #4 prohibition on replacement for this mission. This implementation is NEW;
it is not represented as the original 19-file package or its reported tests.

Executed this mission: clean assigned branch; `git ls-remote` confirmed main;
read Issue #4 body/comments via `gh issue view 4 --json body,comments`; inspect
`git ls-files '*pipeline*' '*mvp*' '*zip' '*MANIFEST*'`. Only the prior governance
archive/manifest were present; no original pipeline package appeared. The preceding
bounded investigation also found reported original commit `87c9505602b788d0a2b9ad7ad0a6e9bea780c677`
unavailable locally and via GitHub (404). No repeated deleted-workspace search.

Authorization comment attempted with `gh issue comment 4 --body ...` on 2026-10-12
before implementation. Exact returned error:

```text
Message: Resource not accessible by integration, Locations: [{Line:1 Column:49}]
```

That authorization comment **was not posted**. The PR body/comment is the fallback
record under GOV-PP-01 §1/الف; an actual Issue comment is still required to close
that publication witness. No HTTP status is inferred from this GraphQL message.

## Selected gap and eligibility

The repository had callable domain services but no reusable non-test application
composition for capture → complete canonical assembly. `src/calibration/stack.py`
only wires a pilot stack to the gate; `src/run_smoke_canonical_assembly.py` and
`src/run_smoke_digital_invoice.py` prove service compositions inside destructive
synthetic smoke harnesses, not a reusable/non-destructive caller API.

Selected gap: **additive, durable, replayable reference capture-to-canonical Python
API**, reusing the frozen public services, gate decisions, VOR and full-chain trace.
This needs no OCR selection, source mapping inference, UI/receipt format, tax adapter,
new lifecycle state, CLI product scope or calibration decision. All validation rules
and bindings are explicit caller declarations, not new policy defaults.

Focused capability boundary (not a general architecture review):
- Capture/extraction/validation/canonical engine: pre-existing services, now composed
  through `src/pipeline/`; synthetic reference-format path tested here.
- Digital lifecycle: existing `src/digital_invoice/`; regression/smoke executed;
  no automatic open/issue added.
- Exact product/customer linking: existing `src/product_candidate/` and
  `src/customer_linking/`; regression/smoke executed, no automatic creation added.
- Windows/Android apps, role onboarding, customer receipt access, native inventory
  application and OS print-spooler integration: not supplied by this increment;
  the Python/reference path must not be advertised as those products.
- Receipt presentation (DEF5), adapter mapping (DEF6), retention policy (DEF4),
  thresholds (WP-12.3) and CLI scope remain outside this implementation.

## Actual behavior

`PipelineWorkspace` owns eleven SQLite stores and closes handles in reverse order,
including partial construction failure. The input rule registry is validated before
creating directories/files. No default tolerance, precision or rounding mode.

`PipelineService.process` performs preflight, aggregate/ingest, **explicit capture
VOR even on replay**, reconstruct/extract/bind/normalize/derive/validate/project/gate,
gate VOR, ACCEPTED-only assembly, invoice VOR and whole-chain trace. Exact outcomes
are retained; failures and REVIEW/REJECT/ALREADY_CANONICALIZED stop without later
stages. `DerivationDeferred` is retained, not guessed away, and passed through to
frozen validation/domain/gate handling. Unexpected errors preserve their cause and
completed-stage context. A durable prefix resumes by resubmitting the same input;
no cross-store transaction or new identity/deduplication scheme is invented.

## Exact added paths

Source / API documentation:
- `src/pipeline/__init__.py`
- `src/pipeline/model.py`
- `src/pipeline/service.py`
- `src/pipeline/workspace.py`
- `src/pipeline/README.md`

Focused tests:
- `src/pipeline/tests/conftest.py`
- `src/pipeline/tests/test_pipeline_execution.py`
- `src/pipeline/tests/test_pipeline_boundary.py`

Report / executed evidence:
- `specs/ISSUE-4-pipeline-implementation-report.md`
- `deliveries/issue-4-replacement/evidence/environment.txt`
- `deliveries/issue-4-replacement/evidence/focused-tests.txt`
- `deliveries/issue-4-replacement/evidence/full-regression.txt`
- `deliveries/issue-4-replacement/evidence/smoke-tests.txt`
- `deliveries/issue-4-replacement/evidence/boundary-check.txt`

Delivery metadata (second, nonrecursive publication commit):
- `deliveries/issue-4-replacement/README.md`
- `deliveries/issue-4-replacement/project.zip`
- `deliveries/issue-4-replacement/MANIFEST-SHA256.txt`
- `deliveries/issue-4-replacement/ARCHIVE-SHA256.txt`

No pre-existing file is modified. `AGENT-CONNECTIVITY-TEST.md` is preserved verbatim
from the prior commit; it appears in the cumulative PR only because that diagnostic
commit already belongs to this branch. No Frozen/accepted source/test, existing
contract, register or global handoff is edited. PR #1's ownership of
`AGENT_HANDOFF.md` / `KANDOO_AGENT_COORDINATION.md` is respected (verified using
`gh pr list` and `gh pr diff 1 --name-only`). This report contains the increment's
bounded handoff instead of changing unrelated/owned governance records.

## Executed tests — actual outputs, not prior-agent claims

Environment: Linux, Python **3.11.2**, pytest **9.1.1** in `/home/user/.venv`.
Production dependencies remain stdlib + repository packages. Initially system
`python -m pytest --version` failed with `No module named pytest`; resolved by
creating the isolated venv and installing pytest, not by changing project dependencies.

From repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/.venv/bin/python -m pytest src/pipeline/tests -q -p no:cacheprovider
# 48 passed in 9.09s
```

From `src/`:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/user/.venv/bin/python -m pytest -q -p no:cacheprovider
# 1654 passed in 179.82s (0:02:59)
```

All 21 existing smoke runners were executed in fresh paths. Exact per-run commands,
stdout and `EXIT_CODE=0` are preserved in `evidence/smoke-tests.txt`. Reproduce from
repository root with the following same loop (temporary directory name varies):

```python
import os, subprocess, sys, tempfile
from pathlib import Path
with tempfile.TemporaryDirectory(prefix='kandoo-smokes-', dir='/home/user') as temp:
    scripts = sorted(Path('src').glob('run_smoke*.py'))
    for script in scripts:
        cmd = [sys.executable, str(script), str(Path(temp) / script.stem)]
        print('$ ' + ' '.join(cmd), flush=True)
        result = subprocess.run(cmd, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        print(f'EXIT_CODE={result.returncode}', flush=True)
        if result.returncode:
            sys.exit(result.returncode)
    print(f'ALL {len(scripts)} EXISTING SMOKE RUNNERS PASSED')
```

Actual final line: `ALL 21 EXISTING SMOKE RUNNERS PASSED` (exit 0).
Includes physical-purge default-deny/storage-stability smoke, digital lifecycle,
canonical assembly/gate, calibration and synthetic read-only Holoo spike. No real
Holoo/production data connection was used.

During development the first focused run had **3 failed, 41 passed**. Two were new
test expectations corrected to the existing contracts (`customer_reference`, and
S2 definite duplicate = REJECTED, not ALREADY_CANONICALIZED). The third exposed a
missing wrapper-level capture VOR on replay; the new composition now explicitly
calls `read_evidence` each run without changing frozen reconstruction behavior.
Then **45 passed**, followed by three additional replay/multipage/final-verification
checks: the final **48 passed** above. Full regression was run after those changes.

No CI, Windows/Android, Python 3.12+, real OS kill/power-loss, multi-process writer or
real POS/OCR tests were run. Existing date-sensitive provenance test passed on this
execution date; its frozen source was not changed.

## Acceptance evidence (increment-only; no register/PO acceptance claim)

| Check (see pipeline README for authorities) | Status | Executed evidence |
|---|---|---|
| P-1 ordered capture through actual canonical fields/lines/provenance | PASS | cold-start and multipage tests |
| P-2 stable replay/restart, resumable committed prefix | PASS | entity-count/restart; two interruption points; retry after final trace failure |
| P-3 preserve REVIEW/REJECT/duplicate routing, never bypass gate | PASS | missing tax/date; exact mismatch; distinct S1/same S2; new projection/same S1 |
| P-4 fail closed on corruption, unknown/refused/unavailable outcomes | PASS | capture/gate/invoice tamper; fourteen-stage unknown-outcome matrix |
| P-5 no policy defaults or forbidden side effects / Frozen edits | PASS | declaration/import/AST/DB-set tests; baseline byte comparison; retention smoke |
| P-6 resource ownership/preflight | PASS | constructor cleanup; repeated close; malformed declaration/page tests |

## Limitations and bounded continuation handoff

Delivered scope is a local trusted **reference-format Python API**, not the whole
store/customer MVP. It has no network/auth layer, product CLI, encrypted DB, process
lock or automatic Digital Invoice acts. Verification is point-in-time; no multi-store
snapshot/atomicity. Between-stage interruption replay is tested; incomplete writes
inside a lower store still require that layer's existing recovery APIs. Replays can
append evidence/update verification timestamps; no claim of byte-stable databases.
Changing origin/binding on an old gate decision does not amend it; frozen replay
semantics remain authoritative. Original package equivalence is unknown and not claimed.

Next owner/action: TM reviews this isolated PR using focused tests and archive hash
verification; PO retains merge/acceptance authority. Next eligible code increment is
an explicitly requested adapter/caller of this Python API only when that caller's
contract is authorized; do not infer a product CLI, receipt UI, Windows integration,
real extraction engine or auto-issuance policy from this delivery. D-09/CLI and all
named deferred decisions stay pending. No further implementation is pre-authorized
by this handoff.

Rollback: remove/revert only this additive package, report/evidence and delivery
metadata on an authorized change; no existing schema migration to reverse. Preserve
any application-owned workspace data and the prior diagnostic file. Nothing was merged.
