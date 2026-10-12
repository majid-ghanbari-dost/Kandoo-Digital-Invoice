# Issue #4 replacement pipeline — exact source delivery

- Source commit: `7b9b288f387afd9d3af29d9e1280121d6c66487c`
- Source tree: `a80d9a447b9d2e46845f610395d8150b41bd4379`
- Branch: `arena/61fdaf1b-kandoo-digital-invoice`
- Base main: `b6c3e08b49bad97429d50dcf135095a0cb6be536`
- Archive: `project.zip` — **316 files**, complete tracked source tree.
- Archive SHA-256: `c96f3fdf269a17e0e1d9289efcc83b9e6926530e4d364258c9a67c753cfe2df5`
- Manifest SHA-256: `44f4b8902b97ccea30c87946a529fa033fca52eebca628f284241dd78148e403`
- Executed: ZIP entry set equals `git ls-tree -r` and every ZIP file equals its
  exact source-commit Git blob; 316/316 files verified.
- Executed tests on that source content: 48 focused PASS; 1654 full regression
  PASS; all 21 existing smoke runners PASS. Raw outputs in `evidence/`.
- Report and bounded continuation handoff:
  `specs/ISSUE-4-pipeline-implementation-report.md`.

## Coverage / nonrecursive publication rule

Per GOV-PP-01, the archive and manifest cover the **source commit above**, including
source/tests/report/evidence and all pre-existing tracked files (including the
unchanged diagnostic and historical governance delivery). They do not recursively
include this README, this ZIP, its own manifest or checksum. Those four files are
added in a subsequent metadata-only publication commit. No source/test changes occur
between the source and publication commits. The final publication SHA is recorded
in the PR and final response; embedding it in itself would be self-referential.

All existing baseline files remain byte-identical. This is a PO-authorized NEW
replacement implementation, not the lost 19-file package. No merge or formal
acceptance is claimed. D-09/CLI scope, DEF4/5/6 and WP-12.3 stay pending.

## Independent verification

From this directory:

```bash
sha256sum -c ARCHIVE-SHA256.txt
checkout=$(mktemp -d)
unzip -q project.zip -d "$checkout"
manifest="$PWD/MANIFEST-SHA256.txt"
(cd "$checkout" && sha256sum -c "$manifest")
# With pytest installed; no application/runtime dependencies to install:
(cd "$checkout" && PYTHONDONTWRITEBYTECODE=1 python -m pytest src/pipeline/tests -q -p no:cacheprovider)
```

Regenerate source archive with `git archive --format=zip 7b9b288f387afd9d3af29d9e1280121d6c66487c > project.zip`.
`MANIFEST-SHA256.txt` is SHA-256 of each extracted file, paths sorted lexicographically.

## Publication audit note

The earlier authorization comment attempt on Issue #4 returned:
`Message: Resource not accessible by integration, Locations: [{Line:1 Column:49}]`.
It was NOT posted. Authorization and delivery evidence are to be recorded in the
PR body/comment under GOV-PP-01 fallback. The Issue-report witness remains UNMET
until a real comment is posted by an authorized account; no success is inferred.
