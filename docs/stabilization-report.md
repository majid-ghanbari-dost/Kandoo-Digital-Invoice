# STABILIZE-V2 — stabilization and image-integrity report

**Date:** 2026-10-17 (workspace local time, Asia/Tehran)
**Repository:** `majid-ghanbari-dost/Kandoo-Digital-Invoice`
**Branch:** `arena/9dc17500-kandoo-digital-invoice`
**Scope:** verify and freeze the B2-1 baseline, inventory PNG files, confirm the invoice #32 fixture against the owner's `5.png`, run the requested test suite, and preserve prior WIP. This report has the 17 requested sections. No B2-2 work was started.

## 1. Scope and guardrails

This stabilization adds only `scripts/verify_image_integrity.py` and `docs/stabilization-report.md`. The inventory uses Pillow and Python's standard library; it performs no OCR and makes no network, VLM, or cloud API calls. No production behavior, adapter/preprocessing code, glyph classifier, frozen contract/default, B2-5 wrapper, or B2-1 diagnosis was changed. No image was edited. No merge to `main` was attempted.

## 2. Initial local state

The branch name was correct, but the initial local checkout did not match the supplied B2-1 HEAD:

- Initial branch: `arena/9dc17500-kandoo-digital-invoice`
- Initial local HEAD: `1b79e630a8f476ed13d2d9fa7b6fb1c3de391cd0`
- Initial `origin/<branch>` tracking ref: absent; checkout was shallow.
- Initial worktree: `AGENT_HANDOFF.md` modified and prior-task paths untracked.
- There were no existing stashes before preserving this WIP.

The worktree was not reset until after the stash was created and the remote target was confirmed.

## 3. Remote verification and baseline alignment

The authorized read-only fetch was run:

```sh
git fetch origin
```

The remote branch was confirmed to contain `8bfee82b7416a2fa18dd40092c222ebbf69767e8`. With the WIP safely stashed, the following was run:

```sh
git reset --hard origin/arena/9dc17500-kandoo-digital-invoice
```

Git reported:

```text
HEAD is now at 8bfee82 docs(payable): B2-1 diagnosis of segmentation failure
```

At the B2-1 baseline, local HEAD and fetched `origin/arena/9dc17500-kandoo-digital-invoice` both resolved to:

```text
8bfee82b7416a2fa18dd40092c222ebbf69767e8
```

This aligned the local branch to an already-existing remote commit; it did not rewrite remote history. No force-push was used.

## 4. B2-0 through B2-1 commit history

The verified baseline history, in order, is:

| Short SHA | Full SHA | Author date (UTC) | Subject |
|---|---|---|---|
| `a0ce97c` | `a0ce97cef9c6ad7f76bccbe7e88f7f0a55981393` | 2026-10-16 18:58:54 | `docs(git): report B2-0 branch sync` |
| `8d441e2` | `8d441e25b65cef41fceaae64a1ab9b49747f9b58` | 2026-10-17 01:50:50 | `feat(layout): fail-closed wrapper B2-5 (OK/REVIEW/BLOCKED)` |
| `6ad1dc9` | `6ad1dc9ab413998714e45887f1970ea9edc0bbb1` | 2026-10-17 02:02:39 | `feat(adapter): rebuild T1 numeric_authority flag (D1=YES, lost in B2-0)` |
| `8bfee82` | `8bfee82b7416a2fa18dd40092c222ebbf69767e8` | 2026-10-17 02:19:46 | `docs(payable): B2-1 diagnosis of segmentation failure` |

## 5. Annotated tag

The annotated tag was created on the B2-1 baseline and pushed before the stabilization files were added:

- Tag: `stable-b2-1`
- Tag object SHA: `71072bfb4de882bd9a8b932474339c7db26b3cd6`
- Peeled target commit: `8bfee82b7416a2fa18dd40092c222ebbf69767e8`
- Message: `Stable state after B2-1 (pending image verification)`
- Push output confirmed: `[new tag] stable-b2-1 -> stable-b2-1`.

The tag intentionally remains on the B2-1 baseline, not on the stabilization commit.

## 6. Preserved stash inventory

To protect the initial modified/untracked work before resetting, this stash was created and remains intact:

- `stash@{0}` SHA: `6bbd1d480a58eb53383cbafb800db54023b3b385`
- Message: `stabilize: preserve WIP`
- Plain `git stash show --stat stash@{0}` sees the tracked `AGENT_HANDOFF.md` change: 110 lines, 56 insertions and 54 deletions; the plain view omits untracked files.
- `git stash show --stat --include-untracked stash@{0}` reports 68 paths, 13,953 insertions, and 54 deletions.
- Recommendation: preserve it until owner/PM review; do not apply or drop it in this stabilization task. None of these stashed changes were added to the stabilization commit.

