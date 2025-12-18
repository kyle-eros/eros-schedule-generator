"""
MCP Server Contract Tests - JSON Schema validation for all 17 MCP tool responses.

These tests define and validate the response schemas for each MCP tool to ensure
API contracts are maintained. This prevents breaking changes in response formats.

Schemas cover:
- Required fields
- Field types
- Enum values where applicable
- Nested object structures
"""

import json
from typing import Any

import pytest

try:
    from jsonschema import ValidationError, validate
except ImportError:
    pytest.skip("jsonschema not installed", allow_module_level=True)


# =============================================================================
# RESPONSE SCHEMAS FOR ALL 17 MCP TOOLS
# =============================================================================


# Schema for creator profile response
CREATOR_PROFILE_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "creator": {
                    "type": ["object", "null"],
                    "properties": {
                        "creator_id": {"type": "string"},
                        "page_name": {"type": "string"},
                        "page_type": {"type": "string", "enum": ["paid", "free"]},
                        "display_name": {"type": ["string", "null"]},
                        "subscription_price": {"type": ["number", "null"]},
                        "timezone": {"type": ["string", "null"]},
                        "current_active_fans": {"type": ["integer", "null"]},
                        "current_total_earnings": {"type": ["number", "null"]},
                        "performance_tier": {"type": ["integer", "null"], "minimum": 1, "maximum": 5},
                        "is_active": {"type": ["integer", "null"]},
                    },
                },
                "analytics_summary": {"type": ["object", "null"]},
                "volume_assignment": {"type": ["object", "null"]},
                "top_content_types": {"type": "array"},
            },
            "required": ["creator"],
        },
    ],
}

# Schema for active creators response
ACTIVE_CREATORS_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "creators": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "creator_id": {"type": "string"},
                            "page_name": {"type": "string"},
                            "page_type": {"type": ["string", "null"]},
                            "performance_tier": {"type": ["integer", "null"]},
                            "volume_level": {"type": ["string", "null"]},
                        },
                    },
                },
                "count": {"type": "integer", "minimum": 0},
            },
            "required": ["creators", "count"],
        },
    ],
}

# Schema for top captions response
TOP_CAPTIONS_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "captions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "caption_id": {"type": "integer"},
                            "caption_text": {"type": "string"},
                            "caption_type": {"type": ["string", "null"]},
                            "performance_score": {"type": ["number", "null"]},
                            "freshness_score": {"type": ["number", "null"]},
                            "content_type_name": {"type": ["string", "null"]},
                        },
                    },
                },
                "count": {"type": "integer", "minimum": 0},
                "send_type_key": {"type": "string"},
            },
            "required": ["captions", "count"],
        },
    ],
}

# Schema for best timing response
BEST_TIMING_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "timezone": {"type": "string"},
                "best_hours": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "hour": {"type": "integer", "minimum": 0, "maximum": 23},
                            "avg_earnings": {"type": ["number", "null"]},
                            "message_count": {"type": "integer"},
                        },
                    },
                },
                "best_days": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "day_of_week": {"type": ["integer", "null"]},
                            "day_name": {"type": "string"},
                            "avg_earnings": {"type": ["number", "null"]},
                            "message_count": {"type": "integer"},
                        },
                    },
                },
                "analysis_period_days": {"type": "integer"},
            },
            "required": ["timezone", "best_hours", "best_days"],
        },
    ],
}

# Schema for volume assignment response
VOLUME_ASSIGNMENT_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "volume_level": {"type": ["string", "null"], "enum": ["Low", "Mid", "High", "Ultra", None]},
                "ppv_per_day": {"type": ["integer", "null"]},
                "bump_per_day": {"type": ["integer", "null"]},
                "assigned_at": {"type": ["string", "null"]},
                "assigned_reason": {"type": ["string", "null"]},
                "message": {"type": "string"},
            },
        },
    ],
}

# Schema for performance trends response
PERFORMANCE_TRENDS_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "saturation_score": {"type": ["number", "null"]},
                "opportunity_score": {"type": ["number", "null"]},
                "avg_revenue_per_send": {"type": ["number", "null"]},
                "view_rate_trend": {"type": ["string", "null"]},
                "purchase_rate_trend": {"type": ["string", "null"]},
                "recommended_volume_delta": {"type": ["integer", "null"]},
                "message": {"type": "string"},
            },
        },
    ],
}

