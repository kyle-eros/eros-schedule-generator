#!/usr/bin/env python3
"""
Vault Matrix Import/Export Tool

Bidirectional sync between Google Sheets (wide format CSV) and database (normalized vault_matrix).

Usage:
    # Export database to CSV for editing
    python vault_matrix_sync.py export --output vault_matrix.csv

    # Import edited CSV back to database
    python vault_matrix_sync.py import --input vault_matrix_edited.csv

    # Dry-run to preview changes before applying
    python vault_matrix_sync.py import --input vault_matrix_edited.csv --dry-run
"""

import os
import sys
import sqlite3
import pandas as pd
import click
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict

# Database path
DB_PATH = os.getenv(
    'EROS_DB_PATH',
    '/Users/kylemerriman/Developer/EROS-SD-MAIN-PROJECT/database/eros_sd_main.db'
)
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)


class VaultMatrixSync:
    """Handles bidirectional sync between CSV and vault_matrix table."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.log_file = LOG_DIR / f"vault_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    def _log(self, message: str, level: str = "INFO"):
        """Log message to file and console."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        with open(self.log_file, 'a') as f:
            f.write(log_entry + '\n')

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def validate_content_types(self, conn: sqlite3.Connection, content_type_names: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate that all content_type names exist in database.

        Returns:
            (is_valid, invalid_names)
        """
        cursor = conn.cursor()
        cursor.execute("SELECT type_name FROM content_types")
        valid_types = {row['type_name'] for row in cursor.fetchall()}

        invalid_types = [name for name in content_type_names if name not in valid_types]

        if invalid_types:
            self._log(f"Invalid content types found: {invalid_types}", "ERROR")
            return False, invalid_types

        return True, []

    def resolve_creator_id(self, conn: sqlite3.Connection, page_name: str) -> Optional[str]:
        """
        Resolve page_name to creator_id.

        Args:
            page_name: Creator page name from CSV

        Returns:
            creator_id if found, None otherwise
        """
        cursor = conn.cursor()
        cursor.execute(
            "SELECT creator_id FROM creators WHERE page_name = ?",
            (page_name,)
        )
        row = cursor.fetchone()
        return row['creator_id'] if row else None

    def get_content_type_id(self, conn: sqlite3.Connection, type_name: str) -> Optional[int]:
        """
        Get content_type_id from type_name.

        Args:
            type_name: Content type name (e.g., 'anal', 'boy_girl')

        Returns:
            content_type_id if found, None otherwise
        """
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content_type_id FROM content_types WHERE type_name = ?",
            (type_name,)
        )
        row = cursor.fetchone()
        return row['content_type_id'] if row else None

    def export_to_csv(self, output_path: str) -> bool:
        """
        Export vault_matrix from database to wide-format CSV.

        CSV Format:
            page_name, anal, boy_girl, squirt, ..., vault_notes
            alexia, 1, 0, 1, ..., "Notes here"

        Args:
            output_path: Path to output CSV file

        Returns:
            True if successful, False otherwise
        """
        try:
            self._log(f"Starting export to {output_path}")
            conn = self._get_connection()

            # Query vault_matrix with content_type names
            query = """
            SELECT
                c.page_name,
                ct.type_name as content_type,
                vm.has_content,
                c.vault_notes
            FROM vault_matrix vm
            JOIN creators c ON vm.creator_id = c.creator_id
            JOIN content_types ct ON vm.content_type_id = ct.content_type_id
            ORDER BY c.page_name, ct.priority_tier, ct.type_name
            """

            self._log("Querying database...")
            df = pd.read_sql_query(query, conn)
            self._log(f"Retrieved {len(df)} rows from database")

            # Pivot long → wide format
            self._log("Pivoting to wide format...")
            df_wide = df.pivot_table(
                index='page_name',
                columns='content_type',
                values='has_content',
                aggfunc='first',
                fill_value=0
            ).reset_index()

            # Add vault_notes column
            # Get vault_notes separately since it's per-creator, not per (creator, content_type)
            vault_notes_df = df[['page_name', 'vault_notes']].drop_duplicates()
            df_wide = df_wide.merge(vault_notes_df, on='page_name', how='left')

            # Reorder columns: page_name, content types (sorted), vault_notes
            content_cols = [col for col in df_wide.columns if col not in ['page_name', 'vault_notes']]
            content_cols_sorted = sorted(content_cols)
            final_cols = ['page_name'] + content_cols_sorted + ['vault_notes']
            df_wide = df_wide[final_cols]

            # Export to CSV
            self._log(f"Exporting {len(df_wide)} creators to CSV...")
            df_wide.to_csv(output_path, index=False)

            self._log(f"✓ Export successful: {len(df_wide)} creators, {len(content_cols_sorted)} content types", "SUCCESS")
            conn.close()
            return True

        except Exception as e:
            self._log(f"Export failed: {str(e)}", "ERROR")
            return False

    def import_from_csv(self, input_path: str, dry_run: bool = False) -> bool:
        """
        Import wide-format CSV into normalized vault_matrix table.

        CSV Format:
            page_name, anal, boy_girl, squirt, ..., vault_notes
            alexia, 1, 0, 1, ..., "Notes here"

        Args:
            input_path: Path to input CSV file
            dry_run: If True, show changes without applying

        Returns:
            True if successful, False otherwise
        """
        try:
            self._log(f"Starting import from {input_path} (dry_run={dry_run})")

            # Load CSV
            self._log("Loading CSV...")
            df = pd.read_csv(input_path)
            self._log(f"Loaded {len(df)} creators from CSV")

            # Validate required columns
            if 'page_name' not in df.columns:
                self._log("ERROR: CSV must have 'page_name' column", "ERROR")
                return False

            # Separate content type columns from page_name and vault_notes
            content_type_cols = [
                col for col in df.columns
                if col not in ['page_name', 'vault_notes']
            ]
            self._log(f"Found {len(content_type_cols)} content type columns")

            conn = self._get_connection()

            # Validate content types exist in database
            self._log("Validating content types...")
            is_valid, invalid_types = self.validate_content_types(conn, content_type_cols)
            if not is_valid:
                self._log(f"Invalid content types: {invalid_types}", "ERROR")
                self._log("Please check your CSV header names against content_types.type_name", "ERROR")
                conn.close()
                return False

            # Transform wide → long format
            self._log("Transforming to long format...")
            df_long = df.melt(
                id_vars=['page_name'] + (['vault_notes'] if 'vault_notes' in df.columns else []),
                value_vars=content_type_cols,
                var_name='content_type_name',
                value_name='has_content'
            )

            # Coerce has_content to 0/1
            df_long['has_content'] = df_long['has_content'].fillna(0).astype(int)
            df_long['has_content'] = df_long['has_content'].apply(lambda x: 1 if x > 0 else 0)

            # Resolve page_name → creator_id
            self._log("Resolving creator IDs...")
            creator_id_map = {}
            unknown_creators = []
            for page_name in df_long['page_name'].unique():
                creator_id = self.resolve_creator_id(conn, page_name)
                if creator_id:
                    creator_id_map[page_name] = creator_id
                else:
                    unknown_creators.append(page_name)

            if unknown_creators:
                self._log(f"WARNING: Unknown creators (will skip): {unknown_creators}", "WARNING")

            df_long = df_long[df_long['page_name'].isin(creator_id_map.keys())]
            df_long['creator_id'] = df_long['page_name'].map(creator_id_map)

            # Resolve content_type_name → content_type_id
            self._log("Resolving content type IDs...")
            content_type_id_map = {}
            for type_name in df_long['content_type_name'].unique():
                content_type_id = self.get_content_type_id(conn, type_name)
                if content_type_id:
                    content_type_id_map[type_name] = content_type_id

            df_long['content_type_id'] = df_long['content_type_name'].map(content_type_id_map)

            # Drop rows with missing mappings
            df_long = df_long.dropna(subset=['creator_id', 'content_type_id'])

            total_updates = len(df_long)
            self._log(f"Prepared {total_updates} vault_matrix updates")

            if dry_run:
                self._log("=== DRY RUN - Changes Preview ===", "INFO")
                self._log(f"Would update {total_updates} vault_matrix entries")
                self._log("\nSample changes:")
                sample = df_long.head(10)
                for _, row in sample.iterrows():
                    self._log(f"  {row['page_name']}: {row['content_type_name']} = {row['has_content']}")
                self._log("\n=== END DRY RUN ===", "INFO")
                conn.close()
                return True

            # Apply updates to vault_matrix
            self._log("Applying updates to vault_matrix...")
            cursor = conn.cursor()

            upsert_query = """
            INSERT INTO vault_matrix (creator_id, content_type_id, has_content, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(creator_id, content_type_id)
            DO UPDATE SET
                has_content = excluded.has_content,
                updated_at = datetime('now')
            """

            update_data = df_long[['creator_id', 'content_type_id', 'has_content']].values.tolist()
            cursor.executemany(upsert_query, update_data)
            self._log(f"Updated {cursor.rowcount} vault_matrix entries")

            # Update creator vault_notes if column exists
            if 'vault_notes' in df.columns:
                self._log("Updating creator vault_notes...")
                vault_notes_data = []
                for _, row in df.iterrows():
                    creator_id = creator_id_map.get(row['page_name'])
                    if creator_id:
                        vault_notes_data.append((row.get('vault_notes'), creator_id))

                cursor.executemany(
                    "UPDATE creators SET vault_notes = ? WHERE creator_id = ?",
                    vault_notes_data
                )
                self._log(f"Updated {cursor.rowcount} creator vault_notes")

            conn.commit()
            self._log(f"✓ Import successful: {total_updates} updates applied", "SUCCESS")
            conn.close()
            return True

        except Exception as e:
            self._log(f"Import failed: {str(e)}", "ERROR")
            import traceback
            self._log(traceback.format_exc(), "ERROR")
            return False


@click.group()
def cli():
    """Vault Matrix Import/Export Tool"""
    pass


@cli.command()
@click.option('--output', '-o', required=True, help='Output CSV file path')
def export(output: str):
    """Export vault_matrix from database to CSV (wide format)."""
    syncer = VaultMatrixSync(DB_PATH)
    success = syncer.export_to_csv(output)
    sys.exit(0 if success else 1)


@cli.command()
@click.option('--input', '-i', 'input_path', required=True, help='Input CSV file path')
@click.option('--dry-run', is_flag=True, help='Preview changes without applying')
def import_csv(input_path: str, dry_run: bool):
    """Import CSV (wide format) into vault_matrix table."""
    syncer = VaultMatrixSync(DB_PATH)
    success = syncer.import_from_csv(input_path, dry_run=dry_run)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    cli()
