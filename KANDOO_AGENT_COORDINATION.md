# KANDOO DIGITAL INVOICE — O15 AGENT COORDINATION

## Current execution context

- Repository: `majid-ghanbari-dost/Kandoo-Digital-Invoice`
- Active Arena branch: `arena/d0587e71-kandoo-digital-invoice`
- O15 work stays on this branch; do not switch branches, merge, push to `main`, or open/merge a PR without explicit authorization.
- `docs/o15-final-report.md` records E-60 through E-64. For the newly authorized E-63 run, use the later executive order and the ZIP checklist at `docs/o15-e63-capture-zip-checklist.md`; the E-64 report's local-only/E-62-Windows instructions are superseded for this run's location/version.

## Ownership and status

| Work item | Owner | Status |
|---|---|---|
| E-60 Windows extractor bundle / CLI | Arena implementation agent | COMPLETE — `o15-E-60-fix-1`; branch and tag CI green |
| E-61 local evidence / offline review queue | Arena implementation agent | COMPLETE — `o15-E-61`; branch and tag CI green |
| E-62 operator-label template | Arena implementation agent | COMPLETE — `o15-E-62`; branch and tag CI green |
| E-63 capture ZIP and run | Arena implementation agent after owner supplies ZIP | WAITING — owner declares invoices synthetic/non-sensitive and authorizes sandbox execution; no ZIP received or processing started |
| E-64 handoff / status report | Arena implementation agent | COMPLETE — `o15-E-64`; branch and tag CI green |
| E-65 Holoo v1.2 stretch | Arena implementation agent after E-63 | NOT STARTED — start only after E-63 result is documented |

`docs/questions/Q-15-01.md` records the resolved source-baseline issue. `docs/questions/Q-15-02.md` records the current ZIP wait, sandbox authorization, and no-repository boundary.

## Coordination rules

1. One work item has one owner; do not edit another agent's active files.
2. Keep frozen contracts and golden outputs unchanged absent a documented blocker/approval.
3. Every technical choice is recorded in one line in `docs/decisions-made.md` with choice, reason, and rejected alternative. The requested E-63 owner-decision line is to be added with the result record after the run.
4. Never claim accuracy or acceptance not measured. Without independent expected-value labels, report `NOT_SCORED` and `extracted_but_wrong: null`.
5. The owner-declared synthetic ZIP may arrive in chat for this run. Keep the ZIP, extracted input and all outputs only in a temporary sandbox location outside the repository. No capture data or derived results may enter any repository, commit, or workflow; no workflow/schema change is needed.
6. E-63 provenance: verify tag `o15-E-60-fix-1` at SHA `68be0e7c08c264a064bae598b5a3917fe6bf4dd9` and its downloaded workflow artifact. Execute the Linux source from that same SHA; the Windows artifact is not runnable on Linux. Report the platform/method honestly.
7. For completed task tags, verify branch/tag CI. E-63's result documentation commit is explicitly no-tag; E-65 requires its own tag and green CI.
8. If the ZIP is still absent after 24 hours, send one text-only reminder when the conversation next becomes active; no background wait or reminder is scheduled.

## Next executable action

Wait for the owner's ZIP. On arrival, validate it against `docs/o15-e63-capture-zip-checklist.md`; download and verify the E-60 tag artifact, process each invoice folder with Linux source at the exact tag SHA, and keep data/outputs outside this Git worktree. Report only the requested aggregate metrics and sanitized technical/operational error categories. Then update `AGENT_HANDOFF.md` and add the one owner-decision line to `docs/decisions-made.md` in a documentation-only commit without a tag; begin E-65 only afterwards. If no ZIP arrives within 24 hours, one text-only reminder is due on the next active conversation.
