"""Deterministic canonical serialization + SYNTHETIC template generators —
WP-12.1 (SPEC-WP121-CORPUS §4/§5).

Entropy discipline (OD-CA-B): all per-entry variation is derived from
iterated S1 digests over counter-tagged byte strings. No `random`, no
direct digest use, no time, no environment. Amounts are integer cents
(OD-CA-C); documents carry canonical decimal strings; the EURO-GROUPING
rendering variant is a declared, seed-gated formatting of the SAME
canonical value (the label stays the canonical form).

Every entry is a pure function of the FULL declaration: (template_id,
seed_base, entry_count, ordinal) — two different declarations never share
an entry, so UNIQUE(entry_fingerprint) holds across versions of one store.

The generators are corpus MATERIAL production — the corpus layer's own
declared templates. They run the frozen pipeline nowhere and decide nothing.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from capture import S1Service

from .model import (
    LABEL_KIND_ABSENT,
    LABEL_KIND_VALUE,
    MARKING_SYNTHETIC,
    ORIGIN_SYNTHETIC,
    CorpusInputRefused,
    CorpusLabel,
    CorpusTemplateUnknown,
)

# Fixed declared template date (OD-CA-G) — away from every known corpus
# date and from the documented date-sensitive flake window (the UTC day the
# P10/P11 regressions ran on; see the REG-AR WP-7.2 flake note).
TEMPLATE_DATE = "2026-06-15"

# Declared tax rate (OD-CA-C) — template-level declaration, NOT a calibrated
# parameter; it shapes synthetic material only and ratifies nothing.
TAX_RATE_NUMERATOR = 8      # 0.08 as 8/100 — integer-only arithmetic
TAX_RATE_DENOMINATOR = 100


# ---------------------------------------------------------------------------
# Deterministic expansion (S1-digest counter chains — no random module)
# ---------------------------------------------------------------------------

def expansion_bytes(s1: S1Service, tag: str, n_bytes: int) -> bytes:
    """n_bytes of deterministic material from S1 digests of `tag|counter`."""
    if not isinstance(tag, str) or not tag:
        raise CorpusInputRefused("expansion tag must be a non-empty string")
    if not isinstance(n_bytes, int) or n_bytes < 0:
        raise CorpusInputRefused("expansion byte count must be a non-negative int")
    out = bytearray()
    counter = 0
    while len(out) < n_bytes:
        digest = s1.compute(f"{tag}|{counter}".encode("utf-8")).s1
        out += bytes.fromhex(digest)
        counter += 1
    return bytes(out[:n_bytes])


def derive_entry_seed(s1: S1Service, template_id: str, seed_base: int,
                      entry_count: int, ordinal: int) -> int:
    """Per-entry seed — 8 bytes of the full-declaration expansion chain,
    masked to 63 bits (SQLite INTEGER is signed 64-bit; the store CHECK pins
    seed >= 0). Depends on the FULL declaration so distinct corpora never
    share an entry."""
    material = expansion_bytes(
        s1, f"seed:{template_id}:{seed_base}:{entry_count}:{ordinal}", 8)
    return int.from_bytes(material, "big") & 0x7FFFFFFFFFFFFFFF


# ---------------------------------------------------------------------------
# Canonical serialization (SPEC §5 — 8-byte big-endian LP, fixed order)
# ---------------------------------------------------------------------------

def _lp(payload: bytes) -> bytes:
    return len(payload).to_bytes(8, "big") + payload


def _u64(value: int) -> bytes:
    if not isinstance(value, int) or value < 0 or value > 0xFFFFFFFFFFFFFFFF:
        raise CorpusInputRefused(f"value out of u64 range: {value!r}")
    return value.to_bytes(8, "big")


def entry_canonical_bytes(template_id: str, entry_seed: int, ordinal: int,
                          parts: Tuple[bytes, ...], labels: Tuple[CorpusLabel, ...],
                          origin_role: str, marking: str) -> bytes:
    """The canonical entry serialization — the fingerprint's byte-exact basis."""
    if not isinstance(template_id, str) or not template_id:
        raise CorpusInputRefused("template_id must be a non-empty string")
    out = bytearray(b"kandoo-corpus-entry-v1")
    out += _lp(template_id.encode("utf-8"))
    out += _u64(entry_seed)
    out += _u64(ordinal)
    out += _u64(len(parts))
    for part in parts:
        if not isinstance(part, (bytes, bytearray)):
            raise CorpusInputRefused("entry parts must be byte sequences")
        out += _lp(bytes(part))
    ordered = _sorted_labels(labels)
    out += _u64(len(ordered))
    for label in ordered:
        out += _lp(label.field_name.encode("utf-8"))
        out += (b"\x01" if label.kind == LABEL_KIND_ABSENT else b"\x00")
        out += _lp((label.expected_value or "").encode("utf-8"))
        out += _lp(label.label_provenance.encode("utf-8"))
    out += _lp(origin_role.encode("utf-8"))
    out += _lp(marking.encode("utf-8"))
    return bytes(out)


