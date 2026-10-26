# N-04 — Optional ParisaOCR name suggestions

**Disposition:** complete as an optional prototype. Keep name suggestions off the default path; if enabled, use them only as human-reviewed suggestions. Never auto-accept a recognized name.

## Behavior and boundary

- `scripts/n04_name_suggestions.py` extends every N-02 candidate with a `name_suggestions` array. When the optional engine is disabled, every array is empty and the document reports `name_suggestions_enabled: false`.
- Enabled suggestions carry the joined display string, the original ordered `lines` array, engine and version, model version, engine confidence summary on the 0–100 scale (mean of available line scores, rounded to four decimals), a crop ID/path/SHA-256 reference, and `accepted: false`. Newlines are preserved, so two-line product names are represented as two lines rather than flattened or silently discarded.
- The enrichment is versioned as `n04.product-candidates-with-name-suggestions.v1`; it validates the N-02 source version and refuses to overwrite pre-existing suggestion records. It remains in optional `scripts/` tooling and does not modify the frozen `contracts/` package or `adapter.py`.
- Confidence is the engine's diagnostic scale, not a calibrated probability or an acceptance threshold. Evaluation references are provisional and owner-unconfirmed; this report makes no accuracy claim.
- ParisaOCR 0.7.2 imports POSIX-only `resource` from a PDF helper even when the image-line API is used. On Windows, a narrowly scoped temporary import shim satisfies that import; its `setrlimit` stub raises explicitly if the unsupported PDF memory-limit call is attempted. The crop-only image path does not invoke that PDF code. Windows PDF support is not claimed.

## Windows-latest measurement

The native Windows Actions benchmark was run at [Windows one-folder workflow run 40311286720](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40311286720), source commit `3d9d28b00acbf0f1944024d5530a4922f15b16e9`. It used `windows-latest` image `win25-vs2026` (`20261021.278.1`), Python `3.11.9`, CPU-only inference, one PyTorch thread, and 22 reference crops produced from real fixtures 29, 31, 32, and 33. The pinned requirements file SHA-256 is `82324907059f1d5300e882f0ce3ed96db7246c01a0941d3cb86383320bf5e319`.

The run identified ParisaOCR `0.7.2`, model `parisaocr-fa-0.1`, PyTorch `2.14.0+cpu`, and no model/network downloads during inference. Model files observed in the wheel/runtime:

| File | Bytes | SHA-256 |
|---|---:|---|
| `parisaocr-fa-0.1.safetensors` | 12,338,980 | `cf41676c0cf590cd0a01ebb342faf1ce72c42e19a213984cbad6e5ddc91ae265` |
| `ppocrv6-det-small.onnx` | 9,929,594 | `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f` |

### Raw aggregate measurements

| Measurement | Raw result | Definition / caveat |
|---|---:|---|
| Installed size delta | 1,389,385,292 bytes = 1,325.021069 MiB = 1.293966 GiB | Before/after logical file-byte delta in an isolated venv's `site-packages`; not the downloaded-wheel total or a PyInstaller bundle size. |
| ParisaOCR / Torch import + CPU reader/model initialization | 5.098956 s | In-process cold initialization including both locally bundled models; not a new executable launch. |
| First crop inference | 1.3804952 s | Includes first-use effects. |
| Per-crop inference, minimum | 0.7513097 s | Across the 22 measured crops, including the first. |
| Per-crop inference, median | 0.79438605 s | Across the same 22 crops. |
| Per-crop inference, p95 | 1.3860779 s | Nearest-rank p95 across the same 22 crops. |
| Per-crop inference, maximum | 1.3948378 s | Across the same 22 crops. |
| Peak resident working set | 798,072,832 bytes = 761.101563 MiB | Windows `PeakWorkingSetSize` for the benchmark Python process; includes runtime, dependencies, and loaded models. |

### Per-crop raw timings

