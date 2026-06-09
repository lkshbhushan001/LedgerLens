"""
Pytest configuration and fixtures for test documents.
Generates sample PDFs, XMLs, CSVs, and TXT files for testing ingestion pipeline.
"""

import io
import json
import pytest
from pathlib import Path
from datetime import datetime
import tempfile
import asyncio
import sys
from unittest.mock import AsyncMock, patch, MagicMock


# Try to import optional PDF library; skip PDF tests if not available
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


# ==============================================================================
# Global Groq API Mocking (Minimize actual API usage)
# ==============================================================================

@pytest.fixture(scope="session", autouse=True)
def mock_groq_api():
    """Mock all Groq API calls globally to minimize API usage during testing."""
    def mock_response(*args, **kwargs):
        class MockMessage:
            content = "Test response from mocked Groq API"
        class MockCompletion:
            choices = [MagicMock(message=MockMessage())]
        return MockCompletion()
    
    async def mock_async_response(*args, **kwargs):
        return mock_response(*args, **kwargs)
    
    # Patch Groq's AsyncOpenAI client
    with patch("app.services.llm.groq_client.chat.completions.create", side_effect=mock_async_response):
        with patch("app.services.evaluation._get_evaluator_llm") as mock_llm:
            mock_llm.return_value = MagicMock()
            yield


# ==============================================================================
# Test Database Setup (Must run before app imports)
# ==============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Configure test environment variables before importing the app."""
    import os
    # Use in-memory SQLite for testing
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    # Ensure test env is set
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars-minimum-required")
    os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
    yield


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db(setup_test_env):
    """Create tables in the test database before running tests."""
    async def init():
        from sqlalchemy.ext.asyncio import create_async_engine
        from app.db.database import Base
        
        test_db_url = "sqlite+aiosqlite:///:memory:"
        engine = create_async_engine(test_db_url, echo=False)
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        await engine.dispose()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init())
    yield




def generate_pdf_content() -> bytes:
    """Generate a sample PDF with financial content."""
    if not HAS_REPORTLAB:
        pytest.skip("reportlab not installed - skipping PDF generation")
    
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Financial Statement - Q1 2024")
    
    # Content
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


# ==============================================================================
# Pytest Fixtures
# ==============================================================================


@pytest.fixture
def test_pdf_file(tmp_path: Path) -> Path:
    """Create a temporary PDF file for testing."""
    if not HAS_REPORTLAB:
        pytest.skip("reportlab not installed")
    
    pdf_file = tmp_path / "test_financial_report.pdf"
    pdf_file.write_bytes(generate_pdf_content())
    return pdf_file


@pytest.fixture
def test_xml_file(tmp_path: Path) -> Path:
    """Create a temporary XML file for testing."""
    xml_file = tmp_path / "test_financial_data.xml"
    xml_file.write_text(generate_xml_content(), encoding="utf-8")
    return xml_file


@pytest.fixture
def test_csv_file(tmp_path: Path) -> Path:
    """Create a temporary CSV file for testing."""
    csv_file = tmp_path / "test_transactions.csv"
    csv_file.write_text(generate_csv_content(), encoding="utf-8")
    return csv_file


@pytest.fixture
def test_txt_file(tmp_path: Path) -> Path:
    """Create a temporary TXT file for testing."""
    txt_file = tmp_path / "test_financial_report.txt"
    txt_file.write_text(generate_txt_content(), encoding="utf-8")
    return txt_file


@pytest.fixture
def test_json_file(tmp_path: Path) -> Path:
    """Create a temporary JSON file for testing."""
    json_file = tmp_path / "test_ledger_data.json"
    json_file.write_text(generate_json_content(), encoding="utf-8")
    return json_file


@pytest.fixture
def test_documents_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with all test documents."""
    docs_dir = tmp_path / "test_documents"
    docs_dir.mkdir()
    
    # Create all test files
    if HAS_REPORTLAB:
        (docs_dir / "financial_report.pdf").write_bytes(generate_pdf_content())
    (docs_dir / "financial_data.xml").write_text(generate_xml_content(), encoding="utf-8")
    (docs_dir / "transactions.csv").write_text(generate_csv_content(), encoding="utf-8")
    (docs_dir / "report.txt").write_text(generate_txt_content(), encoding="utf-8")
    (docs_dir / "ledger.json").write_text(generate_json_content(), encoding="utf-8")
    
    return docs_dir


# ==============================================================================
# Fixtures directory setup (for persistent test documents)
# ==============================================================================


@pytest.fixture(scope="session", autouse=True)
async def initialize_test_db():
    """Initialize test database with all required tables."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.db.database import Base
    from app.db.models import DocumentDBRecord
    
    # Create a fresh test database
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    yield


@pytest.fixture(scope="session", autouse=True)
def create_fixtures_directory():
    """Create persistent test documents in tests/fixtures/ directory."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)
    
    # Create persistent test documents
    doc_files = {
        "financial_data.xml": generate_xml_content(),
        "transactions.csv": generate_csv_content(),
        "report.txt": generate_txt_content(),
        "ledger.json": generate_json_content(),
    }
    
    for filename, content in doc_files.items():
        filepath = fixtures_dir / filename
        filepath.write_text(content, encoding="utf-8")
    
    # Create PDF if reportlab is available
    if HAS_REPORTLAB:
        pdf_path = fixtures_dir / "financial_report.pdf"
        pdf_path.write_bytes(generate_pdf_content())
    
    yield
    # Cleanup is optional - you may want to keep fixtures for inspection


# ==============================================================================
# Helper function for direct use in tests
# ==============================================================================


def get_test_document_path(doc_type: str, tmp_path: Path) -> Path:
    """
    Get a path to a test document of the specified type.
    
    Args:
        doc_type: One of 'pdf', 'xml', 'csv', 'txt', 'json'
        tmp_path: Temporary path fixture from pytest
    
    Returns:
        Path to the generated test document
    """
    generators = {
        "pdf": lambda p: p / "test.pdf" if (p / "test.pdf").write_bytes(generate_pdf_content()) or True else None,
        "xml": lambda p: p / "test.xml" if (p / "test.xml").write_text(generate_xml_content()) or True else None,
        "csv": lambda p: p / "test.csv" if (p / "test.csv").write_text(generate_csv_content()) or True else None,
        "txt": lambda p: p / "test.txt" if (p / "test.txt").write_text(generate_txt_content()) or True else None,
        "json": lambda p: p / "test.json" if (p / "test.json").write_text(generate_json_content()) or True else None,
    }
    
    if doc_type not in generators:
        raise ValueError(f"Unknown document type: {doc_type}")
    
    # Create and return the document
    if doc_type == "pdf":
        path = tmp_path / f"test_{doc_type}.pdf"
        path.write_bytes(generate_pdf_content())
    else:
        path = tmp_path / f"test_{doc_type}.{doc_type}"
        content_func = {
            "xml": generate_xml_content,
            "csv": generate_csv_content,
            "txt": generate_txt_content,
            "json": generate_json_content,
        }[doc_type]
        path.write_text(content_func(), encoding="utf-8")
    
    return path