Complete path list from `git stash show --name-only --include-untracked 'stash@{0}'`:

```text
AGENT_HANDOFF.md
KANDO_AGENT_COORDINATION.md
deliveries/image-extraction-ocr/13.png
deliveries/image-extraction-ocr/31.png
deliveries/image-extraction-ocr/5.png
deliveries/image-extraction-ocr/cell-preprocessing-benchmark.log
deliveries/image-extraction-ocr/cell-preprocessing-comparison.md
deliveries/image-extraction-ocr/cell-preprocessing-issuance-guard.log
deliveries/image-extraction-ocr/dynamic-layout-projection.log
deliveries/image-extraction-ocr/glyph-classifier-build-13-rows03-08.png
deliveries/image-extraction-ocr/glyph-classifier-build-3invoices.log
deliveries/image-extraction-ocr/glyph-classifier-evaluate-13row-3invoice-build.log
deliveries/image-extraction-ocr/holo_row_detection.png
deliveries/image-extraction-ocr/real-holoo-spatial-evidence.md
deliveries/image-extraction-ocr/synthetic-confidence-review.log
deliveries/image-extraction-ocr/synthetic-digital-invoice-evidence.md
deliveries/image-extraction-ocr/synthetic-english-regression.log
deliveries/image-extraction-ocr/synthetic-ocr-success.log
deliveries/image-extraction-ocr/synthetic-persian-confidence-review.log
deliveries/image-extraction-ocr/synthetic-persian-ocr-e2e.log
deliveries/image-extraction-ocr/synthetic-spatial-regression-en.log
deliveries/image-extraction-ocr/synthetic-spatial-regression-fa.log
deliveries/image-extraction-ocr/wp-holoo-image-extraction-09-report.md
deliveries/image-extraction-ocr/wp-holoo-image-extraction-10-e2e.log
deliveries/image-extraction-ocr/wp-holoo-image-extraction-10-report.md
deliveries/issue-4-smoke-suite/ARCHIVE-SHA256.txt
deliveries/issue-4-smoke-suite/MANIFEST-SHA256.txt
deliveries/issue-4-smoke-suite/README.md
deliveries/issue-4-smoke-suite/kandoo-issue4-smoke-suite-aca72c94.zip
docs/PROJECT_STATE.md
docs/git-sync-report.md
docs/glyph-leave-one-out-report.md
docs/name-cluster-report.md
docs/payable-segmentation-diagnosis.md
scripts/diagnose_payable.py
specs/native-checkout-contract-proposal.md
src/image_extraction_adapter/README.md
src/image_extraction_adapter/__init__.py
src/image_extraction_adapter/adapter.py
src/image_extraction_adapter/glyph_classifier.py
src/image_extraction_adapter/model.py
src/image_extraction_adapter/ocr.py
src/image_extraction_adapter/parser.py
src/image_extraction_adapter/preprocessing.py
src/image_extraction_adapter/tests/__init__.py
src/image_extraction_adapter/tests/fixtures/synthetic_invoice.png
src/image_extraction_adapter/tests/fixtures/synthetic_invoice.svg
src/image_extraction_adapter/tests/fixtures/synthetic_invoice_fa.png
src/image_extraction_adapter/tests/test_adapter.py
src/image_extraction_adapter/tests/test_layout_safe.py
src/image_extraction_adapter/tests/test_numeric_authority.py
src/image_extraction_adapter/tests/test_preprocessing.py
src/labels_build.json
src/labels_eval.json
src/run_dynamic_layout_benchmark.py
src/run_glyph_leave_one_out.py
src/run_image_preprocessing_benchmark.py
src/run_name_cluster_experiment.py
src/run_smoke_all.py
src/run_smoke_image_extraction.py
src/templates.json
src/test_run_smoke_all.py
tests/fixtures/real/29.png
tests/fixtures/real/31.png
tests/fixtures/real/32.png
tests/fixtures/real/33.png
tests/fixtures/real/labels.json
tests/test_layout_real.py
```

## 7. PNG inventory

The Pillow script recursively scanned the three requested directories. Modification times are the current workspace filesystem mtimes in Tehran and UTC; they cluster at checkout/reset time and are **not** reliable original upload timestamps. Git author dates are recorded in Section 12.

