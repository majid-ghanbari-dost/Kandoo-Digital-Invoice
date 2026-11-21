# E-22 — Python-only handoff

- **Status:** E-19, E-20, and E-21 complete. This file is the E-22 handoff deliverable.
- **Scope:** Python-only; C# remained untouched.
- **Evidence boundary:** E-20/E-21 are synthetic mechanics and safety tests only. They are not Holo captures, physical printer captures, or evidence about real stores.

## Commit and tag map

| Task | Commit SHA | Annotated tag | Summary |
|---|---|---|---|
| E-19 | `3935d345d310825bd4590076b6ddd06bae908080` | `stable-e-19` | Native Windows one-folder build, frozen CLI verifier, and evidence report. |
| E-20 | `79ca861c0a93ac5598f76ffbfb40f71dd78fbac6` | `stable-e-20` | Alternate installed-font synthetic second-store mechanics test. |
| E-21 | `948caf86bbcd73c7657cbe058a671c63eb1404b2` | `stable-e-21` | Synthetic unknown-layout fail-closed variants. |
| E-22 | This handoff commit | `stable-e-22` | Handoff report; tag points to the commit containing this file. |

All task commits are on `arena/9dc17500-kandoo-digital-invoice`. No force-push was used.

## CI results

### E-19

- Windows one-folder build: [run 40176728562 — success](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40176728562), on `3935d345d310825bd4590076b6ddd06bae908080`.
- Ubuntu Python tests: [run 40176728571 — success](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40176728571), on the same SHA.
- The workflow did not install Tesseract; the frozen Glyph CLI path and fixture checks passed.

### E-20

- Python workflow: [push run 40177772007 — success](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40177772007), on `79ca861c0a93ac5598f76ffbfb40f71dd78fbac6`. The E-20 synthetic job, both Python matrix jobs, and evidence upload passed.
- Windows workflow: [push run 40177772049 — success](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40177772049), on the same SHA.
- PR checks also passed: [Python 40177775048](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40177775048) and [Windows 40177775043](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40177775043).
- The CI E-20 step passed its fail-closed installed-font/glyph-mask check and uploaded `e20-synthetic-40177772007` (14-day artifact). The artifact and run-log download endpoints returned EOF in this sandbox, so the exact CI font/path could not be independently inspected. The committed local report records DejaVu Sans Mono Book; no font fallback or installation was used by the runner.

### E-21

- Python workflow: [push run 40178252987 — success](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40178252987), on `948caf86bbcd73c7657cbe058a671c63eb1404b2`. E-20, E-21, Python 3.11/3.12, and both synthetic evidence uploads passed.
- Windows workflow: [push run 40178252970 — success](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40178252970), on the same SHA.
- PR checks also passed: [Python 40178256030](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40178256030) and [Windows 40178255926](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40178255926).
- Uploaded artifacts: `e20-synthetic-40178252987` and `e21-synthetic-40178252987`, each with 14-day retention. E-21's CI job explicitly depends on the E-20 job.

## E-20 synthetic results

Detailed records: [`docs/e20-second-store.md`](e20-second-store.md) and [`docs/e20-second-store.json`](e20-second-store.json).

- The installed **DejaVu Sans Mono Book** font passed nonempty/distinct-mask checks for Persian digits `۰–۹` and comma in the local runner; the test renders at 576 pixels, 1-bit, with a grayscale threshold of 180. CI independently passed the same no-substitution gate.
- Three synthetic learning pages built one E-05 layout cluster and 27/27 labeled Glyph numeric crops. E-05's held-out exam reference match was 0.999 (answer-key numeric labels were used for this reference match; it is not an OCR result).
- E-03 v3 learning values covered all controlled symbols; no exam symbols were absent from the learning values. E-02 row templates covered all exam symbols. The separate payable-only profile lacks `۱`, `۳`, and `۸`; the existing pipeline uses row templates for payable cells by default.
- The exam image passed layout detection, then E-02 returned REVIEW: 3 correct EXTRACTED, 6 REVIEW, 0 EXTRACTED-but-wrong. The arithmetic gate failed on unreadable cells, and no Canonical Invoice candidate was emitted. E-06 returned REVIEW (`PARTIAL_MATCH`) on the absent candidate. No thresholds were tuned.

## E-21 synthetic results

Detailed records: [`docs/e21-unknown-layout.md`](e21-unknown-layout.md) and [`docs/e21-unknown-layout.json`](e21-unknown-layout.json).

Each row is one synthetic page, so the per-variant safe-route rate is 1/1 (100%); these are mechanics checks, not statistical estimates.

| Variant | Final E-21 route | E-02 result | EXTRACTED-but-wrong | Reason |
|---|---|---|---:|---|
| Swapped columns | REVIEW | REVIEW | 0 | Required numeric fields remained unresolved; no candidate emitted. |
| No vertical rules | BLOCKED | REJECT / layout BLOCKED | 0 | No table geometry was detected. |
| Three columns | BLOCKED | REJECT / layout BLOCKED | 0 | No table geometry was detected. |
| Extra column | BLOCKED | REJECT / layout BLOCKED | 0 | No table geometry was detected. |
| Different table position | REVIEW | REVIEW | 0 | Required numeric fields remained unresolved; E-05 reference score 0.635 was unmatched. |

Overall: 5/5 variants ended REVIEW or BLOCKED with a reason; EXTRACTED-but-wrong cells: 0; wrong Canonical candidates: 0; thresholds tuned: no.

## Repository and PR state

- PR #11 remains **open**, from `arena/9dc17500-kandoo-digital-invoice` into `main`.
- `main` remains at baseline `15901d6c88344c7f5e39471130d60c4dd5658b83`.
- The changes since the E-19 commit did not modify `contracts/` or any C# files. The prior frozen contract tag `stable-e-11` was not force-updated; `stable-e-03-kit-v2` was not changed, and `stable-e-03-kit-v3` remains the active kit.
- No physical print, Windows spool capture, KandooPrintProbe capture, or real-store generalization claim was made.
