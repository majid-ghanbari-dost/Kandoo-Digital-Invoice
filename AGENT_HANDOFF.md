# KANDOO DIGITAL INVOICE — AGENT HANDOFF

> This file is the mandatory project handoff and operational source for onboarding agents.
> It must be updated at the end of every meaningful project conversation/change affecting this repository.
> It is NOT a replacement for authoritative specs/registers; those remain authoritative for technical contracts.

## 1. Project Identity

Repository: `majid-ghanbari-dost/Kandoo-Digital-Invoice`
Purpose: dedicated development line for Kandoo Digital Invoice / Holoo capture / canonicalization work.
Parent project: `majid-ghanbari-dost/Kandoo`

This repository must contain only the Digital Invoice project line and its directly required artifacts.

Conceptual relationship:

Kandoo (parent)
└── Digital Invoice development line
    └── Kandoo-Digital-Invoice

The repositories are intentionally separate during development. At a later integration point the Digital Invoice line may be synchronized/merged back into the parent Kandoo project.

## 2. Mandatory Collaboration Rule

At the end of every meaningful project conversation or implementation change concerning this repository:

1. Update this file with the new verified state.
2. Record completed/changed WPs, decisions, blockers, ownership and next executable work.
3. Update relevant authoritative specs/registers/code/tests in the same project change.
4. Commit the resulting state.
5. Do not claim a change is integrated until the repository state reflects it.

Administrative discussion that causes no project-state change need not create a commit.

### Automatic Project-Sync Policy

For every conversation that produces a real project output/change, the coordinator must:
- update the actual project artifact in the authoritative repository when the available connector permits it;
- update this handoff in the same change/commit;
- update `KANDO_AGENT_COORDINATION.md` when ownership or execution state changes;
- report the exact repository commit/HEAD in the final report;
- never claim source integration when only a local/archive artifact was produced.

If the current tool environment cannot transfer a required local artifact into GitHub, record that limitation here and continue using the verified artifact as the source package; do not fabricate a successful sync.

## 3. Roles

Product Owner / Final Decision Maker: user
Technical Manager / Architect / Coordinator: ChatGPT
Agent 1: current implementation agent
Agent 2: second implementation/research agent

Each WP has one owner. Agents must not concurrently modify the same WP/files.

## 4. Collaboration Rules

- Frozen decisions are not reopened without direct contradictory evidence.
- No Architecture Loop.
- If contract + acceptance criteria are sufficient, implement directly.
- A mission should continue through multiple executable WPs when dependencies and ownership permit.
- Stop only at a real boundary: PO decision, missing contract/AC, real-world evidence requirement, contradiction with frozen architecture, or genuine technical blocker.
- Reports/artifact extraction are not independent project phases.
- Agent branches must not overwrite another agent's work.
- Main is the integration/source branch.
- Every substantive implementation must be tested and committed.
- Full archive + manifest + SHA-256 remain required for delivery checkpoints.

## 5. Frozen Architecture / Domain Principles

- Business → Store → Users/Devices.
- SQLite local Outbox ↔ Cloud API ↔ PostgreSQL.
- OperationId = idempotency key.
- Global Revision = sync cursor.
- AggregateVersion / OCC with base_version.
- No silent overwrite.
- Inventory is ledger-based.
- Negative inventory is allowed.
- Inventory shortage alone must not reject a Sale.
- CorrelationId is not a transaction/FK.
- Product deactivation uses is_active=false.
- Employee cannot final-confirm Product Candidate.
- Customer capture cannot auto-create a Customer.
- Canonical Invoice v1 is source-independent.
- UNRESOLVED and provenance are allowed.
- Native path: Sale → Invoice → Digital Invoice.
- External captures enter domain only through Canonicalization Gate.
- Gate outcomes: AUTO / REVIEW / REJECT.
- External capture must not silently create Sale / Inventory / KPI.
- Digital Invoice lifecycle: DRAFT → EXTRACTED → VALIDATED → ISSUED, plus REVOKED / SUPERSEDED.
- Holoo is an external accounting/tax system.
- Current Holoo path: Holoo → Print Spooler → Kandoo Agent → Raw Capture → durable local storage → extraction/recognition → Canonicalization Gate.
- No real production Holoo DB connection is permitted by the current project boundary.

## 6. Current Verified Project State

### Current serial window — 2026-10-29

The current task branch is `arena/d892dd9b-kandoo-digital-invoice`, based on the PR #11 merge commit `a8662f458255d66307d0783bd7e14b80addeb06b` on `main`. PR #11 is merged; older entries below that say PR #11 is open or `main` is unchanged are historical snapshots and are superseded by this state. E-26 is certified; E-27 is published at `7abf174755d36bdf1aeb787f8bbc5145070725b5` (`stable-e-27`); N-07 closes in this task commit, followed by E-28 → E-29. Frozen paths `contracts/` and `src/image_extraction_adapter/adapter.py` remain byte-identical.

### N-01–N-03 closeout — offline name reading and ProductCandidate prototype (2026-10-25)

This closeout records the serial N-01, N-02, and N-03 work on the existing branch. N-01 and N-02 are committed, pushed, tagged, and green on their final task SHAs. N-03 is this handoff update; its `stable-n-03` tag is applied only after the handoff commit's checks pass.

| Task | Commit SHA(s) | Annotated tag | Result |
|---|---|---|---|
| N-01 | `56ce2847bd47ad00badff109c6ee900e615af843` (measurement) → `c35c47b11aba0789fd6b235d55e104e99476dd05` (CI job and final report) | `stable-n-01` → `c35c47b11aba0789fd6b235d55e104e99476dd05` | Offline OCR measurement, 100 raw results, metrics, local-only CI job. |
| N-02 | `1993f743c2856f194ef8e310b9f59b1465b4006b` | `stable-n-02` → `1993f743c2856f194ef8e310b9f59b1465b4006b` | Deterministic text-free candidate prototype, schema, golden, crop references, tests. |
| N-03 | This handoff commit | `stable-n-03` | Records N-task SHAs, tags, results, caveats, and current repository state. |

**N-01 evidence and limits:** `docs/n01-name-reading.md` and `docs/n01-name-reading.json` contain results for 25 product-name crops from real fixtures 29/31/32/33. Six supplied visual references are provisional and not owner-confirmed; 19 crops remain unscored. Tesseract `fas`: 2/6 exact, CER 8/76 (10.53%), zero hard failures; ParisaOCR: 4/6 exact, CER 2/76 (2.63%), zero hard failures. Raw and Otsu outputs were identical across all 50 crop/engine pairs. The recorded verdict is ParisaOCR as a human-confirmed suggestion only, never auto-accepted; Tesseract is not usable as the suggestion engine on this sample. No images were sent to a network service. The optional `n01-name-reading` job in `.github/workflows/python-tests.yml` passed on the final N-01 push run [40214575315](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40214575315); the push Windows build [40214575334](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40214575334) and PR checks [Python 40214579255](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40214579255) / [Windows 40214579278](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40214579278) also passed. Its 14-day report artifact was uploaded. Artifact download from this sandbox returned EOF, so CI artifact bytes were not independently compared with the committed local report.

