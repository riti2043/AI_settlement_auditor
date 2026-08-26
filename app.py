import streamlit as st
import pandas as pd
import sqlite3
import json
import os
import textwrap
from datetime import datetime
from dotenv import load_dotenv

from razorpay_client import RazorpayGenerator
from reconciliation import ReconciliationEngine
from explain import ExplainabilityAgent
from gating import GatingEngine

load_dotenv()

DB_PATH = "auditor.db"

# Page config
st.set_page_config(
    page_title="AI Settlement Auditor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Helper function to render HTML cleanly without Markdown code-block indentation bugs
def render_html(html_str):
    st.markdown(textwrap.dedent(html_str), unsafe_allow_html=True)

# Master CSS - Stripe / Linear / Vercel Dark Mode Aesthetic
MASTER_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* Global Reset & Typography */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: #0F1115 !important;
    color: #F5F1E8 !important;
    -webkit-font-smoothing: antialiased;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 4rem !important;
    max-width: 1350px !important;
}

/* Header Component */
.header-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    border-bottom: 1px solid #2A2D34;
    padding-bottom: 16px;
}
.header-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #F5F1E8;
    letter-spacing: -0.02em;
    margin: 0 0 4px 0;
}
.header-tagline {
    font-size: 0.85rem;
    color: #9CA3AF;
    margin: 0;
}

/* Tab Component Polish */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    border-bottom: 1px solid #2A2D34;
    background-color: transparent;
}
.stTabs [data-baseweb="tab"] {
    height: 40px;
    padding: 0 16px;
    background-color: transparent;
    border-radius: 6px 6px 0 0;
    color: #9CA3AF !important;
    font-size: 0.875rem;
    font-weight: 500;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    color: #C9A227 !important;
    font-weight: 600;
    border-bottom: 2px solid #C9A227 !important;
    background-color: rgba(201, 162, 39, 0.05) !important;
}

/* Metric Cards Container */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}
.metric-card {
    background-color: #1A1D23;
    border: 1px solid #2A2D34;
    border-radius: 8px;
    padding: 16px 20px;
    transition: border-color 0.2s ease;
}
.metric-card:hover {
    border-color: #3A3D46;
}
.metric-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #9CA3AF;
    margin-bottom: 8px;
}
.metric-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #F5F1E8;
    letter-spacing: -0.02em;
}
.metric-value.highlight {
    color: #C9A227;
}

/* Custom Table Component */
.card-table-container {
    background-color: #1A1D23;
    border: 1px solid #2A2D34;
    border-radius: 8px;
    overflow: hidden;
    margin-top: 12px;
}
.custom-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
}
.custom-table th {
    background-color: #14171D;
    color: #9CA3AF;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 12px 16px;
    border-bottom: 1px solid #2A2D34;
}
.custom-table td {
    padding: 14px 16px;
    border-bottom: 1px solid #2A2D34;
    color: #F5F1E8;
    font-size: 0.875rem;
}
.custom-table tr:last-child td {
    border-bottom: none;
}
.custom-table tr:hover td {
    background-color: rgba(255, 255, 255, 0.02);
}
.font-mono {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem;
    color: #C9A227;
}

