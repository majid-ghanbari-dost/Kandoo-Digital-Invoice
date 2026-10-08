"""WP-12.1 generator tests — determinism, template coverage, label↔document
agreement, declared bounds (SPEC-WP121 §4/§5/§9)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import S1Service  # noqa: E402
from corpus import (  # noqa: E402
    LABEL_KIND_ABSENT,
    LABEL_KIND_VALUE,
    MARKING_SYNTHETIC,
    ORIGIN_SYNTHETIC,
    CorpusInputRefused,
    CorpusTemplateUnknown,
)
def _cents_of(canonical: str) -> int:
    """Integer-cents parse of a canonical decimal string (no float)."""
    whole, frac = canonical.split(".", 1)
    return int(whole) * 100 + int(frac)


def _cents_of_doc_euro(rendered: str) -> int:
    """Integer-cents parse of a document amount (canonical OR EURO-grouped)."""
    if "," in rendered:
        whole, frac = rendered.split(",", 1)
        return int(whole.replace(".", "")) * 100 + int(frac)
    return _cents_of(rendered)


from corpus.generator import (  # noqa: E402
    GENERATORS,
    TAX_RATE_DENOMINATOR,
    TAX_RATE_NUMERATOR,
    TEMPLATE_DATE,
    canonical_to_euro_grouped,
    cents_to_canonical,
    derive_entry_seed,
    expansion_bytes,
    generate_entry,
    manifest_canonical_bytes,
    entry_canonical_bytes,
    origin_and_marking,
    tax_cents_for,
)


# ---------------------------------------------------------------------------
# Deterministic expansion (OD-CA-B)
# ---------------------------------------------------------------------------

def test_expansion_deterministic_same_tag():
    s1 = S1Service()
    assert expansion_bytes(s1, "t|0", 32) == expansion_bytes(s1, "t|0", 32)


def test_expansion_depends_on_tag():
    s1 = S1Service()
    assert expansion_bytes(s1, "a", 32) != expansion_bytes(s1, "b", 32)


def test_expansion_prefix_property():
    """Longer requests extend the same chain (counter-tagged digests)."""
    s1 = S1Service()
    assert expansion_bytes(s1, "k", 64)[:32] == expansion_bytes(s1, "k", 32)


def test_expansion_refuses_bad_args():
    s1 = S1Service()
    for tag, n in (("", 8), (None, 8), ("t", -1), ("t", "x")):
        try:
            expansion_bytes(s1, tag, n)
            raise AssertionError(f"expansion accepted {tag!r}/{n!r}")
        except CorpusInputRefused:
            pass


def test_entry_seed_deterministic_and_in_range():
    s1 = S1Service()
    a = derive_entry_seed(s1, "t", 5, 9, 3)
    assert a == derive_entry_seed(s1, "t", 5, 9, 3)
    assert 0 <= a <= 0x7FFFFFFFFFFFFFFF


# ---------------------------------------------------------------------------
# Amount arithmetic (OD-CA-C — integer cents, HALF_UP)
# ---------------------------------------------------------------------------

def test_cents_to_canonical_shapes():
    assert cents_to_canonical(0) == "0.00"
    assert cents_to_canonical(1) == "0.01"
    assert cents_to_canonical(100) == "1.00"
    assert cents_to_canonical(1965675) == "19656.75"


def test_tax_matches_exact_half_up_over_sweep():
    """tax = net * (8/100) — the declared template rate. The implementation
    must equal exact rational HALF_UP over the whole sweep (integer-cents
    arithmetic, no float anywhere)."""
    from fractions import Fraction
    for net in range(1, 5000):
        exact = Fraction(net * TAX_RATE_NUMERATOR, TAX_RATE_DENOMINATOR)
        expected = int(exact + Fraction(1, 2))     # HALF_UP floor for positives
        assert tax_cents_for(net) == expected


def test_euro_grouping_round_trip_shape():
    assert canonical_to_euro_grouped("12345.67") == "12.345,67"
    assert canonical_to_euro_grouped("1000.00") == "1.000,00"
    assert canonical_to_euro_grouped("1000000.99") == "1.000.000,99"


def test_euro_grouping_refuses_short_integer_parts():
    for value in ("1.00", "99.99", "999.99"):
        try:
            canonical_to_euro_grouped(value)
            raise AssertionError(f"EURO rendering accepted {value!r}")
        except CorpusInputRefused:
            pass


# ---------------------------------------------------------------------------
# Templates (SPEC §4)
# ---------------------------------------------------------------------------

def test_template_registry_exact():
    assert set(GENERATORS) == {
        "kv-invoice-clean-v1",
        "kv-invoice-rounding-probe-v1",
        "kv-invoice-review-probe-v1",
    }


def test_origin_and_marking_are_the_synthetic_pair():
    assert origin_and_marking() == (ORIGIN_SYNTHETIC, MARKING_SYNTHETIC)


def test_unknown_template_refused():
    s1 = S1Service()
    try:
        generate_entry(s1, "kv-invoice-nonexistent", 0, 9, 0)
        raise AssertionError("unknown template accepted")
    except CorpusTemplateUnknown:
        pass


def test_clean_template_shape_and_label_agreement():
    s1 = S1Service()
    parts, labels, seed = generate_entry(s1, "kv-invoice-clean-v1", 77, 9, 0)
    assert seed == derive_entry_seed(s1, "kv-invoice-clean-v1", 77, 9, 0)
    assert len(parts) == 1 and isinstance(parts[0], bytes)
    doc = dict(
        line.split("=", 1) for line in parts[0].decode("utf-8").strip().split("\n"))
    by_name = {label.field_name: label for label in labels}
    assert doc["invoice.date"] == TEMPLATE_DATE
    for field in ("invoice.number", "invoice.date", "total.net", "tax.amount"):
        assert by_name[field].kind == LABEL_KIND_VALUE
        if field == "total.net" and "," in doc[field]:
            # EURO-variant document: the LABEL stays canonical by design
            whole, frac = doc[field].split(",", 1)
            assert by_name[field].expected_value == \
                f"{whole.replace('.', '')}.{frac}"
        else:
            assert by_name[field].expected_value == doc[field]
    # the clean template prints NO gross line (the frozen derivation's
    # output-present gate must stay disengaged on the clean path)
    assert "total.gross" not in doc
    assert "total.gross" not in by_name
    assert tax_cents_for(_cents_of_doc_euro(doc["total.net"])) \
        == _cents_of(doc["tax.amount"])


def test_rounding_probe_prints_a_gross_line():
    s1 = S1Service()
    parts, labels, _seed = generate_entry(
        s1, "kv-invoice-rounding-probe-v1", 3, 8, 0)
    doc_text = parts[0].decode("utf-8")
    assert "total.gross=" in doc_text
    assert {l.field_name for l in labels} == {
        "invoice.number", "invoice.date", "total.net", "tax.amount",
        "total.gross"}


def test_clean_template_deterministic_independent_repeat():
    s1 = S1Service()
    first = generate_entry(s1, "kv-invoice-clean-v1", 123, 9, 4)
    second = generate_entry(s1, "kv-invoice-clean-v1", 123, 9, 4)
    assert first[0] == second[0]
    assert first[1] == second[1]
    assert first[2] == second[2]


def test_distinct_ordinals_produce_distinct_documents():
    s1 = S1Service()
    docs = set()
    for ordinal in range(8):
        parts, _labels, _seed = generate_entry(
            s1, "kv-invoice-clean-v1", 9, 8, ordinal)
        docs.add(parts[0])
    assert len(docs) == 8


def test_distinct_seed_bases_produce_distinct_documents():
    s1 = S1Service()
    a = generate_entry(s1, "kv-invoice-clean-v1", 1, 8, 0)[0]
    b = generate_entry(s1, "kv-invoice-clean-v1", 2, 8, 0)[0]
    assert a != b


def test_clean_template_euro_variant_when_declared():
    """Seed-gated EURO rendering: the DOCUMENT may carry `1.234,56` while the
    LABEL stays canonical `1234.56` (normalization is exercised downstream —
    the ground truth never changes)."""
    s1 = S1Service()
    seen_euro = False
    for seed_base in range(200):
        parts, labels, _seed = generate_entry(
            s1, "kv-invoice-clean-v1", seed_base, 8, 0)
        doc = dict(
            line.split("=", 1) for line in parts[0].decode("utf-8").strip().split("\n"))
        net_label = {l.field_name: l for l in labels}["total.net"]
        if "," in doc["total.net"]:
            seen_euro = True
            # label is canonical, document is EURO-grouped — same value
            assert _cents_of(net_label.expected_value) * 10000 == \
                _cents_of_doc_euro(doc["total.net"]) * 10000
            assert _cents_of(net_label.expected_value) == \
                _cents_of_doc_euro(doc["total.net"])
            # document value must be inside the declared EURO grammar shape
            whole = doc["total.net"].split(",")[0]
            assert len(whole.replace(".", "")) >= 4
    assert seen_euro, "seed sweep never produced the EURO variant"


def test_rounding_probe_declares_printed_gross_with_residual():
    s1 = S1Service()
    residuals = set()
    for seed_base in range(60):
        parts, labels, _seed = generate_entry(
            s1, "kv-invoice-rounding-probe-v1", seed_base, 8, 1)
        doc = dict(
            line.split("=", 1) for line in parts[0].decode("utf-8").strip().split("\n"))
        by_name = {l.field_name: l for l in labels}
        assert by_name["total.gross"].expected_value == doc["total.gross"]
        net = _cents_of_doc_euro(doc["total.net"])
        tax = _cents_of(doc["tax.amount"])
        gross = _cents_of(doc["total.gross"])
        residual = gross - (net + tax)
        assert residual in (-2, -1, 1, 2)          # the D-08 surface
        assert residual != 0                        # never silently consistent
        residuals.add(residual)
    assert len(residuals) >= 2, "residual vocabulary never varied"


def test_review_probe_declares_absent_tax():
    s1 = S1Service()
    parts, labels, _seed = generate_entry(s1, "kv-invoice-review-probe-v1", 5, 8, 0)
    doc_text = parts[0].decode("utf-8")
    assert "tax.amount" not in doc_text
    by_name = {label.field_name: label for label in labels}
    assert by_name["tax.amount"].kind == LABEL_KIND_ABSENT
    assert by_name["tax.amount"].expected_value is None
    assert by_name["invoice.number"].kind == LABEL_KIND_VALUE
    assert by_name["total.net"].kind == LABEL_KIND_VALUE
    assert "total.gross" not in by_name             # no declared gross either


def test_review_probe_carries_no_gross_label():
    s1 = S1Service()
    for seed_base in range(10):
        _parts, labels, _seed = generate_entry(
            s1, "kv-invoice-review-probe-v1", seed_base, 8, 3)
        assert all(l.field_name != "total.gross" for l in labels)


# ---------------------------------------------------------------------------
# Canonical serialization (SPEC §5)
# ---------------------------------------------------------------------------

def test_entry_canonical_bytes_order_sensitive():
    from corpus.model import CorpusLabel
    s1 = S1Service()
    labels_a = (CorpusLabel("a.f", LABEL_KIND_VALUE, "1"),
                CorpusLabel("b.f", LABEL_KIND_VALUE, "2"))
    labels_b = (CorpusLabel("b.f", LABEL_KIND_VALUE, "2"),
                CorpusLabel("a.f", LABEL_KIND_VALUE, "1"))
    fp_a = s1.compute(entry_canonical_bytes("t", 1, 0, (b"x",), labels_a,
                                            ORIGIN_SYNTHETIC,
                                            MARKING_SYNTHETIC)).s1
    fp_b = s1.compute(entry_canonical_bytes("t", 1, 0, (b"x",), labels_b,
                                            ORIGIN_SYNTHETIC,
                                            MARKING_SYNTHETIC)).s1
    assert fp_a == fp_b          # label order is canonicalized (sorted)
    fp_c = s1.compute(entry_canonical_bytes("t", 1, 0, (b"y",), labels_a,
                                            ORIGIN_SYNTHETIC,
                                            MARKING_SYNTHETIC)).s1
    assert fp_a != fp_c          # content sensitivity


def test_entry_fingerprint_is_content_sensitive_single_byte():
    from corpus.model import CorpusLabel
    s1 = S1Service()
    labels = (CorpusLabel("a.f", LABEL_KIND_VALUE, "1"),)
    fp1 = s1.compute(entry_canonical_bytes("t", 1, 0, (b"x\x00",), labels,
                                           ORIGIN_SYNTHETIC,
                                           MARKING_SYNTHETIC)).s1
    fp2 = s1.compute(entry_canonical_bytes("t", 1, 0, (b"x\x01",), labels,
                                           ORIGIN_SYNTHETIC,
                                           MARKING_SYNTHETIC)).s1
    assert fp1 != fp2


def test_manifest_bytes_order_and_count_sensitive():
    s1 = S1Service()
    base = manifest_canonical_bytes("t", 0, 2, [(0, "f0" * 32), (1, "f1" * 32)],
                                    ORIGIN_SYNTHETIC, MARKING_SYNTHETIC)
    reordered = manifest_canonical_bytes("t", 0, 2, [(1, "f1" * 32), (0, "f0" * 32)],
                                         ORIGIN_SYNTHETIC, MARKING_SYNTHETIC)
    assert base == reordered       # manifest ordering is canonicalized
    mutated = manifest_canonical_bytes("t", 0, 2, [(0, "ff" * 32), (1, "f1" * 32)],
                                       ORIGIN_SYNTHETIC, MARKING_SYNTHETIC)
    assert base != mutated


def test_manifest_bytes_reject_out_of_range_values():
    for args in (
        ("t", -1, 1, [], ORIGIN_SYNTHETIC, MARKING_SYNTHETIC),
        ("t", 0, -1, [], ORIGIN_SYNTHETIC, MARKING_SYNTHETIC),
        ("t", 0, 1, [(1 << 64, "f" * 32)], ORIGIN_SYNTHETIC, MARKING_SYNTHETIC),
    ):
        try:
            manifest_canonical_bytes(*args)
            raise AssertionError(f"manifest bytes accepted {args!r}")
        except CorpusInputRefused:
            pass


def test_malformed_labels_refused():
    from corpus.model import CorpusLabel
    for labels in (
        (CorpusLabel("a", LABEL_KIND_VALUE, None),),
        (CorpusLabel("a", LABEL_KIND_ABSENT, "x"),),
        (CorpusLabel("a", "OTHER", "x"),),
        (CorpusLabel("a", LABEL_KIND_VALUE, "1"),
         CorpusLabel("a", LABEL_KIND_VALUE, "2")),   # duplicate field_name
    ):
        try:
            entry_canonical_bytes("t", 1, 0, (b"x",), labels,
                                  ORIGIN_SYNTHETIC, MARKING_SYNTHETIC)
            raise AssertionError(f"malformed labels accepted: {labels!r}")
        except CorpusInputRefused:
            pass
