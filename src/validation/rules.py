"""Declarative, versioned Rule Registry — WP-5.1 R1/R2 (SPEC-WP51-VAL §3).

A rule is DATA — a declaration that is auditable end-to-end, never executable code.
The registry accepts only well-formed `ValidationRule` declarations; construction-
time validation is fail-closed, so a malformed rule can never enter the registry and
therefore never execute. There is no eval, no exec, no callable payload, no arbitrary
Python anywhere in this engine.

Kind/type pairing is structural (fail-closed):
  R1: presence | exact-consistency   — NEVER carries tolerance or rounding parameters
  R2: tolerated-equality | rounded-equality — D-08 parameters REQUIRED, injected at
      construction (no fixed values may ship hardcoded)

Rule fingerprint: sha256-v1 (reused capture S1 capability) over the canonical
length-prefixed serialization of the declaration — id, version, kind, type, target
slot, tolerance, rounding parameters, inputs in declared order, expression tree in
declared order. The same declaration always yields the same fingerprint.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from capture import S1ComputationFailure, S1Service

from derivation.arithmetic import parse_canonical_decimal

from .model import RULE_KIND_R1, ValidationRuleError
from .rounding import ROUNDING_MODES

_EXPR_TAG_OP = "OP"
_EXPR_TAG_SLOT = "SLOT"

_KINDS = ("R1", "R2")
_TYPES_R1 = ("presence", "exact-consistency")
_TYPES_R2 = ("tolerated-equality", "rounded-equality")
_ORIGINS = ("normalized", "derived")
_COMPARISON_TYPES = frozenset(_TYPES_R1[1:]) | frozenset(_TYPES_R2)


@dataclass(frozen=True)
class RuleInput:
    """One declared input slot: a named slot bound to an engine-vocabulary field of
    a declared origin (normalized | derived). No canonical mapping ever happens."""
    slot_name: str
    field_name: str
    origin: str


@dataclass(frozen=True)
class RuleSlotRef:
    """Expression leaf — a reference to a declared input slot (no literals in v1)."""
    slot_name: str


@dataclass(frozen=True)
class RuleExprOp:
    """Expression node — a declared op over child nodes (tree, acyclic by shape).
    Same closed op vocabulary as the WP-4.2 formula mechanism."""
    op: str
    args: Tuple[object, ...]


@dataclass(frozen=True)
class ValidationRule:
    """One declared, versioned validation rule (immutable data — SPEC §3)."""
    rule_id: str
    rule_version: str
    rule_kind: str                       # 'R1' | 'R2'
    rule_type: str                       # presence | exact-consistency |
                                         # tolerated-equality | rounded-equality
    inputs: Tuple[RuleInput, ...]
    target_slot: Optional[str]           # comparison types only
    expression: Optional[object]         # comparison types only (RuleExprOp tree)
    tolerance: Optional[str] = None      # tolerated-equality only (canonical ≥ 0)
    rounding_precision: Optional[int] = None   # rounded-equality only
    rounding_mode: Optional[str] = None        # rounded-equality only


def _validate_declaration(rule: object) -> None:
    """Fail-closed construction-time validation (SPEC §3). Raises
    ValidationRuleError on any violation — registration is the only gate a rule
    must pass, so it must be total."""
    if not isinstance(rule, ValidationRule):
        raise ValidationRuleError(
            f"only ValidationRule declarations are registrable, got {type(rule)!r}")
    for label, value in (("rule_id", rule.rule_id), ("rule_version", rule.rule_version),
                         ("rule_kind", rule.rule_kind), ("rule_type", rule.rule_type)):
        if not isinstance(value, str) or not value:
            raise ValidationRuleError(f"{label} must be a non-empty string")
    if rule.rule_kind not in _KINDS:
        raise ValidationRuleError(
            f"undeclared rule kind: {rule.rule_kind!r} (declared: {', '.join(_KINDS)})")
    allowed_types = _TYPES_R1 if rule.rule_kind == RULE_KIND_R1 else _TYPES_R2
    if rule.rule_type not in allowed_types:
        raise ValidationRuleError(
            f"rule type {rule.rule_type!r} is not declared for kind "
            f"{rule.rule_kind} (allowed: {', '.join(allowed_types)})")

    if not rule.inputs or not isinstance(rule.inputs, tuple):
        raise ValidationRuleError("rule must declare a non-empty tuple of inputs")
    declared_slots = set()
    for slot in rule.inputs:
        if not isinstance(slot, RuleInput):
            raise ValidationRuleError(
                f"inputs must be RuleInput declarations, got {type(slot)!r}")
        for label, value in (("slot_name", slot.slot_name),
                             ("field_name", slot.field_name),
                             ("origin", slot.origin)):
            if not isinstance(value, str) or not value:
                raise ValidationRuleError(f"{label} must be a non-empty string")
        if slot.origin not in _ORIGINS:
            raise ValidationRuleError(
                f"undeclared input origin: {slot.origin!r} (declared: "
                f"{', '.join(_ORIGINS)})")
        if slot.slot_name in declared_slots:
            raise ValidationRuleError(f"duplicate slot_name: {slot.slot_name!r}")
        declared_slots.add(slot.slot_name)

    if rule.rule_type == "presence":
        if rule.target_slot is not None or rule.expression is not None:
            raise ValidationRuleError(
                "presence rule must not declare a target_slot or an expression")
        if rule.tolerance is not None or rule.rounding_precision is not None \
                or rule.rounding_mode is not None:
            raise ValidationRuleError("presence rule carries no R2 parameters")
        return

    # comparison types — structural requirements
    if not isinstance(rule.target_slot, str) or rule.target_slot not in declared_slots:
        raise ValidationRuleError(
            f"comparison rules must declare target_slot among the inputs, got "
            f"{rule.target_slot!r}")
    if not isinstance(rule.expression, (RuleExprOp, RuleSlotRef)):
        raise ValidationRuleError(
            "comparison rules must declare an expression over declared slots "
            "(no literals, no callables, no code)")

    if rule.rule_kind == RULE_KIND_R1 and (rule.tolerance is not None
                                           or rule.rounding_precision is not None
                                           or rule.rounding_mode is not None):
        raise ValidationRuleError(
            "R1 rules can never carry tolerance or rounding parameters "
            "(parametric rounding is R2-only, D-08)")

    used_slots = set()

    def _walk(node: object) -> None:
        if isinstance(node, RuleSlotRef):
            if not isinstance(node.slot_name, str) \
                    or node.slot_name not in declared_slots:
                raise ValidationRuleError(
                    f"expression leaf names an undeclared slot: {node.slot_name!r}")
            used_slots.add(node.slot_name)
            return
        if isinstance(node, RuleExprOp):
            if not isinstance(node.op, str) \
                    or node.op not in ("ADD", "SUB", "MUL", "DIV"):
                raise ValidationRuleError(
                    f"undeclared arithmetic op: {node.op!r} "
                    f"(declared vocabulary: ADD, SUB, MUL, DIV)")
            if not isinstance(node.args, tuple) or not node.args:
                raise ValidationRuleError(f"op {node.op} needs a non-empty args tuple")
            if node.op == "DIV" and len(node.args) != 2:
                raise ValidationRuleError("DIV arity must be exactly 2")
            if node.op in ("ADD", "SUB", "MUL") and len(node.args) < 2:
                raise ValidationRuleError(f"op {node.op} needs at least 2 args")
            for child in node.args:
                _walk(child)
            return
        raise ValidationRuleError(
            f"expression leaves must be declared slot references; refused payload: "
            f"{type(node)!r} (no literals, no callables, no code)")

    _walk(rule.expression)
    # every declared slot must be used: in the expression or as the target
    unused = declared_slots - used_slots - {rule.target_slot}
    if unused:
        raise ValidationRuleError(
            f"declared slots never used in the comparison: {sorted(unused)}")

    if rule.rule_kind == RULE_KIND_R1:
        return                       # exact-consistency: no R2 parameters exist here

    if rule.rule_type == "tolerated-equality":
        if not isinstance(rule.tolerance, str) or not rule.tolerance:
            raise ValidationRuleError(
                "tolerated-equality requires an injected tolerance parameter "
                "(canonical decimal string ≥ 0 — D-08: no fixed value may be "
                "hardcoded, parameters are constructor-injected)")
        parsed = parse_canonical_decimal(rule.tolerance)
        if parsed is None or parsed < 0:
            raise ValidationRuleError(
                f"tolerance must be a canonical decimal string ≥ 0, got "
                f"{rule.tolerance!r}")
        if rule.rounding_precision is not None or rule.rounding_mode is not None:
            raise ValidationRuleError(
                "tolerated-equality must not declare rounding parameters")
        return

    # rounded-equality
    if rule.tolerance is not None:
        raise ValidationRuleError("rounded-equality must not declare a tolerance")
    if not isinstance(rule.rounding_precision, int) \
            or isinstance(rule.rounding_precision, bool) or rule.rounding_precision < 0:
        raise ValidationRuleError(
            "rounded-equality requires an injected rounding_precision parameter "
            "(non-negative integer — D-08: explicit precision, no default)")
    if not isinstance(rule.rounding_mode, str) \
            or rule.rounding_mode not in ROUNDING_MODES:
        raise ValidationRuleError(
            f"rounded-equality requires an injected rounding_mode parameter from the "
            f"declared vocabulary: {', '.join(ROUNDING_MODES)}")


def canonical_rule_bytes(rule: ValidationRule) -> bytes:
    """Canonical serialization of the declaration (deterministic, total — SPEC §3).

    Fail-closed: the declaration is fully validated BEFORE serialization — only
    well-formed declarations can be serialized, fingerprinted, or registered.
    """
    from validation.store import _chunk          # shared canonical element encoding

    _validate_declaration(rule)

    def _expr(node: object):
        if isinstance(node, RuleSlotRef):
            return [_chunk(_EXPR_TAG_SLOT), _chunk(node.slot_name)]
        if isinstance(node, RuleExprOp):
            parts = [_chunk(_EXPR_TAG_OP), _chunk(node.op), _chunk(len(node.args))]
            for child in node.args:
                parts += _expr(child)
            return parts
        raise ValidationRuleError(
            f"non-declaration payload inside expression: {type(node)!r}")

    parts = [
        _chunk("validation-rule:v1"),
        _chunk(rule.rule_id),
        _chunk(rule.rule_version),
        _chunk(rule.rule_kind),
        _chunk(rule.rule_type),
        _chunk(rule.target_slot if rule.target_slot is not None else ""),
        _chunk(rule.tolerance if rule.tolerance is not None else ""),
        _chunk(rule.rounding_precision if rule.rounding_precision is not None else -1),
        _chunk(rule.rounding_mode if rule.rounding_mode is not None else ""),
        _chunk(len(rule.inputs)),
    ]
    for slot in rule.inputs:
        parts += [_chunk(slot.slot_name), _chunk(slot.field_name), _chunk(slot.origin)]
    if rule.expression is not None:                  # presence rules carry none
        parts += _expr(rule.expression)
    return b"".join(parts)


def rule_fingerprint(rule: ValidationRule, s1: S1Service) -> Tuple[str, str]:
    """(fingerprint, algorithm_id) of the declared rule — sha256-v1 (SPEC §3)."""
    try:
        fp = s1.compute(canonical_rule_bytes(rule))
    except S1ComputationFailure as exc:
        raise ValidationRuleError(f"rule fingerprint capability failure: {exc}") from exc
    return fp.s1, fp.s1_algorithm_id


class ValidationRuleRegistry:
    """Constructor-injected registry keyed by (rule_id, rule_version) — two versions
    of one rule coexist as distinct validation keys (SPEC §3)."""

    def __init__(self, rules: Mapping[Tuple[str, str], ValidationRule],
                 s1: S1Service) -> None:
        self._s1 = s1
        self._rules: dict = {}
        self._fingerprints: dict = {}
        for key, rule in dict(rules).items():
            if not (isinstance(key, tuple) and len(key) == 2
                    and isinstance(key[0], str) and isinstance(key[1], str)):
                raise ValidationRuleError(
                    f"registry keys must be (rule_id, rule_version): {key!r}")
            _validate_declaration(rule)
            if (rule.rule_id, rule.rule_version) != key:
                raise ValidationRuleError(
                    f"registry key {key!r} does not match the declaration "
                    f"{(rule.rule_id, rule.rule_version)!r}")
            self._rules[key] = rule
            self._fingerprints[key] = rule_fingerprint(rule, s1)[0]

    def get(self, rule_id: str, rule_version: str) -> Optional[ValidationRule]:
        return self._rules.get((rule_id, rule_version))

    def fingerprint_of(self, rule_id: str, rule_version: str) -> Optional[str]:
        return self._fingerprints.get((rule_id, rule_version))

    def keys(self) -> Tuple[Tuple[str, str], ...]:
        return tuple(sorted(self._rules))

    def __contains__(self, key: object) -> bool:
        return key in self._rules


# ---------------------------------------------------------------------------
# Reference registry (MVP executability choice, NOT a business-rule decision — OD-V9)
# ---------------------------------------------------------------------------

def ReferenceValidationRulesV1(tolerance: str, precision: int, mode: str) -> Mapping[
        Tuple[str, str], ValidationRule]:
    """The declared MVP registry: EXACTLY FOUR rules — with ALL R2 parameters
    REQUIRED constructor arguments (D-08: tolerance/precision/mode are calibration
    parameters injected per deployment; NOTHING is hardcoded):

        R1 presence            kandoo-val-total-net-present       v1
        R1 exact-consistency   kandoo-val-total-gross-consistency v1
        R2 tolerated-equality  kandoo-val-total-gross-tolerance   v1
        R2 rounded-equality    kandoo-val-total-gross-rounded     v1

    New rules enter as declared data with a new (id, version).
    """
    present = ValidationRule(
        rule_id="kandoo-val-total-net-present",
        rule_version="1",
        rule_kind="R1",
        rule_type="presence",
        inputs=(RuleInput(slot_name="field", field_name="total.net",
                          origin="normalized"),),
        target_slot=None,
        expression=None,
    )
    consistency = ValidationRule(
        rule_id="kandoo-val-total-gross-consistency",
        rule_version="1",
        rule_kind="R1",
        rule_type="exact-consistency",
        inputs=(
            RuleInput(slot_name="target", field_name="total.gross", origin="derived"),
            RuleInput(slot_name="net", field_name="total.net", origin="normalized"),
            RuleInput(slot_name="tax", field_name="tax.amount", origin="normalized"),
        ),
        target_slot="target",
        expression=RuleExprOp("ADD", (RuleSlotRef("net"), RuleSlotRef("tax"))),
    )
    tolerated = ValidationRule(
        rule_id="kandoo-val-total-gross-tolerance",
        rule_version="1",
        rule_kind="R2",
        rule_type="tolerated-equality",
        inputs=(consistency.inputs),
        target_slot="target",
        expression=RuleExprOp("ADD", (RuleSlotRef("net"), RuleSlotRef("tax"))),
        tolerance=tolerance,
    )
    rounded = ValidationRule(
        rule_id="kandoo-val-total-gross-rounded",
        rule_version="1",
        rule_kind="R2",
        rule_type="rounded-equality",
        inputs=(consistency.inputs),
        target_slot="target",
        expression=RuleExprOp("ADD", (RuleSlotRef("net"), RuleSlotRef("tax"))),
        rounding_precision=precision,
        rounding_mode=mode,
    )
    return {
        (present.rule_id, present.rule_version): present,
        (consistency.rule_id, consistency.rule_version): consistency,
        (tolerated.rule_id, tolerated.rule_version): tolerated,
        (rounded.rule_id, rounded.rule_version): rounded,
    }
