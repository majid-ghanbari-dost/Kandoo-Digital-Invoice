# KANDOO DIGITAL INVOICE — PYTHON AGENT HANDOFF

This document is maintained under standing order SO-01.

## 1. Current repository state

- Repository: `majid-ghanbari-dost/Kandoo-Digital-Invoice`.
- Fixed session branch: `arena/60d98123-kandoo-digital-invoice`.
- Current local shallow checkout before this SO-01 update: `HEAD=1b79e630a8f476ed13d2d9fa7b6fb1c3de391cd0`; `git rev-parse --is-shallow-repository` returned `true`.
- Read-only remote checks: `stable-e-38` peels to `c143c6d4da379201d489d2caf22f835e05d9c6cc`; remote `w11-E-39` through `w11-E-44` tag targets match the task SHAs below. PR #15 is OPEN, unmerged, based on `main`, with remote head `9f397278bdd03c83d471fe7fbe740d3af080dc76`.
- `blocker-record BR-SO01-LOCAL-HEAD`: the local branch is at `1b79e630a8f476ed13d2d9fa7b6fb1c3de391cd0`, while the PR/remote branch is at `9f397278bdd03c83d471fe7fbe740d3af080dc76`. The `stable-e-38` and W11 task commit objects and tags are absent from local refs/object lookup in this shallow checkout, though their remote tag targets were verified read-only. Do not fetch, unshallow, switch/reset, push, or move tags to resolve this discrepancy without a separate authorization. The local status is not evidence that the remote PR is behind.
- Other pre-existing modified and untracked paths are outside this handoff update and remain untouched.

## 2. W11 task status

The following statuses, tags, and SHAs are manager-authoritative. Remote annotated-tag targets were read-only checked and match the listed commits; those commit objects are not present in this local shallow checkout.

| Task | Status | Tag | Commit SHA | Record |
|---|---|---|---|---|
| E-39 | accepted | `w11-E-39` | `199ea0d9efca8be8987039cbdf8a4a8674c80965` | Docs-only repository/data-flow map and E-31 guide. |
| E-40 | blocked (blocker-record) | `w11-E-40` | `f1a41626dbbe59eddc3af960a41574d2ba4fdf96` | Awaiting approved v1.1 normative addendum and resumption amendment. |
| E-41 | accepted | `w11-E-41` | `495995f9bb1c789faafb5a1a24335efe804ffbd0` | Seeded, reproducible synthetic-layout generator; no real customer data. |
| E-42 | blocked (blocker-record) | `w11-E-42` | `cc546d221149e43826b8e309d16c0fb106def74e` | Same v1.1 addendum/resumption dependency; no accuracy metrics are to be fabricated. |
| E-43 | blocked (blocker-record) | `w11-E-43` | `b2a341e80129fe7cc0fcb69adf9cc8501759a710` | Same dependency; no Holoo mapping has started. |
| E-44 | delivered | `w11-E-44` | `9f397278bdd03c83d471fe7fbe740d3af080dc76` | Final report in chat plus marker commit; no report file change. |

## 3. Valid decisions and open blockers

- Baseline record: `stable-e-38` is the verified base `c143c6d4da379201d489d2caf22f835e05d9c6cc` (remote annotated-tag target verified; local object unavailable in the shallow checkout).
- E-40/E-42/E-43 are blocked by the v1.1 addendum chain. Manager-reported state: the schemas have been delivered and hash-verified; T-DOC-C2C3 and the technical challenge are complete; Contract Addendum v1.1 APPROVED NORMATIVE by the Product Owner 2026-11-10; U7 closed as (b). Resume only after the approved addendum is delivered through the approved single-file courier route and a resumption amendment is issued.
- Verified courier copies currently held under `/tmp/arena-coding-uploads/`:
  - `CLOUD-CONTRACT.md`: 58,755 bytes; SHA-256 `6d4f491a84e93803ab61831084713e5fe7209fdbfbc3d22d794037975037663e`.
  - `issued-invoice-v1-1.schema.json`: 2,011 bytes; SHA-256 `04af72824d15bd17d01a98604265c39bf8d5d5da8ed11d406fe74a28bd5ad15c`.
  - `public-invoice-view-v1-1.schema.json`: 2,174 bytes; SHA-256 `78620a233199dbe191e9c9cf4264a0080aaba744a53e2a820056bf98f4992650`.
  These are temporary courier copies, not committed repository files. Reverify before relying on them in a later session.
- U7 is a confirmed cross-stack hazard: Hub/Cloud control-character and DEL escaping may diverge in canonical JSON and cause `ENTRY_HASH_MISMATCH`. U7 is closed by the approved addendum as option (b): pin the conservative escaping profile for both stacks plus shared cross-stack golden vectors. Do not guess or alter the frozen schema/contract.
- PR #15 remains OPEN and unmerged; leave it untouched.

## 4. Reference paths and verification status

- `AGENT_HANDOFF.md`: tracked handoff document; this file.
- `/tmp/arena-coding-uploads/CLOUD-CONTRACT.md` and the two schema files above: present and hash-verified at the time of this update; temporary, outside Git.
- `docs/DECISIONS.md` and `docs/E-39-python-technical-map.md` through `docs/E-43-holoo-mapping-gate-blocked.md`: present only in the untracked worktree; not present in the current `HEAD`. Their authoritative/remote status is to be confirmed.
- `docs/schemas/v1-1/` and `docs/CLOUD-CONTRACT.md`: absent from the local worktree. The schema/contract files currently held are the courier copies listed above.
- T-DOC-C2C3 and the PM addendum draft: no local or courier file path was found during this check; path to be confirmed. The completion/review state is manager-reported.
- `docs/DECISIONS.md` is present locally but untracked; its applicability to the v1.1 addendum is to be confirmed.

## 5. Delivery boundaries and active Git rules

- The frozen contract and hash-pinned schemas are read-only. New behavior or normative decisions belong in a new approved addendum; do not edit frozen artifacts or infer missing rules.
- No legal/tax claims or tax-authority integration. E-43 Holoo mapping remains unstarted until all required gates pass.
- Documents arrive only via the approved single-file courier route; verify size and SHA-256 before use. Preserve input bytes and do not repair a mismatch.
- For this session, work only on the fixed branch `arena/60d98123-kandoo-digital-invoice`. No force-push; no tag moves; `w11-E-*` tags stay pinned; reports are independent commits. No push to `main`, no merge, and no PR #15 action. Do not unshallow without a separate decision.
- Leave all pre-existing untracked paths untouched. For this SO-01 step, only `AGENT_HANDOFF.md` is authorized to change.