# Schema for content type rankings response
CONTENT_TYPE_RANKINGS_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "rankings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content_type": {"type": "string"},
                            "rank": {"type": "integer"},
                            "performance_tier": {"type": "string", "enum": ["TOP", "MID", "LOW", "AVOID"]},
                            "avg_earnings": {"type": ["number", "null"]},
                            "confidence_score": {"type": ["number", "null"]},
                        },
                    },
                },
                "top_types": {"type": "array", "items": {"type": "string"}},
                "mid_types": {"type": "array", "items": {"type": "string"}},
                "low_types": {"type": "array", "items": {"type": "string"}},
                "avoid_types": {"type": "array", "items": {"type": "string"}},
                "analysis_date": {"type": ["string", "null"]},
                "message": {"type": "string"},
            },
            "required": ["rankings"],
        },
    ],
}

# Schema for persona profile response
PERSONA_PROFILE_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "creator": {
                    "type": "object",
                    "properties": {
                        "creator_id": {"type": "string"},
                        "page_name": {"type": "string"},
                        "display_name": {"type": ["string", "null"]},
                        "persona_type": {"type": ["string", "null"]},
                    },
                },
                "persona": {
                    "type": ["object", "null"],
                    "properties": {
                        "primary_tone": {"type": ["string", "null"]},
                        "secondary_tone": {"type": ["string", "null"]},
                        "emoji_frequency": {"type": ["string", "null"]},
                        "slang_level": {"type": ["string", "null"]},
                    },
                },
                "voice_samples": {"type": "object"},
            },
            "required": ["creator", "persona"],
        },
    ],
}

# Schema for vault availability response
VAULT_AVAILABILITY_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "available_content": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "vault_id": {"type": "integer"},
                            "content_type_id": {"type": "integer"},
                            "type_name": {"type": "string"},
                            "has_content": {"type": "integer"},
                            "quantity_available": {"type": ["integer", "null"]},
                        },
                    },
                },
                "content_types": {"type": "array", "items": {"type": "string"}},
                "total_items": {"type": "integer", "minimum": 0},
            },
            "required": ["available_content", "content_types", "total_items"],
        },
    ],
}

# Schema for save schedule response
SAVE_SCHEDULE_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "success": {"type": "boolean"},
                "template_id": {"type": "integer"},
                "items_created": {"type": "integer", "minimum": 0},
                "week_start": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                "week_end": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["success", "template_id", "items_created"],
        },
    ],
}

# Schema for save schedule input validation
SAVE_SCHEDULE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "creator_id": {"type": "string", "minLength": 1, "maxLength": 100},
        "week_start": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scheduled_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "scheduled_time": {"type": "string", "pattern": "^\\d{2}:\\d{2}$"},
                    "item_type": {"type": "string"},
                    "channel": {"type": "string"},
                    "send_type_key": {"type": "string"},
                    "channel_key": {"type": "string"},
                    "target_key": {"type": "string"},
                    "caption_id": {"type": ["integer", "null"]},
                    "caption_text": {"type": ["string", "null"]},
                    "suggested_price": {"type": ["number", "null"]},
                    "priority": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["scheduled_date", "scheduled_time", "item_type", "channel"],
            },
        },
    },
    "required": ["creator_id", "week_start", "items"],
}

# Schema for execute query response
EXECUTE_QUERY_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "results": {"type": "array"},
                "count": {"type": "integer", "minimum": 0},
                "columns": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["results", "count", "columns"],
        },
    ],
}

# Schema for send types response
SEND_TYPES_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "send_types": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "send_type_id": {"type": "integer"},
                            "send_type_key": {"type": "string"},
                            "category": {"type": "string", "enum": ["revenue", "engagement", "retention"]},
                            "display_name": {"type": "string"},
                            "page_type_restriction": {"type": "string", "enum": ["paid", "free", "both"]},
                            "requires_media": {"type": "integer"},
                            "requires_flyer": {"type": "integer"},
                            "max_per_day": {"type": ["integer", "null"]},
                            "max_per_week": {"type": ["integer", "null"]},
                            "is_active": {"type": "integer"},
                        },
                        "required": ["send_type_id", "send_type_key", "category"],
                    },
                },
                "count": {"type": "integer", "minimum": 0},
            },
            "required": ["send_types", "count"],
        },
    ],
}

