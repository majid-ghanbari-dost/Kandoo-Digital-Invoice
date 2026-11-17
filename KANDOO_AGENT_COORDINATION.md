# KANDOO DIGITAL INVOICE — O15 AGENT COORDINATION

## Current execution context

- Repository: `majid-ghanbari-dost/Kandoo-Digital-Invoice`
- Active Arena branch: `arena/d0587e71-kandoo-digital-invoice`
- O15 work remains on this branch; do not switch branches, merge, push to `main`, or open/merge a PR without explicit authorization.
- The historical P12/bootstrap snapshot in the earlier handoff is not the current O15 work state. See `AGENT_HANDOFF.md`'s current O15 section and `docs/o15-final-report.md`.

## Ownership and status

| Work item | Owner | Status |
|---|---|---|
| E-60 Windows extractor bundle / CLI | Arena implementation agent | COMPLETE — `o15-E-60-fix-1`; branch and tag CI green |
| E-61 local evidence / offline review queue | Arena implementation agent | COMPLETE — `o15-E-61`; branch and tag CI green |
| E-62 operator-label template | Arena implementation agent | COMPLETE — `o15-E-62`; branch and tag CI green |
| E-63 actual owner-capture run | Product Owner, on owner's computer only | BLOCKED — no owner capture/result available in this checkout; do not substitute synthetic or unrelated data |
| E-64 handoff / status report | Arena implementation agent | COMPLETE in the current E-64 changeset; owner run remains a blocker |
| E-65 Holoo v1.2 stretch | NONE until MUST sequence is complete | NOT STARTED — prohibited until E-63 is resolved |

`docs/questions/Q-15-01.md` records the resolved source-baseline issue. `docs/questions/Q-15-02.md` records the active E-63 owner-input/data-residency blocker and the safe local-run path.

## Coordination rules

1. One work item has one owner; do not edit another agent's active files.
2. Keep frozen contracts and golden outputs unchanged absent a documented blocker/approval.
3. Every technical choice is recorded in one line in `docs/decisions-made.md` with choice, reason, and rejected alternative.
4. Never claim accuracy or real-capture acceptance that was not measured. With no independent expected-value labels, report `NOT_SCORED` and `extracted_but_wrong: null`.
5. Real owner capture, OCR, crops, labels, hashes, and outputs stay on the owner's computer. Do not stage, commit, send to CI/upload, or paste them into chat.
6. For each completed task, use its own commit/tag and verify both branch and tag CI. Report links only for CI runs actually inspected.
7. Do not start E-65 before E-60 through E-64 MUST work is complete, including the owner-local E-63 run.

## Next executable action

The Product Owner downloads the Windows one-folder artifact from the successful E-62 tag workflow linked in `docs/o15-final-report.md`, runs it locally against the real capture with a fresh output folder under `%LOCALAPPDATA%\Kandoo\O15`, reviews the local evidence/labels, and retains every sensitive file locally. Return only a sanitized execution/status summary; no raw values, images, crops, hashes, or customer data are needed. If the owner cannot run it yet, keep E-63 BLOCKED and leave E-65 unstarted.
