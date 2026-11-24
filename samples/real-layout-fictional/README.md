# samples/real-layout-fictional

Layout real, content fictional. Certified by the Product Owner on 2026-11-23 (chat statement: the invoices have a real structure; the data inside is fictional so that no real customer information can leak).

- Source: repository `majid-ghanbari-dost/agent-github-test`, folder `DiagnosticResults/` (capture of 2026-11-07: `Job_2_14050816_135747_753`, `Job_3_14050816_135803_641`, `Unassigned`). Ground truth entered by the PO: invoice no. 34, date 1405.08.16, five lines, payable 49,547,706.
- Allowed use: E-70, E-71, E-73, E-74 and the two local checks of ORDER 16/17 (rule PM-17 in the C# repo, `docs/pm-log/2026-11-23.md`).
- Forbidden: adding any real customer name, phone number or real sale to this folder. If a file is found to contain such data, stop, remove it from git history, and report to the PM.
- Layout of this folder (PO uploads it by hand from the source repo):
  `samples/real-layout-fictional/DiagnosticResults/<same sub-folders as the source>`
