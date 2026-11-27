# holdout-invoice-34 — HOLDOUT REFERENCE ONLY

Certified by the Product Owner: **layout real, content fictional** (PM-17). This folder holds the ORIGINAL invoice-34 receipt image (not the ESC/POS raster).

- File: `invoice_34.png` (PNG, 1160 x 2660, 8-bit grayscale, 308,137 bytes)
- sha256: `b92185fe1f028e215f54dbda25aaee3edfb6613661aaec53f0c1832e55346013`
  Verify the hash before use (`sha256sum invoice_34.png`). If the file is missing or the hash differs, stop and report; do not substitute another image.
- Rule (Decision 28): this image is a **holdout reference only**. It is **never training data**, never used to tune, fit or calibrate anything, and never copied elsewhere in the repo.
- Use: Stage 2 of PY-T3 (E-74): the lane's own field-level read of THIS image is the authoritative ground-truth confirmation. Read it independently first, print the raw readings, then compare with the provisional labels in `PY-T3`. The PM added NO field values to this README on purpose, so the holdout stays independent.
- Provenance: the PO supplied the image (2026-11-26); the PM uploaded this README and verified the file hash on the PO's copy.
