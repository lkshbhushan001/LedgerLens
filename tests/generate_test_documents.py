"""
Standalone utility for generating test documents for the LedgerLens ingestion pipeline.

Usage:
    python tests/generate_test_documents.py                  # Generate to tests/fixtures/
    python tests/generate_test_documents.py --output /tmp    # Generate to custom directory
    python tests/generate_test_documents.py --format pdf     # Generate only PDFs
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, List

# Import generators from conftest
sys.path.insert(0, str(Path(__file__).parent))

try:
    from conftest import (
        generate_pdf_content,
        generate_xml_content,
        generate_csv_content,
        generate_txt_content,
        generate_json_content,
        HAS_REPORTLAB,
    )
except ImportError:
    print("Error: Could not import conftest. Make sure this script is run from the tests/ directory.")
    sys.exit(1)


GENERATORS = {
    "pdf": ("financial_report.pdf", generate_pdf_content, "binary"),
    "xml": ("financial_data.xml", generate_xml_content, "text"),
    "csv": ("transactions.csv", generate_csv_content, "text"),
    "txt": ("report.txt", generate_txt_content, "text"),
    "json": ("ledger.json", generate_json_content, "text"),
}


def generate_documents(
    output_dir: Path,
    formats: Optional[List[str]] = None,
    verbose: bool = False,
) -> int:
    """
    Generate test documents.
    
    Args:
        output_dir: Directory to save documents
        formats: List of formats to generate (pdf, xml, csv, txt, json), or None for all
        verbose: Print progress messages
    
    Returns:
        Exit code (0 for success, 1 for errors)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if verbose:
        print(f"📁 Output directory: {output_dir}")
    
    if formats is None:
        formats = list(GENERATORS.keys())
    
    # Validate formats
    invalid = set(formats) - set(GENERATORS.keys())
    if invalid:
        print(f"❌ Invalid formats: {', '.join(invalid)}")
        print(f"   Valid formats: {', '.join(GENERATORS.keys())}")
        return 1
    
    errors = 0
    created = 0
    
    for fmt in formats:
        if fmt == "pdf" and not HAS_REPORTLAB:
            print(f"⏭️  Skipping {fmt.upper()}: reportlab not installed")
            print(f"   Install with: pip install reportlab")
            continue
        
        filename, generator, mode = GENERATORS[fmt]
        filepath = output_dir / filename
        
        try:
            content = generator()
            
            if mode == "binary":
                filepath.write_bytes(content)
            else:
                filepath.write_text(content, encoding="utf-8")
            
            file_size = filepath.stat().st_size
            if verbose:
                print(f"✅ {fmt.upper():<4} → {filename:<30} ({file_size:>6} bytes)")
            created += 1
            
        except Exception as e:
            print(f"❌ Error generating {fmt.upper()}: {e}")
            errors += 1
    
    if verbose:
        print(f"\n📊 Summary: {created} created, {errors} failed")
    
    return 1 if errors > 0 else 0


def list_formats() -> None:
    """Display available formats and their details."""
    print("\n🗂️  Available Document Formats:")
    print("-" * 70)
    
    for fmt, (filename, _, _) in GENERATORS.items():
        # Determine availability
        if fmt == "pdf" and not HAS_REPORTLAB:
            status = "⏭️  (requires: pip install reportlab)"
        else:
            status = "✅"
        
        print(f"  {status} {fmt.upper():<4} → {filename}")
    
    print("-" * 70)
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate test documents for LedgerLens ingestion testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_test_documents.py
      Generate all formats to tests/fixtures/
  
  python generate_test_documents.py --output /tmp/docs
      Generate all formats to custom directory
  
  python generate_test_documents.py --format pdf xml
      Generate only PDF and XML
  
  python generate_test_documents.py --list
      List available formats
        """,
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "fixtures",
        help="Output directory for generated documents (default: tests/fixtures/)",
    )
    
    parser.add_argument(
        "--format",
        nargs="+",
        choices=GENERATORS.keys(),
        help="Document formats to generate (default: all)",
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available formats and exit",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_formats()
        return 0
    
    print(f"🚀 Generating test documents...")
    print()
    
    return generate_documents(
        output_dir=args.output,
        formats=args.format,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
