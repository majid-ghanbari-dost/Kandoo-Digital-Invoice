# O15 local operator labels v1

The extractor can generate `operator-labels.local.json` from the `review-evidence/` directory with either:

```powershell
kandoo-extract.exe operator-label-template `
  --evidence-dir C:\Users\<owner>\AppData\Local\Kandoo\O15\run-001\review-evidence
```

or, when using the source checkout:

```powershell
python scripts/create_operator_label_template.py `
  --evidence-dir C:\Users\<owner>\AppData\Local\Kandoo\O15\run-001\review-evidence
```

The demo wrapper creates this blank file automatically. The generator refuses repository/bundle destinations, requires the label file to stay in the evidence directory so crop references remain relative, and never overwrites an existing label file. The JSON is validated by `schemas/o15/operator-label-v1.schema.json` and starts with `read_correctly: null` and `corrected_value: null` for each numeric field.

## Fill one entry

- `read_correctly: true`: the displayed machine `value` matches the operator's reading; keep `corrected_value: null`.
- `read_correctly: false`: the machine reading is wrong; enter the operator-confirmed text in `corrected_value`.
- Keep both values null when the field cannot be judged. Do not label a `layout` placeholder as a field.

The template preserves the machine value, confidence, reason, and crop reference for audit. It contains no training command and is never applied to the Glyph template bank; labels are local review records only. Corrected values may contain real invoice data, so keep the file, crops, and capture on the owner's machine. Do not commit, upload, or paste them into chat. No online learning is performed.
