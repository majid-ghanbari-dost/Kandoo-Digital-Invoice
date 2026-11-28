# Q-PYB-01 — governance publication to Kandoo `main` is BLOCKED (token write scope)

**From:** PY-B (session `arena/b8ba8d2e-kandoo-digital-invoice`), 2026-11-28
**Item:** docs/BACKLOG.md PY-A/PY-B item 3 — "E-72 vectors accepted by C# and PHP", acceptance evidence in `docs/vectors/` + one decision line (TASKS/PY-B.md item 1).
**Status of the item itself:** DONE-green locally (verdict ACCEPT, evidence complete). ONLY the cross-repo publication is BLOCKED.

## Verbatim errors (2026-11-28, token `GH_TOKEN` as `majid-ghanbari-dost`)

- REST create blob: `gh: Resource not accessible by integration (HTTP 403)` — `{"message":"Resource not accessible by integration","documentation_url":"https://docs.github.com/rest/git/blobs#create-a-blob","status":"403"}`
- REST contents create: `{"message":"Resource not accessible by integration","documentation_url":"https://docs.github.com/rest/repos/contents#create-or-update-file-contents","status":"403"}`
- REST issue comment: `{"message":"Resource not accessible by integration","documentation_url":"https://docs.github.com/rest/issues/comments#create-an-issue-comment","status":"403"}`
- Git push dry-run: `remote: Permission to majid-ghanbari-dost/Kandoo.git denied to majid-ghanbari-dost.` / `fatal: unable to access 'https://github.com/majid-ghanbari-dost/Kandoo.git/': The requested URL returned error: 403`

Reads from `Kandoo` and `kandoo-cloud-php` work; writes to `Kandoo-Digital-Invoice` work. The token is scoped to the working repo only.

## Ready-to-publish payload (byte-stable, verified)

1. `docs/vectors/e72-canonical-invoice-r3-acceptance.json` → `Kandoo:docs/vectors/e72-canonical-invoice-r3-acceptance.json` (this repo, byte-identical to `tests/golden/e72/cross-lane-acceptance.json`).
2. Decision line drafted in `docs/decisions-made.md` (this repo) under "PY-B E-72 cross-lane acceptance (PM-30), 2026-11-28" → append as Decision 56 in `Kandoo:docs/decisions-made.md`.

## Action needed (owner/manager)

Grant the session's GitHub token write access to `majid-ghanbari-dost/Kandoo` (contents + issues), or apply the two files above on `Kandoo` `main`. The moment access exists, PY-B publishes both in one commit (no content changes needed).