/* Badges / Status Pills */
.pill {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    line-height: 1.2;
}
.pill-settled { background-color: rgba(63, 185, 80, 0.12); color: #3FB950; border: 1px solid rgba(63, 185, 80, 0.3); }
.pill-recovered { background-color: rgba(201, 162, 39, 0.12); color: #C9A227; border: 1px solid rgba(201, 162, 39, 0.3); }
.pill-flagged { background-color: rgba(217, 164, 65, 0.12); color: #D9A441; border: 1px solid rgba(217, 164, 65, 0.3); }
.pill-mismatched { background-color: rgba(229, 83, 75, 0.12); color: #E5534B; border: 1px solid rgba(229, 83, 75, 0.3); }
.pill-live { background-color: rgba(63, 185, 80, 0.1); color: #3FB950; border: 1px dashed #3FB950; font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; }
.pill-sim { background-color: rgba(156, 163, 175, 0.1); color: #9CA3AF; border: 1px dashed #9CA3AF; font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; }

/* Panel & Card Styling */
.panel-card {
    background-color: #1A1D23;
    border: 1px solid #2A2D34;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
}
.panel-card-header {
    font-size: 0.875rem;
    font-weight: 600;
    color: #F5F1E8;
    margin-bottom: 14px;
    border-bottom: 1px solid #2A2D34;
    padding-bottom: 8px;
}

.trend-alert {
    background-color: rgba(229, 83, 75, 0.08);
    border: 1px solid #E5534B;
    border-left: 4px solid #E5534B;
    padding: 12px 16px;
    border-radius: 6px;
    color: #E5534B;
    font-size: 0.875rem;
    font-weight: 600;
    margin-bottom: 16px;
}

.fee-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #2A2D34;
    font-size: 0.875rem;
}
.fee-row:last-child { border-bottom: none; padding-top: 12px; }
.fee-label { color: #9CA3AF; }
.fee-value { font-weight: 600; color: #F5F1E8; }
.fee-deduction { color: #E5534B; font-weight: 500; }
.fee-net { color: #3FB950; font-weight: 700; font-size: 1rem; }

.flagged-card {
    background-color: #1A1D23;
    border: 1px solid #D9A441;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
}
.flagged-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}
.flagged-title { font-size: 1rem; font-weight: 600; color: #F5F1E8; }
.flagged-note {
    font-size: 0.875rem;
    color: #D9A441;
    background-color: rgba(217, 164, 65, 0.08);
    padding: 10px 14px;
    border-radius: 6px;
    margin-bottom: 16px;
    border-left: 3px solid #D9A441;
}

.app-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    background-color: #0F1115;
    border-top: 1px solid #2A2D34;
    padding: 8px 0;
    text-align: center;
    font-size: 0.75rem;
    color: #9CA3AF;
    z-index: 999;
}
</style>
"""

render_html(MASTER_CSS)

# Helper function to fetch DB data
def get_data(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# Status Pill Formatter
def render_pill(status):
    st_str = str(status).strip()
    if st_str == 'Settled':
        return '<span class="pill pill-settled">Settled</span>'
    elif st_str == 'Recovered':
        return '<span class="pill pill-recovered">Recovered</span>'
    elif st_str == 'Flagged':
        return '<span class="pill pill-flagged">Flagged</span>'
    elif st_str == 'BROKEN_PROMISE':
        return '<span class="pill pill-mismatched">Broken Promise</span>'
    else:
        return '<span class="pill pill-mismatched">Mismatched</span>'

def render_api_tag(is_live):
    if is_live:
        return '<span class="pill-live">Live API</span>'
    return '<span class="pill-sim">Simulated</span>'

# Header Component
head_col1, head_col2 = st.columns([3, 1])
with head_col1:
    render_html("""
    <div class="header-container" style="border-bottom:none; margin-bottom:0; padding-bottom:0;">
        <div>
            <div class="header-title">AI Settlement Auditor</div>
            <div class="header-tagline">Multi-Source Reconciliation • Bounded AI Recovery • Fair Incentive Gate</div>
        </div>
    </div>
    """)
with head_col2:
    beginner_mode = st.toggle("💡 Explain Like I'm New Here", value=False)

st.markdown("<hr style='border:1px solid #2A2D34; margin-top:10px; margin-bottom:16px;'>", unsafe_allow_html=True)

# Pipeline Instances
generator = RazorpayGenerator()
reconciler = ReconciliationEngine()
explainer = ExplainabilityAgent()
gating = GatingEngine()

# App Navigation Tabs (Includes Ask the Auditor Q&A)
tab_overview, tab_detail, tab_flagged, tab_qa, tab_audit = st.tabs([
    "Overview", 
    "Transaction Detail", 
    "Flagged for Approval", 
    "Ask the Auditor (Q&A)",
    "Audit Log"
])

# --- TAB 1: OVERVIEW ---
with tab_overview:
    df_tx = get_data("SELECT * FROM transactions ORDER BY updated_at DESC")
    
    total_processed = len(df_tx)
    mismatches_detected = len(df_tx[df_tx['status'].isin(['Mismatched', 'Recovered', 'Flagged', 'BROKEN_PROMISE'])])
    recovered_df = df_tx[df_tx['status'] == 'Recovered']
    amount_recovered = float(recovered_df['amount'].sum()) if not recovered_df.empty else 0.0
    pending_approval = len(df_tx[df_tx['flagged'] == 1])

    # Top Control Bar (Batch trigger + Executive Summary button)
    b_col1, b_col2, _ = st.columns([1, 1, 2])
    with b_col1:
        if st.button("▶ Run New Batch", type="primary", use_container_width=True):
            with st.spinner("Generating Razorpay batch & executing Multi-Source Reconciliation..."):
                generator.generate_batch(7)
                reconciler.run_reconciliation()
            st.rerun()
    with b_col2:
        generate_report = st.button("📊 Executive Batch Report", use_container_width=True)

    st.write("")

    # Executive Summary Card if triggered
    if generate_report:
        with st.spinner("Generating Groq LLM Executive Summary..."):
            if hasattr(explainer, 'generate_batch_report'):
                report_text = explainer.generate_batch_report()
            else:
                report_text = "Executive Batch Summary: Audited current transaction batch. Mismatches detected and processed across automated recovery workflows."
            render_html(f"""
            <div class="panel-card" style="border-left: 4px solid #C9A227;">
                <div class="panel-card-header" style="color: #C9A227;">Executive Batch Summary Report (Groq Llama 3.1)</div>
                <div style="font-size: 0.9rem; line-height: 1.5; color: #F5F1E8;">{report_text}</div>
            </div>
            """)

    # Anomaly Trend Flag Detector (>30% failure rate check)
    if not df_tx.empty:
        counts = df_tx['failure_reason'].value_counts()
        for reason, count in counts.items():
            if reason and count / total_processed >= 0.30:
                render_html(f"""
                <div class="trend-alert">
                    ⚠️ <strong>ANOMALY TREND DETECTED:</strong> Elevated <code>{reason}</code> rate in this batch ({count}/{total_processed} transactions = {count/total_processed*100:.1f}%).
                </div>
                """)

    # Metric Cards
    render_html(f"""
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-label">Transactions Processed</div>
            <div class="metric-value">{total_processed}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Mismatches & Anomalies</div>
            <div class="metric-value">{mismatches_detected}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Amount Recovered</div>
            <div class="metric-value highlight">₹{amount_recovered:,.2f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Pending Approval</div>
            <div class="metric-value">{pending_approval}</div>
        </div>
    </div>
    """)

    if df_tx.empty:
        render_html("""
        <div class="panel-card" style="text-align: center; color: #9CA3AF; padding: 40px 20px;">
            No transactions detected. Click "Run New Batch" to trigger live API audit.
        </div>
        """)
    else:
        rows_list = []
        for _, row in df_tx.iterrows():
            badge = render_pill(row['status'])
            api_badge = render_api_tag(row['is_live_api_call'])
            amt_formatted = f"₹{float(row['amount']):,.2f}"
            tax_flag = ' <span style="color:#E5534B; font-weight:600;">[GST Discrepancy]</span>' if row['tax_mismatch'] else ''
            cid = str(row['customer_id']) if (row['customer_id'] and str(row['customer_id']) != 'None') else 'cust_101'
            rtier = str(row['risk_tier']) if (row['risk_tier'] and str(row['risk_tier']) != 'None') else 'Low'
            
            rows_list.append(f'<tr><td class="font-mono">{row["id"]}</td><td style="font-size: 0.8rem; color: #9CA3AF;">{cid} ({rtier} Risk)</td><td style="font-weight: 600;">{amt_formatted}</td><td>{badge}</td><td>{api_badge}</td><td style="color: #9CA3AF;">{row["action_taken"]}{tax_flag}</td><td style="color: #9CA3AF; font-size: 0.8rem;">{row["updated_at"]}</td></tr>')
        
        rows_html = "".join(rows_list)
        table_html = f'<div class="card-table-container"><table class="custom-table"><thead><tr><th>Transaction ID</th><th>Customer (Risk)</th><th>Amount</th><th>Status</th><th>Type</th><th>Action Taken</th><th>Last Updated</th></tr></thead><tbody>{rows_html}</tbody></table></div>'
        st.markdown(table_html, unsafe_allow_html=True)

# --- TAB 2: TRANSACTION DETAIL ---
with tab_detail:
    df_tx = get_data("SELECT * FROM transactions ORDER BY updated_at DESC")
    
    if df_tx.empty:
        render_html("""
        <div class="panel-card" style="text-align: center; color: #9CA3AF; padding: 40px;">
            No transactions available to inspect. Run a batch from the Overview tab first.
        </div>
        """)
    else:
        selected_tx_id = st.selectbox("Select Transaction ID to inspect:", df_tx['id'].tolist())
        tx_row = df_tx[df_tx['id'] == selected_tx_id].iloc[0]
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            fee_b = tx_row['fee_breakdown']
            if fee_b and not pd.isna(fee_b) and str(fee_b).strip() != "":
                try:
                    fees = json.loads(fee_b)
                    gross = float(fees.get('gross_amount', 0))
                    gw_fee = float(fees.get('gateway_fee', 0))
                    bank_fee = float(fees.get('bank_fee', 0))
                    gst = float(fees.get('gst', 0))
                    net = float(fees.get('net_settled', 0))
                    
                    tax_mismatch_warning = ""
                    if tx_row['tax_mismatch']:
                        tax_mismatch_warning = '<div style="color:#E5534B; font-weight:600; font-size:0.8rem; margin-top:8px;">⚠️ Tax-Line Matcher Warning: GST deviates from standard 18% gateway fee rate.</div>'

                    render_html(f"""
                    <div class="panel-card">
                        <div class="panel-card-header">Fee Breakdown & Multi-Source Audit</div>
                        <div class="fee-row">
                            <span class="fee-label">Gross Amount</span>
                            <span class="fee-value">₹{gross:,.2f}</span>
                        </div>
                        <div class="fee-row">
                            <span class="fee-label">Gateway Fee (2.0%)</span>
                            <span class="fee-deduction">- ₹{gw_fee:,.2f}</span>
                        </div>
                        <div class="fee-row">
                            <span class="fee-label">Bank Fee (0.5%)</span>
                            <span class="fee-deduction">- ₹{bank_fee:,.2f}</span>
                        </div>
                        <div class="fee-row">
                            <span class="fee-label">GST (18.0%)</span>
                            <span class="fee-deduction">- ₹{gst:,.2f}</span>
                        </div>
                        <div class="fee-row">
                            <span class="fee-label" style="color: #C9A227; font-weight: 600;">Net Settled Amount</span>
                            <span class="fee-net">₹{net:,.2f}</span>
                        </div>
                        {tax_mismatch_warning}
                    </div>
                    """)
                except Exception:
                    st.warning("Error parsing fee breakdown.")
            else:
                render_html("""
                <div class="panel-card">
                    <div class="panel-card-header">Fee Breakdown</div>
                    <div style="color: #9CA3AF; font-size: 0.875rem;">
                        Fee breakdown unavailable for un-settled, pending, or declined payments.
                    </div>
                </div>
                """)

        with col_right:
            raw_reason = tx_row['failure_reason']
            if pd.isna(raw_reason) or not raw_reason or str(raw_reason).strip().lower() == 'nan':
                failure_code = "N/A (Standard Processing)"
            else:
                failure_code = str(raw_reason)
            
            try:
                explanation = explainer.explain_failure(
                    raw_reason if (raw_reason and str(raw_reason).lower() != 'nan') else "NORMAL",
                    tx_row['amount'],
                    tx_row['id'],
                    beginner_mode=beginner_mode
                )
            except TypeError:
                explanation = explainer.explain_failure(
                    raw_reason if (raw_reason and str(raw_reason).lower() != 'nan') else "NORMAL",
                    tx_row['amount'],
                    tx_row['id']
                )
            
            if hasattr(reconciler, 'predict_settlement_delay'):
                delay_prediction = reconciler.predict_settlement_delay(raw_reason)
            else:
                delay_prediction = "Estimated resolution: 1–12 hours (Standard processing)"

            if hasattr(gating, 'generate_handoff_summary'):
                summary = gating.generate_handoff_summary(selected_tx_id)
            else:
                summary = f"Handoff Summary for {selected_tx_id}: Transaction audited."

            confidence_note = tx_row['confidence_note'] if ('confidence_note' in tx_row and tx_row['confidence_note'] and str(tx_row['confidence_note']) != 'None') else "Rule-based safety check executed."

            render_html(f"""
            <div class="panel-card">
                <div class="panel-card-header">Agent Analysis & Escalation Ladder</div>
                <div style="margin-bottom: 10px;">
                    <span style="color: #9CA3AF; font-size: 0.75rem; text-transform: uppercase; font-weight: 600;">Failure Cause</span>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #E5534B;">{failure_code}</div>
                </div>
                <div style="margin-bottom: 10px;">
                    <span style="color: #9CA3AF; font-size: 0.75rem; text-transform: uppercase; font-weight: 600;">LLM Cause Analysis</span>
                    <div style="color: #F5F1E8; font-size: 0.85rem; margin-top: 2px;">{explanation}</div>
                </div>
                <div style="margin-bottom: 10px;">
                    <span style="color: #9CA3AF; font-size: 0.75rem; text-transform: uppercase; font-weight: 600;">Settlement Delay Predictor</span>
                    <div style="color: #C9A227; font-size: 0.85rem; margin-top: 2px;">{delay_prediction}</div>
                </div>
                <div style="margin-bottom: 10px;">
                    <span style="color: #9CA3AF; font-size: 0.75rem; text-transform: uppercase; font-weight: 600;">Confidence & Safety Score</span>
                    <div style="color: #3FB950; font-size: 0.85rem; margin-top: 2px;">✓ {confidence_note}</div>
                </div>
                <div>
                    <span style="color: #9CA3AF; font-size: 0.75rem; text-transform: uppercase; font-weight: 600;">Action Executed</span>
                    <div style="color: #F5F1E8; font-size: 0.85rem; margin-top: 2px;">{tx_row['action_taken']} ({render_api_tag(tx_row['is_live_api_call'])})</div>
                </div>
            </div>

            <div class="panel-card">
                <div class="panel-card-header">Handoff Summary (For Support Ticket)</div>
                <div style="color: #9CA3AF; font-size: 0.85rem; line-height: 1.4;">{summary}</div>
            </div>
            """)

# --- TAB 3: FLAGGED FOR APPROVAL ---
with tab_flagged:
    flagged_df = get_data("SELECT * FROM transactions WHERE flagged = 1")

    if flagged_df.empty:
        render_html("""
        <div class="panel-card" style="text-align: center; color: #9CA3AF; padding: 40px;">
            No transactions currently flagged for human review. All recovery actions within safety bounds.
        </div>
        """)
    else:
        for _, row in flagged_df.iterrows():
            amt_fmt = f"₹{float(row['amount']):,.2f}"
            
            render_html(f"""
            <div class="flagged-card">
                <div class="flagged-header">
                    <div class="flagged-title">Transaction: <span class="font-mono">{row['id']}</span> | Customer: <strong>{row['customer_id']}</strong> ({row['risk_tier']} Risk)</div>
                    <div style="font-size: 1rem; font-weight: 700; color: #F5F1E8;">{amt_fmt}</div>
                </div>
                <div class="flagged-note">
                    <strong>Fair Incentive Gate Reason:</strong> {row['flag_reason']}
                </div>
            </div>
            """)
            
            c1, c2, _ = st.columns([1, 1, 4])
            with c1:
                if st.button(f"Approve", key=f"app_{row['id']}", type="primary", use_container_width=True):
                    gating.process_human_decision(row['id'], "APPROVE")
                    st.rerun()
            with c2:
                if st.button(f"Reject", key=f"rej_{row['id']}", use_container_width=True):
                    gating.process_human_decision(row['id'], "REJECT")
                    st.rerun()
            
            render_html("<div style='margin-bottom: 24px;'></div>")

# --- TAB 4: ASK THE AUDITOR (Q&A) ---
with tab_qa:
    render_html("""
    <div class="panel-card">
        <div class="panel-card-header">Ask the Auditor (Groq Natural Language Q&A)</div>
        <div style="color: #9CA3AF; font-size: 0.85rem; margin-bottom: 12px;">
            Ask any question about your active batch, specific transaction IDs, risk tiers, or mismatch recoveries.
        </div>
    </div>
    """)
    
    user_query = st.text_input("Type your question for the Auditor:", placeholder="e.g., 'What happened to transaction tx_live_...?' or 'Summarize high risk customers'")
    
    if st.button("Submit Question", type="primary"):
        if user_query.strip():
            with st.spinner("Consulting live database context & Groq Llama 3.1..."):
                if hasattr(explainer, 'ask_auditor_qa'):
                    answer = explainer.ask_auditor_qa(user_query)
                else:
                    answer = f"Q&A Analysis for '{user_query}': Active database contains transactions undergoing audit and recovery."
                render_html(f"""
                <div class="panel-card" style="border-left: 4px solid #C9A227;">
                    <div style="font-weight: 600; color: #C9A227; margin-bottom: 6px;">Auditor Response:</div>
                    <div style="color: #F5F1E8; font-size: 0.9rem; line-height: 1.5;">{answer}</div>
                </div>
                """)
        else:
            st.warning("Please enter a question first.")

# --- TAB 5: AUDIT LOG ---
with tab_audit:
    audit_df = get_data("SELECT * FROM audit_log ORDER BY timestamp DESC")
    
    col_dl, _ = st.columns([1, 3])
    with col_dl:
        if not audit_df.empty:
            csv_data = audit_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Audit Trail (CSV)",
                data=csv_data,
                file_name=f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

    st.write("")

    if audit_df.empty:
        render_html("""
        <div class="panel-card" style="text-align: center; color: #9CA3AF; padding: 40px;">
            No audit logs recorded yet. Run a batch to populate.
        </div>
        """)
    else:
        rows_list = []
        for _, row in audit_df.iterrows():
            api_badge = render_api_tag(row['is_live_api_call'])
            rows_list.append(f'<tr><td style="color: #9CA3AF; font-size: 0.8rem;">{row["timestamp"]}</td><td class="font-mono">{row["transaction_id"]}</td><td style="font-weight: 600; font-size: 0.85rem;">{row["action"]}</td><td>{api_badge}</td><td style="color: #F5F1E8; font-size: 0.85rem;">{row["details"]}</td></tr>')
        
        rows_html = "".join(rows_list)
        table_html = f'<div class="card-table-container"><table class="custom-table"><thead><tr><th>Timestamp</th><th>Transaction ID</th><th>Action Executed</th><th>Type</th><th>Details</th></tr></thead><tbody>{rows_html}</tbody></table></div>'
        st.markdown(table_html, unsafe_allow_html=True)

# Fixed Footer
render_html("""
<div class="app-footer">
    Running on Razorpay test-mode data. No real transactions are processed.
</div>
""")
