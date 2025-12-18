"""Quality validation modules for EROS Schedule Generator.

This package contains validators for ensuring caption quality and structure
compliance with proven high-converting formulas.

Modules:
    ppv_structure: PPV caption structure validation (Winner/Bundle/Wall Campaign)
    emoji_validator: Emoji blending validation (prevents emoji overload)
    font_validator: Font format validation (prevents over-formatting)
    drip_outfit_validator: Drip content outfit consistency validation
    bundle_validator: Bundle value framing validation (Gap 7.3)
    price_validator: Price-length alignment validation (Gap 10.11/10.12)
"""

from .ppv_structure import PPVStructureValidator
from .emoji_validator import EmojiValidator, EmojiValidationResult
from .font_validator import FontFormatValidator, FontValidationResult
from .drip_outfit_validator import (
    DripOutfitValidator,
    DripOutfitValidationResult,
    validate_drip_schedule_outfits,
)
from .bundle_validator import (
    validate_bundle_value_framing,
    validate_all_bundles_in_schedule,
    BUNDLE_SEND_TYPES,
)
from .price_validator import (
    PRICE_LENGTH_MATRIX,
    MISMATCH_PENALTIES,
    PriceValidationResult,
    validate_price_length_match,
    get_optimal_price_for_length,
    calculate_rps_impact,
    validate_batch,
)

__all__ = [
    'PPVStructureValidator',
    'EmojiValidator',
    'EmojiValidationResult',
    'FontFormatValidator',
    'FontValidationResult',
    'DripOutfitValidator',
    'DripOutfitValidationResult',
    'validate_drip_schedule_outfits',
    'validate_bundle_value_framing',
    'validate_all_bundles_in_schedule',
    'BUNDLE_SEND_TYPES',
    # Price validator exports (Gap 10.11/10.12)
    'PRICE_LENGTH_MATRIX',
    'MISMATCH_PENALTIES',
    'PriceValidationResult',
    'validate_price_length_match',
    'get_optimal_price_for_length',
    'calculate_rps_impact',
    'validate_batch',
]