**N-02 prototype results and limits:** `docs/n02-product-candidates.md` documents the builder, schema, golden output, and 22 committed reference crop files. The four label-derived canonical fixtures produce 22 candidates over 25 line-item occurrences (quantity sum 87), including the three expected repeated visual groups recorded by their crop-ID pairs: `31_row0/32_row0`, `31_row1/32_row3`, and `31_row2/33_row1`. Candidate records contain no product-name text or categories. Every fixture's `header.printed_date` is null, so all dated price-observation arrays are empty; no date is inferred from capture time or other metadata. The canonical JSON files contain synthetic context and placeholder product names, which the builder deliberately ignores. N-02 is a prototype, not production catalog state or a confirmed product identity.

**Tests and CI:** Full local suite on Python 3.11 / Pillow 13.0.0: **1,909 passed, 107 subtests passed**. N-01 OCR workflow, Python 3.11/3.12 test matrix, E-20/E-21 checks, and Windows one-folder builds passed on final task commits. N-02 push runs: [Python 40215992858](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40215992858), [Windows 40215992834](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40215992834); PR runs: [Python 40215995865](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40215995865), [Windows 40215995922](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40215995922). On intermediate N-01 commit `56ce284`, push Windows run [40214379388](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40214379388) failed at the E-11 test step, while that commit's PR Windows run [40214382133](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40214382133) and the final N-01 push/PR Windows runs passed. Failed-run log retrieval returned EOF, so the intermediate failure remains unexplained and is superseded by the green final SHA.

**Repository boundary as of the N-03 closeout (2026-10-25):** `arena/9dc17500-kandoo-digital-invoice` was active; PR #11 remained OPEN. The N-02 code commit was `1993f743c2856f194ef8e310b9f59b1465b4006b`; the N-03 handoff commit became the branch head at that closeout. `main` remained `15901d6c88344c7f5e39471130d60c4dd5658b83`. No merge, force-push, C# change, or edit under frozen `contracts/` was made. N-01/N-02 details are in the linked task reports; N-03 recorded that closeout.

### N-04 closeout — optional ParisaOCR name suggestions (2026-10-26)

N-04 is complete as an optional, non-accepting prototype. The full report is [`docs/n04-name-suggestions.md`](docs/n04-name-suggestions.md). It records raw Windows measurements, model/package provenance, verbatim license excerpts, the resolved dependency-license table, comparison with E-19, recommendation, and risks.

| Work group | Commit(s) |
|---|---|
| Optional suggestion prototype and initial Windows workflow | `f953c1103dab46aa91ed7345c19afa45d18ddecf` |
| Failure diagnostics, Windows `resource` shim, and benchmark evidence annotations | `59888b9c3bd463429ff2cd0bd7d453758fff97e6`, `af8dae13b323f71df0b0b535eb6938672fa74930`, `db13db90b89d48c93761738e2e4ba600ca507b1d`, `cbf9edf9193b588c5f2b7d98d679cf7710b05e4a`, `3d9d28b00acbf0f1944024d5530a4922f15b16e9` |
| N-04 report and handoff closeout | `8308023e208d8a648b6bd410f63f2c821d476ab7` (docs-only; `stable-n-04`) |

The sole annotated tag for N-04 is `stable-n-04`, targeting closeout commit `8308023e208d8a648b6bd410f63f2c821d476ab7`; both final workflows passed at that tagged commit. The versioned optional enrichment adds a `name_suggestions` list to every N-02 candidate, keeps two-line text in ordered `lines`, includes engine/version/model/confidence and crop hash provenance, and always writes `accepted: false`. The disabled path produces empty suggestion arrays; it does not load PyTorch. Frozen `contracts/` and `adapter.py` were not changed.

**Benchmark and evidence:** Windows-latest run [40311286720](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40311286720) on measurement SHA `3d9d28b00acbf0f1944024d5530a4922f15b16e9` passed the N-04 CPU benchmark, uploaded its evidence artifact, and passed the ordinary OCR-free one-folder build. Its Python workflow [40311286610](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40311286610) also passed. The optional venv `site-packages` delta was 1,389,385,292 bytes (1,325.021069 MiB); CPU model initialization 5.098956 s; per-crop min/median/p95/max 0.7513097/0.79438605/1.3860779/1.3948378 s over 22 crops; peak resident working set 798,072,832 bytes. These are one-run Windows-latest measurements, not accuracy claims. The full local suite passed **1,918 tests and 111 subtests** after the N-04 code changes; focused tests were 9 passed plus 4 subtests. Artifact `n04-name-suggestions-40311286720` was uploaded (14-day retention, 316,270 bytes at query time); `windows-onefolder-40311286720` was uploaded as the separate no-OCR build. The N-04 closeout commit `8308023e208d8a648b6bd410f63f2c821d476ab7` is docs-only (`AGENT_HANDOFF.md` and `docs/n04-name-suggestions.md`; see `git show --stat 8308023`). The final Python run [40313438293](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40313438293) and Windows run [40313438283](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40313438283) are green at that tagged commit; annotated tag `stable-n-04` targets it.

**Licensing and risk:** The actual PyPI ParisaOCR 0.7.2 wheel metadata declares Apache-2.0 and its NOTICE declares Apache-2.0 for the included detector/model, SIL OFL 1.1 for Vazirmatn fonts, and notes CC BY-SA 4.0 Wikipedia text in synthetic training lines. The pinned upstream model card also says scanned-book copyright status varies and is unknown to its author. The report therefore recommends legal review and upstream clarification before commercial model redistribution. Keep N-04 opt-in; the observed 1.325-GiB venv delta, 761.102-MiB peak working set, ~5.10-s model initialization, and 0.75–1.39-s per-crop inference are substantial compared with the E-19 no-OCR bundle.

