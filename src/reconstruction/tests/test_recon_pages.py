"""Mechanical page derivation & canonical reassembly — determinism and tiling proofs.

Covers the delegated derivation rule (SPEC-WP21-RC §5): pure function of bytes,
content-blind, verbatim slices, total-consumption tiling, no heuristic.
"""
from capture import CaptureService

from reconstruction import derive_pages, reassemble


def test_aggregate_artifact_derives_original_parts_in_order():
    parts = [b"alpha-page;", b"beta-page;", b"gamma-page;"]
    artifact = CaptureService.aggregate(parts)
    assert derive_pages(artifact) == parts            # verbatim slices, list order


def test_derivation_is_deterministic_pure_function_of_bytes():
    parts = [b"x" * 40, b"", b"y" * 5]
    artifact = CaptureService.aggregate(parts)
    assert derive_pages(artifact) == derive_pages(artifact) == parts
    # same content rebuilt independently → identical page list
    assert derive_pages(CaptureService.aggregate(parts)) == parts


def test_single_part_aggregate_derives_that_part():
    artifact = CaptureService.aggregate([b"only-page"])
    assert derive_pages(artifact) == [b"only-page"]


def test_non_aggregate_artifacts_are_single_page_whole_artifact():
    for raw in (b"hello world", b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n", b"\x89PNG\r\n\x1a\nrest",
                b"ab", b"12345678", b"Invoice total: 100 USD"):
        assert derive_pages(raw) == [raw], raw


def test_empty_artifact_is_one_empty_page():
    assert derive_pages(b"") == [b""]


def test_truncated_framing_falls_back_to_single_page_deterministically():
    full = CaptureService.aggregate([b"aaaa", b"bbbb"])
    truncated = full[:-2]                              # torn tail — never a silent guess
    assert derive_pages(truncated) == [truncated]      # deterministic: whole = one page


def test_reassembly_is_exact_inverse_of_derivation_tiling():
    cases = [
        [b"p1", b"p2", b"p3"],
        [b""],                                          # empty single page
        [b"", b"nonempty", b""],                        # empty parts inside the chain
        [b"z" * 300],                                   # large part
        [b"in voice", b"page two", b"page three", b"p4"],
    ]
    for parts in cases:
        artifact = CaptureService.aggregate(parts)
        pages = derive_pages(artifact)
        assert reassemble(pages) == artifact            # tiling: canonical join == artifact
        assert b"".join(pages) == b"".join(parts)       # page bytes are verbatim, untransformed


def test_reassembly_uses_the_frozen_wp11_aggregation_join():
    pages = [b"a", b"bb", b"ccc"]
    assert reassemble(pages) == CaptureService.aggregate(pages)
