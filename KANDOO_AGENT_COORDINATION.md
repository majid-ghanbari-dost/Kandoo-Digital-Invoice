# KANDOO DIGITAL INVOICE — O15 AGENT COORDINATION

## Current execution context

- Repository: `majid-ghanbari-dost/Kandoo-Digital-Invoice`
- Active Arena branch: `arena/d0587e71-kandoo-digital-invoice`
- O15 work stays on this branch; do not switch branches, merge to `main`, push to `main`, or open/merge a PR without explicit authorization.
- `docs/o15-final-report.md` and `AGENT_HANDOFF.md` are authoritative for current E-63 results and the E-65 boundary.

## Ownership and status

| Work item | Owner | Status |
|---|---|---|
| E-60 Windows extractor bundle / CLI | Arena implementation agent | COMPLETE — `o15-E-60-fix-1`; branch and tag CI green |
| E-61 local evidence / offline review queue | Arena implementation agent | COMPLETE — `o15-E-61`; branch and tag CI green |
| E-62 operator-label template | Arena implementation agent | COMPLETE — `o15-E-62`; branch and tag CI green |
| E-63 sandbox measurement | Arena implementation agent | RUN COMPLETE — source `o15-E-63-fix-1`; extractor result `REVIEW`, all aggregates and limitations recorded; accuracy `NOT_SCORED` |
| E-64 handoff / status report | Arena implementation agent | COMPLETE — `o15-E-64`; branch and tag CI green |
| E-65 Holoo v1.2 stretch | Arena implementation agent after owner supplies scope | NOT STARTED — no executable task/acceptance criteria found; do not invent behavior or tag |

`docs/questions/Q-15-01.md` records the resolved source-baseline issue. `docs/questions/Q-15-02.md` records the resolved synthetic-data authorization, E-63 run, sandbox-only boundary, and artifact limitation.

## Coordination rules

1. One work item has one owner; do not edit another agent's active files.
2. Keep frozen contracts and golden outputs unchanged absent a documented blocker and explicit approval.
3. Record substantive technical decisions in `docs/decisions-made.md` with choice, reason, and rejected alternative.
4. Do not claim accuracy without independent expected-value labels. E-63 accuracy remains `NOT_SCORED` and `extracted_but_wrong` remains `null`.
5. Capture data, OCR values, images/crops, raw result JSON, and logs stay only in a temporary sandbox directory. Only aggregate status/counts and sanitized technical reasons may be documented. No capture content enters any repository, commit, tag, CI, or workflow.
6. E-63 initial run is retained as a BLOCKED result in the report/handoff. Its fix-forward is exactly one API-compatible call replacement using Pillow `11.1.0`; no dependency bump, glyph-bank modification, extraction threshold change, schema, contract, workflow, or golden change.
7. E-60 workflow artifact ID `14305290850` has declared digest `sha256:60f9baee9b8910d2817878d9777627b60ae3dde275d74cc8263eb53c9d5be083`. One authenticated API retry returned EOF and zero bytes; actual artifact hash remains unverified. E-63 was run from the approved Linux source tag `o15-E-63-fix-1` per executive instruction.
8. The remote `o15-e63-transfer` branch was deleted after the capture bundle passed exact size/SHA validation. It was not recreated; the capture remains outside Git.
9. E-63 documentation is a separate no-tag commit. E-65 requires its own tag and green branch/tag CI after its scope and acceptance criteria are supplied.

## E-63 result summary

- First run: source SHA `68be0e7c08c264a064bae598b5a3917fe6bf4dd9`; `BLOCKED / REJECT`, exit `20`, one blocked page, zero numeric candidates. Cause: `preprocessing.py:642` called `Image.get_flattened_data()`, absent in pinned Pillow `11.1.0`. E-05 default bank was also unavailable because its expected real fixtures are absent.
- Fix-forward: `o15-E-63-fix-1`, commit `89f78b2099d0f15d01bbf84bd68cc1a997c754c2`; replace `get_flattened_data()` with equivalent flattened `getdata()` and add one synthetic regression test. Pillow remains `11.1.0`.
- Full local suite: `1702 passed`; `scripts/verify_o15_e60.py` passed. Branch CI [44080880091](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44080880091) and tag CI [44081030928](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44081030928) passed.
- Final run: Linux x86_64, CPython `3.11.2`, Pillow `11.1.0`; one invoice/page; exit `10`, result `REVIEW`; nine numeric candidates, all `REVIEW`; E-06 `PARTIAL_MATCH`/`NEW_LAYOUT`; default glyph templates loaded, glyph drift `REVIEW`; E-05 bank unavailable; accuracy `NOT_SCORED`.

## Next executable action

Request the E-65 scope and acceptance criteria from the owner. Once provided, implement only that scope on the current branch; run the full suite and parity checks, commit, tag E-65, and verify green branch/tag CI. Do not alter `main`, and do not copy any E-63 data or raw output into the repository.