**Intermediate CI evidence retained:** Windows push runs [40307573911](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40307573911) and [40308376556](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40308376556) failed because ParisaOCR imported POSIX-only `resource` on Windows; the narrow shim fixed the image-only path. Run [40308983293](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40308983293) was the `windows-build.yml` workflow at head `af8dae13b323f71df0b0b535eb6938672fa74930`, inside job `Windows / Python 3.11 / PyInstaller onedir`. It failed at step “Windows tests - frozen E-11 contract package” (`pytest tests/test_e11_contract_package.py`), exit code 1. The PyInstaller step never ran. The failing assertion is unidentified because log retrieval returned EOF. The same-SHA PR Windows run [40308988488](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40308988488) passed. The owner's whole-window audit of 17 changed paths found no file under `contracts/` and no `src/image_extraction_adapter/adapter.py`; the frozen-path audit is closed. Green final tagged-commit runs supersede the red intermediate. Calling this a Windows packaging failure was an executive-manager mischaracterization.

**Serial closeout status:** N-04, N-05, E-24, and N-06 are complete; E-25 is the current documentation-only window closeout. N-01/N-04 evaluation references remain provisional and owner-unconfirmed. PR #11 remains open; `main` is unchanged.

### N-05 closeout — versioned ProductCandidate and NameSuggestion examples (2026-10-26)

N-05 adds [`schemas/n05/product_candidate_v1.schema.json`](schemas/n05/product_candidate_v1.schema.json), versioned as `n05.product-candidate.v1`, plus four real-fixture golden examples under `tests/fixtures/real/n05-goldens/` and a deterministic generator in `scripts/generate_n05_candidate_goldens.py`. The full scope and limitations are in [`docs/n05-product-candidate-contract.md`](docs/n05-product-candidate-contract.md).

| Work group | Commit / tag | Result |
|---|---|---|
| N-05 schema, generator, tests, docs, and four goldens | `3f5a26e7add23d188163188ba61cfba6d802b691` | Adds a versioned sample envelope around the existing N-02 candidate fields; preserves N-02/N-04 output contracts and does not edit frozen `contracts/` or `adapter.py`. |
| N-05 handoff closeout | `0cc7f32769b8bbc0a035b6ea27fd6e411e1fa256`; sole annotated tag `stable-n-05` targets this commit | Final closeout; `main` unchanged and PR #11 open. |

The goldens use the recorded unprocessed ParisaOCR 0.7.2 outputs in `docs/n01-name-reading.json`, with model `parisaocr-fa-0.1`; suggestions preserve confidence, ordered lines (including the real two-line result for `33_row10`), engine/model versions, crop ID/path/SHA-256, and `accepted: false`. The selected `31_row0` ProductCandidate retains its existing N-02 aggregate with `32_row0` rather than splitting or rewriting that cluster. Raw OCR strings remain suggestions only; N-01/N-04 references are provisional and owner-unconfirmed.

All four canonical fixtures have `header.printed_date: null`, so the real-fixture `price_observations` arrays remain empty. The schema defines explicit ISO-dated rials observations and tests a separate synthetic schema probe; no date is inferred or added to a real golden. The generator does not run OCR. Its same-input/same-output behavior is tested by generating twice from the same canonical inputs and pinned N-01 OCR output and comparing exact serialized bytes with all four committed goldens.

**Verification:** full local suite at N-05 closeout **1,924 passed, 115 subtests passed**; focused N-05/N-04/N-02 tests **22 passed, 33 subtests passed**. On implementation commit `3f5a26e7add23d188163188ba61cfba6d802b691`, the push Python workflow [40315532534](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40315532534) and Windows workflow [40315532561](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40315532561) both succeeded. The final closeout SHA `0cc7f32769b8bbc0a035b6ea27fd6e411e1fa256` was green on Python run [40316077949](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40316077949) and Windows run [40316078058](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40316078058); annotated tag `stable-n-05` targets this SHA.

### E-24 closeout — explicit layout profiles and line-price witnesses (2026-10-26)

E-24 adds the versioned registry `src/image_extraction_adapter/layout_profiles_v1.json` (`e24.layout-profile-registry.v1`) and fail-closed evaluator `src/image_extraction_adapter/layout_profiles.py`. Profiles declare exact column roles and left-to-right order; selection requires an exact registered ID. Unknown IDs, unknown/reordered/extra/missing columns, unsupported or missing currency units, and incomplete/failed arithmetic evidence return REVIEW. No profile, currency unit, price, or conversion is inferred.

`holo-rtl-four-column-v1` declares `(line_total, quantity, description, row_number)` but no explicit unit-price role; the evaluator returns REVIEW instead of deriving unit price by dividing total by quantity. Synthetic profiles cover unit price, discounted price and optional paired pre-discount `unit_price`/`discount_percent`, two-line descriptions, a crossed-out consumer price as non-witness context, and explicit rial/toman settings. Discount arithmetic is exact with no rounding; incomplete discount inputs and crossed-out witness inputs REVIEW.

The deterministic runner covers **11/11 safe routes** (EXTRACTED only with exact witnesses, otherwise REVIEW/BLOCKED), with **zero EXTRACTED-but-wrong**; it loads no images or OCR and uses synthetic ordered values only. No third-party images were added. The four existing real Holo fixtures 29/31/32/33 are separate byte-for-byte compatibility tests against pre-E-24 `extract_pipeline_v0()` goldens; only the environment-specific absolute template-bank path is normalized. Golden byte counts and SHA-256 values are in `docs/e24-layout-profiles.md`.

Implementation commit `b8f4047cef946daaab3f11880669266de932e5bb` was pushed; Python run [40322487925](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40322487925) and Windows run [40322487999](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40322487999) both passed. Local focused tests: **10 passed, 4 subtests passed**; full suite: **1,934 passed, 119 subtests passed**. The only package-surface change is `src/image_extraction_adapter/__init__.py`; `src/image_extraction_adapter/adapter.py` and `contracts/` are unchanged. The E-24 docs-only handoff closeout is commit `9305efbf75091f3a5df1c57bb6fe9756af096c9b`; annotated tag `stable-e-24` targets it. Both closeout workflows passed at that tagged commit: Python run [40323114292](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40323114292) and Windows run [40323114298](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40323114298).

### N-06 closeout — explicit currency unit and Probe capture dates (2026-10-26)

N-06 adds explicit `currency_unit` metadata to the E-05 `TemplateBank` and its JSON serialization. `rial` and `toman` are accepted without conversion; an unset or unsupported value adds E-06 `CURRENCY_UNIT_UNCONFIRMED`, blocks owner promotion, and routes otherwise reviewable invoices to REVIEW. Legacy banks without this field still load as unconfirmed. The capture-folder result exposes the bank setting and status.

