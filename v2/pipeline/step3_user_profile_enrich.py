"""
Step 3: User Profile Enrichment Pipeline

This script enriches qualified user profiles by:
1. Filtering to essential fields for personalization
2. Calculating derived metrics (age, event stats, days since signup/last event)
3. Associating event history by email matching
4. Extracting event host names from ownerId lookup
5. Identifying invited events from qualified_events.json
6. Extracting participant names and identifying friends based on shared events
7. Calculating user status fields (boolean and categorical)
8. Generating comprehensive human-readable summaries

FIELD SCHEMAS:
=============

Input User Schema (from qualified_users.json):
- _id: string (MongoDB ObjectId)
- id: string (same as _id)
- email: string
- firstName: string
- lastName: string
- birthDay: string (ISO 8601 date, e.g., "1990-05-15T00:00:00.000Z")
- createdAt: string (ISO 8601 date)
- role: string ("POTENTIAL", "AMBASSADOR", "ADMIN", etc.)
- interests: array of strings
- preferredCuisines: array of strings (optional)
- allergies: array of strings (optional)
- tableTypePreference: string
- relationshipStatus: string
- occupation: string
- gender: string
- homeNeighborhood: string
- workNeighborhood: string

Output Enriched User Schema:
- id: string
- name: string (constructed from firstName + lastName)
- email: string
- interests: array of strings
- cuisine_preferences: array of strings (from preferredCuisines or derived)
- dietary_restrictions: array of strings (from allergies)
- table_type_preference: string (from tableTypePreference)
- relationship_status: string (from relationshipStatus)
- occupation: string
- gender: string
- homeNeighborhood: string
- workNeighborhood: string
- age: number or null
- event_count: number
- last_event_date: string (ISO 8601) or null
- days_since_last_event: number or null
- days_since_signup: number
- historical_event_names: array of strings
- event_hosts: array of strings (unique host names)
- invited_event_names: array of strings
- friends: array of strings (format: "Name (count)")
- is_new_user: boolean
- has_never_attended_events: boolean
- hasnt_attended_in_60_days: boolean or null
- signed_up_online: boolean
- recently_attended_last_week: boolean or null
- primary_status: string (one of: "new_user", "never_attended", "dormant_60_days", "active_recent", "signed_up_online", "active_regular")
- engagement_tier: string (one of: "high", "medium", "low")
- user_segment: string (one of: "new_online_signup", "new_app_user", "first_timer", "active_regular", "dormant", "churned")
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
    - Each event has: _id, name, startDate, participants (list of emails), ownerId

qualified_events: list[dict]
    - Each event has: _id, name, invitedParticipants (list of emails)
"""

import json
import logging
from collections import Counter
from datetime import datetime, timezone, timedelta
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
    log_file = log_dir / f'user_profile_enrich_{timestamp}.log'
    
    logger = logging.getLogger('user_profile_enrich')
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


def load_qualified_users(filepath):
    """
    Load qualified users from JSON file.
    
    Args:
        filepath: Path to qualified_users.json file
        
    Returns:
        List of user dictionaries
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        users = json.load(f)
    return users


def load_all_events(filepath):
    """
    Load all events from JSON file.
    
    Args:
        filepath: Path to events.json file
        
    Returns:
        List of event dictionaries
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        events = json.load(f)
    return events


def load_qualified_events(filepath):
    """
    Load qualified events from JSON file.
    
    Args:
        filepath: Path to qualified_events.json file
        
    Returns:
        List of qualified event dictionaries
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
        datetime object in UTC timezone
    """
    if not date_string:
        return None
    # Replace 'Z' with '+00:00' for fromisoformat compatibility
    if date_string.endswith('Z'):
        date_string = date_string[:-1] + '+00:00'
    return datetime.fromisoformat(date_string)


