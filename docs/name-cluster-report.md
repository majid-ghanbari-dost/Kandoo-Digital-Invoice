# Offline Product-Name Clustering by Image Hash

## Method

The experiment crops the product-description cell from every labeled row, converts it to grayscale, finds the non-white text bounding box using a 245/255 cutoff, crops to that box, and resizes to 64×16 pixels. aHash uses an 8×8 resize and comparison against the pixel mean; dHash uses a 9×8 resize and horizontal adjacent-pixel comparisons. Clustering is single-link connected components: an edge is added for each pair of hashes with Hamming distance less than or equal to the tested threshold.

Only Pillow is used for image processing and hashing. The projection detector is used to verify that the T2 geometry agrees with the receipt fixtures. Clustering uses only the hashes. Ground-truth group labels below are used only to score the result.

Crop boxes use the product-name column interior with 4 px horizontal, 8 px top and 3 px bottom insets to exclude table rules. Crop files are saved under `/tmp/t3-crops/` as `{invoice_id}_row{row_idx}.png`.

## Projection Geometry Check

The actual detector output confirms the RTL column order `[amount, quantity, description, row number]` for these receipts. The product-description cells are between x=293 and x=487. The task's suggested x=116–244 range is the printed amount/total column on these images, not the product-name column, so it was not used for name hashes.

| invoice | image size | detected rows | detected column boundaries | description x range |
|---:|---:|---:|---|---:|
| 29 | 576×1296 | 4 | [116.0, 244.0, 293.0, 487.0, 527.0] | 293–487 |
| 31 | 576×1224 | 3 | [116.0, 244.0, 293.0, 487.0, 527.0] | 293–487 |
| 32 | 576×1368 | 5 | [116.0, 244.0, 293.0, 487.0, 527.0] | 293–487 |
| 33 | 576×1680 | 13 | [116.0, 244.0, 293.0, 487.0, 527.0] | 293–487 |

Each projection row count and band agrees with `tests/fixtures/real/labels.json` (within 1 px).

## Ground Truth Used for Scoring (Visual, Unconfirmed)

The three names below were visually mapped to rows from the description crops; no OCR was run and this mapping is not operator-confirmed. All other row names are treated as distinct, per the task brief.

| group | visually mapped rows |
|---|---|
| A (دستمال سفره تم) | 31_row0, 32_row0 |
| B (رد پا یا فلش تم) | 31_row1, 32_row3 |
| C (خلال کوچک) | 31_row2, 33_row1 |

## Per-Crop Hashes

| crop | source crop bbox (x1,y1,x2,y2) | text bbox inside crop | aHash | dHash |
|---|---:|---:|---|---|
| 29_row0 | (297, 533, 483, 593) | (64, 9, 124, 31) | `000012feffde8103` | `d0f4c624b1950757` |
| 29_row1 | (297, 604, 483, 661) | (29, 5, 158, 28) | `0008292befff9095` | `989b5bcb9b933535` |
| 29_row2 | (297, 672, 483, 729) | (58, 5, 130, 28) | `101c19d9dfdeb000` | `b5b4b2b31cba636b` |
| 29_row3 | (297, 740, 483, 798) | (64, 4, 124, 28) | `08040e5fdfde9010` | `d8dcd85b15963723` |
| 31_row0 | (297, 533, 483, 593) | (32, 8, 156, 31) | `000444c5f7ff8828` | `a828a9ad26245a5a` |
| 31_row1 | (297, 604, 483, 661) | (36, 4, 152, 29) | `00101e9ebffe6041` | `b4e5b4346e6ecddd` |
| 31_row2 | (297, 672, 483, 730) | (44, 5, 145, 28) | `005e4373f3d70420` | `95b496c726a66969` |
| 32_row0 | (297, 533, 483, 593) | (32, 8, 156, 31) | `000444c5f7ff8828` | `a828a9ad26245a5a` |
| 32_row1 | (297, 604, 483, 661) | (7, 5, 181, 28) | `008281c9ffff3e18` | `565612931557eaaa` |
| 32_row2 | (297, 672, 483, 729) | (52, 5, 136, 28) | `00302077fff58183` | `e464cdc5a5a52b2a` |
| 32_row3 | (297, 740, 483, 797) | (36, 4, 152, 29) | `00101e9ebffe6041` | `b4e5b4346e6ecddd` |
| 32_row4 | (297, 808, 483, 865) | (64, 5, 124, 27) | `087a5643fff70001` | `dad2b4d545a5a501` |
| 33_row0 | (297, 533, 483, 593) | (9, 8, 181, 31) | `0087243dffff4068` | `2c2c68696b6b8a8a` |
| 33_row1 | (297, 604, 483, 661) | (44, 5, 145, 28) | `005e4373f3d70420` | `95b496c726a66969` |
| 33_row2 | (297, 672, 483, 729) | (30, 5, 158, 28) | `00407323ffff8090` | `c696c6c7d2d23424` |
| 33_row3 | (297, 740, 483, 797) | (36, 4, 153, 28) | `0008597bfffb0020` | `da9893d7b636266f` |
| 33_row4 | (297, 808, 483, 865) | (24, 4, 163, 28) | `000676fffbe78480` | `24a4e495d6ce2d2d` |
| 33_row5 | (297, 876, 483, 933) | (60, 5, 129, 28) | `20404377fffe0810` | `ca88a2a7589633b3` |
| 33_row6 | (297, 944, 483, 1001) | (12, 4, 176, 55) | `006fffa000327e64` | `d8dbaa4ee4e6d6cc` |
| 33_row7 | (297, 1012, 483, 1068) | (14, 4, 175, 28) | `0020a1a7ffff5018` | `49424f4d5a52d171` |
| 33_row8 | (297, 1079, 483, 1136) | (42, 9, 145, 28) | `000317fff782d8d8` | `4c2e2f4c46563135` |
| 33_row9 | (297, 1147, 483, 1204) | (48, 5, 142, 29) | `00206077ffff8286` | `45c1cbedd515243e` |
| 33_row10 | (297, 1215, 483, 1272) | (21, 5, 168, 55) | `60edff92000c3c30` | `cac91b36c958d1e0` |
| 33_row11 | (297, 1283, 483, 1340) | (28, 5, 160, 28) | `000103bfffffc242` | `0b2bf75669699696` |
| 33_row12 | (297, 1351, 483, 1409) | (10, 5, 179, 29) | `000040e5ffbfda58` | `6bcb854d495b92d2` |

