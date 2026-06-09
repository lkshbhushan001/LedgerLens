#!/usr/bin/env python3
"""Direct document generator - runs the generation functions directly."""

import io
import json
import sys
from pathlib import Path

# Try to import optional PDF library
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    print("⚠️  reportlab not installed - skipping PDF generation")
    print("   Install with: pip install reportlab\n")


def generate_pdf_content() -> bytes:
    """Generate a sample PDF with financial content."""
    if not HAS_REPORTLAB:
        return None
    
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Financial Statement - Q1 2024")
    
    c.setFont("Helvetica", 12)
    y = 720
    content = [
        "Company Name: Acme Corp",
        "Period: January 1 - March 31, 2024",
        "",
        "REVENUE:",
        "Total Revenue: $2,500,000",
        "Cost of Goods Sold: $1,200,000",
        "Gross Profit: $1,300,000",
        "",
        "OPERATING EXPENSES:",
        "Salaries: $400,000",
        "Rent: $150,000",
        "Utilities: $50,000",
        "Marketing: $100,000",
        "Total Operating Expenses: $700,000",
        "",
        "NET INCOME: $600,000",
    ]
    
    for line in content:
        c.drawString(50, y, line)
        y -= 20
    
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


def generate_xml_content() -> str:
    """Generate a sample XML with financial data."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<FinancialReport>
    <Metadata>
        <CompanyName>TechCorp Inc</CompanyName>
        <ReportDate>2024-01-15</ReportDate>
        <Currency>USD</Currency>
    </Metadata>
    <IncomeStatement>
        <Revenue>
            <ProductSales>3500000</ProductSales>
            <ServiceSales>1200000</ServiceSales>
            <Total>4700000</Total>
        </Revenue>
        <Expenses>
            <COGS>2100000</COGS>
            <OperatingExpenses>1500000</OperatingExpenses>
            <Total>3600000</Total>
        </Expenses>
        <NetIncome>1100000</NetIncome>
    </IncomeStatement>
    <BalanceSheet>
        <Assets>
            <Current>5000000</Current>
            <Fixed>3000000</Fixed>
            <Total>8000000</Total>
        </Assets>
        <Liabilities>
            <Current>2000000</Current>
            <LongTerm>1500000</LongTerm>
            <Total>3500000</Total>
        </Liabilities>
        <Equity>4500000</Equity>
    </BalanceSheet>
</FinancialReport>"""


def generate_csv_content() -> str:
    """Generate a sample CSV with transaction data."""
    return """Date,Description,Category,Amount,Balance
2024-01-01,Opening Balance,Initial,0,100000
2024-01-05,Revenue from Sales,Income,5000,105000
2024-01-10,Rent Payment,Expense,-2000,103000
2024-01-15,Salary Payments,Expense,-8000,95000
2024-01-20,Equipment Purchase,Capital,-3000,92000
2024-01-25,Interest Received,Income,500,92500
2024-02-01,Monthly Utilities,Expense,-1500,91000
2024-02-05,Contract Completion,Income,12000,103000
2024-02-10,Office Supplies,Expense,-800,102200
2024-02-15,Quarterly Review,Reference,0,102200"""


def generate_txt_content() -> str:
    """Generate a sample text document."""
    return """FINANCIAL REPORT - YEAR 2024

Executive Summary
================
This report provides a comprehensive overview of our financial performance
for the fiscal year 2024. The organization has demonstrated strong growth
across all key metrics.

Key Performance Indicators
==========================
- Total Revenue: $15,000,000
- Operating Margin: 22%
- Net Profit Margin: 15%
- Return on Assets: 12%
- Cash Flow from Operations: $3,200,000

Revenue Analysis
================
The organization generated revenue from multiple streams:
1. Product Sales: $9,000,000 (60%)
2. Service Revenue: $4,500,000 (30%)
3. Licensing: $1,500,000 (10%)

Expense Breakdown
=================
- Cost of Goods Sold: $6,000,000
- Operating Expenses: $3,840,000
- Depreciation: $1,500,000
- Total Expenses: $11,340,000

Conclusion
==========
Despite challenging market conditions, the organization has achieved
solid financial results with improved operational efficiency."""


def generate_json_content() -> str:
    """Generate a sample JSON with financial ledger data."""
    ledger_data = {
        "company": {
            "name": "Global Finance Ltd",
            "industry": "Financial Services",
            "reporting_date": "2024-03-31"
        },
        "accounts": [
            {
                "account_id": "ACC001",
                "account_name": "Checking Account",
                "account_type": "Asset",
                "balance": 250000,
                "currency": "USD"
            },
            {
                "account_id": "ACC002",
                "account_name": "Savings Account",
                "account_type": "Asset",
                "balance": 500000,
                "currency": "USD"
            },
            {
                "account_id": "ACC003",
                "account_name": "Accounts Receivable",
                "account_type": "Asset",
                "balance": 350000,
                "currency": "USD"
            },
            {
                "account_id": "ACC004",
                "account_name": "Accounts Payable",
                "account_type": "Liability",
                "balance": -200000,
                "currency": "USD"
            }
        ],
        "transactions": [
            {
                "date": "2024-01-10",
                "description": "Client Invoice Payment",
                "amount": 50000,
                "account_id": "ACC001"
            },
            {
                "date": "2024-01-15",
                "description": "Vendor Payment",
                "amount": -30000,
                "account_id": "ACC001"
            },
            {
                "date": "2024-02-01",
                "description": "Monthly Revenue",
                "amount": 75000,
                "account_id": "ACC001"
            }
        ]
    }
    return json.dumps(ledger_data, indent=2)


def main():
    """Generate all test documents."""
    output_dir = Path(__file__).parent / "fixtures"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🚀 Generating test documents...")
    print(f"📁 Output directory: {output_dir}\n")
    
    documents = {
        "financial_data.xml": ("XML", generate_xml_content(), "text"),
        "transactions.csv": ("CSV", generate_csv_content(), "text"),
        "report.txt": ("TXT", generate_txt_content(), "text"),
        "ledger.json": ("JSON", generate_json_content(), "text"),
    }
    
    if HAS_REPORTLAB:
        documents["financial_report.pdf"] = ("PDF", generate_pdf_content(), "binary")
    
    created = 0
    errors = 0
    
    for filename, (fmt, content, mode) in documents.items():
        if content is None:
            continue
        
        try:
            filepath = output_dir / filename
            
            if mode == "binary":
                filepath.write_bytes(content)
            else:
                filepath.write_text(content, encoding="utf-8")
            
            file_size = filepath.stat().st_size
            print(f"✅ {fmt:<4} → {filename:<30} ({file_size:>6} bytes)")
            created += 1
            
        except Exception as e:
            print(f"❌ Error generating {fmt}: {e}")
            errors += 1
    
    print(f"\n📊 Summary: {created} created, {errors} failed")
    print(f"✨ Documents ready in: {output_dir}\n")
    
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
