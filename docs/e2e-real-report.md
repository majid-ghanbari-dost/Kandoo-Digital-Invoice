# B2-3 real-invoice E2E diagnostic
Timestamp (UTC): 2026-10-17T20:34:15+00:00
Tesseract version: tesseract v5.5.3.20260724
Python version: 3.14.7
Pillow version: 12.3.0
Git HEAD SHA: 0841fa9cf8019718e0faa6f108a0655ef886cb2d
Image fixtures: 29.png, 31.png, 32.png, 33.png
Tesseract language: fas+eng
Minimum word confidence: 60.0
Glyph templates: src\templates.json
No cloud OCR, VLM, or network service is used.

## numeric_authority=glyph

### 29.png (invoice 29)
Reference payable bbox: [214, 820, 116, 28]
Tesseract diagnostic: Estimating resolution as 256
Detected 32 diacritics
Tesseract diagnostic: Estimating resolution as 256
Detected 32 diacritics
Outcome: ReviewRequired
Effective numeric authority: glyph
Reason: flat-text parser blocked: expected exactly one invoice date, OCR yielded 0; spatial parser: expected 3 internal table rules, found 0 long TSV boxes; no table columns could be assigned from TSV geometry; fields require review: invoice.date, invoice.payable, total.net; numeric OCR REVIEW cell(s): line.0.total, line.1.total, line.2.total, line.3.total, invoice.payable
Parsed numeric fields:
  invoice.payable=۷۳2
Numeric cell results:
  line.0.total: raw='۱,۴۵۰,۰۰۰'; status=REVIEW; confidence=99.98761904761905; bbox=[120, 533, 240, 593]; reason=arithmetic gate failed: payable '۷,?۶۰,۰۰۰' is not a well-formed amount
  line.0.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 533, 289, 593]; reason=None
  line.1.total: raw='۴,۸۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 604, 240, 661]; reason=arithmetic gate failed: payable '۷,?۶۰,۰۰۰' is not a well-formed amount
  line.1.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 604, 289, 661]; reason=None
  line.2.total: raw='۵۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 672, 240, 729]; reason=arithmetic gate failed: payable '۷,?۶۰,۰۰۰' is not a well-formed amount
  line.2.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 672, 289, 729]; reason=None
  line.3.total: raw='۵۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 740, 240, 798]; reason=arithmetic gate failed: payable '۷,?۶۰,۰۰۰' is not a well-formed amount
  line.3.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 740, 289, 798]; reason=None
  invoice.payable: raw='۷,?۶۰,۰۰۰'; status=REVIEW; confidence=0.0; bbox=[210, 816, 334, 852]; reason=glyph 3 not accepted: ambiguous: margin 0.118 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; full-page spatial assessment remains REVIEW; cell OCR is supplementary; arithmetic gate failed: payable '۷,?۶۰,۰۰۰' is not a well-formed amount
Runtime payable bbox (OCR word boxes): [214, 820, 116, 28]; status=REVIEW; reason=minimum field confidence 52.60 is below 60.00; reference=[214, 820, 116, 28]
Arithmetic gate: FAIL; line_sum=None; payable=None; extras=0; reason=payable '۷,?۶۰,۰۰۰' is not a well-formed amount

### 31.png (invoice 31)
Reference payable bbox: [214, 752, 116, 28]
Outcome: ReviewRequired
Effective numeric authority: glyph
Reason: flat-text parser blocked: expected exactly one invoice date, OCR yielded 0; spatial parser: no row-number token '1' was found in the rightmost table column; fields require review: invoice.date, invoice.payable, total.net; numeric OCR REVIEW cell(s): line.0.total, line.1.total, line.2.total, invoice.payable
Parsed numeric fields:
  invoice.payable=۴۲۵,۰۰۰و؟ ‏
