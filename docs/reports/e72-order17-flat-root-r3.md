# E-72 round 3 — flat-root Canonical Invoice v0 vector

**Date:** 2026-10-12

**Status:** R3 vector and local verification complete; cross-lane review pending. No tag was created and no remote review is claimed.

## Vector

- File: `tests/golden/e72/canonical-invoice-v1-2-draft-vector-r3.json`
- Size: **1,227 bytes**
- SHA-256: `e56b80edeaca5e8630a04b13ca664853e9afaa9656d086c11f6b19b06f17fa86`
- The document has exactly the 16 required E-11 root fields. `provenance` is at root; `image_sha256` and `template_library_id` remain nested inside it. The vector is synthetic and remains a DRAFT. It contains no `base_invoice`, `synthetic_only`, `vector_id`, or `v1_2_draft_addendum` root field. The R2 vector and its original manifest entry are retained unchanged; the manifest now pins both vectors.

## Addendum disposition

The C# lane's recorded verdict says the v1.2 draft addendum has no home in frozen Canonical Invoice v0. R3 therefore keeps the Canonical v0 payload flat and excludes the addendum; the proposal schema remains separate and unapproved. The PHP repository could not be inspected in this run: both GitHub API and Git access returned HTTP 403 (`Resource not accessible by integration` / `Write access to repository not granted`). Consequently, no PHP position or cross-lane agreement is claimed. No `docs/questions/Q-*.md` was filed because no verified C#/PHP disagreement was available; the cross-lane contract question remains open pending PHP access/review.

## Verification

- `PYTHONPATH=src:scripts .venv/bin/python scripts/verify_e72_vectors.py` — **PASS**, 2 synthetic vectors.
- `PYTHONPATH=src:scripts .venv/bin/python -m pytest -q tests/test_e72_canonical_v1_2_draft.py` — **5 passed in 0.33s**.
- `PYTHONPATH=src:scripts .venv/bin/python scripts/run_order16_harness.py` — **2089 passed in 193.88s**; E-72 verifier and synthetic E-74 hard gate passed.
- Synthetic E-74 only: layout-1, layout-2, and layout-3 each `layout_match=1/1`, `numeric_exact=5/5`, `EXTRACTED-but-wrong=0`, `REVIEW/missing=0`. These metrics are not accuracy evidence for the three approved capture groups.

A third C# review must be requested against the published R3 vector after it is available on the PR branch. PR #16 remains open/create-only; no merge, rebase, close, main push, or tag movement/deletion was performed.
