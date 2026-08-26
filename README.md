# AI Settlement Auditor 🔍

> **Every transaction, explained. Every mismatch, caught. Every action, accounted for.**

An autonomous financial ops agent that audits Razorpay transaction lifecycles end-to-end — explaining fee breakdowns, catching settlement mismatches, performing bounded recovery, and gating risky actions for human approval.

Built for the **Razorpay AI Builder Program (Open Track)**.

---

## 🌟 Key Features

- **Stage 1 — Create & Track:** Integrates Razorpay test-mode SDK to simulate live orders, payment declines, settlement delays, stuck refunds, and incentive anomalies.
- **Stage 2 — Explain:** Generates itemized fee breakdowns (Gross → Gateway Fee → Bank Fee → GST → Net Settled) and plain-English failure causes via **Groq API (Llama 3.1)**.
- **Stage 3 — Detect & Recover:** Multi-source reconciliation engine (`pandas`) cross-checking payment records against settlement ledgers to execute bounded recovery.
- **Stage 4 — Gate & Audit:** Enforces **Fair Incentive Gating** to pause anomalous incentive offers for human approval (`Approve` / `Reject`) and maintains an immutable SQLite audit log.
- **Ask the Auditor (Q&A):** Natural language Q&A tab querying live SQLite batch context.
- **15+ Advanced Ops Capabilities:** Tax-line matcher, duplicate charge detector, customer risk tiering, escalation ladders, delay predictors, executive report generator, and CSV audit exports.

---

## 🛠️ Tech Stack

- **Frontend & Dashboard:** Streamlit (Custom Vercel/Linear dark theme)
- **Core Logic & Reconciliation:** Python, `pandas`
- **Database:** SQLite
- **LLM / Explainability:** Groq API (`llama-3.1-8b-instant`)
- **API Integration:** Razorpay Python SDK

---

## 🚀 Quickstart & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/AI_settlement_auditor.git
   cd AI_settlement_auditor
   ```

2. **Set up virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Create a `.env` file in the root directory:
   ```ini
   RAZORPAY_KEY_ID="rzp_test_your_key_id"
   RAZORPAY_KEY_SECRET="your_key_secret"
   GROQ_API_KEY="gsk_your_groq_key"
   ```

4. **Launch the application:**
   ```bash
   streamlit run app.py
   ```
   Open `http://localhost:8501` in your browser.

---

## 🛡️ License & Safety

*Running on Razorpay test-mode data. No real funds are moved.*