Numeric cell results:
  line.0.total: raw='۹۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 533, 240, 593]; reason=arithmetic gate failed: payable '?,??۵,۰۰۰' is not a well-formed amount
  line.0.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 533, 289, 593]; reason=None
  line.1.total: raw='۹۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 604, 240, 661]; reason=arithmetic gate failed: payable '?,??۵,۰۰۰' is not a well-formed amount
  line.1.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 604, 289, 661]; reason=None
  line.2.total: raw='۴۸۵,۰۰۰'; status=REVIEW; confidence=99.98761904761905; bbox=[120, 672, 240, 730]; reason=arithmetic gate failed: payable '?,??۵,۰۰۰' is not a well-formed amount
  line.2.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 672, 289, 730]; reason=None
  invoice.payable: raw='?,??۵,۰۰۰'; status=REVIEW; confidence=0.0; bbox=[210, 748, 334, 784]; reason=glyph 1 not accepted: ambiguous: margin 0.133 below 0.150; glyph 3 not accepted: ambiguous: margin 0.118 below 0.150; glyph 4 not accepted: ambiguous: margin 0.133 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; full-page spatial assessment remains REVIEW; cell OCR is supplementary; arithmetic gate failed: payable '?,??۵,۰۰۰' is not a well-formed amount
Runtime payable bbox (OCR word boxes): [214, 752, 116, 28]; status=REVIEW; reason=minimum field confidence 7.47 is below 60.00; raw OCR value does not match the declared numeric format; reference=[214, 752, 116, 28]
Arithmetic gate: FAIL; line_sum=None; payable=None; extras=0; reason=payable '?,??۵,۰۰۰' is not a well-formed amount

### 32.png (invoice 32)
Reference payable bbox: [214, 888, 116, 28]
Outcome: ReviewRequired
Effective numeric authority: glyph
Reason: flat-text parser blocked: expected exactly one invoice date, OCR yielded 0; spatial parser: no row-number token '1' was found in the rightmost table column; fields require review: invoice.number, invoice.date, total.net
Parsed numeric fields:
  invoice.payable=۷,۸۵۰,۰۰۰
Numeric cell results:
  line.0.total: raw='۹۷۰,۰۰۰'; status=EXTRACTED; confidence=99.9847619047619; bbox=[120, 533, 240, 593]; reason=None
  line.0.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 533, 289, 593]; reason=None
  line.1.total: raw='۳,۹۵۰,۰۰۰'; status=EXTRACTED; confidence=99.9863492063492; bbox=[120, 604, 240, 661]; reason=None
  line.1.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 604, 289, 661]; reason=None
  line.2.total: raw='۱,۸۷۰,۰۰۰'; status=EXTRACTED; confidence=99.9847619047619; bbox=[120, 672, 240, 729]; reason=None
  line.2.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 672, 289, 729]; reason=None
  line.3.total: raw='۹۷۰,۰۰۰'; status=EXTRACTED; confidence=99.9847619047619; bbox=[120, 740, 240, 797]; reason=None
  line.3.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 740, 289, 797]; reason=None
  line.4.total: raw='۹۰,۰۰۰'; status=EXTRACTED; confidence=99.98761904761905; bbox=[120, 808, 240, 865]; reason=None
  line.4.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 808, 289, 865]; reason=None
  invoice.payable: raw='۷,۸۵۰,۰۰۰'; status=EXTRACTED; confidence=99.95936507936509; bbox=[210, 884, 334, 920]; reason=None
Runtime payable bbox (OCR word boxes): [214, 888, 116, 28]; status=EXTRACTED; reason=None; reference=[214, 888, 116, 28]
Arithmetic gate: PASS; line_sum=7850000; payable=7850000; extras=0; reason=None

### 33.png (invoice 33)
Reference payable bbox: [199, 1431, 147, 28]
Outcome: ReviewRequired
Effective numeric authority: glyph
Reason: flat-text parser blocked: expected exactly one invoice date, OCR yielded 0; spatial parser: row sequence 2 is missing before 4; only one increasing row-number anchor was recognized; fields require review: invoice.date, total.net; numeric OCR REVIEW cell(s): line.0.total, line.0.quantity, line.1.total, line.2.total, line.3.total, line.4.total, line.5.total, line.6.total, line.7.total, line.8.total, line.9.total, line.10.total, line.11.total, line.12.total, invoice.payable
Parsed numeric fields:
  invoice.payable=۳۴۷,۹۲۰,۰۰۰
