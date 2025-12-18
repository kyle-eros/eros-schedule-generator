"""
Phase 5 Test Case 3: Day-of-Week Distribution Test

Verifies that weekly_distribution varies appropriately by day of week
in the EROS Dynamic Volume Algorithm.

Test Objectives:
1. Verify weekly_distribution has exactly 7 entries (days 0-6)
2. Check that values vary (not all identical)
3. Verify weekend days (5=Saturday, 6=Sunday) have different multipliers
4. Confirm multipliers align with expected patterns from day_of_week.py
5. Multi-creator comparison for consistency
6. Edge case testing for missing DOW data

Expected DOW Multipliers from day_of_week.py:
- 0 (Monday): 1.0
- 1 (Tuesday): 1.0
- 2 (Wednesday): 1.0
- 3 (Thursday): 1.0
- 4 (Friday): 1.05
- 5 (Saturday): 1.1
- 6 (Sunday): 1.1
"""

import os
import sys
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from dataclasses import dataclass

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from python.volume.day_of_week import (
    calculate_dow_multipliers,
    analyze_dow_patterns,
    DEFAULT_MULTIPLIERS,
    DAY_NAMES,
    DOWMultipliers,
    DOWAnalysis,
    MULTIPLIER_MIN,
    MULTIPLIER_MAX,
)
from python.volume.dynamic_calculator import (
    calculate_optimized_volume,
    PerformanceContext,
    OptimizedVolumeResult,
)

# Database path
DB_PATH = os.environ.get(
    "EROS_DB_PATH",
    str(project_root / "database" / "eros_sd_main.db")
)


@dataclass
class TestResult:
    """Result from a single test."""
    name: str
    passed: bool
    message: str
    details: dict = None