# Schema for send type details response
SEND_TYPE_DETAILS_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "send_type": {
                    "type": "object",
                    "properties": {
                        "send_type_id": {"type": "integer"},
                        "send_type_key": {"type": "string"},
                        "category": {"type": "string"},
                        "display_name": {"type": "string"},
                        "description": {"type": ["string", "null"]},
                        "purpose": {"type": ["string", "null"]},
                        "strategy": {"type": ["string", "null"]},
                        "requires_media": {"type": "integer"},
                        "requires_flyer": {"type": "integer"},
                        "requires_price": {"type": "integer"},
                        "has_expiration": {"type": "integer"},
                        "default_expiration_hours": {"type": ["integer", "null"]},
                        "can_have_followup": {"type": "integer"},
                        "followup_delay_minutes": {"type": ["integer", "null"]},
                        "caption_length": {"type": ["string", "null"]},
                        "max_per_day": {"type": ["integer", "null"]},
                        "max_per_week": {"type": ["integer", "null"]},
                    },
                    "required": ["send_type_id", "send_type_key", "category"],
                },
                "caption_requirements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "caption_type": {"type": "string"},
                            "priority": {"type": "integer"},
                            "notes": {"type": ["string", "null"]},
                        },
                        "required": ["caption_type", "priority"],
                    },
                },
            },
            "required": ["send_type", "caption_requirements"],
        },
    ],
}

# Schema for send type captions response
SEND_TYPE_CAPTIONS_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "captions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "caption_id": {"type": "integer"},
                            "caption_text": {"type": "string"},
                            "caption_type": {"type": ["string", "null"]},
                            "performance_score": {"type": ["number", "null"]},
                            "freshness_score": {"type": ["number", "null"]},
                            "send_type_priority": {"type": ["integer", "null"]},
                        },
                    },
                },
                "count": {"type": "integer", "minimum": 0},
                "send_type_key": {"type": "string"},
            },
            "required": ["captions", "count", "send_type_key"],
        },
    ],
}

# Schema for channels response
CHANNELS_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "channels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "integer"},
                            "channel_key": {"type": "string"},
                            "display_name": {"type": "string"},
                            "description": {"type": ["string", "null"]},
                            "supports_targeting": {"type": "integer"},
                            "targeting_options": {"type": ["object", "array", "string", "null"]},
                            "requires_manual_send": {"type": "integer"},
                            "is_active": {"type": "integer"},
                        },
                        "required": ["channel_id", "channel_key"],
                    },
                },
                "count": {"type": "integer", "minimum": 0},
            },
            "required": ["channels", "count"],
        },
    ],
}

# Schema for audience targets response
AUDIENCE_TARGETS_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "targets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "target_id": {"type": "integer"},
                            "target_key": {"type": "string"},
                            "display_name": {"type": "string"},
                            "description": {"type": ["string", "null"]},
                            "filter_type": {"type": ["string", "null"]},
                            "filter_criteria": {"type": ["object", "string", "null"]},
                            "applicable_page_types": {"type": ["array", "string", "null"]},
                            "applicable_channels": {"type": ["array", "string", "null"]},
                            "typical_reach_percentage": {"type": ["number", "null"]},
                            "is_active": {"type": "integer"},
                        },
                        "required": ["target_id", "target_key"],
                    },
                },
                "count": {"type": "integer", "minimum": 0},
            },
            "required": ["targets", "count"],
        },
    ],
}

# Schema for volume config response
VOLUME_CONFIG_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "error": {"type": "string"}
            },
            "required": ["error"],
        },
        {
            "properties": {
                "volume_level": {"type": ["string", "null"], "enum": ["Low", "Mid", "High", "Ultra", None]},
                "ppv_per_day": {"type": ["integer", "null"]},
                "bump_per_day": {"type": ["integer", "null"]},
                "revenue_items_per_day": {"type": "integer"},
                "engagement_items_per_day": {"type": "integer"},
                "retention_items_per_day": {"type": "integer"},
                "bundle_per_week": {"type": "integer"},
                "game_per_week": {"type": "integer"},
                "followup_per_day": {"type": "integer"},
                "assigned_at": {"type": ["string", "null"]},
                "assigned_reason": {"type": ["string", "null"]},
                "message": {"type": "string"},
            },
        },
    ],
}


