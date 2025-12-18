"""
Extract Send Type Core Tables to CSV
Exports 4 critical tables from eros_sd_main.db to properly formatted CSV files
"""

import sqlite3
import csv
import json
from pathlib import Path
from typing import Any, List, Tuple

# Configuration
DB_PATH = "/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db"
OUTPUT_DIR = "/Users/kylemerriman/Desktop/database_core_tables"

# Tables to extract
TABLES = [
    "send_types",
    "send_type_caption_requirements",
    "send_type_content_compatibility",
    "channels"
]


def format_value(value: Any) -> str:
    """
    Format a database value for CSV export.

    Args:
        value: Raw database value

    Returns:
        Formatted string representation
    """
    if value is None:
        return ""

    # Handle boolean values
    if isinstance(value, bool):
        return str(int(value))

    # Handle integers
    if isinstance(value, int):
        return str(value)

    # Handle floats
    if isinstance(value, float):
        return str(value)

    # Handle JSON fields (detect by checking if string starts with { or [)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith('{') or stripped.startswith('['):
            try:
                # Validate it's proper JSON and re-serialize compactly
                parsed = json.loads(value)
                return json.dumps(parsed, separators=(',', ':'))
            except json.JSONDecodeError:
                # Not valid JSON, treat as regular string
                pass

    return str(value)


def extract_table(conn: sqlite3.Connection, table_name: str, output_path: Path) -> Tuple[int, int]:
    """
    Extract a single table to CSV format.

    Args:
        conn: SQLite database connection
        table_name: Name of table to extract
        output_path: Path to output CSV file

    Returns:
        Tuple of (row_count, column_count)
    """
    cursor = conn.cursor()

    # Get all rows
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    # Get column names
    column_names = [description[0] for description in cursor.description]

    # Write to CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)

        # Write header
        writer.writerow(column_names)

        # Write data rows with proper formatting
        for row in rows:
            formatted_row = [format_value(value) for value in row]
            writer.writerow(formatted_row)

    return len(rows), len(column_names)


def main():
    """Main execution function."""
    print("=" * 80)
    print("SEND TYPE CORE TABLES EXTRACTION")
    print("=" * 80)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Output Directory: {OUTPUT_DIR}\n")

    # Create output directory
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    results = []

    try:
        for table_name in TABLES:
            output_file = output_dir / f"{table_name}.csv"

            print(f"Extracting: {table_name}")
            print(f"  Target: {output_file}")

            try:
                row_count, col_count = extract_table(conn, table_name, output_file)

                # Verify file was created
                if output_file.exists():
                    file_size = output_file.stat().st_size
                    print(f"  ✓ Success: {row_count} rows, {col_count} columns, {file_size:,} bytes")
                    results.append({
                        'table': table_name,
                        'rows': row_count,
                        'columns': col_count,
                        'size': file_size,
                        'status': 'SUCCESS'
                    })
                else:
                    print(f"  ✗ Failed: File not created")
                    results.append({
                        'table': table_name,
                        'status': 'FAILED'
                    })

            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
                results.append({
                    'table': table_name,
                    'status': 'ERROR',
                    'error': str(e)
                })

            print()

    finally:
        conn.close()

    # Summary
    print("=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    successful = sum(1 for r in results if r.get('status') == 'SUCCESS')
    total_rows = sum(r.get('rows', 0) for r in results)
    total_size = sum(r.get('size', 0) for r in results)

    for result in results:
        table = result['table']
        status = result['status']

        if status == 'SUCCESS':
            print(f"✓ {table}: {result['rows']} rows, {result['size']:,} bytes")
        else:
            print(f"✗ {table}: {status}")
            if 'error' in result:
                print(f"  Error: {result['error']}")

    print(f"\nTotal: {successful}/{len(TABLES)} tables extracted")
    print(f"Total Rows: {total_rows:,}")
    print(f"Total Size: {total_size:,} bytes ({total_size/1024:.1f} KB)")
    print(f"\nOutput Location: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
