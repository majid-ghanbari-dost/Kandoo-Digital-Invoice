# PROJECT_STATE — T0 Baseline Snapshot

Baseline date: **2026-10-16** (Asia/Tehran)

> **Snapshot caveat:** The task supplied base `bea9e56`, but this checkout is actually at `1b79e630a8f476ed13d2d9fa7b6fb1c3de391cd0`; the `bea9e56` object is not present locally. Several implementation files described below exist only as untracked working-tree files and are absent from HEAD. Therefore this records the actual current worktree, not a verified checkout of the supplied base.

## 1. Repository State

### Git snapshot

Commands and outputs captured at the start of T0:

```text
$ git branch --show-current
arena/9dc17500-kandoo-digital-invoice

$ git rev-parse HEAD
1b79e630a8f476ed13d2d9fa7b6fb1c3de391cd0

$ git log --oneline -5
1b79e63 delivery(record): publication record — PR #10, remote head, Issue-report 403 status
```

Only one commit is available in the local branch history (`grafted`/shallow checkout). The task-provided `bea9e56` commit is not in the local object database. The task's requested branch name matches the active branch, but its stated base does not match the actual HEAD.

`git diff -- src` is empty. This is a literal tracked-diff result only: `src/image_extraction_adapter/`, the smoke runners, labels and templates are **untracked** in this working tree and therefore do not appear in `git diff`. `AGENT_HANDOFF.md` is modified and several other prior-task artifacts are untracked. T0 did not edit source code or tests and does not stage those pre-existing files.

There is no root `tests/` directory and no `pyproject.toml`, `pytest.ini`, `setup.cfg`, or `tox.ini` was found within the checked depth. Test modules are under `src/**/tests/`.

### Existing Fixtures

`tests/fixtures/` at the repository root is **absent**. The existing fixture directory in the working tree contains:

| Path | Type / status |
|---|---|
| `src/image_extraction_adapter/tests/fixtures/synthetic_invoice.png` | Synthetic English raster fixture; untracked with the adapter tree |
| `src/image_extraction_adapter/tests/fixtures/synthetic_invoice.svg` | Synthetic English vector fixture; untracked with the adapter tree |
| `src/image_extraction_adapter/tests/fixtures/synthetic_invoice_fa.png` | Synthetic Persian raster fixture; untracked with the adapter tree |

Other image/data files present in the working tree:

| Path | Description / status |
|---|---|
| `deliveries/image-extraction-ocr/5.png` | Supplied non-synthetic five-row receipt image; untracked |
| `deliveries/image-extraction-ocr/13.png` | Supplied non-synthetic thirteen-row receipt image; untracked |
| `deliveries/image-extraction-ocr/holo_row_detection.png` | Supplied non-synthetic four-row receipt image; untracked |
| `deliveries/image-extraction-ocr/glyph-classifier-build-13-rows03-08.png` | Derived training crop from rows 3–8 of `13.png`; not an independent receipt |
| `deliveries/image-extraction-ocr/glyph-classifier-build-rows-0-1.png` | Derived Glyph build/crop artifact; not identified as an independent original receipt |
| `src/labels_build.json` | Provisional visual-transcription labels; not owner-confirmed |
| `src/labels_eval.json` | Provisional evaluation labels; row holdout is within the same 13-row invoice |
| `src/templates.json` | Glyph template data |
| `deliveries/image-extraction-ocr/glyph-classifier-wp06-labels-build.json` | Older WP-06 label artifact; untracked |
| `deliveries/image-extraction-ocr/glyph-classifier-wp06-labels-eval.json` | Older WP-06 label artifact; untracked |
| `deliveries/image-extraction-ocr/glyph-classifier-wp06-templates.json` | Older WP-06 template artifact; untracked |

No image files are tracked in the current HEAD (`git ls-files` returned no image paths). Thus the three supplied receipt images are present in the worktree, but **no real Holo receipt image is committed at this HEAD**. No existing filename matched receipt numbers **29, 31, 32, or 33**. Labels are explicitly provisional and are not invoice-owner-confirmed ground truth.

## 2. Architecture Summary

