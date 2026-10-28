# E-10 — Packaging Feasibility Spike

**Date:** 2026-10-22
**Baseline:** `27d6d14ef02302423a903e09adb60bfe0164c8f7` (E-09)
**Branch:** `arena/9dc17500-kandoo-digital-invoice`
**Scope:** report-only feasibility study; no source-code changes, production bundle, installer, or code signing.

## 1. Scope and executive conclusion

The E-09 command-line product path is a plausible candidate for a small offline executable, but this spike did **not** produce a package. The attempted PyInstaller one-folder build stopped before application analysis because the local Python installation lacks `libpython3.11.so.1.0`. This runner is Linux, and PyInstaller does not cross-compile a Windows executable from it, so native Windows packaging and validation remain open.

The intended extraction product path is:

```text
image_extraction_adapter.cli
  → pipeline_v0
  → detect_layout_safe / spatial layout
  → Glyph numeric-cell classification + arithmetic gate
  → Canonical Invoice v0 validation/output
```

That path reads caller-supplied local files. It requires **Pillow**, **jsonschema**, the local Glyph template-bank JSON, the Canonical Invoice schema JSON, and the Python standard library. It does not call Tesseract, an OCR service, or a network API. `--context PATH` is required and is caller-owned producer JSON: the CLI does not invent identity, customer, or product-name context. AUTO with a valid candidate emits Canonical JSON and exits 0; REVIEW with a candidate emits JSON and exits 10; REVIEW without a candidate exits 10 with empty stdout and diagnostics on stderr; REJECT exits 20 with empty stdout and diagnostics on stderr; invalid input/internal errors exit 30 with empty stdout and diagnostics on stderr.

The separate legacy path (`adapter.py` → Tesseract OCR → flat-text parser) is not part of the E-09 product flow and should **not** be included in a production extraction package. Its OCR backend dynamically imports `tesserocr` and also needs a Tesseract native engine and traineddata when invoked. The Tesseract executable and `tesserocr` are absent from this runner; traineddata was not exercised or verified.

## 2. Source inventory and execution boundaries

The inventory covered **298 Python files under `src/`**: 136 non-test modules (108 package modules and 28 root scripts) and 162 test-only modules. There are 20 package directories. Imports were inventoried across the non-test source modules; the product, legacy, dynamic-import, resource-path, and OCR boundaries were reviewed directly. Test modules and smoke/benchmark scripts are not production bundle contents.

The E-09 path is distinct from the repository's other `pipeline` package. The former is `image_extraction_adapter.pipeline_v0`; it uses local raster/layout processing and does not submit to issuance. The other service/domain packages are not in the E-09 CLI import graph.

One packaging caveat is visible before building: importing `image_extraction_adapter.cli` first executes `image_extraction_adapter/__init__.py`. That initializer eagerly re-exports `adapter.py`, `ocr.py`, and `parser.py`, as well as shared model/preprocessing symbols. The product call does not execute the Tesseract backend or flat-text parser, but a freezer may still collect those legacy Python modules because of the eager exports. The `tesserocr` import itself is dynamic and occurs only when the legacy backend is used.

## 3. Dependency matrix

**Matrix legend:** “Product” means the E-09 extraction CLI product path; “legacy” means the Tesseract/flat-text adapter path. “Network” refers to runtime network/API access, not local process launches.

### Extraction adapter and its direct/helper modules

