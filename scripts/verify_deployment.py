#!/usr/bin/env python3
"""Deployment verification script for EROS Schedule Generator skills package.

This script verifies all components are functional before production use.

Usage:
    python3 verify_deployment.py
    python3 verify_deployment.py --quick  # Skip schedule generation test
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Resolve paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent  # .claude/skills/eros-schedule-generator -> project root
SCRIPTS_DIR = SCRIPT_DIR / "scripts"
REFERENCES_DIR = SCRIPT_DIR / "references"
SQL_DIR = SCRIPT_DIR / "assets" / "sql"
DB_PATH = PROJECT_ROOT / "database" / "eros_sd_main.db"


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")


def print_pass(text: str) -> None:
    """Print a passing check."""
    print(f"  {Colors.GREEN}[PASS]{Colors.RESET} {text}")


def print_fail(text: str) -> None:
    """Print a failing check."""
    print(f"  {Colors.RED}[FAIL]{Colors.RESET} {text}")


def print_warn(text: str) -> None:
    """Print a warning."""
    print(f"  {Colors.YELLOW}[WARN]{Colors.RESET} {text}")


def check_skill_md() -> tuple[bool, int]:
    """Verify SKILL.md exists and is under 500 lines."""
    skill_path = SCRIPT_DIR / "SKILL.md"
    if not skill_path.exists():
        print_fail("SKILL.md not found")
        return False, 0

    with open(skill_path) as f:
        lines = f.readlines()

    line_count = len(lines)
    if line_count > 500:
        print_fail(f"SKILL.md has {line_count} lines (max 500)")
        return False, line_count

    # Check for frontmatter
    content = "".join(lines)
    if not content.startswith("---"):
        print_fail("SKILL.md missing frontmatter")
        return False, line_count

    if "name:" not in content or "description:" not in content:
        print_fail("SKILL.md missing required frontmatter fields")
        return False, line_count

    print_pass(f"SKILL.md valid ({line_count} lines)")
    return True, line_count


def check_scripts() -> tuple[bool, list[str]]:
    """Verify all required scripts exist and show help."""
    required_scripts = [
        "generate_schedule.py",
        "analyze_creator.py",
        "select_captions.py",
        "validate_schedule.py",
        "calculate_freshness.py",
        "match_persona.py",
    ]

    missing = []
    failed = []

    for script in required_scripts:
        script_path = SCRIPTS_DIR / script
        if not script_path.exists():
            print_fail(f"Script missing: {script}")
            missing.append(script)
            continue

        # Test --help
        try:
            result = subprocess.run(
                [sys.executable, str(script_path), "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                print_fail(f"Script failed --help: {script}")
                failed.append(script)
            else:
                print_pass(f"Script functional: {script}")
        except subprocess.TimeoutExpired:
            print_fail(f"Script timed out: {script}")
            failed.append(script)
        except Exception as e:
            print_fail(f"Script error: {script} - {e}")
            failed.append(script)

    all_ok = not missing and not failed
    return all_ok, missing + failed


def check_sql_files() -> tuple[bool, list[str]]:
    """Verify all SQL files exist."""
    required_sql = [
        "get_creator_profile.sql",
        "get_available_captions.sql",
        "get_optimal_hours.sql",
        "get_vault_inventory.sql",
        "get_active_creators.sql",
        "get_performance_trends.sql",
    ]

    missing = []
    for sql_file in required_sql:
        sql_path = SQL_DIR / sql_file
        if not sql_path.exists():
            print_fail(f"SQL file missing: {sql_file}")
            missing.append(sql_file)
        else:
            print_pass(f"SQL file present: {sql_file}")

    return not missing, missing


def check_references() -> tuple[bool, list[str]]:
    """Verify all reference files exist."""
    required_refs = [
        "architecture.md",
        "scheduling_rules.md",
        "extraction_map.md",
        "database_performance.md",
        "analytics_algorithms.md",
        "validation_report.md",
    ]

    missing = []
    for ref in required_refs:
        ref_path = REFERENCES_DIR / ref
        if not ref_path.exists():
            print_fail(f"Reference missing: {ref}")
            missing.append(ref)
        else:
            print_pass(f"Reference present: {ref}")

    return not missing, missing


def check_database() -> bool:
    """Verify database connection."""
    if not DB_PATH.exists():
        print_fail(f"Database not found: {DB_PATH}")
        return False

    import sqlite3
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.execute("SELECT COUNT(*) FROM creators WHERE is_active = 1")
        count = cursor.fetchone()[0]
        conn.close()
        print_pass(f"Database connected: {count} active creators")
        return True
    except Exception as e:
        print_fail(f"Database error: {e}")
        return False


def test_schedule_generation() -> tuple[bool, float]:
    """Test actual schedule generation."""
    import sqlite3

    # Get first active creator
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute("SELECT page_name FROM creators WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        print_fail("No active creators found")
        return False, 0.0

    creator = row[0]
    script = SCRIPTS_DIR / "generate_schedule.py"

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--creator", creator, "--week", "2025-W01"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        elapsed = time.time() - start

        if result.returncode != 0:
            print_fail(f"Schedule generation failed: {result.stderr[:200]}")
            return False, elapsed

        # Check output has expected content
        output = result.stdout
        if "Weekly Schedule" not in output:
            print_fail("Schedule output missing expected header")
            return False, elapsed

        if "PPV" not in output:
            print_fail("Schedule output missing PPV items")
            return False, elapsed

        print_pass(f"Schedule generated for {creator} in {elapsed:.2f}s")
        return True, elapsed
    except subprocess.TimeoutExpired:
        print_fail("Schedule generation timed out (>120s)")
        return False, 120.0
    except Exception as e:
        print_fail(f"Schedule generation error: {e}")
        return False, 0.0


def main():
    parser = argparse.ArgumentParser(description="Verify EROS skills package deployment")
    parser.add_argument("--quick", action="store_true", help="Skip schedule generation test")
    args = parser.parse_args()

    print_header("EROS Schedule Generator - Deployment Verification")

    results = {}

    # 1. Check SKILL.md
    print_header("1. SKILL.md Verification")
    skill_ok, line_count = check_skill_md()
    results["skill_md"] = skill_ok

    # 2. Check scripts
    print_header("2. Scripts Verification")
    scripts_ok, failed_scripts = check_scripts()
    results["scripts"] = scripts_ok

    # 3. Check SQL files
    print_header("3. SQL Files Verification")
    sql_ok, missing_sql = check_sql_files()
    results["sql"] = sql_ok

    # 4. Check references
    print_header("4. References Verification")
    refs_ok, missing_refs = check_references()
    results["references"] = refs_ok

    # 5. Check database
    print_header("5. Database Connection")
    db_ok = check_database()
    results["database"] = db_ok

    # 6. Test schedule generation
    gen_time = 0.0
    if not args.quick:
        print_header("6. Schedule Generation Test")
        gen_ok, gen_time = test_schedule_generation()
        results["generation"] = gen_ok
    else:
        print_header("6. Schedule Generation Test (SKIPPED)")
        print_warn("Schedule generation test skipped with --quick flag")
        results["generation"] = None

    # Summary
    print_header("Deployment Verification Summary")

    all_passed = all(v is True for v in results.values() if v is not None)

    print(f"  SKILL.md:     {'PASS' if results['skill_md'] else 'FAIL'} ({line_count} lines)")
    print(f"  Scripts:      {'PASS' if results['scripts'] else 'FAIL'} (6/6 functional)")
    print(f"  SQL Files:    {'PASS' if results['sql'] else 'FAIL'} (6/6 present)")
    print(f"  References:   {'PASS' if results['references'] else 'FAIL'} (6/6 present)")
    print(f"  Database:     {'PASS' if results['database'] else 'FAIL'}")
    if results["generation"] is not None:
        print(f"  Generation:   {'PASS' if results['generation'] else 'FAIL'} ({gen_time:.2f}s)")
    else:
        print(f"  Generation:   SKIPPED")

    print()
    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}DEPLOYMENT READY{Colors.RESET}")
        print(f"\nSkills package location: {SCRIPT_DIR}")
        print(f"\nQuick start:")
        print(f"  python3 {SCRIPTS_DIR}/generate_schedule.py --creator <name> --week 2025-W01")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}DEPLOYMENT NOT READY - Fix issues above{Colors.RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
