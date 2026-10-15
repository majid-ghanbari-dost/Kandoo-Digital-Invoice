"""English/Persian synthetic raster OCR -> actual Digital Issuance smoke.

Requires optional tesserocr/Pillow plus traineddata supplied out-of-repository.
Fixtures are explicitly synthetic and are not Holoo invoices.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from digital_invoice import (  # noqa: E402
    DigitalInvoiceOpened,
    DigitalInvoiceReadSuccess,
    DigitalInvoiceTraceSuccess,
    LifecycleAdvanced,
    STATE_DRAFT,
    STATE_EXTRACTED,
    STATE_ISSUED,
    STATE_VALIDATED,
)
from image_extraction_adapter import (  # noqa: E402
    ImageExtractionAdapter,
    ImageExtractionBlocked,
    ImageExtractionReady,
    ImageExtractionReviewRequired,
    ImageIssuanceSubmission,
    TesseractOCR,
)
from issuance import DigitalIssuanceWorkspace  # noqa: E402
from validation import ReferenceValidationRulesV1  # noqa: E402

FIXTURES = {
    "en": (Path(__file__).resolve().parent
           / "image_extraction_adapter" / "tests" / "fixtures"
           / "synthetic_invoice.png"),
    "fa": (Path(__file__).resolve().parent
           / "image_extraction_adapter" / "tests" / "fixtures"
           / "synthetic_invoice_fa.png"),
}
EXPECTED = {
    "en": {
        "invoice.number": "SYNTH-IMG-001",
        "invoice.date": "2026-10-14",
        "total.net": "1000.00",
        "tax.amount": "80.00",
        "invoice.payable": "1080.00",
        "line.0.description": "Synthetic Widget",
        "line.0.quantity": "2",
        "line.0.unit_price": "500.00",
        "line.0.total": "1000.00",
    },
    "fa": {
        "invoice.number": "1001",
        "invoice.date": "2026-10-14",
        "total.net": "1300.00",
        "tax.amount": "104.00",
        "invoice.payable": "1404.00",
        "line.0.description": "ساندویچ کالباس",
        "line.0.quantity": "2",
        "line.0.unit_price": "500.00",
        "line.0.total": "1000.00",
        "line.1.description": "دستمال سفره تم",
        "line.1.quantity": "1",
        "line.1.unit_price": "300.00",
        "line.1.total": "300.00",
    },
}
DECLARATIONS = {
    "en": {
        "source_label": "synthetic-image-ocr-smoke",
        "declared_origin": "HOLOO_CAPTURE",  # test declaration; no Holoo data
        "identity_binding": {
            "INVOICE_NUMBER": "invoice.number",
            "INVOICE_DATE": "invoice.date",
            "INVOICE_TOTAL": "invoice.payable",
        },
        "line_binding": {
            0: {
                "LINE_QUANTITY": "line.0.quantity",
                "LINE_UNIT_PRICE": "line.0.unit_price",
                "LINE_TOTAL": "line.0.total",
            }
        },
        "ruleset_id": "synthetic-image-ocr-smoke-declared",
        "ruleset_version": "1",
    },
    "fa": {
        "source_label": "synthetic-persian-image-ocr-smoke",
        "declared_origin": "HOLOO_CAPTURE",  # test declaration; no Holoo data
        "identity_binding": {
            "INVOICE_NUMBER": "invoice.number",
            "INVOICE_DATE": "invoice.date",
            "INVOICE_TOTAL": "invoice.payable",
        },
        "line_binding": {
            index: {
                "LINE_QUANTITY": f"line.{index}.quantity",
                "LINE_UNIT_PRICE": f"line.{index}.unit_price",
                "LINE_TOTAL": f"line.{index}.total",
            }
            for index in (0, 1)
        },
        "ruleset_id": "synthetic-persian-image-ocr-smoke-declared",
        "ruleset_version": "1",
    },
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("en", "fa"), default="en")
    parser.add_argument("--tessdata-dir", type=Path, required=True)
    parser.add_argument("--language", required=True,
                        help="e.g. eng for English or fas+eng for Persian/mixed text")
    parser.add_argument("--minimum-confidence", type=float, required=True)
    parser.add_argument("--image", type=Path,
                        help="override the profile's explicitly synthetic fixture")
    return parser.parse_args()


def _print_ocr(ocr) -> None:
    print(f"ocr.engine={ocr.engine}")
    print(f"ocr.language={ocr.language}")
    print(f"ocr.word_count={len(ocr.word_confidences)}")
    print(f"ocr.mean_confidence={ocr.mean_confidence}")
    print(f"ocr.minimum_confidence={ocr.minimum_confidence}")
    print("ocr.raw_text.begin")
    print(ocr.text.rstrip())
    print("ocr.raw_text.end")


def _print_comparison(actual_fields, expected_fields) -> list[str]:
    actual = dict(actual_fields)
    mismatches = []
    print("ocr.value_comparison=")
    for field, expected in expected_fields.items():
        observed = actual.get(field)
        equal = observed == expected
        print(f"  {field}: expected={expected!r} actual={observed!r} match={equal}")
        if not equal:
            mismatches.append(field)
    return mismatches


def _print_pipeline(image_submission: ImageIssuanceSubmission, workspace) -> int:
    submission = image_submission.submission
    print(f"issuance.submit.completed={submission.completed}")
    print(f"pipeline.result={type(submission.pipeline).__name__}")
    if not submission.completed:
        print(f"pipeline.stop.stage={submission.pipeline.stage}")
        print(f"pipeline.stop.outcome={type(submission.pipeline.outcome).__name__}")
        print("digital_invoice=NONE")
        return 0

    pipeline = submission.pipeline
    invoice_id = submission.invoice_id
    print("pipeline.outcomes=" + ", ".join(
        f"{step.stage}:{type(step.outcome).__name__}"
        for step in pipeline.steps))
    for step in pipeline.steps:
        if step.stage == "validate" and hasattr(step.outcome, "record"):
            record = step.outcome.record
            print(f"validation.{record.rule_id}={record.outcome} "
                  f"({record.outcome_reason})")
        elif step.stage == "project" and hasattr(step.outcome, "record"):
            record = step.outcome.record
            print(f"validation_domain={record.domain_state}/"
                  f"{record.disposition} valid={record.valid_count} "
                  f"invalid={record.invalid_count} deferred={record.deferred_count}")
        elif step.stage == "gate_read" and hasattr(step.outcome, "record"):
            print(f"canonicalization.decision={step.outcome.record.decision}")

    invoice_read = pipeline.invoice
    print(f"canonical_invoice_id={invoice_id}")
    print(f"canonical.field_count={invoice_read.invoice.field_count}")
    print(f"canonical.line_count={invoice_read.invoice.line_count}")
    print("canonical.fields=")
    for field in invoice_read.fields:
        print(f"  {field.field_name}={field.canonical_value} [{field.provenance}]")
    print("canonical.line_fields=")
    for line_field in invoice_read.line_fields:
        print(f"  line.{line_field.line_seq}.{line_field.role}="
              f"{line_field.canonical_value}")

    opened = workspace.service.open_digital_invoice(invoice_id)
    assert isinstance(opened, DigitalInvoiceOpened), opened
    draft = workspace.service.status(invoice_id)
    assert draft.current_state == STATE_DRAFT, draft
    print(f"lifecycle.open_digital_invoice={draft.current_state}")
    for act, expected_state in (
        (workspace.service.mark_extracted, STATE_EXTRACTED),
        (workspace.service.mark_validated, STATE_VALIDATED),
        (workspace.service.issue, STATE_ISSUED),
    ):
        result = act(invoice_id, "synthetic OCR smoke; explicit act")
        assert isinstance(result, LifecycleAdvanced), result
        assert result.current_state == expected_state, result
        print(f"lifecycle.{act.__name__}={result.current_state}")

    status = workspace.service.status(invoice_id)
    assert isinstance(status.outcome, DigitalInvoiceReadSuccess), status
    assert status.verified and status.current_state == STATE_ISSUED, status
    trace = workspace.service.trace(invoice_id)
    assert isinstance(trace, DigitalInvoiceTraceSuccess), trace
    print(f"digital_invoice_id={status.digital_invoice_id}")
    print(f"digital_invoice.state={status.current_state}")
    print(f"digital_invoice.verified={status.verified}")
    print(f"digital_invoice.trace={type(trace).__name__} links={len(trace.chain)}")
    print(f"IMAGE OCR E2E {image_submission.extraction.ocr.language} OK — synthetic fixture only")
    return 0


def main() -> int:
    args = parse_args()
    image = args.image or FIXTURES[args.profile]
    adapter = ImageExtractionAdapter(
        TesseractOCR(tessdata_dir=args.tessdata_dir, language=args.language),
        minimum_word_confidence=args.minimum_confidence,
    )

    with tempfile.TemporaryDirectory(prefix="kandoo-image-ocr-smoke-") as temp:
        rules = dict(ReferenceValidationRulesV1(
            tolerance="0.02", precision=2, mode="HALF_UP"))
        with DigitalIssuanceWorkspace(Path(temp) / "workspace",
                                      validation_rules=rules) as workspace:
            extraction = adapter.extract(image)
            print(f"fixture.label=Synthetic ({args.profile})")
            print(f"fixture.path={image}")
            if isinstance(extraction, ImageExtractionBlocked):
                print(f"ocr.status=BLOCKED reason={extraction.reason}")
                return 2
            if isinstance(extraction, ImageExtractionReviewRequired):
                print("ocr.status=REVIEW_REQUIRED (adapter hold; no submit)")
                print(f"source_image.sha256={extraction.source_image_sha256}")
                _print_ocr(extraction.ocr)
                print(f"review.reason={extraction.reason}")
                print("issuance.submit=NOT_CALLED")
                print("digital_invoice=NONE")
                return 0
            if not isinstance(extraction, ImageExtractionReady):
                print(f"unexpected extraction outcome: {type(extraction).__name__}")
                return 2

            print(f"source_image.sha256={extraction.source_image_sha256}")
            _print_ocr(extraction.ocr)
            mismatches = _print_comparison(extraction.field_values, EXPECTED[args.profile])
            if mismatches:
                print("ocr.status=BLOCKED (expected-value mismatch; fail closed)")
                print("issuance.submit=NOT_CALLED")
                print("digital_invoice=NONE")
                return 2

            outcome = adapter.submit_extraction(
                extraction,
                workspace.service,
                **DECLARATIONS[args.profile],
            )
            assert isinstance(outcome, ImageIssuanceSubmission), outcome
            return _print_pipeline(outcome, workspace)


if __name__ == "__main__":
    raise SystemExit(main())