| Module path | Imports / runtime dependencies | Tesseract? | Network? | Product? | Legacy? | Notes |
|---|---|---:|---:|---:|---:|---|
| `src/image_extraction_adapter/cli.py` | Python stdlib; `.canonical_invoice`, `.pipeline_v0` | No | No | Yes | No | Entry point; reads `--image`, required `--context`, optional timestamp/templates; writes UTF-8 Canonical JSON only for a candidate. |
| `src/image_extraction_adapter/pipeline_v0.py` | Python stdlib; `.canonical_invoice`, `.glyph_classifier`, `.model`, `.preprocessing`; Pillow at image-processing call sites; `run_name_cluster_experiment` imported inside `_dhash_helpers()` | No | No | Yes | No | Calls `detect_layout_safe`, Glyph, arithmetic gate, and offline dHash helper; requires the default bank or caller-supplied templates. Dynamic helper import must be made explicit to a freezer. |
| `src/image_extraction_adapter/canonical_invoice.py` | Python stdlib; `jsonschema>=4.18,<5` loaded by the validator | No | No | Yes | No | Reads `schemas/canonical_invoice_v0.json`; schema validation is on the CLI output boundary. |
| `src/image_extraction_adapter/preprocessing.py` | Python stdlib; Pillow loaded lazily | No | No | Yes | Shared | Projection-based layout detection, cropping, binarization, and line removal; also used by legacy cell OCR. |
| `src/image_extraction_adapter/glyph_classifier.py` | Python stdlib; Pillow loaded lazily | No | No | Yes | Shared/optional | Glyph templates and numeric classification; no Tesseract call. The legacy adapter can also be configured with Glyph as its numeric backend. |
| `src/image_extraction_adapter/model.py` | Python stdlib (`dataclasses`, typing) | No | No | Yes | Yes | Shared outcome and OCR data types; defining Tesseract-shaped types does not load the engine. |
| `src/image_extraction_adapter/__init__.py` | Relative imports of `.adapter`, `.model`, `.ocr`, `.preprocessing`, `.parser` | Not at import | No | Yes, import-time | Yes | Eager compatibility exports are why legacy modules are imported during CLI package initialization. No OCR backend is instantiated here. |
| `src/image_extraction_adapter/adapter.py` | Python stdlib; `.model`, `.ocr`, `.parser` | Yes, when configured backend runs | No | No | Yes | Legacy adapter/orchestrator. Its default numeric authority is `tesseract_parse`; it is not used by `pipeline_v0`. |
| `src/image_extraction_adapter/ocr.py` | Python stdlib; `.model`, `.preprocessing`; dynamic `tesserocr` and Pillow imports in `TesseractOCR` methods | **Yes, when invoked** | No | No | Yes | Needs `tesserocr`, the native Tesseract engine, and requested traineddata (Persian `fas` and English `eng` for `fas+eng`). The code calls the Tesseract API, not a cloud OCR service. |
| `src/image_extraction_adapter/parser.py` | Python stdlib; `.model` | No engine by itself | No | No | Yes | Flat-text/spatial parsing of OCR output; not called by the E-09 product pipeline. |
| `src/run_name_cluster_experiment.py` | Pillow; `image_extraction_adapter.preprocessing`; Python stdlib | No in product use | No | Yes, helper only | No | `pipeline_v0` imports its dHash helpers. The standalone report command checks `shutil.which("tesseract")` only to annotate a comparison; importing/using the helper does not run Tesseract. |

### Other application/domain packages under `src/`

Each row below summarizes all non-test Python modules in that package directory. These packages use Python stdlib and intra-repository imports (including `sqlite3` for durable stores); none has a third-party runtime import, Tesseract dependency, or network call in the inspected source. They are outside both E-09 extraction paths—not a claim that they are non-product code for the wider application.

| Package path | Intra-repository package imports | E-09 product / Tesseract legacy |
|---|---|---|
| `src/calibration/*.py` | `canonicalization`, `capture`, `corpus`, `derivation`, `extraction`, `normalization`, `reconstruction`, `validation`, `validation_domain` | Neither |
| `src/canonical_assembly/*.py` | `canonicalization`, `capture`, `derivation`, `normalization` | Neither |
| `src/canonicalization/*.py` | `capture`, `normalization`, `validation_domain` | Neither |
| `src/capture/*.py` | No application-package imports; `urllib.parse.quote` is used for local path/URI encoding, not HTTP | Neither |
| `src/corpus/*.py` | `capture` | Neither |
| `src/customer_linking/*.py` | `canonical_assembly`, `capture` | Neither |
| `src/derivation/*.py` | `capture`, `derivation`, `extraction`, `normalization`, `reconstruction` | Neither |
| `src/digital_invoice/*.py` | `canonical_assembly`, `capture` | Neither |
| `src/duplicate_flows/*.py` | `capture`, `identity_resolution` | Neither |
| `src/extraction/*.py` | `capture`, `reconstruction` | Neither |
| `src/holoo_spike/*.py` | `capture`; `urllib.parse.quote` is local URI encoding | Neither |
| `src/identity_resolution/*.py` | `canonicalization`, `capture`, `normalization`, `validation_domain` | Neither |
| `src/issuance/*.py` | `capture`, `digital_invoice`, `pipeline` | Neither |
| `src/normalization/*.py` | `capture`, `extraction` | Neither |
| `src/pipeline/*.py` | `canonical_assembly`, `canonicalization`, `capture`, `derivation`, `extraction`, `normalization`, `reconstruction`, `validation`, `validation_domain` | Neither; separate from `pipeline_v0` |
| `src/product_candidate/*.py` | `canonical_assembly`, `capture` | Neither |
| `src/reconstruction/*.py` | `capture` | Neither |
| `src/validation/*.py` | `capture`, `derivation`, `extraction`, `normalization`, `reconstruction` | Neither |
| `src/validation_domain/*.py` | `capture`, `extraction`, `normalization`, `reconstruction`, `validation` | Neither |