- Repository boundary: **Kandoo** is the parent product/repository containing the Windows App. **Kandoo-Digital-Invoice** is the Python development line for capture, extraction, canonicalization and Digital Invoice work. The parent-app UI is not implemented by this Python image-extraction adapter.
- Intended/current working-tree extraction path: Print Spooler capture → dynamic table finding by image projection (no fixed page coordinates; TSV geometry is fallback) → Glyph numeric-cell template classifier for the thermal receipt font → arithmetic gate → page-level `REVIEW` on uncertain or inconsistent output, otherwise continue to the existing parse/issuance flow. `DONE` is not a new state in the frozen lifecycle; successful extraction returns the existing adapter-ready result.
- Local Tesseract is used for full-page raw text and spatial/layout evidence. Glyph reads numeric crops. The intended policy is offline-only: no VLM, cloud OCR, or cloud APIs. No network request or invoice extraction was run for T0.
- The user-described **Shadow Store** is a proposed local product/reference database built from extracted raw product text, with no customer data. No Shadow Store implementation was found in the checked source/spec set.
- **Zero-Tension** is a proposed automatic calibration loop using clustering plus the math gate. No such calibration workflow was found implemented in the checked source/spec set.
- The customer-number popup belongs to the parent Windows App and is not printed on the Holoo invoice; it is not an OCR field in this Python module.

## 3. Key Decisions

- **Offline-only extraction:** do not use internet, VLMs, cloud OCR, or cloud APIs for extraction.
- **Glyph as numeric authority:** intended policy is that Glyph supplies numeric values; Tesseract is supporting evidence, not numeric authority.
- **Fail closed:** uncertain or malformed output stays `REVIEW`; no number is guessed, repaired, or silently corrected.
- **Tesseract policy:** intended policy says Tesseract is an evidence source, not authority and not a veto. The current working-tree adapter contradicts the “not a veto” part: `_numeric_evidence_problem` compares Glyph output against parsed full-page OCR fields and can force page-level REVIEW on disagreement (details in Sections 4 and 7). This is a known implementation risk, not a decision silently resolved by T0.
- **Native Checkout decisions** recorded in the working-tree proposal: Q1=Option 1, Q2=Option 2, Q3=Option 1, Q4=Option 1. These are future-architecture decisions, not current implementation priority.

### D3 — Holo DB Access: CLOSED

هلو همکاری و دسترسی به داده ندارد و وب‌سرویسش برای
فروشگاه‌ها پرهزینه است؛ مسیر چاپ محصول است. تلفن و نام
واقعی مشتری از چاپ نمی‌آید و باید از اپراتور گرفته شود.

Decision: CLOSED on 2026-10-17.
This decision is final and will not be revisited.

## 4. Glyph Classifier State

### Availability and handoff components

`src/image_extraction_adapter/glyph_classifier.py` is **absent from HEAD** and is an untracked 938-line working-tree file. There is no tracked “handoff version” to diff against at the actual HEAD; the comparison below uses the three handoff components stated in T0 and examines the working-tree copy. The adapter and tests are also absent from HEAD.

The three requested components are present in that working-tree file:

1. **Arithmetic gate:** `evaluate_arithmetic_gate()` and `apply_arithmetic_gate()` compare the sum of contiguous line totals plus a caller-supplied `extra_amounts` value to payable; failures downgrade amount cells to REVIEW. Lines 571–650.
2. **Templates / matching:** `GlyphTemplate`, `GlyphTemplateSet`, the classifier and template builder implement labeled glyph template matching. Lines 282–365, 422–554.
3. **Evaluate CLI:** `build` and `evaluate` subcommands are registered at lines 913–934; evaluation is implemented at lines 839–910.

### Extra features beyond those three high-level components

