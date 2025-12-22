"""
Step 2: Event Selection Pipeline

This script loads event data and filters events based on:
1. Future events (startDate is in the future)
2. Public events (type is "public")
3. Active events (eventStatus is not "canceled")
4. Events with available capacity (len(participants) < maxParticipants)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path


def load_events(filepath):
    """
    Load events from JSON file.
    
    Args:
        filepath: Path to events.json file
        
    Returns:
        List of event dictionaries
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        events = json.load(f)
    return events


def parse_iso_date(date_string):
    """
    Parse ISO 8601 date string with 'Z' timezone to datetime object.
    
    Handles format: "2019-08-05T17:00:00.000Z"
    
    Args:
        date_string: ISO 8601 date string with 'Z' timezone
        
    Returns:
        datetime object in UTC timezone
    """
    # Replace 'Z' with '+00:00' for fromisoformat compatibility
    if date_string.endswith('Z'):
        date_string = date_string[:-1] + '+00:00'
    return datetime.fromisoformat(date_string)


def filter_future_events(events):
    """
    Filter events to keep only those with startDate in the future.
    
    Args:
        events: List of event dictionaries
        
    Returns:
        Tuple of (filtered_events, statistics_dict)
        statistics_dict contains:
        - total_events: int
        - past_events: int
        - invalid_date_events: int
        - filtered_count: int
    """
    total_events = len(events)
    now = datetime.now(timezone.utc)
    
    filtered_events = []
    past_events = 0
    invalid_date_events = 0
    
    for event in events:
        start_date_str = event.get('startDate')
        
        if not start_date_str:
            invalid_date_events += 1
            continue
        
        try:
            start_date = parse_iso_date(start_date_str)
            if start_date > now:
                filtered_events.append(event)
            else:
                past_events += 1
        except (ValueError, TypeError):
            invalid_date_events += 1
    
    statistics = {
        'total_events': total_events,
        'past_events': past_events,
        'invalid_date_events': invalid_date_events,
        'filtered_count': len(filtered_events)
    }
    
    return filtered_events, statistics


def filter_public_events(events):
    """
    Filter events to keep only public events (type == "public").
    
    Args:
        events: List of event dictionaries
        
    Returns:
        Tuple of (filtered_events, statistics_dict)
        statistics_dict contains:
        - total_events: int
        - private_events: int
        - missing_type_events: int
        - filtered_count: int
    """
    total_events = len(events)
    
    filtered_events = []
    private_events = 0
    missing_type_events = 0
    
    for event in events:
        event_type = event.get('type')
        
        if not event_type:
            missing_type_events += 1
            continue
        
        if event_type == 'public':
            filtered_events.append(event)
        else:
            private_events += 1
    
    statistics = {
        'total_events': total_events,
        'private_events': private_events,
        'missing_type_events': missing_type_events,
        'filtered_count': len(filtered_events)
    }
    
    return filtered_events, statistics


def filter_active_events(events):
    """
    Filter events to keep only those that are not canceled.
    
    Events with eventStatus == "canceled" are filtered out.
    
    Args:
        events: List of event dictionaries
        
    Returns:
        Tuple of (filtered_events, statistics_dict)
        statistics_dict contains:
        - total_events: int
        - canceled_events: int
        - filtered_count: int
    """
    total_events = len(events)
    
    filtered_events = []
    canceled_events = 0
    
    for event in events:
        event_status = event.get('eventStatus')
        
        # Filter out canceled events
        if event_status and event_status.lower() == 'canceled':
            canceled_events += 1
            continue
        
        filtered_events.append(event)
    
    statistics = {
        'total_events': total_events,
        'canceled_events': canceled_events,
        'filtered_count': len(filtered_events)
    }
    
    return filtered_events, statistics


def filter_events_with_capacity(events):
    """
    Filter events to keep only those with available capacity.
    
    Events must have len(participants) < maxParticipants.
    
    Args:
        events: List of event dictionaries
        
    Returns:
        Tuple of (filtered_events, statistics_dict)
        statistics_dict contains:
        - total_events: int
        - full_events: int
        - missing_fields_events: int
        - filtered_count: int
    """
    total_events = len(events)
    
    filtered_events = []
    full_events = 0
    missing_fields_events = 0
    
    for event in events:
        participants = event.get('participants')
        max_participants = event.get('maxParticipants')
        
        # Check if required fields exist
        if participants is None or max_participants is None:
            missing_fields_events += 1
            continue
        
        # Ensure participants is a list
        if not isinstance(participants, list):
            missing_fields_events += 1
            continue
        
        # Ensure maxParticipants is a number
        if not isinstance(max_participants, (int, float)):
            missing_fields_events += 1
            continue
        
        # Check if event has available capacity
        current_count = len(participants)
        if current_count < max_participants:
            filtered_events.append(event)
        else:
            full_events += 1
    
    statistics = {
        'total_events': total_events,
        'full_events': full_events,
        'missing_fields_events': missing_fields_events,
        'filtered_count': len(filtered_events)
    }
    
    return filtered_events, statistics


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
    log_file = log_dir / f'event_selection_{timestamp}.log'
    
    logger = logging.getLogger('event_selection')
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


