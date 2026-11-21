# E-24 — Explicit layout profiles and line-price witnesses

- **Status:** PASS
- **Evidence class:** deterministic synthetic ordered cell values only; no images or OCR.
- **Profile registry:** `e24.layout-profile-registry.v1`.
- **Currency:** values are never converted; `currency_unit` must be explicitly supplied.

| Synthetic variant | Profile | Currency | Route | Witness / reason | EXTRACTED-but-wrong |
|---|---|---|---|---|---:|
| unknown-layout-id | `unregistered-layout-v99` | rial | **REVIEW** | UNKNOWN_LAYOUT_PROFILE | 0 |
| holo-layout-without-explicit-unit-price-witness | `holo-rtl-four-column-v1` | rial | **REVIEW** | UNIT_PRICE_ROLE_UNDECLARED | 0 |
| unit-price-and-discount-columns | `synthetic-rtl-unit-discount-v1` | rial | **EXTRACTED** | discount_percent: True; quantity_x_unit_price_equals_line_total: True | 0 |
| two-line-row | `synthetic-rtl-unit-price-v1` | rial | **EXTRACTED** | quantity_x_unit_price_equals_line_total: True | 0 |
| crossed-out-consumer-price-with-active-unit-price | `synthetic-rtl-crossed-consumer-price-v1` | rial | **EXTRACTED** | quantity_x_unit_price_equals_line_total: True | 0 |
| unregistered-extra-column | `synthetic-rtl-unit-price-v1` | rial | **REVIEW** | COLUMN_ORDER_MISMATCH | 0 |
| toman-with-explicit-unit | `synthetic-rtl-unit-price-v1` | toman | **EXTRACTED** | quantity_x_unit_price_equals_line_total: True | 0 |
| toman-without-unit-setting | `synthetic-rtl-unit-price-v1` | missing | **REVIEW** | CURRENCY_UNIT_UNCONFIRMED | 0 |
| discount-arithmetic-mismatch | `synthetic-rtl-unit-discount-v1` | rial | **REVIEW** | discount_percent: False | 0 |
| line-total-witness-mismatch | `synthetic-rtl-unit-price-v1` | rial | **REVIEW** | quantity_x_unit_price_equals_line_total: False | 0 |
| crossed-out-price-cannot-be-the-witness | `synthetic-rtl-unit-price-v1` | rial | **REVIEW** | WITNESS_PRICE_CROSSED_OUT | 0 |

## Aggregate

- Safe profile/witness or REVIEW/BLOCK routes: **11/11 (100.0%)**.
- EXTRACTED-but-wrong: **0**.
- Thresholds tuned: **No**.
- No date, currency conversion, or profile selection is inferred.

## Registry and witness rules

The registry is `src/image_extraction_adapter/layout_profiles_v1.json`. Each profile declares its exact columns from left to right and the table reading direction. Profile selection is exact-ID only; unknown IDs, reordered/extra columns, and missing required cells return REVIEW. There is no geometry-based profile guessing.

- `holo-rtl-four-column-v1` retains the existing left-to-right roles `line_total`, `quantity`, `description`, `row_number`; it has no explicit per-unit-price column and therefore cannot pass the new line-price witness. This does not alter the legacy Holo pipeline output.
- `synthetic-rtl-unit-discount-v1` explicitly declares `discounted_price` as the per-unit price used by its line-total witness. When `unit_price` and `discount_percent` are also supplied, the profile requires exact, no-rounding discount arithmetic.
- `synthetic-rtl-unit-price-v1` and `synthetic-rtl-crossed-consumer-price-v1` declare `unit_price` as the witness price. A crossed-out consumer price is retained as non-witness context; a crossed-out witness price is REVIEW.
- Every EXTRACTED row requires `quantity × declared per-unit price = line_total` exactly. Two-line descriptions remain ordered lines. Amounts are not converted; missing currency unit is REVIEW.

## Legacy Holo output compatibility

The four golden files under `tests/fixtures/real/e24-holo-profile/` snapshot `extract_pipeline_v0()` with its existing default Holo/Glyph bank before E-24. Only the environment-specific absolute `template_bank_path` is normalized to `src/templates_bank_default.json`; all other serialized fields are byte-compared. These are compatibility fixtures, not issuance or accuracy claims.

| Fixture | Golden bytes | SHA-256 |
|---|---:|---|
| 29 | 6815 | `0f2810f8aadf9b1e55994db91aefbdf7218a3382ed336019244626e7fa888b31` |
| 31 | 5713 | `e66f3455c660848013db8ebf88be7c3c2bdd2ef65ab5675fc955df83b5d4c69c` |
| 32 | 7933 | `342dc7223fcb7ce47b1d13fa1f1ebe2bfa1946ef7dc3522a33b9ee8292b89e51` |
| 33 | 16917 | `8466d15909aae930ddb849a02ef1e6c3efdff095b731c843c44b70cff53c4502` |

## Reproduction

```bash
PYTHONPATH=src python scripts/run_e24_layout_profiles.py
PYTHONPATH=src python -m pytest -q tests/test_e24_layout_profiles.py
```

Synthetic ordered cell values only. These checks do not use third-party images, do not claim OCR accuracy, and do not change the legacy Holo output.