## Threshold Sweep

`wrong_merges` counts unordered crop pairs from different ground-truth product-name labels that became part of the same connected component. `correct_merges` counts recovered known same-name pairs (0–3).

| hash | threshold (bits) | clusters | correct_merges / 3 | wrong_merges (false-positive pairs) |
|---|---:|---:|---:|---:|
| ahash | 1 | 22 | 3 / 3 | 0 |
| ahash | 2 | 22 | 3 / 3 | 0 |
| ahash | 3 | 22 | 3 / 3 | 0 |
| ahash | 4 | 22 | 3 / 3 | 0 |
| ahash | 5 | 22 | 3 / 3 | 0 |
| ahash | 6 | 22 | 3 / 3 | 0 |
| ahash | 8 | 21 | 3 / 3 | 1 |
| ahash | 10 | 20 | 3 / 3 | 2 |
| ahash | 12 | 15 | 3 / 3 | 16 |
| ahash | 15 | 4 | 3 / 3 | 228 |
| ahash | 20 | 2 | 3 / 3 | 251 |
| dhash | 1 | 22 | 3 / 3 | 0 |
| dhash | 2 | 22 | 3 / 3 | 0 |
| dhash | 3 | 22 | 3 / 3 | 0 |
| dhash | 4 | 22 | 3 / 3 | 0 |
| dhash | 5 | 22 | 3 / 3 | 0 |
| dhash | 6 | 22 | 3 / 3 | 0 |
| dhash | 8 | 22 | 3 / 3 | 0 |
| dhash | 10 | 22 | 3 / 3 | 0 |
| dhash | 12 | 22 | 3 / 3 | 0 |
| dhash | 15 | 22 | 3 / 3 | 0 |
| dhash | 20 | 18 | 3 / 3 | 5 |

## Best Tested Thresholds

Selection rule: maximize recovered known pairs, then minimize false-positive pair joins, then choose the lowest threshold. The two hash algorithms are selected independently.

### ahash: threshold 1

- Correct known groups merged: 3/3 (A (دستمال سفره تم): merged; B (رد پا یا فلش تم): merged; C (خلال کوچک): merged).
- Wrong merges: 0 false-positive crop-pair joins.
- Distinct ground-truth name labels in mixed clusters: 0 (none).
- Observed clusters: 22; expected ground-truth clusters: 22 (3 pairs + 19 singles).

Pair status: A (دستمال سفره تم): merged; B (رد پا یا فلش تم): merged; C (خلال کوچک): merged

### dhash: threshold 1

