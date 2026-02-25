#!/usr/bin/env python3
"""
Standalone extraction demo - extracts from PDF without database.
Shows what the full pipeline would extract and save.
"""
import os
import sys
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path("/workspaces/in-silico-crci-lab")
sys.path.insert(0, str(PROJECT_ROOT))

# Set minimal environment
os.environ.setdefault('ANTHROPIC_API_KEY', open(PROJECT_ROOT / '.env').read().split('ANTHROPIC_API_KEY=')[1].split('\n')[0])

print("═" * 70)
print("  CRCI EXTRACTION PIPELINE - STANDALONE DEMO")
print("  (Running without database - showing extracted data)")
print("═" * 70)
print()

# Import PDF extraction
try:
    import pdfplumber
    
    pdf_path = PROJECT_ROOT / "cherrier2013.pdf"
    print(f"📄 Processing: {pdf_path.name}")
    print()
    
    # Extract text from PDF
    print("[Step 1/5] Extracting PDF text...")
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text:
                full_text += f"\n--- Page {i} ---\n{text}"
        
        print(f"  ✓ Extracted {len(full_text)} characters from {len(pdf.pages)} pages")
    
    # Save full text
    output_file = "/tmp/cherrier2013_fulltext.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(full_text)
    print(f"  ✓ Saved to: {output_file}")
    print()
    
    # Show preview
    print("[Step 2/5] Text Preview (first 500 chars):")
    print("-" * 70)
    print(full_text[:500])
    print("...")
    print("-" * 70)
    print()
    
    # Import LLM client
    print("[Step 3/5] Initializing Claude API...")
    from anthropic import Anthropic
    
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("  ✗ ANTHROPIC_API_KEY not found in environment")
        sys.exit(1)
    
    client = Anthropic(api_key=api_key)
    print("  ✓ Claude API ready")
    print()
    
    # Extract study metadata
    print("[Step 4/5] Extracting study metadata with Claude...")
    
    prompt = f"""You are a scientific paper extraction agent. Analyze this research paper and extract:

1. Study Type (RCT, cohort, meta-analysis, etc.)
2. Sample Size
3. Population (who was studied)
4. Main Intervention or Exposure
5. Main Outcome Measured
6. Key Finding (1-2 sentences)

Paper text:
{full_text[:4000]}

Return as structured JSON:
{{
  "study_type": "...",
  "sample_size": ...,
  "population": "...",
  "intervention": "...",
  "outcome": "...",
  "key_finding": "..."
}}"""
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )
    
    extracted_data = response.content[0].text
    print("  ✓ Extraction complete")
    print()
    
    # Display results
    print("[Step 5/5] Extracted Data:")
    print("=" * 70)
    print(extracted_data)
    print("=" * 70)
    print()
    
    # Save results
    results_file = "/tmp/cherrier2013_extraction.json"
    with open(results_file, 'w') as f:
        f.write(extracted_data)
    
    print(f"✓ Results saved to: {results_file}")
    print()
    print("═" * 70)
    print("  DEMO COMPLETE")
    print()
    print("  In the full pipeline, this data would be:")
    print("  1. Validated (P0-Triage)")
    print("  2. Deep-extracted with 11 specialized agents (P1)")
    print("  3. Harmonized to standard units (P2)")
    print("  4. Assessed for heterogeneity (P3)")
    print("  5. Meta-analyzed if applicable (P4)")
    print("  6. Checked for publication bias (P4B)")
    print("  7. Verified for sufficiency (P5)")
    print("  8. Compiled into evidence tables (P6)")
    print("  9. Integrated into the causal DAG (P7)")
    print()
    print("  To run the full pipeline, you need PostgreSQL admin access.")
    print("═" * 70)
    
except ImportError as e:
    print(f"✗ Missing dependency: {e}")
    print("  Run: pip install pdfplumber anthropic")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