def manifest_canonical_bytes(template_id: str, seed_base: int, entry_count: int,
                             entry_fingerprints: List[Tuple[int, str]],
                             origin_role: str, marking: str) -> bytes:
    """The canonical manifest serialization — the corpus version address basis."""
    out = bytearray(b"kandoo-corpus-manifest-v1")
    out += _lp(template_id.encode("utf-8"))
    out += _u64(seed_base)
    out += _u64(entry_count)
    ordered = sorted(entry_fingerprints, key=lambda pair: pair[0])
    out += _u64(len(ordered))
    for ordinal, fingerprint in ordered:
        out += _u64(ordinal)
        out += _lp(fingerprint.encode("utf-8"))
    out += _lp(origin_role.encode("utf-8"))
    out += _lp(marking.encode("utf-8"))
    return bytes(out)


def _sorted_labels(labels: Tuple[CorpusLabel, ...]) -> Tuple[CorpusLabel, ...]:
    names = [label.field_name for label in labels]
    if len(set(names)) != len(names):
        raise CorpusInputRefused("duplicate label field_name in one entry")
    for label in labels:
        if label.kind not in (LABEL_KIND_VALUE, LABEL_KIND_ABSENT):
            raise CorpusInputRefused(f"unknown label kind: {label.kind!r}")
        if label.kind == LABEL_KIND_VALUE and not (
                isinstance(label.expected_value, str) and label.expected_value):
            raise CorpusInputRefused(
                f"VALUE label for {label.field_name!r} needs a non-empty expected_value")
        if label.kind == LABEL_KIND_ABSENT and label.expected_value is not None:
            raise CorpusInputRefused(
                f"ABSENT label for {label.field_name!r} must carry no expected_value")
    return tuple(sorted(labels, key=lambda label: label.field_name))


# ---------------------------------------------------------------------------
# Amount rendering (integer cents only — OD-CA-C)
# ---------------------------------------------------------------------------

def cents_to_canonical(cents: int) -> str:
    """Integer cents → canonical decimal string (R-D1 canonical form)."""
    if not isinstance(cents, int) or cents < 0:
        raise CorpusInputRefused(f"cents must be a non-negative int, got {cents!r}")
    whole, frac = divmod(cents, 100)
    return f"{whole}.{frac:02d}"


def canonical_to_euro_grouped(canonical: str) -> str:
    """Canonical decimal string → EURO-GROUPING rendering (R-D1 grammar shape
    `1.234,56`), declared for integer parts ≥ 4 digits only. Pure formatting
    of an already-canonical value — the ground truth does not change."""
    whole, frac = canonical.split(".", 1)
    if len(whole) < 4:
        raise CorpusInputRefused(
            f"EURO rendering declared for integer parts >= 4 digits, got {canonical!r}")
    grouped = f"{int(whole):,}".replace(",", ".")
    return f"{grouped},{frac}"


def tax_cents_for(net_cents: int) -> int:
    """Declared rate over integer cents — HALF_UP at the cent boundary."""
    return (net_cents * TAX_RATE_NUMERATOR * 2 + TAX_RATE_DENOMINATOR) \
        // (2 * TAX_RATE_DENOMINATOR)


# ---------------------------------------------------------------------------
# Declared templates (SPEC §4) — each returns (parts, labels)
# ---------------------------------------------------------------------------

