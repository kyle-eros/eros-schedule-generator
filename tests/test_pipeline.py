#!/usr/bin/env python3
"""
Unit tests for SchedulePipeline orchestration.

Tests the 9-step pipeline flow:
    1. ANALYZE - Load creator profile
    2. MATCH CONTENT - Filter captions by vault
    3. MATCH PERSONA - Score by voice profile
    4. BUILD STRUCTURE - Create weekly time slots
    5. ASSIGN CAPTIONS - Pool-based selection
    6. GENERATE FOLLOW-UPS - Create follow-ups
    7. APPLY DRIP WINDOWS - Enforce no-PPV zones
    8. APPLY PAGE TYPE RULES - Paid vs free rules
    9. VALIDATE - Check business rules
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add scripts and tests to path
TESTS_DIR = Path(__file__).parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from fixtures import (
    MOCK_CREATOR_PAID,
    create_mock_caption,
    create_mock_schedule_config,
    create_mock_stratified_pools,
)


# =============================================================================
# MOCK DATABASE CONNECTION
# =============================================================================


class MockConnection:
    """Mock database connection for testing without database."""

    def __init__(self):
        self.row_factory = sqlite3.Row
        self._queries: list[tuple[str, tuple]] = []

    def execute(self, query: str, params: tuple = ()) -> "MockCursor":
        self._queries.append((query, params))
        return MockCursor([])


class MockCursor:
    """Mock cursor for testing."""

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._index = 0

    def fetchone(self):
        if self._index < len(self._rows):
            row = self._rows[self._index]
            self._index += 1
            return row
        return None

    def fetchall(self):
        return self._rows


# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_conn() -> MockConnection:
    """Create a mock database connection."""
    return MockConnection()


@pytest.fixture
def basic_config():
    """Create a basic schedule config for testing."""
    return create_mock_schedule_config(
        creator_id="test-creator-001",
        creator_name="testcreator",
        page_type="paid",
        week_start=date(2025, 1, 6),
        volume_level="Mid",
        ppv_per_day=4,
        mode="quick",
    )


@pytest.fixture
def mock_captions():
    """Create mock captions for testing."""
    return [
        create_mock_caption(
            caption_id=1001 + i,
            caption_text=f"Test caption {i}",
            freshness_score=80.0 - i * 5,
            performance_score=70.0 + i * 3,
            content_type_id=1,
            content_type_name="solo",
        )
        for i in range(10)
    ]


@pytest.fixture
def mock_stratified_pools():
    """Create mock stratified pools for testing."""
    return {
        1: create_mock_stratified_pools(content_type_id=1, type_name="solo"),
        2: create_mock_stratified_pools(content_type_id=2, type_name="sextape"),
    }


# =============================================================================
# PIPELINE ORCHESTRATION TESTS
# =============================================================================


class TestPipelineOrchestration:
    """Tests for SchedulePipeline orchestration."""

    def test_pipeline_initialization(self, basic_config, mock_conn):
        """Test that pipeline initializes with correct state."""
        from models import ScheduleConfig

        # Convert mock config to real ScheduleConfig
        config = ScheduleConfig(
            creator_id=basic_config.creator_id,
            creator_name=basic_config.creator_name,
            page_type=basic_config.page_type,
            week_start=basic_config.week_start,
            week_end=basic_config.week_end,
            volume_level=basic_config.volume_level,
            ppv_per_day=basic_config.ppv_per_day,
            mode=basic_config.mode,
        )

        from pipeline import SchedulePipeline

        pipeline = SchedulePipeline(config, mock_conn, mode="quick")

        assert pipeline.config == config
        assert pipeline.mode == "quick"
        assert pipeline.profile is None
        assert pipeline.captions == []
        assert pipeline.slots == []
        assert pipeline.items == []

    def test_quick_mode_completes(self, basic_config, mock_conn):
        """Test that quick mode completes all pipeline steps."""
        from models import CreatorProfile, ScheduleConfig
        from pipeline import SchedulePipeline

        config = ScheduleConfig(
            creator_id=basic_config.creator_id,
            creator_name=basic_config.creator_name,
            page_type=basic_config.page_type,
            week_start=basic_config.week_start,
            week_end=basic_config.week_end,
            volume_level=basic_config.volume_level,
            ppv_per_day=basic_config.ppv_per_day,
            mode="quick",
        )

        # Create mock profile
        mock_profile = CreatorProfile(
            creator_id="test-001",
            page_name="testcreator",
            display_name="Test Creator",
            page_type="paid",
            active_fans=5000,
            volume_level="Mid",
            primary_tone="playful",
            emoji_frequency="moderate",
            slang_level="light",
            avg_sentiment=0.7,
            best_hours=[10, 14, 18, 21],
            vault_types=[1, 2],
        )

        pipeline = SchedulePipeline(config, mock_conn, mode="quick")

        # Mock internal methods instead of module-level patches
        pipeline._execute_build_steps = MagicMock()
        pipeline._execute_assignment_step = MagicMock()
        pipeline._execute_enrichment_steps = MagicMock()
        pipeline._execute_validation_step = MagicMock()

        result = pipeline.run()

        # Verify result structure
        assert result is not None
        assert result.schedule_id is not None
        assert result.creator_id == config.creator_id
        assert result.creator_name == config.creator_name

    def test_full_mode_completes(self, basic_config, mock_conn):
        """Test that full mode completes all pipeline steps."""
        from models import ScheduleConfig
        from pipeline import SchedulePipeline

        config = ScheduleConfig(
            creator_id=basic_config.creator_id,
            creator_name=basic_config.creator_name,
            page_type=basic_config.page_type,
            week_start=basic_config.week_start,
            week_end=basic_config.week_end,
            volume_level=basic_config.volume_level,
            ppv_per_day=basic_config.ppv_per_day,
            mode="full",
        )

        pipeline = SchedulePipeline(config, mock_conn, mode="full")

        # Mock internal methods
        pipeline._execute_build_steps = MagicMock()
        pipeline._execute_assignment_step = MagicMock()
        pipeline._execute_enrichment_steps = MagicMock()
        pipeline._execute_validation_step = MagicMock()

        result = pipeline.run()

        assert result is not None
        assert result.creator_name == config.creator_name

    def test_step_order_maintained(self, basic_config, mock_conn):
        """Test that pipeline steps execute in correct order."""
        from models import ScheduleConfig
        from pipeline import SchedulePipeline

        config = ScheduleConfig(
            creator_id=basic_config.creator_id,
            creator_name=basic_config.creator_name,
            page_type=basic_config.page_type,
            week_start=basic_config.week_start,
            week_end=basic_config.week_end,
            volume_level=basic_config.volume_level,
            ppv_per_day=basic_config.ppv_per_day,
            mode="quick",
        )

        pipeline = SchedulePipeline(config, mock_conn, mode="quick")

        step_order = []

        # Patch each step to record order
        with patch.object(
            pipeline, "_execute_build_steps", side_effect=lambda: step_order.append(1)
        ):
            with patch.object(
                pipeline,
                "_execute_assignment_step",
                side_effect=lambda: step_order.append(2),
            ):
                with patch.object(
                    pipeline,
                    "_execute_enrichment_steps",
                    side_effect=lambda: step_order.append(3),
                ):
                    with patch.object(
                        pipeline,
                        "_execute_validation_step",
                        side_effect=lambda: step_order.append(4),
                    ):
                        pipeline.run()

        assert step_order == [1, 2, 3, 4], "Pipeline steps executed out of order"

    def test_validation_result_included(self, basic_config, mock_conn):
        """Test that validation results are included in final result."""
        from models import ScheduleConfig, ScheduleItem, ValidationIssue
        from pipeline import SchedulePipeline

        config = ScheduleConfig(
            creator_id=basic_config.creator_id,
            creator_name=basic_config.creator_name,
            page_type=basic_config.page_type,
            week_start=basic_config.week_start,
            week_end=basic_config.week_end,
            volume_level=basic_config.volume_level,
            ppv_per_day=basic_config.ppv_per_day,
            mode="quick",
        )

        pipeline = SchedulePipeline(config, mock_conn, mode="quick")

        # Create test items to populate result
        test_items = [
            ScheduleItem(
                item_id=1,
                creator_id="test-001",
                scheduled_date="2025-01-06",
                scheduled_time="10:00",
                item_type="ppv",
                caption_id=1001,
                caption_text="Test caption",
                freshness_score=80.0,
                performance_score=70.0,
            )
        ]

        # Set up validation issues to be added
        test_issues = [
            ValidationIssue(
                rule_name="ppv_spacing",
                severity="warning",
                message="PPV spacing below recommended",
                item_ids=(1,),
            )
        ]

        # Mock internal methods
        pipeline._execute_build_steps = MagicMock()
        pipeline._execute_assignment_step = MagicMock()
        pipeline._execute_enrichment_steps = MagicMock()

        def mock_validation():
            pipeline.items = test_items
            pipeline.result.validation_issues = test_issues
            pipeline.result.validation_passed = True

        pipeline._execute_validation_step = mock_validation

        result = pipeline.run()

        # Verify validation results included
        assert len(result.validation_issues) > 0
        assert result.validation_issues[0].rule_name == "ppv_spacing"
        assert result.validation_passed is True  # Warning doesn't fail

    def test_error_handling_creator_not_found(self, basic_config, mock_conn):
        """Test error handling when creator is not found."""
        from models import ScheduleConfig, ValidationIssue
        from pipeline import SchedulePipeline

        config = ScheduleConfig(
            creator_id=basic_config.creator_id,
            creator_name=basic_config.creator_name,
            page_type=basic_config.page_type,
            week_start=basic_config.week_start,
            week_end=basic_config.week_end,
            volume_level=basic_config.volume_level,
            ppv_per_day=basic_config.ppv_per_day,
            mode="quick",
        )

        pipeline = SchedulePipeline(config, mock_conn, mode="quick")

        # Simulate build step that fails to find creator
        def mock_build_step_creator_not_found():
            pipeline.profile = None
            pipeline.result.validation_issues.append(
                ValidationIssue(
                    rule_name="creator_not_found",
                    severity="error",
                    message=f"Creator not found: {config.creator_id}",
                )
            )
            pipeline.result.validation_passed = False

        pipeline._execute_build_steps = mock_build_step_creator_not_found
        pipeline._execute_assignment_step = MagicMock()
        pipeline._execute_enrichment_steps = MagicMock()
        pipeline._execute_validation_step = MagicMock()

        result = pipeline.run()

        assert result.validation_passed is False
        assert any(
            "not found" in issue.message.lower() for issue in result.validation_issues
        )

    def test_error_handling_no_captions(self, basic_config, mock_conn):
        """Test error handling when no captions available."""
        from models import ScheduleConfig, ValidationIssue
        from pipeline import SchedulePipeline

        config = ScheduleConfig(
            creator_id=basic_config.creator_id,
            creator_name=basic_config.creator_name,
            page_type=basic_config.page_type,
            week_start=basic_config.week_start,
            week_end=basic_config.week_end,
            volume_level=basic_config.volume_level,
            ppv_per_day=basic_config.ppv_per_day,
            mode="quick",
        )

        pipeline = SchedulePipeline(config, mock_conn, mode="quick")

        # Simulate build step that finds no captions
        def mock_build_step_no_captions():
            pipeline.captions = []
            pipeline.result.validation_issues.append(
                ValidationIssue(
                    rule_name="no_captions",
                    severity="error",
                    message="No eligible captions found with freshness >= 30",
                )
            )
            pipeline.result.validation_passed = False

        pipeline._execute_build_steps = mock_build_step_no_captions
        pipeline._execute_assignment_step = MagicMock()
        pipeline._execute_enrichment_steps = MagicMock()
        pipeline._execute_validation_step = MagicMock()

        result = pipeline.run()

        assert result.validation_passed is False
        assert any(
            "caption" in issue.message.lower() for issue in result.validation_issues
        )


# =============================================================================
# RESULT FINALIZATION TESTS
# =============================================================================


class TestResultFinalization:
    """Tests for result finalization and statistics."""

    def test_statistics_calculation(self, basic_config, mock_conn):
        """Test that result statistics are correctly calculated."""
        from models import ScheduleConfig, ScheduleItem
        from pipeline import SchedulePipeline

        config = ScheduleConfig(
            creator_id=basic_config.creator_id,
            creator_name=basic_config.creator_name,
            page_type=basic_config.page_type,
            week_start=basic_config.week_start,
            week_end=basic_config.week_end,
            volume_level=basic_config.volume_level,
            ppv_per_day=basic_config.ppv_per_day,
            mode="quick",
        )

        # Create test items with various types
        test_items = [
            ScheduleItem(
                item_id=1,
                creator_id="test-001",
                scheduled_date="2025-01-06",
                scheduled_time="10:00",
                item_type="ppv",
                caption_id=1001,
                freshness_score=80.0,
                performance_score=70.0,
            ),
            ScheduleItem(
                item_id=2,
                creator_id="test-001",
                scheduled_date="2025-01-06",
                scheduled_time="14:00",
                item_type="ppv",
                caption_id=1002,
                freshness_score=90.0,
                performance_score=60.0,
            ),
            ScheduleItem(
                item_id=3,
                creator_id="test-001",
                scheduled_date="2025-01-06",
                scheduled_time="10:25",
                item_type="bump",
                is_follow_up=True,
                parent_item_id=1,
            ),
        ]

        pipeline = SchedulePipeline(config, mock_conn, mode="quick")

        # Mock internal methods and set items directly
        pipeline._execute_build_steps = MagicMock()
        pipeline._execute_assignment_step = MagicMock()
        pipeline._execute_enrichment_steps = MagicMock()

        def mock_validation():
            pipeline.items = test_items

        pipeline._execute_validation_step = mock_validation

        result = pipeline.run()

        # Verify statistics
        assert result.total_ppvs == 2
        assert result.total_bumps == 1
        assert result.total_follow_ups == 1
        assert result.unique_captions == 2
        assert result.avg_freshness == 85.0  # (80 + 90) / 2
        assert result.avg_performance == 65.0  # (70 + 60) / 2


# =============================================================================
# RUN PIPELINE CONVENIENCE FUNCTION TESTS
# =============================================================================


class TestRunPipelineFunction:
    """Tests for the run_pipeline convenience function."""

    @patch("pipeline.SchedulePipeline")
    def test_run_pipeline_delegates_to_class(
        self, mock_pipeline_cls, basic_config, mock_conn
    ):
        """Test that run_pipeline creates pipeline and calls run()."""
        from models import ScheduleConfig
        from pipeline import run_pipeline

        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline

        config = ScheduleConfig(
            creator_id=basic_config.creator_id,
            creator_name=basic_config.creator_name,
            page_type=basic_config.page_type,
            week_start=basic_config.week_start,
            week_end=basic_config.week_end,
            volume_level=basic_config.volume_level,
            ppv_per_day=basic_config.ppv_per_day,
            mode="quick",
        )

        run_pipeline(config, mock_conn, mode="quick")

        mock_pipeline_cls.assert_called_once_with(config, mock_conn, "quick")
        mock_pipeline.run.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
