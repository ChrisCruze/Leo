"""
Step 5: User-Event Matching and Message Generation Pipeline

This script matches enriched users to enriched events using Claude AI, generates
personalized SMS messages, quality checks them, and uploads results to Airtable.

WORKFLOW:
---------
1. Load enriched users and events
2. For each user:
   - Match user to ideal event using Claude AI (determines campaign type)
   - Generate personalized message using Claude AI
   - Quality check message using Claude AI
   - Save to processed_messages.json
   - Upload to Airtable

PROMPTS:
--------
All prompts are defined at the top of this script for easy modification.

FIELD SCHEMAS:
=============

Input User Schema (from enriched_users.json):
- id, name, email, interests, summary, event_count, days_since_last_event, etc.

Input Event Schema (from enriched_events.json):
- id, name, startDate, venueName, neighborhood, summary, has_low_occupancy, etc.

Output Message Record Schema:
- user_name, event_name, user_id, event_id, user_email, user_phone
- user_summary, event_summary, message, reasoning, confidence_percentage, campaign
- match_reasoning, message_reasoning, quality_check_response
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add leo-dev root directory to Python path for imports
# This script is in pipeline/, so leo-dev root is parent directory
_script_dir = Path(__file__).parent
_leo_dev_root = _script_dir.parent
if str(_leo_dev_root) not in sys.path:
    sys.path.insert(0, str(_leo_dev_root))

# Import utility functions
from utils.ai_prompt import call_claude, parse_json_response
from utils.airtable_crud import create_message_record

# ============================================================================
# PROMPTS (Edit these to modify matching, message generation, and quality check)
# ============================================================================

MATCHING_PROMPT = """You are an expert event marketer focused on matching users to ideal events and determining the best campaign strategy.

PRIORITY: Find the SINGLE BEST event for this user and determine the appropriate campaign type.

CAMPAIGN TYPES:
- "Seat The Newcomer": For new users (0-2 events attended) - focus on welcoming, beginner-friendly events
- "Fill the Table": For users to fill low-occupancy events (event has low participation) - focus on urgency and scarcity
- "Return to Table": For dormant users (31+ days since last event or hasnt_attended_in_60_days) - focus on reactivation and quality events

CRITICAL: Gender compatibility is mandatory. If event name/description contains gender-specific terms (Girls/Women/Ladies for females, Boys/Men/Gentlemen for males), user gender MUST match. Mismatched events are ineligible regardless of other criteria.

MATCHING CRITERIA (in order of importance):
1. Interest alignment: User interests MUST align with event categories/features (critical)
2. Dietary compatibility: Event cuisine must not conflict with user dietary restrictions
3. Location proximity: Prefer events in or near user's neighborhood
4. Event quality: For "Return to Table" and "Seat The Newcomer", prefer events with good participation (50-80% filled)
5. Event urgency: For "Fill the Table", prioritize events with low occupancy that need participants
6. Event timing: Prefer events happening soon (creates urgency)

IMPORTANT:
- Return ONLY the SINGLE BEST match (not multiple)
- The campaign type should be determined by the user's profile (event_count, days_since_last_event, etc.)
- For "Fill the Table", the event should have has_low_occupancy = true
- For "Seat The Newcomer", user should have event_count <= 2
- For "Return to Table", user should have days_since_last_event >= 31 or hasnt_attended_in_60_days = true

Return a JSON object (not array) with:
- 'event_index': The index number from the events list below (0-based)
- 'campaign': One of "Seat The Newcomer", "Fill the Table", or "Return to Table"
- 'reasoning': Brief explanation (2-3 sentences) of why this event matches this user
- 'confidence': Number 0-100 (should be 80+ for a good match)

User Summary:
{user_summary}

Events (numbered list):
{events_summaries}

Return only the JSON object, no additional text."""

MESSAGE_GENERATION_PROMPT = """You are an expert SMS copywriter specializing in high-conversion, personalized, witty, and funny messages for a social dining app.

