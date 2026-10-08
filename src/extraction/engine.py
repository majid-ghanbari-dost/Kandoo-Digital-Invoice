"""Extraction engine abstraction + deterministic reference engine — WP-3.1 MVP.

Engine-agnostic pipeline (T-3.1.2 scope):

  - `ExtractionEngine` is the REPLACEABLE abstraction (D-09: no OCR/VLM/engine selection
    is made here; the real production engine choice stays deferred). Any engine that
    implements the ABC can be registered in the pipeline; the pipeline neither knows nor
    cares which engine produced which fields.

  - Engine contract (enforced by the pipeline BEFORE anything persists):
      C1  deterministic — same input pages → same output list, always (no time/random/env)
      C2  every returned field has provenance == EXTRACTED (D-01; DERIVED/UNRESOLVED are
          NOT engine outputs)
      C3  every field's span names a page the engine was given: 0 <= page_index < len,
          0 <= byte_start <= byte_end <= that page's byte_len, and the span's
          page_fingerprint equals that page's fingerprint (the span anchors the page it
          claims)
      C4  verbatim binding — strict-decoding the span bytes with value_encoding reproduces
          value_verbatim exactly (no transformation happened inside the engine; that is
          P4 Normalization territory and is forbidden here)
      C5  explicit failure — a broken run raises ExtractionEngineError (or returns fewer
          fields only when the declared grammar says so); the engine never guesses.

  - `ReferenceDelimitedEngine` is ONE concrete engine (reference, not a product choice):
    a deterministic, stdlib-only parser for the declared `key=value` line grammar over
    UTF-8 page content. It exists so the pipeline is executable and testable end-to-end
    in the MVP; it is swappable through the ABC without any pipeline change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Sequence

from reconstruction import PageView

from .model import ExtractedField, Provenance, SourceSpan


class ExtractionEngineError(Exception):
    """Raised by an engine for its own explicit failure (e.g. undecodable content).
    The pipeline surfaces it as ExtractionEngineFailed — never swallowed."""


class ExtractionEngine(ABC):
    """The replaceable engine seam of the extraction pipeline (D-09-safe)."""

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Stable engine identity — part of the INV-X-1:1 uniqueness triple."""

    @property
    @abstractmethod
    def schema_version(self) -> str:
        """Version of the engine's output vocabulary/grammar — part of the triple."""

    @abstractmethod
    def extract_pages(self, pages: Sequence[PageView]) -> List[ExtractedField]:
        """Extract structured fields from the ordered verified pages.

        Returns the fields in deterministic order (field_seq is assigned by the pipeline
        afterwards — engines may leave it 0). MUST raise ExtractionEngineError on any
        run-level failure. MUST NOT mutate the pages; MUST NOT receive or use document/
        capture linkage (content-scoped by contract).
        """


class ReferenceDelimitedEngine(ExtractionEngine):
    """Reference engine: deterministic `key=value` line parser over UTF-8 pages.

    Declared grammar (engine_schema_version "1"):
      - page content MUST be valid UTF-8 (strict decode; anything else → explicit error)
      - lines are separated by b"\n" (LF); a trailing LF ends the last line
      - a line of the form  key=value  (first '=' separates; key non-empty, characters
        [A-Za-z0-9_.-] only) yields ONE field:
            field_name     = key (verbatim from the source)
            value_verbatim = the value part decoded as UTF-8 (may be empty)
            value_encoding = "utf-8"
            span           = byte offsets of the value part within the page
                             (byte_end excludes the LF)
      - every other line (empty, no '=', empty key, illegal key characters) yields NO
        field — declared grammar, deterministic, not an error
    """

    _KEY_OK = frozenset(b"abcdefghijklmnopqrstuvwxyz"
                        b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")   # byte values

    def __init__(self, engine_id: str = "reference-delimited-v1",
                 schema_version: str = "1") -> None:
        self._engine_id = engine_id
        self._schema_version = schema_version

    @property
    def engine_id(self) -> str:
        return self._engine_id

    @property
    def schema_version(self) -> str:
        return self._schema_version

    def extract_pages(self, pages: Sequence[PageView]) -> List[ExtractedField]:
        fields: List[ExtractedField] = []
        for page in pages:
            content = bytes(page.content)
            try:
                content.decode("utf-8")                   # strict — whole-page validity
            except UnicodeDecodeError as exc:
                raise ExtractionEngineError(
                    f"page {page.page_index} is not valid UTF-8: {exc}") from exc
            start = 0
            n = len(content)
            while start < n:
                nl = content.find(b"\n", start)
                line_end = n if nl == -1 else nl          # byte offset of LF (or EOF)
                self._extract_line(page, content, start, line_end, fields)
                start = line_end + 1
        return fields

    def _extract_line(self, page: PageView, content: bytes,
                      line_start: int, line_end: int,
                      fields: List[ExtractedField]) -> None:
        line = content[line_start:line_end]
        eq = line.find(b"=")
        if eq <= 0:                                       # no '=' or empty key → no field
            return
        key = line[:eq]
        if any(b not in self._KEY_OK for b in key):       # illegal key chars → no field
            return
        value_bytes = line[eq + 1:]
        try:
            value = value_bytes.decode("utf-8")           # strict — C4 verbatim binding
        except UnicodeDecodeError as exc:                 # defensive (whole page pre-validated)
            raise ExtractionEngineError(
                f"page {page.page_index}: value segment is not valid UTF-8: {exc}") from exc
        fields.append(ExtractedField(
            field_seq=0,                                  # pipeline assigns the final seq
            field_name=key.decode("ascii"),
            value_verbatim=value,
            value_encoding="utf-8",
            provenance=Provenance.EXTRACTED,
            span=SourceSpan(
                page_index=page.page_index,
                byte_start=line_start + eq + 1,
                byte_end=line_end,
                page_fingerprint=page.page_fingerprint,
            ),
        ))