N-02 now uses only the offset-aware Probe `captured_at` timestamp for price-observation dates: the N-02 CLI accepts an explicit `--captured-at` override, or the builder uses each Canonical fixture's `header.captured_at`. It never reads `header.printed_date`, invoice-image dates, file timestamps, or the current date. The four committed Canonical fixtures have no capture timestamp, so the default golden remains undated. A separate deterministic golden exercises 25 observations with the explicitly synthetic sentinel `2099-01-02T03:04:05+03:30`; this is not real Probe evidence. At the N-06 closeout the capture-folder CLI accepted and forwarded `--captured-at` without parsing `Report.txt`; E-27 subsequently added a narrow synthetic `Timestamp:` subset parser while the real Probe report format remains unspecified.

**N-06 verification after authorized reset:** focused tests **91 passed, 33 subtests passed**; full suite **1,949 passed, 119 subtests passed**; `git diff --check` passed. Frozen `contracts/` and `src/image_extraction_adapter/adapter.py` are unchanged. Commit `bbf08e1aed31d6f165294ffe4ca0f9cf4db3d2cb` is tagged `stable-n-06`. PM-relayed push CI at this SHA: Python `python-tests` run #61 / [40391678234](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40391678234), SUCCESS (5m 40s, Oct 26); Windows `windows-build` run #57, SUCCESS (1m 19s, Oct 26; global run ID/URL was not included in the relay). PR #11 Windows run [40391682594](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40391682594) passed. Incident wording: PR #11 (pull_request event) python-tests run 40391682589 at commit bbf08e1aed31d6f165294ffe4ca0f9cf4db3d2cb failed on its first attempt (job "Ubuntu / Python 3.12", exit code 1, 2026-10-26 19:59Z). The identical tree passed the same job in push run #61 (global 40391678234) and in the run's attempt-2 re-run (job green 20:15:24Z -> 20:18:35Z; run conclusion SUCCESS, run_attempt 2). Classified TRANSIENT (flake or ubuntu-26 runner migration); no code change made; PR #11 checks all green after the re-run. PR #11 remains open; `main` is unchanged.

### E-25 closeout — N-04 correction and task-window ledger (2026-10-27)

E-25 is a docs-only closeout for the N-04 → N-05 → E-24 → N-06 window. The N-04 run 40308983293 correction is recorded in this handoff and `docs/n04-name-suggestions.md` in the same commit group; there is no separate correction commit. Run 40308983293 failed in the frozen E-11 contract-package test step, not in PyInstaller; the exact failing assertion remains unknown because log retrieval returned EOF. The executive-manager's prior “Windows packaging failure” description was a mischaracterization. The frozen paths were untouched throughout N-04, and green final runs at `stable-n-04` supersede the intermediate red. `stable-e-24` remains unchanged.

| Task | Closeout commit | Annotated tag | Final task CI |
|---|---|---|---|
| N-04 | `8308023e208d8a648b6bd410f63f2c821d476ab7` | `stable-n-04` | Python `40313438293` and Windows `40313438283`, both green. |
| N-05 | `0cc7f32769b8bbc0a035b6ea27fd6e411e1fa256` | `stable-n-05` | `40316077949` and `40316078058`, both green. |
| E-24 | `9305efbf75091f3a5df1c57bb6fe9756af096c9b` (implementation `b8f4047cef946daaab3f11880669266de932e5bb`) | `stable-e-24` | Closeout runs `40323114292` and `40323114298`, both green; implementation runs `40322487925` and `40322487999`, both green. |
| N-06 | `bbf08e1aed31d6f165294ffe4ca0f9cf4db3d2cb` | `stable-n-06` | Push Python run #61 / `40391678234`, SUCCESS (5m 40s); push Windows run #57, SUCCESS (1m 19s; global ID not relayed). PR Windows `40391682594` passed; PR Python `40391682589` first-attempt incident and green attempt 2 are recorded above. |
| E-25 | `85b2184501b98523ce959c352d27a8532ffc2c83` | `stable-e-25` | PM-relayed push Python `40454275520` (first attempt red; attempt 2 SUCCESS) and Windows `40454275548` SUCCESS; PR Python `40454279573` and Windows `40454279702` SUCCESS. |

At the E-25 closeout on 2026-10-27, PR #11 was open and all checks on N-06 were green after the Python rerun. No N-06 code change was made in response to its transient first-attempt failure. The E-25 closeout did not move or re-point any existing tag. This status is historical; PR #11 was merged on 2026-10-28, producing `main` commit `a8662f458255d66307d0783bd7e14b80addeb06b`.

### E-26 closeout — operator onboarding CLI (2026-10-28)

E-26 adds `onboard build`, `onboard verdict`, and `onboard register-type` to the local CLI. The normal build path wraps the provenance-checked E-05 builder with capture-root, operator-confirmed labels, Canonical v0 fixtures/sidecar, explicit store ID, and explicit `rial`/`toman` unit. The E-20-only synthetic build path is explicitly separate and does not label synthetic answer-key data as operator-confirmed. Verdict artifacts bind to SHA-256 of the exact E-16 bank-file bytes. E-08 candidates are exported as E-16 `new-type-candidate` snapshots and remain separate from the active bank; the one-shot CLI does not persist E-08 audit trails or synthesize the separate E-02-backed `layout-font-fingerprint` artifact.

The Windows one-folder workflow now includes the E-16 v1 schemas and synthetic E-20 helper. Its built-executable verifier exercises `build`, `verdict`, and `register-type` against the E-20 synthetic second-store mechanics data, while retaining the existing extraction checks. `docs/operator-onboarding-cli.md` documents the CLI and a C# `Process.Start` integration. E-16 schema shapes and frozen Canonical contracts are unchanged.

Local verification: the complete Python suite passed **1,954 tests and 119 subtests**; the focused E-05/E-06/E-08/E-16 suite passed **52 tests**; the new onboarding CLI tests passed **5 tests**; `git diff --check` and `py_compile` passed. Frozen-path diff/status checks for `contracts/` and `src/image_extraction_adapter/adapter.py` were empty. The final E-26 closeout report records the full task SHA, push-event CI URLs/results, and the annotated `stable-e-26` tag.

### E-27 closeout — synthetic capture-folder end-to-end harness (2026-10-29)

E-26 certification: commit `e7b7f65b2fb1fae81c82a73604daed3dee6345bb` (`stable-e-26`) passed Python run `40717568578` and Windows run `40717568817`; frozen paths remained unchanged.

E-27 extends the E-12 capture-folder adapter to read an offset-aware `Timestamp:` from `Report.txt` into `captured_at`, reject conflicting explicit overrides, and validate only the explicit synthetic harness subset (`Spool job ID:`, `Page count:`, optional `SPL SHA-256:`). Missing PNG, hash-corrupt synthetic SPL, zero-page job, duplicate job ID, and two PNGs against a single-page report all return `BLOCKED` / `REVIEW` with stable exit 20 and specific error codes. The Windows built-executable verifier runs four fixture-backed capture folders and compares extracted quantities, line totals, payable, and derived subtotal against their label-derived Canonical JSON goldens; it also checks all five blocked cases. The report/SPL inputs are synthetic conventions, not authentic KandooPrintProbe output; the real report format and SPL structure remain unverified.