Numeric cell results:
  line.0.total: raw='۷,۸۸۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 533, 240, 593]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.0.quantity: raw='?'; status=REVIEW; confidence=0.0; bbox=[248, 533, 289, 593]; reason=glyph 1 not accepted: ambiguous: margin 0.146 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format
  line.1.total: raw='۴,۸۵۰,۰۰۰'; status=REVIEW; confidence=99.98761904761905; bbox=[120, 604, 240, 661]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.1.quantity: raw='۱۰'; status=EXTRACTED; confidence=99.97047619047619; bbox=[248, 604, 289, 661]; reason=None
  line.2.total: raw='۸,۷۵۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 672, 240, 729]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.2.quantity: raw='۵'; status=EXTRACTED; confidence=99.97809523809524; bbox=[248, 672, 289, 729]; reason=None
  line.3.total: raw='۶,۴۰۰,۰۰۰'; status=REVIEW; confidence=99.98190476190476; bbox=[120, 740, 240, 797]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.3.quantity: raw='۲'; status=EXTRACTED; confidence=99.99809523809525; bbox=[248, 740, 289, 797]; reason=None
  line.4.total: raw='۴۹,۴۰۰,۰۰۰'; status=REVIEW; confidence=99.98761904761905; bbox=[120, 808, 240, 865]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.4.quantity: raw='۲۰'; status=EXTRACTED; confidence=99.97047619047619; bbox=[248, 808, 289, 865]; reason=None
  line.5.total: raw='۱,۵۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 876, 240, 933]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.5.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 876, 289, 933]; reason=None
  line.6.total: raw='۶,۹۰۰,۰۰۰'; status=REVIEW; confidence=99.98190476190476; bbox=[120, 944, 240, 1001]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.6.quantity: raw='۵'; status=EXTRACTED; confidence=99.97809523809524; bbox=[248, 944, 289, 1001]; reason=None
  line.7.total: raw='۶,۸۷۰,۰۰۰'; status=REVIEW; confidence=99.98190476190476; bbox=[120, 1012, 240, 1068]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.7.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 1012, 289, 1068]; reason=None
  line.8.total: raw='۳,۷۰۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 1079, 240, 1136]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.8.quantity: raw='۲'; status=EXTRACTED; confidence=99.99809523809525; bbox=[248, 1079, 289, 1136]; reason=None
  line.9.total: raw='??۹,۶۰۰,۰۰۰'; status=REVIEW; confidence=0.0; bbox=[120, 1147, 240, 1204]; reason=glyph 1 not accepted: ambiguous: margin 0.108 below 0.150; glyph 2 not accepted: ambiguous: margin 0.108 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.9.quantity: raw='۸'; status=EXTRACTED; confidence=66.1847619047619; bbox=[248, 1147, 289, 1204]; reason=None
  line.10.total: raw='۱۹,۰۵۰,۰۰۰'; status=REVIEW; confidence=99.98761904761905; bbox=[120, 1215, 240, 1272]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.10.quantity: raw='۱۵'; status=EXTRACTED; confidence=99.97809523809524; bbox=[248, 1215, 289, 1272]; reason=None
  line.11.total: raw='۱,۳۸۰,۰۰۰'; status=REVIEW; confidence=99.9863492063492; bbox=[120, 1283, 240, 1340]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.11.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 1283, 289, 1340]; reason=None
  line.12.total: raw='۱,۵۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 1351, 240, 1409]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.12.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 1351, 289, 1409]; reason=None
  invoice.payable: raw='??۷,۹?۰,۰۰۰'; status=REVIEW; confidence=0.0; bbox=[195, 1427, 350, 1463]; reason=glyph 1 not accepted: ambiguous: margin 0.142 below 0.150; glyph 2 not accepted: ambiguous: margin 0.118 below 0.150; glyph 6 not accepted: ambiguous: margin 0.133 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
Runtime payable bbox (OCR word boxes): [199, 1431, 147, 28]; status=EXTRACTED; reason=None; reference=[199, 1431, 147, 28]
Arithmetic gate: FAIL; line_sum=None; payable=None; extras=0; reason=line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount

