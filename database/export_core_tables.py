"""
Export Creator Core Tables to CSV
Extracts creators, creator_personas, and creator_analytics_summary tables
from EROS SQLite database to properly formatted CSV files.
"""

import sqlite3
import csv
import os
from pathlib import Path
from typing import List, Tuple


def export_table_to_csv(
    db_path: str,
    table_name: str,
    output_path: str
) -> Tuple[int, int]:
    """
    Export a single table from SQLite database to CSV file.

    Args:
        db_path: Path to SQLite database file
        table_name: Name of table to export
        output_path: Destination CSV file path

    Returns:
        Tuple of (row_count, column_count)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all rows from table
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    # Get column names from cursor description
    column_names = [description[0] for description in cursor.description]

    # Write to CSV with proper handling
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(
            csvfile,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator='\n'
        )

        # Write header
        writer.writerow(column_names)

        # Write data rows, converting None to empty string
        for row in rows:
            cleaned_row = ['' if value is None else value for value in row]
            writer.writerow(cleaned_row)

    conn.close()

    return len(rows), len(column_names)


def main():
    """Main execution function."""

    # Configuration
    db_path = '/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db'
    output_dir = '/Users/kylemerriman/Desktop/database_core_tables'

    tables = [
        'creators',
        'creator_personas',
        'creator_analytics_summary'
    ]

    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("EROS Creator Core Tables Export")
    print("=" * 70)
    print(f"Database: {db_path}")
    print(f"Output Directory: {output_dir}\n")

    # Export each table
    results = {}
    for table_name in tables:
        output_path = os.path.join(output_dir, f"{table_name}.csv")

        try:
            row_count, col_count = export_table_to_csv(
                db_path,
                table_name,
                output_path
            )

            results[table_name] = {
                'status': 'SUCCESS',
                'rows': row_count,
                'columns': col_count,
                'path': output_path
            }

            print(f"✓ {table_name}")
            print(f"  Rows: {row_count}")
            print(f"  Columns: {col_count}")
            print(f"  File: {output_path}")
            print()

        except Exception as e:
            results[table_name] = {
                'status': 'FAILED',
                'error': str(e)
            }
            print(f"✗ {table_name}")
            print(f"  Error: {str(e)}")
            print()

    # Summary
    print("=" * 70)
    print("Export Summary")
    print("=" * 70)

    success_count = sum(1 for r in results.values() if r['status'] == 'SUCCESS')
    total_rows = sum(r.get('rows', 0) for r in results.values() if r['status'] == 'SUCCESS')

    print(f"Tables Exported: {success_count}/{len(tables)}")
    print(f"Total Rows: {total_rows}")
    print(f"Output Location: {output_dir}")
    print()

    # Verify files exist
    print("File Verification:")
    for table_name in tables:
        output_path = os.path.join(output_dir, f"{table_name}.csv")
        exists = os.path.exists(output_path)
        size = os.path.getsize(output_path) if exists else 0
        status = "✓" if exists and size > 0 else "✗"
        print(f"{status} {table_name}.csv ({size:,} bytes)")

    print("\nExport complete!")


if __name__ == "__main__":
    main()
