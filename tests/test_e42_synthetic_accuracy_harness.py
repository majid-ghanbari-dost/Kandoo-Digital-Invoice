from __future__ import annotations

from scripts.run_e42_synthetic_accuracy_harness import (
    EVALUATION_SAMPLE_COUNT,
    KNOWN_LAYOUT_PROFILES,
    _contains_forbidden_key,
    _evaluate_unknown_profile_control,
    _route_pipeline_status,
    render_markdown,
    run_harness,
)


def test_prohibited_customer_and_store_fields_are_checked_recursively() -> None:
    assert _contains_forbidden_key({"nested": [{"CUSTOMER_NAME": "synthetic"}]})
    assert _contains_forbidden_key({"metadata": {"store_id": "synthetic"}})
    assert not _contains_forbidden_key({"description": "synthetic row"})


def test_pipeline_statuses_map_to_extracted_review_or_blocked_fail_closed() -> None:
    known = "standard-v1"
    assert _route_pipeline_status(
        profile_id=known,
        pipeline_status="AUTO_CANDIDATE",
        layout_status="OK",
        all_expected_numeric_fields_extracted=True,
    ) == "EXTRACTED"
    assert _route_pipeline_status(
        profile_id=known,
        pipeline_status="AUTO_CANDIDATE",
        layout_status="OK",
        all_expected_numeric_fields_extracted=False,
    ) == "REVIEW"
    assert _route_pipeline_status(
        profile_id=known,
        pipeline_status="REVIEW",
        layout_status="OK",
        all_expected_numeric_fields_extracted=False,
    ) == "REVIEW"
    assert _route_pipeline_status(
        profile_id=known,
        pipeline_status="REJECT",
        layout_status="BLOCKED",
        all_expected_numeric_fields_extracted=False,
    ) == "BLOCKED"
    assert _route_pipeline_status(
        profile_id="unregistered-synthetic-layout-v99",
        pipeline_status="AUTO_CANDIDATE",
        layout_status="OK",
        all_expected_numeric_fields_extracted=True,
    ) == "REVIEW"
    assert _route_pipeline_status(
        profile_id=known,
        pipeline_status="REVIEW",
        layout_status="REVIEW",
        all_expected_numeric_fields_extracted=False,
    ) == "REVIEW"
    assert _route_pipeline_status(
        profile_id=known,
        pipeline_status="REJECT",
        layout_status="REVIEW",
        all_expected_numeric_fields_extracted=False,
    ) == "REVIEW"


def test_unknown_layout_profile_control_routes_review_without_running_ocr() -> None:
    result = _evaluate_unknown_profile_control()

    assert result["e24_profile_status"] == "REVIEW"
    assert result["harness_route"] == "REVIEW"
    assert result["pipeline_invoked"] is False
    assert result["counted_in_accuracy_metrics"] is False


def test_end_to_end_harness_uses_disjoint_synthetic_splits_and_reports_every_layout() -> None:
    report = run_harness()

    assert report["status"] == "PASS"
    assert report["synthetic_only"] is True
    assert report["real_invoice_fixtures_read"] is False
    assert report["external_input_sources"] == []
    assert report["network_access_used"] is False
    assert report["external_ocr_service_used"] is False
    assert report["local_glyph_classifier_used"] is True
    assert report["thresholds_tuned"] is False
    assert report["training"]["seed"] != report["evaluation"]["seed"]
    assert set(report["training"]["training_samples_by_layout"]) == KNOWN_LAYOUT_PROFILES
    assert set(report["evaluation"]["evaluation_samples_by_layout"]) == KNOWN_LAYOUT_PROFILES
    assert not set(report["training"]["source_image_sha256"]).intersection(
        report["evaluation"]["source_image_sha256"]
    )
    assert report["training"]["training_numeric_cells_skipped"] == 0
    assert report["aggregate"]["extracted_but_wrong"] == 0
    assert report["aggregate"]["extracted_label_comparisons"] > 0
    assert set(report["aggregate"]["evaluation_invoice_outcomes"]) == {
        "EXTRACTED", "REVIEW", "BLOCKED"
    }
    assert set(report["aggregate"]["evaluation_numeric_field_outcomes"]) == {
        "EXTRACTED", "REVIEW", "BLOCKED"
    }
    assert len(report["evaluation"]["invoice_outcomes"]) == EVALUATION_SAMPLE_COUNT
    assert all(
        outcome["canonical_invoice_created"] is False
        for outcome in report["evaluation"]["invoice_outcomes"]
    )
    assert all(
        outcome["per_invoice_seconds"] >= 0
        for outcome in report["evaluation"]["invoice_outcomes"]
    )
    assert all(
        item["extracted_but_wrong"] == 0
        and set(item["invoice_status_counts"]) == {"EXTRACTED", "REVIEW", "BLOCKED"}
        and set(item["numeric_field_counts"]) == {"EXTRACTED", "REVIEW", "BLOCKED"}
        for item in report["evaluation"]["known_layouts"]
    )
    controls = report["routing_controls"]
    assert controls["unknown_profile"]["harness_route"] == "REVIEW"
    assert controls["low_confidence_geometry"]["route"] == "REVIEW"
    assert controls["all_routed_to_review"] is True

    markdown = render_markdown(report)
    assert "گزارش E-42" in markdown
    assert "EXTRACTED-but-wrong" in markdown
    assert "BLOCKED" in markdown
    assert "پوشش فیلدها" in markdown
