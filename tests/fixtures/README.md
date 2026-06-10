# Test Documents Guide

This directory contains test fixtures and a system for generating test documents in various formats for testing the ingestion pipeline.

## Quick Start

### Using Pre-Generated Fixtures

Test documents are automatically generated and stored in `tests/fixtures/` when tests run. The following files are created:

- `financial_report.pdf` - Sample PDF with financial data
- `financial_data.xml` - Sample XML with structured financial records
- `transactions.csv` - Sample CSV with transaction data
- `report.txt` - Sample plain text financial report
- `ledger.json` - Sample JSON with ledger entries

### Using in Tests

#### Option 1: Use pytest fixtures (recommended)

```python
def test_with_pdf(test_pdf_file):   
    with open(test_pdf_file, "rb") as f:
        response = client.post("/ingest/upload", files={"file": f})
```

#### Option 2: Use directory fixture

```python
def test_with_all_documents(test_documents_dir):    
    for doc_file in test_documents_dir.glob("*"):
        with open(doc_file, "rb") as f:
            response = client.post("/ingest/upload", files={"file": f})
```

#### Option 3: Persistent fixtures directory

```python
# Access pre-generated files in tests/fixtures/
fixture_dir = Path(__file__).parent / "fixtures"
pdf_file = fixture_dir / "financial_report.pdf"
```

## Available Fixtures

### PDF Fixture
```python
@pytest.fixture
def test_pdf_file(tmp_path: Path) -> Path:
    """Creates a temporary PDF file with financial content"""
```

**Content:** Q1 2024 Financial Statement with Revenue, Expenses, and Net Income

**Requirements:** `reportlab` library (installed with `pip install reportlab`)

### XML Fixture
```python
@pytest.fixture
def test_xml_file(tmp_path: Path) -> Path:
    """Creates a temporary XML file with structured financial data"""
```

**Content:** FinancialReport with Income Statement, Balance Sheet, and Metadata

### CSV Fixture
```python
@pytest.fixture
def test_csv_file(tmp_path: Path) -> Path:
    """Creates a temporary CSV file with transaction records"""
```

**Content:** Transaction ledger with Date, Description, Category, Amount, Balance

### TXT Fixture
```python
@pytest.fixture
def test_txt_file(tmp_path: Path) -> Path:
    """Creates a temporary plain text file"""
```

**Content:** Financial report in text format with sections and metrics

### JSON Fixture
```python
@pytest.fixture
def test_json_file(tmp_path: Path) -> Path:
    """Creates a temporary JSON file with ledger data"""
```

**Content:** Structured JSON with company info, accounts, and transactions

### Multi-Document Directory Fixture
```python
@pytest.fixture
def test_documents_dir(tmp_path: Path) -> Path:
    """Creates a temporary directory with all document types"""
```

## Adding Custom Test Documents

### Method 1: Add Generator Functions to conftest.py

```python
def generate_custom_format_content() -> str:    
    return """Your document content here"""

@pytest.fixture
def test_custom_file(tmp_path: Path) -> Path:    
    custom_file = tmp_path / "test_custom.ext"
    custom_file.write_text(generate_custom_format_content(), encoding="utf-8")
    return custom_file
```

### Method 2: Create Real Test Files Manually

```bash
# Create a new test document
echo "Your financial data" > tests/fixtures/custom_report.txt

# Or create a PDF with a tool
# Or export an Excel file as .xlsx
```

### Method 3: Use the Helper Function

```python
from tests.conftest import get_test_document_path

def test_with_helper(tmp_path):
    pdf_path = get_test_document_path("pdf", tmp_path)
    xml_path = get_test_document_path("xml", tmp_path)
```

## File Format Specifications

### PDF Content
- Title: "Financial Statement - Q1 2024"
- Sections: Company Info, Revenue, Operating Expenses, Net Income
- Pages: 1
- Format: reportlab-generated