## numeric_authority=tesseract_parse

### 29.png (invoice 29)
Reference payable bbox: [214, 820, 116, 28]
Outcome: ReviewRequired
Effective numeric authority: tesseract_parse
Reason: flat-text parser blocked: expected exactly one invoice date, OCR yielded 0; spatial parser: expected 3 internal table rules, found 0 long TSV boxes; no table columns could be assigned from TSV geometry; fields require review: invoice.date, invoice.payable, total.net; numeric OCR REVIEW cell(s): line.0.total, line.1.total, line.2.total, line.3.total, invoice.payable
Parsed numeric fields:
  invoice.payable=۷۳2
Numeric cell results:
  line.0.total: raw='۱,۴۵۰,۰۰۰'; status=REVIEW; confidence=99.98761904761905; bbox=[120, 533, 240, 593]; reason=arithmetic gate failed: payable '۷,?۶۰,۰۰۰' is not a well-formed amount
  line.0.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 533, 289, 593]; reason=None
  line.1.total: raw='۴,۸۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 604, 240, 661]; reason=arithmetic gate failed: payable '۷,?۶۰,۰۰۰' is not a well-formed amount
  line.1.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 604, 289, 661]; reason=None
  line.2.total: raw='۵۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 672, 240, 729]; reason=arithmetic gate failed: payable '۷,?۶۰,۰۰۰' is not a well-formed amount
  line.2.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 672, 289, 729]; reason=None
  line.3.total: raw='۵۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 740, 240, 798]; reason=arithmetic gate failed: payable '۷,?۶۰,۰۰۰' is not a well-formed amount
  line.3.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 740, 289, 798]; reason=None
  invoice.payable: raw='۷,?۶۰,۰۰۰'; status=REVIEW; confidence=0.0; bbox=[210, 816, 334, 852]; reason=glyph 3 not accepted: ambiguous: margin 0.118 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; full-page spatial assessment remains REVIEW; cell OCR is supplementary; arithmetic gate failed: payable '۷,?۶۰,۰۰۰' is not a well-formed amount
Runtime payable bbox (OCR word boxes): [214, 820, 116, 28]; status=REVIEW; reason=minimum field confidence 52.60 is below 60.00; reference=[214, 820, 116, 28]
Arithmetic gate: FAIL; line_sum=None; payable=None; extras=0; reason=payable '۷,?۶۰,۰۰۰' is not a well-formed amount

### 31.png (invoice 31)
Reference payable bbox: [214, 752, 116, 28]
Outcome: ReviewRequired
Effective numeric authority: tesseract_parse
Reason: flat-text parser blocked: expected exactly one invoice date, OCR yielded 0; spatial parser: no row-number token '1' was found in the rightmost table column; fields require review: invoice.date, invoice.payable, total.net; numeric OCR REVIEW cell(s): line.0.total, line.1.total, line.2.total, invoice.payable
Parsed numeric fields:
  invoice.payable=۴۲۵,۰۰۰و؟ ‏
Numeric cell results:
  line.0.total: raw='۹۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 533, 240, 593]; reason=arithmetic gate failed: payable '?,??۵,۰۰۰' is not a well-formed amount
  line.0.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 533, 289, 593]; reason=None
  line.1.total: raw='۹۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 604, 240, 661]; reason=arithmetic gate failed: payable '?,??۵,۰۰۰' is not a well-formed amount
  line.1.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 604, 289, 661]; reason=None
  line.2.total: raw='۴۸۵,۰۰۰'; status=REVIEW; confidence=99.98761904761905; bbox=[120, 672, 240, 730]; reason=arithmetic gate failed: payable '?,??۵,۰۰۰' is not a well-formed amount
  line.2.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 672, 289, 730]; reason=None
  invoice.payable: raw='?,??۵,۰۰۰'; status=REVIEW; confidence=0.0; bbox=[210, 748, 334, 784]; reason=glyph 1 not accepted: ambiguous: margin 0.133 below 0.150; glyph 3 not accepted: ambiguous: margin 0.118 below 0.150; glyph 4 not accepted: ambiguous: margin 0.133 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; full-page spatial assessment remains REVIEW; cell OCR is supplementary; arithmetic gate failed: payable '?,??۵,۰۰۰' is not a well-formed amount
