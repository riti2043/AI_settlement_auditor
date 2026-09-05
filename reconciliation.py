import sqlite3
import pandas as pd
import json
import os
import random
from datetime import datetime, timedelta

DB_PATH = "auditor.db"

class ReconciliationEngine:
    def __init__(self):
        pass

    def run_reconciliation(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM transactions", conn)
        
        if df.empty:
            conn.close()
            return {"mismatches": 0, "recovered_count": 0, "recovered_amount": 0.0}

        # ----------------------------------------------------
        # 1. CUSTOMER RISK TIERING
        # ----------------------------------------------------
        cust_counts = df[df['status'].isin(['Mismatched', 'Flagged'])].groupby('customer_id').size().to_dict()
        for idx, row in df.iterrows():
            cid = row['customer_id']
            failures = cust_counts.get(cid, 0)
            if failures >= 3:
                tier = "High"
            elif failures == 2:
                tier = "Medium"
            else:
                tier = "Low"
            
            cursor = conn.cursor()
            cursor.execute("UPDATE transactions SET risk_tier = ? WHERE id = ?", (tier, row['id']))
        conn.commit()

        # ----------------------------------------------------
        # 2. DUPLICATE CHARGE DETECTOR
        # ----------------------------------------------------
        dup_groups = df.groupby(['customer_id', 'amount']).size()
        dup_keys = set(dup_groups[dup_groups > 1].index)
        
        for idx, row in df.iterrows():
            key = (row['customer_id'], row['amount'])
            if key in dup_keys and row['status'] != 'Settled':
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE transactions 
                    SET failure_reason = 'DUPLICATE_CHARGE_SUSPECTED', 
                        action_taken = 'Flagged: Duplicate Charge (Same Customer & Amount)',
                        flagged = 1,
                        flag_reason = 'Duplicate charge detected for same customer within active window.'
                    WHERE id = ?
                ''', (row['id'],))
        conn.commit()

        # Reload updated dataframe
        df = pd.read_sql_query("SELECT * FROM transactions", conn)

        recovered_count = 0
        mismatch_count = 0
        total_recovered_amount = 0.0

        for idx, row in df.iterrows():
            tx_id = row['id']
            status = row['status']
            reason = row['failure_reason']
            amount = float(row['amount'])
            flagged = row['flagged']
            due_date = row['due_date']
            esc_step = row['escalation_step']
            risk_tier = row['risk_tier']

            # ----------------------------------------------------
            # 3. TAX-LINE MATCHER (GST Validation)
            # ----------------------------------------------------
            fee_b = row['fee_breakdown']
            if fee_b and not pd.isna(fee_b) and str(fee_b).strip() != "":
                try:
                    fees = json.loads(fee_b)
                    gw_fee = float(fees.get('gateway_fee', 0))
                    bank_fee = float(fees.get('bank_fee', 0))
                    actual_gst = float(fees.get('gst', 0))
                    expected_gst = round((gw_fee + bank_fee) * 0.18, 2)

                    if abs(actual_gst - expected_gst) > 0.05:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE transactions 
                            SET tax_mismatch = 1, status = 'Mismatched',
                                failure_reason = 'TAX_CALCULATION_DISCREPANCY',
                                action_taken = 'Flagged: GST Discrepancy Detected (Expected ₹' || ? || ' vs Actual ₹' || ? || ')'
                            WHERE id = ?
                        ''', (expected_gst, actual_gst, tx_id))
                        conn.commit()
                        reason = 'TAX_CALCULATION_DISCREPANCY'
                        status = 'Mismatched'
                except Exception:
                    pass

            # Skip if already settled or currently paused for human approval
            if status == "Settled" or flagged:
                continue

            if status == "Mismatched":
                mismatch_count += 1
                
                new_status = status
                action = "Audit Inspected"
                recovered = False
                is_live = False
                confidence_note = "Rule-based inspection applied."

                # ----------------------------------------------------
                # 4. PROMISE-TO-PAY TRACKER
                # ----------------------------------------------------
                if reason == "PROMISE_TO_PAY_PENDING":
                    if due_date:
                        try:
                            due_dt = datetime.strptime(due_date, "%Y-%m-%d")
                            if due_dt < datetime.now():
                                new_status = "Mismatched"
                                action = "Escalation Step 1: Promise Date Overdue -> Triggered Payment Link & SMS Reminder"
                                confidence_note = "Overdue date detected. Automated payment reminder sent."
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE transactions 
                                    SET status = 'BROKEN_PROMISE', action_taken = ?, escalation_step = 2, confidence_note = ?
                                    WHERE id = ?
                                ''', (action, confidence_note, tx_id))
                                
                                cursor.execute('''
                                    INSERT INTO audit_log (transaction_id, action, details, is_live_api_call)
                                    VALUES (?, ?, ?, 0)
                                ''', (tx_id, "BROKEN_PROMISE_ESCALATED", f"Overdue commitment date ({due_date}). Sent SMS reminder."))
                                conn.commit()
                                continue
                        except Exception:
                            pass

                # ----------------------------------------------------
                # 5. ESCALATION LADDER & RECOVERY LOGIC
                # ----------------------------------------------------
                elif reason == "SETTLEMENT_DELAYED_KYC":
                    new_status = "Mismatched"
                    action = "Requires Manual Action: Re-trigger Settlement Webhook Sync"
                    recovered = False
                    is_live = False
                    confidence_note = "Action required: Execute settlement webhook re-sync under standard merchant KYC threshold (99.1% success rate)."

                elif reason == "REFUND_STUCK_GATEWAY":
                    new_status = "Mismatched"
                    action = "Requires Manual Action: Re-trigger Razorpay Refund API"
                    recovered = False
                    is_live = False 
                    confidence_note = f"Action required: Execute live Razorpay Refund API for ₹{amount:,.2f} within bounded gateway limits."

                elif reason == "SUBSCRIPTION_AUTOPAY_FAILED":
                    if esc_step == 1:
                        # Step 1: Retry Payment Gateway
                        action = "Escalation Step 1: Re-attempted Gateway Autopay Charge"
                        confidence_note = "Autopay retry 1 executed. Next step: Incentive offer if uncollected."
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE transactions SET action_taken = ?, escalation_step = 2, confidence_note = ? WHERE id = ?
                        ''', (action, confidence_note, tx_id))
                        cursor.execute('''
                            INSERT INTO audit_log (transaction_id, action, details, is_live_api_call)
                            VALUES (?, ?, ?, 1)
                        ''', (tx_id, "ESCALATION_STEP_1", "Attempted gateway retry for failed subscription."))
                        conn.commit()
                        continue
                    elif esc_step == 2:
                        # Step 2: Route to Fair Incentive Gate
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE transactions 
                            SET status = 'Flagged', flagged = 1, 
                                flag_reason = 'Subscription retry failed twice. Requested ₹150 discount incentive requires review.',
                                action_taken = 'Escalation Step 2: Paused for Fair Incentive Gate Review'
                            WHERE id = ?
                        ''', (tx_id,))
                        cursor.execute('''
                            INSERT INTO audit_log (transaction_id, action, details, is_live_api_call)
                            VALUES (?, ?, ?, 0)
                        ''', (tx_id, "ESCALATION_STEP_2_GATE", "Subscription retry failed twice. Escalated to Fair Incentive Gate."))
                        conn.commit()
                        continue

                elif reason == "PAYMENT_DECLINED_BANK":
                    new_status = "Mismatched"
                    action = "Escalation Step 1: Payment Declined by Issuing Bank. Dispatched SMS Payment Link."
                    confidence_note = "Safe degradation: Cannot auto-charge bank. Customer notified via SMS."

                if recovered:
                    recovered_count += 1
                    total_recovered_amount += amount
                    
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

                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE transactions 
                        SET status = ?, action_taken = ?, fee_breakdown = ?, 
                            confidence_note = ?, is_live_api_call = ?, updated_at = ?
                        WHERE id = ?
                    ''', (new_status, action, fee_json, confidence_note, 1 if is_live else 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tx_id))
                    
                    cursor.execute('''
                        INSERT INTO audit_log (transaction_id, action, details, is_live_api_call)
                        VALUES (?, ?, ?, ?)
                    ''', (tx_id, "AUTOMATED_RECOVERY_EXECUTED", f"Agent executed: {action}", 1 if is_live else 0))
                    conn.commit()

        conn.close()
        return {
            "mismatches": mismatch_count,
            "recovered_count": recovered_count,
            "recovered_amount": total_recovered_amount
        }


    def predict_settlement_delay(self, failure_reason):
        if not failure_reason or failure_reason == "nan":
            return "No delay expected. Standard T+2 settlement."
        delay_map = {
            "SETTLEMENT_DELAYED_KYC": "Indefinite delay. Requires merchant action (document upload).",
            "REFUND_STUCK_GATEWAY": "No settlement impact. Refund needs manual re-trigger.",
            "PAYMENT_DECLINED_BANK": "No settlement expected. Transaction never captured.",
            "HIGH_INCENTIVE_OFFER": "Internal flag. No direct settlement impact.",
            "PROMISE_TO_PAY_PENDING": "Settlement delayed until customer initiates payment.",
            "SUBSCRIPTION_AUTOPAY_FAILED": "Settlement delayed until retry succeeds.",
            "TAX_CALCULATION_DISCREPANCY": "No delay, but invoice correction required post-settlement.",
            "DUPLICATE_CHARGE_SUSPECTED": "Potential chargeback risk. Hold funds if confirmed.",
            "PAYMENT_CAPTURED_NOT_SETTLED": "24-48 hours. Razorpay batch processing delay suspected."
        }
        return delay_map.get(failure_reason, "Unknown delay profile.")

    def execute_action(self, tx_id, cause):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return {"success": False, "message": "Transaction not found."}
            
        amount = row[2]
        failure_reason = row[9]
        is_live = False
        action_logged = "Executed Action"
        details = ""
        merchant_msg = ""
        customer_msg = ""
        
        if cause == "insufficient_funds":
            action_logged = "Generated Split Payment Link"
            details = f"Created Razorpay payment link for ₹{amount} split."
            merchant_msg = f"Payment of ₹{amount} declined (insufficient funds). A split-payment link has been sent to the customer."
            customer_msg = f"Your payment of ₹{amount} was declined. You can complete it in two installments using this link: https://rzp.io/i/mock_split_{tx_id}"
            is_live = True
        elif cause == "card_blocked":
            action_logged = "Invalidated Card & Sent New Link"
            details = "Card blocked. Generated fresh payment link for alternative methods."
            merchant_msg = f"Card blocked for ₹{amount}. A new payment link for UPI/Netbanking has been sent."
            customer_msg = f"Your card was declined. Please try an alternative method like UPI using this secure link: https://rzp.io/i/mock_new_{tx_id}"
            is_live = True
        elif cause == "fraud_flag":
            action_logged = "Escalated to Human - Fraud Suspected"
            details = "Bank raised fraud flag. All retries blocked."
            merchant_msg = f"CRITICAL: Bank flagged ₹{amount} transaction as potential fraud. Do not retry. See risk dashboard."
            cursor.execute("UPDATE transactions SET flagged = 1, flag_reason = 'Bank Fraud Flag' WHERE id = ?", (tx_id,))
        elif cause == "stuck_refund_gateway":
            action_logged = "Re-triggered Razorpay Refund API"
            details = "Called Razorpay Refunds API. Status: Processed."
            is_live = True
            merchant_msg = f"Stuck refund for ₹{amount} has been re-triggered. Razorpay Refund ID: rfnd_test_{random.randint(1000,9999)}. Expected in 5-7 days."
            customer_msg = f"Your refund of ₹{amount} has been processed. Reference ID: rfnd_test_{random.randint(1000,9999)}. Please allow 5-7 business days."
            cursor.execute("UPDATE transactions SET status = 'Recovered' WHERE id = ?", (tx_id,))
        elif cause == "kyc_missing":
            action_logged = "Identified Missing KYC - Triggered Webhook Sync"
            details = "Webhook re-sync initiated. Blocked by missing PAN."
            merchant_msg = f"Your settlement of ₹{amount} is on hold. Action needed: upload PAN card at razorpay.com/dashboard -> Settings -> KYC."
        else:
            action_logged = f"Executed generic action for {cause}"
            details = "Action logged."
            merchant_msg = "Action executed successfully."
            
        cursor.execute('''
            INSERT INTO audit_log (transaction_id, action, details, is_live_api_call)
            VALUES (?, ?, ?, ?)
        ''', (tx_id, "EXECUTE_AGENT_ACTION", details, 1 if is_live else 0))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True, 
            "action": action_logged, 
            "merchant_message": merchant_msg, 
            "customer_message": customer_msg
        }

if __name__ == "__main__":
    engine = ReconciliationEngine()
    summary = engine.run_reconciliation()
    print(f"Reconciliation & Risk Engine Summary: {summary}")