GOAL: Generate a message that drives RSVPs and attendance. Make it funny, witty, interesting, or engaging based on the campaign type.

CAMPAIGN CONTEXT:
- Campaign: {campaign}
- Campaign Objective: {campaign_objective}

SMS BEST PRACTICES:
1) LENGTH: Message text <130 chars (0 emojis) or <115 chars (1-2 emojis). Link (~50 chars) appended separately, total must be <180.
2) TONE: 
   - For "Seat The Newcomer": Warm, welcoming, encouraging, exciting about first event
   - For "Fill the Table": Friendly, urgent, scarcity-driven, social proof
   - For "Return to Table": Warm, welcoming, nostalgic, friend-like, acknowledge time away
3) STRUCTURE: [Greeting + Name] [Hook tied to interests/occupation/location/campaign] [Event details + urgency + social proof] [CTA].
4) PERSONALIZATION: Reference specific interests, neighborhood convenience, occupation if relevant. If user has dietary restrictions, ensure event cuisine is compatible.
5) SCARCITY: Make spots left/time explicit when applicable
6) SOCIAL PROOF: Mention participants already in if available
7) CTA: End with action phrase like "Tap to RSVP" or "Join us!" (link will be appended automatically)
8) BE FUNNY/WITTY/INTERESTING: Use humor, wit, or interesting angles to make the message stand out
9) AVOID: ALL CAPS, multiple questions, generic hype, long sentences, gender mismatches (matching error, not a creative challenge)

TWILIO RULES:
- Banned words: poker, casino, gambling, betting, marijuana, cannabis, CBD, crypto → use alternatives
- Limits: Message + link <180 chars total. With 1-2 emojis, keep message <115 chars.
- Do NOT include any links in your message - a link will be appended automatically
- Max 2 emojis if relevant

User Summary: {user_summary}
Event Summary: {event_summary}
Match Reasoning: {match_reasoning}

Return JSON:
{{
  "message": "text ending with CTA (no link, make it funny/witty/interesting)",
  "reasoning": "explanation of why this message will work",
  "confidence": <0-100>
}}"""

QUALITY_CHECK_PROMPT = """You are an expert SMS quality checker. Review this message for best practices and accuracy.

CHECKLIST:
0. Gender: User gender matches event gender requirements (if any). If mismatch, approved=false.
1. Length: Is total message (including link) under 180 characters?
2. Tone: Does it match the campaign type and SMS best practices?
3. Accuracy: Are all details correct (event name, date, venue, etc.)?
4. Personalization: Does it reference user interests, location, or other relevant details?
5. Dietary: Event cuisine compatible with user dietary restrictions (if any)
6. Clarity: Is the message clear and easy to understand?
7. CTA: Does it end with a clear call-to-action?
8. Twilio Compliance: No banned words, proper length for emoji count?
9. Engagement: Is it funny, witty, interesting, or engaging?

Message: {message}
User Summary: {user_summary}
Event Summary: {event_summary}
Campaign: {campaign}

Return JSON:
{{
  "quality_score": <0-100>,
  "approved": true/false,
  "issues": ["list of issues found"],
  "improved_message": "improved version if issues found, otherwise same as original"
}}"""

# Campaign objectives for message generation
CAMPAIGN_OBJECTIVES = {
    "Seat The Newcomer": "Convert newcomers (0-2 events attended) to RSVP to their FIRST table. Welcome them warmly and make them excited about their first event.",
    "Fill the Table": "Drive RSVPs to fill underbooked events. Create urgency and emphasize scarcity. Motivate immediate action.",
    "Return to Table": "Re-engage dormant users (31+ days inactive) and drive RSVPs. Acknowledge time away warmly and highlight quality events."
}

# ============================================================================
# LOGGING SETUP
# ============================================================================

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
    log_file = log_dir / f'match_message_{timestamp}.log'
    
    logger = logging.getLogger('match_message')
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


# ============================================================================
# DATA LOADING
# ============================================================================

def load_enriched_users(filepath):
    """
    Load enriched users from JSON file.
    
    Args:
        filepath: Path to enriched_users.json file
        
    Returns:
        List of user dictionaries
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        users = json.load(f)
    return users


