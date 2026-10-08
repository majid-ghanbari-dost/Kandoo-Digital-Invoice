"""Mechanical page derivation & canonical reassembly — WP-2.1 MVP (SPEC-WP21-RC §5).

Delegated implementation detail (declared per D-09, OD-R2/OD-R4 in the task report):
  - Page derivation = total-consumption parse of the FROZEN aggregation framing
    (8-byte big-endian length-prefixed concatenation, list order — the canonical join
    frozen in WP-1.1 `CaptureService.aggregate`, v1.1-C3).
  - The parse is CONTENT-BLIND: it reads only length prefixes; page bytes are verbatim
    slices. No semantic/OCR/extraction interpretation of any kind (AC-2.1.2/AC-2.1.3).
  - Determinism: pure function of the byte sequence → same input, same page list, always.
  - Fallback rule: any byte sequence that does not parse as a complete non-empty chain
    (trailing < 8 bytes, declared length exceeding the remainder) is ONE page carrying
    the full artifact; the empty artifact is one empty page.
  - Canonical reassembly = the SAME frozen framing join applied to ordered page contents
    (uniform rule; for aggregate-format artifacts the reassembly is byte-identical to the
    source artifact).
"""
from __future__ import annotations

from typing import Iterable, List

from capture.service import CaptureService   # frozen WP-1.1 aggregation — behavior reuse

_AGG_HEADER = 8   # bytes — frozen by CaptureService.aggregate (v1.1-C3)


def derive_pages(artifact: bytes) -> List[bytes]:
    """Split a capture artifact into ordered page byte-slices (mechanical, total).

    Returns a non-empty list. Every returned slice is a verbatim sub-sequence of the
    artifact; a successful multi-part parse consumes the artifact exactly (tiling).
    """
    data = bytes(artifact)
    pages: List[bytes] = []
    i, n = 0, len(data)
    while i < n:
        if n - i < _AGG_HEADER:                    # incomplete header → single page
            return [data]
        length = int.from_bytes(data[i:i + _AGG_HEADER], "big")
        i += _AGG_HEADER
        if length > n - i:                         # declared length exceeds remainder → single page
            return [data]
        pages.append(data[i:i + length])           # verbatim slice — no transformation
        i += length
    if not pages:                                  # empty artifact → one empty page
        return [b""]
    return pages


def reassemble(pages: Iterable[bytes]) -> bytes:
    """Canonical join of ordered page contents — the FROZEN aggregation framing.

    Uniform for every document (no format special-casing): the document fingerprint is
    defined over exactly this byte sequence. Uses CaptureService.aggregate unchanged.
    """
    return CaptureService.aggregate(list(pages))
