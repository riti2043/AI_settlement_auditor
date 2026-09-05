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
        Handles Approve or Reject actions for transactions flagged for human review.
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Transaction not found."

        amount = float(row[2]) if row[2] else 0.0
        failure_reason = row[9]
        
        if decision == "APPROVE":
            if failure_reason == "DUPLICATE_CHARGE_SUSPECTED":
                new_status = "Recovered"
                action_taken = "Approved by Human Admin: Duplicate Confirmed. Refund Initiated."
                details = f"Reviewer ({reviewer}) approved duplicate refund for ₹{amount}."
            else:
                new_status = "Recovered"
                action_taken = "Approved by Human Admin: Action Authorized."
                details = f"Reviewer ({reviewer}) approved flagged transaction."
            
            cursor.execute('''
                UPDATE transactions 
                SET status = ?, action_taken = ?, flagged = 0, updated_at = ?
                WHERE id = ?
            ''', (new_status, action_taken, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tx_id))

            cursor.execute('''
                INSERT INTO audit_log (transaction_id, action, details, is_live_api_call)
                VALUES (?, ?, ?, 1)
            ''', (tx_id, "HUMAN_APPROVED", details, 1))

        elif decision == "REJECT":
            if failure_reason == "DUPLICATE_CHARGE_SUSPECTED":
                new_status = "Settled"
                action_taken = "Rejected by Human Admin: Duplicate Denied. Valid Charge."
                details = f"Reviewer ({reviewer}) rejected duplicate flag. Charge stands."
            else:
                new_status = "Mismatched"
                action_taken = "Rejected by Human Admin: Action Denied."
                details = f"Reviewer ({reviewer}) rejected flagged transaction."

            cursor.execute('''
                UPDATE transactions 
                SET status = ?, action_taken = ?, flagged = 0, updated_at = ?
                WHERE id = ?
            ''', (new_status, action_taken, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tx_id))

            cursor.execute('''
                INSERT INTO audit_log (transaction_id, action, details, is_live_api_call)
                VALUES (?, ?, ?, 0)
            ''', (tx_id, "HUMAN_REJECTED", details, 0))

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
                    model="groq/compound-mini",
                    max_tokens=80
                )
                return res.choices[0].message.content.strip()
            except Exception:
                pass

        return f"Handoff Summary for {tx_id}: Amount ₹{amount} encountered failure ({reason}). Current status is {status} following action: '{action}'."

if __name__ == "__main__":
    gate = GatingEngine()
    print("Handoff summary test:", gate.generate_handoff_summary("tx_test_123"))
