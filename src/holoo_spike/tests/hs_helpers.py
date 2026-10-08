"""SYNTHETIC Holoo-shaped fixture builder — WP-11.1 test infrastructure ONLY.

OD-HS-K: this module exists to give the read-only spike something honest to
read in a fully offline, deterministic way. It CREATES a SQLite database with
fixed, hand-written rows shaped like the data classes a Holoo-style accounting
DB would hold for invoices (header/rows/customers/products) PLUS one
space-named table to exercise identifier quoting.

THIS IS NOT A HOLOO DATABASE and MUST NOT be treated as one:
  - the names are synthetic test names, not Holoo schema facts;
  - the spike's contract explicitly forbids built-in schema knowledge (SPEC
    §2.7) — every real source needs an operator-declared mapping;
  - the builder necessarily contains CREATE/INSERT statements and therefore
    lives under tests/ and is NEVER imported by the production package (an
    AST import-sweep in the suite proves the dependency direction).

All rows are deterministic (no random, no clock) so report hashes are stable.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DDL = """
CREATE TABLE "InvoiceHead" (
    InvoiceID    INTEGER PRIMARY KEY,
    InvoiceNo    TEXT NOT NULL,
    InvoiceDate  TEXT NOT NULL,
    CustomerRef  INTEGER,
    TotalAmount  INTEGER NOT NULL,
    Note         TEXT
);

CREATE TABLE "InvoiceRows" (
    RowID        INTEGER PRIMARY KEY,
    InvoiceID    INTEGER NOT NULL,
    ProductCode  TEXT NOT NULL,
    Quantity     INTEGER NOT NULL,
    UnitPrice    REAL NOT NULL,
    LineNote     TEXT
);

CREATE TABLE "Customers" (
    CustomerID   INTEGER PRIMARY KEY,
    CustomerName TEXT NOT NULL,
    Phone        TEXT
);

CREATE TABLE "Products" (
    ProductCode  TEXT PRIMARY KEY,
    ProductName  TEXT NOT NULL,
    Price        REAL,
    Preview      BLOB
);

CREATE TABLE "Archive Notes" (
    NoteID       INTEGER PRIMARY KEY,
    NoteText     TEXT NOT NULL
);
"""

ROWS = [
    """INSERT INTO "Customers" VALUES (1, 'مجید رضایی', NULL)""",
    """INSERT INTO "Customers" VALUES (2, 'Acme Trading Ltd.', '+98 21 5550 0000')""",
    """INSERT INTO "Customers" VALUES (3, 'شرکت نمونهٔ دوم', '021-12345678')""",
    """INSERT INTO "Products" VALUES ('P-001', 'کابل شبکه Cat6', 125000.5, x'00FF10')""",
    """INSERT INTO "Products" VALUES ('P-002', 'Router RB-941', 2450000.0, NULL)""",
    """INSERT INTO "Products" VALUES ('P-003', 'Cable Tie 100pcs', 95000.25, x'DEADBEEF')""",
    """INSERT INTO "InvoiceHead" VALUES (10, 'INV-1404-0010', '2026-10-01', 1, 1275000, NULL)""",
    """INSERT INTO "InvoiceHead" VALUES (11, 'INV-1404-0011', '2026-10-02', 2, 2450000, 'ضرب‌الاجل فوری')""",
    """INSERT INTO "InvoiceHead" VALUES (12, 'INV-1404-0012', '2026-10-03', 1, 1045000, 'پرداخت نسیه')""",
    """INSERT INTO "InvoiceHead" VALUES (13, 'INV-1404-0013', '2026-10-04', NULL, 95000, 'بدون مشتری')""",
    """INSERT INTO "InvoiceRows" VALUES (100, 10, 'P-001', 10, 125000.5, NULL)""",
    """INSERT INTO "InvoiceRows" VALUES (101, 10, 'P-002', 1, 2450000.0, 'تک‌عدد')""",
    """INSERT INTO "InvoiceRows" VALUES (102, 11, 'P-002', 1, 2450000.0, NULL)""",
    """INSERT INTO "InvoiceRows" VALUES (103, 12, 'P-003', 10, 95000.25, NULL)""",
    """INSERT INTO "InvoiceRows" VALUES (104, 12, 'P-001', 4, 125000.5, 'تخفیف نداشت')""",
    """INSERT INTO "InvoiceRows" VALUES (105, 13, 'P-003', 1, 95000.25, NULL)""",
    """INSERT INTO "InvoiceRows" VALUES (106, 13, 'P-001', 1, 125000.5, NULL)""",
    """INSERT INTO "Archive Notes" VALUES (1, 'quote " inside ')""",
    """INSERT INTO "Archive Notes" VALUES (2, 'it''s a note')""",
]


def build_synthetic_holoo_like_db(path: Path) -> Path:
    """Create the deterministic SYNTHETIC fixture DB at `path` (fresh)."""
    path = Path(path)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(DDL)
        for stmt in ROWS:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()
    return path
