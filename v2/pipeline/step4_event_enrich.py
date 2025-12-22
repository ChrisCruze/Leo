"""
Step 4: Event Enrichment Pipeline

This script enriches qualified event profiles by:
1. Filtering to essential fields for event matching
2. Cleaning HTML from descriptions
3. Extracting day of week from startDate
4. Extracting host names from ownerId lookup
5. Calculating common occupations from participants
6. Calculating common interests from participants
7. Calculating average age from participants
8. Extracting participant names with occupations
9. Detecting low occupancy events
10. Generating comprehensive human-readable summaries

FIELD SCHEMAS:
=============

Input Event Schema (from qualified_events.json):
- _id: string (MongoDB ObjectId)
- id: string (same as _id)
- name: string
- startDate: string (ISO 8601 date, e.g., "2025-12-28T22:00:00.000Z")
- endDate: string (ISO 8601 date)
- venueName: string
- neighborhood: string
- categories: array of strings
- features: array of strings (optional)
- maxParticipants: number
- participants: array of strings (email addresses)
- description: string (may contain HTML)
- ownerId: string (MongoDB ObjectId of host user)

Output Enriched Event Schema:
- id: string
- name: string
- startDate: string (ISO 8601)
- endDate: string (ISO 8601)
- venueName: string
- neighborhood: string
- categories: array of strings
- features: array of strings (optional)
- maxParticipants: number
- participant_count: number (calculated: len(participants))
- description: string (cleaned of HTML)
- day_of_week: string (e.g., "Monday", "Friday")
- host_name: string (from ownerId lookup)
- common_occupations: array of strings (top 3-5)
- common_interests: array of strings (top 3-5)
- average_age: number or null (rounded integer)
- has_low_occupancy: boolean
- participant_names: array of strings (format: "FirstName LastName (Occupation)" or "FirstName LastName")
- summary: string (human-readable summary sentence)

DATA STRUCTURES:
===============

users_lookup_by_email: dict[str, dict]
    - Key: user email (string)
    - Value: user object (dict)

users_lookup_by_id: dict[str, dict]
    - Key: user _id (string)
    - Value: user object (dict)

events: list[dict]
    - Each event has: _id, name, startDate, participants (list of emails), ownerId, description, etc.
"""

import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def setup_logging(log_dir):
    """
    Set up logging to both console and file.
    
    Args:
        log_dir: Directory path for log files
        
    Returns:
        Tuple of (logger, log_file_path)
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'event_enrich_{timestamp}.log'
    
    logger = logging.getLogger('event_enrich')
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger, log_file


def load_qualified_events(filepath):
    """
    Load qualified events from JSON file.
    
    Args:
        filepath: Path to qualified_events.json file
        
    Returns:
        List of event dictionaries
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        events = json.load(f)
    return events


