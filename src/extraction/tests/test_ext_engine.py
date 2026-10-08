"""Reference engine tests — determinism, verbatim span binding, declared grammar,
explicit failure (SPEC-WP31-EXT §3; engine contract C1/C4/C5)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from reconstruction import PageView  # noqa: E402

from ext_helpers import PAGE_TEXTS  # noqa: E402
from extraction import ReferenceDelimitedEngine, ExtractionEngineError  # noqa: E402

import hashlib  # noqa: E402


def _page_view(index: int, content: bytes) -> PageView:
    return PageView(page_index=index, content=content, byte_len=len(content),
                    page_fingerprint=hashlib.sha256(content).hexdigest(),
                    fingerprint_algorithm_id="sha256-v1")


def test_reference_engine_is_deterministic_pure_function_of_pages():
    engine = ReferenceDelimitedEngine()
    pages = [_page_view(i, t) for i, t in enumerate(PAGE_TEXTS)]
    first = engine.extract_pages(pages)
    second = engine.extract_pages(pages)
    assert [(f.field_name, f.value_verbatim, f.span) for f in first] == \
           [(f.field_name, f.value_verbatim, f.span) for f in second]


def test_fields_are_verbatim_and_spans_point_at_exact_value_bytes():
    engine = ReferenceDelimitedEngine()
    pages = [_page_view(i, t) for i, t in enumerate(PAGE_TEXTS)]
    fields = engine.extract_pages(pages)
    assert len(fields) == 6                      # 2 + 3 + 1
    for field in fields:
        page = pages[field.span.page_index]
        span_bytes = bytes(page.content)[field.span.byte_start:field.span.byte_end]
        assert span_bytes.decode(field.value_encoding) == field.value_verbatim
        assert field.span.page_fingerprint == page.page_fingerprint
    assert fields[0].field_name == "invoice.number"
    assert fields[0].value_verbatim == "INV-2024-001"
    assert fields[1].value_verbatim == "2026-10-01"


def test_page_index_binding_and_multi_page_field_order():
    engine = ReferenceDelimitedEngine()
    pages = [_page_view(i, t) for i, t in enumerate(PAGE_TEXTS)]
    fields = engine.extract_pages(pages)
    assert [f.span.page_index for f in fields] == [0, 0, 1, 1, 1, 2]
    assert [f.field_name for f in fields] == [
        "invoice.number", "invoice.date", "seller.name", "total.gross",
        "currency.label", "notes"]
    # span offsets are page-local and strictly increasing within a page
    assert fields[0].span.byte_start < fields[0].span.byte_end <= len(PAGE_TEXTS[0])
    assert fields[2].span.byte_start < fields[3].span.byte_start


def test_declared_grammar_edges_empty_values_non_key_lines_no_trailing_lf():
    engine = ReferenceDelimitedEngine()
    content = (b"empty.value=\n"            # empty value → field with ""
               b"\n"                        # empty line → no field
               b"no-key-sign\n"             # no '=' → no field
               b"=orphan\n"                 # empty key → no field
               b"bad$key=x\n"               # illegal key chars → no field
               b"last=final")               # no trailing LF → still extracted
    fields = engine.extract_pages([_page_view(0, content)])
    assert [(f.field_name, f.value_verbatim) for f in fields] == [
        ("empty.value", ""), ("last", "final")]
    last = fields[-1]
    assert last.span.byte_end == len(content)          # EOF-terminated line
    empty = fields[0]
    assert empty.span.byte_start == empty.span.byte_end  # empty value span


def test_undecodable_page_fails_explicitly_never_guesses():
    engine = ReferenceDelimitedEngine()
    with pytest.raises(ExtractionEngineError) as excinfo:
        engine.extract_pages([_page_view(0, b"name=\xff\xfe\x90")])
    assert "not valid UTF-8" in str(excinfo.value)


def test_engine_identity_is_declared_and_stable():
    engine = ReferenceDelimitedEngine()
    assert engine.engine_id == "reference-delimited-v1"
    assert engine.schema_version == "1"
    alt = ReferenceDelimitedEngine(engine_id="reference-delimited-v1-alt")
    assert alt.engine_id == "reference-delimited-v1-alt" and alt.schema_version == "1"