- Correct known groups merged: 3/3 (A (دستمال سفره تم): merged; B (رد پا یا فلش تم): merged; C (خلال کوچک): merged).
- Wrong merges: 0 false-positive crop-pair joins.
- Distinct ground-truth name labels in mixed clusters: 0 (none).
- Observed clusters: 22; expected ground-truth clusters: 22 (3 pairs + 19 singles).

Pair status: A (دستمال سفره تم): merged; B (رد پا یا فلش تم): merged; C (خلال کوچک): merged

## Cluster Memberships at Every Tested Threshold

Each section lists every connected component, including singletons, so all 25 crops are accounted for at every threshold.

### ahash, threshold 1 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### ahash, threshold 2 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### ahash, threshold 3 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### ahash, threshold 4 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### ahash, threshold 5 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### ahash, threshold 6 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### ahash, threshold 8 (clusters=21, correct=3/3, wrong=1)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2, 33_row9
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row10
C20: 33_row11
C21: 33_row12
```

### ahash, threshold 10 (clusters=20, correct=3/3, wrong=2)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2, 33_row9
C10: 32_row4
C11: 33_row0
C12: 33_row2, 33_row5
C13: 33_row3
C14: 33_row4
C15: 33_row6
C16: 33_row7
C17: 33_row8
C18: 33_row10
C19: 33_row11
C20: 33_row12
```

### ahash, threshold 12 (clusters=15, correct=3/3, wrong=16)

```text
C01: 29_row0, 33_row11
C02: 29_row1, 32_row2, 33_row2, 33_row5, 33_row9
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0, 33_row7, 33_row12
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row4
C10: 33_row0
C11: 33_row3
C12: 33_row4
C13: 33_row6
C14: 33_row8
C15: 33_row10
```

### ahash, threshold 15 (clusters=4, correct=3/3, wrong=228)

```text
C01: 29_row0, 29_row1, 29_row2, 29_row3, 31_row0, 31_row1, 31_row2, 32_row0, 32_row1, 32_row2, 32_row3, 32_row4, 33_row0, 33_row1, 33_row2, 33_row3, 33_row4, 33_row5, 33_row7, 33_row9, 33_row11, 33_row12
C02: 33_row6
C03: 33_row8
C04: 33_row10
```

### ahash, threshold 20 (clusters=2, correct=3/3, wrong=251)

```text
C01: 29_row0, 29_row1, 29_row2, 29_row3, 31_row0, 31_row1, 31_row2, 32_row0, 32_row1, 32_row2, 32_row3, 32_row4, 33_row0, 33_row1, 33_row2, 33_row3, 33_row4, 33_row5, 33_row7, 33_row8, 33_row9, 33_row11, 33_row12
C02: 33_row6, 33_row10
```

### dhash, threshold 1 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### dhash, threshold 2 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### dhash, threshold 3 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### dhash, threshold 4 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### dhash, threshold 5 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### dhash, threshold 6 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### dhash, threshold 8 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### dhash, threshold 10 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### dhash, threshold 12 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### dhash, threshold 15 (clusters=22, correct=3/3, wrong=0)

```text
C01: 29_row0
C02: 29_row1
C03: 29_row2
C04: 29_row3
C05: 31_row0, 32_row0
C06: 31_row1, 32_row3
C07: 31_row2, 33_row1
C08: 32_row1
C09: 32_row2
C10: 32_row4
C11: 33_row0
C12: 33_row2
C13: 33_row3
C14: 33_row4
C15: 33_row5
C16: 33_row6
C17: 33_row7
C18: 33_row8
C19: 33_row9
C20: 33_row10
C21: 33_row11
C22: 33_row12
```

### dhash, threshold 20 (clusters=18, correct=3/3, wrong=5)

```text
C01: 29_row0
C02: 29_row1, 29_row3
C03: 29_row2, 31_row2, 33_row1
C04: 31_row0, 32_row0
C05: 31_row1, 32_row3
C06: 32_row1
C07: 32_row2
C08: 32_row4
C09: 33_row0
C10: 33_row2
C11: 33_row3
C12: 33_row4
C13: 33_row5
C14: 33_row6
C15: 33_row7, 33_row8
C16: 33_row9
C17: 33_row10
C18: 33_row11, 33_row12
```

## Tesseract Comparison

Tesseract comparison skipped: no `tesseract` executable is available in this environment. No OCR or network/VLM service was used.

## Reproduction

```sh
PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python src/run_name_cluster_experiment.py \
  --labels tests/fixtures/real/labels.json \
  --crop-dir /tmp/t3-crops \
  --output docs/name-cluster-report.md
```

Generated 25 description crops; thresholds tested: 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20.