# =============================================================================
# CONTRACT VALIDATION TESTS
# =============================================================================


class TestCreatorProfileContract:
    """Contract tests for get_creator_profile response."""

    @pytest.mark.unit
    def test_valid_creator_profile_response(self):
        """Test valid creator profile response matches schema."""
        response = {
            "creator": {
                "creator_id": "test_001",
                "page_name": "testcreator",
                "page_type": "paid",
                "display_name": "Test Creator",
                "subscription_price": 9.99,
                "timezone": "America/Los_Angeles",
                "current_active_fans": 5000,
                "current_total_earnings": 50000.0,
                "performance_tier": 3,
                "is_active": 1,
            },
            "analytics_summary": None,
            "volume_assignment": None,
            "top_content_types": [],
        }
        validate(response, CREATOR_PROFILE_SCHEMA)

    @pytest.mark.unit
    def test_error_response_matches_schema(self):
        """Test error response matches schema."""
        response = {"error": "Creator not found"}
        validate(response, CREATOR_PROFILE_SCHEMA)

    @pytest.mark.unit
    def test_invalid_page_type_fails_validation(self):
        """Test invalid page_type fails validation."""
        response = {
            "creator": {
                "creator_id": "test_001",
                "page_name": "testcreator",
                "page_type": "invalid",  # Invalid enum value
            },
        }
        with pytest.raises(ValidationError):
            validate(response, CREATOR_PROFILE_SCHEMA)


class TestActiveCreatorsContract:
    """Contract tests for get_active_creators response."""

    @pytest.mark.unit
    def test_valid_active_creators_response(self):
        """Test valid active creators response matches schema."""
        response = {
            "creators": [
                {
                    "creator_id": "test_001",
                    "page_name": "testcreator",
                    "page_type": "paid",
                    "performance_tier": 3,
                    "volume_level": "High",
                }
            ],
            "count": 1,
        }
        validate(response, ACTIVE_CREATORS_SCHEMA)

    @pytest.mark.unit
    def test_empty_creators_list(self):
        """Test empty creators list matches schema."""
        response = {"creators": [], "count": 0}
        validate(response, ACTIVE_CREATORS_SCHEMA)


class TestSendTypesContract:
    """Contract tests for get_send_types response."""

    @pytest.mark.unit
    def test_valid_send_types_response(self):
        """Test valid send types response matches schema."""
        response = {
            "send_types": [
                {
                    "send_type_id": 1,
                    "send_type_key": "ppv_unlock",
                    "category": "revenue",
                    "display_name": "PPV Unlock",
                    "page_type_restriction": "both",
                    "requires_media": 1,
                    "requires_flyer": 0,
                    "max_per_day": 4,
                    "max_per_week": 20,
                    "is_active": 1,
                }
            ],
            "count": 1,
        }
        validate(response, SEND_TYPES_SCHEMA)

    @pytest.mark.unit
    def test_invalid_category_fails_validation(self):
        """Test invalid category fails validation."""
        response = {
            "send_types": [
                {
                    "send_type_id": 1,
                    "send_type_key": "test",
                    "category": "invalid",  # Invalid enum value
                }
            ],
            "count": 1,
        }
        with pytest.raises(ValidationError):
            validate(response, SEND_TYPES_SCHEMA)


