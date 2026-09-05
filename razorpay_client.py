import os
import razorpay
import random
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import get_db

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_dummy")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "dummy_secret")


class RazorpayGenerator:
    def __init__(self):
        try:
            self.client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        except Exception as e:
            print(f"Razorpay Client Init Warning: {e}")
            self.client = None

    def generate_batch(self, count=10, session_id: str = "default"):
        """
        Generates a batch of test transactions tagged with session_id for tenant isolation.
        """
        conn = get_db()
        cursor = conn.cursor()

        scenarios = [
            "NORMAL_SETTLED",
            "DECLINED_PAYMENT",
            "DELAYED_SETTLEMENT",
            "STUCK_REFUND",
            "INCENTIVE_ANOMALY",
            "PROMISE_TO_PAY",
            "SUBSCRIPTION_PAYMENT_FAILED",
            "TAX_MISMATCH",
            "DUPLICATE_CHARGE",
            "PAYMENT_CAPTURED_NOT_SETTLED"
        ]

        # Always run all 10 scenarios in a single batch
        count = len(scenarios)

        batch_results = []
        customers = ["cust_101", "cust_102", "cust_103", "cust_104", "cust_105"]

        for i in range(count):
            scenario = scenarios[i % len(scenarios)]
            tx_id = f"tx_live_{random.randint(10000, 99999)}"
            customer_id = random.choice(customers)
            amount_rupees = random.choice([500, 1200, 2500, 4999, 8500])
            amount_paise = amount_rupees * 100

            order_id = f"order_rzp_{random.randint(100, 999)}"
            payment_id = f"pay_rzp_{random.randint(100, 999)}"
            refund_id = None
            settlement_id = None
            is_live_api = False
            due_date = None
            tax_mismatch = False
            confidence_note = "Generated initial ledger record."

            if self.client and not RAZORPAY_KEY_ID.startswith("rzp_test_dummy"):
                try:
                    order_data = {"amount": amount_paise, "currency": "INR", "receipt": f"receipt_{tx_id}"}
                    rzp_order = self.client.order.create(data=order_data)
                    order_id = rzp_order.get("id", order_id)
                    is_live_api = True
                except Exception as e:
                    print(f"Razorpay API Note: {e}")

            status = "Pending"
            failure_reason = None
            flagged = False
            flag_reason = None
            action_taken = "None"
            fee_breakdown = None

            if scenario == "NORMAL_SETTLED":
                status = "Settled"
                settlement_id = f"set_{random.randint(1000, 9999)}"
                gw_fee = round(amount_rupees * 0.02, 2)
                bank_fee = round(amount_rupees * 0.005, 2)
                gst = round((gw_fee + bank_fee) * 0.18, 2)
                net_settled = round(amount_rupees - (gw_fee + bank_fee + gst), 2)
                fee_breakdown = json.dumps({
                    "gross_amount": amount_rupees,
                    "gateway_fee": gw_fee,
                    "bank_fee": bank_fee,
                    "gst": gst,
                    "net_settled": net_settled
                })
                action_taken = "Reconciled & Settled Automatically"
                confidence_note = "Auto-settled with 100% confidence matching bank ledger."

            elif scenario == "DECLINED_PAYMENT":
                status = "Mismatched"
                failure_reason = "PAYMENT_DECLINED_BANK"
                action_taken = "Flagged: Payment Declined by Issuing Bank"

            elif scenario == "DELAYED_SETTLEMENT":
                status = "Mismatched"
                failure_reason = "SETTLEMENT_DELAYED_KYC"
                action_taken = "Pending Recovery: Retry Settlement Webhook"

            elif scenario == "STUCK_REFUND":
                status = "Mismatched"
                refund_id = f"rfnd_{random.randint(1000, 9999)}"
                failure_reason = "REFUND_STUCK_GATEWAY"
                action_taken = "Pending Recovery: Re-trigger Refund API"

            elif scenario == "INCENTIVE_ANOMALY":
                status = "Flagged"
                failure_reason = "HIGH_INCENTIVE_OFFER"
                flagged = True
                flag_reason = "Requested retry incentive (Rs.250 waiver) exceeds threshold for customer tier."
                action_taken = "Paused for Human Approval"

            elif scenario == "PROMISE_TO_PAY":
                status = "Mismatched"
                failure_reason = "PROMISE_TO_PAY_PENDING"
                due_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
                action_taken = "Tracking Payment Commitment"

            elif scenario == "SUBSCRIPTION_PAYMENT_FAILED":
                status = "Mismatched"
                failure_reason = "SUBSCRIPTION_AUTOPAY_FAILED"
                action_taken = "Pending Recovery: Escalation Ladder Initiated"

            elif scenario == "TAX_MISMATCH":
                status = "Mismatched"
                failure_reason = "TAX_CALCULATION_DISCREPANCY"
                tax_mismatch = True
                gw_fee = round(amount_rupees * 0.02, 2)
                bank_fee = round(amount_rupees * 0.005, 2)
                gst = 5.00  # Intentionally wrong
                net_settled = round(amount_rupees - (gw_fee + bank_fee + gst), 2)
                fee_breakdown = json.dumps({
                    "gross_amount": amount_rupees,
                    "gateway_fee": gw_fee,
                    "bank_fee": bank_fee,
                    "gst": gst,
                    "net_settled": net_settled
                })
                action_taken = "Flagged: Tax Line Discrepancy"

            elif scenario == "DUPLICATE_CHARGE":
                status = "Mismatched"
                customer_id = "cust_101"
                amount_rupees = 2500
                failure_reason = "DUPLICATE_CHARGE_SUSPECTED"
                action_taken = "Flagged: Potential Duplicate Charge"

            elif scenario == "PAYMENT_CAPTURED_NOT_SETTLED":
                status = "Mismatched"
                failure_reason = "PAYMENT_CAPTURED_NOT_SETTLED"
                settlement_id = None
                action_taken = "Pending Recovery: Missing Settlement"

            cursor.execute('''
                INSERT OR REPLACE INTO transactions (
                    id, session_id, customer_id, amount, currency, status,
                    payment_id, order_id, refund_id, settlement_id,
                    failure_reason, fee_breakdown, action_taken,
                    flagged, flag_reason, due_date, tax_mismatch,
                    confidence_note, is_live_api_call, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tx_id, session_id, customer_id, amount_rupees, "INR", status,
                payment_id, order_id, refund_id, settlement_id,
                failure_reason, fee_breakdown, action_taken,
                flagged, flag_reason, due_date, tax_mismatch,
                confidence_note, is_live_api,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            cursor.execute('''
                INSERT INTO audit_log (session_id, transaction_id, action, details, is_live_api_call)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                session_id,
                tx_id,
                "TRANSACTION_GENERATED",
                f"Generated scenario: {scenario} for {customer_id} (Amount: Rs.{amount_rupees})",
                is_live_api
            ))

            batch_results.append({
                "id": tx_id,
                "customer_id": customer_id,
                "scenario": scenario,
                "amount": amount_rupees,
                "status": status
            })

        conn.commit()
        conn.close()
        return batch_results


if __name__ == "__main__":
    generator = RazorpayGenerator()
    results = generator.generate_batch(session_id="test_session")
    print(f"Generated batch with {len(results)} scenarios.")