### Root tools, tests, and runtime data

| Path(s) | Imports / requirements | Classification and packaging note |
|---|---|---|
| `src/run_dynamic_layout_benchmark.py` | Pillow and adapter preprocessing | Development benchmark; no Tesseract/network; not needed by CLI. |
| `src/run_image_preprocessing_benchmark.py` | Adapter, Pillow, `TesseractOCR` | Tesseract-dependent diagnostic; not product packaging. |
| `src/run_smoke_image_extraction.py` | Adapter, TesseractOCR, digital invoice/issuance/validation packages | Tesseract-dependent legacy smoke path; not the E-09 CLI. |
| `src/run_glyph_leave_one_out.py` | Python stdlib, Glyph module, local subprocess invocations | Development evaluation tool; subprocesses are local Python processes, not network. |
| `src/run_smoke_all.py` and other `src/run_smoke*.py` scripts | Python stdlib and the corresponding local service packages; some use SQLite; the all-smoke runner launches local Python subprocesses | Development/smoke tooling, not the E-09 executable. The image smoke runner is listed separately above because it instantiates Tesseract. |
| `src/test_run_smoke_all.py` and `src/**/tests/*.py` | Test-only modules; pytest is a development/test dependency | Exclude from a runtime bundle. Synthetic test fixtures are not runtime data. |
| `src/templates_bank_default.json` | Local JSON data | Required default Glyph template bank for the product CLI. |
| `schemas/canonical_invoice_v0.json` | Local JSON data | Required schema for Canonical Invoice validation. |
| `src/templates.json`, `src/labels_build.json`, `src/labels_eval.json` | Local legacy/calibration data | Not needed for normal E-09 CLI extraction; do not substitute the legacy template bank for the default product bank. |

The E-09 product call graph contains no network client or network request. The CLI test `test_cli_makes_no_network_calls` patches `socket.create_connection`, `urllib.request.urlopen`, and `http.client.HTTPConnection.connect`; it passes. The only `urllib` imports found in the other application packages are `urllib.parse.quote` for local SQLite URI/path encoding.

## 4. Runtime contents and resource-path constraints

The only third-party runtime packages on the E-09 product path found in the source import inventory are **Pillow** and **jsonschema**. In this spike environment their versions were Pillow 13.0.0 and jsonschema 4.26.0; the source explicitly bounds jsonschema to `>=4.18,<5`. The current environment is Python 3.11.2. `src/README.md` describes the wider source stack as Python 3.12+, so the supported release interpreter still needs to be declared and tested rather than inferred from this run. There is no `pyproject.toml`, `setup.py`, requirements file, or existing PyInstaller spec in the repository root.

Two source-relative data lookups must be preserved by any frozen bundle:

- `pipeline_v0.py` computes the template default from `Path(__file__).resolve().parents[2] / "src" / "templates_bank_default.json`.
- `canonical_invoice.py` computes the schema path from `Path(__file__).resolve().parents[2] / "schemas" / "canonical_invoice_v0.json`.

A PyInstaller spec therefore needs to place both JSON files at paths that satisfy those lookups in the frozen one-folder layout, or a later, separately scoped code change should switch resource resolution to an explicit bundle-aware/package-resource mechanism. The product path also imports `run_name_cluster_experiment` inside a function, so the attempted build explicitly named it as a hidden import. Since the build stopped before analysis, resource collection and frozen import behavior remain unverified.

Although the logical CLI path does not use legacy OCR, the eager package initializer may cause PyInstaller to collect `adapter.py`, `ocr.py`, and `parser.py` Python modules. That is packaging overhead and a boundary-cleanup recommendation, not evidence that the runtime needs Tesseract. No Tesseract binary, `tesserocr`, or traineddata should be added to the product bundle.

## 5. PyInstaller one-folder attempt

PyInstaller was not initially present in the venv, so the spike installed PyInstaller 6.22.3. The attempted Linux one-folder feasibility command used a temporary wrapper (outside the repository) and the known dynamic helper import:

```sh
/tmp/kandoo-t2-venv/bin/python -m PyInstaller \
  --clean --noconfirm --onedir --console \
  --name kandoo-extract --paths src \
  --hidden-import run_name_cluster_experiment \
  --distpath /tmp/e10-dist --workpath /tmp/e10-work \
  --specpath /tmp/e10-spec /tmp/e10_cli_entry.py
```

**Result:** exit code 1, before PyInstaller reached application analysis:

```text
ERROR: Python shared library ('libpython3.11.so.1.0') was not found!
```