| Directory | Filename | Bytes | MD5 | Dimensions | Mtime (Tehran) | Mtime (UTC) |
|---|---|---:|---|---|---|---|
| `tests/fixtures/real` | `29.png` | 24,659 | `026902604f40b33a43c63948f42b6fd7` | 576×1296 | 2026-10-17 06:37:22.026922 +03:30 | 2026-10-17 03:07:22.026922 +00:00 |
| `tests/fixtures/real` | `31.png` | 46,209 | `8a4a9593d6de6bd32a0f2c77c9b5ad0f` | 576×1224 | 2026-10-17 06:37:22.026922 +03:30 | 2026-10-17 03:07:22.026922 +00:00 |
| `tests/fixtures/real` | `32.png` | 51,303 | `0ffd7a5e417aca8eb7f6c6ba16d5b1da` | 576×1368 | 2026-10-17 06:37:22.026922 +03:30 | 2026-10-17 03:07:22.026922 +00:00 |
| `tests/fixtures/real` | `33.png` | 68,437 | `d38d8cde2f7b4920250f0fc692861f48` | 576×1680 | 2026-10-17 06:37:22.026922 +03:30 | 2026-10-17 03:07:22.026922 +00:00 |
| `deliveries/image-extraction-ocr` | `13.png` | 68,437 | `d38d8cde2f7b4920250f0fc692861f48` | 576×1680 | 2026-10-17 06:37:21.998922 +03:30 | 2026-10-17 03:07:21.998922 +00:00 |
| `deliveries/image-extraction-ocr` | `31.png` | 46,209 | `8a4a9593d6de6bd32a0f2c77c9b5ad0f` | 576×1224 | 2026-10-17 06:37:21.998922 +03:30 | 2026-10-17 03:07:21.998922 +00:00 |
| `deliveries/image-extraction-ocr` | `5.png` | 51,303 | `0ffd7a5e417aca8eb7f6c6ba16d5b1da` | 576×1368 | 2026-10-17 06:37:21.998922 +03:30 | 2026-10-17 03:07:21.998922 +00:00 |
| `deliveries/image-extraction-ocr` | `glyph-classifier-build-13-rows03-08.png` | 6,816 | `e0f1ee35d7b8fae98ce6c0abb4b8b101` | 576×439 | 2026-10-17 06:37:21.998922 +03:30 | 2026-10-17 03:07:21.998922 +00:00 |
| `deliveries/image-extraction-ocr` | `holo_row_detection.png` | 24,659 | `026902604f40b33a43c63948f42b6fd7` | 576×1296 | 2026-10-17 06:37:21.998922 +03:30 | 2026-10-17 03:07:21.998922 +00:00 |

`deliveries/issue-4-smoke-suite/` exists and contains zero `.png` files. The ZIP file in that directory was not unpacked; the inventory covers PNGs in the requested directory tree.

## 8. Exact-content groups

Matching MD5 values establish byte-identical file contents:

| MD5 | Dimensions | Files |
|---|---|---|
| `026902604f40b33a43c63948f42b6fd7` | 576×1296 | `tests/fixtures/real/29.png`; `deliveries/image-extraction-ocr/holo_row_detection.png` |
| `0ffd7a5e417aca8eb7f6c6ba16d5b1da` | 576×1368 | `tests/fixtures/real/32.png`; `deliveries/image-extraction-ocr/5.png` |
| `8a4a9593d6de6bd32a0f2c77c9b5ad0f` | 576×1224 | `tests/fixtures/real/31.png`; `deliveries/image-extraction-ocr/31.png` |
| `d38d8cde2f7b4920250f0fc692861f48` | 576×1680 | `tests/fixtures/real/33.png`; `deliveries/image-extraction-ocr/13.png` |
| `e0f1ee35d7b8fae98ce6c0abb4b8b101` | 576×439 | `deliveries/image-extraction-ocr/glyph-classifier-build-13-rows03-08.png` only; no exact fixture match |

## 9. Critical invoice #32 verification

**Does `tests/fixtures/real/32.png` exist? YES.** It is 51,303 bytes, 576×1368, MD5 `0ffd7a5e417aca8eb7f6c6ba16d5b1da`.

**Is it byte-identical to `deliveries/image-extraction-ocr/5.png`? YES.** Size, dimensions, and MD5 all match. `labels.json` maps the fixture to invoice ID 32 and payable `۷,۸۵۰,۰۰۰` (7,850,000).

