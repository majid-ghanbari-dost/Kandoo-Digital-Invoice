"""WP-12.2 runner tests — the measured path, pinned observations, report
determinism, aggregate counts (SPEC-WP122 §4/§5/§7/§9)."""
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from calibration import (  # noqa: E402
    CLASS_MATCH,
    CLASS_MISSING,
    CLASS_UNEXPECTED_PRESENT,
    DECISION_ACCEPTED,
    DECISION_REVIEW,
    RunConfig,
)


def _report(run_service, run_config, manifest, read):
    service = run_service() if callable(run_service) else run_service
    return service.run(read, run_config(manifest))


def _obs_by_ordinal(report):
    return {obs.ordinal: obs for obs in report.entry_observations}


# ---------------------------------------------------------------------------
# Clean corpus — the ACCEPTED path
# ---------------------------------------------------------------------------

def test_clean_corpus_reaches_gate_accepted(run_service, run_config,
                                            clean_corpus):
    manifest, read = clean_corpus
    report = _report(run_service, run_config, manifest, read)
    assert report.corpus_entry_count == 3
    assert report.gate_counts == {DECISION_ACCEPTED: 3}
    for obs in report.entry_observations:
        assert obs.stage_reached == "gate"
        assert obs.gate_decision == DECISION_ACCEPTED
        assert obs.gate_reason is None
        # the four reference rules ALL hold on the clean path
        outcomes = {rule_id: outcome for rule_id, outcome, _ in
                    obs.reference_outcomes}
        assert set(outcomes) == {
            "kandoo-val-total-net-present",
            "kandoo-val-total-gross-consistency",
            "kandoo-val-total-gross-tolerance",
            "kandoo-val-total-gross-rounded",
        }
        assert set(outcomes.values()) == {"VALID"}


def test_clean_corpus_field_observations_all_match(run_service, run_config,
                                                   clean_corpus):
    manifest, read = clean_corpus
    report = _report(run_service, run_config, manifest, read)
    assert set(report.field_counts) == {
        "invoice.number", "invoice.date", "total.net", "tax.amount"}
    for field_name, counts in report.field_counts.items():
        assert counts == {CLASS_MATCH: 3}, (field_name, counts)


def test_clean_corpus_sweep_is_honestly_not_evaluable(run_service, run_config,
                                                      clean_corpus):
    """The clean template prints NO gross line — the D-08 agreement rule has
    no declared gross to compare: not_evaluable across ALL candidates."""
    manifest, read = clean_corpus
    report = _report(run_service, run_config, manifest, read)
    assert len(report.candidate_results) == 3
    for result in report.candidate_results:
        assert result.evaluated == 0
        assert result.not_evaluable == 3
        assert result.within_tolerance == 0
        assert result.beyond_tolerance == 0


# ---------------------------------------------------------------------------
# Rounding-probe corpus — the D-08 sweep surface
# ---------------------------------------------------------------------------

def test_rounding_corpus_routes_to_review(run_service, run_config,
                                          rounding_corpus):
    """The printed gross engages the frozen derivation output-present gate —
    the pipeline holds the uncertainty upstream (REVIEW), by frozen design."""
    manifest, read = rounding_corpus
    report = _report(run_service, run_config, manifest, read)
    assert report.gate_counts == {DECISION_REVIEW: 6}
    for obs in report.entry_observations:
        assert obs.gate_decision == DECISION_REVIEW
        assert obs.gate_reason  # the frozen relayed reason is present


def test_rounding_corpus_sweep_texture_pinned(run_service, run_config,
                                              rounding_corpus):
    """The ±1/±2-cent residuals against the declared candidates: |r| ≤ t is
    within. The 0.00 candidate exceeds EVERY residual; 0.02 contains ALL."""
    manifest, read = rounding_corpus
    report = _report(run_service, run_config, manifest, read)
    results = {r.tolerance: r for r in report.candidate_results}
    assert results["0.00"].beyond_tolerance == 6
    assert results["0.00"].within_tolerance == 0
    assert results["0.02"].beyond_tolerance == 0
    assert results["0.02"].within_tolerance == 6
    # the 0.01 candidate splits the residual vocabulary (±1 within, ±2 beyond)
    assert results["0.01"].evaluated == 6
    assert results["0.01"].within_tolerance >= 1
    assert results["0.01"].beyond_tolerance >= 1
    assert results["0.01"].within_tolerance + \
        results["0.01"].beyond_tolerance == 6


def test_rounding_corpus_field_labels_match_printed_values(run_service,
                                                           run_config,
                                                           rounding_corpus):
    """Labels declare the PRINTED values verbatim — the pipeline reproduces
    them exactly (the residual is a DOCUMENT property, not a pipeline error)."""
    manifest, read = rounding_corpus
    report = _report(run_service, run_config, manifest, read)
    assert set(report.field_counts) == {
        "invoice.number", "invoice.date", "total.net", "tax.amount",
        "total.gross"}
    for field_name, counts in report.field_counts.items():
        assert counts == {CLASS_MATCH: 6}, (field_name, counts)