def load_all_users(filepath):
    """
    Load all users from JSON file for lookup purposes.
    
    Args:
        filepath: Path to users.json file
        
    Returns:
        List of user dictionaries
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        users = json.load(f)
    return users


def parse_iso_date(date_string):
    """
    Parse ISO 8601 date string with 'Z' timezone to datetime object.
    
    Handles format: "2019-08-05T17:00:00.000Z"
    
    Args:
        date_string: ISO 8601 date string with 'Z' timezone
        
    Returns:
        datetime object in UTC timezone or None if invalid
    """
    if not date_string:
        return None
    # Replace 'Z' with '+00:00' for fromisoformat compatibility
    if date_string.endswith('Z'):
        date_string = date_string[:-1] + '+00:00'
    return datetime.fromisoformat(date_string)


def clean_html(html_string):
    """
    Remove HTML tags from text using regex.
    
    Args:
        html_string: String that may contain HTML tags
        
    Returns:
        Cleaned string with HTML tags removed and extra whitespace cleaned
    """
    if not html_string:
        return ''
    
    if not isinstance(html_string, str):
        return str(html_string)
    
    # Remove HTML tags
    clean_text = re.sub(r'<[^>]+>', '', html_string)
    
    # Clean up extra whitespace
    clean_text = ' '.join(clean_text.split())
    
    return clean_text


def get_day_of_week(start_date):
    """
    Extract day of week from startDate.
    
    Args:
        start_date: ISO 8601 date string or datetime object
        
    Returns:
        Day name string (e.g., "Monday", "Friday") or None if invalid
    """
    if not start_date:
        return None
    
    if isinstance(start_date, str):
        dt = parse_iso_date(start_date)
        if not dt:
            return None
    else:
        dt = start_date
    
    return dt.strftime('%A')


def _construct_name(user):
    """
    Construct full name from firstName and lastName.
    
    Args:
        user: User dictionary
        
    Returns:
        Full name string
    """
    first = user.get('firstName') or ''
    last = user.get('lastName') or ''
    first = first.strip() if isinstance(first, str) else ''
    last = last.strip() if isinstance(last, str) else ''
    if first and last:
        return f"{first} {last}"
    elif first:
        return first
    elif last:
        return last
    else:
        return user.get('name') or ''


def get_host_name(event, users_lookup_by_id):
    """
    Get host name by looking up ownerId in users.
    
    Args:
        event: Event dictionary with ownerId field
        users_lookup_by_id: Dictionary mapping _id to user object
        
    Returns:
        Host name string or None if not found
    """
    owner_id = event.get('ownerId')
    if not owner_id:
        return None
    
    host_user = users_lookup_by_id.get(owner_id)
    if not host_user:
        return None
    
    return _construct_name(host_user)


def get_common_occupations(event, users_lookup_by_email):
    """
    Get common occupations from event participants.
    
    Args:
        event: Event dictionary with participants list
        users_lookup_by_email: Dictionary mapping email to user object
        
    Returns:
        List of most common occupations (top 3-5, excluding null/empty)
    """
    participants = event.get('participants', [])
    if not participants:
        return []
    
    occupations = []
    for email in participants:
        user = users_lookup_by_email.get(email)
        if user:
            occupation = user.get('occupation')
            if occupation and isinstance(occupation, str) and occupation.strip():
                occupations.append(occupation.strip())
    
    if not occupations:
        return []
    
    # Count frequencies
    occupation_counts = Counter(occupations)
    
    # Get top 3-5 most common
    most_common = occupation_counts.most_common(5)
    return [occ for occ, count in most_common]


def get_common_interests(event, users_lookup_by_email):
    """
    Get common interests from event participants.
    
    Args:
        event: Event dictionary with participants list
        users_lookup_by_email: Dictionary mapping email to user object
        
    Returns:
        List of most common interests (top 3-5, excluding null/empty)
    """
    participants = event.get('participants', [])
    if not participants:
        return []
    
    all_interests = []
    for email in participants:
        user = users_lookup_by_email.get(email)
        if user:
            interests = user.get('interests', [])
            if isinstance(interests, list):
                for interest in interests:
                    if interest and isinstance(interest, str) and interest.strip():
                        all_interests.append(interest.strip())
    
    if not all_interests:
        return []
    
    # Count frequencies
    interest_counts = Counter(all_interests)
    
    # Get top 3-5 most common
    most_common = interest_counts.most_common(5)
    return [interest for interest, count in most_common]


def calculate_age(birthDay):
    """
    Calculate age from birthDay ISO date string.
    
    Args:
        birthDay: ISO 8601 date string or None
        
    Returns:
        Age as integer or None if birthDay is missing/invalid
    """
    if not birthDay:
        return None
    
    birth_date = parse_iso_date(birthDay)
    if not birth_date:
        return None
    
    now = datetime.now(timezone.utc)
    age = now.year - birth_date.year
    
    # Adjust if birthday hasn't occurred this year
    if (now.month, now.day) < (birth_date.month, birth_date.day):
        age -= 1
    
    return age


def get_average_age(event, users_lookup_by_email):
    """
    Calculate average age of event participants.
    
    Args:
        event: Event dictionary with participants list
        users_lookup_by_email: Dictionary mapping email to user object
        
    Returns:
        Rounded average age (integer) or None if no participants with valid ages
    """
    participants = event.get('participants', [])
    if not participants:
        return None
    
    ages = []
    for email in participants:
        user = users_lookup_by_email.get(email)
        if user:
            age = calculate_age(user.get('birthDay'))
            if age is not None:
                ages.append(age)
    
    if not ages:
        return None
    
    average = sum(ages) / len(ages)
    return round(average)


def get_participant_names(event, users_lookup_by_email):
    """
    Get list of participant names with occupations.
    
    Args:
        event: Event dictionary with participants list
        users_lookup_by_email: Dictionary mapping email to user object
        
    Returns:
        Array of formatted participant name strings
        Format: "FirstName LastName (Occupation)" or "FirstName LastName"
    """
    participants = event.get('participants', [])
    if not participants:
        return []
    
    participant_names = []
    for email in participants:
        user = users_lookup_by_email.get(email)
        if user:
            name = _construct_name(user)
            if name:
                occupation = user.get('occupation')
                if occupation and isinstance(occupation, str) and occupation.strip():
                    participant_names.append(f"{name} ({occupation.strip()})")
                else:
                    participant_names.append(name)
    
    return participant_names


def has_low_occupancy(event):
    """
    Determine if event has very low occupancy.
    
    Args:
        event: Event dictionary with participant_count and maxParticipants
        
    Returns:
        Boolean: true if low occupancy, false otherwise
    """
    participant_count = event.get('participant_count', 0)
    max_participants = event.get('maxParticipants', 0)
    
    if max_participants == 0:
        return False
    
    # Calculate occupancy ratio
    occupancy_ratio = participant_count / max_participants
    
    # Low occupancy if:
    # - occupancy ratio < 0.3 (less than 30% full), OR
    # - participant_count < 3 AND maxParticipants >= 10
    if occupancy_ratio < 0.3:
        return True
    
    if participant_count < 3 and max_participants >= 10:
        return True
    
    return False


def filter_event_fields(event):
    """
    Filter event to keep only essential fields for matching.
    
    Args:
        event: Event dictionary from qualified_events.json
        
    Returns:
        Filtered event dictionary with essential fields
    """
    filtered = {
        'id': event.get('id') or event.get('_id'),
        'name': event.get('name'),
        'startDate': event.get('startDate'),
        'endDate': event.get('endDate'),
        'venueName': event.get('venueName'),
        'neighborhood': event.get('neighborhood'),
        'categories': event.get('categories', []),
        'features': event.get('features', []),
        'maxParticipants': event.get('maxParticipants'),
        'participant_count': len(event.get('participants', [])),
        # Keep participants for calculations
        '_participants': event.get('participants', []),
        '_ownerId': event.get('ownerId'),
        '_description': event.get('description'),
    }
    return filtered


def generate_summary(event, host_name, common_occupations, common_interests, average_age, participant_names, day_of_week, has_low_occupancy):
    """
    Generate human-readable summary sentence with all most relevant fields.
    
    Args:
        event: Enriched event dictionary
        host_name: Host name string or None
        common_occupations: List of common occupations
        common_interests: List of common interests
        average_age: Average age (number) or None
        participant_names: List of participant name strings
        day_of_week: Day of week string or None
        has_low_occupancy: Boolean indicating low occupancy
        
    Returns:
        Summary string
    """
    parts = []
    
    # Event name and basic info
    name = event.get('name', 'Event')
    categories = event.get('categories', [])
    category_str = ', '.join(categories[:2]).lower() if categories else 'event'
    
    # Date formatting with day of week
    start_date_str = event.get('startDate')
    date_part = ""
    if start_date_str:
        try:
            start_date = parse_iso_date(start_date_str)
            if start_date:
                if day_of_week:
                    date_part = f"on {day_of_week}, {start_date.strftime('%b %d, %Y at %I:%M %p')}"
                else:
                    date_part = f"on {start_date.strftime('%b %d, %Y at %I:%M %p')}"
        except (ValueError, TypeError, AttributeError):
            pass
    
    # Venue and neighborhood
    venue = event.get('venueName')
    neighborhood = event.get('neighborhood')
    
    intro_parts = [f"{name} is a {category_str}"]
    if date_part:
        intro_parts.append(date_part)
    if venue:
        intro_parts.append(f"at {venue}")
    if neighborhood:
        intro_parts.append(f"in {neighborhood}")
    if host_name:
        intro_parts.append(f"hosted by {host_name}")
    
    if len(intro_parts) > 1:
        parts.append(' '.join(intro_parts) + ".")
    
    # Participant count and capacity
    participant_count = event.get('participant_count', 0)
    max_participants = event.get('maxParticipants', 0)
    
    if max_participants > 0:
        capacity_text = f"The event has {participant_count} participant"
        if participant_count != 1:
            capacity_text += "s"
        capacity_text += f" out of {max_participants} max capacity"
        
        # Add participant names if available
        if participant_names:
            names_to_show = participant_names[:5]
            if len(names_to_show) == 1:
                capacity_text += f", including {names_to_show[0]}"
            elif len(names_to_show) == 2:
                capacity_text += f", including {names_to_show[0]} and {names_to_show[1]}"
            else:
                names_str = ', '.join(names_to_show[:-1])
                capacity_text += f", including {names_str}, and {names_to_show[-1]}"
        
        capacity_text += "."
        parts.append(capacity_text)
    
    # Low occupancy mention
    if has_low_occupancy:
        parts.append(f"This event currently has low attendance with only {participant_count} participant{'s' if participant_count != 1 else ''}.")
    
    # Common occupations
    if common_occupations:
        occ_str = ', '.join(common_occupations[:3])
        if len(common_occupations) > 3:
            occ_str += f" and {len(common_occupations) - 3} more"
        parts.append(f"Common occupations of attendees include {occ_str}.")
    
    # Common interests
    if common_interests:
        int_str = ', '.join(common_interests[:3])
        if len(common_interests) > 3:
            int_str += f" and {len(common_interests) - 3} more"
        parts.append(f"Common interests include {int_str}.")
    
    # Average age
    if average_age is not None:
        parts.append(f"The average age of attendees is {average_age}.")
    
    # Description (cleaned, truncated if long)
    description = event.get('description', '')
    if description:
        # Truncate if too long (keep first 200 characters)
        if len(description) > 200:
            description = description[:200] + "..."
        parts.append(description)
    
    # Combine all parts
    summary = ' '.join(parts)
    if not summary:
        summary = f"{name} is an event."
    
    return summary


def enrich_event(event, users_lookup_by_email, users_lookup_by_id):
    """
    Main enrichment function that orchestrates all steps.
    
    Args:
        event: Event dictionary from qualified_events.json
        users_lookup_by_email: Dictionary mapping email to user object
        users_lookup_by_id: Dictionary mapping _id to user object
        
    Returns:
        Enriched event dictionary
    """
    # Step 1: Filter to essential fields
    enriched = filter_event_fields(event)
    
    # Step 2: Clean HTML from description
    enriched['description'] = clean_html(enriched.pop('_description', ''))
    
    # Step 3: Extract day of week
    enriched['day_of_week'] = get_day_of_week(enriched.get('startDate'))
    
    # Step 4: Get host name
    enriched['host_name'] = get_host_name(event, users_lookup_by_id)
    
    # Step 5: Get common occupations
    enriched['common_occupations'] = get_common_occupations(event, users_lookup_by_email)
    
    # Step 6: Get common interests
    enriched['common_interests'] = get_common_interests(event, users_lookup_by_email)
    
    # Step 7: Get average age
    enriched['average_age'] = get_average_age(event, users_lookup_by_email)
    
    # Step 8: Get participant names
    enriched['participant_names'] = get_participant_names(event, users_lookup_by_email)
    
    # Step 9: Determine low occupancy
    enriched['has_low_occupancy'] = has_low_occupancy(enriched)
    
    # Step 10: Generate summary
    enriched['summary'] = generate_summary(
        enriched,
        enriched['host_name'],
        enriched['common_occupations'],
        enriched['common_interests'],
        enriched['average_age'],
        enriched['participant_names'],
        enriched['day_of_week'],
        enriched['has_low_occupancy']
    )
    
    # Remove internal fields
    enriched.pop('_participants', None)
    enriched.pop('_ownerId', None)
    
    return enriched


def save_enriched_events(events, output_path):
    """
    Save enriched events to JSON file.
    
    Args:
        events: List of enriched event dictionaries
        output_path: Path to output JSON file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
    
    return output_path


