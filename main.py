import uuid
import json
import pandas as pd
from typing import Optional
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db, get_db
from razorpay_client import RazorpayGenerator
from reconciliation import ReconciliationEngine
from explain import ExplainabilityAgent
from gating import GatingEngine

init_db()

app = FastAPI(
    title="AI Settlement Auditor API",
    description="REST API backend for autonomous Razorpay settlement auditing and recovery.",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-ID"],
)

generator = RazorpayGenerator()
reconciler = ReconciliationEngine()
explainer = ExplainabilityAgent()
gating = GatingEngine()


# ---------------------------------------------------------------------------
# Session Dependency
# ---------------------------------------------------------------------------
def get_session_id(request: Request) -> str:
    """
    Extracts X-Session-ID from request headers.
    If absent, generates a new UUID4 and attaches it to request.state
    so it can be added to the response header by the middleware below.
    """
    sid = request.headers.get("X-Session-ID", "").strip()
    if not sid:
        sid = str(uuid.uuid4())
    request.state.session_id = sid
    return sid


@app.middleware("http")
async def attach_session_header(request: Request, call_next):
    """
    Ensures every response carries the active X-Session-ID header
    so the frontend can persist it in localStorage.
    """
    response = await call_next(request)
    sid = getattr(request.state, "session_id", None)
    if sid:
        response.headers["X-Session-ID"] = sid
    return response


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------
class QARequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class DecisionRequest(BaseModel):
    tx_id: str
    decision: str          # APPROVE or REJECT
    reviewer: Optional[str] = "Human Admin"
    session_id: Optional[str] = None

class ExecuteRequest(BaseModel):
    cause: str
    session_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "AI Settlement Auditor API",
        "version": "3.0.0"
    }


@app.post("/api/batch/run")
def run_new_batch(request: Request):
    session_id = get_session_id(request)
    try:
        gen_results = generator.generate_batch(session_id=session_id)
        recon_results = reconciler.run_reconciliation(session_id=session_id)
        return {
            "success": True,
            "session_id": session_id,
            "message": "Batch generated and reconciled successfully.",
            "generated": len(gen_results),
            "reconciliation": recon_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/transactions")
def get_transactions(request: Request):
    session_id = get_session_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transactions WHERE session_id = ? ORDER BY updated_at DESC",
        (session_id,)
    )
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
        "session_id": session_id,
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
def get_transaction_detail(tx_id: str, request: Request, beginner_mode: bool = False):
    session_id = get_session_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transactions WHERE id = ? AND session_id = ?",
        (tx_id, session_id)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found or does not belong to this session.")

    tx_dict = dict(row)
    raw_reason = tx_dict.get('failure_reason')

    explanation = explainer.explain_failure(
        raw_reason if (raw_reason and str(raw_reason).lower() != 'nan') else "NORMAL",
        tx_dict['amount'],
        tx_dict['id'],
        beginner_mode=beginner_mode
    )
    delay_prediction = reconciler.predict_settlement_delay(raw_reason)
    handoff_summary = gating.generate_handoff_summary(tx_id, session_id=session_id)

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


@app.post("/api/transaction/{tx_id}/execute")
def execute_transaction_action(tx_id: str, req: ExecuteRequest, request: Request):
    session_id = req.session_id or get_session_id(request)
    result = reconciler.execute_action(tx_id, req.cause, session_id=session_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@app.post("/api/qa")
def ask_auditor_qa(req: QARequest, request: Request):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    session_id = req.session_id or get_session_id(request)
    answer = explainer.ask_auditor_qa(req.query, session_id=session_id)
    return {"query": req.query, "answer": answer, "session_id": session_id}


@app.post("/api/approve")
def handle_human_decision(req: DecisionRequest, request: Request):
    session_id = req.session_id or get_session_id(request)
    success, msg = gating.process_human_decision(
        req.tx_id, req.decision.upper(), req.reviewer, session_id=session_id
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.get("/api/report")
def get_batch_report(request: Request):
    session_id = get_session_id(request)
    report = explainer.generate_batch_report(session_id=session_id)
    return {"report": report, "session_id": session_id}


@app.get("/api/audit-log")
def get_audit_log(request: Request):
    session_id = get_session_id(request)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM audit_log WHERE session_id = ? ORDER BY timestamp DESC",
        (session_id,)
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"audit_log": rows, "session_id": session_id}


@app.get("/api/export-csv")
def export_csv(request: Request):
    """
    Enterprise-grade audit trail CSV.
    Deterministically sorted, enriched with transaction context,
    and strictly scoped to the active session.
    """
    session_id = get_session_id(request)
    conn = get_db()

    df = pd.read_sql_query(
        """
        SELECT
            a.id          AS audit_entry_id,
            a.timestamp,
            a.transaction_id,
            t.customer_id,
            t.amount,
            t.currency,
            t.status      AS current_status,
            a.action,
            a.details,
            CASE WHEN a.is_live_api_call = 1 THEN 'LIVE_API' ELSE 'SIMULATED' END AS execution_mode
        FROM audit_log a
        LEFT JOIN transactions t ON a.transaction_id = t.id
        WHERE a.session_id = ?
        ORDER BY a.timestamp ASC, a.id ASC
        """,
        conn,
        params=(session_id,)
    )
    conn.close()

    csv_str = df.to_csv(index=False)
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_trail.csv"}
    )


@app.get("/api/export-pdf")
def export_pdf(request: Request):
    session_id = get_session_id(request)
    from report_generator import generate_pdf_report
    pdf_buffer = generate_pdf_report(session_id=session_id)
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=AI_Settlement_Executive_Report.pdf"}
    )


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
