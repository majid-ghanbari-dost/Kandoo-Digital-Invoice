from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from e05_template_bank import (
    TemplateBank,
    build_template_bank,
    load_template_bank,
    load_training_observations,
    match_observation,
    save_template_bank,
)
from image_extraction_adapter.canonical_invoice import validate_canonical_invoice


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_DIR = REPOSITORY_ROOT / "tests" / "fixtures" / "real" / "canonical"
LABELS_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "real" / "labels.json"
EXPECTED_SOURCE_IDS = ("29", "31", "32", "33")


@pytest.fixture(scope="module")
def bank() -> TemplateBank:
    return build_template_bank(CANONICAL_DIR, LABELS_PATH)


@pytest.fixture(scope="module")
def observations():
    return load_training_observations(CANONICAL_DIR, LABELS_PATH)


def test_synthesized_canonical_fixtures_are_schema_valid_and_marked() -> None:
    manifest = json.loads((CANONICAL_DIR / "synthesis-manifest.json").read_text(encoding="utf-8"))
    assert manifest["synthesis_marker"] == "synthesized_from_labels"
    assert [record["source_id"] for record in manifest["invoices"]] == list(EXPECTED_SOURCE_IDS)
    assert all(record["synthesized_from_labels"] is True for record in manifest["invoices"])
    required_synthetic_fields = {
        "mode",
        "invoice_id",
        "display_number",
        "operation_id",
        "device_id",
        "public_token",
        "store_id",
        "customer.phone",
        "customer.phone_status",
        "line_items[].product_name",
    }
    for record in manifest["invoices"]:
        assert required_synthetic_fields <= set(record["synthetic_context_fields"])
        assert record["synthetic_context_source"] == (
            "docs/cli-contract.md example; IDs and product names use explicit E-05 test placeholders"
        )

    states = {"29": "EXTRACTED", "31": "EXTRACTED", "32": "EXTRACTED", "33": "DRAFT"}
    for record in manifest["invoices"]:
        invoice = json.loads((CANONICAL_DIR / record["canonical_file"]).read_text(encoding="utf-8"))
        valid, errors = validate_canonical_invoice(invoice)
        assert valid, errors
        assert invoice["state"] == states[record["source_id"]]
        assert "synthesized_from_labels" not in invoice
        assert all(type(item["quantity"]) is int for item in invoice["line_items"])
        assert all(item["unit_price"] * item["quantity"] == item["line_total"] for item in invoice["line_items"])


def test_template_bank_builds_one_layout_from_all_four_labelled_invoices(
    bank: TemplateBank,
) -> None:
    assert len(bank.templates) == 1
    template = bank.templates[0]
    assert template.source_invoice_ids == EXPECTED_SOURCE_IDS
    assert template.row_count_min == 3
    assert template.row_count_max == 13
    assert template.known_row_counts == (3, 4, 5, 13)
    assert template.amount_thousands_separator == ","
    assert template.amount_group_size == 3
    assert template.digit_alphabet == tuple("۰۱۲۳۴۵۶۷۸۹")
    assert {position.field_name for position in template.field_positions} == {
        "line.total",
        "line.quantity",
        "line.description",
        "line.sequence",
        "invoice.payable",
    }


def test_each_training_invoice_matches_its_learned_template_with_high_confidence(
    bank: TemplateBank,
    observations,
) -> None:
    assert tuple(observation.source_id for observation in observations) == EXPECTED_SOURCE_IDS
    for observation in observations:
        result = match_observation(bank, observation)
        assert result.template_id == bank.templates[0].template_id
        assert result.matched, (observation.source_id, result.to_dict())
        assert result.confidence_score >= 0.85
        assert result.numeric_evidence_present


def test_match_uses_numeric_format_not_memorized_invoice_amounts(
    bank: TemplateBank,
    observations,
) -> None:
    original = observations[0]
    different_values = {}
    for field_name, raw_value in original.field_values:
        if field_name.endswith(".quantity"):
            different_values[field_name] = "۲"
        elif field_name == "invoice.payable" or field_name.endswith(".total"):
            different_values[field_name] = "۹,۹۹۹,۰۰۰"
        else:
            different_values[field_name] = raw_value
    new_observation = replace(original, source_id="new-invoice", field_values=different_values)

    result = match_observation(bank, new_observation)
    assert result.matched
    assert result.confidence_score >= 0.85
    assert result.component_scores["numeric_format"] == 1.0


def test_incompatible_column_geometry_is_not_matched(
    bank: TemplateBank,
    observations,
) -> None:
    observation = observations[0]
    shifted = replace(
        observation,
        column_boundaries=(116.0, 200.0, 350.0, 470.0, 527.0),
    )
    result = match_observation(bank, shifted)
    assert not result.matched
    assert result.component_scores["columns"] == 0.0
    assert result.confidence_score < 0.85


def test_unseen_numeric_script_fails_closed(
    bank: TemplateBank,
    observations,
) -> None:
    observation = observations[0]
    ascii_values = {
        field_name: raw_value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
        for field_name, raw_value in observation.field_values
    }
    result = match_observation(bank, replace(observation, field_values=ascii_values))
    assert not result.matched
    assert result.component_scores["numeric_format"] == 0.0
    assert any("learned numeric format" in reason for reason in result.reasons)


def test_row_count_outside_learned_range_is_not_matched(
    bank: TemplateBank,
    observations,
) -> None:
    observation = observations[0]
    top = observation.row_bands[0][0]
    bands = tuple((top + 68 * index, top + 68 * (index + 1)) for index in range(14))
    extended = replace(
        observation,
        image_height=1600,
        row_bands=bands,
        payable_bbox=(214.0, 1500.0, 116.0, 28.0),
    )
    result = match_observation(bank, extended)
    assert not result.matched
    assert result.component_scores["row_count"] == 0.0
    assert result.confidence_score < 0.85


def test_geometry_only_match_is_explicitly_marked_without_numeric_evidence(
    bank: TemplateBank,
    observations,
) -> None:
    layout_only = replace(observations[0], field_values=())
    result = match_observation(bank, layout_only)
    assert result.matched
    assert not result.numeric_evidence_present
    assert any("not evaluated" in reason for reason in result.reasons)
    assert "numeric_format" not in result.component_scores


def test_template_bank_serializes_and_reloads(tmp_path: Path, bank: TemplateBank) -> None:
    round_trip = TemplateBank.from_dict(bank.to_dict())
    assert round_trip == bank

    path = tmp_path / "reusable-bank.json"
    save_template_bank(bank, path)
    loaded = load_template_bank(path)
    assert loaded == bank