def load_enriched_events(filepath):
    """
    Load enriched events from JSON file.
    
    Args:
        filepath: Path to enriched_events.json file
        
    Returns:
        List of event dictionaries
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        events = json.load(f)
    return events


def load_raw_users(filepath):
    """
    Load raw users from JSON file for phone number lookup.
    
    Args:
        filepath: Path to users.json file
        
    Returns:
        List of user dictionaries
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        users = json.load(f)
    return users


def create_phone_lookup(users: List[Dict]) -> Dict[str, str]:
    """
    Create lookup dictionary mapping email to phone number.
    
    Args:
        users: List of raw user dictionaries
        
    Returns:
        Dictionary mapping email to phone number
    """
    lookup = {}
    for user in users:
        email = user.get('email')
        phone = user.get('phone')
        if email and phone:
            lookup[email] = phone
    return lookup


# ============================================================================
# MATCHING FUNCTION
# ============================================================================

def match_user_to_event(user: Dict, events: List[Dict], logger: logging.Logger) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Match user to ideal event using Claude AI.
    
    Args:
        user: User dictionary with summary field
        events: List of event dictionaries with summary fields
        logger: Logger instance
        
    Returns:
        Tuple of (matched_event, match_result)
        - matched_event: Event dictionary if match found, None otherwise
        - match_result: Dictionary with event_index, campaign, confidence, reasoning
    """
    logger.info(f"Matching user: {user.get('name', 'Unknown')} ({user.get('email', 'Unknown')})")
    
    # Format events as numbered list
    events_summaries = []
    for i, event in enumerate(events):
        events_summaries.append(f"{i}. {event.get('name', 'Unknown Event')}\n   {event.get('summary', 'No summary')}")
    
    events_text = "\n\n".join(events_summaries)
    
    # Format matching prompt
    prompt = MATCHING_PROMPT.format(
        user_summary=user.get('summary', 'No user summary available'),
        events_summaries=events_text
    )
    
    # Call Claude AI
    response_text = call_claude(
        prompt=prompt,
        model="claude-sonnet-4-20250514",
        temperature=0.7,
        max_tokens=4096,
        logger=logger
    )
    
    # Parse JSON response
    match_result = parse_json_response(response_text, logger)
    
    # Get matched event
    event_index = match_result.get('event_index')
    if event_index is not None and 0 <= event_index < len(events):
        matched_event = events[event_index]
        logger.info(f"Matched to event: {matched_event.get('name')} (index {event_index})")
        logger.info(f"Campaign: {match_result.get('campaign')}")
        logger.info(f"Confidence: {match_result.get('confidence')}")
        return matched_event, match_result
    else:
        logger.error(f"Invalid event_index: {event_index}")
        return None, None


# ============================================================================
# MESSAGE GENERATION FUNCTION
# ============================================================================

def generate_message(
    user: Dict,
    event: Dict,
    match_result: Dict,
    logger: logging.Logger
) -> Optional[Dict]:
    """
    Generate personalized message using Claude AI.
    
    Args:
        user: User dictionary
        event: Event dictionary
        match_result: Match result dictionary with campaign and reasoning
        logger: Logger instance
        
    Returns:
        Dictionary with message, reasoning, confidence, or None if error
    """
    logger.info(f"Generating message for user: {user.get('name')} and event: {event.get('name')}")
    
    campaign = match_result.get('campaign', 'Fill the Table')
    campaign_objective = CAMPAIGN_OBJECTIVES.get(campaign, 'Drive RSVPs and attendance')
    match_reasoning = match_result.get('reasoning', 'No reasoning provided')
    
    # Format message generation prompt
    prompt = MESSAGE_GENERATION_PROMPT.format(
        campaign=campaign,
        campaign_objective=campaign_objective,
        user_summary=user.get('summary', 'No user summary available'),
        event_summary=event.get('summary', 'No event summary available'),
        match_reasoning=match_reasoning
    )
    
    # Call Claude AI with higher temperature for creativity
    response_text = call_claude(
        prompt=prompt,
        model="claude-sonnet-4-20250514",
        temperature=0.9,  # Higher temperature for more creative/witty messages
        max_tokens=4096,
        logger=logger
    )
    
    # Parse JSON response
    message_result = parse_json_response(response_text, logger)
    
    # Append event link
    event_id = event.get('id')
    if event_id:
        event_link = f"https://cucu.li/bookings/{event_id}"
        message_text = message_result.get('message', '')
        if message_text and not message_text.endswith(event_link):
            message_result['message'] = f"{message_text} {event_link}"
    
    logger.info(f"Generated message: {message_result.get('message', '')[:100]}...")
    return message_result


# ============================================================================
# QUALITY CHECK FUNCTION
# ============================================================================

def quality_check_message(
    message_result: Dict,
    user: Dict,
    event: Dict,
    campaign: str,
    logger: logging.Logger
) -> Optional[Dict]:
    """
    Quality check message using Claude AI.
    
    Args:
        message_result: Message result dictionary with message field
        user: User dictionary
        event: Event dictionary
        campaign: Campaign type string
        logger: Logger instance
        
    Returns:
        Dictionary with quality_score, approved, issues, improved_message, or None if error
    """
    logger.info("Running quality check on message...")
    
    message_text = message_result.get('message', '')
    
    # Format quality check prompt
    prompt = QUALITY_CHECK_PROMPT.format(
        message=message_text,
        user_summary=user.get('summary', 'No user summary available'),
        event_summary=event.get('summary', 'No event summary available'),
        campaign=campaign
    )
    
    # Call Claude AI
    response_text = call_claude(
        prompt=prompt,
        model="claude-sonnet-4-20250514",
        temperature=0.7,
        max_tokens=4096,
        logger=logger
    )
    
    # Parse JSON response
    quality_result = parse_json_response(response_text, logger)
    
    logger.info(f"Quality score: {quality_result.get('quality_score')}")
    logger.info(f"Approved: {quality_result.get('approved')}")
    
    return quality_result


# ============================================================================
# SAVE SUMMARIES TO MARKDOWN
# ============================================================================

def save_summaries_to_markdown(users: List[Dict], events: List[Dict], reports_dir: Path, logger: logging.Logger):
    """
    Save all user and event summaries to a markdown file.
    
    Args:
        users: List of enriched user dictionaries
        events: List of enriched event dictionaries
        reports_dir: Directory path for reports
        logger: Logger instance
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = reports_dir / f'summaries_{timestamp}.md'
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# User and Event Summaries\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total Users: {len(users)}\n")
        f.write(f"Total Events: {len(events)}\n\n")
        f.write("---\n\n")
        
        # Write user summaries
        f.write("## Users\n\n")
        for i, user in enumerate(users, 1):
            f.write(f"### User {i}: {user.get('name', 'Unknown')}\n\n")
            f.write(f"**Email:** {user.get('email', 'N/A')}\n\n")
            f.write(f"**Summary:**\n{user.get('summary', 'No summary available')}\n\n")
            f.write("---\n\n")
        
        # Write event summaries
        f.write("## Events\n\n")
        for i, event in enumerate(events, 1):
            f.write(f"### Event {i}: {event.get('name', 'Unknown Event')}\n\n")
            f.write(f"**ID:** {event.get('id', 'N/A')}\n\n")
            f.write(f"**Summary:**\n{event.get('summary', 'No summary available')}\n\n")
            f.write("---\n\n")
    
    logger.info(f"Saved summaries to {report_file}")
    return report_file


