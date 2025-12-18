# Followup Selector Quick Start

5-minute guide to using the Type-Specific Followup Selector.

## Basic Usage

```python
from python.caption.followup_selector import select_followup_caption
from datetime import date

# For schedule generation (deterministic)
caption = select_followup_caption(
    parent_ppv_type='bundle',
    creator_id='creator_alexia',
    schedule_date=date(2025, 12, 16)
)
# → "OF glitched and sent that for way too cheap, grab it before i fix it 😳"

# For ad-hoc usage (random)
caption = select_followup_caption(parent_ppv_type='solo')
# → Random selection from solo templates
```

## With Schedule Items

```python
from python.caption.followup_selector import get_followup_for_schedule_item

# Schedule item from database
item = {
    'ppv_style': 'sextape',
    'price': 35.00,
    'content_type': 'b/g'
}

caption = get_followup_for_schedule_item(
    item,
    creator_id='creator_alexia',
    schedule_date=date(2025, 12, 16)
)
# → Sextape-specific followup caption
```

## Template Types

| Type     | Tone                              | Example                                    |
|----------|-----------------------------------|--------------------------------------------|
| winner   | Excited, exclusive                | "omg cant believe u actually won! ..."     |
| bundle   | Urgent, pricing error             | "HOLY SHIT I FUCKED UP that bundle ..."    |
| solo     | Playful, challenging              | "you must be likin dick or somthin ..."    |
| sextape  | Hype, premium quality             | "bby you have to see this... literally ..." |
| default  | Generic, safe                     | "hey babe did you see what i sent? ..."    |

## Key Features

**Deterministic**: Same inputs = same output (for reproducibility)
**Type-specific**: Authentic tone matching PPV content
**Fallback**: Unknown types use default templates
**Logging**: All selections logged with structured context

## Testing

```bash
# Run tests
python3 test_followup_selector.py

# Run demo
python3 demo_followup_selector.py
```

## Integration

### In followup-generator Agent

```python
from python.caption.followup_selector import select_followup_caption

def generate_followup(ppv_item, creator_id, schedule_date):
    caption = select_followup_caption(
        parent_ppv_type=ppv_item['ppv_style'],
        creator_id=creator_id,
        schedule_date=schedule_date
    )
    return {
        'caption_text': caption,
        'is_followup': True,
        'parent_item_id': ppv_item['id']
    }
```

### In Schedule Assembler

```python
from python.caption.followup_selector import get_followup_for_schedule_item

for item in schedule_items:
    if item.get('is_followup'):
        parent = find_parent_item(item['parent_item_id'])
        item['caption_text'] = get_followup_for_schedule_item(
            parent,
            creator_id=creator_id,
            schedule_date=schedule_date
        )
```

## Common Patterns

### Generate Multiple Followups

```python
from datetime import date, timedelta

creator_id = 'creator_alexia'
start_date = date(2025, 12, 16)

# Generate followups for a week
for day in range(7):
    current_date = start_date + timedelta(days=day)
    caption = select_followup_caption(
        parent_ppv_type='bundle',
        creator_id=creator_id,
        schedule_date=current_date
    )
    print(f"{current_date}: {caption}")
```

### Handle Missing PPV Style

```python
# If ppv_style might be missing
ppv_type = item.get('ppv_style', 'default')
caption = select_followup_caption(
    parent_ppv_type=ppv_type,
    creator_id=creator_id,
    schedule_date=schedule_date
)
```

### Type-Specific Logic

```python
# Different handling by type
if ppv_type == 'winner':
    delay_minutes = 5  # Quick followup for winners
elif ppv_type == 'bundle':
    delay_minutes = 15  # Let urgency build
else:
    delay_minutes = 20  # Standard delay

caption = select_followup_caption(
    parent_ppv_type=ppv_type,
    creator_id=creator_id,
    schedule_date=schedule_date
)
```

## Need More?

- **Full documentation**: See `README.md`
- **Implementation details**: See `followup_selector.py`
- **Test suite**: See `../test_followup_selector.py`
- **Demonstration**: See `../demo_followup_selector.py`
