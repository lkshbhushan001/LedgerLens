# LedgerLens Test Documents - Quick Start Guide

## 📋 What We Created

Your test infrastructure now includes:

### 1. **`conftest.py`** - Document Generators
- Generates PDF, XML, CSV, TXT, JSON documents automatically
- Provides pytest fixtures for each document type
- Creates persistent fixtures in `tests/fixtures/`

### 2. **`test_ingestion_with_documents.py`** - Comprehensive Tests  
- 15+ test cases covering all document types
- Tests individual ingestion paths (PDF, XML, CSV, etc.)
- Tests batch ingestion of multiple documents
- Tests error handling and authentication
- Tests query integration after ingestion

### 3. **`generate_test_documents.py`** - Standalone Utility
- Generate test documents without running pytest
- Customizable output directory
- Selective format generation
- Works from command line

### 4. **`fixtures/README.md`** - Full Documentation
- API reference for all fixtures
- Usage examples
- Troubleshooting guide
- Extension instructions

---

## 🚀 Getting Started (3 Steps)

### Step 1: Generate Test Documents

**Option A: Auto-generate when running tests** (easiest)
```bash
# Tests automatically generate documents on first run
pytest tests/test_ingestion_with_documents.py -v
```

**Option B: Pre-generate documents**
```bash
# Generate to tests/fixtures/
cd tests
python generate_test_documents.py -v

# Output:
# ✅ PDF  → financial_report.pdf              (15234 bytes)
# ✅ XML  → financial_data.xml                (2580 bytes)
# ✅ CSV  → transactions.csv                  (1245 bytes)
# ✅ TXT  → report.txt                        (3820 bytes)
# ✅ JSON → ledger.json                       (1890 bytes)
```

**Option C: Generate specific formats**
```bash
python generate_test_documents.py --format pdf xml csv -v
python generate_test_documents.py --output /custom/path
python generate_test_documents.py --list
```

### Step 2: Run Document Ingestion Tests

```bash
# Run all document ingestion tests
pytest tests/test_ingestion_with_documents.py -v

# Run specific test
pytest tests/test_ingestion_with_documents.py::test_ingest_pdf_document -v

# Run with output
pytest tests/test_ingestion_with_documents.py -v -s

# Run and show failures
pytest tests/test_ingestion_with_documents.py -v --tb=short
```

### Step 3: Use in Your Own Tests

```python
# Example 1: Simple PDF test
def test_my_pdf_ingestion(test_pdf_file, client, auth_headers):
    with open(test_pdf_file, "rb") as f:
        response = client.post(
            "/ingest/upload",
            files={"file": ("report.pdf", f, "application/pdf")},
            headers=auth_headers,
        )
    assert response.status_code == 202

# Example 2: Test all document types
def test_all_formats(test_documents_dir, client, auth_headers):
    for doc_file in test_documents_dir.glob("*"):
        with open(doc_file, "rb") as f:
            response = client.post(
                "/ingest/upload",
                files={"file": (doc_file.name, f, "application/octet-stream")},
                headers=auth_headers,
            )
        assert response.status_code == 202

# Example 3: Access persistent fixtures
from pathlib import Path

def test_with_persistent_fixtures():
    fixtures_dir = Path(__file__).parent / "fixtures"
    pdf_file = fixtures_dir / "financial_report.pdf"
    assert pdf_file.exists()
```

---

## 📊 Document Types Generated

| Format | File | Size | Content |
|--------|------|------|---------|
| PDF | `financial_report.pdf` | ~15 KB | Q1 2024 Financial Statement |
| XML | `financial_data.xml` | ~2.5 KB | Structured financial records |
| CSV | `transactions.csv` | ~1.2 KB | Transaction ledger |
| TXT | `report.txt` | ~3.5 KB | Financial report in text |
| JSON | `ledger.json` | ~1.8 KB | Ledger data with accounts |

---

## 🔧 Usage Examples

### Add Your Own Documents

1. **Add real PDF** (recommended for integration testing):
   ```bash
   # Copy a real financial PDF to tests/fixtures/
   cp ~/Downloads/FinancialReport_2024.pdf tests/fixtures/
   ```

