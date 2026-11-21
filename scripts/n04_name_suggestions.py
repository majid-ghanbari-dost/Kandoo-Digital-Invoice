#!/usr/bin/env python3
"""Optional, non-accepting ParisaOCR name suggestions for N-02 candidates.

This is a prototype enrichment surface only. Importing the module does not
import PyTorch, Kraken, ParisaOCR, or any OCR runtime. ParisaOCR is loaded only
when the caller explicitly constructs ``ParisaOCRNameSuggester``.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import math
import os
import re
import sys
import time
import types
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterator, Protocol

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCHEMA_VERSION = "n02.product-candidates.v1"
SCHEMA_VERSION = "n04.product-candidates-with-name-suggestions.v1"
CROP_ID_PATTERN = re.compile(r"^[0-9]+_row[0-9]+$")
MODEL_VERSION = "parisaocr-fa-0.1"
DETECTOR_MODEL = "ppocrv6-det-small.onnx"


@dataclass(frozen=True)
class NameRecognition:
    """Raw reading result from one crop; confidence uses the engine's 0..100 scale."""

    lines: tuple[str, ...]
    confidence: float | None

    def __post_init__(self) -> None:
        lines = tuple(self.lines)
        if any(not isinstance(line, str) for line in lines):
            raise TypeError("recognition lines must all be strings")
        object.__setattr__(self, "lines", lines)
        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
                raise TypeError("confidence must be a number from 0 to 100 or null")
            confidence = float(self.confidence)
            if not math.isfinite(confidence) or not 0.0 <= confidence <= 100.0:
                raise ValueError("confidence must be finite and between 0 and 100")
            object.__setattr__(self, "confidence", round(confidence, 4))


class NameSuggester(Protocol):
    """Small seam that keeps the optional engine outside the base candidate path."""

    engine_name: str
    engine_version: str
    model_version: str

    def suggest(self, crop_path: Path) -> NameRecognition:
        """Recognize a crop and return zero, one, or multiple ordered text lines."""