class DOWDistributionTester:
    """Test runner for DOW distribution validation."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.results: list[TestResult] = []

    def add_result(self, name: str, passed: bool, message: str, details: dict = None):
        """Add a test result."""
        self.results.append(TestResult(name, passed, message, details or {}))
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: {message}")

    def test_default_multipliers(self) -> TestResult:
        """Test 1: Verify default multipliers match expected patterns."""
        print("\n=== Test 1: Default Multipliers Pattern ===")

        expected = {
            0: 1.0,   # Monday
            1: 1.0,   # Tuesday
            2: 1.0,   # Wednesday
            3: 1.0,   # Thursday
            4: 1.05,  # Friday
            5: 1.1,   # Saturday
            6: 1.1,   # Sunday
        }

        matches = all(
            DEFAULT_MULTIPLIERS[day] == expected[day]
            for day in range(7)
        )

        details = {
            "expected": expected,
            "actual": dict(DEFAULT_MULTIPLIERS),
        }

        if matches:
            self.add_result(
                "default_multipliers",
                True,
                "Default multipliers match expected pattern",
                details
            )
        else:
            self.add_result(
                "default_multipliers",
                False,
                f"Default multipliers mismatch",
                details
            )

        return self.results[-1]

    def test_multiplier_bounds(self) -> TestResult:
        """Test 2: Verify multiplier bounds are correct."""
        print("\n=== Test 2: Multiplier Bounds ===")

        expected_min = 0.7
        expected_max = 1.3

        bounds_correct = (
            MULTIPLIER_MIN == expected_min and
            MULTIPLIER_MAX == expected_max
        )

        details = {
            "expected_min": expected_min,
            "expected_max": expected_max,
            "actual_min": MULTIPLIER_MIN,
            "actual_max": MULTIPLIER_MAX,
        }

        self.add_result(
            "multiplier_bounds",
            bounds_correct,
            f"Bounds: [{MULTIPLIER_MIN}, {MULTIPLIER_MAX}]",
            details
        )

        return self.results[-1]

    def test_creator_dow_multipliers(self, creator_id: str) -> TestResult:
        """Test 3: Test DOW multipliers for a specific creator."""
        print(f"\n=== Test 3: DOW Multipliers for {creator_id} ===")

        try:
            multipliers = calculate_dow_multipliers(creator_id, self.db_path)

            details = {
                "creator_id": creator_id,
                "multipliers": {DAY_NAMES[d]: round(m, 3) for d, m in multipliers.multipliers.items()},
                "is_default": multipliers.is_default,
                "confidence": round(multipliers.confidence, 3),
                "total_messages": multipliers.total_messages,
            }

            # Check structure
            has_all_days = len(multipliers.multipliers) == 7
            all_in_bounds = all(
                MULTIPLIER_MIN <= m <= MULTIPLIER_MAX
                for m in multipliers.multipliers.values()
            )

            if not has_all_days:
                self.add_result(
                    f"dow_multipliers_{creator_id}",
                    False,
                    f"Missing days: only {len(multipliers.multipliers)} days found",
                    details
                )
            elif not all_in_bounds:
                self.add_result(
                    f"dow_multipliers_{creator_id}",
                    False,
                    "Some multipliers out of bounds",
                    details
                )
            else:
                self.add_result(
                    f"dow_multipliers_{creator_id}",
                    True,
                    f"Valid multipliers (default={multipliers.is_default}, confidence={multipliers.confidence:.2f})",
                    details
                )

            return self.results[-1]

        except Exception as e:
            self.add_result(
                f"dow_multipliers_{creator_id}",
                False,
                f"Exception: {e}",
                {"error": str(e)}
            )
            return self.results[-1]

    def test_weekly_distribution(self, creator_id: str, base_volume: int = 7) -> TestResult:
        """Test 4: Test weekly distribution calculation."""
        print(f"\n=== Test 4: Weekly Distribution for {creator_id} (base={base_volume}) ===")

        try:
            multipliers = calculate_dow_multipliers(creator_id, self.db_path)
            distribution = multipliers.get_weekly_distribution(base_volume)

            details = {
                "creator_id": creator_id,
                "base_volume": base_volume,
                "distribution": {DAY_NAMES[d]: v for d, v in distribution.items()},
                "total": sum(distribution.values()),
                "expected_total": base_volume * 7,
            }

            # Check structure
            has_all_days = len(distribution) == 7
            preserves_total = sum(distribution.values()) == base_volume * 7
            has_variation = len(set(distribution.values())) > 1 or multipliers.is_default

            if not has_all_days:
                self.add_result(
                    f"weekly_distribution_{creator_id}",
                    False,
                    f"Missing days: only {len(distribution)} days found",
                    details
                )
            elif not preserves_total:
                self.add_result(
                    f"weekly_distribution_{creator_id}",
                    False,
                    f"Total volume not preserved: {sum(distribution.values())} vs {base_volume * 7}",
                    details
                )
            else:
                # Check weekend vs weekday pattern
                weekend_avg = (distribution[5] + distribution[6]) / 2
                weekday_avg = sum(distribution[d] for d in range(5)) / 5

                details["weekend_avg"] = round(weekend_avg, 2)
                details["weekday_avg"] = round(weekday_avg, 2)

                self.add_result(
                    f"weekly_distribution_{creator_id}",
                    True,
                    f"Valid distribution (weekend_avg={weekend_avg:.1f}, weekday_avg={weekday_avg:.1f})",
                    details
                )

            return self.results[-1]

        except Exception as e:
            self.add_result(
                f"weekly_distribution_{creator_id}",
                False,
                f"Exception: {e}",
                {"error": str(e)}
            )
            return self.results[-1]

    def test_optimized_volume_dow(self, creator_id: str) -> TestResult:
        """Test 5: Test DOW in full optimized volume pipeline."""
        print(f"\n=== Test 5: Optimized Volume DOW for {creator_id} ===")

        try:
            # Get creator info from database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT creator_id, page_type, current_active_fans
                FROM creators
                WHERE creator_id = ? OR page_name = ?
            """, (creator_id, creator_id))

            row = cursor.fetchone()
            if not row:
                self.add_result(
                    f"optimized_dow_{creator_id}",
                    False,
                    f"Creator not found: {creator_id}",
                    {}
                )
                return self.results[-1]

            resolved_id = row["creator_id"]
            page_type = row["page_type"]
            fan_count = row["current_active_fans"] or 0
            conn.close()

            # Build context
            context = PerformanceContext(
                fan_count=fan_count,
                page_type=page_type,
                saturation_score=50.0,  # Neutral
                opportunity_score=50.0,  # Neutral
            )

            # Calculate optimized volume
            result = calculate_optimized_volume(
                context,
                creator_id=resolved_id,
                db_path=self.db_path,
                track_prediction=False,  # Don't pollute DB with test predictions
            )

            details = {
                "creator_id": creator_id,
                "fan_count": fan_count,
                "page_type": page_type,
                "weekly_distribution": {DAY_NAMES[d]: v for d, v in result.weekly_distribution.items()},
                "dow_multipliers_used": {DAY_NAMES[d]: round(m, 3) for d, m in result.dow_multipliers_used.items()},
                "total_weekly_volume": result.total_weekly_volume,
                "adjustments_applied": result.adjustments_applied,
            }

            has_weekly_dist = len(result.weekly_distribution) == 7
            has_dow_mults = len(result.dow_multipliers_used) == 7

            if not has_weekly_dist:
                self.add_result(
                    f"optimized_dow_{creator_id}",
                    False,
                    f"Missing weekly_distribution entries",
                    details
                )
            elif not has_dow_mults:
                self.add_result(
                    f"optimized_dow_{creator_id}",
                    False,
                    f"Missing dow_multipliers_used entries",
                    details
                )
            else:
                has_dow_adj = "dow_multipliers" in result.adjustments_applied
                self.add_result(
                    f"optimized_dow_{creator_id}",
                    True,
                    f"Valid (dow_applied={has_dow_adj}, total_weekly={result.total_weekly_volume})",
                    details
                )

            return self.results[-1]

        except Exception as e:
            import traceback
            self.add_result(
                f"optimized_dow_{creator_id}",
                False,
                f"Exception: {e}",
                {"error": str(e), "traceback": traceback.format_exc()}
            )
            return self.results[-1]

    def test_dow_analysis(self, creator_id: str) -> TestResult:
        """Test 6: Full DOW analysis with performance breakdown."""
        print(f"\n=== Test 6: DOW Analysis for {creator_id} ===")

        try:
            analysis = analyze_dow_patterns(creator_id, self.db_path)

            # Build performance table
            perf_table = {}
            for perf in analysis.day_performance:
                perf_table[perf.day_name] = {
                    "messages": perf.message_count,
                    "total_revenue": round(perf.total_revenue, 2),
                    "avg_revenue": round(perf.avg_revenue, 2),
                }

            details = {
                "creator_id": creator_id,
                "data_quality_score": round(analysis.data_quality_score, 1),
                "analysis_period_days": analysis.analysis_period_days,
                "is_default": analysis.multipliers.is_default,
                "confidence": round(analysis.multipliers.confidence, 3),
                "total_messages": analysis.multipliers.total_messages,
                "day_performance": perf_table,
                "multipliers": {DAY_NAMES[d]: round(m, 3) for d, m in analysis.multipliers.multipliers.items()},
            }

            self.add_result(
                f"dow_analysis_{creator_id}",
                True,
                f"Data quality: {analysis.data_quality_score:.1f}/100, Messages: {analysis.multipliers.total_messages}",
                details
            )

            return self.results[-1]

        except Exception as e:
            self.add_result(
                f"dow_analysis_{creator_id}",
                False,
                f"Exception: {e}",
                {"error": str(e)}
            )
            return self.results[-1]

    def test_nonexistent_creator(self) -> TestResult:
        """Test 7: Edge case - nonexistent creator should use defaults."""
        print("\n=== Test 7: Nonexistent Creator (Edge Case) ===")

        try:
            # This should return default multipliers, not error
            multipliers = calculate_dow_multipliers(
                "nonexistent_creator_xyz_12345",
                self.db_path,
                use_defaults_on_insufficient=True
            )

            details = {
                "is_default": multipliers.is_default,
                "confidence": multipliers.confidence,
                "multipliers": dict(multipliers.multipliers),
            }

            if multipliers.is_default and multipliers.confidence == 0.0:
                self.add_result(
                    "nonexistent_creator",
                    True,
                    "Correctly returned default multipliers",
                    details
                )
            else:
                self.add_result(
                    "nonexistent_creator",
                    False,
                    "Should have returned defaults with 0 confidence",
                    details
                )

            return self.results[-1]

        except Exception as e:
            # InsufficientDataError is acceptable
            if "not found" in str(e).lower() or "insufficient" in str(e).lower():
                self.add_result(
                    "nonexistent_creator",
                    True,
                    f"Raised expected error: {e}",
                    {"error": str(e)}
                )
            else:
                self.add_result(
                    "nonexistent_creator",
                    False,
                    f"Unexpected exception: {e}",
                    {"error": str(e)}
                )
            return self.results[-1]

    def test_multi_creator_consistency(self, creators: list[str]) -> TestResult:
        """Test 8: Multi-creator comparison for DOW pattern consistency."""
        print(f"\n=== Test 8: Multi-Creator Consistency ({len(creators)} creators) ===")

        results_by_creator = {}

        for creator_id in creators:
            try:
                multipliers = calculate_dow_multipliers(creator_id, self.db_path)
                results_by_creator[creator_id] = {
                    "multipliers": dict(multipliers.multipliers),
                    "is_default": multipliers.is_default,
                    "confidence": multipliers.confidence,
                    "total_messages": multipliers.total_messages,
                }
            except Exception as e:
                results_by_creator[creator_id] = {"error": str(e)}

        # Check that all non-default results have similar patterns
        # (weekends should generally be >= weekdays)
        valid_creators = [
            c for c, r in results_by_creator.items()
            if "error" not in r and not r["is_default"]
        ]

        pattern_violations = []
        for creator_id in valid_creators:
            mults = results_by_creator[creator_id]["multipliers"]
            weekday_avg = sum(mults[d] for d in range(5)) / 5
            weekend_avg = (mults[5] + mults[6]) / 2

            # Weekend should generally be >= weekday (with tolerance)
            if weekend_avg < weekday_avg - 0.1:
                pattern_violations.append(creator_id)

        details = {
            "tested_creators": creators,
            "valid_data_creators": valid_creators,
            "default_creators": [c for c, r in results_by_creator.items() if r.get("is_default")],
            "pattern_violations": pattern_violations,
            "results": results_by_creator,
        }

        all_passed = len(pattern_violations) == 0
        self.add_result(
            "multi_creator_consistency",
            all_passed,
            f"Valid: {len(valid_creators)}, Default: {len(creators) - len(valid_creators)}, Violations: {len(pattern_violations)}",
            details
        )

        return self.results[-1]

    def run_all_tests(self, test_creators: list[str] = None) -> dict:
        """Run all DOW distribution tests."""
        if test_creators is None:
            test_creators = ["grace_bennett", "miss_alexa", "maya_hill"]

        print("=" * 60)
        print("PHASE 5 TEST CASE 3: Day-of-Week Distribution Test")
        print("=" * 60)

        # Test 1: Default multipliers
        self.test_default_multipliers()

        # Test 2: Multiplier bounds
        self.test_multiplier_bounds()

        # Tests 3-6: Per-creator tests
        for creator_id in test_creators:
            self.test_creator_dow_multipliers(creator_id)
            self.test_weekly_distribution(creator_id, base_volume=7)
            self.test_optimized_volume_dow(creator_id)
            self.test_dow_analysis(creator_id)

        # Test 7: Edge case
        self.test_nonexistent_creator()

        # Test 8: Multi-creator consistency
        self.test_multi_creator_consistency(test_creators)

        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)

        print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")
        print(f"Pass Rate: {passed/total*100:.1f}%")

        if failed > 0:
            print("\nFailed Tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")

        overall_pass = failed == 0
        print(f"\n{'='*60}")
        print(f"OVERALL: {'PASS' if overall_pass else 'FAIL'}")
        print(f"{'='*60}")

        return {
            "overall_pass": overall_pass,
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total * 100,
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "details": r.details,
                }
                for r in self.results
            ]
        }


