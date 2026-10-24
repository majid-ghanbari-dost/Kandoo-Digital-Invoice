"""Configurable E-06 verdict thresholds and onboarding policy."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class VerdictThresholds:
    """Conservative, versionable defaults for the E-06 decision layer."""

    accept_confidence: float = 0.95
    review_confidence: float = 0.80
    onboarding_invoice_count: int = 4
    kit_required_digits: tuple[str, ...] = ("۲", "۶")
    min_kit_digit_occurrences: int = 5
    template_ambiguity_margin: float = 0.03
    required_layout_components: tuple[str, ...] = (
        "columns",
        "row_rhythm",
        "table_anchor",
        "payable_anchor",
    )

    def __post_init__(self) -> None:
        accept = float(self.accept_confidence)
        review = float(self.review_confidence)
        margin = float(self.template_ambiguity_margin)
        if not math.isfinite(accept) or not math.isfinite(review):
            raise ValueError("confidence thresholds must be finite")
        if not 0 <= review < accept <= 1:
            raise ValueError("thresholds must satisfy 0 <= review < accept <= 1")
        if not math.isfinite(margin) or not 0 <= margin <= 1:
            raise ValueError("template_ambiguity_margin must be in [0, 1]")
        if type(self.onboarding_invoice_count) is not int or self.onboarding_invoice_count < 1:
            raise ValueError("onboarding_invoice_count must be a positive integer")
        if type(self.min_kit_digit_occurrences) is not int or self.min_kit_digit_occurrences < 1:
            raise ValueError("min_kit_digit_occurrences must be a positive integer")
        if not self.kit_required_digits or len(set(self.kit_required_digits)) != len(self.kit_required_digits):
            raise ValueError("kit_required_digits must be non-empty and unique")
        if any(not isinstance(digit, str) or len(digit) != 1 for digit in self.kit_required_digits):
            raise ValueError("each kit-required digit must be a single character")
        if not self.required_layout_components:
            raise ValueError("required_layout_components must not be empty")
        if len(set(self.required_layout_components)) != len(self.required_layout_components):
            raise ValueError("required_layout_components must be unique")


DEFAULT_THRESHOLDS = VerdictThresholds()
