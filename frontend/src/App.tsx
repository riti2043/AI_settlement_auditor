import React, { useState, useEffect } from 'react';
import { 
  Play, 
  FileText, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  ShieldCheck, 
  Download, 
  RefreshCw, 
  Activity,
  ArrowRight,
  ShieldAlert,
  MessageCircle,
  X,
  ChevronRight
} from 'lucide-react';
import { Transaction, Metrics, TxDetail, AuditLogEntry } from './types';

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'https://ai-settlement-auditor.onrender.com';

// Persistent session ID — one per browser tab / localStorage slot
function getOrCreateSessionId(): string {
  let sid = localStorage.getItem('aisa_session_id');
  if (!sid) {
    sid = crypto.randomUUID();
    localStorage.setItem('aisa_session_id', sid);
  }
  return sid;
}

const SESSION_ID = getOrCreateSessionId();

// Wrapper so every fetch call includes the session header automatically
function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  return window.fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Session-ID': SESSION_ID,
      ...(options.headers || {})
    }
  });
}


const PIPELINE_STEPS = [
  { id: 'api', name: 'Razorpay API', desc: 'Pulls raw transaction and settlement data directly from Razorpay.' },
  { id: 'recon', name: 'Reconciliation', desc: 'Compares gateway data against internal merchant ledger expectations.' },
  { id: 'anomaly', name: 'Anomaly Detection', desc: 'Identifies missing funds, fee mismatches, or stuck refunds.' },
  { id: 'llm', name: 'LLM Analysis', desc: 'Groq translates complex failure codes into plain English context.' },
  { id: 'rules', name: 'Rules Engine', desc: 'Determines bounded recovery actions based on deterministic policies.' },
  { id: 'gate', name: 'Human Gate', desc: 'Pauses out-of-bounds or high-risk actions for manual merchant approval.' },
  { id: 'audit', name: 'Audit Log', desc: 'Records every API call, AI explanation, and human decision immutably.' }
];

