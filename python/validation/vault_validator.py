"""
Vault Validator - Content availability validation with ranked preferences.

Validates content availability against vault matrix and selects optimal
content types based on send type requirements and ranked preferences.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from python.logging_config import get_logger, log_fallback
from python.models.send_type import (
    PPV_TYPES,
    PPV_REVENUE_TYPES,
    resolve_send_type_key,
)

# Module logger
logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ContentTypePreference:
    """Content type with preference metadata.

    Attributes:
        content_type: The content type identifier (e.g., 'video', 'photo_set')
        priority: Priority rank (1 = highest priority)
        requires_media: Whether this content type requires media files
        min_items: Minimum number of items needed
        description: Human-readable description
    """

    content_type: str
    priority: int
    requires_media: bool = True
    min_items: int = 1
    description: str = ""


@dataclass
class VaultValidationResult:
    """Result of vault content validation.

    Attributes:
        valid: Whether validation passed (content is available)
        selected_type: The content type selected for use
        fallback_used: Whether a fallback content type was used
        fallback_level: 0 = primary, 1+ = fallback level used
        available_types: List of all available content types
        unavailable_types: List of unavailable content types that were checked
        reason: Explanation of the validation result
        metadata: Additional validation metadata
    """

    valid: bool
    selected_type: Optional[str]
    fallback_used: bool
    fallback_level: int
    available_types: List[str] = field(default_factory=list)
    unavailable_types: List[str] = field(default_factory=list)
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class VaultValidator:
    """Validates content availability against vault matrix."""

    # Default content type preferences by send type category
    # Priority 1 = most preferred, higher numbers = fallback options
    DEFAULT_PREFERENCES: Dict[str, List[ContentTypePreference]] = {
        # PPV revenue types prefer video content
        "ppv_unlock": [
            ContentTypePreference("video", 1, True, 1, "Full video content"),
            ContentTypePreference("photo_set", 2, True, 3, "Photo set (3+ images)"),
            ContentTypePreference("photo", 3, True, 1, "Single photo"),
        ],
        "ppv_wall": [
            ContentTypePreference("video", 1, True, 1, "Full video content"),
            ContentTypePreference("photo_set", 2, True, 3, "Photo set (3+ images)"),
            ContentTypePreference("photo", 3, True, 1, "Single photo"),
        ],
        "tip_goal": [
            ContentTypePreference("video", 1, True, 1, "Exclusive video content"),
            ContentTypePreference("photo_set", 2, True, 5, "Premium photo set"),
            ContentTypePreference("custom", 3, True, 1, "Custom content promise"),
        ],
        # Bundle types prefer collections
        "bundle": [
            ContentTypePreference("video_bundle", 1, True, 3, "Multiple videos"),
            ContentTypePreference("mixed_bundle", 2, True, 5, "Videos + photos"),
            ContentTypePreference("photo_bundle", 3, True, 10, "Large photo set"),
        ],
        "flash_bundle": [
            ContentTypePreference("video_bundle", 1, True, 2, "Quick video bundle"),
            ContentTypePreference("photo_bundle", 2, True, 5, "Flash photo set"),
        ],
        "snapchat_bundle": [
            ContentTypePreference("snap_content", 1, True, 5, "Snapchat-style content"),
            ContentTypePreference("video", 2, True, 1, "Standard video"),
        ],
        # Engagement types have flexible requirements
        "bump_normal": [
            ContentTypePreference("photo", 1, True, 1, "Attention-grabbing photo"),
            ContentTypePreference("selfie", 2, True, 1, "Casual selfie"),
            ContentTypePreference("text_only", 3, False, 0, "Text only message"),
        ],
        "bump_flyer": [
            ContentTypePreference("flyer", 1, True, 1, "Promotional flyer"),
            ContentTypePreference("graphic", 2, True, 1, "Custom graphic"),
        ],
        # PPV followup uses original content reference
        "ppv_followup": [
            ContentTypePreference("reference", 1, False, 0, "Reference to original PPV"),
            ContentTypePreference("preview", 2, True, 1, "Preview/teaser"),
        ],
    }

    # Send types that don't require vault content
    NO_CONTENT_REQUIRED: frozenset[str] = frozenset({
        "bump_text_only",
        "dm_farm",
        "like_farm",
        "renew_on_message",
    })

    def __init__(
        self,
        custom_preferences: Optional[Dict[str, List[ContentTypePreference]]] = None
    ) -> None:
        """Initialize vault validator.

        Args:
            custom_preferences: Optional custom content type preferences to merge
                with defaults.
        """
        self.preferences = self.DEFAULT_PREFERENCES.copy()
        if custom_preferences:
            self.preferences.update(custom_preferences)

    def validate_content_for_send_type(
        self,
        send_type_key: str,
        vault_availability: Dict[str, bool],
        recommended_types: Optional[List[str]] = None
    ) -> VaultValidationResult:
        """Validate content availability with ranked preference.

        Checks vault availability against send type requirements, using
        ranked preferences to select the best available content type.
        Falls back through preferences if primary type is unavailable.

        Args:
            send_type_key: The send type requiring content
            vault_availability: Dict mapping content_type -> is_available
            recommended_types: Optional ordered list of preferred content types
                (overrides default preferences if provided)

        Returns:
            VaultValidationResult with validation status and selected type
        """
        # Resolve deprecated send types
        resolved_key = resolve_send_type_key(send_type_key)

        # Check if this send type requires content at all
        if resolved_key in self.NO_CONTENT_REQUIRED:
            return VaultValidationResult(
                valid=True,
                selected_type=None,
                fallback_used=False,
                fallback_level=0,
                reason=f"Send type '{resolved_key}' does not require vault content",
                metadata={"content_required": False}
            )

        # Get preferences for this send type
        if recommended_types:
            # Convert recommended list to preferences
            preferences = [
                ContentTypePreference(ct, idx + 1)
                for idx, ct in enumerate(recommended_types)
            ]
        else:
            preferences = self.preferences.get(resolved_key, [])

        # If no preferences defined, use generic fallback
        if not preferences:
            preferences = [
                ContentTypePreference("video", 1, True, 1, "Default video"),
                ContentTypePreference("photo", 2, True, 1, "Default photo"),
                ContentTypePreference("any", 3, True, 1, "Any available content"),
            ]
            logger.warning(
                f"No content preferences defined for send_type '{resolved_key}', "
                "using generic fallback preferences"
            )

        # Track validation progress
        available_types: List[str] = []
        unavailable_types: List[str] = []

        # Check each preference in priority order
        for idx, pref in enumerate(preferences):
            content_type = pref.content_type
            is_available = vault_availability.get(content_type, False)

            if is_available:
                available_types.append(content_type)

                # First available type wins
                if len(available_types) == 1:
                    fallback_used = idx > 0
                    if fallback_used:
                        log_fallback(
                            logger,
                            operation="validate_vault_content",
                            fallback_reason=f"Primary content type '{preferences[0].content_type}' unavailable",
                            fallback_action=f"Using fallback content type '{content_type}'",
                            send_type_key=resolved_key,
                            fallback_level=idx
                        )

                    return VaultValidationResult(
                        valid=True,
                        selected_type=content_type,
                        fallback_used=fallback_used,
                        fallback_level=idx,
                        available_types=available_types,
                        unavailable_types=unavailable_types,
                        reason=f"Content type '{content_type}' available (priority {pref.priority})",
                        metadata={
                            "content_required": True,
                            "requires_media": pref.requires_media,
                            "min_items": pref.min_items,
                            "preference_description": pref.description
                        }
                    )
            else:
                unavailable_types.append(content_type)

        # Check for "any" content as last resort
        any_available = [
            ct for ct, available in vault_availability.items()
            if available and ct not in unavailable_types
        ]

        if any_available:
            selected = any_available[0]
            log_fallback(
                logger,
                operation="validate_vault_content",
                fallback_reason="All preferred content types unavailable",
                fallback_action=f"Using any available content: '{selected}'",
                send_type_key=resolved_key,
                fallback_level=len(preferences),
                severity="high"
            )

            return VaultValidationResult(
                valid=True,
                selected_type=selected,
                fallback_used=True,
                fallback_level=len(preferences),
                available_types=any_available,
                unavailable_types=unavailable_types,
                reason=f"Using any available content '{selected}' (last resort fallback)",
                metadata={
                    "content_required": True,
                    "last_resort": True
                }
            )

        # No content available at all
        logger.error(
            f"No content available for send_type '{resolved_key}'",
            extra={
                "send_type_key": resolved_key,
                "checked_types": unavailable_types,
                "vault_availability": vault_availability
            }
        )

        return VaultValidationResult(
            valid=False,
            selected_type=None,
            fallback_used=False,
            fallback_level=-1,
            available_types=[],
            unavailable_types=unavailable_types,
            reason=f"No content available for send_type '{resolved_key}'. "
                   f"Checked types: {', '.join(unavailable_types)}",
            metadata={
                "content_required": True,
                "vault_empty": not any(vault_availability.values())
            }
        )

    def validate_ppv_content(
        self,
        send_type_key: str,
        vault_availability: Dict[str, bool],
        page_type: str = "both"
    ) -> VaultValidationResult:
        """Validate content specifically for PPV send types.

        Specialized validation for PPV types with page-type-aware preferences.

        Args:
            send_type_key: PPV send type key
            vault_availability: Dict mapping content_type -> is_available
            page_type: 'paid', 'free', or 'both'

        Returns:
            VaultValidationResult with PPV-specific validation
        """
        resolved_key = resolve_send_type_key(send_type_key)

        # Verify this is a PPV type
        if resolved_key not in PPV_TYPES and resolved_key not in PPV_REVENUE_TYPES:
            logger.warning(
                f"validate_ppv_content called for non-PPV type '{resolved_key}'"
            )

        # PPV types always prefer video content
        ppv_preferences = [
            ContentTypePreference("video", 1, True, 1, "Premium video content"),
            ContentTypePreference("video_clip", 2, True, 1, "Video clip"),
            ContentTypePreference("photo_set", 3, True, 5, "Exclusive photo set"),
            ContentTypePreference("photo", 4, True, 1, "Single exclusive photo"),
        ]

        # Run standard validation with PPV preferences
        result = self.validate_content_for_send_type(
            resolved_key,
            vault_availability,
            [p.content_type for p in ppv_preferences]
        )

        # Add PPV-specific metadata
        result.metadata["ppv_type"] = resolved_key
        result.metadata["page_type"] = page_type

        return result

    def get_available_content_types(
        self,
        vault_availability: Dict[str, bool]
    ) -> List[str]:
        """Get list of all available content types from vault.

        Args:
            vault_availability: Dict mapping content_type -> is_available

        Returns:
            List of available content type names
        """
        return [ct for ct, available in vault_availability.items() if available]

    def get_missing_content_types(
        self,
        send_type_key: str,
        vault_availability: Dict[str, bool]
    ) -> List[str]:
        """Get list of preferred but unavailable content types.

        Args:
            send_type_key: The send type to check preferences for
            vault_availability: Dict mapping content_type -> is_available

        Returns:
            List of unavailable content type names in priority order
        """
        resolved_key = resolve_send_type_key(send_type_key)
        preferences = self.preferences.get(resolved_key, [])

        missing = []
        for pref in preferences:
            if not vault_availability.get(pref.content_type, False):
                missing.append(pref.content_type)

        return missing