The fixture path was added in `55d6c609cda84aaaf1afa911f5a5b67da790921b`; the delivery path `5.png` was added earlier in `ccb9e99dbc7d0bfd482ab8ee28f89c3a724a6052`. Git recorded the fixture as a new path, not a rename. The matching MD5 proves byte identity, although Git does not record the manual copy/renaming operation.

## 10. Other image findings

- `deliveries/image-extraction-ocr/5.png` does **not** match fixture `33.png` (MD5 `0ffd7a5e417aca8eb7f6c6ba16d5b1da` vs `d38d8cde2f7b4920250f0fc692861f48`).
- `deliveries/image-extraction-ocr/13.png` matches fixture `33.png` exactly. Thus its numeric filename differs from the invoice ID inferred from fixture content.
- Fixture `31.png` matches delivery `31.png`; fixture `29.png` matches delivery `holo_row_detection.png`.
- The diagnostic `glyph-classifier-build-13-rows03-08.png` is unique in the scanned paths. Its invoice ID is unknown without OCR, which this task intentionally did not use.
- All four fixture PNGs are labeled. There are no PNGs in `deliveries/issue-4-smoke-suite/`.

## 11. Label and dimension consistency

`tests/fixtures/real/labels.json` has `label_status: OPERATOR_CONFIRMED`. It contains the following ID/path/payable entries:

| Invoice ID | Path | Payable | Integrity result |
|---|---|---|---|
| 29 | `29.png` | `۷,۴۶۰,۰۰۰` | exists; ID and 576×1296 dimensions match |
| 31 | `31.png` | `۲,۴۲۵,۰۰۰` | exists; ID and 576×1224 dimensions match; payable marked `DERIVED_FROM_ARITHMETIC` |
| 32 | `32.png` | `۷,۸۵۰,۰۰۰` | exists; ID and 576×1368 dimensions match |
| 33 | `33.png` | `۳۴۷,۹۲۰,۰۰۰` | exists; ID and 576×1680 dimensions match |

Every label path exists, each filename stem matches its invoice ID, every declared dimension matches Pillow's decoded dimensions, and all four fixture PNGs have a label. There are no missing or extra fixture PNGs. The #31 payable caveat does not affect image/path integrity.

## 12. Image provenance and Git history

Git history shows the following path additions (timestamps are commit author dates; the repository does not encode upload/copy operations beyond commits):

| Image/path group | Commit | Author date | Author | Subject |
|---|---|---|---|---|
| First tracked files in `deliveries/image-extraction-ocr/` | `931d14111dace044681b3d902b791fa8539066c8` | 2026-10-14 21:00:26 UTC | majid-ghanbari-dost | `feat: add synthetic image OCR adapter and EOD handoff` |
| `holo_row_detection.png` | `3fa1a7f0644342f810f1ae50f064f6b55c9b1869` | 2026-10-15 13:03:55 +03:30 | Majid Ghanbari Dost | `Add files via upload` |
| `glyph-classifier-build-13-rows03-08.png` | `e5ff46defff0f1c92ba7759979526215e9ae9c14` | 2026-10-16 01:13:57 UTC | majid-ghanbari-dost | `Add dynamic Holoo table layout detection` |
| Delivery `5.png` and `13.png` | `ccb9e99dbc7d0bfd482ab8ee28f89c3a724a6052` | 2026-10-16 04:21:57 +03:30 | Majid Ghanbari Dost | `Add files via upload` |
| Delivery `31.png` | `fa951719e25e56d7522b65aa20d116c34bed061f` | 2026-10-16 18:08:31 +03:30 | Majid Ghanbari Dost | `Add files via upload` |
| Fixture `29.png`, `31.png`, `32.png`, `33.png`, and `labels.json` | `55d6c609cda84aaaf1afa911f5a5b67da790921b` | 2026-10-16 18:55:00 UTC | majid-ghanbari-dost | `Add Glyph leave-one-out evaluation artifacts` |

Standard Git rename/copy history queries found no rename/copy status records for these paths. The same-content cross-path relationships in Section 8 are established by MD5 and size/dimensions, not by a Git rename event. The delivery folder's earliest tracked content dates to `931d141`; the real fixture set first appears together in `55d6c60`.

## 13. B2-1 diagnosis validity

**B2-1 is valid with respect to invoice-image identity.** Fixture `32.png` is byte-identical to the owner's delivery file `5.png`; the operator-confirmed label maps it to invoice #32 and payable `۷,۸۵۰,۰۰۰`. The filename discrepancy is an alias in the fixture/delivery paths, not evidence that B2-1 analyzed a different image. B2-1 does **not** need to be repeated solely because the fixture filename is `32.png`.