export default function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'flagged' | 'audit'>('overview');
  const [activePipelineStep, setActivePipelineStep] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<Metrics>({ total_processed: 0, mismatches_detected: 0, amount_recovered: 0, pending_approval: 0 });
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [loadingBatch, setLoadingBatch] = useState<boolean>(false);
  const [batchResult, setBatchResult] = useState<any>(null);
  
  // Modal state
  const [selectedTx, setSelectedTx] = useState<Transaction | null>(null);
  const [txDetail, setTxDetail] = useState<TxDetail | null>(null);
  const [loadingTx, setLoadingTx] = useState<boolean>(false);
  
  const [executing, setExecuting] = useState<boolean>(false);
  const [execResult, setExecResult] = useState<any>(null);

  // Executive Summary Modal state
  const [summaryModalOpen, setSummaryModalOpen] = useState(false);
  const [summaryText, setSummaryText] = useState<string>('');
  const [loadingSummary, setLoadingSummary] = useState(false);

  const openExecutiveSummaryModal = async () => {
    setSummaryModalOpen(true);
    setLoadingSummary(true);
    try {
      const res = await apiFetch(`/api/report`);
      const data = await res.json();
      if (data && data.report) {
        setSummaryText(data.report);
      }
    } catch (err) {
      console.error('Error fetching executive summary:', err);
    } finally {
      setLoadingSummary(false);
    }
  };

  // QA floating chat
  const [qaOpen, setQaOpen] = useState(false);
  const [qaQuery, setQaQuery] = useState('');
  const [qaAnswer, setQaAnswer] = useState('');
  const [loadingQA, setLoadingQA] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const res = await apiFetch(`/api/transactions`);
      const data = await res.json();
      setMetrics(data.metrics || {});
      setTransactions(data.transactions || []);
    } catch (err) {
      console.error('API Error:', err);
    }
  };

  const fetchAuditLog = async () => {
    try {
      const res = await apiFetch(`/api/audit-log`);
      const data = await res.json();
      setAuditLog(data.audit_log || []);
    } catch (err) {
      console.error('Audit Log Error:', err);
    }
  };

  useEffect(() => {
    if (activeTab === 'audit') fetchAuditLog();
  }, [activeTab]);

  const handleRunBatch = async () => {
    setLoadingBatch(true);
    setBatchResult(null);
    try {
      const res = await apiFetch(`/api/batch/run`, { method: 'POST' });
      const data = await res.json();
      setBatchResult(data);
      await fetchData();
    } catch (err) {
      console.error('Batch Run Error:', err);
    } finally {
      setLoadingBatch(false);
    }
  };

  const openTxModal = async (tx: Transaction) => {
    setSelectedTx(tx);
    setTxDetail(null);
    setExecResult(null);
    setLoadingTx(true);
    try {
      const res = await apiFetch(`/api/transaction/${tx.id}`);
      const data = await res.json();
      setTxDetail(data);
    } catch (err) {
      console.error('Tx Detail Error:', err);
    } finally {
      setLoadingTx(false);
    }
  };

  const closeTxModal = () => {
    setSelectedTx(null);
    setTxDetail(null);
    setExecResult(null);
  };

  const executeAction = async (cause: string) => {
    if (!selectedTx) return;
    setExecuting(true);
    try {
      const res = await apiFetch(`/api/transaction/${selectedTx.id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cause })
      });
      const data = await res.json();
      setExecResult(data);
      fetchData(); // Refresh underlying table
    } catch (err) {
      console.error('Execute Error:', err);
    } finally {
      setExecuting(false);
    }
  };

  const handleApprove = async (txId: string, decision: string) => {
    try {
      await apiFetch(`/api/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tx_id: txId, decision })
      });
      fetchData();
      closeTxModal();
    } catch (err) {
      console.error('Approval Error:', err);
    }
  };

  const handleQASubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!qaQuery.trim()) return;
    setLoadingQA(true);
    try {
      const res = await apiFetch(`/api/qa`, {
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

  const getRazorpayStatusBadge = (status: string, reason?: string) => {
    const st = String(status || '').trim();
    if (st === 'Settled') {
      return (
        <span className="text-green-400 font-mono text-xs uppercase tracking-wider font-bold">captured · settled</span>
      );
    }
    if (st === 'Recovered') {
      return (
        <span className="text-emerald-400 font-mono text-xs uppercase tracking-wider font-bold">recovered</span>
      );
    }
    if (st === 'Flagged') {
      return (
        <span className="text-amber-400 font-mono text-xs uppercase tracking-wider font-bold animate-pulse">captured · flagged</span>
      );
    }
    if (st === 'BROKEN_PROMISE') {
      return (
        <span className="text-rose-400 font-mono text-xs uppercase tracking-wider font-bold">breach · escalated</span>
      );
    }
    if (st === 'Mismatched') {
      if (reason === 'PAYMENT_DECLINED_BANK') {
        return (
          <span className="text-red-400 font-mono text-xs uppercase tracking-wider font-bold">failed · mismatch detected</span>
        );
      }
      return (
        <span className="text-[#C9A227] font-mono text-xs uppercase tracking-wider font-bold">authorized · mismatch detected</span>
      );
    }
    return <span className="font-mono text-xs uppercase text-zinc-400 font-bold">{st}</span>;
  };

  const flaggedTxs = transactions.filter(t => t.flagged === 1);

  return (
    <div className="max-w-7xl mx-auto px-8 pb-32">
      {/* --- TOP NAVBAR --- */}
      <div className="py-6 border-b border-[rgba(255,255,255,0.08)] flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#C9A227] flex items-center justify-center text-[#000000] font-bold text-lg">
            <ShieldCheck className="w-5 h-5 stroke-[2.5]" />
          </div>
          <div>
            <div className="text-lg font-bold text-[#FFFFFF] tracking-tight leading-none">AI Settlement Auditor</div>
            <div className="text-xs text-[#71717A] mt-1 font-mono uppercase tracking-widest">Razorpay Open Track</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <a 
            href={`${API_BASE}/api/export-pdf`} 
            download="AI_Settlement_Executive_Report.pdf" 
            className="text-xs text-[#C9A227] hover:text-white transition-colors flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#C9A227]/10 hover:bg-[#C9A227]/20 border border-[#C9A227]/25 font-mono"
            title="Download Official Audit PDF Report"
          >
            <FileText className="w-3.5 h-3.5" /> Executive PDF
          </a>
          <a href={`${API_BASE}/api/export-csv`} download className="text-xs text-[#71717A] hover:text-white transition-colors flex items-center gap-1.5 px-2.5 py-1.5 font-mono">
            <Download className="w-3 h-3" /> Export CSV
          </a>
        </div>
      </div>

      {/* --- HERO SECTION --- */}
      <div className="pt-6 pb-6">
        <div className="grid grid-cols-12 gap-8 items-start mb-6">
          
          {/* Left: Headline block + Features + Run Batch */}
          <div className="col-span-7 space-y-3.5 pr-2">
            <h1 className="font-display text-4xl lg:text-[42px] font-bold text-white leading-[1.08] tracking-[-0.02em]">
              Autonomous Settlement<br />Auditing for Razorpay<br />Merchants.
            </h1>

            {/* 4 Bullet Points - Compact & Tight */}
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 py-0.5">
              <div className="flex items-center gap-2 group">
                <span className="text-[#C9A227] text-xs font-mono font-bold">›</span>
                <span className="text-[#A1A1AA] text-sm font-medium group-hover:text-white transition-colors">Detect mismatches</span>
              </div>
              <div className="flex items-center gap-2 group">
                <span className="text-[#C9A227] text-xs font-mono font-bold">›</span>
                <span className="text-[#A1A1AA] text-sm font-medium group-hover:text-white transition-colors">Explain failures in plain English</span>
              </div>
              <div className="flex items-center gap-2 group">
                <span className="text-[#C9A227] text-xs font-mono font-bold">›</span>
                <span className="text-[#A1A1AA] text-sm font-medium group-hover:text-white transition-colors">Recover amounts within policy bounds</span>
              </div>
              <div className="flex items-center gap-2 group">
                <span className="text-[#C9A227] text-xs font-mono font-bold">›</span>
                <span className="text-[#A1A1AA] text-sm font-medium group-hover:text-white transition-colors">Log every decision for audit</span>
              </div>
            </div>

            {/* Run Batch Box - Tight & Elevated */}
            <div className="border border-[rgba(255,255,255,0.07)] bg-[#0d0d10] rounded-xl p-4 sm:p-5">
              <button
                className="btn-gold-primary mb-2.5 font-display tracking-wide py-2.5 px-5 text-sm"
                onClick={handleRunBatch}
                disabled={loadingBatch}
              >
                {loadingBatch ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
                <span>{loadingBatch ? 'Running Batch...' : 'Run New Batch'}</span>
              </button>
              <p className="text-[12.5px] text-[#71717A] leading-relaxed">
                Running a batch pulls 10 live transactions from the Razorpay test environment, reconciles each against your expected ledger, and dispatches bounded recovery actions for known failure types. Anything out of policy is held for your review before any money moves.
              </p>
            </div>
          </div>

          {/* Right: Stacked Stat cards + Active Exec Summary */}
          <div className="col-span-5 flex flex-col gap-2.5">
            {/* Card 1 */}
            <div className="relative bg-[#0d0d10] border border-[rgba(255,255,255,0.07)] rounded-xl p-3.5 overflow-hidden group hover:border-[rgba(255,255,255,0.14)] transition-colors">
              <div className="absolute top-0 right-0 w-24 h-24 bg-white opacity-[0.02] rounded-bl-full group-hover:scale-110 transition-transform"></div>
              <div className="flex justify-between items-center relative z-10">
                <div className="text-[11px] font-mono text-[#71717A] uppercase tracking-widest">Transactions Audited</div>
                <div className="font-display text-2xl font-bold text-white leading-none">{metrics.total_processed}</div>
              </div>
            </div>

            {/* Card 2 */}
            <div className="relative bg-[#0d0d10] border border-[rgba(201,162,39,0.2)] rounded-xl p-3.5 overflow-hidden group hover:border-[rgba(201,162,39,0.35)] transition-colors">
              <div className="absolute top-0 right-0 w-24 h-24 bg-[#C9A227] opacity-5 rounded-bl-full group-hover:scale-110 transition-transform"></div>
              <div className="flex justify-between items-center relative z-10">
                <div className="text-[11px] font-mono text-[#C9A227] uppercase tracking-widest">Amount Recovered</div>
                <div className="font-display text-2xl font-bold text-[#C9A227] leading-none">
                  ₹{metrics.amount_recovered.toLocaleString('en-IN')}
                </div>
              </div>
            </div>

            {/* Card 3 — clickable */}
            <div
              className="relative bg-[#0d0d10] border border-[rgba(245,158,11,0.2)] rounded-xl p-3.5 overflow-hidden group cursor-pointer hover:border-[rgba(245,158,11,0.4)] transition-colors"
              onClick={() => setActiveTab('flagged')}
            >
              <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500 opacity-5 rounded-bl-full group-hover:scale-110 transition-transform"></div>
              <div className="flex justify-between items-center relative z-10">
                <div className="text-[11px] font-mono text-amber-500 uppercase tracking-widest flex items-center gap-1">
                  Pending Review <ArrowRight className="w-3 h-3" />
                </div>
                <div className="font-display text-2xl font-bold text-amber-400 leading-none">{metrics.pending_approval}</div>
              </div>
            </div>

            {/* Card 4 */}
            <div className="relative bg-[#0d0d10] border border-[rgba(239,68,68,0.15)] rounded-xl p-3.5 overflow-hidden group hover:border-[rgba(239,68,68,0.3)] transition-colors">
              <div className="absolute top-0 right-0 w-24 h-24 bg-rose-500 opacity-5 rounded-bl-full group-hover:scale-110 transition-transform"></div>
              <div className="flex justify-between items-center relative z-10">
                <div className="text-[11px] font-mono text-rose-500 uppercase tracking-widest">Mismatches Detected</div>
                <div className="font-display text-2xl font-bold text-white leading-none">{metrics.mismatches_detected}</div>
              </div>
            </div>

            {/* Executive Summary Active Interactive Card */}
            <div className="relative bg-[#0d0d10] border border-[rgba(255,255,255,0.08)] hover:border-[#C9A227]/40 rounded-xl p-4 transition-all group">
              <div className="flex items-center justify-between mb-2">
                <div className="text-[11px] font-mono text-white uppercase tracking-widest flex items-center gap-1.5 font-bold">
                  <FileText className="w-3.5 h-3.5 text-[#C9A227]" />
                  Executive Summary
                </div>
                <a
                  href={`${API_BASE}/api/export-pdf`}
                  download="AI_Settlement_Executive_Report.pdf"
                  className="inline-flex items-center gap-1 text-[10px] font-mono text-[#C9A227] hover:text-white bg-[#C9A227]/10 hover:bg-[#C9A227]/20 border border-[#C9A227]/30 px-2 py-0.5 rounded transition-colors"
                  title="Direct Download PDF Report"
                >
                  <Download className="w-3 h-3" />
                  PDF
                </a>
              </div>
              
              <p className="text-[12px] text-[#71717A] leading-relaxed mb-3">
                {metrics.total_processed === 0 
                  ? "AI Auditor standing by. Ready for batch ingestion." 
                  : `Audited ${metrics.total_processed} transactions. Detected ${metrics.mismatches_detected} mismatches with ₹${metrics.amount_recovered.toLocaleString('en-IN')} recovered.`}
              </p>

              <div className="flex items-center gap-2 pt-2 border-t border-[rgba(255,255,255,0.06)]">
                <button
                  onClick={openExecutiveSummaryModal}
                  className="flex-1 py-1.5 text-xs font-mono text-white bg-white/5 hover:bg-white/10 rounded-lg border border-white/10 transition-colors text-center"
                >
                  View Summary
                </button>
                <a
                  href={`${API_BASE}/api/export-pdf`}
                  download="AI_Settlement_Executive_Report.pdf"
                  className="flex-1 py-1.5 text-xs font-mono text-black font-bold bg-[#C9A227] hover:bg-[#DEB53A] rounded-lg transition-colors flex items-center justify-center gap-1 text-center"
                >
                  <Download className="w-3 h-3" />
                  Export PDF
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* --- PIPELINE STRIP --- */}
      {metrics.total_processed > 0 && (
        <div className="mb-12">
          <div className="mb-4">
            <h3 className="text-white font-medium mb-1">System Architecture: The 7-Step Pipeline</h3>
            <p className="text-sm text-zinc-400">Click on any stage below to understand how the agent processes transactions from ingestion to final audit. No steps are skipped.</p>
          </div>
          <div className="border border-[rgba(255,255,255,0.08)] rounded-xl bg-[#0a0a0c] p-6 relative">
            <div className="flex items-center justify-between">
              {PIPELINE_STEPS.map((step, index) => (
                <React.Fragment key={step.id}>
                  <div 
                    className={`flex flex-col items-center gap-2 cursor-pointer group flex-1 transition-transform hover:-translate-y-1 ${activePipelineStep === step.id ? 'opacity-100' : 'opacity-70 hover:opacity-100'}`}
                    onClick={() => setActivePipelineStep(activePipelineStep === step.id ? null : step.id)}
                  >
                    <div className={`text-xs font-mono font-bold uppercase text-center px-2 py-1 rounded transition-colors ${activePipelineStep === step.id ? 'bg-[#C9A227] text-black' : 'bg-zinc-900 text-zinc-400 group-hover:text-white'}`}>
                      {step.name}
                    </div>
                  </div>
                  {index < PIPELINE_STEPS.length - 1 && (
                    <div className="text-zinc-700 flex-shrink-0 px-2">
                      <ChevronRight className="w-4 h-4" />
                    </div>
                  )}
                </React.Fragment>
              ))}
            </div>
            
            {activePipelineStep && (
              <div className="mt-6 p-4 bg-[#121215] border border-[#C9A227]/30 rounded-lg text-sm text-zinc-300 animate-in fade-in slide-in-from-top-2">
                <span className="text-[#C9A227] font-bold mr-2">{PIPELINE_STEPS.find(s => s.id === activePipelineStep)?.name}:</span>
                {PIPELINE_STEPS.find(s => s.id === activePipelineStep)?.desc}
              </div>
            )}
          </div>
        </div>
      )}

      {/* --- BATCH RESULT BANNER --- */}
      {batchResult && (
        <div className="mb-8 p-4 bg-emerald-950/30 border border-emerald-900/50 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-3 text-emerald-400 text-sm">
            <CheckCircle2 className="w-5 h-5" />
            <span>
              Batch complete | {batchResult.generated} processed | {batchResult.reconciliation.mismatches} mismatches detected | 
              ₹{batchResult.reconciliation.recovered_amount} recovery actions dispatched.
            </span>
          </div>
          <button className="text-emerald-400 hover:text-white" onClick={() => setBatchResult(null)}><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* --- ALERT CARD --- */}
      {metrics.pending_approval > 0 && activeTab !== 'flagged' && (
        <div className="mb-8 p-4 bg-amber-950/20 border border-amber-900/50 rounded-xl flex items-center justify-between cursor-pointer hover:bg-amber-950/30 transition-colors" onClick={() => setActiveTab('flagged')}>
          <div className="flex items-center gap-3 text-amber-500 text-sm font-medium">
            <AlertTriangle className="w-5 h-5" />
            {metrics.pending_approval} transaction(s) require your review before recovery can proceed
          </div>
          <div className="flex items-center gap-2 text-amber-500 text-xs uppercase tracking-wider font-bold">
            Open Flagged Queue <ArrowRight className="w-3 h-3" />
          </div>
        </div>
      )}

      {/* --- TABS NAVIGATION --- */}
      <div className="flex items-center gap-8 border-b border-[rgba(255,255,255,0.08)] mb-8 px-2">
        <button
          className={`pb-4 text-sm font-medium tracking-wide transition-all border-b-2 ${activeTab === 'overview' ? 'text-[#C9A227] border-[#C9A227]' : 'text-[#71717A] border-transparent hover:text-white'}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          className={`pb-4 text-sm font-medium tracking-wide transition-all border-b-2 flex items-center gap-2 ${activeTab === 'flagged' ? 'text-[#C9A227] border-[#C9A227]' : 'text-[#71717A] border-transparent hover:text-white'}`}
          onClick={() => setActiveTab('flagged')}
        >
          Flagged Queue
          {metrics.pending_approval > 0 && (
            <span className="bg-amber-500 text-black text-[10px] font-bold px-1.5 py-0.5 rounded-full">{metrics.pending_approval}</span>
          )}
        </button>
        <button
          className={`pb-4 text-sm font-medium tracking-wide transition-all border-b-2 ${activeTab === 'audit' ? 'text-[#C9A227] border-[#C9A227]' : 'text-[#71717A] border-transparent hover:text-white'}`}
          onClick={() => setActiveTab('audit')}
        >
          Audit Log
        </button>
      </div>

      {/* --- TAB CONTENT --- */}
      <div className="min-h-[500px]">
        {activeTab === 'overview' && (
          <div className="overflow-x-auto rounded-xl border border-[rgba(255,255,255,0.08)] bg-[#121215]">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)]">
                  <th className="py-4 px-6 text-xs font-mono text-[#71717A] uppercase tracking-wider">Transaction ID</th>
                  <th className="py-4 px-6 text-xs font-mono text-[#71717A] uppercase tracking-wider">Customer</th>
                  <th className="py-4 px-6 text-xs font-mono text-[#71717A] uppercase tracking-wider">Amount</th>
                  <th className="py-4 px-6 text-xs font-mono text-[#71717A] uppercase tracking-wider">Status</th>
                  <th className="py-4 px-6 text-xs font-mono text-[#71717A] uppercase tracking-wider">Failure Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[rgba(255,255,255,0.03)]">
                {transactions.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-[#71717A] text-sm">
                      No transactions found. Run a batch to generate test data.
                    </td>
                  </tr>
                ) : (
                  transactions.map(tx => (
                    <tr key={tx.id} className="hover:bg-[rgba(255,255,255,0.02)] transition-colors cursor-pointer group" onClick={() => openTxModal(tx)}>
                      <td className="py-4 px-6 text-sm font-mono text-[#D4D4D8]">{tx.id}</td>
                      <td className="py-4 px-6 text-sm text-[#A1A1AA]">{tx.customer_id}</td>
                      <td className="py-4 px-6 text-sm text-white font-medium">₹{tx.amount.toLocaleString('en-IN')}</td>
                      <td className="py-4 px-6">
                        {getRazorpayStatusBadge(tx.status, tx.failure_reason)}
                      </td>
                      <td className="py-4 px-6 text-sm text-[#A1A1AA] group-hover:text-white transition-colors">
                        {tx.failure_reason || '--'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'flagged' && (
          <div className="space-y-6">
            {flaggedTxs.length === 0 ? (
              <div className="text-center py-20 text-zinc-500 border border-zinc-800/50 rounded-xl bg-zinc-900/20">
                No transactions currently await human review.
              </div>
            ) : (
              flaggedTxs.map(tx => (
                <div key={tx.id} className="p-6 rounded-xl border border-amber-900/30 bg-[#121215] shadow-lg">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <div className="text-xl font-bold text-white font-display mb-1">₹{tx.amount}</div>
                      <div className="text-sm font-mono text-zinc-500">{tx.id} · {tx.customer_id}</div>
                    </div>
                    {getRazorpayStatusBadge(tx.status, tx.failure_reason)}
                  </div>
                  <div className="p-4 bg-amber-950/20 border border-amber-900/50 rounded-lg mb-6">
                    <div className="text-amber-500 text-sm font-medium mb-2">Consistency Check Flag</div>
                    <div className="text-amber-400/80 text-sm mb-4">{tx.flag_reason}</div>
                    
                    {tx.failure_reason === 'DUPLICATE_CHARGE_SUSPECTED' && (
                      <div className="bg-black/30 p-3 rounded border border-amber-900/30 text-xs font-mono text-zinc-400">
                        <div className="mb-1 text-zinc-300">Context provided for Review:</div>
                        <div className="flex items-center gap-4 mt-2">
                          <div className="flex-1 p-2 bg-zinc-900/50 rounded border border-zinc-800">
                            <span className="text-zinc-500 block mb-1">Previous Charge (Settled)</span>
                            tx_prev_12345<br/>₹{tx.amount}<br/>09:12 AM
                          </div>
                          <div className="text-amber-500">vs</div>
                          <div className="flex-1 p-2 bg-amber-950/30 rounded border border-amber-900/50 text-amber-500">
                            <span className="text-amber-600 block mb-1">Current Charge (Flagged)</span>
                            {tx.id}<br/>₹{tx.amount}<br/>09:15 AM
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {tx.failure_reason === 'HIGH_INCENTIVE_OFFER' && (
                      <div className="bg-black/30 p-3 rounded border border-amber-900/30 text-xs font-mono text-zinc-400">
                        <div className="mb-1 text-zinc-300">Context provided for Review:</div>
                        <ul className="list-disc list-inside mt-2 space-y-1">
                          <li>Customer Tier: Basic</li>
                          <li>Requested Waiver: ₹250</li>
                          <li>Max Threshold for Tier: ₹100</li>
                          <li>Historical Precedent: 0 approvals in last 30 days</li>
                        </ul>
                      </div>
                    )}
                  </div>
                  <div className="flex gap-4">
                    <button className="flex-1 py-2 rounded-lg bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors font-medium text-sm" onClick={() => handleApprove(tx.id, 'APPROVE')}>
                      Approve Action
                    </button>
                    <button className="flex-1 py-2 rounded-lg bg-rose-500/10 text-rose-500 border border-rose-500/20 hover:bg-rose-500/20 transition-colors font-medium text-sm" onClick={() => handleApprove(tx.id, 'REJECT')}>
                      Reject & Escalate
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'audit' && (
          <div className="overflow-x-auto rounded-xl border border-[rgba(255,255,255,0.08)] bg-[#121215]">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)]">
                  <th className="py-4 px-6 text-xs font-mono text-[#71717A] uppercase tracking-wider">Timestamp</th>
                  <th className="py-4 px-6 text-xs font-mono text-[#71717A] uppercase tracking-wider">Transaction</th>
                  <th className="py-4 px-6 text-xs font-mono text-[#71717A] uppercase tracking-wider">Action Category</th>
                  <th className="py-4 px-6 text-xs font-mono text-[#71717A] uppercase tracking-wider">Details</th>
                  <th className="py-4 px-6 text-xs font-mono text-[#71717A] uppercase tracking-wider">Mode</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[rgba(255,255,255,0.03)]">
                {auditLog.map((log, i) => {
                  let badgeClass = "bg-zinc-800 text-zinc-300";
                  if (log.action.includes('GENERATED')) badgeClass = "bg-blue-900/50 text-blue-400";
                  if (log.action.includes('RECOVERY') || log.action.includes('EXECUTE')) badgeClass = "bg-[#C9A227]/20 text-[#C9A227]";
                  if (log.action.includes('HUMAN_APP')) badgeClass = "bg-emerald-900/50 text-emerald-400";
                  if (log.action.includes('HUMAN_REJ')) badgeClass = "bg-rose-900/50 text-rose-400";
                  
                  return (
                    <tr key={i} className="hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                      <td className="py-4 px-6 text-xs font-mono text-[#A1A1AA] whitespace-nowrap">{log.timestamp}</td>
                      <td className="py-4 px-6 text-xs font-mono text-[#D4D4D8]">{log.transaction_id}</td>
                      <td className="py-4 px-6">
                        <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider ${badgeClass}`}>
                          {log.action}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-sm text-[#A1A1AA] max-w-md truncate">{log.details}</td>
                      <td className="py-4 px-6">
                        {log.is_live_api_call === 1 ? (
                          <span className="text-[10px] font-bold text-amber-500 uppercase tracking-widest bg-amber-500/10 px-2 py-1 rounded">Live API</span>
                        ) : (
                          <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest bg-zinc-800 px-2 py-1 rounded">Simulated</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* --- TRANSACTION MODAL --- */}
      {selectedTx && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-[#121215] border border-zinc-800 w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl shadow-2xl flex flex-col">
            
            {/* Header */}
            <div className="flex justify-between items-center p-6 border-b border-zinc-800 bg-[#0a0a0c] sticky top-0 z-10">
              <div>
                <div className="flex items-center gap-4 mb-2">
                  <h2 className="text-2xl font-display font-bold text-white">{selectedTx.id}</h2>
                  <div className="text-xl text-[#C9A227] font-bold">₹{selectedTx.amount}</div>
                </div>
                {getRazorpayStatusBadge(selectedTx.status, selectedTx.failure_reason)}
              </div>
              <button onClick={closeTxModal} className="p-2 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-white transition-colors">
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6 flex-1 space-y-6">
              
              {/* Detection Sentence */}
              <div className="bg-zinc-900/50 p-4 rounded-xl border border-zinc-800">
                <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2">Failure Detected</div>
                <div className="text-zinc-300 text-sm leading-relaxed">
                  {loadingTx ? 'Analyzing with Groq LLM...' : (txDetail?.explanation || 'No explanation available.')}
                </div>
              </div>
              
              {/* Handoff Summary - The "unburied" context loss feature */}
              {txDetail?.handoff_summary && (
                <div className="bg-indigo-950/20 p-4 rounded-xl border border-indigo-900/30">
                  <div className="text-xs font-mono text-indigo-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                    <Activity className="w-3 h-3" /> Support Handoff Summary
                  </div>
                  <div className="text-indigo-200/80 text-sm font-medium italic">
                    "{txDetail.handoff_summary}"
                  </div>
                </div>
              )}

              {/* Action Result / Execution panel */}
              {execResult && (
                <div className="bg-emerald-950/20 p-5 rounded-xl border border-emerald-900/50 space-y-4">
                  <div className="text-emerald-400 font-bold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" /> Action Executed Successfully
                  </div>
                  <div className="text-zinc-300 text-sm">{execResult.action}</div>
                  
                  {execResult.merchant_message && (
                    <div className="space-y-1">
                      <div className="text-xs font-mono text-zinc-500 uppercase">Merchant Notification</div>
                      <div className="p-3 bg-black/40 rounded border border-zinc-800 text-zinc-300 text-sm font-mono">{execResult.merchant_message}</div>
                    </div>
                  )}
                  {execResult.customer_message && (
                    <div className="space-y-1">
                      <div className="text-xs font-mono text-zinc-500 uppercase">Customer Receipt / Link</div>
                      <div className="p-3 bg-black/40 rounded border border-zinc-800 text-zinc-300 text-sm font-mono">{execResult.customer_message}</div>
                    </div>
                  )}
                </div>
              )}

              {/* Possible Causes & Agent Actions */}
              {!execResult && selectedTx.failure_reason && selectedTx.failure_reason !== 'nan' && selectedTx.status === 'Mismatched' && (
                <div className="space-y-4">
                  <div className="text-sm font-bold text-white border-b border-zinc-800 pb-2">Root Cause Resolution Paths</div>
                  
                  {selectedTx.failure_reason === 'PAYMENT_DECLINED_BANK' && (
                    <>
                      <div className="flex items-center justify-between p-4 bg-zinc-900/30 rounded-lg border border-zinc-800">
                        <div>
                          <div className="text-white text-sm font-medium mb-1">Insufficient funds</div>
                          <div className="text-zinc-500 text-xs">Generates a split payment link via Razorpay Links API.</div>
                        </div>
                        <button onClick={() => executeAction('insufficient_funds')} disabled={executing} className="btn-dark-secondary text-xs">Execute Agent</button>
                      </div>
                      <div className="flex items-center justify-between p-4 bg-zinc-900/30 rounded-lg border border-zinc-800">
                        <div>
                          <div className="text-white text-sm font-medium mb-1">Card blocked or expired</div>
                          <div className="text-zinc-500 text-xs">Generates a fresh payment link for alternative methods.</div>
                        </div>
                        <button onClick={() => executeAction('card_blocked')} disabled={executing} className="btn-dark-secondary text-xs">Execute Agent</button>
                      </div>
                      <div className="flex items-center justify-between p-4 bg-rose-950/20 rounded-lg border border-rose-900/30">
                        <div>
                          <div className="text-rose-400 text-sm font-medium mb-1">Fraud flag from bank</div>
                          <div className="text-rose-400/70 text-xs">Blocks retries and escalates to human review.</div>
                        </div>
                        <button onClick={() => executeAction('fraud_flag')} disabled={executing} className="px-4 py-2 bg-rose-500/20 text-rose-400 rounded-lg text-xs font-medium hover:bg-rose-500/30">Escalate</button>
                      </div>
                    </>
                  )}

                  {selectedTx.failure_reason === 'REFUND_STUCK_GATEWAY' && (
                    <div className="flex items-center justify-between p-4 bg-zinc-900/30 rounded-lg border border-zinc-800">
                      <div>
                        <div className="text-white text-sm font-medium mb-1">Gateway timeout during refund processing</div>
                        <div className="text-zinc-500 text-xs">Calls Razorpay Refunds API to re-trigger.</div>
                      </div>
                      <button onClick={() => executeAction('stuck_refund_gateway')} disabled={executing} className="btn-dark-secondary text-xs">Execute Agent</button>
                    </div>
                  )}

                  {selectedTx.failure_reason === 'SETTLEMENT_DELAYED_KYC' && (
                    <div className="flex items-center justify-between p-4 bg-zinc-900/30 rounded-lg border border-zinc-800">
                      <div>
                        <div className="text-white text-sm font-medium mb-1">Missing KYC document on merchant account</div>
                        <div className="text-zinc-500 text-xs">Identifies missing document and triggers webhook sync.</div>
                      </div>
                      <button onClick={() => executeAction('kyc_missing')} disabled={executing} className="btn-dark-secondary text-xs">Execute Agent</button>
                    </div>
                  )}
                  
                  {selectedTx.failure_reason === 'PAYMENT_CAPTURED_NOT_SETTLED' && (
                    <div className="flex items-center justify-between p-4 bg-zinc-900/30 rounded-lg border border-zinc-800">
                      <div>
                        <div className="text-white text-sm font-medium mb-1">Batch processing delay at Razorpay</div>
                        <div className="text-zinc-500 text-xs">Polls Settlements API to confirm status.</div>
                      </div>
                      <button onClick={() => executeAction('kyc_missing')} disabled={executing} className="btn-dark-secondary text-xs">Execute Agent</button>
                    </div>
                  )}

                  {selectedTx.failure_reason === 'TAX_CALCULATION_DISCREPANCY' && txDetail?.fee_breakdown && (
                    <div className="p-4 bg-zinc-900/30 rounded-lg border border-zinc-800 space-y-3">
                      <div className="text-white text-sm font-medium">Wrong GST rate applied</div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="p-3 bg-rose-950/20 border border-rose-900/30 rounded">
                          <div className="text-xs text-rose-400 mb-1 uppercase font-mono">Reported GST</div>
                          <div className="text-lg text-rose-300 font-mono">₹{txDetail.fee_breakdown.gst}</div>
                        </div>
                        <div className="p-3 bg-emerald-950/20 border border-emerald-900/30 rounded">
                          <div className="text-xs text-emerald-400 mb-1 uppercase font-mono">Corrected @ 18%</div>
                          <div className="text-lg text-emerald-300 font-mono">₹{((txDetail.fee_breakdown.gateway_fee + txDetail.fee_breakdown.bank_fee) * 0.18).toFixed(2)}</div>
                        </div>
                      </div>
                      <div className="text-xs text-zinc-500">Agent Action: Awaiting merchant confirmation to issue corrected invoice.</div>
                    </div>
                  )}

                  {selectedTx.failure_reason === 'DUPLICATE_CHARGE_SUSPECTED' && (
                    <div className="p-4 bg-zinc-900/30 rounded-lg border border-zinc-800 space-y-3">
                      <div className="text-white text-sm font-medium">Customer retried after timeout believing payment failed</div>
                      <div className="flex items-center gap-4 text-xs font-mono text-zinc-400">
                        <div className="flex-1 p-2 bg-black/50 rounded border border-zinc-800">tx_prev_12345 (Captured)</div>
                        <div>← AND →</div>
                        <div className="flex-1 p-2 bg-amber-950/30 text-amber-500 rounded border border-amber-900/50">{selectedTx.id} (Captured)</div>
                      </div>
                      <div className="text-xs text-zinc-500 mt-2">Agent Action: Both payments successfully captured. Refund for {selectedTx.id} paused pending merchant verification.</div>
                    </div>
                  )}

                </div>
              )}

              {/* Normal Settled Details */}
              {selectedTx.status === 'Settled' && txDetail?.fee_breakdown && (
                <div className="grid grid-cols-5 gap-2 border border-zinc-800 rounded-lg overflow-hidden">
                  <div className="bg-zinc-900/50 p-3 text-center border-r border-zinc-800">
                    <div className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Gross</div>
                    <div className="text-sm text-white font-mono">₹{txDetail.fee_breakdown.gross_amount}</div>
                  </div>
                  <div className="bg-zinc-900/50 p-3 text-center border-r border-zinc-800">
                    <div className="text-[10px] text-zinc-500 font-mono uppercase mb-1">GW Fee (2%)</div>
                    <div className="text-sm text-rose-400 font-mono">-₹{txDetail.fee_breakdown.gateway_fee}</div>
                  </div>
                  <div className="bg-zinc-900/50 p-3 text-center border-r border-zinc-800">
                    <div className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Bank Fee</div>
                    <div className="text-sm text-rose-400 font-mono">-₹{txDetail.fee_breakdown.bank_fee}</div>
                  </div>
                  <div className="bg-zinc-900/50 p-3 text-center border-r border-zinc-800">
                    <div className="text-[10px] text-zinc-500 font-mono uppercase mb-1">GST (18%)</div>
                    <div className="text-sm text-rose-400 font-mono">-₹{txDetail.fee_breakdown.gst}</div>
                  </div>
                  <div className="bg-[#121215] p-3 text-center">
                    <div className="text-[10px] text-emerald-500 font-mono uppercase mb-1">Net Settled</div>
                    <div className="text-sm text-emerald-400 font-mono font-bold">₹{txDetail.fee_breakdown.net_settled}</div>
                  </div>
                </div>
              )}

              {/* Flagged actions if directly in flagged state */}
              {selectedTx.flagged === 1 && (
                <div className="mt-6 border-t border-zinc-800 pt-6 flex gap-4">
                  <button className="flex-1 py-3 rounded-lg bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors font-medium" onClick={() => handleApprove(selectedTx.id, 'APPROVE')}>
                    Approve Action
                  </button>
                  <button className="flex-1 py-3 rounded-lg bg-rose-500/10 text-rose-500 border border-rose-500/20 hover:bg-rose-500/20 transition-colors font-medium" onClick={() => handleApprove(selectedTx.id, 'REJECT')}>
                    Reject & Escalate
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* --- EXECUTIVE SUMMARY MODAL --- */}
      {summaryModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f0f13] border border-[rgba(255,255,255,0.12)] rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl animate-in zoom-in-95">
            <div className="p-6 border-b border-zinc-800 flex justify-between items-center bg-zinc-900/50">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-[#C9A227]/10 border border-[#C9A227]/30 flex items-center justify-center text-[#C9A227]">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-white font-bold text-lg">Executive Audit Summary</h3>
                  <div className="text-xs text-[#71717A] font-mono">Autonomous Batch Synthesis & Leadership Report</div>
                </div>
              </div>
              <button 
                onClick={() => setSummaryModalOpen(false)}
                className="text-zinc-400 hover:text-white p-1 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
              {/* AI Executive Synthesis */}
              <div className="bg-[#121215] border border-[rgba(255,255,255,0.08)] rounded-xl p-4">
                <div className="text-xs font-mono text-[#C9A227] uppercase tracking-wider mb-2 flex items-center gap-2">
                  <span>AI Leadership Brief</span>
                  {loadingSummary && <RefreshCw className="w-3 h-3 animate-spin" />}
                </div>
                <div className="text-sm text-zinc-300 leading-relaxed">
                  {loadingSummary ? (
                    <div className="flex items-center gap-2 py-4 text-zinc-500 text-sm">
                      <RefreshCw className="w-4 h-4 animate-spin text-[#C9A227]" />
                      Synthesizing executive findings across current batch...
                    </div>
                  ) : summaryText ? (
                    summaryText
                  ) : (
                    `Audited ${metrics.total_processed} transactions against the ledger. Identified ${metrics.mismatches_detected} mismatches across fees and timing anomalies, with ₹${metrics.amount_recovered.toLocaleString('en-IN')} safely recovered via bounded recovery workflows.`
                  )}
                </div>
              </div>

              {/* Key Highlights Grid */}
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-3 text-center">
                  <div className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Audited Volume</div>
                  <div className="text-xl font-bold text-white font-display">{metrics.total_processed} txs</div>
                </div>
                <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-3 text-center">
                  <div className="text-[10px] text-[#C9A227] font-mono uppercase mb-1">Total Recovered</div>
                  <div className="text-xl font-bold text-[#C9A227] font-display">₹{metrics.amount_recovered.toLocaleString('en-IN')}</div>
                </div>
                <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-3 text-center">
                  <div className="text-[10px] text-amber-500 font-mono uppercase mb-1">Safety Held</div>
                  <div className="text-xl font-bold text-amber-400 font-display">{metrics.pending_approval} items</div>
                </div>
              </div>

              {/* Architectural Assurance */}
              <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800 text-xs text-zinc-400 leading-relaxed">
                <strong className="text-white">Safety Guarantee:</strong> All autonomous recovery actions operate within strict deterministic bounds (split links, dispute triggers, fee re-audits). Any out-of-bounds anomaly is halted and queued for manual human sign-off.
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex items-center gap-3">
                <a
                  href={`${API_BASE}/api/export-pdf`}
                  download="AI_Settlement_Executive_Report.pdf"
                  className="flex-1 btn-gold-primary justify-center text-sm py-2.5"
                >
                  <Download className="w-4 h-4" />
                  Download Official PDF Report
                </a>
                <button
                  onClick={() => window.print()}
                  className="btn-dark-secondary text-sm py-2.5 px-4"
                >
                  Print Report
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* --- QA FLOATING BUBBLE --- */}
      <div className="fixed bottom-8 right-8 z-40">
        {qaOpen ? (
          <div className="bg-[#121215] border border-zinc-800 rounded-2xl shadow-2xl w-[400px] flex flex-col overflow-hidden animate-in slide-in-from-bottom-5">
            <div className="bg-zinc-900 p-4 border-b border-zinc-800 flex justify-between items-center">
              <div className="flex items-center gap-2 text-white font-medium">
                <MessageCircle className="w-4 h-4 text-[#C9A227]" /> Ask the Auditor
              </div>
              <button onClick={() => setQaOpen(false)} className="text-zinc-500 hover:text-white"><X className="w-4 h-4"/></button>
            </div>
            <div className="p-4 h-64 overflow-y-auto">
              {qaAnswer ? (
                <div className="text-sm text-zinc-300 leading-relaxed bg-zinc-900/50 p-3 rounded-lg border border-zinc-800">
                  {qaAnswer}
                </div>
              ) : (
                <div className="text-sm text-zinc-500 text-center mt-20">
                  Ask Groq any question about the current ledger state, flagged transactions, or recovery metrics.
                </div>
              )}
            </div>
            <form onSubmit={handleQASubmit} className="p-3 border-t border-zinc-800 bg-zinc-950 flex gap-2">
              <input 
                type="text" 
                value={qaQuery}
                onChange={e => setQaQuery(e.target.value)}
                placeholder="E.g., Why are there so many mismatches?"
                className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#C9A227]"
              />
              <button type="submit" disabled={loadingQA} className="btn-gold-primary px-4 py-2">
                {loadingQA ? '...' : 'Ask'}
              </button>
            </form>
          </div>
        ) : (
          <button 
            onClick={() => setQaOpen(true)}
            className="w-14 h-14 rounded-full bg-[#C9A227] hover:bg-[#D4AF37] flex items-center justify-center text-black shadow-lg shadow-[#C9A227]/20 transition-transform hover:scale-105"
          >
            <MessageCircle className="w-6 h-6" />
          </button>
        )}
      </div>
    </div>
  );
}