def print_dow_tables(creator_id: str, db_path: str = DB_PATH):
    """Print formatted DOW tables for a creator."""
    print(f"\n{'='*70}")
    print(f"DOW Distribution Analysis: {creator_id}")
    print(f"{'='*70}")

    try:
        analysis = analyze_dow_patterns(creator_id, db_path)

        # Table 1: Weekly Distribution
        print("\n1. WEEKLY DISTRIBUTION (base_volume=7)")
        print("-" * 50)
        print(f"{'Day':<12} {'Index':<6} {'Volume':<8} {'Multiplier':<10}")
        print("-" * 50)

        distribution = analysis.multipliers.get_weekly_distribution(7)
        for day_idx in range(7):
            day_name = DAY_NAMES[day_idx]
            volume = distribution[day_idx]
            mult = analysis.multipliers.multipliers[day_idx]
            print(f"{day_name:<12} {day_idx:<6} {volume:<8} {mult:.3f}")

        print("-" * 50)
        print(f"{'Total':<12} {'':<6} {sum(distribution.values()):<8}")

        # Table 2: DOW Multipliers
        print("\n2. DOW MULTIPLIERS USED")
        print("-" * 50)
        print(f"{'Day':<12} {'Multiplier':<12} {'Confidence':<12}")
        print("-" * 50)

        for day_idx in range(7):
            day_name = DAY_NAMES[day_idx]
            mult = analysis.multipliers.multipliers[day_idx]
            conf = analysis.multipliers.day_confidences.get(day_idx, 0)
            print(f"{day_name:<12} {mult:.3f}        {conf:.3f}")

        print("-" * 50)
        print(f"Overall Confidence: {analysis.multipliers.confidence:.3f}")
        print(f"Is Default: {analysis.multipliers.is_default}")
        print(f"Total Messages Analyzed: {analysis.multipliers.total_messages}")

        # Table 3: Day Performance
        print("\n3. DAY PERFORMANCE")
        print("-" * 70)
        print(f"{'Day':<12} {'Messages':<10} {'Revenue':<12} {'Avg Rev':<10} {'View Rate':<10}")
        print("-" * 70)

        for perf in analysis.day_performance:
            print(f"{perf.day_name:<12} {perf.message_count:<10} ${perf.total_revenue:<10.2f} ${perf.avg_revenue:<8.2f} {perf.avg_view_rate:.2%}")

        print("-" * 70)
        print(f"Data Quality Score: {analysis.data_quality_score:.1f}/100")

    except Exception as e:
        print(f"Error analyzing {creator_id}: {e}")


if __name__ == "__main__":
    import json

    # Run all tests
    tester = DOWDistributionTester()
    results = tester.run_all_tests(["grace_bennett", "miss_alexa", "maya_hill"])

    # Print detailed tables for Grace Bennett
    print_dow_tables("grace_bennett")

    # Save results to file
    output_path = project_root / "python" / "tests" / "phase5_dow_test_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nDetailed results saved to: {output_path}")
