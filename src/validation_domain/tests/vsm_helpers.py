"""Shared helpers for the WP-5.2 validation-domain tests (unique module name —
safe for combined collection with the capture/reconstruction/extraction/
normalization/derivation/validation suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → validation_domain → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

VAL_TESTS = SRC / "validation" / "tests"
if str(VAL_TESTS) not in sys.path:
    sys.path.insert(0, str(VAL_TESTS))

from capture import S1Service  # noqa: E402
from derivation import DerivationCompleted  # noqa: E402
from val_helpers import (  # noqa: E402  (P5.1 helpers reused verbatim)
    FORMULA,
    PAGE_AMBIGUOUS,
    PAGE_ABSENT_FIELD,
    PAGE_DEFERRED_INPUT,
    PAGE_MISSING_TAX,
    PAGE_OK,
    R_CONSIST,
    R_PRESENT,
    R_ROUNDED,
    R_TOLERANCE,
    TOLERANCE,
    PRECISION,
    MODE,
    ingest_pages,
    reference_rules,
    ValidationStack,
)
from validation import (  # noqa: E402
    RuleExprOp,
    RuleInput,
    RuleSlotRef,
    ValidationCompleted,
    ValidationRule,
)
from validation_domain import (  # noqa: E402
    DomainStateProjected,
    ReviewEventAppended,
    ValidationDomainService,
    ValidationDomainStore,
)

# Test corpus — key=value pages (the declared reference-engine grammar).
PAGE_QUOT = [b"a=1.00\nb=3\nt=2.00\n"]     # DIV(a,b) = 1/3 → non-exact probe
PAGE_ALT_OK = [b"total.net=2000.00\ntax.amount=160\ninvoice.number=VSM-1\n"]
# ^ same semantics as PAGE_OK, different bytes (D-03-safe second normalization)


def exact_probe_rule(rule_id="vsm-probe-exact-mismatch", version="1",
                     target_field="tax.amount", numerator="total.net"):
    """R1 exact-consistency probe: expression SUB(net, net) = 0 vs target
    tax.amount = 80 → decisive mismatch (T1 route). Matching twin below."""
    return ValidationRule(
        rule_id=rule_id,
        rule_version=version,
        rule_kind="R1",
        rule_type="exact-consistency",
        inputs=(
            RuleInput(slot_name="target", field_name=target_field,
                      origin="normalized"),
            RuleInput(slot_name="n", field_name=numerator, origin="normalized"),
        ),
        target_slot="target",
        expression=RuleExprOp("SUB", (RuleSlotRef("n"), RuleSlotRef("n"))),
    )


def exact_match_rule(rule_id="vsm-probe-exact-match", version="1",
                     target_field="tax.amount", numerator="total.net"):
    """R1 exact-consistency probe that MATCHES: ADD(tax, SUB(net, net)) == tax."""
    return ValidationRule(
        rule_id=rule_id,
        rule_version=version,
        rule_kind="R1",
        rule_type="exact-consistency",
        inputs=(
            RuleInput(slot_name="target", field_name=target_field,
                      origin="normalized"),
            RuleInput(slot_name="n", field_name=numerator, origin="normalized"),
        ),
        target_slot="target",
        expression=RuleExprOp("ADD", (RuleSlotRef("target"),
                                      RuleExprOp("SUB", (RuleSlotRef("n"),
                                                         RuleSlotRef("n"))))),
    )


def tolerance_probe_rule(rule_id="vsm-probe-tolerance-mismatch", version="1",
                         target_field="tax.amount", numerator="total.net",
                         tolerance=TOLERANCE):
    """R2 tolerated-equality probe: |SUB(net,net) − tax| = 80 > tolerance →
    mismatch-beyond-tolerance (T2 route, D-08)."""
    return ValidationRule(
        rule_id=rule_id,
        rule_version=version,
        rule_kind="R2",
        rule_type="tolerated-equality",
        inputs=(
            RuleInput(slot_name="target", field_name=target_field,
                      origin="normalized"),
            RuleInput(slot_name="n", field_name=numerator, origin="normalized"),
        ),
        target_slot="target",
        expression=RuleExprOp("SUB", (RuleSlotRef("n"), RuleSlotRef("n"))),
        tolerance=tolerance,
    )


def rounded_probe_rule(rule_id="vsm-probe-rounded-mismatch", version="1",
                       target_field="tax.amount", numerator="total.net",
                       precision=PRECISION, mode=MODE):
    """R2 rounded-equality probe: SUB(net,net)=0 rounded → 0.00 ≠ 80 →
    mismatch-after-rounding (T2 route, D-08)."""
    return ValidationRule(
        rule_id=rule_id,
        rule_version=version,
        rule_kind="R2",
        rule_type="rounded-equality",
        inputs=(
            RuleInput(slot_name="target", field_name=target_field,
                      origin="normalized"),
            RuleInput(slot_name="n", field_name=numerator, origin="normalized"),
        ),
        target_slot="target",
        expression=RuleExprOp("SUB", (RuleSlotRef("n"), RuleSlotRef("n"))),
        rounding_precision=precision,
        rounding_mode=mode,
    )


def nonexact_probe_rule(rule_id="vsm-probe-nonexact", version="1"):
    """R1 exact-consistency probe over DIV: 1/3 is non-terminating → durable
    DEFERRED(non-exact-intermediate) (T4 route)."""
    return ValidationRule(
        rule_id=rule_id,
        rule_version=version,
        rule_kind="R1",
        rule_type="exact-consistency",
        inputs=(
            RuleInput(slot_name="target", field_name="t", origin="normalized"),
            RuleInput(slot_name="x", field_name="a", origin="normalized"),
            RuleInput(slot_name="y", field_name="b", origin="normalized"),
        ),
        target_slot="target",
        expression=RuleExprOp("DIV", (RuleSlotRef("x"), RuleSlotRef("y"))),
    )


def presence_rule_for(field_name, rule_id="vsm-probe-presence", version="1",
                      origin="normalized"):
    """R1 presence probe over an arbitrary field/origin."""
    return ValidationRule(
        rule_id=rule_id,
        rule_version=version,
        rule_kind="R1",
        rule_type="presence",
        inputs=(RuleInput(slot_name="field", field_name=field_name,
                          origin=origin),),
        target_slot=None,
        expression=None,
    )


class ValidationDomainStack(ValidationStack):
    """The P5.1 composition PLUS the WP-5.2 domain store/service — the WP-5.2
    stack under test. All test-declared probe rules are pre-registered (rules
    are data; only validate() calls create records, so pre-registration is
    behaviorally inert for the completeness gate)."""

    def __init__(self, capture_db, recon_db, extraction_db, binding_db, norm_db,
                 deriv_db, val_db, vsm_db, with_evidence=True, engines=None,
                 rules=None, extra_rules=(), formulas=None, norm_rulesets=None,
                 domain_rule_map=None):
        probes = [
            exact_probe_rule(), exact_match_rule(), tolerance_probe_rule(),
            rounded_probe_rule(), nonexact_probe_rule(),
            presence_rule_for("seller.vat", rule_id="vsm-probe-presence"),
            tolerance_probe_rule(rule_id="vsm-probe-tolerance-absent",
                                 target_field="seller.vat"),
            tolerance_probe_rule(rule_id="vsm-probe-tolerance-ambiguous",
                                 target_field="tax.amount"),
        ]
        extra_rules = tuple(extra_rules) + tuple(probes)
        super().__init__(capture_db, recon_db, extraction_db, binding_db,
                         norm_db, deriv_db, val_db, with_evidence=with_evidence,
                         engines=engines, rules=rules, extra_rules=extra_rules,
                         formulas=formulas, norm_rulesets=norm_rulesets)
        self.vsm_db = vsm_db
        self.vsm_store = ValidationDomainStore(vsm_db, S1Service())
        self.vsm = ValidationDomainService(
            self.vsm_store, self.val, self.vregistry, self.norm, self.extraction,
            self.binder, self.recon, S1Service())

    # -- pipeline helpers --------------------------------------------------

    def build_normalization(self, parts=None, label="vsm-test",
                            ruleset_id="kandoo-norm-v1",
                            engine_id="reference-delimited-v1") -> str:
        return self.build_extract_normalize(
            PAGE_OK if parts is None else parts, engine_id=engine_id,
            label=label, ruleset_id=ruleset_id)

    def build_derived(self, parts=None, label="vsm-test") -> str:
        """Full happy path up to a DERIVED total.gross → normalization_id."""
        normalization_id = self.build_normalization(parts, label=label)
        outcome = self.deriv.derive(normalization_id, FORMULA, "1")
        assert isinstance(outcome, DerivationCompleted), outcome
        return normalization_id

    def validate_all_reference(self, normalization_id):
        """Run the COMPLETE reference ruleset (4 rules) → list of records."""
        records = []
        for rule in (R_PRESENT, R_CONSIST, R_TOLERANCE, R_ROUNDED):
            outcome = self.val.validate(normalization_id, rule, "1")
            assert isinstance(outcome, ValidationCompleted), outcome
            records.append(outcome.record)
        return records

    def project(self, normalization_id, keys, ruleset_id="kandoo-vsm-rules",
                ruleset_version="1"):
        outcome = self.vsm.project_domain_state(normalization_id, ruleset_id,
                                                ruleset_version, list(keys))
        assert isinstance(outcome, DomainStateProjected), outcome
        return outcome

    def close(self):
        self.vsm_store.close()
        super().close()


REF_KEYS = [(R_PRESENT, "1"), (R_CONSIST, "1"), (R_TOLERANCE, "1"),
            (R_ROUNDED, "1")]
