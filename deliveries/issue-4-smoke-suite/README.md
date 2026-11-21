# Issue #4 delivery — aggregate isolated smoke execution

## Scope

This additive developer-verification capability gives the repository one command to run its existing smoke scenarios from fresh, isolated temporary paths. It does not add Windows/Android application behavior, a product CLI, customer roles, receipt presentation, inventory policy, or POS/Holoo integration.

The remaining user-facing gaps observed in source require decisions or contracts: UI/API design is prohibited by D-09; roles/access are DEF2; receipt presentation is DEF5; native inventory has no implementation contract under AS-02; production POS/Holoo mapping is blocked by WP-11.2/DEF6. Physical purge remains blocked under DEF4.

## Identity and coverage

- Verified live `main` base: `15901d6c88344c7f5e39471130d60c4dd5658b83`
- Verification time: `2026-10-12T11:23:13Z` (UTC; live GitHub API and `git ls-remote` agreed)
- Session branch: `arena/9dc17500-kandoo-digital-invoice` (fixed session branch)
- Implementation commit covered by the archive: `aca72c94fa83f40bd7e95bd9d62e650e80ce0808`
- Implementation tree: `2211f2a33e3657dd7f7a4f218fe6d3b41bc7b7b7`
- The archive contains all **341 tracked project files** at the implementation commit. The delivery directory, archive, manifest, and this README are metadata added after that commit and are intentionally excluded (non-recursive coverage).

## Changed implementation files

- `src/run_smoke_all.py` — discovers all top-level `run_smoke*.py` scripts except itself; runs each with the active Python interpreter, its own temporary workspace, bytecode writes disabled, and a bounded timeout; continues after failures and returns a nonzero status if any runner fails.
- `src/test_run_smoke_all.py` — focused tests for deterministic discovery, isolated paths, failure reporting/continuation, and empty discovery.

## Executed evidence

Environment: Linux sandbox, CPython 3.11.2, pytest 9.1.1 installed into `/tmp/kandoo-issue4-venv`; application/runtime code uses only the Python standard library.

```text
PYTHONDONTWRITEBYTECODE=1 /tmp/kandoo-issue4-venv/bin/python -m pytest src/test_run_smoke_all.py -q -p no:cacheprovider
4 passed in 0.02s — exit 0

PYTHONDONTWRITEBYTECODE=1 /tmp/kandoo-issue4-venv/bin/python src/run_smoke_all.py
22/22 smoke runners passed; 0 failed — exit 0

PYTHONDONTWRITEBYTECODE=1 /tmp/kandoo-issue4-venv/bin/python -m pytest -q -p no:cacheprovider
1687 passed in 240.41s — exit 0
```

## Delivery artifacts and verification

- Archive: `kandoo-issue4-smoke-suite-aca72c94.zip`
- Archive SHA-256: `b48fabfb6b26db41d719d91121a31a084926f7e93b6861049700cb448e792f93`
- Manifest: `MANIFEST-SHA256.txt` — 341 rows; each row records archive-relative path, byte length, and SHA-256.
- Manifest file SHA-256: `0f3538bcebd95145005605256bb621921229e9ffe4a405ff33dccddd080fef97`
- Separate archive hash record: `ARCHIVE-SHA256.txt`
- Verification actually performed: `unzip -tq` reported no compressed-data errors; `sha256sum -c ARCHIVE-SHA256.txt` returned `OK`; the manifest was independently recomputed from files extracted from the ZIP and matched exactly (`MANIFEST-VERIFY: MATCH`, all 341 files).

Re-check archive checksum/integrity from this directory:

```bash
sha256sum -c ARCHIVE-SHA256.txt
unzip -tq kandoo-issue4-smoke-suite-aca72c94.zip
```

## Disposition

No frozen contract or governance-owned file was changed. The capability is a smoke/test orchestration tool, not a user-facing application. Remaining product-policy blockers are listed above and in the PR/Issue report. Rollback requires reverting the additive implementation commit and the later delivery-metadata commit; there is no database migration or customer data to reverse.

**NOT MERGED — awaiting Product Owner approval.**