This finding verifies image identity. It does not add a live Tesseract runtime bounding-box measurement beyond the diagnostic scope documented in B2-1.

## 14. Required unittest run

Command:

```sh
PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python -m unittest discover -s src -p 'test_*.py' -v
```

Exact result: **Ran 44 tests in 1.275s — OK** (process exit code 0). All 44 passed. Pillow 13 emitted two existing `Image.Image.getdata` deprecation warnings from `src/image_extraction_adapter/preprocessing.py:614` and `src/image_extraction_adapter/tests/test_preprocessing.py:151`; they did not fail tests and were not addressed in this scope.

Full verbose output (stderr):

```text
test_adapter_spatial_fallback_holds_and_never_submits (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_adapter_spatial_fallback_holds_and_never_submits) ... ok
test_ambiguous_parse_is_review_not_success (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_ambiguous_parse_is_review_not_success) ... ok
test_cell_variants_are_supplementary_and_do_not_replace_review_fields (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_cell_variants_are_supplementary_and_do_not_replace_review_fields) ... ok
test_geometry_parser_groups_right_to_left_cells_and_preserves_uncertain_raw (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_geometry_parser_groups_right_to_left_cells_and_preserves_uncertain_raw) ... ok
test_high_confidence_image_calls_existing_submit_with_key_value_page (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_high_confidence_image_calls_existing_submit_with_key_value_page) ... ok
test_high_confidence_persian_ocr_submits_utf8_fields (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_high_confidence_persian_ocr_submits_utf8_fields) ... ok
test_invalid_confidence_values_are_review_not_success (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_invalid_confidence_values_are_review_not_success) ... ok
test_low_confidence_is_review_hold_and_never_submits (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_low_confidence_is_review_hold_and_never_submits) ... ok
test_matching_primary_numeric_evidence_is_carried_into_ready_result (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_matching_primary_numeric_evidence_is_carried_into_ready_result) ... ok
test_missing_word_confidences_are_review_not_success (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_missing_word_confidences_are_review_not_success) ... ok
test_parser_maps_labeled_table_without_coordinates (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_parser_maps_labeled_table_without_coordinates) ... ok
test_persian_parser_normalizes_digits_and_bidi_controls_to_utf8 (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_persian_parser_normalizes_digits_and_bidi_controls_to_utf8) ... ok
test_primary_numeric_disagreement_with_transcript_holds_page (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_primary_numeric_disagreement_with_transcript_holds_page) ... ok
test_primary_numeric_review_holds_page_and_never_calls_submit (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_primary_numeric_review_holds_page_and_never_calls_submit) ... ok
test_submit_extraction_cannot_bypass_required_numeric_evidence (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_submit_extraction_cannot_bypass_required_numeric_evidence) ... ok
test_submit_extraction_rejects_low_confidence_ready_result (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_submit_extraction_rejects_low_confidence_ready_result) ... ok
test_tesseract_tsv_reader_retains_word_boxes_and_whitespace_rules (image_extraction_adapter.tests.test_adapter.ImageExtractionAdapterTests.test_tesseract_tsv_reader_retains_word_boxes_and_whitespace_rules) ... ok
test_all_real_invoices_return_ok_with_labeled_row_counts (image_extraction_adapter.tests.test_layout_safe.DetectLayoutSafeTests.test_all_real_invoices_return_ok_with_labeled_row_counts) ... ok
test_blank_image_is_classified_without_raising (image_extraction_adapter.tests.test_layout_safe.DetectLayoutSafeTests.test_blank_image_is_classified_without_raising) ... ok
test_detector_exception_from_corrupt_image_is_blocked (image_extraction_adapter.tests.test_layout_safe.DetectLayoutSafeTests.test_detector_exception_from_corrupt_image_is_blocked) ... ok
test_incomplete_geometry_is_review_and_preserved (image_extraction_adapter.tests.test_layout_safe.DetectLayoutSafeTests.test_incomplete_geometry_is_review_and_preserved) ... ok
test_partial_geometry_touching_edge_is_blocked_as_truncated (image_extraction_adapter.tests.test_layout_safe.DetectLayoutSafeTests.test_partial_geometry_touching_edge_is_blocked_as_truncated) ... ok
test_text_only_image_is_review_or_blocked (image_extraction_adapter.tests.test_layout_safe.DetectLayoutSafeTests.test_text_only_image_is_review_or_blocked) ... ok
test_tiny_truncated_image_is_blocked (image_extraction_adapter.tests.test_layout_safe.DetectLayoutSafeTests.test_tiny_truncated_image_is_blocked) ... ok
test_unreasonable_row_count_is_review (image_extraction_adapter.tests.test_layout_safe.DetectLayoutSafeTests.test_unreasonable_row_count_is_review) ... ok
test_zero_rows_are_review_and_preserved (image_extraction_adapter.tests.test_layout_safe.DetectLayoutSafeTests.test_zero_rows_are_review_and_preserved) ... ok
test_default_flag_value_is_tesseract_parse (image_extraction_adapter.tests.test_numeric_authority.NumericAuthorityTests.test_default_flag_value_is_tesseract_parse) ... ok
test_glyph_mode_agreement_with_tesseract_is_extracted (image_extraction_adapter.tests.test_numeric_authority.NumericAuthorityTests.test_glyph_mode_agreement_with_tesseract_is_extracted) ... ok
test_glyph_mode_disagreement_with_tesseract_is_review (image_extraction_adapter.tests.test_numeric_authority.NumericAuthorityTests.test_glyph_mode_disagreement_with_tesseract_is_review) ... ok
test_glyph_mode_glyph_blocked_stays_blocked (image_extraction_adapter.tests.test_numeric_authority.NumericAuthorityTests.test_glyph_mode_glyph_blocked_stays_blocked) ... ok
test_glyph_mode_glyph_review_stays_review (image_extraction_adapter.tests.test_numeric_authority.NumericAuthorityTests.test_glyph_mode_glyph_review_stays_review) ... ok
test_glyph_mode_tesseract_missing_is_extracted (image_extraction_adapter.tests.test_numeric_authority.NumericAuthorityTests.test_glyph_mode_tesseract_missing_is_extracted) ... ok
test_tesseract_parse_mode_preserves_existing_behavior (image_extraction_adapter.tests.test_numeric_authority.NumericAuthorityTests.test_tesseract_parse_mode_preserves_existing_behavior) ... ok
test_to_rials_converts_persian_digits_and_commas (image_extraction_adapter.tests.test_numeric_authority.NumericAuthorityTests.test_to_rials_converts_persian_digits_and_commas) ... ok
test_to_rials_handles_invalid_input (image_extraction_adapter.tests.test_numeric_authority.NumericAuthorityTests.test_to_rials_handles_invalid_input) ... ok
test_to_rials_handles_none_and_empty (image_extraction_adapter.tests.test_numeric_authority.NumericAuthorityTests.test_to_rials_handles_none_and_empty) ... ok
test_all_modes_return_copies_and_keep_dimensions (image_extraction_adapter.tests.test_preprocessing.CellPreprocessingTests.test_all_modes_return_copies_and_keep_dimensions) ... /home/user/Kandoo-Digital-Invoice/src/image_extraction_adapter/preprocessing.py:614: DeprecationWarning: Image.Image.getdata is deprecated and will be removed in Pillow 14 (2027-10-15). Use get_flattened_data instead.
  removed_pixels = sum(1 for value in line_mask.getdata() if value > 0)
/home/user/Kandoo-Digital-Invoice/src/image_extraction_adapter/tests/test_preprocessing.py:151: DeprecationWarning: Image.Image.getdata is deprecated and will be removed in Pillow 14 (2027-10-15). Use get_flattened_data instead.
  self.assertEqual(list(source.getdata()), list(original.getdata()))
ok
test_crop_uses_projection_before_spatial_fallback (image_extraction_adapter.tests.test_preprocessing.CellPreprocessingTests.test_crop_uses_projection_before_spatial_fallback) ... ok
test_morphological_opening_removes_long_rules_not_small_glyph (image_extraction_adapter.tests.test_preprocessing.CellPreprocessingTests.test_morphological_opening_removes_long_rules_not_small_glyph) ... ok
test_numeric_review_rejects_pipe_bang_and_unrestricted_disagreement (image_extraction_adapter.tests.test_preprocessing.CellPreprocessingTests.test_numeric_review_rejects_pipe_bang_and_unrestricted_disagreement) ... ok
test_otsu_threshold_zero_keeps_black_foreground (image_extraction_adapter.tests.test_preprocessing.CellPreprocessingTests.test_otsu_threshold_zero_keeps_black_foreground) ... ok
test_projection_detects_four_five_and_thirteen_rows_without_fixed_coords (image_extraction_adapter.tests.test_preprocessing.CellPreprocessingTests.test_projection_detects_four_five_and_thirteen_rows_without_fixed_coords) ... ok
test_real_holoo_images_have_dynamic_row_and_column_geometry (image_extraction_adapter.tests.test_preprocessing.CellPreprocessingTests.test_real_holoo_images_have_dynamic_row_and_column_geometry) ... ok
test_spatial_crop_uses_rtl_columns_and_preserves_source (image_extraction_adapter.tests.test_preprocessing.CellPreprocessingTests.test_spatial_crop_uses_rtl_columns_and_preserves_source) ... ok

----------------------------------------------------------------------
Ran 44 tests in 1.275s

OK
```

