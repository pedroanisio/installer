#!/bin/bash
# Generate documentation in various formats from the man page

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAN_FILE="$SCRIPT_DIR/installer.1"
OUTPUT_DIR="$SCRIPT_DIR/generated"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Generating documentation from man page..."

# Generate HTML version
if command -v groff &> /dev/null; then
    echo "Generating HTML..."
    groff -man -Thtml "$MAN_FILE" > "$OUTPUT_DIR/installer.html"
    echo "  ✓ HTML generated: $OUTPUT_DIR/installer.html"
else
    echo "  ⚠ groff not found, skipping HTML generation"
fi

# Generate PDF version
if command -v groff &> /dev/null && command -v ps2pdf &> /dev/null; then
    echo "Generating PDF..."
    groff -man -Tps "$MAN_FILE" | ps2pdf - "$OUTPUT_DIR/installer.pdf"
    echo "  ✓ PDF generated: $OUTPUT_DIR/installer.pdf"
else
    echo "  ⚠ groff or ps2pdf not found, skipping PDF generation"
fi

# Generate plain text version
if command -v man &> /dev/null; then
    echo "Generating plain text..."
    MANWIDTH=80 man "$MAN_FILE" | col -b > "$OUTPUT_DIR/installer.txt"
    echo "  ✓ Plain text generated: $OUTPUT_DIR/installer.txt"
else
    echo "  ⚠ man command not found, skipping plain text generation"
fi

# Generate Markdown version (basic conversion)
if command -v pandoc &> /dev/null; then
    echo "Generating Markdown..."
    pandoc -f man -t markdown "$MAN_FILE" -o "$OUTPUT_DIR/installer.md"
    echo "  ✓ Markdown generated: $OUTPUT_DIR/installer.md"
else
    echo "  ⚠ pandoc not found, skipping Markdown generation"
    echo "  Install pandoc for Markdown conversion: https://pandoc.org/installing.html"
fi

echo ""
echo "Documentation generation complete!"
echo "Generated files are in: $OUTPUT_DIR"
