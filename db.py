"""Database layer for Jawabdari: connection, schema and ID generation.

Only table creation and low-level helpers live here.
All business rules (DLP, liability, deposits) live in services.py.
"""

import sqlite3

import config  # read config.DB_PATH at call time, so tests can point it to a temp file

# Tables allowed in next_id() - table names cannot be passed as "?" parameters,
# so we check them against this list to stay safe from SQL injection.
ALLOWED_TABLES = {"contractors", "works", "defects"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS contractors (
    id          TEXT PRIMARY KEY,                 -- e.g. C-001
    name        TEXT NOT NULL,
    phone       TEXT,
    gst_no      TEXT,
    created_at  TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS works (
    id                  TEXT PRIMARY KEY,         -- e.g. W-0001
    name                TEXT NOT NULL,
    asset_type          TEXT NOT NULL
        CHECK (asset_type IN ('Road', 'Bridge', 'Drain', 'Building', 'Streetlight')),
    ward                TEXT,
    zone                TEXT,
    latitude            REAL,
    longitude           REAL,
    contractor_id       TEXT NOT NULL REFERENCES contractors(id),
    cost_rs             INTEGER NOT NULL CHECK (cost_rs > 0),
    completion_date     TEXT NOT NULL,            -- 'YYYY-MM-DD'
    dlp_months          INTEGER NOT NULL,
    dlp_end_date        TEXT NOT NULL,            -- 'YYYY-MM-DD'
    security_deposit_rs INTEGER NOT NULL DEFAULT 0,
    deposit_status      TEXT NOT NULL DEFAULT 'Held'
        CHECK (deposit_status IN ('Held', 'Released', 'Forfeited')),
    lifecycle_stage     TEXT NOT NULL DEFAULT 'Under Guarantee'
        CHECK (lifecycle_stage IN ('Under Guarantee', 'Guarantee Ended', 'Decommissioned')),
    created_at          TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS defects (
    id              TEXT PRIMARY KEY,             -- e.g. D-0001
    work_id         TEXT NOT NULL REFERENCES works(id),
    reported_by     TEXT NOT NULL CHECK (reported_by IN ('Citizen', 'Engineer')),
    reporter_name   TEXT,
    description     TEXT NOT NULL,
    photo_path      TEXT,                         -- NULL if no photo
    language        TEXT DEFAULT 'en',
    reported_on     TEXT NOT NULL,                -- 'YYYY-MM-DD'
    liable_party    TEXT NOT NULL CHECK (liable_party IN ('Contractor', 'City')),
    status          TEXT NOT NULL
        CHECK (status IN ('Open', 'Notice Sent', 'Repaired - Pending Verification',
                          'Closed', 'Overdue')),
    notice_deadline TEXT,                         -- NULL when the city is liable
    repair_cost_rs  INTEGER DEFAULT 0,
    repaired_on     TEXT,
    verified_on     TEXT
);

-- Append-only audit log: we only INSERT here, never UPDATE or DELETE.
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id     TEXT REFERENCES works(id),
    event_type  TEXT NOT NULL,                    -- e.g. WORK_REGISTERED, NOTICE_SENT
    details     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes to keep common lookups fast as data grows
CREATE INDEX IF NOT EXISTS idx_works_contractor ON works(contractor_id);
CREATE INDEX IF NOT EXISTS idx_works_dlp_end    ON works(dlp_end_date);
CREATE INDEX IF NOT EXISTS idx_defects_work     ON defects(work_id);
CREATE INDEX IF NOT EXISTS idx_defects_status   ON defects(status);
CREATE INDEX IF NOT EXISTS idx_events_work      ON events(work_id);
"""


def get_conn():
    """Open a connection with foreign keys ON and rows usable like dicts (row['name'])."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables and indexes if they don't exist yet. Safe to run many times."""
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def reset_db():
    """Delete all tables and create them again (used by seed.py). Destroys all data!"""
    conn = get_conn()
    # Drop children before parents because of foreign keys
    conn.executescript(
        """
        DROP TABLE IF EXISTS events;
        DROP TABLE IF EXISTS defects;
        DROP TABLE IF EXISTS works;
        DROP TABLE IF EXISTS contractors;
        """
    )
    conn.commit()
    conn.close()
    init_db()


def next_id(table, prefix, width, conn=None):
    """Return the next ID for a table, e.g. next_id('works', 'W', 4) -> 'W-0007'.

    Pass `conn` when calling inside another operation so it sees uncommitted rows.
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"next_id not allowed for table: {table}")

    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    rows = conn.execute(f"SELECT id FROM {table} WHERE id LIKE ?", (f"{prefix}-%",)).fetchall()
    if own_conn:
        conn.close()

    # Find the highest number used so far (ignore any badly formatted IDs)
    highest = 0
    for row in rows:
        number_part = row["id"].split("-", 1)[1]
        if number_part.isdigit():
            highest = max(highest, int(number_part))

    return f"{prefix}-{highest + 1:0{width}d}"


def table_names():
    """List user tables in the database (handy for checks)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    conn.close()
    return [row["name"] for row in rows]


if __name__ == "__main__":
    init_db()
    print("Database ready at:", config.DB_PATH)
    print("Tables:", ", ".join(table_names()))
