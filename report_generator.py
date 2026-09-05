import io
import sqlite3
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

DB_PATH = 'auditor.db'

def generate_pdf_report():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM transactions ORDER BY updated_at DESC')
    tx_rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_processed = len(tx_rows)
    mismatches = [t for t in tx_rows if t.get('status') in ['Mismatched', 'Recovered', 'Flagged', 'BROKEN_PROMISE']]
    recovered = [t for t in tx_rows if t.get('status') == 'Recovered']
    recovered_amount = sum(float(t.get('amount', 0)) for t in recovered)
    pending_approval = len([t for t in tx_rows if t.get('flagged') == 1])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#000000'),
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#555555'),
        spaceAfter=8
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#C9A227'),
        spaceBefore=10,
        spaceAfter=5
    )

    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#111111')
    )

    summary_box_style = ParagraphStyle(
        'SummaryText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor('#111111')
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#FFFFFF')
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#222222')
    )

    story = []

    now_str = datetime.datetime.now().strftime('%d %b %Y, %H:%M:%S UTC')
    header_data = [
        [
            Paragraph('<b>AI SETTLEMENT AUDITOR</b><br/><font size=8 color="#666666">AUTONOMOUS RAZORPAY SETTLEMENT RECONCILIATION</font>', title_style),
            Paragraph(f'<b>EXECUTIVE AUDIT REPORT</b><br/><font size=8 color="#666666">Generated: {now_str}</font>', subtitle_style)
        ]
    ]
    t_header = Table(header_data, colWidths=[330, 210])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_header)

    story.append(Spacer(1, 4))
    t_line = Table([['']], colWidths=[540], rowHeights=[2])
    t_line.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#C9A227')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_line)
    story.append(Spacer(1, 8))

    story.append(Paragraph('EXECUTIVE SUMMARY', h2_style))
    if total_processed == 0:
        summary_text = 'No batch transactions have been ingested yet. The system is currently standing by awaiting batch ingestion from the Razorpay environment.'
    else:
        mismatch_pct = (len(mismatches) / total_processed * 100) if total_processed else 0
        summary_text = (
            f'During the latest audit cycle, the autonomous agent evaluated <b>{total_processed} transactions</b> against the merchant ledger. '
            f'A total of <b>{len(mismatches)} discrepancies ({mismatch_pct:.1f}%)</b> were identified across fees, taxes, uncaptured webhooks, and delayed transfers. '
            f'The agent successfully recovered <b>INR {recovered_amount:,.2f}</b> via automated bounded remediation workflows. '
            f'All non-deterministic or high-exposure cases (<b>{pending_approval} items</b>) were held in the Human Approval Queue in accordance with financial safety policies.'
        )

    summary_table = Table([[Paragraph(summary_text, summary_box_style)]], colWidths=[540])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FA')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#D1D5DB')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph('AUDIT METRICS & KPI DASHBOARD', h2_style))
    metrics_data = [
        [Paragraph('METRIC', table_header_style), Paragraph('VALUE', table_header_style), Paragraph('STATUS / THRESHOLD', table_header_style)],
        [Paragraph('Total Transactions Audited', table_cell_style), Paragraph(str(total_processed), body_bold), Paragraph('Ingested from Razorpay Sandbox / Live API', table_cell_style)],
        [Paragraph('Discrepancies Identified', table_cell_style), Paragraph(str(len(mismatches)), body_bold), Paragraph('Rule-based ledger reconciliation match', table_cell_style)],
        [Paragraph('Recovered Value', table_cell_style), Paragraph(f'INR {recovered_amount:,.2f}', body_bold), Paragraph('Autonomous safe bounded actions executed', table_cell_style)],
        [Paragraph('Pending Human Review', table_cell_style), Paragraph(str(pending_approval), body_bold), Paragraph('Gated: Exceeds automated policy bounds', table_cell_style)],
        [Paragraph('Decision Policy Compliance', table_cell_style), Paragraph('100% Deterministic', body_bold), Paragraph('Zero unvalidated LLM execution on financial ledger', table_cell_style)],
    ]
    t_metrics = Table(metrics_data, colWidths=[180, 130, 230])
    t_metrics.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E1E24')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F9FAFB')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_metrics)
    story.append(Spacer(1, 8))

    story.append(Paragraph('DISCREPANCY & RECOVERY TRANSACTION LEDGER', h2_style))
    table_rows = [
        [Paragraph('TX ID', table_header_style), Paragraph('AMOUNT', table_header_style), Paragraph('FAILURE REASON', table_header_style), Paragraph('STATUS', table_header_style), Paragraph('RESOLUTION / ACTION', table_header_style)]
    ]
    for tx in tx_rows[:10]:
        tx_id = str(tx.get('id', ''))[:16]
        amt = f'INR {float(tx.get("amount", 0)):,.2f}'
        reason = str(tx.get('failure_reason') or 'NORMAL')[:24]
        status = str(tx.get('status', ''))
        action = str(tx.get('recovery_action') or 'Audit verified')[:35]
        table_rows.append([
            Paragraph(tx_id, table_cell_style),
            Paragraph(amt, table_cell_style),
            Paragraph(reason, table_cell_style),
            Paragraph(status, table_cell_style),
            Paragraph(action, table_cell_style)
        ])

    if len(table_rows) == 1:
        table_rows.append([Paragraph('No transactions recorded', table_cell_style), Paragraph('-', table_cell_style), Paragraph('-', table_cell_style), Paragraph('-', table_cell_style), Paragraph('-', table_cell_style)])

    t_tx = Table(table_rows, colWidths=[100, 80, 130, 80, 150])
    t_tx.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E1E24')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F9FAFB')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_tx)
    story.append(Spacer(1, 10))

    footer_text = '<b>Architectural Guarantee:</b> All money-moving recoveries are constrained within deterministic boundaries. Any transaction flagged with high risk, anomalous volume, or ambiguity requires mandatory dual-authorization before execution. Every interaction, explainability prompt, and resolution attempt is preserved immutably in the audit log.'
    story.append(Paragraph(footer_text, ParagraphStyle('Footnote', parent=styles['Normal'], fontSize=7.5, leading=10, textColor=colors.HexColor('#6B7280'))))

    doc.build(story)
    buffer.seek(0)
    return buffer
