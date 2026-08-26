import os
import sqlite3
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DB_PATH = "auditor.db"

class ExplainabilityAgent:
    def __init__(self):
        if GROQ_API_KEY and not GROQ_API_KEY.startswith("gsk_..."):
            try:
                self.client = Groq(api_key=GROQ_API_KEY)
            except Exception as e:
                print(f"Groq Client Init Warning: {e}")
                self.client = None
        else:
            self.client = None

    def explain_failure(self, failure_reason, amount, tx_id, beginner_mode=False):
        """
        Generates explanation with tone adjusted based on 'Explain Like I'm New Here' mode toggle.
        """
        if not self.client:
            fallbacks = {
                "PAYMENT_DECLINED_BANK": "The customer's issuing bank declined the transaction due to temporary network downtime or insufficient funds.",
                "SETTLEMENT_DELAYED_KYC": "Settlement is temporarily delayed due to routine merchant KYC compliance verification with the partner bank.",
                "REFUND_STUCK_GATEWAY": "The refund request was accepted by Razorpay but hit a gateway timeout with the beneficiary bank.",
                "HIGH_INCENTIVE_OFFER": "Recovery action paused because the requested retry incentive waiver exceeds standard merchant threshold rules.",
                "TAX_CALCULATION_DISCREPANCY": "The GST amount stored on this transaction deviates from the expected 18% tax calculation rate.",
                "DUPLICATE_CHARGE_SUSPECTED": "Multiple identical charge requests were detected for the same customer within a short time window.",
                "SUBSCRIPTION_AUTOPAY_FAILED": "Recurring subscription payment attempt failed at the gateway and is undergoing escalation."
            }
            res = fallbacks.get(failure_reason, "Transaction encountered a technical delay during processing.")
            if beginner_mode:
                return f"[Beginner Explanation] {res} In simple terms: we are watching this step so no funds get misplaced while the bank or system catches up."
            return res

        tone_instruction = (
            "Explain in simple, educational, beginner-friendly terms (as if explaining to someone new to fintech). "
            "Avoid overly dense jargon and use 2 friendly sentences."
        ) if beginner_mode else (
            "Explain in 1-2 concise, professional, direct sentences for an experienced financial ops dashboard."
        )

        prompt = f"""
        You are an AI financial auditor. {tone_instruction}
        - Transaction ID: {tx_id}
        - Amount: ₹{amount}
        - Failure Code: {failure_reason}

        Do not include markdown codeblocks or quotes.
        """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                max_tokens=120
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Groq API Error: {e}")
            return "Transaction encountered a delay during settlement processing."

    def ask_auditor_qa(self, user_query):
        """
        Settlement Q&A Agent ('Ask the Auditor'): Answers natural language questions using SQLite context.
        """
        conn = sqlite3.connect(DB_PATH)
        df_tx = pd.read_sql_query("SELECT id, customer_id, amount, status, failure_reason, action_taken, risk_tier FROM transactions", conn)
        conn.close()

        context_str = df_tx.to_string(index=False)

        if not self.client:
            return f"Q&A Analysis for: '{user_query}'\nBased on your database ({len(df_tx)} records), the agent is actively auditing settlements. Key issues detected: {len(df_tx[df_tx['status']=='Mismatched'])} mismatches."

        prompt = f"""
        You are the 'Ask the Auditor' Q&A assistant for the AI Settlement Auditor dashboard.
        Answer the user's question accurately using ONLY the live transaction database context below:

        [DATABASE CONTEXT]
        {context_str}

        [USER QUESTION]
        {user_query}

        Provide a direct, helpful 2-3 sentence response. If asking about a specific transaction, highlight its amount, status, and action taken.
        """

        try:
            res = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                max_tokens=200
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            return f"Error executing Q&A analysis: {e}"

    def generate_batch_report(self):
        """
        Weekly / Batch Executive Summary Report Generator.
        """
        conn = sqlite3.connect(DB_PATH)
        df_tx = pd.read_sql_query("SELECT * FROM transactions", conn)
        conn.close()

        if df_tx.empty:
            return "No batch data available to generate executive report."

        total = len(df_tx)
        mismatches = len(df_tx[df_tx['status'].isin(['Mismatched', 'Recovered', 'Flagged'])])
        recovered_df = df_tx[df_tx['status'] == 'Recovered']
        recovered_amt = float(recovered_df['amount'].sum()) if not recovered_df.empty else 0.0

        if not self.client:
            return f"Executive Batch Summary: Audited {total} transactions. Detected {mismatches} mismatches and successfully recovered ₹{recovered_amt:,.2f} across automated workflows. All recovery actions were logged to the audit trail."

        prompt = f"""
        Generate a concise, 3-sentence Executive Summary Report for a fintech CEO based on this audit batch:
        - Total Transactions: {total}
        - Total Mismatches Detected: {mismatches}
        - Total Amount Recovered: ₹{recovered_amt:,.2f}
        - Anomaly Types: {', '.join(df_tx['failure_reason'].dropna().unique())}

        Highlight audit precision, money recovered, and safety gating.
        """

        try:
            res = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                max_tokens=150
            )
            return res.choices[0].message.content.strip()
        except Exception:
            return f"Executive Batch Summary: Audited {total} transactions. Detected {mismatches} mismatches and successfully recovered ₹{recovered_amt:,.2f}."

if __name__ == "__main__":
    agent = ExplainabilityAgent()
    print("Q&A Test:", agent.ask_auditor_qa("How many transactions were recovered?"))
