# KANDOO DIGITAL INVOICE — O15 AGENT COORDINATION

## Current execution context

- Repository: `majid-ghanbari-dost/Kandoo-Digital-Invoice`
- Active Arena branch: `arena/d0587e71-kandoo-digital-invoice`
- O15 work stays on this branch; do not switch branches, merge to `main`, push to `main`, or open/merge a PR without explicit authorization.
- `docs/o15-final-report.md` and `AGENT_HANDOFF.md` contain the E-63 three-axis evidence and current E-65 gate.

## Ownership and status

| Work item | Owner | Status |
|---|---|---|
| E-60 Windows extractor bundle / CLI | Arena implementation agent | COMPLETE — `o15-E-60-fix-1`; branch and tag CI green |
| E-61 local evidence / offline review queue | Arena implementation agent | COMPLETE — `o15-E-61`; branch and tag CI green |
| E-62 operator-label template | Arena implementation agent | COMPLETE — `o15-E-62`; branch and tag CI green |
| E-63 sandbox measurement | Arena implementation agent | EXECUTION/EVIDENCE COMPLETE — source `o15-E-63-fix-1`; extractor output `REVIEW`; criterion report complete; final owner acceptance/disposition pending |
| E-64 handoff / status report | Arena implementation agent | COMPLETE — `o15-E-64`; branch and tag CI green |
| E-65 Holoo v1.2 stretch | Arena implementation agent after owner decision | NOT STARTED — requires E-63 disposition and executable E-65 scope/acceptance criteria |

`docs/questions/Q-15-01.md` records the resolved source-baseline issue. `docs/questions/Q-15-02.md` records the E-63 authorization, transfer cleanup, artifact limitation, result and pending disposition.

## Coordination rules

1. One work item has one owner; do not edit another agent's active files.
2. Keep frozen contracts and golden outputs unchanged absent a documented blocker and explicit approval.
3. Record substantive technical decisions in `docs/decisions-made.md` with choice, reason, and rejected alternative.
4. Do not claim accuracy without independent expected-value labels. E-63 accuracy remains `NOT_SCORED` and `extracted_but_wrong` remains `null`.
5. Capture data, OCR values, images/crops, raw result JSON, and logs stay only in a temporary sandbox directory. Only aggregate statuses/counts and sanitized technical reasons may be documented. No capture content enters any repository, commit, tag, CI, or workflow.
6. E-63 initial `BLOCKED / REJECT` result is retained in report/handoff. Fix-forward changed only `get_flattened_data()` to equivalent `getdata()` under Pillow `11.1.0`; no dependency bump, glyph-bank modification, extraction threshold, output contract, schema, workflow, or golden change.
7. The specific equivalence/regression test is `test_line_mask_flattened_pixel_count_uses_pillow_11_1_data_api`; it checks the expected removal count, cleaned output, and that the source image stays unchanged. Full local suite and Ubuntu/Windows CI passed on the tagged fix commit.
8. E-60 workflow artifact ID `14305290850` has declared digest `sha256:60f9baee9b8910d2817878d9777627b60ae3dde275d74cc8263eb53c9d5be083`. One authenticated API retry returned EOF and zero bytes; actual artifact hash remains unverified. E-63 used the approved Linux source tag `o15-E-63-fix-1` as executive-authorized.
9. Remote `o15-e63-transfer` was deleted after exact capture size/SHA validation. It was not recreated; input and raw outputs remain sandbox-only.
10. E-63 is not automatically accepted by a green code CI or a weak/strong extraction result. Report technical health, actual extraction quality, and checklist compliance separately, with uncertain provenance/accuracy explicitly marked.
11. E-65 may not start until the owner formally dispositions E-63 and supplies executable E-65 scope/acceptance criteria. It requires its own tag and green branch/tag CI after authorization.

## E-63 evidence summary

- Initial source `o15-E-60-fix-1` / SHA `68be0e7c08c264a064bae598b5a3917fe6bf4dd9`: `BLOCKED / REJECT`, exit `20`, one blocked page and zero numeric candidates. `preprocessing.py:642` called `Image.get_flattened_data()`, absent in pinned Pillow `11.1.0`; E-05 default fixtures were also unavailable.
- Fix tag `o15-E-63-fix-1` / SHA `89f78b2099d0f15d01bbf84bd68cc1a997c754c2`: one API call replacement and the named synthetic regression test. Full suite `1702 passed`, parity verifier PASS; branch CI [44080880091](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44080880091) and tag CI [44081030928](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44081030928) succeeded on Ubuntu and Windows.
- Two post-fix runs from that exact tag/source had identical aggregates and schema-valid JSON: one invoice/page, exit `10`, verdict `REVIEW`, nine candidates all `REVIEW`, E-06 `PARTIAL_MATCH`/`NEW_LAYOUT`; default Glyph templates loaded, glyph drift `REVIEW`; E-05 bank unavailable; accuracy `NOT_SCORED`.
- Criteria disposition is detailed per item in `docs/o15-final-report.md`: input structure/integrity/method/reporting passed; variety is not required; synthetic/non-sensitive status is owner-asserted; source origin is not independently provable; accuracy is unscorable; artifact bytes/hash are unverified. Formal E-63 acceptance remains for owner disposition.

## Next executable action

Request the owner's formal E-63 disposition on the documented criteria and the E-65 scope/acceptance criteria. Only then, if authorized, implement E-65 on the current branch, run the full suite/parity, create its own tag, and verify green branch/tag CI. Do not alter `main` or copy E-63 data/raw output into the repository.
