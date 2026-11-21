# Python CI status (E-17)

The Ubuntu GitHub Actions workflow at
[`.github/workflows/python-tests.yml`](../.github/workflows/python-tests.yml)
checks Python **3.11** and **3.12** and runs the existing repository suite with
`python -m pytest -q`. Its Python test dependencies are `pytest`, Pillow, and
`jsonschema>=4.18,<5`.

The workflow does **not** install Tesseract or `pytesseract`. Glyph-only image
classification and the adapter's explicit no-Tesseract regression test are
covered without requiring an external OCR executable. This CI scope does not
claim that Tesseract-backed OCR or Windows/Holo printing is validated.

**Owner/verifier CI result: PENDING.** Local validation on Python 3.11 ran
`python -m pytest -q`: **1,898 passed, 82 subtests passed**. This is not a
substitute for the GitHub Actions result, especially the Python 3.12 matrix
leg. The result must be relayed by the owner/verifier; this note will be updated
under E-18 only after that report is received. No Actions result has been
inspected or recorded here.
