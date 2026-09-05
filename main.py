import sqlite3
import json
import pandas as pd
from typing import Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db
from razorpay_client import RazorpayGenerator
from reconciliation import ReconciliationEngine
from explain import ExplainabilityAgent
from gating import GatingEngine

DB_PATH = "auditor.db"
init_db()

app = FastAPI(
    title="AI Settlement Auditor API",
    description="REST API backend for autonomous Razorpay settlement auditing and recovery.",
    version="2.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

generator = RazorpayGenerator()
reconciler = ReconciliationEngine()
explainer = ExplainabilityAgent()
gating = GatingEngine()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

class QARequest(BaseModel):
    query: str

class DecisionRequest(BaseModel):
    tx_id: str
    decision: str  # APPROVE or REJECT
    reviewer: Optional[str] = "Human Admin"

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "AI Settlement Auditor API",
        "version": "2.0.0"
    }

@app.post("/api/batch/run")
def run_new_batch():
    try:
        gen_results = generator.generate_batch(7)
        recon_results = reconciler.run_reconciliation()
        return {
            "success": True,
            "message": "Batch generated and reconciled successfully.",
            "generated": len(gen_results),
            "reconciliation": recon_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/transactions")
def get_transactions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions ORDER BY updated_at DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    df = pd.DataFrame(rows) if rows else pd.DataFrame()

    total_processed = len(df)
    mismatches = len(df[df['status'].isin(['Mismatched', 'Recovered', 'Flagged', 'BROKEN_PROMISE'])]) if not df.empty else 0
    recovered_df = df[df['status'] == 'Recovered'] if not df.empty else pd.DataFrame()
    recovered_amount = float(recovered_df['amount'].sum()) if not recovered_df.empty else 0.0
    pending_approval = len(df[df['flagged'] == 1]) if not df.empty else 0

    trend_warning = None
    if not df.empty and 'failure_reason' in df.columns:
        counts = df['failure_reason'].value_counts()
        for reason, count in counts.items():
            if reason and count / total_processed >= 0.30:
                trend_warning = f"Elevated {reason} rate in this batch ({count}/{total_processed} = {count/total_processed*100:.1f}%)"
                break

    return {
        "metrics": {
            "total_processed": total_processed,
            "mismatches_detected": mismatches,
            "amount_recovered": recovered_amount,
            "pending_approval": pending_approval,
            "trend_warning": trend_warning
        },
        "transactions": rows
    }

@app.get("/api/transaction/{tx_id}")
def get_transaction_detail(tx_id: str, beginner_mode: bool = False):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found")

    tx_dict = dict(row)
    raw_reason = tx_dict.get('failure_reason')

    explanation = explainer.explain_failure(
        raw_reason if (raw_reason and str(raw_reason).lower() != 'nan') else "NORMAL",
        tx_dict['amount'],
        tx_dict['id'],
        beginner_mode=beginner_mode
    )
    delay_prediction = reconciler.predict_settlement_delay(raw_reason)
    handoff_summary = gating.generate_handoff_summary(tx_id)

    fees = None
    if tx_dict.get('fee_breakdown'):
        try:
            fees = json.loads(tx_dict['fee_breakdown'])
        except Exception:
            pass

    return {
        "transaction": tx_dict,
        "fee_breakdown": fees,
        "explanation": explanation,
        "delay_prediction": delay_prediction,
        "handoff_summary": handoff_summary
    }

class ExecuteRequest(BaseModel):
    cause: str

@app.post("/api/transaction/{tx_id}/execute")
def execute_transaction_action(tx_id: str, req: ExecuteRequest):
    result = reconciler.execute_action(tx_id, req.cause)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result

@app.post("/api/qa")
def ask_auditor_qa(req: QARequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    answer = explainer.ask_auditor_qa(req.query)
    return {"query": req.query, "answer": answer}

@app.post("/api/approve")
def handle_human_decision(req: DecisionRequest):
    success, msg = gating.process_human_decision(req.tx_id, req.decision.upper(), req.reviewer)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}

@app.get("/api/report")
def get_batch_report():
    report = explainer.generate_batch_report()
    return {"report": report}

@app.get("/api/audit-log")
def get_audit_log():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log ORDER BY timestamp DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"audit_log": rows}

@app.get("/api/export-csv")
def export_csv():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM audit_log ORDER BY timestamp DESC", conn)
    conn.close()
    
    csv_str = df.to_csv(index=False)
    return Response(content=csv_str, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit_log.csv"})

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