| Extra feature | Location | Description | Changes default behavior? |
|---|---|---|---|
| Connected-component segmentation and normalized features | Lines 116–275 | Labels/merges connected components, filters rule remnants, computes line-relative geometry and a 10×14 bitmap grid before matching. | Yes; used by normal build/read paths. |
| Otsu and table-rule preprocessing | Lines 508–511; called at 541 and 684 | Uses `preprocess_cell(cell_image, "otsu")` before template creation and runtime recognition; reports removed line pixels. | Yes; the normal Glyph path uses it. |
| Per-glyph rejection and uncertainty output | Lines 422–505 and 674–713 | Default distance/margin/width limits, crop-edge checks, minimum confidence and numeric-format checks; rejected glyphs are emitted as `?`, never repaired. | Yes; defaults are max distance 0.25, minimum margin 0.15 and max width ratio 1.0. The evaluate CLI defaults minimum confidence to 60; the runtime spatial-recognition API requires its caller to pass a confidence threshold. |
| Payable-profile fallback | Lines 400–407 and 657–668 | `payable_uses_row_templates=True` lets payable recognition use row-profile templates after payable-profile templates. | Yes; enabled by default. |
| Spatial-cell backend / projection-based crops | Lines 657–755; CLI geometry helper at 774–797 | Exposes `recognize_spatial_cells()` and calls `crop_spatial_cells()` for numeric cells; the imported cropper prefers image projection and uses OCR geometry as fallback. | Yes when this backend is called; arithmetic gate is enabled by default via `apply_gate=True`. |
| Full-page REVIEW propagation into Glyph | Lines 105–106 and 677–699 | If the source spatial assessment for a cell is REVIEW, Glyph also makes that cell REVIEW (`SOURCE_REVIEW_REASON`). | Yes; always applied by the normal recognition path. This is a separate Tesseract/spatial veto. |
| Strict gate validation and optional known extras | Lines 571–650 and 715–755 | Gate rejects missing payable/totals, non-contiguous rows and malformed amounts; `extra_amounts` supports known VAT/levies, defaults to zero, and the gate only downgrades. | Yes; gate is on by default. `extra_amounts=0` is only appropriate when there are no omitted VAT/levy amounts. |
| Template format/provenance and build-time safeguards | Lines 289–365, 525–554 and 814–838 | Version/grid/alphabet validation, duplicate-template suppression, JSON provenance, image SHA-256 recording, invalid-label/segmentation skips and missing-row-symbol warnings. | Build/load behavior; does not independently change runtime values, but affects which templates are available. |
| Evaluation diagnostics and leakage guard | Lines 839–910 and 923–931 | Reports exact-cell accuracy, digit CER, segmentation mismatches, arithmetic-gate rates, distance/margin spans; compares source hashes to template provenance and exits 3 for detected leakage unless `--allow-leakage` is passed. | Evaluation only; leakage is rejected by default, with explicit opt-in to allow it. |

### Tesseract reference check

The string `adapter._numeric_evidence_problem` is **not referenced by name** in `glyph_classifier.py` (search returned no match). It is defined and called by the working-tree `adapter.py`. The decisive code is:

```python
expected = {
    field: value for field, value in fields
    if field == "invoice.payable" or _NUMERIC_FIELD.fullmatch(field)
}
observed = {item.field_name: item.raw_value for item in variants}
duplicates = len(observed) != len(variants)
missing = sorted(set(expected) - set(observed))
unexpected = sorted(set(observed) - set(expected))
mismatched = []
for field in sorted(set(expected) & set(observed)):
    expected_value = self._numeric_value(expected[field])
    observed_value = self._numeric_value(observed[field])
    if (expected_value is None or observed_value is None
            or expected_value != observed_value):
        mismatched.append(field)
if duplicates or missing or unexpected or mismatched:
    problems = []
    if duplicates:
        problems.append("duplicate numeric OCR field results")
    if missing:
        problems.append("missing numeric OCR fields: " + ", ".join(missing))
    if unexpected:
        problems.append("unexpected numeric OCR fields: " + ", ".join(unexpected))
    if mismatched:
        problems.append("numeric OCR disagrees with parsed values: "
                        + ", ".join(mismatched))
    return "primary numeric OCR coverage/consistency failed: " + "; ".join(problems)
return None
```

The adapter calls that check and converts any returned problem into a page hold:

```python
problem = self._numeric_evidence_problem(fields, variants)
if problem:
    return self._numeric_backend_review(
        digest, ocr, fields, spatial=spatial, variants=variants,
        reason=problem + "; full page held"), variants
```

`fields` come from `parse_invoice_text(ocr.text)` after `self._ocr.recognize(image)` (adapter lines 225–231); the smoke path configures Tesseract as that full-page backend. Thus an otherwise EXTRACTED Glyph value that disagrees with a Tesseract-parsed number is held as REVIEW. This is the known **Tesseract veto** and conflicts with the intended “Tesseract is not a veto” decision. T0 records but does not change this behavior.

## 5. Baseline Test Results

No pytest configuration was found; the root `tests/` directory is absent. The working tree contains 121 `test_*.py` files under `src`, and 90 test files import pytest.

