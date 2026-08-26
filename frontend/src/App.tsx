import React, { useState, useEffect } from 'react';
import { 
  Play, 
  FileText, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  ShieldCheck, 
  Download, 
  Search, 
  RefreshCw, 
  Activity,
  ArrowRight,
  Info,
  Clock,
  ShieldAlert,
  Check
} from 'lucide-react';
import { Transaction, Metrics, TxDetail, AuditLogEntry } from './types';

const API_BASE = 'http://localhost:8000';

export default function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'detail' | 'flagged' | 'qa' | 'audit'>('overview');
  const [beginnerMode, setBeginnerMode] = useState<boolean>(false);
  const [metrics, setMetrics] = useState<Metrics>({ total_processed: 0, mismatches_detected: 0, amount_recovered: 0, pending_approval: 0 });
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [selectedTxId, setSelectedTxId] = useState<string>('');
  const [txDetail, setTxDetail] = useState<TxDetail | null>(null);
  const [qaQuery, setQaQuery] = useState<string>('');
  const [qaAnswer, setQaAnswer] = useState<string>('');
  const [execReport, setExecReport] = useState<string>('');
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [loadingBatch, setLoadingBatch] = useState<boolean>(false);
  const [loadingReport, setLoadingReport] = useState<boolean>(false);
  const [loadingQA, setLoadingQA] = useState<boolean>(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/transactions`);
      const data = await res.json();
      setMetrics(data.metrics || {});
      setTransactions(data.transactions || []);
      if (data.transactions && data.transactions.length > 0 && !selectedTxId) {
        setSelectedTxId(data.transactions[0].id);
      }
    } catch (err) {
      console.error('API Error:', err);
    }
  };

  const fetchTxDetail = async (txId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/transaction/${txId}?beginner_mode=${beginnerMode}`);
      const data = await res.json();
      setTxDetail(data);
    } catch (err) {
      console.error('Tx Detail Error:', err);
    }
  };

  useEffect(() => {
    if (selectedTxId) {
      fetchTxDetail(selectedTxId);
    }
  }, [selectedTxId, beginnerMode]);

  const handleRunBatch = async () => {
    setLoadingBatch(true);
    try {
      await fetch(`${API_BASE}/api/batch/run`, { method: 'POST' });
      await fetchData();
    } catch (err) {
      console.error('Batch Run Error:', err);
    } finally {
      setLoadingBatch(false);
    }
  };

  const handleGenerateReport = async () => {
    setLoadingReport(true);
    try {
      const res = await fetch(`${API_BASE}/api/report`);
      const data = await res.json();
      setExecReport(data.report);
    } catch (err) {
      console.error('Report Error:', err);
    } finally {
      setLoadingReport(false);
    }
  };

  const handleQASubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!qaQuery.trim()) return;
    setLoadingQA(true);
    try {
      const res = await fetch(`${API_BASE}/api/qa`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: qaQuery })
      });
      const data = await res.json();
      setQaAnswer(data.answer);
    } catch (err) {
      console.error('QA Error:', err);
    } finally {
      setLoadingQA(false);
    }
  };

  const handleApprove = async (txId: string, decision: string) => {
    try {
      await fetch(`${API_BASE}/api/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tx_id: txId, decision })
      });
      fetchData();
    } catch (err) {
      console.error('Approval Error:', err);
    }
  };

  const fetchAuditLog = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/audit-log`);
      const data = await res.json();
      setAuditLog(data.audit_log || []);
    } catch (err) {
      console.error('Audit Log Error:', err);
    }
  };

  useEffect(() => {
    if (activeTab === 'audit') {
      fetchAuditLog();
    }
  }, [activeTab]);

  const renderBadge = (status: string) => {
    const st = String(status || '').trim();
    if (st === 'Settled') return <span className="pill badge-settled">Settled</span>;
    if (st === 'Recovered') return <span className="pill badge-recovered">Recovered</span>;
    if (st === 'Flagged') return <span className="pill badge-flagged">Flagged</span>;
    if (st === 'BROKEN_PROMISE') return <span className="pill badge-mismatched">Broken Promise</span>;
    return <span className="pill badge-mismatched">Mismatched</span>;
  };

  const renderApiTag = (isLive?: number) => {
    return isLive ? <span className="badge-live">Live API</span> : <span className="badge-sim">Simulated</span>;
  };

  const flaggedTxs = transactions.filter(t => t.flagged === 1);

  return (
    <div className="max-w-7xl mx-auto px-8 pb-32">
      {/* --- TOP NAVBAR --- */}
      <div className="py-6 border-b border-[rgba(255,255,255,0.08)] flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#C9A227] flex items-center justify-center text-[#000000] font-bold text-lg">
            <ShieldAlert className="w-5 h-5 stroke-[2.5]" />
          </div>
          <div>
            <div className="text-lg font-bold text-[#FFFFFF] tracking-tight leading-none">AI Settlement Auditor</div>
            <div className="text-xs text-[#71717A] mt-1 font-mono">Razorpay Builder Program</div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#121215] border border-[rgba(255,255,255,0.08)] text-xs text-[#A1A1AA]">
            <span className="w-2 h-2 rounded-full bg-[#22C55E] animate-pulse"></span>
            <span>Razorpay Sandbox Connected</span>
          </div>

          <label className="flex items-center gap-2 text-xs text-[#A1A1AA] cursor-pointer select-none">
            <input
              type="checkbox"
              checked={beginnerMode}
              onChange={(e) => setBeginnerMode(e.target.checked)}
              className="rounded border-[rgba(255,255,255,0.15)] accent-[#C9A227]"
            />
            <span>Explain Like I'm New Here</span>
          </label>

          <button className="btn-gold-primary" onClick={handleRunBatch} disabled={loadingBatch}>
            {loadingBatch ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
            <span>{loadingBatch ? 'Running...' : 'Run New Batch'}</span>
          </button>
        </div>
      </div>

      {/* --- RAPPID-STYLE HERO SECTION (Left-Aligned Headline + Stats Panel) --- */}
      <div className="pt-16 pb-16 grid grid-cols-12 gap-12 items-center">
        {/* Left Column: Bold Headline & CTA */}
        <div className="col-span-7 space-y-6">
          <h1 className="text-[52px] font-extrabold font-display text-[#FFFFFF] tracking-[-0.03em] leading-[1.08]">
            The payment platform <br />
            that recovers your money.
          </h1>
          <p className="text-lg text-[#A1A1AA] font-normal leading-relaxed max-w-xl">
            Autonomous multi-source reconciliation, plain-English failure analysis, and bounded AI recovery for Razorpay merchant settlements.
          </p>

          <div className="flex items-center gap-4 pt-2">
            <button className="btn-gold-primary" onClick={handleRunBatch} disabled={loadingBatch}>
              {loadingBatch ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>{loadingBatch ? 'Executing Pipeline...' : 'Run New Batch'}</span>
            </button>
            <button className="btn-dark-secondary" onClick={handleGenerateReport} disabled={loadingReport}>
              <FileText className="w-4 h-4 text-[#C9A227]" />
              <span>{loadingReport ? 'Generating Report...' : 'Executive Summary'}</span>
            </button>
          </div>

          {/* Key Feature Bullets */}
          <div className="grid grid-cols-2 gap-4 pt-6 text-xs text-[#A1A1AA]">
            <div className="flex items-center gap-2">
              <Check className="w-4 h-4 text-[#C9A227]" />
              <span>Multi-Source Ledger Audit</span>
            </div>
            <div className="flex items-center gap-2">
              <Check className="w-4 h-4 text-[#C9A227]" />
              <span>Groq Llama 3.1 Plain English</span>
            </div>
            <div className="flex items-center gap-2">
              <Check className="w-4 h-4 text-[#C9A227]" />
              <span>Fair Incentive Safety Gate</span>
            </div>
            <div className="flex items-center gap-2">
              <Check className="w-4 h-4 text-[#C9A227]" />
              <span>100% Deterministic Recovery</span>
            </div>
          </div>
        </div>

        {/* Right Column: Hero Stats Card (Rappid Style) */}
        <div className="col-span-5 space-y-4">
          <div className="card-container p-8 space-y-6 border border-[rgba(255,255,255,0.12)]">
            <div className="text-xs font-semibold text-[#C9A227] uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#C9A227]"></span>
              <span>Total Recovered Revenue</span>
            </div>
            <div className="text-[44px] font-bold text-[#C9A227] font-mono tracking-tight leading-none">
              ₹{(metrics.amount_recovered || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <p className="text-xs text-[#71717A]">
              Spent 0 seconds manual auditing across active merchant settlement batches.
            </p>
            <div className="border-t border-[rgba(255,255,255,0.08)] pt-4 grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-xs text-[#71717A] uppercase font-mono">Processed</div>
                <div className="text-xl font-bold text-[#FFFFFF] font-mono mt-1">{metrics.total_processed || 0}</div>
              </div>
              <div>
                <div className="text-xs text-[#71717A] uppercase font-mono">Mismatches</div>
                <div className="text-xl font-bold text-[#FFFFFF] font-mono mt-1">{metrics.mismatches_detected || 0}</div>
              </div>
              <div>
                <div className="text-xs text-[#71717A] uppercase font-mono">Pending</div>
                <div className="text-xl font-bold text-[#FFFFFF] font-mono mt-1">{metrics.pending_approval || 0}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Executive Report Card */}
      {execReport && (
        <div className="card-container p-6 mb-10 border-l-4 border-l-[#C9A227]">
          <h3 className="text-sm font-semibold text-[#C9A227] mb-2 flex items-center gap-2">
            <FileText className="w-4 h-4" /> Executive Batch Summary Report (Groq Llama 3.1)
          </h3>
          <p className="text-sm text-[#FFFFFF] leading-relaxed font-normal">{execReport}</p>
        </div>
      )}

      {/* Anomaly Trend Warning Banner */}
      {metrics.trend_warning && (
        <div className="trend-alert flex items-center gap-3 mb-10">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{metrics.trend_warning}</span>
        </div>
      )}

      {/* --- DASHBOARD TAB WORKSPACE --- */}
      <div className="flex gap-4 border-b border-[rgba(255,255,255,0.08)] mb-8">
        <button 
          className={`px-6 py-3 text-sm font-semibold transition-all duration-150 border-b-2 ${activeTab === 'overview' ? 'border-[#C9A227] text-[#C9A227] bg-[#C9A227]/5 rounded-t-lg' : 'border-transparent text-[#A1A1AA] hover:text-[#FFFFFF]'}`} 
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button 
          className={`px-6 py-3 text-sm font-semibold transition-all duration-150 border-b-2 ${activeTab === 'detail' ? 'border-[#C9A227] text-[#C9A227] bg-[#C9A227]/5 rounded-t-lg' : 'border-transparent text-[#A1A1AA] hover:text-[#FFFFFF]'}`} 
          onClick={() => setActiveTab('detail')}
        >
          Transaction Detail
        </button>
        <button 
          className={`px-6 py-3 text-sm font-semibold transition-all duration-150 border-b-2 ${activeTab === 'flagged' ? 'border-[#C9A227] text-[#C9A227] bg-[#C9A227]/5 rounded-t-lg' : 'border-transparent text-[#A1A1AA] hover:text-[#FFFFFF]'}`} 
          onClick={() => setActiveTab('flagged')}
        >
          Flagged Queue {flaggedTxs.length > 0 && <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-[#F59E0B]/20 text-[#F59E0B] font-mono">{flaggedTxs.length}</span>}
        </button>
        <button 
          className={`px-6 py-3 text-sm font-semibold transition-all duration-150 border-b-2 ${activeTab === 'qa' ? 'border-[#C9A227] text-[#C9A227] bg-[#C9A227]/5 rounded-t-lg' : 'border-transparent text-[#A1A1AA] hover:text-[#FFFFFF]'}`} 
          onClick={() => setActiveTab('qa')}
        >
          Ask the Auditor (Q&A)
        </button>
        <button 
          className={`px-6 py-3 text-sm font-semibold transition-all duration-150 border-b-2 ${activeTab === 'audit' ? 'border-[#C9A227] text-[#C9A227] bg-[#C9A227]/5 rounded-t-lg' : 'border-transparent text-[#A1A1AA] hover:text-[#FFFFFF]'}`} 
          onClick={() => setActiveTab('audit')}
        >
          Audit Log
        </button>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="card-container overflow-hidden">
            {loadingBatch ? (
              <div className="p-8 space-y-4">
                <div className="skeleton h-8 w-full"></div>
                <div className="skeleton h-8 w-full"></div>
                <div className="skeleton h-8 w-full"></div>
              </div>
            ) : transactions.length === 0 ? (
              <div className="text-center text-[#71717A] py-16">
                <Info className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm font-normal">No transactions detected. Click "Run New Batch" to trigger live API audit.</p>
              </div>
            ) : (
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Transaction ID</th>
                    <th>Customer (Risk)</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Type</th>
                    <th>Action Taken</th>
                    <th>Last Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map(t => (
                    <tr key={t.id}>
                      <td className="font-mono text-[#C9A227] font-medium">{t.id}</td>
                      <td className="text-xs text-[#A1A1AA] font-mono">
                        {t.customer_id || 'cust_101'} ({t.risk_tier || 'Low'} Risk)
                      </td>
                      <td className="font-mono font-medium text-[#FFFFFF]">₹{Number(t.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                      <td>{renderBadge(t.status)}</td>
                      <td>{renderApiTag(t.is_live_api_call)}</td>
                      <td className="text-[#A1A1AA] text-sm font-normal">
                        {t.action_taken}
                        {t.tax_mismatch === 1 && <span className="text-[#EF4444] font-medium ml-2">[GST Discrepancy]</span>}
                      </td>
                      <td className="text-[#71717A] text-xs font-mono">{t.updated_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: TRANSACTION DETAIL */}
      {activeTab === 'detail' && (
        <div className="space-y-8">
          <div className="flex items-center gap-3">
            <label className="text-sm text-[#A1A1AA] font-normal">Select Transaction ID:</label>
            <select
              value={selectedTxId}
              onChange={(e) => setSelectedTxId(e.target.value)}
              className="bg-[#121215] text-[#FFFFFF] border border-[rgba(255,255,255,0.15)] px-4 py-2.5 rounded-xl text-sm font-mono focus:outline-none focus:border-[#C9A227]"
            >
              {transactions.map(t => (
                <option key={t.id} value={t.id}>{t.id} ({t.status})</option>
              ))}
            </select>
          </div>

          {txDetail && (
            <div className="grid grid-cols-2 gap-8">
              {/* Left Column: Fee Breakdown */}
              <div className="card-container p-8 space-y-6">
                <h3 className="text-[16px] font-semibold text-[#FFFFFF] pb-4 border-b border-[rgba(255,255,255,0.08)] flex items-center gap-2">
                  <Activity className="w-4 h-4 text-[#C9A227]" /> Fee Breakdown & Multi-Source Audit
                </h3>
                {txDetail.fee_breakdown ? (
                  <div className="space-y-3 text-sm">
                    <div className="fee-row">
                      <span className="fee-label">Gross Amount</span>
                      <span className="fee-value font-mono">₹{Number(txDetail.fee_breakdown.gross_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="fee-row">
                      <span className="fee-label">Gateway Fee (2.0%)</span>
                      <span className="fee-deduction font-mono">- ₹{Number(txDetail.fee_breakdown.gateway_fee).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="fee-row">
                      <span className="fee-label">Bank Fee (0.5%)</span>
                      <span className="fee-deduction font-mono">- ₹{Number(txDetail.fee_breakdown.bank_fee).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="fee-row">
                      <span className="fee-label">GST (18.0%)</span>
                      <span className="fee-deduction font-mono">- ₹{Number(txDetail.fee_breakdown.gst).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="fee-row pt-4">
                      <span className="text-[#C9A227] font-semibold">Net Settled Amount</span>
                      <span className="fee-net font-mono">₹{Number(txDetail.fee_breakdown.net_settled).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    </div>
                    {txDetail.transaction.tax_mismatch === 1 && (
                      <div className="text-[#EF4444] text-xs font-normal pt-2 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                        <span>Tax-Line Matcher Warning: GST deviates from standard 18% gateway fee rate.</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-[#A1A1AA] font-normal">Fee breakdown unavailable for un-settled or declined payments.</p>
                )}
              </div>

              {/* Right Column: Rationale & Actions */}
              <div className="space-y-8">
                <div className="card-container p-8 space-y-5">
                  <h3 className="text-[16px] font-semibold text-[#FFFFFF] pb-4 border-b border-[rgba(255,255,255,0.08)] flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-[#22C55E]" /> Agent Analysis & Escalation Ladder
                  </h3>
                  <div>
                    <div className="text-[12px] font-medium text-[#71717A] uppercase tracking-[0.04em] mb-1">Failure Cause</div>
                    <div className="font-mono text-sm text-[#EF4444]">{txDetail.transaction.failure_reason || 'N/A (Standard Processing)'}</div>
                  </div>
                  <div>
                    <div className="text-[12px] font-medium text-[#71717A] uppercase tracking-[0.04em] mb-1">LLM Cause Analysis</div>
                    <div className="text-sm text-[#A1A1AA] font-normal leading-relaxed">{txDetail.explanation}</div>
                  </div>
                  <div>
                    <div className="text-[12px] font-medium text-[#71717A] uppercase tracking-[0.04em] mb-1">Settlement Delay Predictor</div>
                    <div className="text-sm text-[#C9A227] font-medium flex items-center gap-2 font-mono">
                      <Clock className="w-4 h-4" /> {txDetail.delay_prediction}
                    </div>
                  </div>
                  <div>
                    <div className="text-[12px] font-medium text-[#71717A] uppercase tracking-[0.04em] mb-1">Confidence & Safety Score</div>
                    <div className="text-sm text-[#22C55E] font-medium flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4" /> {txDetail.transaction.confidence_note || 'Rule-based safety check executed.'}
                    </div>
                  </div>
                  <div>
                    <div className="text-[12px] font-medium text-[#71717A] uppercase tracking-[0.04em] mb-1">Action Executed</div>
                    <div className="text-sm text-[#FFFFFF] font-normal flex items-center gap-2">
                      <span>{txDetail.transaction.action_taken}</span>
                      {renderApiTag(txDetail.transaction.is_live_api_call)}
                    </div>
                  </div>
                </div>

                <div className="card-container p-8">
                  <h3 className="text-[16px] font-semibold text-[#FFFFFF] pb-4 border-b border-[rgba(255,255,255,0.08)] mb-3 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-[#C9A227]" /> Handoff Summary (For Support Ticket)
                  </h3>
                  <p className="text-sm text-[#A1A1AA] font-normal leading-relaxed">{txDetail.handoff_summary}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: FLAGGED FOR APPROVAL */}
      {activeTab === 'flagged' && (
        <div className="space-y-6">
          {flaggedTxs.length === 0 ? (
            <div className="card-container text-center text-[#A1A1AA] py-16">
              <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-[#22C55E] opacity-80" />
              <p className="text-sm font-normal">No transactions currently flagged for human review. All recovery actions within safety bounds.</p>
            </div>
          ) : (
            flaggedTxs.map(t => (
              <div key={t.id} className="card-container p-8 space-y-4">
                <div className="flex justify-between items-center">
                  <div className="text-sm text-[#FFFFFF] font-normal">
                    Transaction: <span className="font-mono text-[#C9A227]">{t.id}</span> | Customer: <strong>{t.customer_id || 'cust_101'}</strong> ({t.risk_tier || 'Low'} Risk)
                  </div>
                  <div className="text-lg font-bold font-mono text-[#FFFFFF]">₹{Number(t.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
                </div>
                <div className="bg-[rgba(245,158,11,0.08)] border-l-4 border-[#F59E0B] p-4 rounded-r-lg text-xs font-normal text-[#F59E0B]">
                  <strong>Fair Incentive Gate Reason:</strong> {t.flag_reason}
                </div>
                <div className="flex gap-4 pt-2">
                  <button className="btn-gold-primary text-xs" onClick={() => handleApprove(t.id, 'APPROVE')}>
                    <CheckCircle2 className="w-4 h-4" /> Approve Incentive
                  </button>
                  <button className="btn-dark-secondary text-xs" onClick={() => handleApprove(t.id, 'REJECT')}>
                    <XCircle className="w-4 h-4 text-[#EF4444]" /> Reject Incentive
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* TAB 4: ASK THE AUDITOR (Q&A) */}
      {activeTab === 'qa' && (
        <div className="space-y-8">
          <div className="card-container p-8">
            <h3 className="text-[16px] font-semibold text-[#FFFFFF] mb-2 flex items-center gap-2">
              <Search className="w-4 h-4 text-[#C9A227]" /> Ask the Auditor (Groq Natural Language Q&A)
            </h3>
            <p className="text-xs text-[#A1A1AA] mb-6 font-normal">Ask any question about active batch statistics, specific transaction IDs, risk tiers, or mismatch recoveries.</p>
            <form onSubmit={handleQASubmit} className="flex gap-4">
              <input
                type="text"
                placeholder="e.g. 'What happened to transaction tx_live_...?' or 'Summarize high risk customers'"
                value={qaQuery}
                onChange={(e) => setQaQuery(e.target.value)}
                className="flex-1 bg-[#000000] text-[#FFFFFF] border border-[rgba(255,255,255,0.15)] px-5 py-3 rounded-xl text-sm font-normal focus:outline-none focus:border-[#C9A227]"
              />
              <button type="submit" className="btn-gold-primary" disabled={loadingQA}>
                {loadingQA ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                <span>Submit Question</span>
              </button>
            </form>
          </div>

          {qaAnswer && (
            <div className="card-container p-8 border-l-4 border-l-[#C9A227] space-y-2">
              <div className="text-xs font-medium text-[#C9A227] uppercase tracking-[0.04em]">Auditor Response (Groq Llama 3.1):</div>
              <p className="text-sm text-[#FFFFFF] font-normal leading-relaxed">{qaAnswer}</p>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: AUDIT LOG */}
      {activeTab === 'audit' && (
        <div className="space-y-6">
          <div className="flex justify-start">
            <a href={`${API_BASE}/api/export-csv`} download="audit_log.csv" className="btn-dark-secondary text-xs flex items-center gap-2">
              <Download className="w-4 h-4 text-[#C9A227]" /> Export Audit Trail (CSV)
            </a>
          </div>

          <div className="card-container overflow-hidden">
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Transaction ID</th>
                  <th>Action Executed</th>
                  <th>Type</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {auditLog.map((a, idx) => (
                  <tr key={a.id || idx}>
                    <td className="text-xs text-[#71717A] font-mono">{a.timestamp}</td>
                    <td className="font-mono text-[#C9A227] font-medium">{a.transaction_id}</td>
                    <td className="text-xs font-medium text-[#FFFFFF]">{a.action}</td>
                    <td>{renderApiTag(a.is_live_api_call)}</td>
                    <td className="text-xs text-[#A1A1AA] font-normal">{a.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="app-footer">
        Running on Razorpay test-mode data. No real transactions are processed.
      </div>
    </div>
  );
}
