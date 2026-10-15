"""Experimental, confidence-gated image invoice extraction adapter."""
from .adapter import ImageExtractionAdapter, IssuanceSubmitter
from .model import (
    ImageAdapterOutcome,
    ImageExtractionBlocked,
    ImageExtractionReady,
    ImageExtractionReviewRequired,
    ImageIssuanceSubmission,
    CellOCRVariantResult,
    OCRResult,
    OCRWord,
    FieldAssessment,
)
from .ocr import (
    OCRBackend,
    OCREngineUnavailable,
    OCRExecutionError,
    NUMERIC_TESSERACT_WHITELIST,
    PERSIAN_TESSERACT_LANGUAGE,
    TesseractOCR,
)
from .preprocessing import (
    PREPROCESSING_MODES,
    adaptive_binarize,
    crop_spatial_cells,
    otsu_binarize,
    preprocess_cell,
    remove_morphological_table_lines,
)
from .parser import (
    InvoiceTextParseError,
    ParsedImageInvoice,
    SpatialParseResult,
    parse_invoice_geometry,
    parse_invoice_text,
)

__all__ = [
    "ImageExtractionAdapter",
    "IssuanceSubmitter",
    "ImageAdapterOutcome",
    "ImageExtractionBlocked",
    "ImageExtractionReady",
    "ImageExtractionReviewRequired",
    "ImageIssuanceSubmission",
    "CellOCRVariantResult",
    "OCRResult",
    "OCRWord",
    "FieldAssessment",
    "OCRBackend",
    "OCREngineUnavailable",
    "OCRExecutionError",
    "NUMERIC_TESSERACT_WHITELIST",
    "PERSIAN_TESSERACT_LANGUAGE",
    "TesseractOCR",
    "PREPROCESSING_MODES",
    "adaptive_binarize",
    "crop_spatial_cells",
    "otsu_binarize",
    "preprocess_cell",
    "remove_morphological_table_lines",
    "InvoiceTextParseError",
    "ParsedImageInvoice",
    "SpatialParseResult",
    "parse_invoice_geometry",
    "parse_invoice_text",
]
