"""Shared helpers for the WP-7.2 duplicate-flows tests (unique module name —
safe for combined collection with all prior suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → duplicate_flows → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

IR_TESTS = SRC / "identity_resolution" / "tests"
if str(IR_TESTS) not in sys.path:
    sys.path.insert(0, str(IR_TESTS))

from ir_helpers import (      # noqa: E402  (WP-7.1 helpers reused verbatim)
    IdentityResolutionStack,
    BINDING,
    BINDING_TOTAL_VIA_VAT,
    REF_KEYS,
    unique_ir_pages,
    twin_pages,
    third_order_pages,
    no_number_pages,
    ambiguous_number_pages,
    ambiguous_total_role_pages,
    one_char_diff_pages,
    whitespace_pages,
    no_whitespace_pages,
    absent_total_role_pages,
    decisive_invalid_state,
    tolerance_invalid_state,
    deferred_state,
    unresolved_state,
    ORIGIN_KANDOO_SALE,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    IdentityDefiniteDuplicate,
    IdentityReadSuccess,
    IdentityReplay,
    IdentityResolutionRecorded,
    IdentityRequestRefused,
    IdentityInputIntegrityFailure,
)
from identity_resolution import (  # noqa: E402
    IdentityResolutionStore,
)
from duplicate_flows import (  # noqa: E402
    DuplicateFlowService,
    FlowDispositionStore,
    FlowDuplicateRecognized,
    FlowIdentityEstablished,
    FlowInputIntegrityFailure,
    FlowReadSuccess,
    FlowReadIntegrityFailure,
    FlowReadRefused,
    FlowReadVerificationUnavailable,
    FlowReprintRecognized,
    FlowRequestRefused,
    FlowStorageUnavailable,
    FLOW_OUTCOME_DUPLICATE_RECOGNIZED,
    FLOW_OUTCOME_IDENTITY_ESTABLISHED,
)
from capture import S1Service  # noqa: E402


_NO_NUMBER_SEQ = {"n": 2000}


def unique_no_number_pages():
    """Distinct no-invoice-number captures (VALID states whose
    INVOICE_NUMBER role has no usable value) — each call produces different
    bytes, hence a different capture S1."""
    _NO_NUMBER_SEQ["n"] += 1
    return [f"invoice.number=\ninvoice.date=2026-10-08\n"
            f"total.net=300.00\ntax.amount=24\nz={_NO_NUMBER_SEQ['n']}\n"
            .encode("utf-8")]


class DuplicateFlowStack(IdentityResolutionStack):
    """The WP-7.1 composition PLUS the WP-7.2 flow store/service — the
    WP-7.2 stack under test. All identity resolution machinery is the
    VERBATIM WP-7.1 stack (the flow layer consumes it, never bypasses it)."""

    def __init__(self, capture_db, recon_db, extraction_db, binding_db,
                 norm_db, deriv_db, val_db, vsm_db, identity_db, flows_db,
                 with_evidence=True, engines=None, rules=None,
                 extra_rules=(), formulas=None, norm_rulesets=None):
        super().__init__(capture_db, recon_db, extraction_db, binding_db,
                         norm_db, deriv_db, val_db, vsm_db, identity_db,
                         with_evidence=with_evidence, engines=engines,
                         rules=rules, extra_rules=extra_rules,
                         formulas=formulas, norm_rulesets=norm_rulesets)
        self.flows_db = flows_db
        self._s1 = S1Service()
        self.flow_store = FlowDispositionStore(flows_db, self._s1)
        self.flows = DuplicateFlowService(self.flow_store, self.identity,
                                          self._s1)

    # -- flow helpers ------------------------------------------------------

    def establish(self, parts=None, label="df-test", binding=None):
        """Full happy path: capture → … → VALID/CLEAR state → first flow
        handling. Returns (flow_outcome, normalization_id)."""
        nid, projection = self.build_valid_identity_state(
            parts=parts, label=label)
        outcome = self.flows.handle(projection.record.domain_state_id,
                                    ORIGIN_HOLOO_CAPTURE,
                                    BINDING if binding is None else binding)
        return outcome, nid

    def handle_new(self, parts=None, label="df-flow",
                   origin=ORIGIN_HOLOO_CAPTURE, binding=None, keys=None):
        """A NEW capture (fresh bytes → fresh S1) through the full path →
        its first flow handling. This is the canonical duplicate-corpus
        entry (each call is a DIFFERENT capture)."""
        nid, projection = self.build_valid_identity_state(
            parts=parts, label=label, keys=keys)
        outcome = self.flows.handle(projection.record.domain_state_id,
                                    origin,
                                    BINDING if binding is None else binding)
        return outcome

    def handle_nid(self, nid, origin=ORIGIN_HOLOO_CAPTURE, binding=None,
                   ruleset_id="kandoo-ir-rules-b", keys=None):
        """Re-present an EXISTING normalization under a NEW ruleset
        identity → a genuinely NEW domain_state_id over the SAME capture_s1
        (the WP-7.1 Case-A3 discipline), then handle it."""
        projection = self.project(nid, keys or REF_KEYS,
                                  ruleset_id=ruleset_id,
                                  ruleset_version="1")
        outcome = self.flows.handle(projection.record.domain_state_id,
                                    origin,
                                    BINDING if binding is None else binding)
        return outcome

    def close(self):
        self.flow_store.close()
        super().close()


__all__ = [
    "IdentityResolutionStack", "DuplicateFlowStack",
    "IdentityResolutionStore", "FlowDispositionStore",
    "DuplicateFlowService",
    "BINDING", "BINDING_TOTAL_VIA_VAT", "REF_KEYS",
    "unique_ir_pages", "twin_pages", "third_order_pages",
    "unique_no_number_pages",
    "no_number_pages", "ambiguous_number_pages",
    "ambiguous_total_role_pages", "one_char_diff_pages",
    "whitespace_pages", "no_whitespace_pages", "absent_total_role_pages",
    "decisive_invalid_state", "tolerance_invalid_state",
    "deferred_state", "unresolved_state",
    "ORIGIN_KANDOO_SALE", "ORIGIN_HOLOO_CAPTURE", "ORIGIN_OTHER_POS_CAPTURE",
    "IdentityDefiniteDuplicate", "IdentityReadSuccess", "IdentityReplay",
    "IdentityResolutionRecorded", "IdentityRequestRefused",
    "IdentityInputIntegrityFailure",
    "FlowIdentityEstablished", "FlowDuplicateRecognized",
    "FlowReprintRecognized", "FlowReadSuccess", "FlowRequestRefused",
    "FlowInputIntegrityFailure", "FlowStorageUnavailable",
    "FLOW_OUTCOME_IDENTITY_ESTABLISHED", "FLOW_OUTCOME_DUPLICATE_RECOGNIZED",
]