Local verification at E-27 closeout: full suite **1,961 passed, 119 subtests passed**; capture-folder suite **20 passed**; source CLI harness rehearsal matched all four Canonical goldens and returned exit 20 for all five failure cases; `py_compile` and `git diff --check` passed. Windows built-executable execution is delegated to the push workflow and its CI relay; no local Windows run is claimed, and CI relay remains pending. Published commit `7abf174755d36bdf1aeb787f8bbc5145070725b5` is tagged `stable-e-27` (annotated tag object `dab009e88ada3d3b283ad7eb5edb4edac57bfea8`). N-07 follows E-27; E-28 → E-29 remain queued.

### N-07 closeout — deterministic NameConfirmation work-list (2026-10-29)

N-07 adds `scripts/run_n07_name_worklist.py` and the `n07.name-worklist.v1` schema. For the repository's 25 crop occurrences, the work-list emits one crop PNG per exact normalized dHash ProductCandidate, an empty `confirmed_name`, and a stable `UNCONFIRMED` state by default. Reuse is keyed only by exact `name_crop_cluster_id`; the test adds a later synthetic invoice occurrence and confirms the prior name is reused with the same bytes on rerun. The work-list re-groups only exact hash matches; distinct hashes at the one-bit dHash threshold remain separate, both require REVIEW, and no merge or confirmation transfer occurs. The current repository samples contain no one-bit boundary pair; this behavior is tested with an explicitly synthetic pair.

`schemas/n05/product_candidate_v1.schema.json` now defines `NameConfirmation`; all four N-05 golden examples were regenerated with empty names and empty suggestions. The default N-05/N-07 build does not initialize OCR. `--suggest-names` is explicit and requires the optional ParisaOCR package; any emitted N-04 suggestion remains `accepted: false` and never fills `confirmed_name`. `docs/n07-name-worklist.md` records the output, confirmation-file format, reuse key, and safety policy. The extension did not touch frozen `contracts/` or `src/image_extraction_adapter/adapter.py`.

Verification at N-07 closeout: full suite **1,968 passed, 123 subtests passed**; combined N-05/N-07 focused suite **13 passed, 8 subtests passed**; the N-07 schema validated all 22 generated fixture-backed work items and crop hashes; same-input JSON/crop reruns were byte-identical; `git diff --check` and `py_compile` passed. E-27 and N-07 push-workflow CI relays are pending; no Windows execution or Actions inspection is claimed. The N-07 commit is tagged `stable-n-07` after full local verification. E-28 is next, followed by E-29.

### Dispatch closeout — E-03-kit-v3 and E-15–E-18 (2026-10-24)

This dated closeout supersedes earlier status snapshots below wherever they conflict. All listed changes were made serially on `arena/9dc17500-kandoo-digital-invoice`; `main` was not changed, PR #11 remains open, and frozen E-11 files under `contracts/` remain untouched.

| Task | Commit SHA | Annotated tag | Verified output |
|---|---|---|---|
| E-03-kit-v3 | `84c4c92872b838ecc5bc6a3cbf3c98a7cc206078` | `stable-e-03-kit-v3` | Checker passed; combined v2/v3 regression tests: 9 passed, 4 subtests. V2 files were not changed. |
| E-15 | `261817e17ed5b3fd1aca3d5d5712bb1dd78069df` | `stable-e-15` | `deliveries/e15-robustness/report.md`: 28 deterministic perturbation runs; final E-06 verdicts 14 REVIEW / 14 REJECT, zero ACCEPT, and zero EXTRACTED-but-wrong. Each of seven perturbation types was fail-closed in 4/4 runs. The report also discloses upstream E-02 AUTO_CANDIDATE results for some small shifts, blur, and noise. |
| E-16 | `62d439092bf10c5581b65c7fa9d74a604473817c` | `stable-e-16` | Four Draft 2020-12 schemas, docs, generated golden examples and reproducibility tests; targeted tests: 4 passed. |
| E-17 | `fd1c8461a7544c067a99905839944b807f5e4de6` | `stable-e-17` | Ubuntu GitHub Actions matrix for Python 3.11/3.12; no Tesseract installation or requirement on the Glyph path. Local Python 3.11 suite: 1,898 passed, 82 subtests. |
| E-18 | recorded in the commit carrying this handoff update | `stable-e-18` | Handoff records the owner/verifier's CI relay below. |

**Owner/verifier CI relay — GREEN (reported 2026-10-24; independently verified on GitHub by the owner/verifier):** E-17 workflow “ci: add Python 3.11 and 3.12 test matrix” at `fd1c846` succeeded on Ubuntu for Python 3.11 and 3.12. The PR #11 smoke workflow run was green and PR #11 remained open. E-15 and E-16 predate the workflow; the successful E-17 workflow run covers their cumulative repository state. The owner/verifier also relayed the sandbox suite result of 1,898 passed plus 82 subtests. The agent did not inspect GitHub Actions results; this paragraph records the owner's relay.

The E-03-kit-v3 report explicitly limits its claim: no actual Holo/Windows print, KandooPrintProbe spool capture, or SPL-to-PNG conversion was performed in Arena. No physical print-capture verification is claimed. The E-16 schemas and examples are separate from the frozen `contracts/` package.

**Sequence status:** E-03-kit-v3, E-15, E-16, E-17, and E-18 are complete. PR #11 remains open; no merge or `main` change is authorized by this closeout. Any future physical Holo/Windows print-and-capture validation requires owner-provided Windows evidence and is outside the completed Arena checks.

### E-03-kit-v1 — archived and obsolete (2026-10-23)

- The original files `docs/E-03-kit-inventory.md`, `docs/E-03-kit-guide-fa.md`, and `docs/E-03-kit-checklist.md` are preserved for audit history. Each now begins with: “Kit v1 is OBSOLETE per Director, do not use.”
- V1's incorrect print source, phone-scanned capture, assumed unit-price column, and incomplete digit coverage are the reasons it must not be used. The old workflow is not a source of instructions for v2.
- The PM's earlier authorization to use the existing operator-confirmed `labels.json` for E-04.5/E-05 remains historical and separate from the v2 print evidence.

### E-03-kit-v2 — active print-extraction kit (2026-10-24)

