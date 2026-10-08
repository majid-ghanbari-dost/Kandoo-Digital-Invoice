"""Shared helpers for the WP-6.1 canonicalization-gate tests (unique module
name — safe for combined collection with the capture/reconstruction/extraction/
normalization/derivation/validation/validation_domain suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → canonicalization → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

VAL_TESTS = SRC / "validation" / "tests"
if str(VAL_TESTS) not in sys.path:
    sys.path.insert(0, str(VAL_TESTS))

VSM_TESTS = SRC / "validation_domain" / "tests"
if str(VSM_TESTS) not in sys.path:
    sys.path.insert(0, str(VSM_TESTS))

from capture import S1Service  # noqa: E402
from val_helpers import (  # noqa: E402  (P5.1 helpers reused verbatim)
    FORMULA,
    PAGE_OK,
    R_CONSIST,
    R_PRESENT,
    R_ROUNDED,
    R_TOLERANCE,
    TOLERANCE,
    PRECISION,
    MODE,
    ValidationStack,
)
from vsm_helpers import (  # noqa: E402  (P5.2 helpers reused verbatim)
    ValidationDomainStack,
    REF_KEYS,
    exact_probe_rule,
    nonexact_probe_rule,
    tolerance_probe_rule,
)
from canonicalization import (  # noqa: E402
    CanonicalizationAccepted,
    CanonicalizationGateService,
    CanonicalizationGateStore,
    ORIGIN_HOLOO_CAPTURE,
)

# Identity test corpus — the S2 triad rides on distinct, deterministic fields.
# invoice.number → text fallback; invoice.date → date kind; total.gross →
# decimal kind (derived). All three come out NORMALIZED in the verified read.
PAGE_IDENTITY_OK = [
    b"invoice.number=INV-CG-2026-001\ninvoice.date=2026-10-07\n"
    b"total.net=1000.00\ntax.amount=80\n",
]
PAGE_IDENTITY_TWIN = [
    b"invoice.date=2026-10-07\ninvoice.number=INV-CG-2026-001\n"
    b"tax.amount=80\ntotal.net=1000.00\n",
]   # same semantics, different byte order → DIFFERENT capture (different S1)
PAGE_IDENTITY_TWIN3 = [
    b"total.net=1000.00\ntax.amount=80\ninvoice.number=INV-CG-2026-001\n"
    b"invoice.date=2026-10-07\n",
]   # a third byte-ordering of the SAME identity values (distinct capture)
PAGE_IDENTITY_OTHER = [
    b"invoice.number=INV-CG-2026-002\ninvoice.date=2026-10-07\n"
    b"total.net=2500.00\ntax.amount=200\n",
]
PAGE_IDENTITY_NO_DATE = [
    b"invoice.number=INV-CG-2026-003\ntotal.net=500.00\ntax.amount=40\n",
]
PAGE_IDENTITY_AMBIGUOUS_NUMBER = [
    b"invoice.number=INV-AMBIG-A\ninvoice.number=INV-AMBIG-B\n"
    b"invoice.date=2026-10-07\ntotal.net=750.00\ntax.amount=60\n",
]
PAGE_IDENTITY_EMPTY_NUMBER = [
    b"invoice.number=\ninvoice.date=2026-10-07\n"
    b"total.net=300.00\ntax.amount=24\n",
]

_PAGE_SEQ = {"n": 0}


def unique_identity_pages(total_net="1000.00", tax="80"):
    """Distinct identity pages (unique invoice number) — each call produces a
    different capture S1, so multiple states can coexist in one test."""
    _PAGE_SEQ["n"] += 1
    return [f"invoice.number=INV-CG-SEQ-{_PAGE_SEQ['n']:04d}\n"
            f"invoice.date=2026-10-07\n"
            f"total.net={total_net}\ntax.amount={tax}\n".encode("utf-8")]


# The declared identity binding — the frozen D-02 roles → source field names.
# D-02 requires the S2 triad to be fully EXTRACTED ("کاملاً استخراج و تأیید
# شده") — so the total role binds the extracted total.net, not the DERIVED
# total.gross (the verified WP-4.1 read is the only sanctioned value path).
BINDING = {
    "INVOICE_NUMBER": "invoice.number",
    "INVOICE_DATE": "invoice.date",
    "INVOICE_TOTAL": "total.net",
}


class CanonicalizationStack(ValidationDomainStack):
    """The P5.2 composition PLUS the WP-6.1 gate store/service — the WP-6.1
    stack under test. All test-declared probe rules are pre-registered."""

    def __init__(self, capture_db, recon_db, extraction_db, binding_db,
                 norm_db, deriv_db, val_db, vsm_db, gate_db,
                 with_evidence=True, engines=None, rules=None,
                 extra_rules=(), formulas=None, norm_rulesets=None):
        probes = [
            exact_probe_rule(),
            nonexact_probe_rule(),
            tolerance_probe_rule(rule_id="vsm-probe-tolerance-absent",
                                 target_field="seller.vat"),
        ]
        extra_rules = tuple(extra_rules) + tuple(probes)
        super().__init__(capture_db, recon_db, extraction_db, binding_db,
                         norm_db, deriv_db, val_db, vsm_db,
                         with_evidence=with_evidence, engines=engines,
                         rules=rules, extra_rules=extra_rules,
                         formulas=formulas, norm_rulesets=norm_rulesets)
        self.gate_db = gate_db
        self.gate_store = CanonicalizationGateStore(gate_db, S1Service())
        self.gate = CanonicalizationGateService(
            self.gate_store, self.vsm, self.norm, S1Service())

    # -- pipeline helpers --------------------------------------------------

    def build_valid_identity_state(self, parts=None, label="cg-test",
                                   ruleset_id="kandoo-cg-rules",
                                   ruleset_version="1", keys=None):
        """Full happy path: capture → … → VALID/CLEAR domain state over the
        complete reference ruleset, with the identity fields present.
        Returns (normalization_id, projection_outcome)."""
        nid = self.build_derived(
            unique_identity_pages() if parts is None else parts, label=label)
        self.validate_all_reference(nid)
        projection = self.project(nid, keys or REF_KEYS,
                                  ruleset_id=ruleset_id,
                                  ruleset_version=ruleset_version)
        return nid, projection

    def canonicalize_ok(self, domain_state_id, origin=ORIGIN_HOLOO_CAPTURE,
                        binding=None):
        outcome = self.gate.canonicalize(
            domain_state_id, origin,
            BINDING if binding is None else binding)
        assert isinstance(outcome, CanonicalizationAccepted), outcome
        return outcome

    def close(self):
        self.gate_store.close()
        super().close()


def decisive_invalid_state(stack, parts=None, label="cg-decisive"):
    """INVALID/REJECT state: exact probe rule decisively violated
    (SUB(net,net)=0 vs tax.amount=80)."""
    nid = stack.build_normalization(
        unique_identity_pages() if parts is None else parts, label=label)
    outcome = stack.val.validate(nid, "vsm-probe-exact-mismatch", "1")
    assert type(outcome).__name__ == "ValidationCompleted", outcome
    assert outcome.record.outcome == "INVALID"
    projection = stack.project(nid, [("vsm-probe-exact-mismatch", "1")],
                               ruleset_id="cg-decisive-rules")
    return nid, projection


def tolerance_invalid_state(stack, parts=None, label="cg-tolerance"):
    """INVALID/REVIEW state: D-08 tolerance mismatch (T2 route) — the
    pre-registered tolerance probe decisively mismatches beyond tolerance."""
    nid = stack.build_normalization(
        unique_identity_pages() if parts is None else parts, label=label)
    outcome = stack.val.validate(nid, "vsm-probe-tolerance-mismatch", "1")
    assert type(outcome).__name__ == "ValidationCompleted", outcome
    assert outcome.record.outcome == "INVALID"
    assert outcome.record.outcome_reason == "mismatch-beyond-tolerance"
    projection = stack.project(nid, [("vsm-probe-tolerance-mismatch", "1")],
                               ruleset_id="cg-tolerance-rules")
    return nid, projection


def deferred_state(stack, parts=None, label="cg-deferred"):
    """DEFERRED/REVIEW state: non-exact intermediate (T4 route)."""
    if parts is None:
        _PAGE_SEQ["n"] += 1
        parts = [f"a=1.00\nb=3\nt=2.00\nz={_PAGE_SEQ['n']}\n"
                 .encode("utf-8")]
    nid = stack.build_normalization(parts, label=label)
    outcome = stack.val.validate(nid, "vsm-probe-nonexact", "1")
    assert type(outcome).__name__ == "ValidationCompleted", outcome
    projection = stack.project(nid, [("vsm-probe-nonexact", "1")],
                               ruleset_id="cg-deferred-rules")
    return nid, projection


def unresolved_state(stack, parts=None, label="cg-unresolved"):
    """UNRESOLVED/REVIEW state: D-01 order exhausted (T3 route) — the R2 rule
    input tax.amount has no usable EXTRACTED value and no DERIVED value."""
    if parts is None:
        _PAGE_SEQ["n"] += 1
        parts = [f"total.net=1000.00\nz={_PAGE_SEQ['n']}\n"
                 .encode("utf-8")]
    nid = stack.build_normalization(parts, label=label)
    outcome = stack.val.validate(nid, R_TOLERANCE, "1")
    assert type(outcome).__name__ == "ValidationCompleted", outcome
    projection = stack.project(nid, [(R_TOLERANCE, "1")],
                               ruleset_id="cg-unresolved-rules")
    return nid, projection