Confidence is ParisaOCR’s mean line score on the 0–100 scale, rounded to four decimals; it is shown only as a diagnostic output and is not calibrated. Crop IDs and numbers below are taken from the benchmark's structured Actions annotation; the uploaded artifact contains the corresponding JSON/Markdown report.

| Crop ID | Seconds | Recognized lines | Confidence (0–100, diagnostic only) |
|---|---:|---:|---:|
| `33_row11` | 1.3804952 | 1 | 99.8 |
| `33_row4` | 0.7870191 | 1 | 99.9 |
| `33_row0` | 0.8828899 | 1 | 99.7 |
| `33_row9` | 0.7941511 | 1 | 100.0 |
| `33_row7` | 0.7708397 | 1 | 99.0 |
| `33_row8` | 0.9884764 | 1 | 99.9 |
| `32_row1` | 0.7548679 | 1 | 100.0 |
| `33_row12` | 0.7985564 | 1 | 100.0 |
| `31_row2` | 0.7728057 | 1 | 99.8 |
| `29_row1` | 0.7868669 | 1 | 100.0 |
| `31_row0` | 0.8036345 | 1 | 100.0 |
| `31_row1` | 0.7691161 | 1 | 99.9 |
| `29_row2` | 0.7946210 | 1 | 99.8 |
| `33_row2` | 0.7595910 | 1 | 99.6 |
| `33_row5` | 0.7704598 | 1 | 98.4 |
| `33_row10` | 1.3948378 | 2 | 98.65 |
| `29_row0` | 0.7955969 | 1 | 99.8 |
| `33_row6` | 1.3860779 | 2 | 99.25 |
| `29_row3` | 0.7982087 | 1 | 99.8 |
| `33_row3` | 0.8486782 | 1 | 99.8 |
| `32_row4` | 0.7791283 | 1 | 100.0 |
| `32_row2` | 0.7513097 | 1 | 100.0 |

## Comparison with the E-19 no-OCR build

The E-19 reference is the passing no-OCR Windows artifact [run 40176606025](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40176606025), documented in [`docs/windows-build.md`](windows-build.md). The current N-04 workflow's separate, OCR-free one-folder job also passed on run 40311286720.

| No-OCR Windows package measurement | E-19 recorded run 40176606025 | Current OCR-free job in run 40311286720 |
|---|---:|---:|
| Executable | 3,671,939 bytes (3.502 MiB) | 3,671,939 bytes (3.502 MiB) |
| Expanded one-folder directory | 34,117,267 bytes (32.537 MiB) | 34,117,267 bytes (32.537 MiB) |
| Compressed Actions artifact | 16,949,333 bytes (16.164 MiB) | 16,948,878 bytes (16.164 MiB) |
| Fresh `extract --help` process timing | min 0.1604 / median 0.1749 / max 0.1927 s | min 0.1618 / median 0.1645 / max 0.2078 s |
| OCR runtime included | No | No |

The optional N-04 venv delta of 1,325.021 MiB is about 40.7 times the 32.537 MiB expanded E-19 directory, but these are **different measurement boundaries** (installed Python `site-packages` versus a frozen one-folder directory). N-04 did not build a PyInstaller bundle containing PyTorch/ParisaOCR, so a shipped N-04 bundle size is unknown. The E-19 runs do not provide a comparable peak-memory measurement. The 5.099 s model initialization is also not directly comparable to the E-19 fresh-process `--help` timing.

## Package, model, dependency licensing, and redistribution

### ParisaOCR wheel and bundled model notices