- `docs/E-03-kit-v2/` contains exactly three learning pages and one exam page, a README coverage matrix, and an `expected-values.json` limited to quantities, line totals, and invoice-level payable. No unit-price field/value is assumed.
- Combined controlled-value coverage is `۰` 10, `۱` 14, `۲` 23, `۳` 9, `۴` 12, `۵` 11, `۶` 20, `۷` 6, `۸` 8, `۹` 7, comma 20; all meet the minimum of five. Every page also preserves ASM-39's per-page Persian `۲`/`۶` coverage.
- The owner-confirmed safety decision is fabricated Hello data only: no real customer, sale, or stock movement; nothing to cancel, delete, or roll back; the print job is the test artifact and the fake invoice may be discarded.
- Required capture is an actual Hello Windows print job captured by KandooPrintProbe as SPL, converted to PNG for downstream OCR/extraction, and accompanied by `Report.txt` identifying printer, spool job ID, timestamp, and page count. Phone scans and word-processor prints are prohibited. Arena has no Windows printer/Hello job, so no actual SPL capture or conversion is claimed; owner verification remains pending.
- `scripts/verify_e03_kit_v2.py` checks page-file count, page/answer-key consistency, arithmetic, glyph coverage, and README matrix; optional capture mode checks only file/metadata shape, not Hello origin or conversion correctness. Local verification passed: the checker reported all eleven glyph counts at or above five, the focused unittest suite passed (5 tests), `py_compile` passed, and `git diff --check` passed. Capture mode was not run because no actual owner Windows capture exists in Arena. Focused tests are in `tests/test_e03_kit_v2.py`.

### E-08 — new-layout review flow (2026-10-24)

- E-08 was committed as `d70fb3778b6f69de23740ec9f16cbb4ac221445b`; `stable-e-08` was pushed and verified at that commit before E-03-kit-v2 began.

### E-04.5 + E-05 — Label-derived fixtures and template bank (2026-10-23)

- PM authorized synthesis of four strict Canonical Invoice v0 fixtures from operator-confirmed `tests/fixtures/real/labels.json`. Files 29/31/32 are `EXTRACTED` fixture projections of E-07 `AUTO_CANDIDATE`; 33 is `DRAFT` because E-07 returned `REVIEW`. None is pipeline-emitted, `VALIDATED`, or `ISSUED`.
- `tests/fixtures/real/canonical/README.md` and `synthesis-manifest.json` identify `synthesized_from_labels: true`, source hashes, synthetic context fields, and statuses. Label quantities/totals remain integer v0 values; unit prices/subtotals are derived as documented. No extra Canonical property was added.
- `src/e05_template_bank/` builds a serializable geometry/numeric-format bank using label measurements and schema-validated canonical pairs. It performs no OCR. Four training observations cluster into one layout template; scores are advisory and resubstitution only.
- Validation: E-05 tests 9 passed; existing Canonical Invoice v0 tests 42 passed plus 39 subtests; `compileall` and `git diff --check` passed. Pytest/jsonschema were installed in a temporary `/tmp` virtual environment and were not added as repository dependencies.
- No E-03 kit capture was used for E-04.5/E-05. The old v1 six-phone-scan plan is now obsolete and must not be produced; the four v2 Hello SPL→PNG captures remain future owner-provided evidence. No OCR or image-extraction pipeline was run for E-04.5/E-05. E-05 was committed as `66b4274597471a2837b79f3019f03d13c8ff00e0`, pushed to the fixed branch, and tagged `stable-e-05`; remote branch/tag verification passed. Do not merge or create another PR. Existing PR #11 remains open; no PR action was performed.

### E-06 — Onboarding verdict (2026-10-23)

- Part A is documented in `docs/E-06-onboarding-verdict.md`; decisions ASM-35 through ASM-40 are in `docs/DECISIONS.md`. The policy is fail-closed: confidence `>=0.95` only advances to later gates, `[0.80, 0.95)` is REVIEW, `<0.80` is REJECT; N=4 warm-up, locked bank, D14 signed agreement, kit-only digit coverage, exact numeric checks, and audited store-owner verification gate ACCEPT.
- Part B is in `src/e06_onboarding_verdict/` with E-05-backed scoring, stable reason enums, configurable thresholds, and tests. Canonical-derived label fixtures are not used as kit scans; bad/partial fixtures are synthetic test-only, and bad fixture provenance is recorded by sidecar.
- Final verification: E-06 suite 18 passed; E-05 suite 9 passed; Canonical Invoice v0 suite 42 passed plus 39 subtests; `py_compile` and `git diff --check` passed. `TemplateMatch.to_dict()` compatibility is asserted through `VerdictResult.to_dict()`.
- E-06 is complete at commit `91f5b04`; the local `stable-e-06` tag is present. It is not pending. Work continues only on `arena/9dc17500-kandoo-digital-invoice`; do not merge, force-push, create, or otherwise manage a PR. Existing PR #11 remains open and untouched.

WP-05 was verified on 2026-10-15; WP-09 and WP-10 verification was added on 2026-10-16 below.