def _make_windows_resource_stub() -> types.ModuleType:
    """Supply only the POSIX import seam ParisaOCR evaluates on Windows.

    ParisaOCR 0.7.2 imports ``resource`` from its PDF-page module even when
    only the image-line API is used. The image-only wrapper never calls the
    PDF subprocess memory limiter; make an accidental call fail explicitly.
    """
    module = types.ModuleType("resource")
    module.RLIMIT_AS = 0

    def unsupported_setrlimit(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError(
            "ParisaOCR's PDF subprocess memory limit requires POSIX resource APIs")

    module.setrlimit = unsupported_setrlimit
    return module


@contextmanager
def _windows_resource_import_compatibility() -> Iterator[None]:
    """Temporarily satisfy ParisaOCR's unconditional POSIX-only module import."""
    if os.name != "nt" or "resource" in sys.modules:
        yield
        return
    shim = _make_windows_resource_stub()
    sys.modules["resource"] = shim
    try:
        yield
    finally:
        if sys.modules.get("resource") is shim:
            del sys.modules["resource"]


@dataclass(frozen=True)
class CropReference:
    crop_id: str
    file: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {"crop_id": self.crop_id, "file": self.file, "sha256": self.sha256}


@dataclass(frozen=True)
class NameSuggestion:
    """Suggestion provenance and output; acceptance is deliberately impossible here."""

    lines: tuple[str, ...]
    confidence: float | None
    engine: str
    engine_version: str
    model_version: str
    crop_reference: CropReference

    @property
    def suggested_name(self) -> str:
        """Join printed lines without flattening a two-line product name."""
        return "\n".join(self.lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggested_name": self.suggested_name,
            "lines": list(self.lines),
            "confidence": self.confidence,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "model_version": self.model_version,
            "crop_reference": self.crop_reference.to_dict(),
            "accepted": False,
        }


class ParisaOCRNameSuggester:
    """Lazy CPU-only wrapper around the ParisaOCR line-reading API."""

    engine_name = "ParisaOCR"
    model_version = MODEL_VERSION

    def __init__(self) -> None:
        started = time.perf_counter()
        try:
            import torch
            import parisaocr
            if os.name == "nt":
                # ParisaOCR 0.7.2's image-only API imports a PDF helper that
                # unconditionally imports POSIX ``resource``. The shim is
                # limited to API import; its PDF memory-limit operation fails
                # explicitly and is not part of this crop-only wrapper.
                with _windows_resource_import_compatibility():
                    from parisaocr import OCR
            else:
                from parisaocr import OCR
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(
                "install the optional, pinned N-04 ParisaOCR requirements") from exc

        # Match the measured N-01 execution mode and avoid oversubscribing a CPU runner.
        torch.set_num_threads(1)
        self.reader = OCR(cpu=True)
        self.engine_version = importlib.metadata.version("parisaocr")
        self.torch_version = str(torch.__version__)
        self.package_root = Path(parisaocr.__file__).resolve().parent
        self.recognizer_path = self.package_root / "models" / f"{MODEL_VERSION}.safetensors"
        self.detector_path = self.package_root / "models" / DETECTOR_MODEL
        if not self.recognizer_path.is_file() or not self.detector_path.is_file():
            raise FileNotFoundError("ParisaOCR's bundled local OCR model files are missing")
        self.recognizer_sha256 = _sha256(self.recognizer_path)
        self.detector_sha256 = _sha256(self.detector_path)
        # Includes PyTorch/ParisaOCR imports and loading both bundled models.
        self.initialization_seconds = time.perf_counter() - started

    def suggest(self, crop_path: Path) -> NameRecognition:
        lines = self.reader.lines(str(crop_path))
        text_lines: list[str] = []
        confidences: list[float] = []
        for line in lines:
            text = str(line.text)
            if text.strip():
                text_lines.append(text)
            if line.conf is not None:
                confidences.append(float(line.conf))
        confidence = sum(confidences) / len(confidences) if confidences else None
        return NameRecognition(tuple(text_lines), confidence)

    def provenance(self) -> dict[str, Any]:
        return {
            "engine": self.engine_name,
            "engine_version": self.engine_version,
            "model_version": self.model_version,
            "recognizer_file": self.recognizer_path.name,
            "recognizer_sha256": self.recognizer_sha256,
            "detector_file": self.detector_path.name,
            "detector_sha256": self.detector_sha256,
            "torch_version": self.torch_version,
            "device": "CPU",
            "torch_threads": 1,
            "network_downloads_during_inference": False,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_crop_path(repo_root: Path, crop_file: Any) -> tuple[str, str, Path]:
    if not isinstance(crop_file, str) or not crop_file:
        raise ValueError("reference_crop_file must be a non-empty repository-relative string")
    pure = PurePosixPath(crop_file)
    windows_path = PureWindowsPath(crop_file)
    if (pure.is_absolute() or windows_path.is_absolute() or windows_path.drive
            or ".." in pure.parts or ".." in windows_path.parts or "\\" in crop_file):
        raise ValueError("reference_crop_file must be a safe POSIX repository-relative path")
    crop_id = pure.stem
    if not CROP_ID_PATTERN.fullmatch(crop_id):
        raise ValueError(f"reference crop filename does not contain a valid crop ID: {crop_file!r}")
    root = repo_root.resolve()
    path = root.joinpath(*pure.parts).resolve()
    if not path.is_relative_to(root):
        raise ValueError("reference_crop_file resolves outside repo_root")
    return crop_id, pure.as_posix(), path


def enrich_product_candidates(
    source_document: dict[str, Any],
    repo_root: Path = ROOT,
    *,
    suggester: NameSuggester | None = None,
    inference_timings: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Add a ``name_suggestions`` list to every candidate without accepting one.

    With no engine supplied, every candidate still gets an explicit empty list;
    the base command remains OCR-free. With the opt-in engine, each candidate's
    representative crop receives one suggestion record, even when OCR returns
    no text (that record then has ``lines: []`` and ``confidence: null``).
    """
    if not isinstance(source_document, dict):
        raise TypeError("source_document must be an object")
    if source_document.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise ValueError(f"expected source schema {SOURCE_SCHEMA_VERSION!r}")
    source_candidates = source_document.get("candidates")
    if not isinstance(source_candidates, list):
        raise ValueError("source_document.candidates must be an array")
    if suggester is not None:
        for attribute in ("engine_name", "engine_version", "model_version", "suggest"):
            if not hasattr(suggester, attribute):
                raise TypeError(f"suggester must declare {attribute}")

    result = copy.deepcopy(source_document)
    result["source_schema_version"] = SOURCE_SCHEMA_VERSION
    result["schema_version"] = SCHEMA_VERSION
    result["name_suggestions_enabled"] = suggester is not None

    for candidate in result["candidates"]:
        if not isinstance(candidate, dict):
            raise ValueError("each source candidate must be an object")
        if "name_suggestions" in candidate:
            raise ValueError("source candidate already contains name_suggestions")
        candidate["name_suggestions"] = []
        if suggester is None:
            continue

        crop_id, crop_file, crop_path = _safe_crop_path(
            Path(repo_root), candidate.get("reference_crop_file"))
        if not crop_path.is_file():
            raise FileNotFoundError(f"missing candidate reference crop: {crop_file}")
        started = time.perf_counter()
        recognition = suggester.suggest(crop_path)
        elapsed = time.perf_counter() - started
        if not isinstance(recognition, NameRecognition):
            raise TypeError("suggester.suggest() must return NameRecognition")
        if inference_timings is not None:
            inference_timings[crop_id] = elapsed
        crop_ref = CropReference(
            crop_id=crop_id,
            file=crop_file,
            sha256=_sha256(crop_path),
        )
        suggestion = NameSuggestion(
            lines=recognition.lines,
            confidence=recognition.confidence,
            engine=str(suggester.engine_name),
            engine_version=str(suggester.engine_version),
            model_version=str(suggester.model_version),
            crop_reference=crop_ref,
        )
        candidate["name_suggestions"].append(suggestion.to_dict())

    return result


def build_name_suggestion_document(
    repo_root: Path = ROOT,
    *,
    suggester: NameSuggester | None = None,
    inference_timings: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build N-02 candidates then apply this optional N-04 enrichment."""
    try:
        from run_n02_product_candidates import build_product_candidates
    except ImportError as exc:  # pragma: no cover - invocation setup error
        raise RuntimeError("add src/ and scripts/ to PYTHONPATH") from exc
    base_document = build_product_candidates(
        Path(repo_root).resolve(), write_reference_crops=False)
    return enrich_product_candidates(
        base_document,
        Path(repo_root),
        suggester=suggester,
        inference_timings=inference_timings,
    )


def serialize_document(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