- **Full-suite command attempted:** `python -m pytest -v` — exit code 1, `/usr/bin/python: No module named pytest`. Pytest did not collect tests, so full-suite total/passed/failed/errors/skipped counts are **unavailable**, not zero.
- **Standard-library fallback:** `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s src -p 'test_*.py' -v` — 32 discovered tests: **24 passed, 0 failed, 0 errors, 8 skipped**. The 8 image-preprocessing/layout tests were skipped because Pillow is not installed. This is only the unittest-discoverable subset and is **not** the full pytest suite.
- Pillow, tesserocr and the Tesseract executable are absent from this runtime. No image extraction was run. Complete captured command output is in `docs/baseline-test-output.txt`.

## 6. Task Board Status

| Task | Status | Notes |
|---|---|---|
| T0 | IN PROGRESS | State/log files drafted. Full pytest suite is blocked by missing pytest; actual HEAD also differs from supplied base `bea9e56`. Record and report this environment limitation; no source changes. |
| T1 | BLOCKED | Needs D1=yes. |
| T2 | BLOCKED | Needs U1 (labels) + T1. |
| T3 | BLOCKED | Needs T2 step 1. |
| T4 | BLOCKED | Needs T2 step 1. |

## 7. Known Risks

1. **Tesseract veto in `adapter._numeric_evidence_problem`:** quoted in Section 4. Parsed full-page OCR numeric fields are compared with Glyph numeric fields; any mismatch returns page-level REVIEW even if Glyph marked its cell EXTRACTED. This contradicts the intended policy that Tesseract is evidence only, not veto.
2. **A second spatial veto exists in Glyph:** `glyph_classifier.py` lines 696–699 checks `spatial.assessments` and adds REVIEW when the full-page assessment is REVIEW. This is active by default and can veto a Glyph read independently of `_numeric_evidence_problem`.
3. **Fixtures/receipt commitment:** the fixture directory contains Synthetic English/Persian examples only. Three non-synthetic receipt images are present in the worktree, but they are untracked and none is committed at HEAD. Their visual labels are provisional and not invoice-owner-confirmed. No image filename for #29, #31, #32, or #33 was found.
4. **Limited generalization:** current labels/templates describe the supplied receipt set and one apparent print/font/store configuration; generalization to other stores, printers, fonts and layouts is unknown. The module docstring says default distance/margin calibration came from only a pair of invoices. The 13-row train/evaluation split is by rows from the same invoice, not independent-invoice validation.
5. **Gate configuration:** `extra_amounts` defaults to zero; the gate docstring says this is only correct when VAT/levies are empty. Incorrect extras or an omitted VAT/levy model can cause an unnecessary REVIEW or an unsafe arithmetic comparison.
6. **Evaluation exit status:** `_cmd_evaluate()` returns 0 at lines 907–910 after printing metrics unless template leakage is detected. Poor exact accuracy or a failed arithmetic gate alone does not make the CLI exit nonzero, so automation must inspect the metric lines rather than relying only on process status.
7. **Baseline limitations:** pytest, Pillow, tesserocr and Tesseract are absent. The full suite cannot be established here; fallback tests skipped the image tests. Also, source files are untracked and absent from HEAD, while the prompt supplied a different base SHA. Results describe the working tree, not a reproducible `bea9e56` checkout.
8. **Planned components not present:** no Shadow Store, Zero-Tension clustering/calibration workflow, or parent Windows customer-number popup implementation was found in this Python module/repository subset.

## Layout Detector Robustness (T4)

Test command:

```sh
PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python -m unittest discover -s tests -p 'test_layout_real.py' -v
```

The tests use Pillow and `image_extraction_adapter.preprocessing.detect_dynamic_table_layout`; they do not require Tesseract. The detector is a geometry helper only: it returns `DynamicTableLayout` or `None`, with no `REVIEW`/`Blocked` status field and no payable-box detector. Therefore, `None` means the caller has no projection geometry and must fail closed; partial geometry from a known truncated image must also be held for caller/operator review.

### Real Image Results

All dimensions, column boundaries, and row bands below are detector results. The payable boxes are the reference bboxes from `tests/fixtures/real/labels.json`; the projection detector does not detect or return these bboxes.