class TestSaveScheduleContract:
    """Contract tests for save_schedule input and response."""

    @pytest.mark.unit
    def test_valid_save_schedule_input(self):
        """Test valid save_schedule input matches schema."""
        input_data = {
            "creator_id": "test_creator_001",
            "week_start": "2025-01-06",
            "items": [
                {
                    "scheduled_date": "2025-01-06",
                    "scheduled_time": "10:00",
                    "item_type": "ppv",
                    "channel": "mass_message",
                    "send_type_key": "ppv_unlock",
                    "caption_id": 101,
                    "priority": 1,
                }
            ],
        }
        validate(input_data, SAVE_SCHEDULE_INPUT_SCHEMA)

    @pytest.mark.unit
    def test_valid_save_schedule_response(self):
        """Test valid save_schedule response matches schema."""
        response = {
            "success": True,
            "template_id": 123,
            "items_created": 5,
            "week_start": "2025-01-06",
            "week_end": "2025-01-12",
            "warnings": [],
        }
        validate(response, SAVE_SCHEDULE_SCHEMA)

    @pytest.mark.unit
    def test_save_schedule_with_warnings(self):
        """Test save_schedule response with warnings matches schema."""
        response = {
            "success": True,
            "template_id": 123,
            "items_created": 5,
            "week_start": "2025-01-06",
            "week_end": "2025-01-12",
            "warnings": ["Item 0: Unknown send_type_key 'unknown'"],
        }
        validate(response, SAVE_SCHEDULE_SCHEMA)

    @pytest.mark.unit
    def test_invalid_date_format_fails_validation(self):
        """Test invalid date format fails validation."""
        input_data = {
            "creator_id": "test_creator",
            "week_start": "01-06-2025",  # Invalid format (should be YYYY-MM-DD)
            "items": [],
        }
        with pytest.raises(ValidationError):
            validate(input_data, SAVE_SCHEDULE_INPUT_SCHEMA)


class TestExecuteQueryContract:
    """Contract tests for execute_query response."""

    @pytest.mark.unit
    def test_valid_query_response(self):
        """Test valid query response matches schema."""
        response = {
            "results": [{"creator_id": "test_001", "page_name": "testcreator"}],
            "count": 1,
            "columns": ["creator_id", "page_name"],
        }
        validate(response, EXECUTE_QUERY_SCHEMA)

    @pytest.mark.unit
    def test_error_query_response(self):
        """Test error query response matches schema."""
        response = {"error": "Only SELECT queries are allowed"}
        validate(response, EXECUTE_QUERY_SCHEMA)


class TestChannelsContract:
    """Contract tests for get_channels response."""

    @pytest.mark.unit
    def test_valid_channels_response(self):
        """Test valid channels response matches schema."""
        response = {
            "channels": [
                {
                    "channel_id": 1,
                    "channel_key": "mass_message",
                    "display_name": "Mass Message",
                    "description": "Send mass messages to fans",
                    "supports_targeting": 1,
                    "targeting_options": ["all_fans", "active_fans"],
                    "requires_manual_send": 0,
                    "is_active": 1,
                }
            ],
            "count": 1,
        }
        validate(response, CHANNELS_SCHEMA)


class TestVolumeConfigContract:
    """Contract tests for get_volume_config response."""

    @pytest.mark.unit
    def test_valid_volume_config_response(self):
        """Test valid volume config response matches schema."""
        response = {
            "volume_level": "High",
            "ppv_per_day": 4,
            "bump_per_day": 3,
            "revenue_items_per_day": 6,
            "engagement_items_per_day": 5,
            "retention_items_per_day": 2,
            "bundle_per_week": 3,
            "game_per_week": 2,
            "followup_per_day": 4,
            "assigned_at": "2025-01-01 12:00:00",
            "assigned_reason": "Performance based",
        }
        validate(response, VOLUME_CONFIG_SCHEMA)

    @pytest.mark.unit
    def test_no_assignment_response(self):
        """Test no assignment response matches schema."""
        response = {
            "volume_level": None,
            "ppv_per_day": None,
            "bump_per_day": None,
            "message": "No active volume assignment found",
        }
        validate(response, VOLUME_CONFIG_SCHEMA)


class TestAudienceTargetsContract:
    """Contract tests for get_audience_targets response."""

    @pytest.mark.unit
    def test_valid_targets_response(self):
        """Test valid audience targets response matches schema."""
        response = {
            "targets": [
                {
                    "target_id": 1,
                    "target_key": "all_fans",
                    "display_name": "All Fans",
                    "description": "Target all fans",
                    "filter_type": "none",
                    "applicable_page_types": ["paid", "free"],
                    "applicable_channels": ["mass_message", "wall_post"],
                    "typical_reach_percentage": 100.0,
                    "is_active": 1,
                }
            ],
            "count": 1,
        }
        validate(response, AUDIENCE_TARGETS_SCHEMA)


