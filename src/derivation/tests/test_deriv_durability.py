"""WP-4.2 durability tests — restart-safe persistence, atomic commit with zero
residue, INV-D-1:1 backstop, append-only semantics, storage gates
(SPEC-WP42-DER §9, OD-D1..OD-D7)."""
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from deriv_helpers import PAGE_OK             # noqa: E402
from derivation import (                      # noqa: E402
    DerivationAlreadyExists,
    DerivationCompleted,
    DerivationPersistenceUnavailable,
    DerivationReadSuccess,
    DerivationStore,
)

REF = "kandoo-der-total-gross-from-net-tax"


class TestRestartDurability:
    def test_records_survive_full_restart_and_reverify(self, make_stack):
        s = make_stack()
        outcome, norm_id = s.derive_ok(PAGE_OK)
        record, inputs = outcome.record, outcome.inputs
        s.close()

        s2 = make_stack()
        try:
            read = s2.deriv.read_derivation(record.derivation_id)
            assert isinstance(read, DerivationReadSuccess)
            assert read.record == record
            assert read.inputs == inputs
            # frozen upstream stores survived too
            assert isinstance(s2.norm.read_normalization(norm_id), type(
                s2.norm.read_normalization(norm_id)))
            # idempotent replay after restart
            replay = s2.deriv.derive(norm_id, REF, "1")
            assert isinstance(replay, DerivationAlreadyExists)
        finally:
            s2.close()

    def test_derivation_ids_deterministically_enumerable(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_OK)
        first = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(first, DerivationCompleted)
        ids = stack.deriv.derivations_for_normalization(norm_id)
        assert ids == (first.record.derivation_id,)
        assert ids == tuple(sorted(ids))


class TestAtomicity:
    def test_commit_refusal_leaves_zero_residue(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_OK)
        rec = stack.norm.read_normalization(norm_id).record
        # input pointers outside the source record are refused before anything persists
        from derivation import DerivationInputRef
        with pytest.raises(DerivationPersistenceUnavailable):
            stack.deriv_store.commit_derivation(
                normalization_id=norm_id,
                extraction_id=rec.extraction_id,
                document_id=rec.document_id,
                capture_id=rec.capture_id,
                capture_s1=rec.capture_s1,
                capture_s1_algorithm_id=rec.capture_s1_algorithm_id,
                ruleset_id=rec.ruleset_id,
                ruleset_version=rec.ruleset_version,
                formula_id=REF, formula_version="1",
                formula_fingerprint="f" * 64,
                formula_fingerprint_algorithm_id="sha256-v1",
                output_field_name="total.gross", output_value="1080",
                inputs=(DerivationInputRef(0, "net", "total.net",
                                           "OTHER-normalization", 1,
                                           rec.extraction_id),))
        rows = stack.deriv_store._conn.execute(
            "SELECT COUNT(*) AS n FROM derivation_records").fetchone()["n"]
        assert rows == 0
        # the connection is still usable — no txn left open
        outcome = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(outcome, DerivationCompleted)

    def test_commit_without_inputs_is_refused(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_OK)
        rec = stack.norm.read_normalization(norm_id).record
        with pytest.raises(DerivationPersistenceUnavailable):
            stack.deriv_store.commit_derivation(
                normalization_id=norm_id,
                extraction_id=rec.extraction_id,
                document_id=rec.document_id,
                capture_id=rec.capture_id,
                capture_s1=rec.capture_s1,
                capture_s1_algorithm_id=rec.capture_s1_algorithm_id,
                ruleset_id=rec.ruleset_id,
                ruleset_version=rec.ruleset_version,
                formula_id=REF, formula_version="1",
                formula_fingerprint="f" * 64,
                formula_fingerprint_algorithm_id="sha256-v1",
                output_field_name="total.gross", output_value="1080",
                inputs=())
        assert stack.deriv_store._conn.execute(
            "SELECT COUNT(*) AS n FROM derivation_records").fetchone()["n"] == 0