| Invoice | Image size | Detected rows | Column boundaries | Detected row bands | Payable bbox (label reference only) |
|---:|---:|---:|---|---|---|
| #29 | 576×1296 | 4 | `[116, 244, 293, 487, 527]` | `[(525,596), (596,664), (664,732), (732,801)]` | `[214,820,116,28]` |
| #31 | 576×1224 | 3 | `[116, 244, 293, 487, 527]` | `[(525,596), (596,664), (664,733)]` | `[214,752,116,28]` |
| #32 | 576×1368 | 5 | `[116, 244, 293, 487, 527]` | `[(525,596), (596,664), (664,732), (732,800), (800,868)]` | `[214,888,116,28]` |
| #33 | 576×1680 | 13 | `[116, 244, 293, 487, 527]` | `[(525,596), (596,664), (664,732), (732,800), (800,868), (868,936), (936,1004), (1004,1071), (1071,1139), (1139,1207), (1207,1275), (1275,1343), (1343,1412)]` | `[199,1431,147,28]` |

All four detected row counts match the expected 4, 3, 5, and 13 rows. All four detected column-boundary tuples match the labeled T2 geometry.

### Negative Image Results

`tests/test_layout_real.py` creates these images under `/tmp` using Pillow. The no-table pattern is deterministic (seed 1405) and has scattered small marks without table rules.

| Input | Size | Detector result | Spurious rows? | Exception? | Status behavior |
|---|---:|---|---|---|---|
| `/tmp/t4-blank.png` | 576×1296 | `None`; 0 rows and no columns | No | No | No state is returned; no geometry requires caller REVIEW/Blocked. |
| `/tmp/t4-no-table.png` | 576×1296 | `None`; 0 rows and no columns | No | No | No state is returned; no geometry requires caller REVIEW/Blocked. |
| `/tmp/t4-truncated.png` | 576×1008 | 7 row bands, 5 columns; last band ends at y=1004; no payable bbox field | No; all seven bands are the first seven real rows of #33 | No | Detector returns partial geometry, not a status. Because this is the known truncated #33 fixture (13 expected rows), caller/operator REVIEW is required. |

The truncated image keeps the top 60% of #33 and removes the bottom 40%. It yields 7 rows rather than 13; the projection API itself cannot tell that the scan is incomplete and does not attach a REVIEW state.

### Payable-Box Edge Exclusion

The payable boxes lie below the final item-row bands and none overlaps a detected `row_band`: the final item-row bottom is y=801/#29, y=733/#31, y=868/#32, and y=1412/#33, while the corresponding payable tops are y=820, 752, 888, and 1431. The payable bbox is not produced by `detect_dynamic_table_layout`; these comparisons use the T2 label reference geometry.

The detector projects long horizontal runs, selects the longest median-spaced horizontal-line chain, optionally excludes the shorter leading header interval, and forms item bands only from consecutive body borders in that chain. Rounded payable-box edges occur below the item table and are separated from its final border by a short irregular gap (about 19–20 px here), unlike the roughly 68 px item-row pitch. They therefore do not join the selected regular table chain. This is a geometric chain/spacing exclusion, not a semantic payable detector or an explicit bbox mask.

### T4 Acceptance Snapshot

- Real row counts and five column boundaries on all four fixtures: **PASS**.
- Negative inputs raise no exceptions and produce no layout for blank/no-table: **PASS**.
- Payable area excluded from all real-image `row_bands`: **PASS**.
- Negative inputs end in an explicit `REVIEW`/`Blocked` status: **FAIL / not provided by this geometry API**. The truncated image returns a seven-row partial layout with no status field; production callers must add/retain a fail-closed completeness decision. No existing source/default behavior was changed in this check.

Test run: 8 tests, all passed. Tesseract was not run.

### Board v4 Sync (E-00)

#### Decisions Confirmed by Owner (D1-D14)
- D1: Two modes. A: Kandoo is the store software.
  B: Kandoo runs beside other software.
- D2: Language-independent Canonical contract.
  Extraction in Python. Platform in C# (ASP.NET Core).
- D3: No Holo database access. Print path is the product.
- D4: Customer delivery: SMS + QR + share button.
  Link carries unguessable token (>= 128 bit).
  Viewing one invoice needs no account.
  Seeing all invoices needs registration with OTP.
  phone_status = claimed | verified.
- D5: Hosting: free or foreign host allowed for MVP only
  if migration takes under one hour.
- D6: One Kandoo app for Windows and Android.
  One account, many memberships.
- D7: One hub per store. Other devices work only on LAN.
  Hub off = other devices cannot start work. No Bluetooth.
  Hub runs without internet, replicates to cloud.