class TestTopCaptionsContract:
    """Contract tests for get_top_captions response."""

    @pytest.mark.unit
    def test_valid_captions_response(self):
        """Test valid captions response matches schema."""
        response = {
            "captions": [
                {
                    "caption_id": 101,
                    "caption_text": "Exclusive content!",
                    "caption_type": "ppv_unlock",
                    "performance_score": 85.0,
                    "freshness_score": 70.0,
                    "content_type_name": "video",
                }
            ],
            "count": 1,
        }
        validate(response, TOP_CAPTIONS_SCHEMA)


class TestBestTimingContract:
    """Contract tests for get_best_timing response."""

    @pytest.mark.unit
    def test_valid_timing_response(self):
        """Test valid timing response matches schema."""
        response = {
            "timezone": "America/Los_Angeles",
            "best_hours": [
                {"hour": 19, "avg_earnings": 150.0, "message_count": 50},
                {"hour": 21, "avg_earnings": 120.0, "message_count": 45},
            ],
            "best_days": [
                {"day_of_week": 5, "day_name": "Saturday", "avg_earnings": 200.0, "message_count": 30},
            ],
            "analysis_period_days": 30,
        }
        validate(response, BEST_TIMING_SCHEMA)


class TestContentTypeRankingsContract:
    """Contract tests for get_content_type_rankings response."""

    @pytest.mark.unit
    def test_valid_rankings_response(self):
        """Test valid rankings response matches schema."""
        response = {
            "rankings": [
                {
                    "content_type": "solo_video",
                    "rank": 1,
                    "performance_tier": "TOP",
                    "avg_earnings": 150.0,
                    "confidence_score": 0.95,
                }
            ],
            "top_types": ["solo_video"],
            "mid_types": ["photo_set"],
            "low_types": ["text_only"],
            "avoid_types": [],
            "analysis_date": "2025-01-01",
        }
        validate(response, CONTENT_TYPE_RANKINGS_SCHEMA)


class TestPersonaProfileContract:
    """Contract tests for get_persona_profile response."""

    @pytest.mark.unit
    def test_valid_persona_response(self):
        """Test valid persona response matches schema."""
        response = {
            "creator": {
                "creator_id": "test_001",
                "page_name": "testcreator",
                "display_name": "Test Creator",
                "persona_type": "playful",
            },
            "persona": {
                "primary_tone": "flirty",
                "secondary_tone": "playful",
                "emoji_frequency": "moderate",
                "slang_level": "low",
            },
            "voice_samples": {},
        }
        validate(response, PERSONA_PROFILE_SCHEMA)


class TestSendTypeDetailsContract:
    """Contract tests for get_send_type_details response."""

    @pytest.mark.unit
    def test_valid_details_response(self):
        """Test valid send type details response matches schema."""
        response = {
            "send_type": {
                "send_type_id": 1,
                "send_type_key": "ppv_unlock",
                "category": "revenue",
                "display_name": "PPV Unlock",
                "description": "Pay-per-view unlock content (pics + videos)",
                "purpose": "Generate direct revenue",
                "strategy": "Send during peak hours",
                "requires_media": 1,
                "requires_flyer": 1,
                "requires_price": 1,
                "has_expiration": 0,
                "default_expiration_hours": None,
                "can_have_followup": 1,
                "followup_delay_minutes": 20,
                "caption_length": "long",
                "max_per_day": 4,
                "max_per_week": None,
            },
            "caption_requirements": [
                {"caption_type": "ppv_unlock", "priority": 1, "notes": "Primary caption type"},
                {"caption_type": "ppv_teaser", "priority": 2, "notes": None},
            ],
        }
        validate(response, SEND_TYPE_DETAILS_SCHEMA)


class TestVaultAvailabilityContract:
    """Contract tests for get_vault_availability response."""

    @pytest.mark.unit
    def test_valid_vault_response(self):
        """Test valid vault response matches schema."""
        response = {
            "available_content": [
                {
                    "vault_id": 1,
                    "content_type_id": 1,
                    "type_name": "solo_video",
                    "has_content": 1,
                    "quantity_available": 50,
                }
            ],
            "content_types": ["solo_video"],
            "total_items": 50,
        }
        validate(response, VAULT_AVAILABILITY_SCHEMA)