Runtime payable bbox (OCR word boxes): [214, 752, 116, 28]; status=REVIEW; reason=minimum field confidence 7.47 is below 60.00; raw OCR value does not match the declared numeric format; reference=[214, 752, 116, 28]
Arithmetic gate: FAIL; line_sum=None; payable=None; extras=0; reason=payable '?,??۵,۰۰۰' is not a well-formed amount

### 32.png (invoice 32)
Reference payable bbox: [214, 888, 116, 28]
Outcome: ReviewRequired
Effective numeric authority: tesseract_parse
Reason: flat-text parser blocked: expected exactly one invoice date, OCR yielded 0; spatial parser: no row-number token '1' was found in the rightmost table column; fields require review: invoice.number, invoice.date, total.net
Parsed numeric fields:
  invoice.payable=۷,۸۵۰,۰۰۰
Numeric cell results:
  line.0.total: raw='۹۷۰,۰۰۰'; status=EXTRACTED; confidence=99.9847619047619; bbox=[120, 533, 240, 593]; reason=None
  line.0.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 533, 289, 593]; reason=None
  line.1.total: raw='۳,۹۵۰,۰۰۰'; status=EXTRACTED; confidence=99.9863492063492; bbox=[120, 604, 240, 661]; reason=None
  line.1.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 604, 289, 661]; reason=None
  line.2.total: raw='۱,۸۷۰,۰۰۰'; status=EXTRACTED; confidence=99.9847619047619; bbox=[120, 672, 240, 729]; reason=None
  line.2.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 672, 289, 729]; reason=None
  line.3.total: raw='۹۷۰,۰۰۰'; status=EXTRACTED; confidence=99.9847619047619; bbox=[120, 740, 240, 797]; reason=None
  line.3.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 740, 289, 797]; reason=None
  line.4.total: raw='۹۰,۰۰۰'; status=EXTRACTED; confidence=99.98761904761905; bbox=[120, 808, 240, 865]; reason=None
  line.4.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 808, 289, 865]; reason=None
  invoice.payable: raw='۷,۸۵۰,۰۰۰'; status=EXTRACTED; confidence=99.95936507936509; bbox=[210, 884, 334, 920]; reason=None
Runtime payable bbox (OCR word boxes): [214, 888, 116, 28]; status=EXTRACTED; reason=None; reference=[214, 888, 116, 28]
Arithmetic gate: PASS; line_sum=7850000; payable=7850000; extras=0; reason=None

### 33.png (invoice 33)
Reference payable bbox: [199, 1431, 147, 28]
Outcome: ReviewRequired
Effective numeric authority: tesseract_parse
Reason: flat-text parser blocked: expected exactly one invoice date, OCR yielded 0; spatial parser: row sequence 2 is missing before 4; only one increasing row-number anchor was recognized; fields require review: invoice.date, total.net; numeric OCR REVIEW cell(s): line.0.total, line.0.quantity, line.1.total, line.2.total, line.3.total, line.4.total, line.5.total, line.6.total, line.7.total, line.8.total, line.9.total, line.10.total, line.11.total, line.12.total, invoice.payable
Parsed numeric fields:
  invoice.payable=۳۴۷,۹۲۰,۰۰۰
