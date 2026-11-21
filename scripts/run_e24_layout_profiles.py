#!/usr/bin/env python3
"""Run deterministic, data-only E-24 layout-profile and price-witness checks.

All variants in this runner are synthetic ordered cell values; no invoice image
or OCR backend is loaded. The four real Holo profile output snapshots are
checked separately by ``tests/test_e24_layout_profiles.py``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOLO_OUTPUT_GOLDENS = {
    "29": (6815, "0f2810f8aadf9b1e55994db91aefbdf7218a3382ed336019244626e7fa888b31"),
    "31": (5713, "e66f3455c660848013db8ebf88be7c3c2bdd2ef65ab5675fc955df83b5d4c69c"),
    "32": (7933, "342dc7223fcb7ce47b1d13fa1f1ebe2bfa1946ef7dc3522a33b9ee8292b89e51"),
    "33": (16917, "8466d15909aae930ddb849a02ef1e6c3efdff095b731c843c44b70cff53c4502"),
}

from image_extraction_adapter.layout_profiles import (  # noqa: E402
    ProfileCell,
    evaluate_profile_row,
    load_layout_profile_registry,
    serialize_profile_output,
)


def _case(
    *,
    name: str,
    profile_id: str,
    values: list[Any],
    currency_unit: str | None,
    expected_status: str,
    expected_fields: dict[str, Any] | None = None,
    observed_column_roles: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    registry = load_layout_profile_registry()
    result = evaluate_profile_row(
        profile_id,
        values,
        currency_unit=currency_unit,
        observed_column_roles=observed_column_roles,
        registry=registry,
    )
    result_dict = result.to_dict()
    actual_fields = result_dict["fields"]
    expected_fields = expected_fields or {}
    values_match = all(actual_fields.get(key) == value
                       for key, value in expected_fields.items())
    witnesses = result_dict["witnesses"]
    all_witnesses_passed = bool(witnesses) and all(
        isinstance(witness, dict) and witness.get("passed") is True
        for witness in witnesses.values()
    )
    extracted = result.status == "EXTRACTED"
    extracted_but_wrong = extracted and not values_match
    outcome_safe = (
        (extracted and values_match and all_witnesses_passed)
        or (result.status in {"REVIEW", "BLOCKED"} and bool(result.reason))
    )
    return {
        "variant": name,
        "profile_id": profile_id,
        "synthetic_only": True,
        "currency_unit": currency_unit,
        "expected_status": expected_status,
        "result": result_dict,
        "expected_fields": expected_fields,
        "expected_fields_match": values_match,
        "all_witnesses_passed": all_witnesses_passed,
        "extracted_but_wrong": extracted_but_wrong,
        "safe_outcome": outcome_safe and result.status == expected_status,
    }


def build_e24_report() -> dict[str, Any]:
    """Return the complete deterministic synthetic-variant evidence report."""
    registry = load_layout_profile_registry()
    unit_price_roles = registry.get("synthetic-rtl-unit-price-v1").column_roles
    cases = [
        _case(
            name="unknown-layout-id",
            profile_id="unregistered-layout-v99",
            values=["1000", "1", "Synthetic unknown layout", "1"],
            currency_unit="rial",
            expected_status="REVIEW",
        ),
        _case(
            name="holo-layout-without-explicit-unit-price-witness",
            profile_id="holo-rtl-four-column-v1",
            values=["2400", "2", "Synthetic Holo row", "1"],
            currency_unit="rial",
            expected_status="REVIEW",
        ),
        _case(
            name="unit-price-and-discount-columns",
            profile_id="synthetic-rtl-unit-discount-v1",
            values=["1800", "900", "10", "1000", "2", "Synthetic discounted item", "1"],
            currency_unit="rial",
            expected_status="EXTRACTED",
            expected_fields={
                "quantity": 2,
                "unit_price": 1000,
                "discount_percent": "10",
                "discounted_price": 900,
                "line_total": 1800,
                "line_total_unit_price_role": "discounted_price",
                "currency_unit": "rial",
            },
        ),
        _case(
            name="two-line-row",
            profile_id="synthetic-rtl-unit-price-v1",
            values=["2400", "1200", "2", ["Synthetic item", "second description line"], "1"],
            currency_unit="rial",
            expected_status="EXTRACTED",
            expected_fields={
                "description_lines": ["Synthetic item", "second description line"],
                "description": "Synthetic item\nsecond description line",
                "quantity": 2,
                "unit_price": 1200,
                "line_total": 2400,
            },
        ),
        _case(
            name="crossed-out-consumer-price-with-active-unit-price",
            profile_id="synthetic-rtl-crossed-consumer-price-v1",
            values=[
                "1800",
                ProfileCell("2500", crossed_out=True),
                "900",
                "2",
                "Synthetic product",
                "1",
            ],
            currency_unit="rial",
            expected_status="EXTRACTED",
            expected_fields={
                "consumer_price": "2500",
                "consumer_price_crossed_out": True,
                "unit_price": 900,
                "line_total": 1800,
                "line_total_unit_price_role": "unit_price",
            },
        ),
        _case(
            name="unregistered-extra-column",
            profile_id="synthetic-rtl-unit-price-v1",
            values=["1800", "900", "2", "Synthetic product", "1", "UNDECLARED"],
            currency_unit="rial",
            expected_status="REVIEW",
            observed_column_roles=unit_price_roles + ("unregistered_extra",),
        ),
        _case(
            name="toman-with-explicit-unit",
            profile_id="synthetic-rtl-unit-price-v1",
            values=["3000", "1500", "2", "Synthetic toman item", "1"],
            currency_unit="toman",
            expected_status="EXTRACTED",
            expected_fields={
                "quantity": 2,
                "unit_price": 1500,
                "line_total": 3000,
                "currency_unit": "toman",
            },
        ),
        _case(
            name="toman-without-unit-setting",
            profile_id="synthetic-rtl-unit-price-v1",
            values=["3000", "1500", "2", "Synthetic toman item", "1"],
            currency_unit=None,
            expected_status="REVIEW",
        ),
        _case(
            name="discount-arithmetic-mismatch",
            profile_id="synthetic-rtl-unit-discount-v1",
            values=["1800", "950", "10", "1000", "2", "Synthetic mismatch", "1"],
            currency_unit="rial",
            expected_status="REVIEW",
        ),
        _case(
            name="line-total-witness-mismatch",
            profile_id="synthetic-rtl-unit-price-v1",
            values=["1801", "900", "2", "Synthetic mismatch", "1"],
            currency_unit="rial",
            expected_status="REVIEW",
        ),
        _case(
            name="crossed-out-price-cannot-be-the-witness",
            profile_id="synthetic-rtl-unit-price-v1",
            values=["1800", ProfileCell("900", crossed_out=True), "2", "Synthetic item", "1"],
            currency_unit="rial",
            expected_status="REVIEW",
        ),
    ]
    safe_count = sum(case["safe_outcome"] for case in cases)
    extracted_wrong = sum(case["extracted_but_wrong"] for case in cases)
    report = {
        "task": "E-24",
        "status": "PASS" if safe_count == len(cases) and extracted_wrong == 0 else "FAIL",
        "synthetic_only": True,
        "images_loaded": 0,
        "network_or_ocr_used": False,
        "profile_registry_version": registry.schema_version,
        "profile_ids": [profile.profile_id for profile in registry.profiles],
        "aggregate": {
            "sample_count": len(cases),
            "safe_profile_witness_or_review_count": safe_count,
            "safe_profile_witness_or_review_rate_percent": round(
                safe_count * 100 / len(cases), 2
            ),
            "extracted_but_wrong": extracted_wrong,
            "thresholds_tuned": False,
        },
        "variants": cases,
        "notice": (
            "Synthetic ordered cell values only. These checks do not use third-party "
            "images, do not claim OCR accuracy, and do not change the legacy Holo output."
        ),
    }
    return report


def render_e24_markdown(report: dict[str, Any]) -> str:
    rows = [
        "# E-24 — Explicit layout profiles and line-price witnesses",
        "",
        f"- **Status:** {report['status']}",
        "- **Evidence class:** deterministic synthetic ordered cell values only; no images or OCR.",
        f"- **Profile registry:** `{report['profile_registry_version']}`.",
        "- **Currency:** values are never converted; `currency_unit` must be explicitly supplied.",
        "",
        "| Synthetic variant | Profile | Currency | Route | Witness / reason | EXTRACTED-but-wrong |",
        "|---|---|---|---|---|---:|",
    ]
    for case in report["variants"]:
        result = case["result"]
        if result["witnesses"]:
            witness = "; ".join(
                f"{name}: {item['passed']}"
                for name, item in result["witnesses"].items()
            )
        else:
            witness = result["reason_code"]
        rows.append(
            f"| {case['variant']} | `{case['profile_id']}` | "
            f"{case['currency_unit'] or 'missing'} | **{result['status']}** | "
            f"{witness} | {int(case['extracted_but_wrong'])} |"
        )
    aggregate = report["aggregate"]
    rows.extend((
        "",
        "## Aggregate",
        "",
        f"- Safe profile/witness or REVIEW/BLOCK routes: "
        f"**{aggregate['safe_profile_witness_or_review_count']}/"
        f"{aggregate['sample_count']} ({aggregate['safe_profile_witness_or_review_rate_percent']}%)**.",
        f"- EXTRACTED-but-wrong: **{aggregate['extracted_but_wrong']}**.",
        "- Thresholds tuned: **No**.",
        "- No date, currency conversion, or profile selection is inferred.",
        "",
        "## Registry and witness rules",
        "",
        "The registry is `src/image_extraction_adapter/layout_profiles_v1.json`. Each profile declares its exact columns from left to right and the table reading direction. Profile selection is exact-ID only; unknown IDs, reordered/extra columns, and missing required cells return REVIEW. There is no geometry-based profile guessing.",
        "",
        "- `holo-rtl-four-column-v1` retains the existing left-to-right roles `line_total`, `quantity`, `description`, `row_number`; it has no explicit per-unit-price column and therefore cannot pass the new line-price witness. This does not alter the legacy Holo pipeline output.",
        "- `synthetic-rtl-unit-discount-v1` explicitly declares `discounted_price` as the per-unit price used by its line-total witness. When `unit_price` and `discount_percent` are also supplied, the profile requires exact, no-rounding discount arithmetic.",
        "- `synthetic-rtl-unit-price-v1` and `synthetic-rtl-crossed-consumer-price-v1` declare `unit_price` as the witness price. A crossed-out consumer price is retained as non-witness context; a crossed-out witness price is REVIEW.",
        "- Every EXTRACTED row requires `quantity × declared per-unit price = line_total` exactly. Two-line descriptions remain ordered lines. Amounts are not converted; missing currency unit is REVIEW.",
        "",
        "## Legacy Holo output compatibility",
        "",
        "The four golden files under `tests/fixtures/real/e24-holo-profile/` snapshot `extract_pipeline_v0()` with its existing default Holo/Glyph bank before E-24. Only the environment-specific absolute `template_bank_path` is normalized to `src/templates_bank_default.json`; all other serialized fields are byte-compared. These are compatibility fixtures, not issuance or accuracy claims.",
        "",
        "| Fixture | Golden bytes | SHA-256 |",
        "|---|---:|---|",
    ))
    for fixture_id, (size, digest) in HOLO_OUTPUT_GOLDENS.items():
        rows.append(f"| {fixture_id} | {size} | `{digest}` |")
    rows.extend((
        "",
        "## Reproduction",
        "",
        "```bash",
        "PYTHONPATH=src python scripts/run_e24_layout_profiles.py",
        "PYTHONPATH=src python -m pytest -q tests/test_e24_layout_profiles.py",
        "```",
        "",
        report["notice"],
        "",
    ))
    return "\n".join(rows)


def write_e24_report(report_json: Path, report_markdown: Path) -> dict[str, Any]:
    report = build_e24_report()
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_markdown.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(serialize_profile_output(report), encoding="utf-8", newline="\n")
    report_markdown.write_text(render_e24_markdown(report), encoding="utf-8", newline="\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-json",
        type=Path,
        default=ROOT / "docs" / "e24-layout-profiles.json",
    )
    parser.add_argument(
        "--report-md",
        type=Path,
        default=ROOT / "docs" / "e24-layout-profiles.md",
    )
    args = parser.parse_args(argv)
    report = write_e24_report(args.report_json, args.report_md)
    print(json.dumps({
        "task": report["task"],
        "status": report["status"],
        "sample_count": report["aggregate"]["sample_count"],
        "extracted_but_wrong": report["aggregate"]["extracted_but_wrong"],
        "report_json": str(args.report_json),
        "report_markdown": str(args.report_md),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