def filter_user_fields(user):
    """
    Filter user to keep only essential fields and map field names.
    
    Args:
        user: User dictionary from qualified_users.json
        
    Returns:
        Filtered user dictionary with mapped field names
    """
    filtered = {
        'id': user.get('id') or user.get('_id'),
        'name': _construct_name(user),
        'email': user.get('email'),
        'interests': user.get('interests', []),
        'cuisine_preferences': user.get('preferredCuisines', []),
        'dietary_restrictions': user.get('allergies'),  # Can be string, array, or null
        'table_type_preference': user.get('tableTypePreference'),
        'relationship_status': user.get('relationshipStatus'),
        'occupation': user.get('occupation'),
        'gender': user.get('gender'),
        'homeNeighborhood': user.get('homeNeighborhood'),
        'workNeighborhood': user.get('workNeighborhood'),
        # Keep original fields needed for calculations
        '_birthDay': user.get('birthDay'),
        '_createdAt': user.get('createdAt'),
        '_role': user.get('role'),
    }
    return filtered


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
    
    try:
        birth_date = parse_iso_date(birthDay)
        now = datetime.now(timezone.utc)
        age = now.year - birth_date.year
        
        # Adjust if birthday hasn't occurred this year
        if (now.month, now.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        return age
    except (ValueError, TypeError, AttributeError):
        return None


def associate_user_events(user, events):
    """
    Match user email with event participants, return user's events.
    
    Args:
        user: User dictionary (must have 'email' field)
        events: List of all event dictionaries
        
    Returns:
        List of events where user email appears in participants list,
        sorted by startDate (most recent first)
    """
    user_email = user.get('email')
    if not user_email:
        return []
    
    user_events = []
    for event in events:
        participants = event.get('participants', [])
        if isinstance(participants, list) and user_email in participants:
            user_events.append(event)
    
    # Sort by startDate (most recent first)
    def get_start_date(event):
        start_date_str = event.get('startDate')
        if not start_date_str:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            return parse_iso_date(start_date_str) or datetime.min.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return datetime.min.replace(tzinfo=timezone.utc)
    
    user_events.sort(key=get_start_date, reverse=True)
    return user_events


def calculate_event_stats(user_events):
    """
    Calculate event statistics for a user.
    
    Args:
        user_events: List of events user attended
        
    Returns:
        Dictionary with:
        - event_count: int
        - last_event_date: string (ISO 8601) or None
        - days_since_last_event: int or None
        - historical_event_names: list of strings
    """
    event_count = len(user_events)
    historical_event_names = [event.get('name', '') for event in user_events if event.get('name')]
    
    if event_count == 0:
        return {
            'event_count': 0,
            'last_event_date': None,
            'days_since_last_event': None,
            'historical_event_names': []
        }
    
    # Get most recent event
    last_event = user_events[0]  # Already sorted by startDate
    last_event_date_str = last_event.get('startDate')
    
    if not last_event_date_str:
        return {
            'event_count': event_count,
            'last_event_date': None,
            'days_since_last_event': None,
            'historical_event_names': historical_event_names
        }
    
    try:
        last_event_date = parse_iso_date(last_event_date_str)
        now = datetime.now(timezone.utc)
        days_since = (now - last_event_date).days
        return {
            'event_count': event_count,
            'last_event_date': last_event_date_str,
            'days_since_last_event': days_since,
            'historical_event_names': historical_event_names
        }
    except (ValueError, TypeError):
        return {
            'event_count': event_count,
            'last_event_date': last_event_date_str,
            'days_since_last_event': None,
            'historical_event_names': historical_event_names
        }


def get_event_hosts(user_events, users_lookup_by_id):
    """
    Get host names for events user attended by looking up ownerId in users.
    
    Args:
        user_events: List of events user attended
        users_lookup_by_id: Dictionary mapping _id to user object
        
    Returns:
        List of unique host names (strings)
    """
    host_names = []
    for event in user_events:
        owner_id = event.get('ownerId')
        if owner_id and owner_id in users_lookup_by_id:
            host_user = users_lookup_by_id[owner_id]
            host_name = _construct_name(host_user)
            if host_name and host_name not in host_names:
                host_names.append(host_name)
    return host_names


def get_invited_events(user, qualified_events):
    """
    Get names of events user has been invited to (from invitedParticipants list).
    
    Args:
        user: User dictionary (must have 'email' field)
        qualified_events: List of qualified event dictionaries
        
    Returns:
        List of invited event names (strings)
    """
    user_email = user.get('email')
    if not user_email:
        return []
    
    invited_event_names = []
    for event in qualified_events:
        invited_participants = event.get('invitedParticipants', [])
        if isinstance(invited_participants, list) and user_email in invited_participants:
            event_name = event.get('name')
            if event_name:
                invited_event_names.append(event_name)
    
    return invited_event_names


def calculate_user_status_fields(user, event_stats):
    """
    Calculate all user status boolean and categorical fields.
    
    Args:
        user: User dictionary (must have _createdAt, _role fields)
        event_stats: Dictionary from calculate_event_stats()
        
    Returns:
        Dictionary with all status fields
    """
    now = datetime.now(timezone.utc)
    
    # Calculate days_since_signup
    days_since_signup = None
    created_at_str = user.get('_createdAt')
    if created_at_str:
        try:
            created_at = parse_iso_date(created_at_str)
            days_since_signup = (now - created_at).days
        except (ValueError, TypeError):
            pass
    
    # Boolean fields
    is_new_user = days_since_signup is not None and days_since_signup <= 30
    has_never_attended_events = event_stats['event_count'] == 0
    hasnt_attended_in_60_days = None
    if event_stats['days_since_last_event'] is not None:
        hasnt_attended_in_60_days = event_stats['days_since_last_event'] > 60
    signed_up_online = user.get('_role') == 'POTENTIAL'
    recently_attended_last_week = None
    if event_stats['days_since_last_event'] is not None:
        recently_attended_last_week = event_stats['days_since_last_event'] <= 7
    
    # Primary status (priority order)
    primary_status = "active_regular"
    if signed_up_online:
        primary_status = "signed_up_online"
    elif is_new_user:
        primary_status = "new_user"
    elif has_never_attended_events:
        primary_status = "never_attended"
    elif recently_attended_last_week:
        primary_status = "active_recent"
    elif hasnt_attended_in_60_days:
        primary_status = "dormant_60_days"
    
    # Engagement tier
    event_count = event_stats['event_count']
    days_since = event_stats['days_since_last_event']
    if event_count >= 10 or recently_attended_last_week:
        engagement_tier = "high"
    elif event_count >= 3 or (event_count > 0 and days_since is not None and days_since <= 30):
        engagement_tier = "medium"
    else:
        engagement_tier = "low"
    
    # User segment
    if signed_up_online and is_new_user:
        user_segment = "new_online_signup"
    elif is_new_user and not signed_up_online:
        user_segment = "new_app_user"
    elif has_never_attended_events and not is_new_user:
        user_segment = "first_timer"
    elif recently_attended_last_week or (event_count >= 3 and days_since is not None and days_since <= 30):
        user_segment = "active_regular"
    elif hasnt_attended_in_60_days and event_count > 0:
        user_segment = "dormant"
    elif hasnt_attended_in_60_days and event_count == 0:
        user_segment = "churned"
    else:
        user_segment = "active_regular"
    
    return {
        'days_since_signup': days_since_signup,
        'is_new_user': is_new_user,
        'has_never_attended_events': has_never_attended_events,
        'hasnt_attended_in_60_days': hasnt_attended_in_60_days,
        'signed_up_online': signed_up_online,
        'recently_attended_last_week': recently_attended_last_week,
        'primary_status': primary_status,
        'engagement_tier': engagement_tier,
        'user_segment': user_segment
    }


def get_participant_names(event, users_lookup_by_email):
    """
    Get participant names from event participants list.
    
    Args:
        event: Event dictionary
        users_lookup_by_email: Dictionary mapping email to user object
        
    Returns:
        List of participant names (strings)
    """
    participant_names = []
    participants = event.get('participants', [])
    if not isinstance(participants, list):
        return participant_names
    
    for email in participants:
        if email in users_lookup_by_email:
            user = users_lookup_by_email[email]
            name = _construct_name(user)
            if name:
                participant_names.append(name)
    
    return participant_names


def identify_friends(user, all_events, users_lookup_by_email):
    """
    Identify friends based on shared events frequency.
    
    Args:
        user: User dictionary (must have 'email' field)
        all_events: List of all event dictionaries
        users_lookup_by_email: Dictionary mapping email to user object
        
    Returns:
        List of friend names with shared event count (format: "Name (count)")
    """
    user_email = user.get('email')
    if not user_email:
        return []
    
    # Find all events user attended
    user_events = associate_user_events(user, all_events)
    if not user_events:
        return []
    
    # Count shared events with other participants
    friend_counts = Counter()
    for event in user_events:
        participants = event.get('participants', [])
        if not isinstance(participants, list):
            continue
        
        for email in participants:
            if email != user_email and email in users_lookup_by_email:
                other_user = users_lookup_by_email[email]
                friend_name = _construct_name(other_user)
                if friend_name:
                    friend_counts[friend_name] += 1
    
    # Filter friends who share 2+ events and format
    friends = []
    for friend_name, count in friend_counts.most_common():
        if count >= 2:
            friends.append(f"{friend_name} ({count})")
    
    return friends


def _extract_frequent_words(event_names, min_count=3):
    """
    Extract frequently used words from event names.
    
    Args:
        event_names: List of event name strings
        min_count: Minimum number of occurrences to include a word
        
    Returns:
        List of frequent words (strings)
    """
    if not event_names:
        return []
    
    # Count word frequencies (case-insensitive, ignore common words)
    word_counts = Counter()
    common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
    
    for event_name in event_names:
        if not event_name:
            continue
        # Split by common delimiters and extract words
        words = event_name.lower().replace('!', ' ').replace('?', ' ').replace('.', ' ').replace(',', ' ').replace(':', ' ').replace(';', ' ').split()
        for word in words:
            # Remove emojis and special characters, keep only alphanumeric
            word = ''.join(c for c in word if c.isalnum())
            if len(word) > 2 and word not in common_words:
                word_counts[word] += 1
    
    # Return words that appear at least min_count times, sorted by frequency
    frequent_words = [word for word, count in word_counts.most_common() if count >= min_count]
    return frequent_words[:5]  # Limit to top 5


def _extract_friend_names(friends_list, max_friends=3):
    """
    Extract friend names from friends list (format: "Name (count)").
    
    Args:
        friends_list: List of strings in format "Name (count)"
        max_friends: Maximum number of friends to return
        
    Returns:
        List of friend names (strings)
    """
    friend_names = []
    for friend_entry in friends_list[:max_friends]:
        # Extract name before " (" 
        if ' (' in friend_entry:
            name = friend_entry.split(' (')[0]
            friend_names.append(name)
        else:
            friend_names.append(friend_entry)
    return friend_names


def generate_summary(user, user_events=None):
    """
    Generate human-readable summary sentence with all most relevant fields.
    
    Args:
        user: Enriched user dictionary
        user_events: Optional list of events user attended (for extracting last event name)
        
    Returns:
        Summary string
    """
    parts = []
    
    # Name and basic info
    name = user.get('name', 'User')
    age = user.get('age')
    gender_val = user.get('gender')
    gender = gender_val.lower() if gender_val and isinstance(gender_val, str) else None
    occupation = user.get('occupation')
    
    intro = name
    if age:
        intro += f" is a {age}-year-old"
    if gender:
        intro += f" {gender}"
    if occupation:
        intro += f" {occupation}"
    
    # Neighborhood
    home_neighborhood = user.get('homeNeighborhood')
    work_neighborhood = user.get('workNeighborhood')
    neighborhoods = []
    if home_neighborhood:
        neighborhoods.append(home_neighborhood)
    if work_neighborhood and work_neighborhood != home_neighborhood:
        neighborhoods.append(work_neighborhood)
    
    if neighborhoods:
        intro += f" in {', '.join(neighborhoods)}"
    
    # Join date
    days_since_signup = user.get('days_since_signup')
    if days_since_signup is not None:
        created_at_str = user.get('_createdAt')
        if created_at_str:
            try:
                created_at = parse_iso_date(created_at_str)
                join_month = created_at.strftime('%B %Y')
                intro += f" who joined in {join_month}"
            except (ValueError, TypeError):
                pass
    
    if intro != name:
        parts.append(intro + ".")
    
    # Determine pronoun based on gender
    pronoun = "They"
    if gender == 'male':
        pronoun = "He"
    elif gender == 'female':
        pronoun = "She"
    
    # Interests and preferences - combine into one sentence for better flow
    interests = user.get('interests', [])
    cuisine_prefs = user.get('cuisine_preferences', [])
    table_pref = user.get('table_type_preference')
    dietary = user.get('dietary_restrictions')
    
    preference_parts = []
    if interests:
        interests_str = ', '.join(interests[:3])  # Limit to 3
        if len(interests) > 3:
            interests_str += f" and {len(interests) - 3} more"
        preference_parts.append(f"enjoys {interests_str}")
    
    if cuisine_prefs:
        cuisine_str = ', '.join(cuisine_prefs[:3])
        if len(cuisine_prefs) > 3:
            cuisine_str += f" and {len(cuisine_prefs) - 3} more"
        preference_parts.append(f"prefers {cuisine_str} food")
    
    if table_pref:
        preference_parts.append(f"likes {table_pref} tables")
    
    if preference_parts:
        pref_sentence = f"{pronoun} {', '.join(preference_parts)}."
        parts.append(pref_sentence)
    
    # Dietary restrictions - separate sentence for clarity
    if dietary:
        # Handle both string and array formats
        if isinstance(dietary, str):
            dietary_str = dietary
        elif isinstance(dietary, list):
            dietary_str = ', '.join(dietary)
        else:
            dietary_str = str(dietary)
        if dietary_str.strip():
            parts.append(f"{pronoun} has dietary restrictions: {dietary_str}.")
    
    # Event count and last event
    event_count = user.get('event_count', 0)
    last_event_date = user.get('last_event_date')
    days_since_last = user.get('days_since_last_event')
    historical_event_names = user.get('historical_event_names', [])
    
    if event_count > 0:
        event_text = f"{pronoun} has attended {event_count} event"
        if event_count != 1:
            event_text += "s"
        
        # Include last event name if attended recently (within last 30 days)
        if days_since_last is not None and days_since_last <= 30 and user_events and len(user_events) > 0:
            last_event = user_events[0]  # Already sorted by date, most recent first
            last_event_name = last_event.get('name')
            if last_event_name:
                event_text += f", most recently \"{last_event_name}\""
                if last_event_date:
                    try:
                        last_date = parse_iso_date(last_event_date)
                        last_date_str = last_date.strftime('%b %d, %Y')
                        event_text += f" on {last_date_str}"
                    except (ValueError, TypeError):
                        pass
        elif last_event_date:
            try:
                last_date = parse_iso_date(last_event_date)
                last_date_str = last_date.strftime('%b %d, %Y')
                event_text += f", most recently on {last_date_str}"
            except (ValueError, TypeError):
                pass
        
        # Add frequently used words from event names if attended many events
        if event_count >= 5 and historical_event_names:
            frequent_words = _extract_frequent_words(historical_event_names, min_count=2)
            if frequent_words:
                words_str = ', '.join(frequent_words[:3])
                event_text += f", often attending events featuring {words_str}"
        
        event_text += "."
        parts.append(event_text)
    
    # Engagement status
    user_segment = user.get('user_segment')
    if user_segment:
        segment_map = {
            'new_online_signup': 'a new online signup',
            'new_app_user': 'a new app user',
            'first_timer': 'a first-time user',
            'active_regular': 'an active regular user',
            'dormant': 'a dormant user',
            'churned': 'a churned user'
        }
        segment_text = segment_map.get(user_segment, 'a user')
        parts.append(f"{pronoun} is {segment_text}.")
    
    # Preferred hosts
    event_hosts = user.get('event_hosts', [])
    if event_hosts:
        hosts_str = ', '.join(event_hosts[:2])
        if len(event_hosts) > 2:
            hosts_str += f" and {len(event_hosts) - 2} more"
        parts.append(f"{pronoun} frequently attends events hosted by {hosts_str}.")
    
    # Invited events - include event names
    invited_events = user.get('invited_event_names', [])
    if invited_events:
        count = len(invited_events)
        if count == 1:
            parts.append(f"{pronoun} has been invited to the upcoming event \"{invited_events[0]}\".")
        elif count <= 3:
            events_str = ', '.join([f'"{event}"' for event in invited_events])
            parts.append(f"{pronoun} has been invited to {count} upcoming events: {events_str}.")
        else:
            events_str = ', '.join([f'"{event}"' for event in invited_events[:2]])
            parts.append(f"{pronoun} has been invited to {count} upcoming events, including {events_str} and {count - 2} more.")
    
    # Top friends - include names in sentence
    friends = user.get('friends', [])
    if friends:
        friend_names = _extract_friend_names(friends, max_friends=3)
        if len(friend_names) == 1:
            parts.append(f"{pronoun} frequently attends events with {friend_names[0]}.")
        elif len(friend_names) == 2:
            parts.append(f"{pronoun} frequently attends events with {friend_names[0]} and {friend_names[1]}.")
        else:
            friends_str = ', '.join(friend_names[:2])
            parts.append(f"{pronoun} frequently attends events with {friends_str} and {len(friends) - 2} other friends.")
    
    # Combine all parts
    summary = ' '.join(parts)
    if not summary:
        summary = f"{name} is a user."
    
    return summary


def enrich_user(user, all_events, qualified_events, users_lookup_by_email, users_lookup_by_id):
    """
    Main enrichment function that orchestrates all steps.
    
    Args:
        user: User dictionary from qualified_users.json
        all_events: List of all event dictionaries
        qualified_events: List of qualified event dictionaries
        users_lookup_by_email: Dictionary mapping email to user object
        users_lookup_by_id: Dictionary mapping _id to user object
        
    Returns:
        Enriched user dictionary
    """
    # Step 1: Filter to essential fields
    enriched = filter_user_fields(user)
    
    # Step 2: Calculate age
    enriched['age'] = calculate_age(user.get('birthDay'))
    
    # Step 3: Associate events
    user_events = associate_user_events(enriched, all_events)
    
    # Step 4: Get event hosts
    enriched['event_hosts'] = get_event_hosts(user_events, users_lookup_by_id)
    
    # Step 5: Get invited events
    enriched['invited_event_names'] = get_invited_events(enriched, qualified_events)
    
    # Step 6: Calculate event stats
    event_stats = calculate_event_stats(user_events)
    enriched.update(event_stats)
    
    # Step 7: Calculate user status fields
    status_fields = calculate_user_status_fields(enriched, event_stats)
    enriched.update(status_fields)
    
    # Step 8: Identify friends
    enriched['friends'] = identify_friends(enriched, all_events, users_lookup_by_email)
    
    # Step 9: Generate summary (pass user_events for last event name)
    enriched['summary'] = generate_summary(enriched, user_events)
    
    # Remove internal fields
    enriched.pop('_birthDay', None)
    enriched.pop('_createdAt', None)
    enriched.pop('_role', None)
    
    return enriched


def save_enriched_users(users, output_path):
    """
    Save enriched users to JSON file.
    
    Args:
        users: List of enriched user dictionaries
        output_path: Path to output JSON file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)
    
    return output_path


def main():
    """
    Main function to run the user profile enrichment pipeline.
    """
    # Define paths
    base_dir = Path(__file__).parent.parent
    qualified_users_path = base_dir / 'data' / 'processed' / 'qualified_users.json'
    all_events_path = base_dir / 'data' / 'raw' / 'events.json'
    qualified_events_path = base_dir / 'data' / 'processed' / 'qualified_events.json'
    all_users_path = base_dir / 'data' / 'raw' / 'users.json'
    output_path = base_dir / 'data' / 'processed' / 'enriched_users.json'
    log_dir = base_dir / 'logs'
    
    # Setup logging
    logger, log_file = setup_logging(log_dir)
    
    logger.info("=" * 80)
    logger.info("USER PROFILE ENRICHMENT PIPELINE - STEP 3")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    # Step 1: Load qualified users
    logger.info("STEP 1: Loading qualified users...")
    qualified_users = load_qualified_users(qualified_users_path)
    logger.info(f"Loaded {len(qualified_users)} qualified users")
    logger.info("")
    
    # Step 2: Load all events
    logger.info("STEP 2: Loading all events...")
    all_events = load_all_events(all_events_path)
    logger.info(f"Loaded {len(all_events)} events")
    logger.info("")
    
    # Step 3: Load qualified events
    logger.info("STEP 3: Loading qualified events...")
    qualified_events = load_qualified_events(qualified_events_path)
    logger.info(f"Loaded {len(qualified_events)} qualified events")
    logger.info("")
    
    # Step 4: Load all users for lookup
    logger.info("STEP 4: Loading all users for lookup...")
    all_users = load_all_users(all_users_path)
    logger.info(f"Loaded {len(all_users)} users for lookup")
    logger.info("")
    
    # Step 5: Create lookup dictionaries
    logger.info("STEP 5: Creating lookup dictionaries...")
    users_lookup_by_email = {}
    users_lookup_by_id = {}
    for user in all_users:
        email = user.get('email')
        user_id = user.get('_id') or user.get('id')
        if email:
            users_lookup_by_email[email] = user
        if user_id:
            users_lookup_by_id[user_id] = user
    logger.info(f"Created email lookup: {len(users_lookup_by_email)} entries")
    logger.info(f"Created ID lookup: {len(users_lookup_by_id)} entries")
    logger.info("")
    
    # Step 6: Enrich users
    logger.info("STEP 6: Enriching users...")
    enriched_users = []
    enrichment_stats = {
        'total_users': len(qualified_users),
        'users_with_age': 0,
        'users_with_events': 0,
        'users_with_hosts': 0,
        'users_with_invited_events': 0,
        'users_with_friends': 0,
        'total_events_associated': 0,
        'total_friends_identified': 0,
    }
    
    for i, user in enumerate(qualified_users, 1):
        if i % 10 == 0:
            logger.info(f"  Processing user {i}/{len(qualified_users)}...")
        
        enriched = enrich_user(
            user,
            all_events,
            qualified_events,
            users_lookup_by_email,
            users_lookup_by_id
        )
        enriched_users.append(enriched)
        
        # Update statistics
        if enriched.get('age') is not None:
            enrichment_stats['users_with_age'] += 1
        if enriched.get('event_count', 0) > 0:
            enrichment_stats['users_with_events'] += 1
            enrichment_stats['total_events_associated'] += enriched.get('event_count', 0)
        if enriched.get('event_hosts'):
            enrichment_stats['users_with_hosts'] += 1
        if enriched.get('invited_event_names'):
            enrichment_stats['users_with_invited_events'] += 1
        if enriched.get('friends'):
            enrichment_stats['users_with_friends'] += 1
            enrichment_stats['total_friends_identified'] += len(enriched.get('friends', []))
    
    logger.info(f"Enriched {len(enriched_users)} users")
    logger.info("")
    
    # Step 7: Log enrichment statistics
    logger.info("=" * 80)
    logger.info("ENRICHMENT STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Total users processed: {enrichment_stats['total_users']}")
    logger.info(f"Users with age calculated: {enrichment_stats['users_with_age']} ({enrichment_stats['users_with_age']/enrichment_stats['total_users']*100:.1f}%)")
    logger.info(f"Users with events: {enrichment_stats['users_with_events']} ({enrichment_stats['users_with_events']/enrichment_stats['total_users']*100:.1f}%)")
    logger.info(f"Total events associated: {enrichment_stats['total_events_associated']}")
    if enrichment_stats['users_with_events'] > 0:
        logger.info(f"Average events per user (with events): {enrichment_stats['total_events_associated']/enrichment_stats['users_with_events']:.1f}")
    logger.info(f"Users with event hosts: {enrichment_stats['users_with_hosts']} ({enrichment_stats['users_with_hosts']/enrichment_stats['total_users']*100:.1f}%)")
    logger.info(f"Users with invited events: {enrichment_stats['users_with_invited_events']} ({enrichment_stats['users_with_invited_events']/enrichment_stats['total_users']*100:.1f}%)")
    logger.info(f"Users with friends: {enrichment_stats['users_with_friends']} ({enrichment_stats['users_with_friends']/enrichment_stats['total_users']*100:.1f}%)")
    logger.info(f"Total friends identified: {enrichment_stats['total_friends_identified']}")
    if enrichment_stats['users_with_friends'] > 0:
        logger.info(f"Average friends per user (with friends): {enrichment_stats['total_friends_identified']/enrichment_stats['users_with_friends']:.1f}")
    logger.info("")
    
    # Step 8: Log field enrichment statistics
    logger.info("=" * 80)
    logger.info("FIELD ENRICHMENT STATISTICS")
    logger.info("=" * 80)
    field_stats = {}
    for user in enriched_users:
        for key, value in user.items():
            if key not in field_stats:
                field_stats[key] = {'populated': 0, 'missing': 0}
            if value is not None and value != [] and value != '':
                field_stats[key]['populated'] += 1
            else:
                field_stats[key]['missing'] += 1
    
    for field, stats in sorted(field_stats.items()):
        total = stats['populated'] + stats['missing']
        pct = (stats['populated'] / total * 100) if total > 0 else 0
        logger.info(f"{field}: {stats['populated']}/{total} populated ({pct:.1f}%)")
    logger.info("")
    
    # Step 9: Log user status distribution
    logger.info("=" * 80)
    logger.info("USER STATUS DISTRIBUTION")
    logger.info("=" * 80)
    status_counts = Counter()
    segment_counts = Counter()
    tier_counts = Counter()
    for user in enriched_users:
        status_counts[user.get('primary_status', 'unknown')] += 1
        segment_counts[user.get('user_segment', 'unknown')] += 1
        tier_counts[user.get('engagement_tier', 'unknown')] += 1
    
    logger.info("Primary Status:")
    for status, count in status_counts.most_common():
        pct = count / len(enriched_users) * 100
        logger.info(f"  {status}: {count} ({pct:.1f}%)")
    logger.info("")
    
    logger.info("User Segment:")
    for segment, count in segment_counts.most_common():
        pct = count / len(enriched_users) * 100
        logger.info(f"  {segment}: {count} ({pct:.1f}%)")
    logger.info("")
    
    logger.info("Engagement Tier:")
    for tier, count in tier_counts.most_common():
        pct = count / len(enriched_users) * 100
        logger.info(f"  {tier}: {count} ({pct:.1f}%)")
    logger.info("")
    
    # Step 10: Log top 50 user summaries
    logger.info("=" * 80)
    logger.info("TOP 50 USER SUMMARIES")
    logger.info("=" * 80)
    # Sort by event_count descending, then by name
    sorted_users = sorted(enriched_users, key=lambda u: (u.get('event_count', 0), u.get('name', '')), reverse=True)
    for i, user in enumerate(sorted_users[:50], 1):
        name = user.get('name', 'Unknown')
        event_count = user.get('event_count', 0)
        summary = user.get('summary', 'No summary available')
        logger.info(f"{i}. {name} (Events: {event_count})")
        logger.info(f"   {summary}")
        logger.info("")
    
    # Step 11: Save enriched users
    logger.info("STEP 11: Saving enriched users...")
    save_enriched_users(enriched_users, output_path)
    logger.info(f"Saved {len(enriched_users)} enriched users to {output_path}")
    logger.info("")
    
    # Final summary
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total users enriched: {len(enriched_users)}")
    logger.info(f"Output file: {output_path}")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 80)
    
    print(f"\nPipeline completed. Enriched users: {len(enriched_users)}")


if __name__ == "__main__":
    main()

