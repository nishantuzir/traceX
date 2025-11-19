import os
import sys
from tracex.lineage_extractor.extractor import DbtColumnLineageExtractor
from tracex.report.generator import TraceXReportGenerator

# Fixed version
version = "1.10"

print(f"Processing dbt version {version}...")

manifest_path = f"tests/test_data/{version}/manifest.json"
catalog_path = f"tests/test_data/{version}/catalog.json"

# Output must be 'dist/' for GitHub Pages
output_dir = "dist"

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Check if input files exist
if not os.path.exists(manifest_path):
    print(f"Error: Manifest file not found: {manifest_path}")
    sys.exit(1)

if not os.path.exists(catalog_path):
    print(f"Error: Catalog file not found: {catalog_path}")
    sys.exit(1)

try:
    # Extract lineage
    extractor = DbtColumnLineageExtractor(
        manifest_path=manifest_path,
        catalog_path=catalog_path
    )

    # Generate HTML report
    report_generator = TraceXReportGenerator(extractor)
    report_generator.generate_report(output_dir=output_dir)

    # Verify output file was created
    output_file = os.path.join(output_dir, "index.html")
    if not os.path.exists(output_file):
        print(f"Error: Output file was not created: {output_file}")
        sys.exit(1)

    print(f"Report generated successfully in {output_file}")
except Exception as e:
    print(f"Error generating report: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