# ---------------------------------------------------------------------------
# Review-probe corpus — the uncertainty path + ABSENT labels
# ---------------------------------------------------------------------------

def test_review_corpus_absent_tax_is_matched_as_declared(run_service,
                                                         run_config,
                                                         review_corpus):
    manifest, read = review_corpus
    report = _report(run_service, run_config, manifest, read)
    assert report.gate_counts == {DECISION_REVIEW: 2}
    # tax.amount is DECLARED ABSENT and the pipeline agrees (no row)
    assert report.field_counts["tax.amount"] == {CLASS_MATCH: 2}
    # the other labels are VALUE labels and match
    for field_name in ("invoice.number", "invoice.date", "total.net"):
        assert report.field_counts[field_name] == {CLASS_MATCH: 2}


def test_review_corpus_derivation_deferred_is_observed(run_service, run_config,
                                                       review_corpus):
    manifest, read = review_corpus
    report = _report(run_service, run_config, manifest, read)
    obs = _obs_by_ordinal(report)[0]
    outcomes = {rule_id: (outcome, reason)
                for rule_id, outcome, reason in obs.reference_outcomes}
    # consistency/tolerance/rounded all lack an input (no tax, no derived
    # gross — the frozen rules honestly defer)
    for rule_id in ("kandoo-val-total-gross-consistency",
                    "kandoo-val-total-gross-tolerance",
                    "kandoo-val-total-gross-rounded"):
        assert outcomes[rule_id][0] == "DEFERRED"
    assert outcomes["kandoo-val-total-net-present"][0] == "VALID"


# ---------------------------------------------------------------------------
# Report determinism + shape (SPEC §2.7)
# ---------------------------------------------------------------------------

def test_report_determinism_across_independent_workspaces(run_service,
                                                          run_config,
                                                          rounding_corpus):
    manifest, read = rounding_corpus
    first = _report(run_service("det-a"), run_config, manifest, read)
    second = _report(run_service("det-b"), run_config, manifest, read)
    assert first.to_json_bytes() == second.to_json_bytes()


def test_report_determinism_clean_corpus(run_service, run_config,
                                         clean_corpus):
    manifest, read = clean_corpus
    first = _report(run_service("det-c"), run_config, manifest, read)
    second = _report(run_service("det-d"), run_config, manifest, read)
    assert first.to_json_bytes() == second.to_json_bytes()


def test_report_json_has_no_volatile_content(run_service, run_config,
                                             clean_corpus):
    """No uuid-shaped scalars, no ISO timestamps, no filesystem paths."""
    import re
    manifest, read = clean_corpus
    report = _report(run_service(), run_config, manifest, read)
    text = report.to_json_bytes().decode("utf-8")
    uuid_re = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    assert not uuid_re.search(text), "report carries uuid bookkeeping"
    iso_re = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
    assert not iso_re.search(text), "report carries a timestamp"
    assert "/tmp" not in text and str(SRC) not in text, \
        "report carries filesystem paths"


def test_report_config_echo_is_verbatim(run_service, run_config,
                                        clean_corpus):
    manifest, read = clean_corpus
    report = _report(run_service(), run_config, manifest, read)
    payload = json.loads(report.to_json_bytes())
    config = payload["config"]
    assert config["corpus_version_id"] == manifest.corpus_version_id
    assert config["origin"] == "HOLOO_CAPTURE"
    assert config["engine_id"] == "reference-delimited-v1"
    assert config["formula_id"] == "kandoo-der-total-gross-from-net-tax"
    assert config["declared_reference_parameters"] == {
        "tolerance": "0.02", "precision": 2, "mode": "HALF_UP"}
    assert config["candidate_tolerances"] == ["0.00", "0.01", "0.02"]
    assert config["identity_binding"] == [
        {"role": "INVOICE_DATE", "source_field": "invoice.date"},
        {"role": "INVOICE_NUMBER", "source_field": "invoice.number"},
        {"role": "INVOICE_TOTAL", "source_field": "total.net"},
    ]


def test_report_counts_agree_with_observations(run_service, run_config,
                                               rounding_corpus):
    manifest, read = rounding_corpus
    report = _report(run_service(), run_config, manifest, read)
    obs = _obs_by_ordinal(report)
    assert sorted(obs) == list(range(6))
    total_classifications = sum(
        sum(counts.values()) for counts in report.field_counts.values())
    declared_labels = sum(
        len(entry.labels) for entry in read.entries)
    assert total_classifications == declared_labels
    # reference-rule totals: 6 entries × 4 rules
    for rule_id, counts in report.reference_rule_counts.items():
        assert sum(counts.values()) == 6, rule_id
