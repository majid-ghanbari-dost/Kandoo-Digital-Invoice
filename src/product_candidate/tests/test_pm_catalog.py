"""WP-8.1 catalog-identity register tests — explicit, idempotent,
append-only registration; UNIQUE definitiveness backstop; verbatim storage;
VOR reads (SPEC §3/§5/§6/§7; OD-PM2/PM3/PM5)."""
import sqlite3

from pc_helpers import (
    CatalogIdentityReplay,
    CatalogIdentityRegistered,
    CatalogReadSuccess,
    PC_KIND,
    ProductCandidateStack,
)


def test_registration_happy_path_creates_one_verbatim_identity(stack):
    outcome = stack.register("SKU", "SKU-A-001")
    assert isinstance(outcome, CatalogIdentityRegistered)
    record = outcome.catalog_identity
    assert record.identifier_kind == "SKU"
    assert record.identifier_value == "SKU-A-001"     # verbatim (OD-PM3)
    assert record.record_fingerprint                   # sha256-v1 anchor
    assert record.fingerprint_algorithm_id == "sha256-v1"
    assert len(stack.products.catalog()) == 1


def test_re_registration_of_same_identifier_is_verbatim_replay(stack):
    first = stack.register("SKU", "SKU-A-001").catalog_identity
    second = stack.products.register_catalog_identity("SKU", "SKU-A-001")
    assert isinstance(second, CatalogIdentityReplay)
    assert second.catalog_identity == first            # VERBATIM — no new row
    assert len(stack.products.catalog()) == 1


def test_distinct_identifiers_coexist_in_the_register(stack):
    stack.register("SKU", "SKU-A-001")
    stack.register("SKU", "SKU-B-002")
    stack.register("EAN", "SKU-A-001")   # different kind — different identity
    catalog = stack.products.catalog()
    assert len(catalog) == 3
    assert {(c.identifier_kind, c.identifier_value) for c in catalog} == {
        ("SKU", "SKU-A-001"), ("SKU", "SKU-B-002"), ("EAN", "SKU-A-001")}


def test_whitespace_is_stored_verbatim_no_normalization_here(stack):
    """P4.1 is the sole normalizer — the register never trims/folds
    (OD-PM3): ' SKU-1' and 'SKU-1' are DIFFERENT declared identifiers."""
    stack.register("SKU", " SKU-1")
    stack.register("SKU", "SKU-1")
    assert len(stack.products.catalog()) == 2


def test_empty_kind_or_value_refused_zero_residue(stack):
    for kind, value in (("", "SKU-1"), ("SKU", ""), ("", "")):
        outcome = stack.products.register_catalog_identity(kind, value)
        assert type(outcome).__name__ == "CatalogRegistrationRefused", outcome
    assert len(stack.products.catalog()) == 0


def test_unique_backstop_is_a_real_database_constraint(stack):
    stack.register("SKU", "SKU-A-001")
    conn = sqlite3.connect(str(stack.product_db))
    try:
        try:
            conn.execute(
                "INSERT INTO catalog_identities (catalog_identity_id, "
                "identifier_kind, identifier_value, created_at, "
                "record_fingerprint, fingerprint_algorithm_id) "
                "VALUES ('forged', 'SKU', 'SKU-A-001', 't', 'fp', 'a')")
            conn.commit()
            raise AssertionError("UNIQUE definitiveness backstop missing")
        except sqlite3.IntegrityError:
            pass
    finally:
        conn.close()
    assert len(stack.products.catalog()) == 1


def test_check_gates_refuse_empty_identifier_columns_via_direct_sql(stack):
    conn = sqlite3.connect(str(stack.product_db))
    try:
        for kind, value in (("", "v"), ("k", "")):
            try:
                conn.execute(
                    "INSERT INTO catalog_identities (catalog_identity_id, "
                    "identifier_kind, identifier_value, created_at, "
                    "record_fingerprint, fingerprint_algorithm_id) "
                    "VALUES ('x', ?, ?, 't', 'fp', 'a')", (kind, value))
                conn.commit()
                raise AssertionError("CHECK gate missing for empty identifier")
            except sqlite3.IntegrityError:
                pass
    finally:
        conn.close()


def test_verified_catalog_read_and_refused_unknown_id(stack):
    registered = stack.register("SKU", "SKU-A-001").catalog_identity
    read = stack.products.read_catalog_identity(registered.catalog_identity_id)
    assert isinstance(read, CatalogReadSuccess)
    assert read.catalog_identity == registered
    refused = stack.products.read_catalog_identity("missing")
    assert type(refused).__name__ == "CatalogReadRefused", refused


def test_tampered_catalog_row_is_withheld_never_served(stack):
    registered = stack.register("SKU", "SKU-A-001").catalog_identity
    conn = sqlite3.connect(str(stack.product_db))
    try:
        conn.execute(
            "UPDATE catalog_identities SET identifier_value = 'forged' "
            "WHERE catalog_identity_id = ?",
            (registered.catalog_identity_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.products.read_catalog_identity(registered.catalog_identity_id)
    assert type(read).__name__ == "CatalogReadIntegrityFailure", read


def test_catalog_survives_restart_and_still_verifies(stack, make_stack):
    registered = stack.register("SKU", "SKU-A-001").catalog_identity
    stack.close()
    reopened = make_stack()
    try:
        read = reopened.products.read_catalog_identity(
            registered.catalog_identity_id)
        assert isinstance(read, CatalogReadSuccess)
        assert read.catalog_identity == registered
        replay = reopened.products.register_catalog_identity("SKU", "SKU-A-001")
        assert isinstance(replay, CatalogIdentityReplay)   # durable idempotency
        assert len(reopened.products.catalog()) == 1
    finally:
        reopened.close()