- Work is on the Arena-fixed branch `arena/9dc17500-kandoo-digital-invoice`. `HOLOO-IMAGE-EXTRACTION-05` started from commit `395443ebdc3843767a526151f403170266fd3fbf`; no other branch was used and `main` was not changed.
- Native Checkout PO decisions remain recorded in `specs/native-checkout-contract-proposal.md`: Q1=Option 1, Q2=Option 2, Q3=Option 1, Q4=Option 1. Per PO direction this is future architecture, not current MVP priority; no Native Checkout code was added.
- `WP-HOLOO-IMAGE-EXTRACTION-02 — Persian OCR Support` is implemented in the experimental `src/image_extraction_adapter/` on top of the existing Tesseract/image-to-issuance path. `fas+eng` is configured, Persian/Arabic digits and separators and bidi controls are normalized, and the parser supports the tested Persian labels and line blocks. The original image extraction is preflighted against expected synthetic values before the existing `IssuanceService` is called.
- The current spatial-backend regression on the explicitly Synthetic Persian PNG used Tesseract 5.5.1 with `fas+eng`: 47 word scores, mean 91.47784295744681, minimum 65.31218. Declared values matched and the smoke reached `ISSUED`; its complete output is `deliveries/image-extraction-ocr/synthetic-spatial-regression-fa.log`. The fixture SHA-256 remains `df0e79c5acef87a6f2bcd3c9d36c6afadfb612a7210afadc0ea717c08856d782`. Earlier pre-spatial output is retained in `synthetic-persian-ocr-e2e.log`.
- The existing pipeline completed for the synthetic fixture: 4 configured validations `VALID`, domain `VALID/CLEAR`, canonicalization `ACCEPTED`, 2 canonical lines, and lifecycle `DRAFT → EXTRACTED → VALIDATED → ISSUED`; final Digital Invoice was verified with a 24-link trace. Evidence and IDs are in the retained smoke log and `deliveries/image-extraction-ocr/synthetic-digital-invoice-evidence.md`.
- A confidence threshold of 70 returned adapter-local `REVIEW_REQUIRED` at measured minimum 65; issuance was not called and no Digital Invoice was created. This is not a persisted P5.2 ReviewQueue record: Frozen contracts do not carry OCR confidence.
- Persian `fas` and English `eng` traineddata were successfully installed and exercised from `/tmp/kandoo-ocr-runtime`; model provenance and SHA-256 checksums are in the evidence document. Optional OCR/test packages and model binaries are not committed.
- `HOLOO-EXTRACTION-CONTINUATION-01` adds level-5 TSV word boxes and a right-to-left spatial fallback in `src/image_extraction_adapter/`. On the user-supplied cleaned image `deliveries/image-extraction-ocr/holo_row_detection.png`, it found four ordered table rows and assigned description/quantity/amount columns without visible row transposition. It preserved OCR strings and marked ambiguous or missing values `REVIEW`; report: `deliveries/image-extraction-ocr/real-holoo-spatial-evidence.md`.
- A `submit_image()` run used a counting wrapper around the real `IssuanceService`: `IssuanceService.submit` calls = 0 and no Digital Invoice was issued. This remains an adapter-local hold, not a persisted P5.2 review record.
- `WP-HOLOO-IMAGE-EXTRACTION-05 — OCR Preprocessing & Cell Isolation` crops row amounts, quantities, descriptions, and a detected payable box using TSV-derived geometry. Pillow implements Otsu/adaptive thresholding plus directional morphological line removal; numeric crops use PSM 7 and whitelist `0123456789۰۱۲۳۴۵۶۷۸۹.,`, while descriptions have no numeric whitelist. All three cell modes are returned as supplementary variants; they never overwrite the original fields.
- Real-image comparison: Otsu and adaptive tied at 4/9 exact digit-cell matches (55.56% exact-cell error, 56.76% digit CER); the unthresholded cell crop achieved 1/9 (88.89% error, 67.57% CER). The full-page baseline had 0/9 exact matches but a lower CER (54.05%). None of the five monetary cells matched the provisional manual visual reference in any cell mode. No numeric output was accepted; all remain `REVIEW`. Details: `deliveries/image-extraction-ocr/cell-preprocessing-comparison.md` and `.log`.
- The `submit_image()` preprocessing guard run returned `ImageExtractionReviewRequired`; the real-service spy counted 0 submit calls and no Digital Invoice was created. Evidence: `cell-preprocessing-issuance-guard.log`.
- The one-image scoring reference is a manual visual transcription not confirmed by the invoice owner; metrics are exploratory and do not establish general Holoo accuracy. The source image remains unchanged and Frozen contracts D-01–D-09 were not changed.
- Spatial/cell OCR uses `tesserocr.GetTSVText(0)`, which supplies equivalent level-5 text/confidence/box fields. `pytesseract` and the native Tesseract CLI were unavailable in this runtime; neither is claimed as used. Pillow 11.3.0, Tesseract 5.5.1, `tesserocr` 2.11.0, and `fas+eng` traineddata were supplied from `/tmp/kandoo-ocr-runtime`, not committed.
- Focused image-adapter/preprocessing tests passed (18); the full repository suite passed (1,712). Current English and Persian smoke regressions passed on explicitly Synthetic fixtures; those results are not Holoo validation.

### WP-HOLOO-IMAGE-EXTRACTION-09 — Dynamic Layout Detector (2026-10-16)

- `preprocessing.py` now uses Pillow image projection as the primary `crop_spatial_cells` geometry source. Horizontal and vertical candidates are contiguous black runs at least 80% of the axis maximum. The longest median-spaced horizontal chain identifies the grid; a shorter header interval is excluded, median row height filters rounded-payable borders, and vertical rules are projected only across the table span. TSV geometry is retained only as a compatibility fallback when projection is incomplete.
- `deliveries/image-extraction-ocr/dynamic-layout-projection.log` reports successful geometry and cell crops for all supplied images: `holo_row_detection.png` 4 rows/5 vertical boundaries/12 cells; `5.png` 5/5/15; `13.png` 13/5/39. These are the only three real layouts tested; this does not prove general invoice-layout accuracy.
- Glyph build used all three receipts. The row template profile contains all ten Persian digits plus comma. The evaluation is a row-disjoint split within the same 13-row invoice: source rows 3–8 train from a separate crop; rows 0–2 and 9–12 plus payable are scored from the full image. It is not independent-invoice validation. The visual labels are provisional and not confirmed by the invoice owner.
- The prior Adapter spatial geometry produced payable bbox `(199, 1431, 147, 28)` for `13.png`; its raw payable is `۳۴۷,۹۲۰,۰۰۰`. The Glyph evaluation's payable result did not match and remains `REVIEW`.
- 13-row Glyph evaluation: `exact_digit_cells=12/15`; 12 of 27 returned numeric cells were `EXTRACTED`, 15 were `REVIEW`; zero extracted values were wrong against the available visual labels. Arithmetic Gate failed because line 9 total was malformed (`??۹,۶۰۰,۰۰۰`); all amount cells remained REVIEW. Output: `deliveries/image-extraction-ocr/glyph-classifier-evaluate-13row-3invoice-build.log`.
- Focused image-adapter suite: 21 passed plus 6 subtests. Full repository suite: 1,715 passed plus 6 subtests. At WP-09 completion, `glyph_classifier.py` was not yet connected to `adapter.py`; WP-10 subsequently authorized and implemented that integration. Pillow, tesserocr, and pytest used for this run were installed only under `/tmp/kandoo-glyph-runtime`.

### WP-HOLOO-IMAGE-EXTRACTION-10 — Glyph Integration & E2E (2026-10-16)

- `ImageExtractionAdapter` accepts an explicit numeric-cell backend; `GlyphClassifierOCR` is now the primary numeric-cell engine while Tesseract remains the full-page text/layout backend. Any numeric cell with status other than `EXTRACTED`, missing numeric coverage, disagreement with parsed values, or a backend failure holds the whole page as `ImageExtractionReviewRequired`.
- The accepted Glyph variants are carried on `ImageExtractionReady`, and `submit_extraction()` rechecks the evidence when Glyph is configured so a ready result without valid numeric evidence cannot bypass the gate. Frozen contracts D-01–D-09 were unchanged.
- Guarded E2E on `deliveries/image-extraction-ocr/13.png` used `src/templates.json` and detected 13 rows/27 numeric cells: 12 EXTRACTED, 15 REVIEW. The arithmetic gate failed on malformed `line.9.total` (`??۹,۶۰۰,۰۰۰`); the payable was also malformed. The adapter returned `ImageExtractionReviewRequired`.
- E2E passed its fail-closed check: `NonIssuingSubmitProbe` call count was zero. The real `IssuanceService` was not attached to this guarded real-image run; no Digital Invoice was created and no `ISSUED` state was reached. Do not describe this as a production accuracy result or as an actual invoice issuance-service run.
- Full log and report: `deliveries/image-extraction-ocr/wp-holoo-image-extraction-10-e2e.log` and `deliveries/image-extraction-ocr/wp-holoo-image-extraction-10-report.md`. Focused image-adapter suite: 25 passed; full repository suite: 1,719 passed plus 6 subtests.