Numeric cell results:
  line.0.total: raw='۷,۸۸۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 533, 240, 593]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.0.quantity: raw='?'; status=REVIEW; confidence=0.0; bbox=[248, 533, 289, 593]; reason=glyph 1 not accepted: ambiguous: margin 0.146 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format
  line.1.total: raw='۴,۸۵۰,۰۰۰'; status=REVIEW; confidence=99.98761904761905; bbox=[120, 604, 240, 661]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.1.quantity: raw='۱۰'; status=EXTRACTED; confidence=99.97047619047619; bbox=[248, 604, 289, 661]; reason=None
  line.2.total: raw='۸,۷۵۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 672, 240, 729]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.2.quantity: raw='۵'; status=EXTRACTED; confidence=99.97809523809524; bbox=[248, 672, 289, 729]; reason=None
  line.3.total: raw='۶,۴۰۰,۰۰۰'; status=REVIEW; confidence=99.98190476190476; bbox=[120, 740, 240, 797]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.3.quantity: raw='۲'; status=EXTRACTED; confidence=99.99809523809525; bbox=[248, 740, 289, 797]; reason=None
  line.4.total: raw='۴۹,۴۰۰,۰۰۰'; status=REVIEW; confidence=99.98761904761905; bbox=[120, 808, 240, 865]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.4.quantity: raw='۲۰'; status=EXTRACTED; confidence=99.97047619047619; bbox=[248, 808, 289, 865]; reason=None
  line.5.total: raw='۱,۵۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 876, 240, 933]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.5.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 876, 289, 933]; reason=None
  line.6.total: raw='۶,۹۰۰,۰۰۰'; status=REVIEW; confidence=99.98190476190476; bbox=[120, 944, 240, 1001]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.6.quantity: raw='۵'; status=EXTRACTED; confidence=99.97809523809524; bbox=[248, 944, 289, 1001]; reason=None
  line.7.total: raw='۶,۸۷۰,۰۰۰'; status=REVIEW; confidence=99.98190476190476; bbox=[120, 1012, 240, 1068]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.7.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 1012, 289, 1068]; reason=None
  line.8.total: raw='۳,۷۰۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 1079, 240, 1136]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.8.quantity: raw='۲'; status=EXTRACTED; confidence=99.99809523809525; bbox=[248, 1079, 289, 1136]; reason=None
  line.9.total: raw='??۹,۶۰۰,۰۰۰'; status=REVIEW; confidence=0.0; bbox=[120, 1147, 240, 1204]; reason=glyph 1 not accepted: ambiguous: margin 0.108 below 0.150; glyph 2 not accepted: ambiguous: margin 0.108 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.9.quantity: raw='۸'; status=EXTRACTED; confidence=66.1847619047619; bbox=[248, 1147, 289, 1204]; reason=None
  line.10.total: raw='۱۹,۰۵۰,۰۰۰'; status=REVIEW; confidence=99.98761904761905; bbox=[120, 1215, 240, 1272]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.10.quantity: raw='۱۵'; status=EXTRACTED; confidence=99.97809523809524; bbox=[248, 1215, 289, 1272]; reason=None
  line.11.total: raw='۱,۳۸۰,۰۰۰'; status=REVIEW; confidence=99.9863492063492; bbox=[120, 1283, 240, 1340]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.11.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 1283, 289, 1340]; reason=None
  line.12.total: raw='۱,۵۷۰,۰۰۰'; status=REVIEW; confidence=99.9847619047619; bbox=[120, 1351, 240, 1409]; reason=arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
  line.12.quantity: raw='۱'; status=EXTRACTED; confidence=99.99714285714286; bbox=[248, 1351, 289, 1409]; reason=None
  invoice.payable: raw='??۷,۹?۰,۰۰۰'; status=REVIEW; confidence=0.0; bbox=[195, 1427, 350, 1463]; reason=glyph 1 not accepted: ambiguous: margin 0.142 below 0.150; glyph 2 not accepted: ambiguous: margin 0.118 below 0.150; glyph 6 not accepted: ambiguous: margin 0.133 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount
Runtime payable bbox (OCR word boxes): [199, 1431, 147, 28]; status=EXTRACTED; reason=None; reference=[199, 1431, 147, 28]
Arithmetic gate: FAIL; line_sum=None; payable=None; extras=0; reason=line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount

# SUMMARY

## numeric_authority=glyph
Ready: 0 / 4
REVIEW: 4 / 4
Blocked: 0 / 4
REVIEW because tesseract_disagreement_with_glyph_authority: 0
REVIEW because InvoiceTextParseError: 4
REVIEW because other reasons:
  (none)

## numeric_authority=tesseract_parse
Ready: 0 / 4
REVIEW: 4 / 4
Blocked: 0 / 4
REVIEW because tesseract_disagreement_with_glyph_authority: 0
REVIEW because InvoiceTextParseError: 4
REVIEW because other reasons:
  (none)
