"""Reusable E-05 invoice layout template-bank implementation."""

from .template import (
    FieldPosition,
    LayoutObservation,
    LayoutTemplate,
    TemplateBank,
    TemplateMatch,
)
from .template_bank import (
    build_template_bank,
    load_template_bank,
    load_training_observations,
    match_observation,
    parse_labeled_integer,
    save_template_bank,
)

__all__ = [
    "FieldPosition",
    "LayoutObservation",
    "LayoutTemplate",
    "TemplateBank",
    "TemplateMatch",
    "build_template_bank",
    "load_template_bank",
    "load_training_observations",
    "match_observation",
    "parse_labeled_integer",
    "save_template_bank",
]