def main():
    """
    Main function to run the event enrichment pipeline.
    """
    # Define paths
    base_dir = Path(__file__).parent.parent
    qualified_events_path = base_dir / 'data' / 'processed' / 'qualified_events.json'
    all_users_path = base_dir / 'data' / 'raw' / 'users.json'
    output_path = base_dir / 'data' / 'processed' / 'enriched_events.json'
    log_dir = base_dir / 'logs'
    
    # Setup logging
    logger, log_file = setup_logging(log_dir)
    
    logger.info("=" * 80)
    logger.info("EVENT ENRICHMENT PIPELINE - STEP 4")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    # Step 1: Load qualified events
    logger.info("STEP 1: Loading qualified events...")
    qualified_events = load_qualified_events(qualified_events_path)
    logger.info(f"Loaded {len(qualified_events)} qualified events")
    logger.info("")
    
    # Step 2: Load all users
    logger.info("STEP 2: Loading all users...")
    all_users = load_all_users(all_users_path)
    logger.info(f"Loaded {len(all_users)} users")
    logger.info("")
    
    # Step 3: Create lookup dictionaries
    logger.info("STEP 3: Creating lookup dictionaries...")
    users_lookup_by_email = {}
    users_lookup_by_id = {}
    
    for user in all_users:
        email = user.get('email')
        if email:
            users_lookup_by_email[email] = user
        
        user_id = user.get('_id') or user.get('id')
        if user_id:
            users_lookup_by_id[user_id] = user
    
    logger.info(f"Created email lookup with {len(users_lookup_by_email)} entries")
    logger.info(f"Created ID lookup with {len(users_lookup_by_id)} entries")
    logger.info("")
    
    # Step 4: Enrich events
    logger.info("STEP 4: Enriching events...")
    enriched_events = []
    
    stats = {
        'total_events': len(qualified_events),
        'events_with_host': 0,
        'events_with_occupations': 0,
        'events_with_interests': 0,
        'events_with_age': 0,
        'events_with_participant_names': 0,
        'events_low_occupancy': 0,
        'day_of_week_distribution': Counter(),
        'occupation_counts': Counter(),
        'interest_counts': Counter(),
        'age_distribution': [],
    }
    
    for event in qualified_events:
        enriched = enrich_event(event, users_lookup_by_email, users_lookup_by_id)
        enriched_events.append(enriched)
        
        # Update statistics
        if enriched.get('host_name'):
            stats['events_with_host'] += 1
        if enriched.get('common_occupations'):
            stats['events_with_occupations'] += 1
            for occ in enriched['common_occupations']:
                stats['occupation_counts'][occ] += 1
        if enriched.get('common_interests'):
            stats['events_with_interests'] += 1
            for interest in enriched['common_interests']:
                stats['interest_counts'][interest] += 1
        if enriched.get('average_age') is not None:
            stats['events_with_age'] += 1
            stats['age_distribution'].append(enriched['average_age'])
        if enriched.get('participant_names'):
            stats['events_with_participant_names'] += 1
        if enriched.get('has_low_occupancy'):
            stats['events_low_occupancy'] += 1
        if enriched.get('day_of_week'):
            stats['day_of_week_distribution'][enriched['day_of_week']] += 1
    
    logger.info(f"Enriched {len(enriched_events)} events")
    logger.info("")
    
    # Step 5: Log statistics
    logger.info("=" * 80)
    logger.info("ENRICHMENT STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Total events enriched: {stats['total_events']}")
    logger.info(f"Events with host name: {stats['events_with_host']} ({stats['events_with_host']/stats['total_events']*100:.1f}%)")
    logger.info(f"Events with common occupations: {stats['events_with_occupations']} ({stats['events_with_occupations']/stats['total_events']*100:.1f}%)")
    logger.info(f"Events with common interests: {stats['events_with_interests']} ({stats['events_with_interests']/stats['total_events']*100:.1f}%)")
    logger.info(f"Events with average age: {stats['events_with_age']} ({stats['events_with_age']/stats['total_events']*100:.1f}%)")
    logger.info(f"Events with participant names: {stats['events_with_participant_names']} ({stats['events_with_participant_names']/stats['total_events']*100:.1f}%)")
    logger.info(f"Events with low occupancy: {stats['events_low_occupancy']} ({stats['events_low_occupancy']/stats['total_events']*100:.1f}%)")
    logger.info("")
    
    # Day of week distribution
    logger.info("Day of week distribution:")
    for day, count in sorted(stats['day_of_week_distribution'].items()):
        logger.info(f"  {day}: {count}")
    logger.info("")
    
    # Top occupations
    logger.info("Top 10 most common occupations across events:")
    for occ, count in stats['occupation_counts'].most_common(10):
        logger.info(f"  {occ}: {count}")
    logger.info("")
    
    # Top interests
    logger.info("Top 10 most common interests across events:")
    for interest, count in stats['interest_counts'].most_common(10):
        logger.info(f"  {interest}: {count}")
    logger.info("")
    
    # Age statistics
    if stats['age_distribution']:
        avg_age = sum(stats['age_distribution']) / len(stats['age_distribution'])
        min_age = min(stats['age_distribution'])
        max_age = max(stats['age_distribution'])
        logger.info(f"Average age statistics:")
        logger.info(f"  Mean: {avg_age:.1f}")
        logger.info(f"  Min: {min_age}")
        logger.info(f"  Max: {max_age}")
        logger.info("")
    
    # Step 6: Log top 50 summaries
    logger.info("=" * 80)
    logger.info("TOP 50 EVENT SUMMARIES")
    logger.info("=" * 80)
    for i, event in enumerate(enriched_events[:50], 1):
        logger.info(f"{i}. {event.get('name', 'Unknown Event')}")
        logger.info(f"   Summary: {event.get('summary', 'No summary')}")
        logger.info("")
    
    # Step 7: Save enriched events
    logger.info("STEP 7: Saving enriched events...")
    save_enriched_events(enriched_events, output_path)
    logger.info(f"Saved {len(enriched_events)} enriched events to {output_path}")
    logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total events enriched: {len(enriched_events)}")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Output file: {output_path}")
    logger.info("=" * 80)
    
    print(f"\nPipeline completed. Enriched events: {len(enriched_events)}")


if __name__ == "__main__":
    main()