The runner has Python 3.11.2 but no discoverable matching shared library. No executable or one-folder bundle was produced; package size and frozen-startup time are therefore **not available**. This is an environment/build prerequisite failure, not a reported application import/runtime failure. Because the host is Linux, this attempt was not a Windows build; PyInstaller cannot cross-compile a Windows executable from this runner.

Remedy for another Linux feasibility run: use a Python distribution with its matching `libpython3.11.so.1.0` available (or install the matching runtime package and configure its library path), then repeat the onedir build and test the bundled schema/template locations. For the requested Windows result, build on a native Windows runner with the selected supported CPython version and PyInstaller. A Linux success would still not constitute Windows validation.

## 6. B2-3 ASCII-path history and non-ASCII path test

The B2-3 history records a Tesseract-specific failure with non-ASCII/Persian paths. Keep an **ASCII-only installation path for the separate legacy Tesseract deployment until a native Windows retest says otherwise**. This historical constraint is about the legacy OCR path; it is not evidence that the E-09 Glyph product path requires ASCII-only paths.

A source-mode product CLI test was run on this Linux host with a temporary Persian-named working directory and Persian-named image/context files. It used fixture `tests/fixtures/real/29.png`, copied to `رسید-۲۹.png`, and a test-only producer-shaped context JSON at `زمینه-صورتحساب.json`:

```text
cwd:     /tmp/کندو-آزمون-…
image:   /tmp/کندو-آزمون-…/رسید-۲۹.png
context: /tmp/کندو-آزمون-…/زمینه-صورتحساب.json
exit:    0
stdout:  2,964 UTF-8 bytes of Canonical JSON
stderr:  empty
result:  EXTRACTED, 4 line items
```

The call succeeded with neither the `tesseract` executable nor `tesserocr` installed, consistent with the no-Tesseract product boundary. This confirms the **Linux source-mode** path handling for the tested image/context/current-working-directory paths only. It does **not** establish Windows Unicode-path compatibility, a Unicode PyInstaller install path, or behavior of the legacy Tesseract route. A frozen executable could not be tested because the build failed above.

## 7. Verification results

The requested test command passed on the E-09 baseline:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python -m unittest discover -s src -p 'test_*.py' -v
Ran 106 tests in 3.262s
OK
```

The run used Pillow 13.0.0 and jsonschema 4.26.0. One non-failing Pillow deprecation warning was emitted by a test using `Image.Image.getdata`; it does not affect the package feasibility result. The CLI tests covering “does not require Tesseract” and “makes no network calls” both passed.

No source module, frozen contract, or adapter behavior was changed for E-10. The non-ASCII test used only temporary files outside the repository, and the attempted PyInstaller work/spec/output paths were under `/tmp`.

## 8. Recommendations and next steps

1. **Keep the product bundle narrow:** package the E-09 CLI path, Pillow, jsonschema, `run_name_cluster_experiment` as an explicit hidden import, `src/templates_bank_default.json`, and `schemas/canonical_invoice_v0.json`. Exclude tests, smoke/benchmark tools, legacy parser execution, Tesseract, `tesserocr`, traineddata, network clients, and unrelated service packages unless a separate product scope requires them.
2. **Make resources deterministic:** when packaging work resumes, either preserve the source-relative resource layout expected by the current code or propose a separately reviewed resource-loading change. Do not silently fall back to the legacy `src/templates.json` bank.
3. **Separate legacy imports in a future scoped change:** consider splitting the E-09 CLI into a product-only package or making compatibility exports lazy so a future freezer need not collect the legacy adapter/parser modules. This E-10 report does not make that source change.
4. **Retry on a supported build host:** first fix the shared-Python-library prerequisite for Linux analysis if useful; then perform an actual native Windows onedir build on the declared CPython version. Record build logs, package size, and repeated cold/warm startup timings only after a successful artifact exists.
5. **Validate paths on Windows:** run the product executable from a Persian/non-ASCII installation directory with Persian image and `--context` paths, and separately check ASCII paths. Do not infer Windows behavior from this Linux test. Keep the legacy Tesseract deployment on an ASCII-only path until its own native test clears the historical B2-3 issue.
6. **Keep OCR deployments separate:** the product extraction path is offline and Tesseract-free. If the legacy adapter is ever distributed for diagnostics, treat it as a separate optional package with explicit Tesseract/native-library/traineddata provisioning and its own path/Windows tests; do not make it a production prerequisite.
7. **Do not treat this spike as a release:** no production package, installer, code signing, or Windows compatibility claim was produced. Those remain outside E-10 and require a later packaging task with a successful native build and acceptance run.
