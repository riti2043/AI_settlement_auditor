import sqlite3
import os

DB_PATH = "auditor.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Transactions Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
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
    
    # Audit Log Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT,
        action TEXT,
        details TEXT,
        is_live_api_call BOOLEAN DEFAULT 0,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (transaction_id) REFERENCES transactions (id)
    )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized with expanded schema.")