def _document_bytes(invoice_number: str, net_cents: int, tax_cents: int,
                    gross_cents: int, euro_net: bool) -> bytes:
    net_canonical = cents_to_canonical(net_cents)
    net_rendered = canonical_to_euro_grouped(net_canonical) if euro_net \
        else net_canonical
    lines = [
        f"invoice.number={invoice_number}",
        f"invoice.date={TEMPLATE_DATE}",
        f"total.net={net_rendered}",
        f"tax.amount={cents_to_canonical(tax_cents)}",
        f"total.gross={cents_to_canonical(gross_cents)}",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _base_labels(invoice_number: str, net_cents: int, tax_cents: int,
                 gross_cents: int) -> List[CorpusLabel]:
    return [
        CorpusLabel("invoice.date", LABEL_KIND_VALUE, TEMPLATE_DATE),
        CorpusLabel("invoice.number", LABEL_KIND_VALUE, invoice_number),
        CorpusLabel("total.gross", LABEL_KIND_VALUE,
                    cents_to_canonical(gross_cents)),
        CorpusLabel("total.net", LABEL_KIND_VALUE, cents_to_canonical(net_cents)),
        CorpusLabel("tax.amount", LABEL_KIND_VALUE, cents_to_canonical(tax_cents)),
    ]


def _gen_clean(s1: S1Service, tag: str, ordinal: int) \
        -> Tuple[Tuple[bytes, ...], Tuple[CorpusLabel, ...]]:
    """Well-formed invoice WITHOUT a printed gross line — the pipeline's
    reference derivation computes total.gross (a document-printed gross
    would engage the frozen output-present gate and route the entry to the
    uncertainty path instead)."""
    material = expansion_bytes(s1, f"doc:{tag}:{ordinal}", 16)
    number = f"INV-CORPUS-{tag}-{ordinal:06d}"
    net_cents = 10_000 + int.from_bytes(material[0:4], "big") % 9_900_000
    tax_cents = tax_cents_for(net_cents)
    euro_net = bool(material[15] & 0x01) and net_cents >= 100_000
    lines = [
        f"invoice.number={number}",
        f"invoice.date={TEMPLATE_DATE}",
        f"total.net={canonical_to_euro_grouped(cents_to_canonical(net_cents)) if euro_net else cents_to_canonical(net_cents)}",
        f"tax.amount={cents_to_canonical(tax_cents)}",
    ]
    parts = (("\n".join(lines) + "\n").encode("utf-8"),)
    labels = (
        CorpusLabel("invoice.date", LABEL_KIND_VALUE, TEMPLATE_DATE),
        CorpusLabel("invoice.number", LABEL_KIND_VALUE, number),
        CorpusLabel("total.net", LABEL_KIND_VALUE, cents_to_canonical(net_cents)),
        CorpusLabel("tax.amount", LABEL_KIND_VALUE, cents_to_canonical(tax_cents)),
    )
    return parts, labels


def _gen_rounding_probe(s1: S1Service, tag: str, ordinal: int) \
        -> Tuple[Tuple[bytes, ...], Tuple[CorpusLabel, ...]]:
    """Declared gross deviates from net + tax by a seed-derived ±1/±2-cent
    residual — the D-08 calibration surface (the label declares the PRINTED
    values verbatim; nothing is corrected)."""
    material = expansion_bytes(s1, f"doc:{tag}:{ordinal}", 16)
    number = f"INV-CORPUS-RP-{tag}-{ordinal:06d}"
    net_cents = 10_000 + int.from_bytes(material[0:4], "big") % 9_900_000
    tax_cents = tax_cents_for(net_cents)
    sign = -1 if material[14] & 0x01 else 1
    residual = sign * (1 + (material[13] & 0x01))        # ±1 or ±2 cents
    gross_cents = net_cents + tax_cents + residual       # printed gross disagrees
    euro_net = bool(material[15] & 0x01) and net_cents >= 100_000
    parts = (_document_bytes(number, net_cents, tax_cents, gross_cents, euro_net),)
    labels = _base_labels(number, net_cents, tax_cents, gross_cents)
    return parts, tuple(labels)


def _gen_review_probe(s1: S1Service, tag: str, ordinal: int) \
        -> Tuple[Tuple[bytes, ...], Tuple[CorpusLabel, ...]]:
    """tax.amount line ABSENT — the downstream uncertainty route (D-01/D-08
    territory). The absent field is a declared ABSENT label."""
    material = expansion_bytes(s1, f"doc:{tag}:{ordinal}", 16)
    number = f"INV-CORPUS-RV-{tag}-{ordinal:06d}"
    net_cents = 10_000 + int.from_bytes(material[0:4], "big") % 9_900_000
    lines = [
        f"invoice.number={number}",
        f"invoice.date={TEMPLATE_DATE}",
        f"total.net={cents_to_canonical(net_cents)}",
    ]
    parts = (("\n".join(lines) + "\n").encode("utf-8"),)
    labels = (
        CorpusLabel("invoice.date", LABEL_KIND_VALUE, TEMPLATE_DATE),
        CorpusLabel("invoice.number", LABEL_KIND_VALUE, number),
        CorpusLabel("total.net", LABEL_KIND_VALUE, cents_to_canonical(net_cents)),
        CorpusLabel("tax.amount", LABEL_KIND_ABSENT, None),
    )
    return parts, labels


GENERATORS: Dict[str, object] = {
    "kv-invoice-clean-v1": _gen_clean,
    "kv-invoice-rounding-probe-v1": _gen_rounding_probe,
    "kv-invoice-review-probe-v1": _gen_review_probe,
}


def generate_entry(s1: S1Service, template_id: str, seed_base: int,
                   entry_count: int, ordinal: int) \
        -> Tuple[Tuple[bytes, ...], Tuple[CorpusLabel, ...], int]:
    """One declared template invocation — deterministic in the FULL
    declaration (template, seed_base, entry_count, ordinal). Unknown
    template → typed refusal (fail-closed)."""
    generator = GENERATORS.get(template_id)
    if generator is None:
        raise CorpusTemplateUnknown(
            f"unknown corpus template_id: {template_id!r} "
            f"(declared: {', '.join(sorted(GENERATORS))})")
    tag = f"{template_id}:{seed_base}:{entry_count}"
    entry_seed = derive_entry_seed(s1, template_id, seed_base, entry_count,
                                   ordinal)
    parts, labels = generator(s1, tag, ordinal)
    return parts, labels, entry_seed


def origin_and_marking() -> Tuple[str, str]:
    """The only origin/marking pair this layer can produce (SPEC §2.1)."""
    return ORIGIN_SYNTHETIC, MARKING_SYNTHETIC