class TestInvD11:
    def test_unique_index_backstops_the_triple(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_OK)
        outcome = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(outcome, DerivationCompleted)
        rec = stack.norm.read_normalization(norm_id).record
        raw = sqlite3.connect(str(stack.deriv_db))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                raw.execute(
                    """INSERT INTO derivation_records (
                           derivation_id, normalization_id, extraction_id, document_id,
                           capture_id, capture_s1, capture_s1_algorithm_id,
                           ruleset_id, ruleset_version, formula_id, formula_version,
                           formula_fingerprint, formula_fingerprint_algorithm_id,
                           output_field_name, output_provenance, output_value,
                           input_count, created_at, record_fingerprint,
                           fingerprint_algorithm_id)
                       VALUES ('fake-id', ?, ?, ?, ?, ?, ?, ?, ?, ?, '1',
                               'f' * 1, 'sha256-v1', 'total.gross', 'DERIVED', '1',
                               1, 'now', 'f', 'sha256-v1')""",
                    (norm_id, rec.extraction_id, rec.document_id, rec.capture_id,
                     rec.capture_s1, rec.capture_s1_algorithm_id, rec.ruleset_id,
                     rec.ruleset_version, REF))
        finally:
            raw.close()

    def test_no_update_or_delete_path_exists_in_the_store(self, stack):
        public = [name for name in dir(stack.deriv_store) if not name.startswith("_")]
        assert not any(name.lower().startswith(("update", "delete"))
                       for name in public), public


class TestStorageGates:
    def test_unresolved_provenance_cannot_be_stored(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_OK)
        rec = stack.norm.read_normalization(norm_id).record
        raw = sqlite3.connect(str(stack.deriv_db))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                raw.execute(
                    """INSERT INTO derivation_records (
                           derivation_id, normalization_id, extraction_id, document_id,
                           capture_id, capture_s1, capture_s1_algorithm_id,
                           ruleset_id, ruleset_version, formula_id, formula_version,
                           formula_fingerprint, formula_fingerprint_algorithm_id,
                           output_field_name, output_provenance, output_value,
                           input_count, created_at, record_fingerprint,
                           fingerprint_algorithm_id)
                       VALUES ('x1', ?, ?, ?, ?, ?, ?, ?, ?, ?, '1',
                               'f', 'sha256-v1', 'total.gross', 'UNRESOLVED', '1',
                               1, 'now', 'f', 'sha256-v1')""",
                    (norm_id, rec.extraction_id, rec.document_id, rec.capture_id,
                     rec.capture_s1, rec.capture_s1_algorithm_id, rec.ruleset_id,
                     rec.ruleset_version, REF))
            with pytest.raises(sqlite3.IntegrityError):
                raw.execute(
                    """INSERT INTO derivation_records (
                           derivation_id, normalization_id, extraction_id, document_id,
                           capture_id, capture_s1, capture_s1_algorithm_id,
                           ruleset_id, ruleset_version, formula_id, formula_version,
                           formula_fingerprint, formula_fingerprint_algorithm_id,
                           output_field_name, output_provenance, output_value,
                           input_count, created_at, record_fingerprint,
                           fingerprint_algorithm_id)
                       VALUES ('x2', ?, ?, ?, ?, ?, ?, ?, ?, ?, '1',
                               'f', 'sha256-v1', 'total.gross', 'EXTRACTED', '1',
                               1, 'now', 'f', 'sha256-v1')""",
                    (norm_id, rec.extraction_id, rec.document_id, rec.capture_id,
                     rec.capture_s1, rec.capture_s1_algorithm_id, rec.ruleset_id,
                     rec.ruleset_version, REF))
        finally:
            raw.close()

    def test_zero_input_count_cannot_be_stored(self, stack):
        raw = sqlite3.connect(str(stack.deriv_db))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                raw.execute(
                    """INSERT INTO derivation_records (
                           derivation_id, normalization_id, extraction_id, document_id,
                           capture_id, capture_s1, capture_s1_algorithm_id,
                           ruleset_id, ruleset_version, formula_id, formula_version,
                           formula_fingerprint, formula_fingerprint_algorithm_id,
                           output_field_name, output_provenance, output_value,
                           input_count, created_at, record_fingerprint,
                           fingerprint_algorithm_id)
                       VALUES ('x3', 'n', 'e', 'd', 'c', 's', 'sha256-v1',
                               'r', '1', 'f', '1', 'f', 'sha256-v1',
                               'total.gross', 'DERIVED', '1',
                               0, 'now', 'f', 'sha256-v1')""")
        finally:
            raw.close()
