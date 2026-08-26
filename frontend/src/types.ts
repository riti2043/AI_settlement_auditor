export interface Transaction {
  id: string;
  customer_id?: string;
  amount: number;
  currency?: string;
  status: string;
  payment_id?: string;
  order_id?: string;
  refund_id?: string;
  settlement_id?: string;
  failure_reason?: string;
  fee_breakdown?: string;
  action_taken?: string;
  flagged?: number;
  flag_reason?: string;
  due_date?: string;
  risk_tier?: string;
  tax_mismatch?: number;
  confidence_note?: string;
  is_live_api_call?: number;
  escalation_step?: number;
  updated_at?: string;
}

export interface FeeBreakdown {
  gross_amount: number;
  gateway_fee: number;
  bank_fee: number;
  gst: number;
  net_settled: number;
}

export interface Metrics {
  total_processed: number;
  mismatches_detected: number;
  amount_recovered: number;
  pending_approval: number;
  trend_warning?: string | null;
}

export interface TxDetail {
  transaction: Transaction;
  fee_breakdown?: FeeBreakdown | null;
  explanation: string;
  delay_prediction: string;
  handoff_summary: string;
}

export interface AuditLogEntry {
  id?: number;
  transaction_id: string;
  action: string;
  details: string;
  is_live_api_call?: number;
  timestamp: string;
}
