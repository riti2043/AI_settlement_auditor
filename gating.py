import json
from datetime import datetime
from explain import ExplainabilityAgent
from database import get_db


class GatingEngine:
    def __init__(self):
        self.explainer = ExplainabilityAgent()

    def process_human_decision(self, tx_id: str, decision: str,
                               reviewer: str = "Human Admin",
                               session_id: str = "default"):
        """
        Handles Approve or Reject actions for flagged transactions.
        Validates that the transaction belongs to the requesting session.
        """
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM transactions WHERE id = ? AND session_id = ?",
            (tx_id, session_id)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Transaction not found or does not belong to this session."

        amount = float(row["amount"]) if row["amount"] else 0.0
        failure_reason = row["failure_reason"]

        if decision == "APPROVE":
            if failure_reason == "DUPLICATE_CHARGE_SUSPECTED":
                new_status = "Recovered"
                action_taken = "Approved by Human Admin: Duplicate Confirmed. Refund Initiated."
                details = f"Reviewer ({reviewer}) approved duplicate refund for Rs.{amount}."
            else:
                new_status = "Recovered"
                action_taken = "Approved by Human Admin: Action Authorized."
                details = f"Reviewer ({reviewer}) approved flagged transaction."

            cursor.execute('''
                UPDATE transactions
                SET status = ?, action_taken = ?, flagged = 0, updated_at = ?
                WHERE id = ? AND session_id = ?
            ''', (new_status, action_taken,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  tx_id, session_id))

            cursor.execute('''
                INSERT INTO audit_log (session_id, transaction_id, action, details, is_live_api_call)
                VALUES (?, ?, ?, ?, 1)
            ''', (session_id, tx_id, "HUMAN_APPROVED", details))

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
                WHERE id = ? AND session_id = ?
            ''', (new_status, action_taken,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  tx_id, session_id))

            cursor.execute('''
                INSERT INTO audit_log (session_id, transaction_id, action, details, is_live_api_call)
                VALUES (?, ?, ?, ?, 0)
            ''', (session_id, tx_id, "HUMAN_REJECTED", details))

        conn.commit()
        conn.close()
        return True, f"Transaction {tx_id} successfully updated to {decision}."

    def generate_handoff_summary(self, tx_id: str, session_id: str = "default"):
        """
        Generates a concise case summary for a support agent taking over.
        Scoped to the requesting session.
        """
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM transactions WHERE id = ? AND session_id = ?",
            (tx_id, session_id)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return "Case Summary: Transaction not found."

        amount = row["amount"]
        status = row["status"]
        reason = row["failure_reason"]
        action = row["action_taken"]

        prompt = f"""
        Generate a 2-sentence Handoff Summary for a human support ticket:
        - Transaction: {tx_id}
        - Amount: Rs.{amount}
        - Current Status: {status}
        - Failure Cause: {reason}
        - Last Agent Action: {action}

        Make it clear so a support agent reading this instantly understands the current state. No em dashes.
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

        return (
            f"Handoff Summary for {tx_id}: Amount Rs.{amount} encountered failure ({reason}). "
            f"Current status is {status} following action: '{action}'."
        )


if __name__ == "__main__":
    gate = GatingEngine()
    print("Handoff summary test:", gate.generate_handoff_summary("tx_test_123"))