The inspected [PyPI release](https://pypi.org/project/parisaocr/0.7.2/) file is `parisaocr-0.7.2-py3-none-any.whl`, 23,724,727 bytes (22.625663 MiB), SHA-256 `5a7ce373784f3c549d8c38bf24a82f161d9845c23a922b1baacf142e6128f6db`. Its actual wheel `METADATA` declares `License-Expression: Apache-2.0` and includes `LICENSE` and `NOTICE`; it does not include a separate `MODEL_CARD.md`. The model-card excerpts below come from the pinned upstream source revision.

Verbatim excerpts from that wheel's `NOTICE`:

> “This product is licensed under the Apache License, Version 2.0 (see LICENSE).”
>
> “`parisaocr/models/ppocrv6-det-small.onnx`: the PP-OCRv6 small text detection model of PaddleOCR (https://github.com/PaddlePaddle/PaddleOCR), Copyright PaddlePaddle Authors, licensed under the Apache License, Version 2.0, in the ONNX conversion distributed by RapidOCR (https://github.com/RapidAI/RapidOCR), also under the Apache License, Version 2.0.”
>
> “`parisaocr/models/parisaocr-fa-0.1.safetensors`: a text recognition model trained with Kraken (https://github.com/mittagessen/kraken, Apache License, Version 2.0). See MODEL_CARD.md for its training data, including synthetic lines rendered from Persian and English Wikipedia text (CC BY-SA 4.0).”
>
> “`parisaocr/fonts/Vazirmatn-*.ttf`: the Vazirmatn font, Regular and Bold (https://github.com/rastikerdar/vazirmatn), Copyright 2015 The Vazirmatn Project Authors, licensed under the SIL Open Font License 1.1 (parisaocr/fonts/OFL-Vazirmatn.txt). It is embedded, subset, in the invisible text layer of the searchable PDFs ParisaOCR writes, and whole in the EPUB books it writes, under the same license.”

The wheel's Apache `LICENSE` grants, in §2, “a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce, prepare Derivative Works of, publicly display, publicly perform, sublicense, and distribute” the work, subject to the license. Section 4 requires, among other things, a copy of the license, notices for changed files, preservation of relevant notices, and inclusion of readable attributions from a distributed `NOTICE` file.

The upstream [`MODEL_CARD.md` at source revision `210dc627d1531a5838b2cfec9c35677c55c37df3`](https://github.com/givia/ParisaOCR/blob/210dc627d1531a5838b2cfec9c35677c55c37df3/MODEL_CARD.md) declares `license: apache-2.0`, but also states:

> “About 200 scanned Persian books, mostly 20th-century and modern print, from a public online collection whose copyright status varies and is unknown to us. Twelve pages per book were used. The scans, line images and labels are not redistributed; only the trained model is.”
>
> “Wikipedia text is licensed CC BY-SA 4.0.”

This preserves an important distinction: the wheel and model card declare Apache-2.0 for the package/model, while the model card itself records uncertain copyright status for scanned training sources and CC BY-SA 4.0 synthetic Wikipedia text. Apache terms permit redistribution subject to their conditions, but the declared model license alone does not resolve the documented training-data provenance question. **Do not treat this report as legal clearance. Obtain upstream clarification and legal review before commercially redistributing the model or a product bundle containing it.** The OFL font and every dependency's own terms/notice requirements also need to be carried through any distribution.

### Windows-resolved dependency metadata

The benchmark captured `pip freeze` and installed-distribution `License-Expression`, `License`, and `License ::` classifier metadata after installing the pinned requirements. It found 82 non-base-venv distributions. The table below reports the installed metadata as declared; it does not infer missing SPDX expressions. The two long raw `License` fields (`scikit-image`, `scipy`) are shown as excerpts because the diagnostic inventory caps each field at 500 characters. The full uploaded JSON artifact includes the raw resolved versions and collected metadata.

| Scope | Distribution | Resolved version | Installed metadata declaration |
|---|---|---:|---|
| Transitive | `aiohappyeyeballs` | `2.7.1` | `License`: PSF-2.0<br>`Classifier`: License :: OSI Approved :: Python Software Foundation License |
| Transitive | `aiohttp` | `3.14.5` | `License-Expression`: `Apache-2.0 AND MIT` |
| Transitive | `aiosignal` | `1.4.0` | `License`: Apache 2.0<br>`Classifier`: License :: OSI Approved :: Apache Software License |
| Transitive | `atpublic` | `9.0.0` | `License`: Apache-2.0<br>`Classifier`: License :: OSI Approved :: Apache Software License |
| Transitive | `attrs` | `26.1.0` | `License-Expression`: `MIT` |
| Transitive | `cattrs` | `26.2.1` | `License`: MIT<br>`Classifier`: License :: OSI Approved :: MIT License |
| Transitive | `certifi` | `2026.10.23` | `License`: MPL-2.0<br>`Classifier`: License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0) |
| Transitive | `charset-normalizer` | `3.5.2` | `License`: MIT |
| Transitive | `click` | `8.2.1` | `License-Expression`: `BSD-3-Clause` |
| Transitive | `cloudpickle` | `3.1.2` | `License`: BSD-3-Clause<br>`Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `colorama` | `0.4.6` | `Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `colorlog` | `6.12.0` | `License`: MIT License<br>`Classifier`: License :: OSI Approved :: MIT License |
| Transitive | `coremltools` | `9.0` | `License`: BSD |
| Transitive | `filelock` | `4.2.4` | `License-Expression`: `MIT`<br>`Classifier`: License :: OSI Approved :: MIT License |
| Transitive | `flatbuffers` | `25.12.19` | `License`: Apache 2.0<br>`Classifier`: License :: OSI Approved :: Apache Software License |
| Transitive | `flufl.lock` | `10.0.0` | `License`: Apache-2.0<br>`Classifier`: License :: OSI Approved :: Apache Software License |
| Transitive | `frozenlist` | `1.8.0` | `License`: Apache-2.0 |
| Transitive | `fsspec` | `2026.9.0` | `License-Expression`: `BSD-3-Clause` |
| Transitive | `htrmopo` | `0.6` | `License-Expression`: `Apache-2.0`<br>`Classifier`: License :: OSI Approved :: Apache Software License |
| Transitive | `idna` | `3.20` | `License-Expression`: `BSD-3-Clause` |
| Transitive | `ImageIO` | `2.38.1` | `License-Expression`: `BSD-2-Clause` |
| Transitive | `iso639-lang` | `2.6.3` | `Classifier`: License :: OSI Approved :: MIT License |
| Transitive | `Jinja2` | `3.1.6` | `Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `joblib` | `1.6.0` | `License-Expression`: `BSD-3-Clause` |
| Transitive | `jsonschema` | `4.26.0` | `License-Expression`: `MIT` |
| Transitive | `jsonschema-specifications` | `2025.9.1` | `License-Expression`: `MIT` |
| Pinned direct | `kraken` | `7.1.1` | `License-Expression`: `Apache-2.0`<br>`Classifier`: License :: OSI Approved :: Apache Software License |
| Transitive | `lazy-loader` | `0.6` | `License-Expression`: `BSD-3-Clause` |
| Transitive | `lightning` | `2.6.1` | `License`: Apache-2.0<br>`Classifier`: License :: OSI Approved :: Apache Software License |
| Transitive | `lightning-utilities` | `0.15.3` | `License`: Apache-2.0 |
| Transitive | `lxml` | `6.1.3` | `License`: BSD-3-Clause |
| Transitive | `Markdown` | `3.11.2` | `License-Expression`: `BSD-3-Clause` |
| Transitive | `markdown-it-py` | `4.2.0` | `Classifier`: License :: OSI Approved :: MIT License |
| Transitive | `MarkupSafe` | `3.0.4` | `License-Expression`: `BSD-3-Clause` |
| Transitive | `mdurl` | `0.1.2` | `Classifier`: License :: OSI Approved :: MIT License |
| Transitive | `mpmath` | `1.3.0` | `License`: BSD<br>`Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `multidict` | `7.2.1` | `License-Expression`: `Apache-2.0` |
| Transitive | `networkx` | `3.6.1` | `License-Expression`: `BSD-3-Clause` |
| Pinned direct | `numpy` | `2.4.6` | `License-Expression`: `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0` |
| Transitive | `omegaconf` | `2.4.0` | `Classifier`: License :: OSI Approved :: BSD License |
| Pinned direct | `onnxruntime` | `1.31.0` | `License`: MIT License<br>`Classifier`: License :: OSI Approved :: MIT License |
| Transitive | `opencv-python-headless` | `5.0.0.93` | `License`: Apache 2.0<br>`Classifier`: License :: OSI Approved :: Apache Software License |
| Transitive | `packaging` | `26.3` | `License-Expression`: `Apache-2.0 OR BSD-2-Clause` |
| Pinned direct | `parisaocr` | `0.7.2` | `License-Expression`: `Apache-2.0` |
| Transitive | `pikepdf` | `10.17.0` | `License-Expression`: `MPL-2.0` |
| Pinned direct | `pillow` | `13.0.0` | `License-Expression`: `MIT-CMU` |
| Transitive | `platformdirs` | `4.13.5` | `License-Expression`: `MIT`<br>`Classifier`: License :: OSI Approved :: MIT License |
| Transitive | `propcache` | `0.5.4` | `License`: Apache-2.0 |
| Transitive | `protobuf` | `7.36.2` | `License`: 3-Clause BSD License |
| Transitive | `psutil` | `7.2.2` | `License`: BSD-3-Clause |
| Transitive | `pyaml` | `26.7.0` | `License`: WTFPL<br>`Classifier`: License :: Public Domain |
| Transitive | `pyarrow` | `26.0.0` | `License-Expression`: `Apache-2.0` |
| Transitive | `pyclipper` | `1.4.0` | `License`: MIT<br>`Classifier`: License :: OSI Approved<br>`Classifier`: License :: OSI Approved :: MIT License |
| Transitive | `Pygments` | `2.21.0` | `License-Expression`: `BSD-2-Clause` |
| Transitive | `python-dateutil` | `3.0.0` | `License`: Dual License<br>`Classifier`: License :: OSI Approved :: Apache Software License<br>`Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `pytorch-lightning` | `2.6.6` | `License`: Apache-2.0<br>`Classifier`: License :: OSI Approved :: Apache Software License |
| Transitive | `PyYAML` | `6.0.3` | `License`: MIT<br>`Classifier`: License :: OSI Approved :: MIT License |
| Pinned direct | `rapidocr` | `3.10.0` | `License-Expression`: `Apache-2.0` |
| Transitive | `referencing` | `0.37.0` | `License-Expression`: `MIT` |
| Transitive | `regex` | `2026.9.29` | `License-Expression`: `Apache-2.0 AND CNRI-Python` |
| Transitive | `reportlab` | `5.1.0` | `License`: BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc.<br>`Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `requests` | `2.34.2` | `License`: Apache-2.0<br>`Classifier`: License :: OSI Approved :: Apache Software License |
| Transitive | `rich` | `14.0.0` | `License`: MIT<br>`Classifier`: License :: OSI Approved :: MIT License |
| Transitive | `rpds-py` | `2026.9.1` | `License-Expression`: `MIT` |
| Transitive | `safetensors` | `0.7.0` | `Classifier`: License :: OSI Approved :: Apache Software License |
| Transitive | `scikit-image` | `0.25.2` | `License`: Files: * Copyright: 2009-2022 the scikit-image team License: BSD-3-Clause Files: doc/source/themes/scikit-image/layout.html Copyright: 2007-2010 the Sphinx team… [excerpt; inventory field capped at 500 chars]<br>`Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `scikit-learn` | `1.7.2` | `License-Expression`: `BSD-3-Clause` |
| Pinned direct | `scipy` | `1.15.3` | `License`: Copyright (c) 2001-2002 Enthought, Inc. 2003-2024, SciPy Developers. All rights reserved. Redistribution and use in source and binary forms, with or without mod… [excerpt; inventory field capped at 500 chars]<br>`Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `shapely` | `2.1.2` | `License`: BSD 3-Clause<br>`Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `Sickle` | `0.7.0` | `License`: BSD<br>`Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `six` | `1.17.0` | `License`: MIT<br>`Classifier`: License :: OSI Approved :: MIT License |
| Transitive | `sympy` | `1.14.0` | `License`: BSD<br>`Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `threadpoolctl` | `3.6.0` | `License`: BSD-3-Clause<br>`Classifier`: License :: OSI Approved :: BSD License |
| Transitive | `tifffile` | `2026.3.3` | `License`: BSD-3-Clause |
| Pinned direct | `torch` | `2.14.0` | `License-Expression`: `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT` |
| Transitive | `torchmetrics` | `1.9.0` | `License`: Apache-2.0<br>`Classifier`: License :: OSI Approved :: Apache Software License |
| Pinned direct | `torchvision` | `0.29.1` | `License`: BSD |
| Transitive | `tqdm` | `4.70.1` | `License`: MPL-2.0 AND MIT |
| Transitive | `typing_extensions` | `4.16.0` | `License-Expression`: `PSF-2.0` |
| Transitive | `tzdata` | `2026.5` | `License`: Apache-2.0 |
| Transitive | `urllib3` | `2.8.0` | `License-Expression`: `MIT` |
| Transitive | `yarl` | `1.25.1` | `License`: Apache-2.0 |

The full resolved package/version list and package metadata were uploaded as Actions artifact `n04-name-suggestions-40311286720` (14-day retention at the time of the run); its raw JSON report contains the per-run `pip_freeze`, the package metadata inventory, and the before/after size snapshots. The package/model excerpts above are from the actual PyPI wheel and the pinned upstream model-card revision, not assumptions based on package names.

## Recommendation and risks

**Recommendation:** keep N-04 opt-in and non-accepting. Do not enable it in the default Windows deliverable or ship the current OCR stack broadly without a product need, an installer/bundle-size measurement, memory/startup budgeting, a third-party license inventory, and legal review of the model's training-source caveat. If exposed in a UI, show each proposed name and its original lines as a suggestion requiring explicit human confirmation; never turn its confidence into acceptance.

Key risks are the roughly 1.3 GiB installed dependency footprint, 761 MiB observed peak resident working set, ~5.10 s cold model initialization, 0.75–1.39 s per-crop inference on this Windows-latest runner, uncalibrated confidence, provisional evaluation references, and unresolved upstream scanned-book copyright provenance. Performance numbers describe one `windows-latest` image and one 22-crop run, not a service-level or accuracy guarantee.

## Tests, CI, and intermediate failures

- Full local Python suite after the N-04 implementation/diagnostic changes: **1,918 passed, 111 subtests passed** in 320.60 s. Focused N-04 tests: **9 passed, 4 subtests passed**; `py_compile` and `git diff --check` passed.
- The Python test workflow passed on the measurement commit: [40311286610](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40311286610).
- The Windows workflow passed on the measurement commit, including the N-04 benchmark, artifact upload, and OCR-free one-folder build: [40311286720](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40311286720).
- Retained intermediate Windows failures: [40307573911](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40307573911) and [40308376556](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40308376556) failed in N-04 because ParisaOCR 0.7.2 imported POSIX-only `resource` on Windows; the explicit import shim fixed that path and the later N-04 run passed. Run [40308983293](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40308983293) was the `windows-build.yml` workflow at head `af8dae13b323f71df0b0b535eb6938672fa74930`. Its job `Windows / Python 3.11 / PyInstaller onedir` failed with exit code 1 during Windows packaging; this was not an E-11 contract-test failure. The same-SHA PR Windows run [40308988488](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40308988488) passed, and later N-04 measurement runs passed.
- N-04 closeout commit `8308023e208d8a648b6bd410f63f2c821d476ab7` is docs-only: `AGENT_HANDOFF.md` and this report. Annotated tag `stable-n-04` targets it. Both workflows passed at that tagged commit: [Python 40313438293](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40313438293) and [Windows 40313438283](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40313438283).

The Windows Actions runner's Node.js 20 deprecation notices are non-blocking and unrelated to N-04.
