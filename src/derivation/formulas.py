"""Declarative, versioned Formula Registry — WP-4.2 (SPEC-WP42-DER §3).

A formula is DATA — a declaration that is auditable end-to-end, never executable code.
The registry accepts only well-formed `DerivationFormula` declarations; construction-
time validation is fail-closed, so a malformed formula can never enter the registry
and therefore never execute. There is no eval, no exec, no callable payload, no
arbitrary Python anywhere in this mechanism.

Formula fingerprint: sha256-v1 (reused capture S1 capability) over the canonical
length-prefixed serialization of the declaration — id, version, output field, inputs
in declared order, expression tree in declared order. The same declaration always
yields the same fingerprint (determinism test axis).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from capture import S1ComputationFailure, S1Service

from .arithmetic import OPS
from .model import DerivationFormulaError

_EXPR_TAG_OP = "OP"
_EXPR_TAG_INPUT = "INPUT"


@dataclass(frozen=True)
class FormulaInput:
    """One declared input slot: a named slot bound to an engine-vocabulary field."""
    slot_name: str
    field_name: str


@dataclass(frozen=True)
class FormulaInputRef:
    """Expression leaf — a reference to a declared input slot (v1 has no literals)."""
    slot_name: str


@dataclass(frozen=True)
class FormulaOp:
    """Expression node — a declared op over child nodes (tree, acyclic by shape)."""
    op: str
    args: Tuple[object, ...]


@dataclass(frozen=True)
class DerivationFormula:
    """One declared, versioned formula (immutable data — SPEC §3)."""
    formula_id: str
    formula_version: str
    output_field_name: str
    inputs: Tuple[FormulaInput, ...]
    expression: object                    # FormulaOp | FormulaInputRef


def _validate_declaration(formula: object) -> None:
    """Fail-closed construction-time validation (SPEC §3). Raises
    DerivationFormulaError on any violation — registration is the only gate a formula
    must pass, so it must be total."""
    if not isinstance(formula, DerivationFormula):
        raise DerivationFormulaError(
            f"only DerivationFormula declarations are registrable, got {type(formula)!r}")
    for label, value in (("formula_id", formula.formula_id),
                         ("formula_version", formula.formula_version),
                         ("output_field_name", formula.output_field_name)):
        if not isinstance(value, str) or not value:
            raise DerivationFormulaError(f"{label} must be a non-empty string")
    if not formula.inputs or not isinstance(formula.inputs, tuple):
        raise DerivationFormulaError("formula must declare a non-empty tuple of inputs")
    declared_slots = set()
    input_fields = set()
    for slot in formula.inputs:
        if not isinstance(slot, FormulaInput):
            raise DerivationFormulaError(
                f"inputs must be FormulaInput declarations, got {type(slot)!r}")
        if not isinstance(slot.slot_name, str) or not slot.slot_name:
            raise DerivationFormulaError("slot_name must be a non-empty string")
        if not isinstance(slot.field_name, str) or not slot.field_name:
            raise DerivationFormulaError("field_name must be a non-empty string")
        if slot.slot_name in declared_slots:
            raise DerivationFormulaError(f"duplicate slot_name: {slot.slot_name!r}")
        declared_slots.add(slot.slot_name)
        input_fields.add(slot.field_name)
    if formula.output_field_name in input_fields:
        raise DerivationFormulaError(
            "output_field_name must not equal any input field_name "
            "(a formula that would shadow a read value is malformed by construction)")

    used_slots = set()

    def _walk(node: object) -> None:
        if isinstance(node, FormulaInputRef):
            if not isinstance(node.slot_name, str) or node.slot_name not in declared_slots:
                raise DerivationFormulaError(
                    f"expression leaf names an undeclared slot: {node.slot_name!r}")
            used_slots.add(node.slot_name)
            return
        if isinstance(node, FormulaOp):
            if not isinstance(node.op, str) or node.op not in OPS:
                raise DerivationFormulaError(
                    f"undeclared arithmetic op: {node.op!r} "
                    f"(declared vocabulary: {', '.join(OPS)})")
            if not isinstance(node.args, tuple) or not node.args:
                raise DerivationFormulaError(f"op {node.op} needs a non-empty args tuple")
            if node.op == "DIV" and len(node.args) != 2:
                raise DerivationFormulaError("DIV arity must be exactly 2")
            if node.op in ("ADD", "SUB", "MUL") and len(node.args) < 2:
                raise DerivationFormulaError(f"op {node.op} needs at least 2 args")
            for child in node.args:
                _walk(child)
            return
        raise DerivationFormulaError(
            f"expression leaves must be declared input-slot references; "
            f"refused payload: {type(node)!r} (no literals, no callables, no code)")

    _walk(formula.expression)
    unused = declared_slots - used_slots
    if unused:
        raise DerivationFormulaError(
            f"declared slots never used in the expression: {sorted(unused)}")


def canonical_formula_bytes(formula: DerivationFormula) -> bytes:
    """Canonical serialization of the declaration (deterministic, total — SPEC §3).

    Fail-closed: the declaration is fully validated BEFORE serialization — only
    well-formed declarations can be serialized, fingerprinted, or registered.

    Order is fixed by the declaration: id, version, output field, inputs in declared
    order, expression tree in declared shape. The same declaration ALWAYS yields the
    same byte sequence.
    """
    from derivation.store import _chunk            # shared canonical element encoding

    _validate_declaration(formula)

    def _expr(node: object):
        if isinstance(node, FormulaInputRef):
            return [_chunk(_EXPR_TAG_INPUT), _chunk(node.slot_name)]
        if isinstance(node, FormulaOp):
            parts = [_chunk(_EXPR_TAG_OP), _chunk(node.op),
                     _chunk(len(node.args))]
            for child in node.args:
                parts += _expr(child)
            return parts
        raise DerivationFormulaError(
            f"non-declaration payload inside expression: {type(node)!r}")

    parts = [
        _chunk("derivation-formula:v1"),
        _chunk(formula.formula_id),
        _chunk(formula.formula_version),
        _chunk(formula.output_field_name),
        _chunk(len(formula.inputs)),
    ]
    for slot in formula.inputs:
        parts += [_chunk(slot.slot_name), _chunk(slot.field_name)]
    parts += _expr(formula.expression)
    return b"".join(parts)


def formula_fingerprint(formula: DerivationFormula,
                        s1: S1Service) -> Tuple[str, str]:
    """(fingerprint, algorithm_id) of the declared formula — sha256-v1 (SPEC §3)."""
    try:
        fp = s1.compute(canonical_formula_bytes(formula))
    except S1ComputationFailure as exc:
        raise DerivationFormulaError(f"formula fingerprint capability failure: {exc}") from exc
    return fp.s1, fp.s1_algorithm_id


class DerivationFormulaRegistry:
    """Constructor-injected registry keyed by (formula_id, formula_version) — two
    versions of one formula coexist as distinct derivation keys (SPEC §3)."""

    def __init__(self, formulas: Mapping[Tuple[str, str], DerivationFormula],
                 s1: S1Service) -> None:
        self._s1 = s1
        self._formulas: dict = {}
        self._fingerprints: dict = {}
        for key, formula in dict(formulas).items():
            if not (isinstance(key, tuple) and len(key) == 2
                    and isinstance(key[0], str) and isinstance(key[1], str)):
                raise DerivationFormulaError(
                    f"registry keys must be (formula_id, formula_version): {key!r}")
            _validate_declaration(formula)
            if (formula.formula_id, formula.formula_version) != key:
                raise DerivationFormulaError(
                    f"registry key {key!r} does not match the declaration "
                    f"{(formula.formula_id, formula.formula_version)!r}")
            self._formulas[key] = formula
            self._fingerprints[key] = formula_fingerprint(formula, s1)[0]

    def get(self, formula_id: str, formula_version: str) -> Optional[DerivationFormula]:
        return self._formulas.get((formula_id, formula_version))

    def fingerprint_of(self, formula_id: str, formula_version: str) -> Optional[str]:
        return self._fingerprints.get((formula_id, formula_version))

    def keys(self) -> Tuple[Tuple[str, str], ...]:
        return tuple(sorted(self._formulas))

    def __contains__(self, key: object) -> bool:
        return key in self._formulas


# ---------------------------------------------------------------------------
# Reference registry (MVP executability choice, NOT a business-rule decision — OD-D9)
# ---------------------------------------------------------------------------

def ReferenceDerivationFormulasV1() -> Mapping[Tuple[str, str], DerivationFormula]:
    """The declared MVP registry: EXACTLY ONE formula — the dispatch's allowed example

        total.gross = ADD(total.net, tax.amount)

    No unit_amount formula is shipped (association is P6; non-exact division/rounding
    is D-08/WP-5.1). New formulas enter as declared data with a new (id, version).
    """
    total_gross = DerivationFormula(
        formula_id="kandoo-der-total-gross-from-net-tax",
        formula_version="1",
        output_field_name="total.gross",
        inputs=(
            FormulaInput(slot_name="net", field_name="total.net"),
            FormulaInput(slot_name="tax", field_name="tax.amount"),
        ),
        expression=FormulaOp("ADD", (FormulaInputRef("net"), FormulaInputRef("tax"))),
    )
    return {(total_gross.formula_id, total_gross.formula_version): total_gross}
