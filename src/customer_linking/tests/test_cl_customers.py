"""WP-9.1 customer-identity register tests — explicit, idempotent,
append-only registration of EXISTING customers; UNIQUE definitiveness
backstop; verbatim storage; VOR reads; NO capture path (D-06/DEF3/OD-CL2)
(SPEC §3/§5/§6/§7)."""
import sqlite3

from cl_helpers import (
    CustomerIdentityReplay,
    CustomerIdentityRegistered,
    CustomerReadSuccess,
    CustomerLinkingStack,
    CL_KIND,
)


def test_registration_happy_path_creates_one_verbatim_identity(stack):
    outcome = stack.register("CUST-CODE", "CUST-A-001")
    assert isinstance(outcome, CustomerIdentityRegistered)
    record = outcome.customer_identity
    assert record.identifier_kind == "CUST-CODE"
    assert record.identifier_value == "CUST-A-001"    # verbatim (OD-CL3)
    assert record.record_fingerprint                   # sha256-v1 anchor
    assert record.fingerprint_algorithm_id == "sha256-v1"
    assert len(stack.customers_svc.customers()) == 1


def test_re_registration_of_same_identifier_is_verbatim_replay(stack):
    first = stack.register("CUST-CODE", "CUST-A-001").customer_identity
    second = stack.customers_svc.register_customer_identity("CUST-CODE",
                                                            "CUST-A-001")
    assert isinstance(second, CustomerIdentityReplay)
    assert second.customer_identity == first            # VERBATIM — no new row
    assert len(stack.customers_svc.customers()) == 1


def test_distinct_identifiers_coexist_in_the_register(stack):
    stack.register("CUST-CODE", "CUST-A-001")
    stack.register("CUST-CODE", "CUST-B-002")
    stack.register("NATIONAL-ID", "CUST-A-001")   # different kind — different
    customers = stack.customers_svc.customers()
    assert len(customers) == 3
    assert {(c.identifier_kind, c.identifier_value) for c in customers} == {
        ("CUST-CODE", "CUST-A-001"), ("CUST-CODE", "CUST-B-002"),
        ("NATIONAL-ID", "CUST-A-001")}


def test_whitespace_is_stored_verbatim_no_normalization_here(stack):
    """P4.1 is the sole normalizer — the register never trims/folds
    (OD-CL3): ' CUST-1' and 'CUST-1' are DIFFERENT declared identifiers."""
    stack.register("CUST-CODE", " CUST-1")
    stack.register("CUST-CODE", "CUST-1")
    assert len(stack.customers_svc.customers()) == 2


def test_empty_kind_or_value_refused_zero_residue(stack):
    for kind, value in (("", "CUST-1"), ("CUST-CODE", ""), ("", "")):
        outcome = stack.customers_svc.register_customer_identity(kind, value)
        assert type(outcome).__name__ == "CustomerRegistrationRefused", outcome
    assert len(stack.customers_svc.customers()) == 0


def test_unique_backstop_is_a_real_database_constraint(stack):
    stack.register("CUST-CODE", "CUST-A-001")
    conn = sqlite3.connect(str(stack.customer_db))
    try:
        try:
            conn.execute(
                "INSERT INTO customer_identities (customer_identity_id, "
                "identifier_kind, identifier_value, created_at, "
                "record_fingerprint, fingerprint_algorithm_id) "
                "VALUES ('forged', 'CUST-CODE', 'CUST-A-001', 't', 'fp',"
                " 'a')")
            conn.commit()
            raise AssertionError("UNIQUE definitiveness backstop missing")
        except sqlite3.IntegrityError:
            pass
    finally:
        conn.close()
    assert len(stack.customers_svc.customers()) == 1


def test_check_gates_refuse_empty_identifier_columns_via_direct_sql(stack):
    conn = sqlite3.connect(str(stack.customer_db))
    try:
        for kind, value in (("", "v"), ("k", "")):
            try:
                conn.execute(
                    "INSERT INTO customer_identities (customer_identity_id,"
                    " identifier_kind, identifier_value, created_at, "
                    "record_fingerprint, fingerprint_algorithm_id) "
                    "VALUES ('x', ?, ?, 't', 'fp', 'a')", (kind, value))
                conn.commit()
                raise AssertionError("CHECK gate missing for empty identifier")
            except sqlite3.IntegrityError:
                pass
    finally:
        conn.close()


def test_verified_customer_read_and_refused_unknown_id(stack):
    registered = stack.register("CUST-CODE", "CUST-A-001").customer_identity
    read = stack.customers_svc.read_customer_identity(
        registered.customer_identity_id)
    assert isinstance(read, CustomerReadSuccess)
    assert read.customer_identity == registered
    refused = stack.customers_svc.read_customer_identity("missing")
    assert type(refused).__name__ == "CustomerReadRefused", refused


def test_tampered_customer_row_is_withheld_never_served(stack):
    registered = stack.register("CUST-CODE", "CUST-A-001").customer_identity
    conn = sqlite3.connect(str(stack.customer_db))
    try:
        conn.execute(
            "UPDATE customer_identities SET identifier_value = 'forged' "
            "WHERE customer_identity_id = ?",
            (registered.customer_identity_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.customers_svc.read_customer_identity(
        registered.customer_identity_id)
    assert type(read).__name__ == "CustomerReadIntegrityFailure", read


def test_customers_survive_restart_and_still_verify(stack, make_stack):
    registered = stack.register("CUST-CODE", "CUST-A-001").customer_identity
    stack.close()
    reopened = make_stack()
    try:
        read = reopened.customers_svc.read_customer_identity(
            registered.customer_identity_id)
        assert isinstance(read, CustomerReadSuccess)
        assert read.customer_identity == registered
        replay = reopened.customers_svc.register_customer_identity(
            "CUST-CODE", "CUST-A-001")
        assert isinstance(replay, CustomerIdentityReplay)  # durable idempotency
        assert len(reopened.customers_svc.customers()) == 1
    finally:
        reopened.close()
