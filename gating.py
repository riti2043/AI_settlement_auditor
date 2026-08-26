import sqlite3
import json
from datetime import datetime
from explain import ExplainabilityAgent

DB_PATH = "auditor.db"

class GatingEngine:
    def __init__(self):
        self.explainer = ExplainabilityAgent()

    def process_human_decision(self, tx_id, decision, reviewer="Human Admin"):
        """
        Handles Approve or Reject actions for transactions paused by the Fair Incentive Gate.
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Transaction not found."

        amount = float(row[2]) if row[2] else 0.0
        
        if decision == "APPROVE":
            new_status = "Recovered"
            action_taken = "Approved by Human Admin: Overridden Incentive Threshold & Retry Sent"
            
            gw_fee = round(amount * 0.02, 2)
            bank_fee = round(amount * 0.005, 2)
            gst = round((gw_fee + bank_fee) * 0.18, 2)
            net_settled = round(amount - (gw_fee + bank_fee + gst), 2)
            fee_json = json.dumps({
                "gross_amount": amount,
                "gateway_fee": gw_fee,
                "bank_fee": bank_fee,
                "gst": gst,
                "net_settled": net_settled
            })

            cursor.execute('''
                UPDATE transactions 
                SET status = ?, action_taken = ?, flagged = 0, fee_breakdown = ?, updated_at = ?
                WHERE id = ?
            ''', (new_status, action_taken, fee_json, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tx_id))

            cursor.execute('''
                INSERT INTO audit_log (transaction_id, action, details, is_live_api_call)
                VALUES (?, ?, ?, 1)
            ''', (tx_id, "HUMAN_APPROVED", f"Reviewer ({reviewer}) approved flagged transaction. Incentive applied.", 1))

        elif decision == "REJECT":
            new_status = "Mismatched"
            action_taken = "Rejected by Human Admin: Incentive Cancelled. Standard Recovery Initiated."

            cursor.execute('''
                UPDATE transactions 
                SET status = ?, action_taken = ?, flagged = 0, updated_at = ?
                WHERE id = ?
            ''', (new_status, action_taken, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tx_id))

            cursor.execute('''
                INSERT INTO audit_log (transaction_id, action, details, is_live_api_call)
                VALUES (?, ?, ?, 0)
            ''', (tx_id, "HUMAN_REJECTED", f"Reviewer ({reviewer}) rejected flagged transaction. Incentive declined.", 0))

        conn.commit()
        conn.close()
        return True, f"Transaction {tx_id} successfully updated to {decision}."

    def generate_handoff_summary(self, tx_id):
        """
        Generates a concise case summary for a support agent taking over.
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return "Case Summary: Transaction not found."

        amount = row[2]
        status = row[4]
        reason = row[9]
        action = row[11]

        prompt = f"""
        Generate a 2-sentence Handoff Summary for a human support ticket:
        - Transaction: {tx_id}
        - Amount: ₹{amount}
        - Current Status: {status}
        - Failure Cause: {reason}
        - Last Agent Action: {action}

        Make it clear so a support agent reading this instantly understands the current state.
        """
        
        if self.explainer.client:
            try:
                res = self.explainer.client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.1-8b-instant",
                    max_tokens=80
                )
                return res.choices[0].message.content.strip()
            except Exception:
                pass

        return f"Handoff Summary for {tx_id}: Amount ₹{amount} encountered failure ({reason}). Current status is {status} following action: '{action}'."

if __name__ == "__main__":
    gate = GatingEngine()
    print("Handoff summary test:", gate.generate_handoff_summary("tx_test_123"))