## 15. Integrity script validation and output

The environment `/tmp/kandoo-t2-venv` was absent initially, so it was recreated and Pillow 13.0.0 installed. Syntax validation command:

```sh
PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python -m py_compile scripts/verify_image_integrity.py
```

Result: exit 0 (`py_compile: exit 0`). Inventory command:

```sh
PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python scripts/verify_image_integrity.py
```

The script's exact stdout:

```text
Image integrity inventory (PNG bytes; no OCR)
Repository root: /home/user/Kandoo-Digital-Invoice
Labels: tests/fixtures/real/labels.json
Directories scanned:
  tests/fixtures/real: present; PNG files=4
  deliveries/image-extraction-ocr: present; PNG files=5
  deliveries/issue-4-smoke-suite: present; PNG files=0

File inventory
directory | filename | bytes | MD5 | dimensions | mtime (Tehran) | mtime (UTC)
tests/fixtures/real | 29.png | 24659 | 026902604f40b33a43c63948f42b6fd7 | 576x1296 | 2026-10-17T06:37:22.026922+03:30 | 2026-10-17T03:07:22.026922+00:00
tests/fixtures/real | 31.png | 46209 | 8a4a9593d6de6bd32a0f2c77c9b5ad0f | 576x1224 | 2026-10-17T06:37:22.026922+03:30 | 2026-10-17T03:07:22.026922+00:00
tests/fixtures/real | 32.png | 51303 | 0ffd7a5e417aca8eb7f6c6ba16d5b1da | 576x1368 | 2026-10-17T06:37:22.026922+03:30 | 2026-10-17T03:07:22.026922+00:00
tests/fixtures/real | 33.png | 68437 | d38d8cde2f7b4920250f0fc692861f48 | 576x1680 | 2026-10-17T06:37:22.026922+03:30 | 2026-10-17T03:07:22.026922+00:00
deliveries/image-extraction-ocr | 13.png | 68437 | d38d8cde2f7b4920250f0fc692861f48 | 576x1680 | 2026-10-17T06:37:21.998922+03:30 | 2026-10-17T03:07:21.998922+00:00
deliveries/image-extraction-ocr | 31.png | 46209 | 8a4a9593d6de6bd32a0f2c77c9b5ad0f | 576x1224 | 2026-10-17T06:37:21.998922+03:30 | 2026-10-17T03:07:21.998922+00:00
deliveries/image-extraction-ocr | 5.png | 51303 | 0ffd7a5e417aca8eb7f6c6ba16d5b1da | 576x1368 | 2026-10-17T06:37:21.998922+03:30 | 2026-10-17T03:07:21.998922+00:00
deliveries/image-extraction-ocr | glyph-classifier-build-13-rows03-08.png | 6816 | e0f1ee35d7b8fae98ce6c0abb4b8b101 | 576x439 | 2026-10-17T06:37:21.998922+03:30 | 2026-10-17T03:07:21.998922+00:00
deliveries/image-extraction-ocr | holo_row_detection.png | 24659 | 026902604f40b33a43c63948f42b6fd7 | 576x1296 | 2026-10-17T06:37:21.998922+03:30 | 2026-10-17T03:07:21.998922+00:00

Groups by exact MD5 (same bytes => same file content)
  MD5 026902604f40b33a43c63948f42b6fd7; dimensions=576x1296
    (tests/fixtures/real, 29.png)
    (deliveries/image-extraction-ocr, holo_row_detection.png)
  MD5 0ffd7a5e417aca8eb7f6c6ba16d5b1da; dimensions=576x1368
    (tests/fixtures/real, 32.png)
    (deliveries/image-extraction-ocr, 5.png)
  MD5 8a4a9593d6de6bd32a0f2c77c9b5ad0f; dimensions=576x1224
    (tests/fixtures/real, 31.png)
    (deliveries/image-extraction-ocr, 31.png)
  MD5 d38d8cde2f7b4920250f0fc692861f48; dimensions=576x1680
    (tests/fixtures/real, 33.png)
    (deliveries/image-extraction-ocr, 13.png)
  MD5 e0f1ee35d7b8fae98ce6c0abb4b8b101; dimensions=576x439
    (deliveries/image-extraction-ocr, glyph-classifier-build-13-rows03-08.png)

Labels cross-reference
  label status: OPERATOR_CONFIRMED
  invoice 29: 29.png; exists=YES; filename-id=MATCH; dimensions declared=[576, 1296], actual=576x1296; dimensions=MATCH; OK
  invoice 31: 31.png; exists=YES; filename-id=MATCH; dimensions declared=[576, 1224], actual=576x1224; dimensions=MATCH; OK
  invoice 32: 32.png; exists=YES; filename-id=MATCH; dimensions declared=[576, 1368], actual=576x1368; dimensions=MATCH; OK
  invoice 33: 33.png; exists=YES; filename-id=MATCH; dimensions declared=[576, 1680], actual=576x1680; dimensions=MATCH; OK

Delivery filename/content cross-reference
  deliveries/image-extraction-ocr/13.png: exact fixture content for invoice(s) 33; filename-id=MISMATCH
  deliveries/image-extraction-ocr/31.png: exact fixture content for invoice(s) 31; filename-id=MATCH
  deliveries/image-extraction-ocr/5.png: exact fixture content for invoice(s) 32; filename-id=MISMATCH
  deliveries/image-extraction-ocr/glyph-classifier-build-13-rows03-08.png: no exact fixture-content match; invoice id unknown without OCR
  deliveries/image-extraction-ocr/holo_row_detection.png: exact fixture content for invoice(s) 29; filename-id=non-numeric filename

Critical filename/hash checks
  tests/fixtures/real/32.png exists: YES
  tests/fixtures/real/32.png == deliveries/image-extraction-ocr/5.png: YES
  tests/fixtures/real/32.png MD5: 0ffd7a5e417aca8eb7f6c6ba16d5b1da
  deliveries/image-extraction-ocr/5.png MD5: 0ffd7a5e417aca8eb7f6c6ba16d5b1da
  deliveries/image-extraction-ocr/5.png == tests/fixtures/real/33.png: NO
  deliveries/image-extraction-ocr/13.png == any fixture: YES (33.png)

Labels consistency summary
  PASS: all 4 label paths exist, filename IDs and declared dimensions match, and all 4 fixture PNGs are labeled
  Note: a hash match proves byte identity, not provenance or original upload time.
```