### XML Structure
```xml
<FinancialReport>
  <Metadata>
    <CompanyName>, <ReportDate>, <Currency>
  </Metadata>
  <IncomeStatement>
    <Revenue>, <Expenses>, <NetIncome>
  </IncomeStatement>
  <BalanceSheet>
    <Assets>, <Liabilities>, <Equity>
  </BalanceSheet>
</FinancialReport>
```

### CSV Columns
- Date
- Description
- Category
- Amount
- Balance

### JSON Structure
```json
{
  "company": { name, industry, reporting_date },
  "accounts": [ { account_id, name, type, balance } ],
  "transactions": [ { date, description, amount, account_id } ]
}
```

### TXT Structure
- Executive Summary
- Key Performance Indicators
- Revenue Analysis
- Expense Breakdown
- Conclusion

## Running Tests with Documents

### Run all document ingestion tests
```bash
pytest tests/test_ingestion_with_documents.py -v
```

### Run specific document type tests
```bash
pytest tests/test_ingestion_with_documents.py::test_ingest_pdf_document -v
pytest tests/test_ingestion_with_documents.py::test_ingest_xml_document -v
pytest tests/test_ingestion_with_documents.py::test_ingest_csv_document -v
```

### Run batch ingestion test
```bash
pytest tests/test_ingestion_with_documents.py::test_ingest_multiple_documents -v
```

### Run with document generation logging
```bash
pytest tests/test_ingestion_with_documents.py -v -s
```

## Troubleshooting

### ImportError: No module named 'reportlab'
PDF tests require reportlab. Install it:
```bash
pip install reportlab
```

Or the tests will automatically skip if reportlab is not available.

### Large File Sizes
Test documents are generated in-memory and temporary. They won't consume significant disk space unless you save them to `tests/fixtures/`.

### Memory Issues
If generating many documents, use the fixture directory approach (persists to disk) instead of tmp_path.

### Fixture Not Found
Ensure `conftest.py` is in the `tests/` directory and imports are correct:
```bash
# Should show conftest.py
ls tests/conftest.py
```

## Document Size Reference

For ingestion performance testing, here are typical file sizes:
- PDF: ~15 KB
- XML: ~2.5 KB
- CSV: ~1.2 KB
- TXT: ~3.5 KB
- JSON: ~1.8 KB

## Extending with Real Data

For production-like testing, you can:

1. **Export real company documents** (with anonymized data)
2. **Create additional formats** (.xlsx, .docx, .pptx via python-pptx, python-docx)
3. **Add error cases** (corrupted files, empty files, very large files)
4. **Add language variants** (non-English financial documents)

### Example: Adding Excel Support

```python
# Install: pip install openpyxl

def generate_xlsx_content():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws['A1'] = 'Transaction Date'
    ws['B1'] = 'Amount'
    ws['A2'] = '2024-01-01'
    ws['B2'] = 5000
    # ... add more rows
    return wb

@pytest.fixture
def test_xlsx_file(tmp_path):
    xlsx_file = tmp_path / "data.xlsx"
    wb = generate_xlsx_content()
    wb.save(xlsx_file)
    return xlsx_file
```

## Best Practices

1. **Use fixtures for isolation**: Each test gets fresh documents
2. **Mock external services**: Test document parsing, not API dependencies
3. **Test multiple formats**: Verify parser works with all supported types
4. **Test error cases**: Corrupted files, unsupported formats
5. **Measure performance**: Monitor ingestion time with larger documents
6. **Version test data**: Keep fixtures under version control if they're real data

## Related Documentation

- ETL Pipeline: `app/services/etl.py`
- Ingestion Router: `app/routers/ingestion.py`
- Document Models: `app/db/models.py`
- Integration Tests: `tests/test_ingestion_with_documents.py`
- Cache Tests: `tests/test_cache_and_llm.py`
- Query Tests: `tests/test_ingest_query_integration.py`
