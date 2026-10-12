# Issue #4 continuation — Digital Issuance composition: exact source delivery

- Delivery (covered) commit: `4d16ecf445e82ce854a8bac686376387d8b174cb`
- Delivery tree: `0c27e85a5b91a991ecf7c0732a21070749e15c30`
- Tested source commit (code + tests + smoke bytes): `93e1c6e8b3e225f4351cf87214307ec98431d673`
- Base `main` (verified via `git ls-remote`): `2d61b4dd61837810134cfcd97df8e7d4c0eba9b0`
- Branch: `arena/5fbd6749-kandoo-digital-invoice`
- Archive: `project.zip` — **335 files, 382 ZIP entries**, complete tracked tree of the delivery commit.
- Archive SHA-256: `586357463638a209e83385b53125d73263a20755bfa508695e90154cd580232e`
- Manifest SHA-256 (hash of `MANIFEST-SHA256.txt` itself): `f903c40e68f47ae4e8d1fe572f49794fcd74a39bee787bce0b01fb753d5feb6c`
- Executed on the tested source commit: focused suite **29 passed**; full regression
  **1683 passed** (1654 baseline + 29 new); **all 22 smoke runners EXIT_CODE=0**
  (including the new 8-step `run_smoke_issuance.py` → `SMOKE OK — 8 steps`).
  Raw outputs and the environment record are in `evidence/`.
- Report and bounded handoff: `specs/ISSUE-4-issuance-composition-report.md`.

## Coverage / nonrecursive publication rule (GOV-PP-01 §ب)

The archive and manifest cover the **delivery commit above** — including all
pre-existing tracked files, the new `src/issuance/` package and tests, the smoke
runner, the report, the register/handoff updates and the raw `evidence/` files.
They do **not** recursively include this README, this ZIP, its own manifest or
checksum: those four files are added by a subsequent metadata-only commit. No source
or test byte changes between the tested, delivery and metadata commits — the proof
is recorded in `evidence/boundary-check.txt` and restated here:

```text
git diff --stat 93e1c6e8b3e225f4351cf87214307ec98431d673 4d16ecf445e82ce854a8bac686376387d8b174cb -- '*.py'
(no output — no Python file changed after the tested commit)
```

## Independent verification

From this directory:

```bash
sha256sum -c ARCHIVE-SHA256.txt
checkout=$(mktemp -d)
unzip -q project.zip -d "$checkout"
manifest="$PWD/MANIFEST-SHA256.txt"
(cd "$checkout" && sha256sum -c "$manifest")
# With pytest installed; no application/runtime dependencies to install:
(cd "$checkout" && PYTHONDONTWRITEBYTECODE=1 python -m pytest src/issuance/tests -q -p no:cacheprovider)
(cd "$checkout" && PYTHONDONTWRITEBYTECODE=1 python src/run_smoke_issuance.py /tmp/kandoo-issuance-verify)
```

Regenerate the archive with `git archive --format=zip -o project.zip <delivery commit>`;
`MANIFEST-SHA256.txt` is the SHA-256 of each extracted file, paths sorted
lexicographically (`find . -type f | LC_ALL=C sort | xargs sha256sum`).

## Boundaries

Additive only: no pre-existing source or test file was modified
(`git diff --name-status origin/main...HEAD` shows only `A` entries). Frozen
decisions and the Deferred register are untouched; physical purge stays blocked and
is unreachable from the composed layer. No merge and no formal acceptance is
claimed — merge/acceptance authority remains with the Product Owner.

## Publication record (2026-10-12)

- Pull request: https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/10
  (base `main`, head `arena/5fbd6749-kandoo-digital-invoice`) — **OPEN, NOT merged**.
- Branch pushed and verified remotely: `git ls-remote origin
  refs/heads/arena/5fbd6749-kandoo-digital-invoice` equals local HEAD.
- PR delivery comment (substitute record of record):
  https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/10#issuecomment-6121949978
- **Issue #4 report: NOT POSTED.** Two attempts failed —
  `gh issue comment 4` (GraphQL addComment): `Message: Resource not accessible by
  integration, Locations: [{Line:1 Column:49}]`; REST `POST …/issues/4/comments`:
  **HTTP 403** `{"message":"Resource not accessible by integration"}`. The latest
  comment on Issue #4 is still the TM dispatch of `2026-10-12T09:07:13Z`.
  Per GOV-PP-01 §1/الف the copyable block lives in the PR body and in the PR
  delivery comment, and the Issue-report witness remains **UNMET**.
- The archive/manifest above cover the delivery commit
  `4d16ecf445e82ce854a8bac686376387d8b174cb`; this README is delivery metadata and is
  deliberately outside the archive (non-recursive rule). Later metadata-only changes
  to this README (publication record) do not alter the archive, its checksum or any
  source/test byte.