## 16. Concerns and PM recommendations

- Workspace mtimes reflect checkout/reset, not source upload dates. Use Git addition history above for provenance.
- Delivery filename aliases are confirmed by hash: `5.png → invoice #32`; `13.png → invoice #33`. Keep the files unchanged and document this mapping in a manifest/delivery note to prevent confusion.
- The diagnostic glyph-classifier image is unmatched to an exact fixture; do not infer its invoice ID without separate evidence/OCR.
- The preserved WIP stash contains prior-task source, evidence, and experiment artifacts; retain until the owner decides whether to restore or discard it.
- The new inventory script/report are safe to review on this feature branch; they do not alter production behavior.
- Do not touch `adapter.py`, `preprocessing.py`, `glyph_classifier.py`, frozen contracts/defaults, or the B2-5 wrapper in this task. B2-2 remains out of scope pending PM direction.
- Keep the B2-1 diagnosis. Its image identity is confirmed; a repeat solely due to the `32.png`/`5.png` naming difference is unnecessary.

## 17. Stabilization commit and post-push verification

At report-writing time, the only untracked stabilization files were `scripts/verify_image_integrity.py` and this report; generated `__pycache__` directories from test/compile runs were removed. The required unittest run and inventory run both passed. The tag is already pushed at the B2-1 baseline.

The script and report are to be committed together with the requested message:

```text
docs(stabilize): freeze state + verify image integrity (critical 32.png check)
```

Post-commit, the branch is to be pushed without force and fetched/verified so local HEAD equals `origin/arena/9dc17500-kandoo-digital-invoice`. The resulting stabilization commit SHA, exact push/fetch output, final `git log --oneline -10`, and final tag list are recorded in the task completion response. The new commit SHA is intentionally not embedded in this file because that would make its content self-referential.
