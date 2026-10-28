#!/usr/bin/env python3
"""Regenerate the E-16 Mode B artifact examples from the current Python APIs.

The examples are synthetic/test-only wrappers around the existing E-05, E-06,
E-08, and Glyph serializers. They contain no image bytes or customer records.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from e05_template_bank import (  # noqa: E402
    build_template_bank,
    load_training_observations,
)
from e06_onboarding_verdict import evaluate_verdict  # noqa: E402
from e08_new_type_flow import DetectionKind, detect_invoice_type  # noqa: E402
from e08_new_type_flow.candidate import CandidateRegistry  # noqa: E402
from image_extraction_adapter.canonical_invoice import validate_canonical_invoice  # noqa: E402
from image_extraction_adapter.pipeline_v0 import (  # noqa: E402
    REPOSITORY_ROOT,
    build_templates_for_fold,
)


DEFAULT_OUTPUT_DIR = ROOT / "schemas" / "mode-b" / "v1" / "examples"
FIXED_TIME = "2026-10-24T00:00:00Z"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "real"
CANONICAL_DIR = FIXTURE_DIR / "canonical"
LABELS_PATH = FIXTURE_DIR / "labels.json"
STORE_ID = "e05-synth-store"
SOURCE_FIXTURE_ID = "29"


EXAMPLE_METADATA = {
    "template-bank.json": {
        "artifact_type": "kandoo.mode-b.template-bank",
        "schema": "../template-bank.schema.json",
        "generated_from": [
            "e05_template_bank.build_template_bank",
            "e05_template_bank.TemplateBank.to_dict",
        ],
        "purpose": "Portable E-05 layout bank; numeric-format and normalized geometry only.",
    },
    "onboarding-verdict.json": {
        "artifact_type": "kandoo.mode-b.onboarding-verdict",
        "schema": "../onboarding-verdict.schema.json",
        "generated_from": [
            "e06_onboarding_verdict.evaluate_verdict",
            "e06_onboarding_verdict.VerdictResult.to_dict",
        ],
        "purpose": "E-06 REVIEW example during the four-invoice warm-up gate.",
    },
    "layout-font-fingerprint.json": {
        "artifact_type": "kandoo.mode-b.layout-font-fingerprint",
        "schema": "../layout-font-fingerprint.schema.json",
        "generated_from": [
            "e08_new_type_flow.TemplateCandidate.propose",
            "e08_new_type_flow.TemplateCandidate.to_dict",
            "image_extraction_adapter.pipeline_v0.build_templates_for_fold",
            "image_extraction_adapter.glyph_classifier.GlyphTemplateSet.to_json_dict",
        ],
        "purpose": "New-layout geometry and numeric script profile with a fold-local Glyph feature profile.",
    },
    "new-type-candidate.json": {
        "artifact_type": "kandoo.mode-b.new-type-candidate",
        "schema": "../new-type-candidate.schema.json",
        "generated_from": [
            "e08_new_type_flow.detect_invoice_type",
            "e08_new_type_flow.TemplateCandidate.to_dict",
        ],
        "purpose": "E-08 PROPOSED candidate emitted for a changed layout; it is not installed in the bank.",
    },
}


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_canonical(fixture_id: str) -> dict[str, Any]:
    return json.loads(
        (CANONICAL_DIR / f"canonical-{fixture_id}.json").read_text(encoding="utf-8")
    )


def _candidate_invoice(invoice: dict[str, Any]) -> dict[str, Any]:
    """Use synthetic test context and remove fixture-only attention blockers."""
    candidate = copy.deepcopy(invoice)
    candidate["attention_cells"] = []
    candidate["customer"]["phone"] = "+15550001111"
    candidate["provenance"]["image_sha256"] = None
    candidate["provenance"]["fields"]["customer"]["phone"] = "captured"
    for index, line in enumerate(candidate["line_items"]):
        line["product_name"] = f"Example item {index + 1}"
        candidate["provenance"]["fields"]["line_items"][index]["product_name"] = "captured"
    valid, errors = validate_canonical_invoice(candidate)
    if not valid:
        raise RuntimeError(f"test-only new-type Canonical fixture is invalid: {errors}")
    return candidate


def build_artifacts() -> dict[str, dict[str, Any]]:
    bank = build_template_bank(CANONICAL_DIR, LABELS_PATH, currency_unit="rial")
    observations = load_training_observations(CANONICAL_DIR, LABELS_PATH)
    observation = next(item for item in observations if item.source_id == SOURCE_FIXTURE_ID)
    invoice = _load_canonical(SOURCE_FIXTURE_ID)
    if invoice["store_id"] != STORE_ID:
        raise RuntimeError("synthetic fixture store ID changed; review and update this generator explicitly")

    template_bank_artifact = {
        "artifact_type": "kandoo.mode-b.template-bank",
        "artifact_version": "1",
        "mode": "B",
        "store_id": STORE_ID,
        "created_at": FIXED_TIME,
        "template_bank": bank.to_dict(),
    }
    bank_sha256 = _sha256_bytes(_json_text(template_bank_artifact).encode("utf-8"))

    extraction_confidence = 0.99
    verdict = evaluate_verdict(
        invoice,
        bank,
        observation,
        extraction_confidence,
        processed_invoice_count=0,
        template_bank_locked=False,
        d14_agreement_signed=False,
        require_kit_digit_coverage=False,
    )
    onboarding_artifact = {
        "artifact_type": "kandoo.mode-b.onboarding-verdict",
        "artifact_version": "1",
        "mode": "B",
        "store_id": STORE_ID,
        "invoice_id": invoice["invoice_id"],
        "evaluated_at": FIXED_TIME,
        "template_bank_sha256": bank_sha256,
        "evaluation_context": {
            "processed_invoice_count": 0,
            "template_bank_locked": False,
            "d14_agreement_signed": False,
            "require_kit_digit_coverage": False,
            "extraction_confidence": extraction_confidence,
            "missing_fields": [],
        },
        "result": verdict.to_dict(),
    }

    # Shift only layout metadata to create an E-08 new-type example. Numeric
    # observations remain equal to the test invoice so candidate creation is
    # based on geometry, not an invented numeric correction.
    new_layout_observation = replace(
        observation,
        source_id="e16-synthetic-new-layout",
        column_boundaries=(0.0, 80.0, 180.0, 280.0, 380.0),
    )
    detection = detect_invoice_type(
        _candidate_invoice(invoice),
        bank,
        new_layout_observation,
        extraction_confidence,
        store_id=STORE_ID,
        accepted_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=True,
        detected_at=FIXED_TIME,
        candidate_registry=CandidateRegistry(),
    )
    if detection.kind is not DetectionKind.NEW_TYPE or detection.candidate is None:
        raise RuntimeError(
            "expected existing E-08 code to create a synthetic new-type candidate; "
            f"received {detection.kind.value} ({detection.reason_code_strings})"
        )
    candidate = detection.candidate
    candidate_doc = candidate.to_dict()

    glyph_templates = build_templates_for_fold(
        LABELS_PATH,
        "33",
        repo_root=REPOSITORY_ROOT,
    ).to_json_dict()
    source_metadata = []
    for source in glyph_templates["provenance"]:
        image_name = Path(source["image"]).stem
        source_metadata.append({
            "invoice_id": image_name,
            "image_sha256": source["sha256"],
        })
    source_metadata.sort(key=lambda item: item["invoice_id"])
    glyph_profile = {
        "format_version": glyph_templates["format_version"],
        "grid": glyph_templates["grid"],
        "training_sources": source_metadata,
        # Keep the exact numeric features produced by GlyphTemplateSet but omit
        # machine-local image paths from its provenance field.
        "profiles": glyph_templates["profiles"],
    }
    fingerprint_artifact = {
        "artifact_type": "kandoo.mode-b.layout-font-fingerprint",
        "artifact_version": "1",
        "mode": "B",
        "store_id": STORE_ID,
        "fingerprint_id": candidate.candidate_id,
        "observed_at": candidate.proposed_at,
        "source_invoice_ids": list(candidate.source_invoice_ids),
        "layout_signature": candidate_doc["layout_signature"],
        "field_positions": candidate_doc["field_positions"],
        "numeric_digit_alphabet": candidate_doc["numeric_digit_alphabet"],
        "numeric_separators": candidate_doc["numeric_separators"],
        "numeric_group_sizes": candidate_doc["numeric_group_sizes"],
        "observed_numeric_fields": candidate_doc["observed_numeric_fields"],
        "glyph_profile": glyph_profile,
    }
    candidate_artifact = {
        "artifact_type": "kandoo.mode-b.new-type-candidate",
        "artifact_version": "1",
        "mode": "B",
        "store_id": STORE_ID,
        "exported_at": FIXED_TIME,
        "candidate": candidate_doc,
    }
    return {
        "template-bank.json": template_bank_artifact,
        "onboarding-verdict.json": onboarding_artifact,
        "layout-font-fingerprint.json": fingerprint_artifact,
        "new-type-candidate.json": candidate_artifact,
    }


def write_examples(output_dir: Path) -> None:
    artifacts = build_artifacts()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_examples = []
    for file_name, artifact in artifacts.items():
        encoded = _json_text(artifact).encode("utf-8")
        (output_dir / file_name).write_bytes(encoded)
        metadata = EXAMPLE_METADATA[file_name]
        manifest_examples.append({
            "path": file_name,
            "artifact_type": metadata["artifact_type"],
            "schema": metadata["schema"],
            "sha256": _sha256_bytes(encoded),
            "generated_from": metadata["generated_from"],
            "purpose": metadata["purpose"],
        })
    manifest = {
        "manifest_version": "1",
        "generated_by": "scripts/generate_mode_b_artifact_goldens.py",
        "examples": manifest_examples,
    }
    (output_dir / "manifest.json").write_text(_json_text(manifest), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    write_examples(args.output_dir.resolve())
    print(f"Generated four E-16 Mode B examples in {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