## EOD Status [2026-10-16]

- **WP-09 (Dynamic Layout):** Successfully implemented and pushed as `e5ff46d`. Dynamic projection detected the supplied 4-, 5-, and 13-row layouts and their table columns. These are three tested layouts, not proof of general layout accuracy.
- **WP-10 (Integration & E2E):** Glyph was integrated into the adapter as the primary numeric-cell engine and the 13-row image was run with the Glyph templates/runtime assets. The arithmetic gate failed, so the adapter returned page-level `ImageExtractionReviewRequired`; the non-issuing submit probe recorded zero calls. The actual issuance service was not attached, so no Digital Invoice could be created and none reached `ISSUED`. Commit: `76a37f0`.
- The E2E demonstrates the extraction/review fail-closed path, not production OCR accuracy or owner-confirmed values. WP-09 labels/references remain provisional and the row-level train/evaluation split is within the same invoice, not independent-invoice validation. This adapter-local hold is not a persisted Frozen P5.2 review record; D-01–D-09 remain unchanged.
- **Priority for tomorrow:** Discuss the Windows App interface and the Per-Store Calibration process (clustering and operator labeling). The MVP technical control path for dynamic layout plus fail-closed numeric review has been demonstrated; production OCR accuracy/calibration is not yet proven. Keep Synthetic results separate from Holoo evidence.

## 7. Current Agent Ownership

- **Serial closeout state:** N-04, N-05, E-24, and N-06 are complete; E-25 closes this task window in the current documentation commit group. Preserve the stated fixture/layout/currency boundaries. N-01 and N-04 evaluation references remain provisional and owner-unconfirmed.
- **Historical image-extraction work:** `WP-HOLOO-IMAGE-EXTRACTION-02` synthetic Persian support remains complete. `HOLOO-EXTRACTION-CONTINUATION-01` provides spatial OCR; `WP-HOLOO-IMAGE-EXTRACTION-05` adds cell preprocessing; `WP-HOLOO-IMAGE-EXTRACTION-09` adds dynamic projection layout; `WP-HOLOO-IMAGE-EXTRACTION-10` integrates Glyph as the primary numeric-cell backend with a page-level fail-closed review gate. The guarded 13-row E2E returned REVIEW and recorded zero submit-probe calls; real issuance was not attached and no invoice issued. OCR accuracy remains unproven and visual labels are provisional.
- **Product Owner:** Native Checkout Q1–Q4 decisions are recorded; any later change to those decisions or MVP priority remains a PO decision.
- **WP-11.2 Holoo DB adapter:** remains a separate deferred scope; the image-extraction adapter does not resolve its source mapping/authority/synchronization decisions.
- Preserve unrelated work already present in the working tree; do not absorb the untracked spooler adapter or runner into this image-extraction change.

## 8. Current Real Boundaries

1. The 13-row target `deliveries/image-extraction-ocr/13.png` was processed through full-page Tesseract plus Glyph numeric-cell OCR. Dynamic crop geometry returned 13 rows and 27 numeric cells (12 EXTRACTED, 15 REVIEW); all 13 totals and payable remain REVIEW after the arithmetic gate failed on malformed `line.9.total`. This does not establish general Holoo accuracy or suitability across layouts.
2. The guarded E2E adapter outcome was `ImageExtractionReviewRequired`; `NonIssuingSubmitProbe` recorded zero calls. The real `IssuanceService` was not attached to this run, so no Digital Invoice was created or reached `ISSUED`. This is an adapter-local hold, not a persistent Frozen `REVIEW` state or P5.2 ReviewQueue record.
3. WP-09 visual labels and references are provisional and unconfirmed by the invoice owner. The 13-row train/evaluation split is by rows from the same invoice, not independent-invoice validation. Do not use these results to auto-correct values or claim general accuracy.
4. Synthetic English and Persian smokes reached `ISSUED` through the existing pipeline, but this is Synthetic evidence only. Threshold 60 is a test setting, not a production recommendation; confidence is not calibrated.
5. The flat text parser handles tested English/Persian labels. The dynamic projection detector recovered four-column RTL tables in the three supplied images (4, 5, and 13 rows); it has not been validated on other layouts. Projection is primary for crops, with TSV geometry fallback. Ambiguous values remain REVIEW. Jalali-to-Gregorian calendar conversion is not implemented.
6. Native Checkout is future architecture only under the recorded Q1–Q4 choices; it is not the current MVP priority and no Native Checkout code was added.
7. WP-11.2 (Holoo database adapter/enrichment) remains separate and deferred pending its own decisions/evidence.

## 9. Repository and EOD Branch Status

All task-scoped image-extraction source, tests, Synthetic regression evidence, real-image spatial/preprocessing/Glyph reports, and handoff updates stay on `arena/9dc17500-kandoo-digital-invoice`. WP-05 was pushed as `fbfe7c0`; remote upload commit `ccb9e99` added the supplied `5.png` and `13.png` images before WP-09 work. WP-09 was pushed as `e5ff46d`; WP-10 was pushed as `76a37f0`. No change is to be merged to `main`. Earlier untracked WP-06 classifier artifacts and the unrelated spooler adapter/runner are intentionally left out of task commits. Do not force-push or overwrite remote work if a future non-fast-forward condition occurs; report that blocker instead.

## 10. Handoff Protocol

Every agent joining this project must:

1. Read this file completely.
2. Inspect current Git HEAD and working tree.
3. Read authoritative registers/specs.
4. Read `KANDO_AGENT_COORDINATION.md` for current WP ownership/status. `KANDOO_AGENT_COORDINATION.md` is legacy repository-bootstrap context, not the current image-extraction status.
5. Identify active WP ownership before editing anything.
6. Work only inside its assigned ownership boundary.
7. Run required tests/regression/smoke.
8. Commit.
9. Update this handoff and coordination state.
10. Report exact commit, tests, blockers and next executable work.

Never infer missing technical contracts from this handoff when an authoritative spec/register is available.
