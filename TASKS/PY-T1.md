# [AGENT-TASK PY-T1] ORDER 16 PR #16 (E-70–E-74) — CI verification + ready-for-review report

**Lane:** Python (`majid-ghanbari-dost/Kandoo-Digital-Invoice`) — **Posted by:** exec-manager (2026-11-23, Asia/Tehran)
**How to report:** post your verification report as a comment on PR #16 itself and link it under this file (reply comment or new issue referencing `PY-T1`). PM is the trigger and the only merger.

## Context (verified 2026-11-23)
- PR #16 "ORDER 16: E-70–E-74 و آزمونهای synthetic" is **open** (non-draft), head `arena/d0587e71-kandoo-digital-invoice` @ `1e620cc`.
- Older PRs (#1–#15) are closed history — do not reopen them.

## Work items
1. Verify CI on PR #16: open the checks for head commit `1e620cc`, confirm every check (green/red) and record it.
2. Any red check: fix on the same branch `arena/d0587e71-kandoo-digital-invoice` and push; re-verify until green.
3. Confirm the PR description fully lists E-70–E-74 deliverables and synthetic-test evidence; if gaps, update the PR body.
4. Post the verification report comment on PR #16 containing:
   - Status per E-item (E-70, E-71, E-72, E-73, E-74): delivered / partial / deferred + one line each;
   - CI checks table (all checks, head commit SHA);
   - Synthetic-data confirmation (PM-06: synthetic fixtures only, no real data);
   - Anything explicitly NOT done + reason code;
   - Merge-readiness verdict for PM (mergeable now / blockers).
5. Update this file (`TASKS/PY-T1.md`) status line to `DONE` with the PR #16 comment link.

## Constraints
- Do NOT merge — PM is the merger (trigger role).
- Do NOT touch `.github/workflows/` (token has no workflows permission).
- Synthetic fixtures only (PM-06) — no real data anywhere.

## Definition of done
PR #16 CI green + verification report comment on PR #16 + status line updated in this file.

---
**Status:** DONE — closed by exec-manager 2026-11-24: CI green on head `1e620cc` (18 SUCCESS + 4 SKIPPED), PR OPEN/CLEAN/MERGEABLE, verification report: https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/16#issuecomment-7100112086 — remaining owner-side local gates (E-70 owner run, E-73 local structure check) are re-scoped into TASKS/PY-T2.md.