# ============================================================================
# SAVE PROCESSED MESSAGES
# ============================================================================

def save_processed_messages(messages: List[Dict], filepath):
    """
    Save processed messages to JSON file.
    
    Args:
        messages: List of message record dictionaries
        filepath: Path to output JSON file
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)
    
    return filepath


# ============================================================================
# PROCESS USER FUNCTION
# ============================================================================

def process_user(
    user: Dict,
    events: List[Dict],
    phone_lookup: Dict[str, str],
    logger: logging.Logger,
    enable_quality_check: bool = False
) -> Optional[Dict]:
    """
    Process one user through the full pipeline.
    
    Args:
        user: User dictionary
        events: List of event dictionaries
        phone_lookup: Dictionary mapping email to phone number
        logger: Logger instance
        enable_quality_check: Whether to run quality check (default: False)
        
    Returns:
        Message record dictionary if successful, None otherwise
    """
    logger.info("=" * 80)
    logger.info(f"Processing user: {user.get('name', 'Unknown')} ({user.get('email', 'Unknown')})")
    logger.info("=" * 80)
    
    # Step 1: Match user to event
    matched_event, match_result = match_user_to_event(user, events, logger)
    if not matched_event or not match_result:
        logger.error("Failed to match user to event")
        return None
    
    # Step 2: Generate message
    message_result = generate_message(user, matched_event, match_result, logger)
    if not message_result:
        logger.error("Failed to generate message")
        return None
    
    # Step 3: Quality check (optional)
    quality_result = None
    if enable_quality_check:
        quality_result = quality_check_message(
            message_result,
            user,
            matched_event,
            match_result.get('campaign', 'Fill the Table'),
            logger
        )
        
        # Use improved message if quality check provided one and message wasn't approved
        if quality_result and not quality_result.get('approved', True):
            improved_message = quality_result.get('improved_message')
            if improved_message:
                logger.info("Using improved message from quality check")
                # Ensure improved message has event link appended
                event_id = matched_event.get('id')
                if event_id:
                    event_link = f"https://cucu.li/bookings/{event_id}"
                    if improved_message and not improved_message.endswith(event_link):
                        improved_message = f"{improved_message} {event_link}"
                message_result['message'] = improved_message
    
    # Step 4: Create message record
    message_record = {
        'user_name': user.get('name'),
        'event_name': matched_event.get('name'),
        'user_id': user.get('id'),
        'event_id': matched_event.get('id'),
        'user_email': user.get('email'),
        'user_phone': phone_lookup.get(user.get('email')),  # Get from raw users lookup
        'user_summary': user.get('summary'),
        'event_summary': matched_event.get('summary'),
        'message': message_result.get('message'),
        'match_reasoning': match_result.get('reasoning'),  # Match reasoning
        'message_reasoning': message_result.get('reasoning'),  # Message generation reasoning
        'confidence_percentage': match_result.get('confidence', 0),
        'campaign': match_result.get('campaign', 'Fill the Table'),
        'quality_check_response': quality_result if quality_result else None,
        'generated_at': datetime.now().isoformat()
    }
    
    logger.info("=" * 80)
    logger.info("User processing complete")
    logger.info("=" * 80)
    logger.info("")
    
    return message_record


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """
    Main function to run the matching and messaging pipeline.
    """
    # Define paths
    base_dir = Path(__file__).parent.parent
    enriched_users_path = base_dir / 'data' / 'processed' / 'enriched_users.json'
    enriched_events_path = base_dir / 'data' / 'processed' / 'enriched_events.json'
    processed_messages_path = base_dir / 'data' / 'processed' / 'processed_messages.json'
    log_dir = base_dir / 'logs'
    reports_dir = base_dir / 'reports'
    
    # Quality check setting (off by default)
    enable_quality_check = False
    
    # Setup logging
    logger, log_file = setup_logging(log_dir)
    
    logger.info("=" * 80)
    logger.info("USER-EVENT MATCHING AND MESSAGE GENERATION PIPELINE - STEP 5")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    # Check for API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        logger.error("ANTHROPIC_API_KEY environment variable not set. Set it at root level.")
        return
    
    # Step 1: Load enriched users
    logger.info("STEP 1: Loading enriched users...")
    users = load_enriched_users(enriched_users_path)
    logger.info(f"Loaded {len(users)} enriched users")
    logger.info("")
    
    # Step 2: Load enriched events
    logger.info("STEP 2: Loading enriched events...")
    events = load_enriched_events(enriched_events_path)
    logger.info(f"Loaded {len(events)} enriched events")
    logger.info("")
    
    # Step 2.5: Load raw users for phone lookup
    logger.info("STEP 2.5: Loading raw users for phone lookup...")
    raw_users_path = base_dir / 'data' / 'raw' / 'users.json'
    raw_users = load_raw_users(raw_users_path)
    phone_lookup = create_phone_lookup(raw_users)
    logger.info(f"Created phone lookup with {len(phone_lookup)} entries")
    logger.info("")
    
    # Step 2.6: Save summaries to markdown
    logger.info("STEP 2.6: Saving user and event summaries to markdown...")
    save_summaries_to_markdown(users, events, reports_dir, logger)
    logger.info("")
    
    # Step 3: Process users
    logger.info("STEP 3: Processing users...")
    processed_messages = []
    
    stats = {
        'total_users': len(users),
        'matched': 0,
        'messages_generated': 0,
        'quality_checked': 0,
        'airtable_uploaded': 0,
        'errors': 0,
        'campaign_distribution': {}
    }
    
    for i, user in enumerate(users, 1):
        logger.info(f"Processing user {i}/{len(users)}")
        
        # Process user
        message_record = process_user(user, events, phone_lookup, logger, enable_quality_check=enable_quality_check)
        
        if message_record:
            # Add to processed messages
            processed_messages.append(message_record)
            stats['matched'] += 1
            stats['messages_generated'] += 1
            
            if message_record.get('quality_check_response'):
                stats['quality_checked'] += 1
            
            # Upload to Airtable
            success, record_id = create_message_record(message_record, logger=logger)
            if success:
                stats['airtable_uploaded'] += 1
                message_record['airtable_record_id'] = record_id
            else:
                logger.warning(f"Failed to upload message to Airtable for user: {user.get('name')}")
            
            # Track campaign distribution
            campaign = message_record.get('campaign', 'Unknown')
            stats['campaign_distribution'][campaign] = stats['campaign_distribution'].get(campaign, 0) + 1
        else:
            stats['errors'] += 1
    
    # Step 4: Save processed messages
    logger.info("")
    logger.info("STEP 4: Saving processed messages...")
    save_processed_messages(processed_messages, processed_messages_path)
    logger.info(f"Saved {len(processed_messages)} processed messages to {processed_messages_path}")
    logger.info("")
    
    # Step 5: Log statistics
    logger.info("=" * 80)
    logger.info("PIPELINE STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Total users processed: {stats['total_users']}")
    if stats['total_users'] > 0:
        logger.info(f"Users matched: {stats['matched']} ({stats['matched']/stats['total_users']*100:.1f}%)")
    else:
        logger.info(f"Users matched: {stats['matched']} (0%)")
    logger.info(f"Messages generated: {stats['messages_generated']}")
    logger.info(f"Messages quality checked: {stats['quality_checked']}")
    if stats['matched'] > 0:
        logger.info(f"Messages uploaded to Airtable: {stats['airtable_uploaded']} ({stats['airtable_uploaded']/stats['matched']*100:.1f}%)")
    else:
        logger.info(f"Messages uploaded to Airtable: {stats['airtable_uploaded']} (0%)")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("")
    logger.info("Campaign distribution:")
    for campaign, count in sorted(stats['campaign_distribution'].items()):
        logger.info(f"  {campaign}: {count}")
    logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total messages processed: {len(processed_messages)}")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Processed messages file: {processed_messages_path}")
    logger.info("=" * 80)
    
    print(f"\nPipeline completed. Processed messages: {len(processed_messages)}")


if __name__ == "__main__":
    main()

