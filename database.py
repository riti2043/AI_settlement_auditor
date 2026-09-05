import sqlite3
import os

DB_PATH = "auditor.db"

def get_db():
    """
    Returns a WAL-mode, thread-safe SQLite connection with a 5s busy timeout.
    Call this any time you need a connection — never cache connections across threads.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Transactions Table — session_id column added for multi-tenant isolation
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL DEFAULT 'legacy',
        customer_id TEXT,
        amount REAL,
        currency TEXT,
        status TEXT,
        payment_id TEXT,
        order_id TEXT,
        refund_id TEXT,
        settlement_id TEXT,
        failure_reason TEXT,
        fee_breakdown TEXT,
        action_taken TEXT,
        flagged BOOLEAN DEFAULT 0,
        flag_reason TEXT,
        due_date TEXT,
        risk_tier TEXT DEFAULT 'Low',
        tax_mismatch BOOLEAN DEFAULT 0,
        confidence_note TEXT,
        is_live_api_call BOOLEAN DEFAULT 0,
        escalation_step INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Audit Log Table — session_id added for scoped exports
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL DEFAULT 'legacy',
        transaction_id TEXT,
        action TEXT,
        details TEXT,
        is_live_api_call BOOLEAN DEFAULT 0,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (transaction_id) REFERENCES transactions (id)
    )
    ''')

    # Add session_id column to existing tables if upgrading from older schema
    for table in ("transactions", "audit_log"):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN session_id TEXT NOT NULL DEFAULT 'legacy'")
        except Exception:
            pass  # Column already exists

    # Performance indexes for session-scoped queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_session_status ON transactions (session_id, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_session_updated ON transactions (session_id, updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log (session_id, timestamp)")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized with session isolation and WAL mode.")