- D8: Backup/restore: cloud full copy + local backup.
  Hub disk is single point of failure (known limitation).
- D9: Products: unique store product id + normalised name.
  Near-duplicate names raise warning.
- D10: Concurrency: inventory is event ledger.
  Price/spec edits carry base version. Conflicts shown to
  operator, never overwritten silently. Issued invoice is
  immutable. Every operation has operation_id (idempotent)
  and device_id.
- D11: Per-phone invoice lock: second device gets hard
  error. Lock ends on issue/cancel/disconnect/timeout.
  Sequential purchases with same number allowed.
- D12: Invoice numbering: internal unique id + sequential
  display number from hub.
- D13: Staged delivery. Multi-device from day one.
- D14: Legal status UNKNOWN. Customer pages say "digital
  receipt, not an official tax document" (wording needs
  owner approval).

#### Known-Answer Onboarding
- E-03 will provide 4 test invoices (3 learning + 1 exam)
  with fully prescribed items.
- Every symbol 0-9 and comma appears >= 5 times.
- Exam printed twice (print-to-print variance).

#### Local-First Principle
- No image leaves a store without explicit approval.
- Extraction is local (Pillow + standard library).
- Tesseract only in legacy adapter path (not in product path).

#### Stash Inventory (read-only)
- Stash 72c4b48 was previously reported as missing.
- Current available stash: fea913a (safety snapshot).
- No apply, no drop. List only.

#### Open Items (need owner)
- SMS provider
- Host
- Default lock timeout (proposal: 15 minutes)
- Legal wording (D14)

#### E-00 Execution Note
- The supplied verbatim text names `fea913a`, but the E-00 safety snapshot in this checkout is `a397d8fa73ddfb90e743659e46e13c27062f3e65` (`stash@{0}`). The read-only stash list contained no `fea913a` entry. No stash was applied or dropped.

### Amendment v4.1 (E-00b)

#### D4 Amended
- SMS provider is NOT chosen yet.
- Use a stub provider through P-10.
- Real provider is selected before P-08 starts.

#### D5 Amended
- Vercel is NOT recommended (not suited to ASP.NET +
  PostgreSQL containers; reports of access problems
  from Iran; sanctions environment).
- Pilot host = a small VPS (domestic or non-US) running
  Docker.
- Free tiers must NOT carry customer data.
- Final host is the owner's decision.

#### D11 Clarified
- The lock covers an invoice DRAFT in progress for one
  phone number on one device.
- Released on: issue, cancel, disconnect, timeout
  (default 15 minutes, configurable).
- Resending the same operation id is a separate
  idempotency rule.
- Sequential purchases with the same number are allowed.

#### D14 Replaced
- Wording is "Kandoo digital invoice" (NOT described as
  a receipt).
- Store agreement (accepted at install with a digital
  signature) states data custody and encryption.
- ALL legal wording is drafted/reviewed by a lawyer.
- Developers write NO legal claims.

#### NEW SEC-1 (decision, S)
- Three options for data protection:
  1. Server-side encryption with restricted audited access
  2. End-to-end encryption for private store data with
     recovery key
  3. Hybrid
- Default for MVP: server-side encryption + restricted,
  logged access, with a key design that does not block a
  later move to end-to-end encryption.

#### NEW Rule: Restore Second Factor
- Restoring a store after reinstall requires a second
  factor besides the SMS code:
  * Recovery key created at install, OR
  * Approval from a previously paired device
- SIM-swap must NOT expose a whole store.
- Affects: P-02 (restore), P-04 (restore export), P-12.

#### NEW Rule: Agreement Truthfulness
- The agreement text must NEVER claim something the code
  does not do.
- Example: "we cannot see data" requires a test that
  proves it.
- All claims in agreement text must have a corresponding
  test.

#### Tasks Affected by v4.1
- P-02: D11 clarified, SEC-1 restore 2FA
- P-04: SEC-1 restore export 2FA
- P-08: D4 (stub until P-10, real before P-08)
- P-09: D14 (legal wording "Kandoo digital invoice")
- P-10: D5 (VPS with Docker, not Vercel)
- P-12: SEC-1 restore 2FA
- P-16: SEC-1 encryption

#### Tasks NOT Affected
- E-01, E-02, E-03, E-04, E-09, E-10 (extraction pipeline,
  independent of SMS/hosting/restore/legal)