2. **Add custom generator** to `conftest.py`:
   ```python
   def generate_xlsx_content() -> bytes:
       import openpyxl
       wb = openpyxl.Workbook()
       # ... populate workbook ...
       buffer = io.BytesIO()
       wb.save(buffer)
       return buffer.getvalue()
   
   @pytest.fixture
   def test_xlsx_file(tmp_path):
       xlsx_file = tmp_path / "data.xlsx"
       xlsx_file.write_bytes(generate_xlsx_content())
       return xlsx_file
   ```

3. **Programmatically generate** in tests:
   ```python
   from tests.conftest import generate_pdf_content
   
   pdf_bytes = generate_pdf_content()
   # Use pdf_bytes in your test
   ```

### Run Full Test Suite

```bash
# Run all tests (cache, LLM, integration, documents)
pytest tests/ -v

# Run specific test file
pytest tests/test_ingestion_with_documents.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run with markers
pytest tests/ -m "not slow"
```

---

## 📁 Directory Structure

```
tests/
├── __init__.py
├── conftest.py                          ← Document generators & fixtures
├── generate_test_documents.py           ← Standalone utility script
├── fixtures/
│   ├── README.md                        ← Full fixture documentation
│   ├── financial_report.pdf             ← Auto-generated
│   ├── financial_data.xml               ← Auto-generated
│   ├── transactions.csv                 ← Auto-generated
│   ├── report.txt                       ← Auto-generated
│   └── ledger.json                      ← Auto-generated
├── test_security.py                     ← Existing security tests
├── test_cache_and_llm.py                ← Cache & LLM regression tests
├── test_ingest_query_integration.py     ← Auth → Ingest → Query tests
└── test_ingestion_with_documents.py     ← New: Document ingestion tests
```

---

## ⚙️ Dependencies

### Required
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `fastapi` - Already in project

### Optional (for PDF generation)
- `reportlab` - Install with: `pip install reportlab`
- If not installed, PDF tests will be skipped automatically

### For extending with other formats
- `openpyxl` - For Excel files
- `python-docx` - For Word files
- `pptx` - For PowerPoint files

---

## 🧪 What You Can Test Now

✅ **Document Ingestion**
- Upload PDF, XML, CSV, TXT, JSON files
- Verify 202 Accepted response
- Test document status polling

✅ **Multi-Document Batch Ingestion**
- Upload multiple files at once
- Test rate limiting and batch handling

✅ **Query Integration**
- Ingest documents
- Query against ingested content
- Test end-to-end pipeline

✅ **Error Handling**
- Unsupported file types
- Authentication failures
- Large file handling

✅ **Security**
- RBAC enforcement
- Role-based access to ingested documents
- Token validation

---

## 🐛 Troubleshooting

### "reportlab not installed"
```bash
pip install reportlab
pytest tests/test_ingestion_with_documents.py -v
```

### "fixtures directory not found"
```bash
# Fixtures are created on first run
# Or manually create:
mkdir -p tests/fixtures
python tests/generate_test_documents.py
```

### "Test documents not appearing"
```bash
# Documents are created in temp directories by default
# To persist them:
python tests/generate_test_documents.py --output tests/fixtures -v
```

### Test fails with "file not found"
```python
# Use fixtures instead of hardcoding paths
def test_my_test(test_pdf_file):  # Gets path from fixture
    with open(test_pdf_file, "rb") as f:
        # ... your test
```

---

## 🎯 Next Steps

1. **Run tests**: `pytest tests/ -v`
2. **Add real documents**: Copy actual financial documents to `tests/fixtures/`
3. **Extend generators**: Add custom document types to `conftest.py`
4. **Setup integration environment**: 
   - Start Qdrant: `docker-compose up qdrant`
   - Start Redis: `docker-compose up redis`
   - Run against live services: `pytest tests/ --live`

---

## 📚 Documentation

- Full fixture API: `tests/fixtures/README.md`
- Generator code: `tests/conftest.py` (see lines 20-100)
- Test examples: `tests/test_ingestion_with_documents.py`
- ETL pipeline: `app/services/etl.py`
- Ingestion router: `app/routers/ingestion.py`

---

**Happy Testing! 🚀**
