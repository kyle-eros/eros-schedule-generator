#!/usr/bin/env python3
"""
Wave 0 Phase 0.1 - Batch Schedule Generation (Batch 1)
Generate sample schedules for first 10 creators to establish baseline.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
os.environ['EROS_DB_PATH'] = str(PROJECT_ROOT / "database" / "eros_sd_main.db")

# Import MCP server database connection
from mcp.eros_db_server import get_db_connection

# Creator batch
BATCH_1_CREATORS = [
    # Tier 1 Paid
    "miss_alexa",
    "chloe_wildd",
    "shelby_d_vip",
    "del_vip",
    # Tier 2 Paid
    "itskassielee_paid_page",
    "jazmyn_gabriella",
    "neenah",
    "selena",
    # Tier 1 Free
    "maya_hill",
    "tessatan_free"
]

WEEK_START = "2025-12-16"


def get_creator_data(conn, page_name):
    """Get comprehensive creator data."""
    cursor = conn.cursor()

    # Get creator profile
    cursor.execute("""
        SELECT
            c.creator_id,
            c.page_name,
            c.page_type,
            c.performance_tier,
            c.current_active_fans,
            c.is_active
        FROM creators c
        WHERE c.page_name = ? AND c.is_active = 1
    """, (page_name,))

    creator = cursor.fetchone()
    if not creator:
        return None

    return dict(creator)


def get_volume_config(conn, creator_id):
    """Get volume configuration for creator."""
    cursor = conn.cursor()

    # Get volume assignment
    cursor.execute("""
        SELECT
            volume_level,
            ppv_per_day,
            bump_per_day
        FROM volume_assignments
        WHERE creator_id = ?
    """, (creator_id,))

    volume = cursor.fetchone()
    if volume:
        return dict(volume)

    # Fallback to default based on fan count
    cursor.execute("""
        SELECT current_active_fans
        FROM creators
        WHERE creator_id = ?
    """, (creator_id,))

    result = cursor.fetchone()
    fans = result['current_active_fans'] if result else 0

    if fans < 1000:
        return {"volume_level": "Low", "ppv_per_day": 2, "bump_per_day": 2}
    elif fans < 5000:
        return {"volume_level": "Mid", "ppv_per_day": 3, "bump_per_day": 3}
    elif fans < 15000:
        return {"volume_level": "High", "ppv_per_day": 5, "bump_per_day": 4}
    else:
        return {"volume_level": "Ultra", "ppv_per_day": 6, "bump_per_day": 6}


def get_content_rankings(conn, creator_id):
    """Get content type rankings for creator."""
    cursor = conn.cursor()

    # Use top_content_types table
    cursor.execute("""
        SELECT
            content_type,
            rank,
            performance_tier,
            avg_earnings,
            send_count
        FROM top_content_types
        WHERE creator_id = ?
        ORDER BY rank
        LIMIT 10
    """, (creator_id,))

    results = cursor.fetchall()

    # If no creator-specific rankings, return generic content types
    if not results:
        cursor.execute("""
            SELECT
                content_type_id,
                content_type_name
            FROM content_types
            WHERE is_active = 1
            ORDER BY content_type_name
            LIMIT 10
        """)
        results = cursor.fetchall()

    return [dict(row) for row in results]


def get_captions(conn, creator_id, limit=50):
    """Get top captions for creator with freshness scoring."""
    cursor = conn.cursor()

    # Check if creator has universal access
    cursor.execute("""
        SELECT enabled FROM creator_universal_access
        WHERE creator_id = ? AND enabled = 1
    """, (creator_id,))
    has_universal = cursor.fetchone() is not None

    if has_universal:
        # Universal access - return all captions filtered by vault_matrix
        cursor.execute("""
            SELECT DISTINCT
                cb.caption_id,
                cb.caption_text,
                cb.performance_score,
                cb.caption_type,
                LENGTH(cb.caption_text) as char_length,
                COALESCE(cb.freshness_score, 50) as freshness_score,
                cb.last_used_date as last_used
            FROM caption_bank cb
            INNER JOIN vault_matrix vm
                ON cb.content_type_id = vm.content_type_id
                AND vm.creator_id = ?
                AND vm.available_quantity > 0
            WHERE cb.caption_text IS NOT NULL
                AND LENGTH(cb.caption_text) > 10
                AND cb.is_active = 1
            ORDER BY
                (COALESCE(cb.performance_score, 50) * 0.6 +
                 COALESCE(cb.freshness_score, 50) * 0.4) DESC,
                cb.performance_score DESC
            LIMIT ?
        """, (creator_id, limit))
    else:
        # No universal access - only creator-specific captions
        cursor.execute("""
            SELECT
                cb.caption_id,
                cb.caption_text,
                cb.performance_score,
                cb.caption_type,
                LENGTH(cb.caption_text) as char_length,
                COALESCE(cb.freshness_score, 50) as freshness_score,
                cb.last_used_date as last_used
            FROM caption_bank cb
            WHERE cb.caption_text IS NOT NULL
                AND LENGTH(cb.caption_text) > 10
                AND cb.is_active = 1
                AND cb.creator_id = ?
            ORDER BY
                (COALESCE(cb.performance_score, 50) * 0.6 +
                 COALESCE(cb.freshness_score, 50) * 0.4) DESC,
                cb.performance_score DESC
            LIMIT ?
        """, (creator_id, limit))

    return [dict(row) for row in cursor.fetchall()]


def get_send_types(conn, page_type):
    """Get applicable send types for page type."""
    cursor = conn.cursor()

    # Get all active send types
    # Filter by page_type_restriction if needed (paid vs free)
    cursor.execute("""
        SELECT
            send_type_id,
            send_type_key,
            display_name as send_type_name,
            category as send_type_category,
            page_type_restriction
        FROM send_types
        WHERE is_active = 1
        ORDER BY category, display_name
    """)

    all_types = [dict(row) for row in cursor.fetchall()]

    # Filter based on page type
    # 'heavy' restriction means paid pages only
    # No restriction or NULL means available for all
    filtered_types = []
    for st in all_types:
        restriction = st.get('page_type_restriction')
        if page_type == 'paid':
            # Paid pages can use all types
            filtered_types.append(st)
        elif page_type == 'free':
            # Free pages cannot use 'heavy' restricted types
            if restriction != 'heavy':
                filtered_types.append(st)

    return filtered_types


def get_best_timing(conn, creator_id):
    """Get optimal posting times for creator."""
    cursor = conn.cursor()

    # Get historical best hours
    cursor.execute("""
        SELECT
            CAST(strftime('%H', scheduled_time) AS INTEGER) as hour,
            COUNT(*) as count,
            AVG(performance_score) as avg_performance
        FROM schedule_items si
        JOIN caption_bank cb ON si.caption_id = cb.caption_id
        WHERE si.creator_id = ?
            AND si.scheduled_date >= date('now', '-30 days')
        GROUP BY hour
        ORDER BY avg_performance DESC
        LIMIT 10
    """, (creator_id,))

    timing_data = [dict(row) for row in cursor.fetchall()]

    if not timing_data:
        # Default optimal hours
        return [
            {"hour": 9, "count": 0, "avg_performance": 75},
            {"hour": 14, "count": 0, "avg_performance": 80},
            {"hour": 20, "count": 0, "avg_performance": 85}
        ]

    return timing_data


def generate_schedule_items(creator, volume, captions, send_types, timing, week_start):
    """Generate schedule items for a week."""
    items = []
    page_type = creator['page_type']

    # Filter send types by category
    revenue_types = [st for st in send_types if st['send_type_category'] == 'revenue']
    engagement_types = [st for st in send_types if st['send_type_category'] == 'engagement']
    retention_types = [st for st in send_types if st['send_type_category'] == 'retention']

    # Get optimal hours
    optimal_hours = [t['hour'] for t in timing[:5]] if timing else [9, 14, 20]

    # Start date
    start_date = datetime.strptime(week_start, "%Y-%m-%d")

    caption_idx = 0

    # Generate items for 7 days
    for day_offset in range(7):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")

        daily_items = []

        # PPV items (revenue)
        for i in range(volume['ppv_per_day']):
            if caption_idx >= len(captions):
                break

            # Select send type with variety
            send_type = revenue_types[i % len(revenue_types)] if revenue_types else None
            if not send_type:
                continue

            # Select hour
            hour_idx = (len(daily_items)) % len(optimal_hours)
            hour = optimal_hours[hour_idx]

            caption = captions[caption_idx]
            caption_idx += 1

            item = {
                "scheduled_date": date_str,
                "scheduled_time": f"{hour:02d}:00",
                "send_type_key": send_type['send_type_key'],
                "channel_key": "mass_message",
                "target_key": "all_fans",
                "caption_id": caption['caption_id'],
                "item_type": "ppv",
                "priority": 1
            }
            daily_items.append(item)

        # Bump/Engagement items
        for i in range(volume['bump_per_day']):
            if caption_idx >= len(captions):
                break

            # Mix bumps and engagement types
            if i % 2 == 0 and engagement_types:
                send_type = engagement_types[i % len(engagement_types)]
            else:
                # Use bump types if available
                bump_types = [st for st in engagement_types if 'bump' in st['send_type_key']]
                send_type = bump_types[i % len(bump_types)] if bump_types else engagement_types[0]

            # Select hour (offset from PPV times)
            hour_idx = (len(daily_items)) % len(optimal_hours)
            hour = (optimal_hours[hour_idx] + 2) % 24

            caption = captions[caption_idx]
            caption_idx += 1

            item = {
                "scheduled_date": date_str,
                "scheduled_time": f"{hour:02d}:00",
                "send_type_key": send_type['send_type_key'],
                "channel_key": "mass_message",
                "target_key": "all_fans",
                "caption_id": caption['caption_id'],
                "item_type": "engagement",
                "priority": 2
            }
            daily_items.append(item)

        # Retention items (only for paid pages, 1 per day)
        if page_type == 'paid' and retention_types and day_offset % 2 == 0:
            if caption_idx < len(captions):
                send_type = retention_types[day_offset % len(retention_types)]
                caption = captions[caption_idx]
                caption_idx += 1

                item = {
                    "scheduled_date": date_str,
                    "scheduled_time": f"{optimal_hours[0]:02d}:30",
                    "send_type_key": send_type['send_type_key'],
                    "channel_key": "mass_message",
                    "target_key": "all_fans",
                    "caption_id": caption['caption_id'],
                    "item_type": "retention",
                    "priority": 3
                }
                daily_items.append(item)

        items.extend(daily_items)

    return items


def save_schedule_to_db(conn, creator_id, week_start, items):
    """Save schedule to database."""
    cursor = conn.cursor()

    # Calculate week_end (7 days from start)
    week_start_date = datetime.strptime(week_start, "%Y-%m-%d")
    week_end_date = week_start_date + timedelta(days=6)
    week_end = week_end_date.strftime("%Y-%m-%d")

    # Create schedule template
    cursor.execute("""
        INSERT INTO schedule_templates
        (creator_id, week_start, week_end, generated_at, generated_by,
         algorithm_version, total_items, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        creator_id,
        week_start,
        week_end,
        datetime.now().isoformat(),
        'batch_generation_v1',
        '2.2.0',
        len(items),
        'generated'
    ))

    template_id = cursor.lastrowid

    # Insert schedule items
    for item in items:
        cursor.execute("""
            INSERT INTO schedule_items
            (template_id, creator_id, scheduled_date, scheduled_time,
             channel, caption_id, item_type, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            template_id,
            creator_id,
            item['scheduled_date'],
            item['scheduled_time'],
            item.get('channel_key', 'mass_message'),
            item['caption_id'],
            item.get('item_type', 'ppv'),
            item.get('priority', 1),
            'pending'
        ))

    conn.commit()
    return template_id


def calculate_character_distribution(items, captions_dict):
    """Calculate character length distribution."""
    lengths = []
    for item in items:
        caption_id = item['caption_id']
        caption = captions_dict.get(caption_id)
        if caption and 'char_length' in caption:
            lengths.append(caption['char_length'])

    if not lengths:
        return "N/A"

    in_range = sum(1 for l in lengths if 250 <= l <= 449)
    percentage = (in_range / len(lengths)) * 100
    return f"{percentage:.1f}%"


def process_creator(conn, page_name, week_start):
    """Process a single creator and generate schedule."""
    print(f"\n{'='*80}")
    print(f"Processing: {page_name}")
    print(f"{'='*80}")

    # Get creator data
    creator = get_creator_data(conn, page_name)
    if not creator:
        print(f"ERROR: Creator '{page_name}' not found or inactive")
        return None

    creator_id = creator['creator_id']

    # Get volume config
    volume = get_volume_config(conn, creator_id)

    # Get content rankings
    rankings = get_content_rankings(conn, creator_id)

    # Get captions
    captions = get_captions(conn, creator_id, limit=50)
    captions_dict = {c['caption_id']: c for c in captions}

    if not captions:
        print(f"WARNING: No captions available for {page_name}")
        return None

    # Get send types
    send_types = get_send_types(conn, creator['page_type'])

    # Get timing
    timing = get_best_timing(conn, creator_id)

    # Generate schedule
    items = generate_schedule_items(
        creator, volume, captions, send_types, timing, week_start
    )

    if not items:
        print(f"WARNING: No schedule items generated for {page_name}")
        return None

    # Save to database
    try:
        template_id = save_schedule_to_db(conn, creator_id, week_start, items)
    except Exception as e:
        print(f"ERROR saving schedule: {e}")
        return None

    # Calculate statistics
    send_types_used = list(set(item['send_type_key'] for item in items))
    char_dist = calculate_character_distribution(items, captions_dict)

    # Print summary
    summary = {
        "creator": page_name,
        "page_type": creator['page_type'],
        "performance_tier": creator['performance_tier'],
        "active_fans": creator['current_active_fans'],
        "volume_level": volume['volume_level'],
        "ppv_per_day": volume['ppv_per_day'],
        "bump_per_day": volume['bump_per_day'],
        "schedule_items": len(items),
        "unique_send_types": len(send_types_used),
        "send_types": send_types_used,
        "char_length_250_449_pct": char_dist,
        "template_id": template_id
    }

    print(f"\nCREATOR: {summary['creator']}")
    print(f"Page Type: {summary['page_type']}")
    print(f"Performance Tier: {summary['performance_tier']}")
    print(f"Active Fans: {summary['active_fans']}")
    print(f"Volume Config: {summary['ppv_per_day']} PPV/day, {summary['bump_per_day']} Bump/day ({summary['volume_level']})")
    print(f"Schedule Items: {summary['schedule_items']}")
    print(f"Send Type Diversity: {summary['unique_send_types']} types")
    print(f"Send Types Used: {', '.join(send_types_used)}")
    print(f"Character Length Distribution (250-449): {summary['char_length_250_449_pct']}")
    print(f"Template ID: {summary['template_id']}")

    return summary


def main():
    """Main execution function."""
    print("="*80)
    print("WAVE 0 PHASE 0.1 - BATCH SCHEDULE GENERATION (BATCH 1)")
    print("="*80)
    print(f"Week Start: {WEEK_START}")
    print(f"Creators to Process: {len(BATCH_1_CREATORS)}")
    print("="*80)

    conn = get_db_connection()

    results = []
    success_count = 0

    for page_name in BATCH_1_CREATORS:
        try:
            summary = process_creator(conn, page_name, WEEK_START)
            if summary:
                results.append(summary)
                success_count += 1
        except Exception as e:
            print(f"\nERROR processing {page_name}: {e}")
            import traceback
            traceback.print_exc()

    conn.close()

    # Final summary
    print(f"\n{'='*80}")
    print("BATCH COMPLETION SUMMARY")
    print(f"{'='*80}")
    print(f"Total Creators Processed: {len(BATCH_1_CREATORS)}")
    print(f"Successfully Generated: {success_count}")
    print(f"Failed: {len(BATCH_1_CREATORS) - success_count}")

    # Save results to JSON
    output_file = PROJECT_ROOT / "batch_1_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_file}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