def save_qualified_events(events, output_path):
    """
    Save qualified events to JSON file.
    
    Args:
        events: List of qualified event dictionaries
        output_path: Path to output JSON file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
    
    return output_path


def format_date_for_display(date_string):
    """
    Format ISO 8601 date string for display.
    
    Args:
        date_string: ISO 8601 date string
        
    Returns:
        Formatted date string (e.g., "Dec 26, 2025 at 6:30 PM")
    """
    try:
        dt = parse_iso_date(date_string)
        return dt.strftime('%b %d, %Y at %I:%M %p')
    except (ValueError, TypeError):
        return date_string


def log_qualified_events(logger, events):
    """
    Log list of qualified events with name, date, and participants info.
    
    Args:
        logger: Logger instance
        events: List of qualified event dictionaries
    """
    logger.info("")
    logger.info("QUALIFIED EVENTS")
    logger.info("=" * 80)
    
    if not events:
        logger.info("No qualified events found.")
        return
    
    for event in events:
        name = event.get('name', 'Unknown')
        start_date = event.get('startDate', 'Unknown')
        participants = event.get('participants', [])
        max_participants = event.get('maxParticipants', 'Unknown')
        
        current_count = len(participants) if isinstance(participants, list) else 0
        formatted_date = format_date_for_display(start_date)
        
        logger.info(f"  - {name}")
        logger.info(f"    Date: {formatted_date}")
        logger.info(f"    Participants: {current_count}/{max_participants}")
        logger.info("")


def main():
    """
    Main function to run the event selection pipeline.
    """
    # Define paths
    base_dir = Path(__file__).parent.parent
    events_path = base_dir / 'data' / 'raw' / 'events.json'
    output_path = base_dir / 'data' / 'processed' / 'qualified_events.json'
    log_dir = base_dir / 'logs'
    
    # Setup logging
    logger, log_file = setup_logging(log_dir)
    
    logger.info("=" * 80)
    logger.info("EVENT SELECTION PIPELINE - STEP 2")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    # Step 1: Load events
    logger.info("STEP 1: Loading events...")
    events = load_events(events_path)
    logger.info(f"Loaded {len(events)} events from {events_path}")
    logger.info("")
    
    # Step 2: Filter future events
    logger.info("STEP 2: Filtering future events...")
    future_events, future_stats = filter_future_events(events)
    logger.info(f"Total events: {future_stats['total_events']}")
    logger.info(f"Past events (filtered out): {future_stats['past_events']}")
    logger.info(f"Invalid date events (filtered out): {future_stats['invalid_date_events']}")
    logger.info(f"Future events remaining: {future_stats['filtered_count']}")
    logger.info("")
    
    # Step 3: Filter public events
    logger.info("STEP 3: Filtering public events...")
    public_events, public_stats = filter_public_events(future_events)
    logger.info(f"Total events before public filter: {public_stats['total_events']}")
    logger.info(f"Private events (filtered out): {public_stats['private_events']}")
    logger.info(f"Missing type events (filtered out): {public_stats['missing_type_events']}")
    logger.info(f"Public events remaining: {public_stats['filtered_count']}")
    logger.info("")
    
    # Step 4: Filter out canceled events
    logger.info("STEP 4: Filtering out canceled events...")
    active_events, active_stats = filter_active_events(public_events)
    logger.info(f"Total events before active filter: {active_stats['total_events']}")
    logger.info(f"Canceled events (filtered out): {active_stats['canceled_events']}")
    logger.info(f"Active events remaining: {active_stats['filtered_count']}")
    logger.info("")
    
    # Step 5: Filter events with capacity
    logger.info("STEP 5: Filtering events with available capacity...")
    qualified_events, capacity_stats = filter_events_with_capacity(active_events)
    logger.info(f"Total events before capacity filter: {capacity_stats['total_events']}")
    logger.info(f"Full events (filtered out): {capacity_stats['full_events']}")
    logger.info(f"Missing fields events (filtered out): {capacity_stats['missing_fields_events']}")
    logger.info(f"Events with capacity remaining: {capacity_stats['filtered_count']}")
    logger.info("")
    
    # Step 6: Log qualified events
    log_qualified_events(logger, qualified_events)
    
    # Step 7: Save qualified events
    logger.info("STEP 7: Saving qualified events...")
    save_qualified_events(qualified_events, output_path)
    logger.info(f"Saved {len(qualified_events)} qualified events to {output_path}")
    logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total events loaded: {len(events)}")
    logger.info(f"Events filtered out (past events): {future_stats['past_events']}")
    logger.info(f"Events filtered out (private events): {public_stats['private_events']}")
    logger.info(f"Events filtered out (canceled events): {active_stats['canceled_events']}")
    logger.info(f"Events filtered out (no capacity): {capacity_stats['full_events']}")
    logger.info(f"FINAL QUALIFIED EVENTS: {len(qualified_events)}")
    logger.info("")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Output file: {output_path}")
    logger.info("=" * 80)
    
    return len(qualified_events)


if __name__ == '__main__':
    qualified_count = main()
    print(f"\n✓ Pipeline completed. Qualified events: {qualified_count}")

