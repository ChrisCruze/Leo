#!/usr/bin/env python3
"""
Seat Newcomers Campaign Script

This script identifies newcomers (0-2 events attended, recently joined) with complete profiles,
ranks them by conversion potential (prioritizing 0 events), and matches them with perfect,
welcoming events for their first table to drive first-time RSVPs.
"""

import os
import sys
import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from collections import defaultdict

# Third-party imports
try:
    import pymongo
    from pymongo import MongoClient
    from bson import ObjectId
    from urllib.parse import quote_plus
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    import ssl
    from anthropic import Anthropic
    from dotenv import load_dotenv
except ImportError as e:
    print(f"ERROR: Missing required dependency: {e}")
    print("Please install requirements: pip install pymongo anthropic python-dotenv")
    sys.exit(1)

# Load environment variables from .env file (matching leo_automation.py)
script_dir = os.path.dirname(os.path.abspath(__file__))
env_file = os.path.join(script_dir, '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    # Try parent directory
    parent_env = os.path.join(os.path.dirname(script_dir), '.env')
    if os.path.exists(parent_env):
        load_dotenv(parent_env)
    else:
        # Try to load from current directory as fallback
        load_dotenv()

# Add backend directory to path to import utils
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')
utils_dir = os.path.join(backend_dir, 'utils')
sys.path.insert(0, backend_dir)

# Import from utils modules
from utils.report_creation.report_generator import generate_report
from utils.firebase_manage.firebase_manager import FirebaseManager
from utils.mongodb_pull.mongodb_pull import MongoDBPull

# ============================================================================
# LOGGING SETUP (matching leo_automation.py)
# ============================================================================

def setup_logging(log_dir: str = None) -> logging.Logger:
    """
    Set up comprehensive logging to both file and console.
    
    Creates a timestamped log file in the logs directory and also outputs
    to console for real-time monitoring.
    
    Args:
        log_dir: Directory for log files (default: 'logs')
    
    Returns:
        Configured logger instance
    """
    if log_dir is None:
        # Create logs directory in the same directory as this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(script_dir, 'logs')
    
    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Create timestamped log file
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_dir, f"seat_newcomers_{timestamp}.log")
    
    # Configure logging
    logger = logging.getLogger('SeatNewcomers')
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers = []
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger


class SeatNewcomersCampaign:
    """Main campaign class for Seat Newcomers initiative"""

    def __init__(self, logger: logging.Logger = None):
        """Initialize connections to MongoDB, Firebase, and Anthropic"""
        self.logger = logger or logging.getLogger('SeatNewcomers')
        self.campaign_id = f"seat-newcomers-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.campaign_name = "seat-newcomers"
        self.all_users_cache: List[Dict[str, Any]] = []
        self.user_lookup: Dict[str, Dict[str, Any]] = {}
        
        # Get script directory for data folder paths
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_raw_dir = os.path.join(self.script_dir, 'data', 'raw')
        self.data_processed_dir = os.path.join(self.script_dir, 'data', 'processed')
        self.data_output_dir = os.path.join(self.script_dir, 'data', 'output')
        
        # Create data directories
        os.makedirs(self.data_raw_dir, exist_ok=True)
        os.makedirs(self.data_processed_dir, exist_ok=True)
        os.makedirs(self.data_output_dir, exist_ok=True)

        # Statistics
        self.stats = {
            'users_processed': 0,
            'events_processed': 0,
            'matches_created': 0,
            'messages_generated': 0,
            'errors': []
        }

        # Store prompt templates for reporting
        self.matching_prompt_template = None
        self.message_generation_prompt_template = None

        # Initialize connections
        self._init_mongodb()
        self._init_firebase()
        self._init_anthropic()
        
        # Initialize Firebase Manager (with local testing support)
        save_local = os.getenv('SAVE_LOCAL', 'false').lower() == 'true'
        self.firebase_manager = FirebaseManager(
            firebase_url=self.firebase_url,
            base_path=self.firebase_base_path,
            save_local=save_local,
            local_data_dir=self.data_output_dir,
            logger_instance=self.logger
        )

        self.logger.info(f"Campaign initialized: {self.campaign_id}")

    def _init_mongodb(self):
        """Initialize MongoDB connection using mongodb_pull helper"""
        try:
            # Use mongodb_pull helper for MongoDB connection
            self.mongodb_pull = MongoDBPull(logger=self.logger)
            self.mongo_client = self.mongodb_pull.connection.client
            self.db = self.mongodb_pull.connection.get_database()
            self.users_collection = self.db['user']
            self.events_collection = self.db['event']
            self.logger.info("MongoDB connection established via mongodb_pull helper")
        except Exception as e:
            self.logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def _init_firebase(self):
        """Initialize Firebase connection using HTTP API (matching leo_automation.py)"""
        try:
            # Firebase Configuration (matching leo_automation.py)
            self.firebase_url = os.getenv('FIREBASE_DATABASE_URL', 
                'https://cuculi-2c473.firebaseio.com').rstrip('/')
            self.firebase_base_path = os.getenv('FIREBASE_BASE_PATH', 'Leo2')
            
            self.logger.info(f"Firebase connection configured: {self.firebase_url}/{self.firebase_base_path}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Firebase: {e}")
            raise
    
    def _firebase_request(self, path: str, method: str = 'GET', data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Internal method to handle all Firebase HTTP requests (matching leo_automation.py)"""
        full_url = f"{self.firebase_url}/{self.firebase_base_path}/{path}.json"
        req_data = json.dumps(data).encode('utf-8') if data else None
        headers = {'Content-Type': 'application/json'}
        
        # Create SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        req = Request(full_url, data=req_data, method=method, headers=headers)
        
        try:
            with urlopen(req, context=ssl_context) as r:
                response_data = r.read().decode('utf-8')
                if response_data:
                    return json.loads(response_data)
                return None
        except HTTPError as e:
            if e.code == 404 and method == 'GET':
                return None
            raise ConnectionError(f"Firebase Error {e.code}: {e.reason} on URL {full_url}")
        except URLError as e:
            raise ConnectionError(f"Failed to connect to Firebase: {str(e)}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from Firebase: {str(e)}")

    def _init_anthropic(self):
        """Initialize Anthropic client for Cuculi MCP"""
        try:
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")

            self.anthropic_client = Anthropic(api_key=api_key)
            self.logger.info("Anthropic client initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Anthropic client: {e}")
            raise

    def _convert_objectid(self, obj: Any) -> Any:
        """Helper function to convert ObjectId to string for JSON serialization (matching leo_automation.py)"""
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_objectid(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_objectid(item) for item in obj]
        else:
            return obj


    def _save_raw_data(self, users: List[Dict[str, Any]], events: List[Dict[str, Any]]):
        """Save raw data to JSON files in data/raw folder (matching leo_automation.py)"""
        try:
            # Save users
            users_file = os.path.join(self.data_raw_dir, 'users.json')
            users_serializable = self._convert_objectid(users)
            with open(users_file, 'w', encoding='utf-8') as f:
                json.dump(users_serializable, f, indent=2, ensure_ascii=False, default=str)
            self.logger.info(f"✓ Saved {len(users)} users to {users_file}")
            
            # Save events
            events_file = os.path.join(self.data_raw_dir, 'events.json')
            events_serializable = self._convert_objectid(events)
            with open(events_file, 'w', encoding='utf-8') as f:
                json.dump(events_serializable, f, indent=2, ensure_ascii=False, default=str)
            self.logger.info(f"✓ Saved {len(events)} events to {events_file}")
        except Exception as e:
            self.logger.error(f"Error saving raw data: {e}")

    def _save_processed_users(self, users: List[Dict[str, Any]]):
        """Save processed users to JSON file in data/processed folder"""
        try:
            users_file = os.path.join(self.data_processed_dir, 'newcomer_users.json')
            users_serializable = self._convert_objectid(users)
            with open(users_file, 'w', encoding='utf-8') as f:
                json.dump(users_serializable, f, indent=2, ensure_ascii=False, default=str)
            self.logger.info(f"✓ Saved {len(users)} processed users to {users_file}")
        except Exception as e:
            self.logger.error(f"Error saving processed users: {e}")

    def _save_processed_events(self, events: List[Dict[str, Any]]):
        """Save processed events to JSON file in data/processed folder"""
        try:
            events_file = os.path.join(self.data_processed_dir, 'future_events.json')
            events_serializable = self._convert_objectid(events)
            with open(events_file, 'w', encoding='utf-8') as f:
                json.dump(events_serializable, f, indent=2, ensure_ascii=False, default=str)
            self.logger.info(f"✓ Saved {len(events)} processed events to {events_file}")
        except Exception as e:
            self.logger.error(f"Error saving processed events: {e}")

    def _save_processed_matches(self, matches: List[Dict[str, Any]]):
        """Save matches to JSON file in data/processed folder"""
        try:
            matches_file = os.path.join(self.data_processed_dir, 'matches.json')
            matches_serializable = self._convert_objectid(matches)
            with open(matches_file, 'w', encoding='utf-8') as f:
                json.dump(matches_serializable, f, indent=2, ensure_ascii=False, default=str)
            self.logger.info(f"✓ Saved {len(matches)} matches to {matches_file}")
        except Exception as e:
            self.logger.error(f"Error saving matches: {e}")

    def _save_processed_messages(self, messages: List[Dict[str, Any]]):
        """Save messages to JSON file in data/processed folder"""
        try:
            messages_file = os.path.join(self.data_processed_dir, 'messages.json')
            messages_serializable = self._convert_objectid(messages)
            with open(messages_file, 'w', encoding='utf-8') as f:
                json.dump(messages_serializable, f, indent=2, ensure_ascii=False, default=str)
            self.logger.info(f"✓ Saved {len(messages)} messages to {messages_file}")
        except Exception as e:
            self.logger.error(f"Error saving messages: {e}")

    def get_newcomer_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get newcomer users (0-2 events, joined within 90 days) with complete profiles, ranked by newcomer score.
        Uses mongodb_pull helper to get fully enriched users.

        Args:
            limit: Maximum number of users to return (default: 10)

        Returns:
            List of enriched user documents with newcomer scores, sorted by score (descending)
        """
        self.logger.info("Fetching newcomer users with complete profiles using mongodb_pull...")

        try:
            # Get fully enriched users from mongodb_pull
            all_enriched_users = self.mongodb_pull.users_pull(generate_report=False)
            
            # Cache users for participant enrichment downstream
            self.all_users_cache = all_enriched_users
            self.user_lookup = {str(u.get('_id')): u for u in all_enriched_users if u.get('_id')}
            self.logger.info(f"Found {len(all_enriched_users)} total enriched users")
            
            # Save raw data to JSON files (using enriched users)
            all_events = self.mongodb_pull.connection.get_events()
            self._save_raw_data(all_enriched_users, all_events)

            # Filter for users who qualify for seat-newcomers campaign
            newcomer_users = [
                user for user in all_enriched_users
                if user.get('campaign_qualifications', {}).get('qualifies_seat_newcomers', False)
            ]
            
            self.logger.info(f"Found {len(newcomer_users)} users qualified for seat-newcomers campaign")

            # Add is_first_timer flag for logging
            for user in newcomer_users:
                event_count = user.get('event_count', 0)
                user['is_first_timer'] = (event_count == 0)
                # Use event_count instead of eventCount for consistency
                user['eventCount'] = event_count  # Keep for backward compatibility

            # Sort by newcomer score (descending) - already calculated in enriched data
            newcomer_users.sort(key=lambda x: x.get('newcomer_score', 0), reverse=True)

            # Get top users
            top_newcomer_users = newcomer_users[:limit]

            self.stats['users_processed'] = len(top_newcomer_users)
            self.logger.info(f"Selected top {len(top_newcomer_users)} newcomer users by score")
            first_timers = sum(1 for u in top_newcomer_users if u.get('is_first_timer', False))
            few_events = len(top_newcomer_users) - first_timers
            self.logger.info(f"  First-timers (0 events): {first_timers}, Few events (1-2): {few_events}")
            for i, user in enumerate(top_newcomer_users, 1):
                name = f"{user.get('firstName', '')} {user.get('lastName', '')}".strip()
                score = user.get('newcomer_score', 0)
                events = user.get('event_count', 0)
                days = user.get('days_since_registration', 0)
                first_timer = "FIRST-TIMER" if user.get('is_first_timer') else f"{events} events"
                self.logger.info(f"  {i}. {name}: score={score}, {first_timer}, days_since_join={days}")

            return top_newcomer_users

        except Exception as e:
            self.logger.error(f"Error fetching newcomer users: {e}")
            self.stats['errors'].append(f"Error fetching users: {str(e)}")
            return []

    def get_future_events(self) -> List[Dict[str, Any]]:
        """
        Get future public events, preferring beginner-friendly events with good participation.
        Uses mongodb_pull helper to get fully enriched events.

        Returns:
            List of enriched event documents with participation percentage, sorted by participation (50-80% ideal)
        """
        self.logger.info("Fetching future events (preferring beginner-friendly) using mongodb_pull...")

        try:
            # Get fully enriched events from mongodb_pull
            all_enriched_events = self.mongodb_pull.events_pull(generate_report=False)
            self.logger.info(f"Found {len(all_enriched_events)} total enriched events")

            # Filter for events that qualify for seat-newcomers campaign (future, public, 50-80% participation)
            future_events = [
                event for event in all_enriched_events
                if event.get('campaign_qualifications', {}).get('qualifies_seat_newcomers', False)
            ]

            # Sort by participation percentage (prefer 50-80% range for beginner-friendliness)
            # Create a custom sort key that prioritizes 50-80% range
            def sort_key(e):
                pct = e.get('participationPercentage', 0)
                if 50 <= pct <= 80:
                    # Ideal range: sort by how close to 65% (middle of ideal range)
                    return abs(65 - pct)
                elif pct < 50:
                    # Below ideal: add penalty
                    return 1000 + (50 - pct)
                else:
                    # Above ideal: add penalty
                    return 1000 + (pct - 80)

            future_events.sort(key=sort_key)

            self.stats['events_processed'] = len(future_events)
            self.logger.info(f"Found {len(future_events)} future public events")
            ideal_events = [e for e in future_events if 50 <= e.get('participationPercentage', 0) <= 80]
            self.logger.info(f"  Events in ideal range (50-80% filled): {len(ideal_events)}")
            if future_events:
                top_events_str = ', '.join([f"{e.get('name', 'N/A')} ({e.get('participationPercentage', 0):.1f}%)" for e in future_events[:5]])
                self.logger.info(f"  Top 5 events by suitability: {top_events_str}")

            return future_events

        except Exception as e:
            self.logger.error(f"Error fetching future events: {e}")
            self.stats['errors'].append(f"Error fetching events: {str(e)}")
            return []


    def create_individual_matching_prompt(self, user: Dict[str, Any], events: List[Dict[str, Any]]) -> str:
        """
        Create an individual prompt for matching a single user to the best first event.

        Args:
            user: User document with summary
            events: List of all available event documents with summaries

        Returns:
            Prompt string for the AI
        """
        # Get user name and summary
        first_name = user.get('firstName', '')
        last_name = user.get('lastName', '')
        user_name = f"{first_name} {last_name}".strip()
        user_summary = user.get('summary', '')
        
        # Prepare simplified event list - include name, ID, and summary
        event_list = []
        for event in events:
            event_name = event.get('name', '')
            event_id = str(event.get('_id', ''))
            event_summary = event.get('summary', 'Event summary not available')
            max_participants = event.get('maxParticipants', 0)
            participants = len(event.get('participants', []))
            fill_rate = (participants / max_participants * 100) if max_participants > 0 else 0
            event_list.append(f"- {event_name} (ID: {event_id}, {fill_rate:.1f}% full): {event_summary}")
        
        events_text = "\n".join(event_list)

        # Simplified prompt
        prompt = f"""You are an expert user onboarding specialist focused on converting new users to their first event attendance.

PRIORITY: Find the SINGLE BEST event for this newcomer that will convert them to RSVP to their FIRST table.

MATCHING CRITERIA (in order of importance):
1. Interest alignment: User interests MUST match event categories/features (this is critical for first-timers)
2. Location proximity: Prefer events in or near user's neighborhood for convenience
3. Event welcomingness: Prefer events with GOOD participation (50-80% filled) to show quality without feeling exclusive
4. Beginner-friendly: Consider events with welcoming descriptions, group-friendly features
5. Event timing: Prefer events happening soon (creates urgency for first RSVP)
6. First-time appeal: Events that feel welcoming and not intimidating for newcomers

IMPORTANT:
- Return ONLY the SINGLE BEST match (not multiple)
- This is their FIRST (or one of their first) events - make it count!
- Prioritize events with moderate participation (50-80% filled) - good social proof, not too exclusive
- The goal is to convert this user to their first RSVP
- Quality and relevance are critical for first-time conversion

Return a JSON object (not array) with:
- 'event_name': The event name (exact match from list below)
- 'event_id': The event ID (REQUIRED - use the ID from the event list below)
- 'reasoning': Detailed explanation (3-4 sentences) focusing on why this specific event is perfect for THIS user's FIRST table, how interests align (critical for first-timers), why the event is welcoming and beginner-friendly, and how location/timing work for first-time attendance
- 'confidence_percentage': Number 0-100 (should be 80+ for a good match)
- 'match_purpose': "convert_newcomer_first_table"

User:
Name: {user_name}
Summary: {user_summary}

Events:
{events_text}

Return only the JSON object, no additional text."""

        # Store prompt template for reporting
        self.matching_prompt_template = prompt

        return prompt

    def get_best_match_for_user(self, user: Dict[str, Any], events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Get the single best event match for a user using Claude API.

        Args:
            user: User document
            events: List of all available event documents

        Returns:
            Match dictionary or None if no match found
        """
        try:
            self.logger.info(f"Finding best match for user: {user.get('firstName', '')} {user.get('lastName', '')}")

            # Create individual prompt
            prompt = self.create_individual_matching_prompt(user, events)

            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",  # Matching leo_automation.py model
                max_tokens=4096,  # Matching leo_automation.py
                temperature=0.7,  # Lower temperature for more consistent matching
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract the response text
            response_text = response.content[0].text if response.content else ""
            self.logger.debug(f"Claude response: {response_text[:500]}...")

            # Parse JSON response using regex (matching leo_automation.py)
            try:
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    match = json.loads(json_match.group(0))
                else:
                    match = json.loads(response_text)
                
                # Ensure match is a dict (not list)
                if isinstance(match, list) and len(match) > 0:
                    match = match[0]
                
                if not isinstance(match, dict):
                    self.logger.error(f"Invalid match format: {type(match)}")
                    return None
                
                # Find the actual event object
                event_id = match.get('event_id', '')
                event_name = match.get('event_name', '')
                
                # Try to find by ID first
                matched_event = next((e for e in events if str(e.get('_id', '')) == event_id), None)
                
                # Fallback to name if ID lookup fails
                if not matched_event and event_name:
                    matched_event = next((e for e in events if e.get('name', '') == event_name), None)
                    if matched_event:
                        event_id = str(matched_event.get('_id', ''))
                        self.logger.info(f"  Matched by name instead of ID: {event_name}")
                
                if not matched_event:
                    self.logger.warning(f"Could not find event with ID: {event_id} or name: {event_name}")
                    return None
                
                # Build full match record
                first_name = user.get('firstName', '')
                last_name = user.get('lastName', '')
                user_name = f"{first_name} {last_name}".strip()
                
                match_record = {
                    'user_name': user_name,
                    'event_name': match.get('event_name', ''),
                    'user_id': str(user.get('_id', '')),
                    'event_id': event_id,
                    'confidence_percentage': match.get('confidence_percentage', 0),
                    'reasoning': match.get('reasoning', ''),
                    'match_purpose': match.get('match_purpose', 'convert_newcomer_first_table'),
                    'strategy': 'convert_newcomer_first_table',
                    'matched_at': datetime.now(timezone.utc).isoformat(),
                    'campaign': 'seat-newcomers',
                    'updatedAt': datetime.now(timezone.utc).isoformat(),
                    'user': user,  # Include full user object
                    'event': matched_event  # Include full event object
                }
                
                self.logger.info(f"  ✓ Found match: {user_name} → {match_record['event_name']} (confidence: {match_record['confidence_percentage']}%)")
                return match_record
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse Claude's response: {e}")
                self.logger.error(f"Raw response: {response_text[:500]}")
                return None

        except Exception as e:
            self.logger.error(f"Error getting match from AI: {e}")
            self.stats['errors'].append(f"Error getting AI match: {str(e)}")
            return None

    def generate_message_for_user(self, user: Dict[str, Any], event: Dict[str, Any], match_reasoning: str) -> Dict[str, Any]:
        """
        Generate a personalized first-time message for a user about an event (matching leo_automation.py)

        Args:
            user: User document
            event: Event document
            match_reasoning: Why this user was matched to this event

        Returns:
            Message dictionary with message_text, personalization_notes, character_count
        """
        try:
            first_name = user.get('firstName', '')
            last_name = user.get('lastName', '')
            user_name = f"{first_name} {last_name}".strip()
            
            # Prepare match summary (matching leo_automation.py format)
            match_summary = {
                'user_name': user_name,
                'event_name': event.get('name', ''),
                'user_summary': user.get('summary', 'User summary not available'),
                'event_summary': event.get('summary', 'Event summary not available'),
                'reasoning': match_reasoning,
                'user_id': str(user.get('_id', '')),
                'event_id': str(event.get('_id', '')),
                'is_first_timer': user.get('is_first_timer', False),
                'event_count': user.get('eventCount', 0),
                'days_since_join': user.get('days_since_registration', user.get('days_since_join', 0)),
                'personalization_ready': user.get('personalization_ready', False)
            }

            # Get event ID for link
            event_id = str(event.get('_id', ''))
            event_link = f"https://cucu.li/bookings/{event_id}"
            
            # Prompt with first-time conversion-focused best practices
            prompt = f"""You are an expert SMS copywriter specializing in converting new users to their first event attendance.

GOAL: Convert newcomers (0-2 events attended) to RSVP to their FIRST table.

SMS BEST PRACTICES:
1) LENGTH: <180 chars total (including link). Be concise.
2) TONE: Warm, welcoming, encouraging. Make them feel excited about their first event.
3) STRUCTURE: [Greeting + Name] [Welcome to community hook] [Event hook by interests/occupation/location] [Spots left + time urgency + social proof] [CTA + link at end].
4) FIRST-TIME FOCUS: Welcome them ("Welcome to Cuculi!", "Ready for your first table?", "Join us for your first event!").
5) PERSONALIZATION: Reference specific interests, neighborhood convenience, occupation if relevant.
6) WELCOMING: Emphasize that the event is welcoming, beginner-friendly, perfect for first-timers.
7) SCARCITY: Make spots left/time explicit; create urgency for first RSVP.
8) SOCIAL PROOF: Mention participants already in if available (shows community is active).
9) CTA: Tie directly to link ("Tap to RSVP: {event_link}"); link must be last.
10) AVOID: ALL CAPS, multiple questions, generic hype, long sentences, excessive punctuation, anything intimidating.

EXAMPLES (with links):
- "Hey Sarah! 👋 Welcome to Cuculi! Your first table: Ramen night Thu 7:30p near SoHo, 4 spots left—perfect for your food love. Join us! Tap to RSVP: https://cucu.li/bookings/12345"
- "Hi Mike! Ready for your first table? Comedy + dinner near West Village tomorrow, only 3 seats—welcoming group waiting. Tap to RSVP: https://cucu.li/bookings/12345"
- "Hi Priya! 🎉 Welcome! Mexican supper near SoMa, 2 spots left; walkable from you. Perfect first event! Tap to RSVP: https://cucu.li/bookings/12345"

Match context:
{json.dumps(match_summary, default=str, indent=2)}

Return a JSON object:
- message_text (must end with {event_link})
- personalization_notes
- character_count"""

            # Store prompt template for reporting (only need to capture once)
            if not self.message_generation_prompt_template:
                self.message_generation_prompt_template = prompt

            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",  # Matching leo_automation.py model
                max_tokens=4096,  # Matching leo_automation.py
                temperature=0.9,  # Higher creativity per request
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.content[0].text if response.content else ""
            
            # Parse JSON response using regex (matching leo_automation.py)
            try:
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    message_data = json.loads(json_match.group(0))
                else:
                    message_data = json.loads(response_text)
                
                message_text = message_data.get('message_text', '').strip()
                if not message_text:
                    # Fallback if parsing fails
                    raise ValueError("No message_text in response")
                
                # Ensure the message ends with the event link (in case AI didn't include it)
                if not message_text.endswith(event_link):
                    # Check if link is already in the message somewhere
                    if event_link not in message_text:
                        message_text = f"{message_text} {event_link}"
                    else:
                        # Link is in message but not at end - move it to end
                        message_text = message_text.replace(event_link, '').strip()
                        message_text = f"{message_text} {event_link}"
                
                self.logger.info(f"Generated message for user {user.get('_id')}: {message_text[:50]}...")
                self.stats['messages_generated'] += 1
                
                return {
                    'message_text': message_text,
                    'personalization_notes': message_data.get('personalization_notes', ''),
                    'character_count': len(message_text)  # Use actual length including link
                }
                
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.error(f"Failed to parse Claude's response: {e}")
                self.logger.error(f"Raw response: {response_text[:500]}")
                # Fallback message with event link
                event_title = event.get('name', 'an upcoming event')
                event_id = str(event.get('_id', ''))
                event_link = f"https://cucu.li/bookings/{event_id}"
                fallback = f"Hi {first_name}! 👋 Welcome to Cuculi! Ready for your first table? Check out {event_title}. Tap to RSVP: {event_link}"
                return {
                    'message_text': fallback,
                    'personalization_notes': 'Fallback message',
                    'character_count': len(fallback)
                }

        except Exception as e:
            self.logger.error(f"Error generating message: {e}")
            # Fallback message with event link
            first_name = user.get('firstName', 'there')
            event_title = event.get('name', 'an upcoming event')
            event_id = str(event.get('_id', ''))
            event_link = f"https://cucu.li/bookings/{event_id}"
            fallback = f"Hi {first_name}! 👋 Welcome to Cuculi! Ready for your first table? Check out {event_title}. Tap to RSVP: {event_link}"
            return {
                'message_text': fallback,
                'personalization_notes': 'Error fallback',
                'character_count': len(fallback)
            }

    def _generate_self_assessment(self, users: List[Dict[str, Any]], events: List[Dict[str, Any]], 
                                   matches: List[Dict[str, Any]], messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Use Claude API to automatically assess campaign results and generate recommendations.
        
        Args:
            users: List of processed users
            events: List of matched events
            matches: List of matches
            messages: List of generated messages
        
        Returns:
            Dictionary with assessment, strengths, recommendations, focus_areas
        """
        try:
            self.logger.info("Generating automatic self-assessment using Claude API...")
            
            # Prepare campaign data for analysis
            first_timers_count = sum(1 for u in users if u.get('eventCount', 0) == 0)
            few_events_count = sum(1 for u in users if 1 <= u.get('eventCount', 0) <= 2)
            
            campaign_data = {
                'users_processed': len(users),
                'first_timers_count': first_timers_count,
                'few_events_count': few_events_count,
                'average_newcomer_score': sum(u.get('newcomer_score', 0) for u in users) / len(users) if users else 0,
                'events_processed': len(events),
                'matches_created': len(matches),
                'average_confidence': sum(m.get('confidence_percentage', 0) for m in matches) / len(matches) if matches else 0,
                'messages_generated': len(messages),
                'average_message_length': sum(m.get('character_count', 0) for m in messages) / len(messages) if messages else 0,
                'sample_matches': matches[:3] if matches else [],  # Include sample matches for analysis
                'sample_messages': messages[:3] if messages else [],  # Include sample messages for analysis
                'errors': self.stats.get('errors', [])
            }
            
            prompt = f"""You are an expert campaign analyst reviewing a "Seat Newcomers" campaign designed to convert new users (0-2 events attended) to their first table RSVP.

CAMPAIGN GOAL: Convert newcomers to RSVP to their first table by matching them with welcoming, beginner-friendly events.

CAMPAIGN RESULTS:
{json.dumps(campaign_data, default=str, indent=2)}

ANALYZE:
1. User Selection: Were the right newcomers selected? (0 events prioritized over 1-2 events? Good profile completeness? Account recency appropriate?)
2. Event Matching: Were matches high-quality? (Interest alignment? Location proximity? Beginner-friendly events? Appropriate participation rates?)
3. Message Quality: Were messages welcoming and first-time focused? (Character count? Personalization? First-time language? Welcome messaging?)
4. Overall Performance: What worked well? What could be improved?

GENERATE RECOMMENDATIONS:
Provide 4-6 specific, actionable recommendations for improving first-time conversion rates. Focus on:
- User selection and ranking (prioritize 0 events, profile completeness, account recency)
- Event matching criteria (interest alignment, location, beginner-friendliness, participation rates)
- Message tone and content (welcome messaging, first-time language, personalization)
- First-time conversion strategies (removing barriers, creating excitement, building confidence)
- Any patterns you notice in successful vs unsuccessful matches

Return a JSON object with:
- 'assessment': Brief overall assessment (2-3 sentences)
- 'strengths': List of 2-3 things that worked well
- 'recommendations': List of 4-6 specific, actionable recommendations (each as a string)
- 'focus_areas': List of 2-3 areas to prioritize for next iteration

Return only the JSON object, no additional text."""

            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                temperature=0.7,  # Lower temperature for more consistent analysis
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse response
            response_text = response.content[0].text if response.content else ""
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                assessment = json.loads(json_match.group(0))
            else:
                assessment = json.loads(response_text)
            
            self.logger.info("✓ Generated self-assessment with recommendations")
            return assessment
            
        except Exception as e:
            self.logger.error(f"Error generating self-assessment: {e}")
            # Return fallback recommendations
            return {
                'assessment': 'Self-assessment could not be generated automatically. Review campaign results manually.',
                'strengths': ['Campaign executed successfully', 'Matches and messages generated'],
                'recommendations': [
                    'Review user selection criteria to ensure optimal newcomers are prioritized',
                    'Analyze match quality and interest alignment for first-time conversion',
                    'Review message tone and first-time language effectiveness',
                    'Track first-time RSVP conversion rates to measure success'
                ],
                'focus_areas': ['User selection', 'Message quality', 'Conversion tracking']
            }

    def save_campaign_data_to_firebase(self, users: List[Dict[str, Any]],
                                      events: List[Dict[str, Any]],
                                      matches: List[Dict[str, Any]],
                                      messages: List[Dict[str, Any]]):
        """Save all campaign data using FirebaseManager
        
        Saves users and events as individual nodes using their IDs.
        Matches and messages are saved incrementally (already done in run() method).
        """
        try:
            # Save users using FirebaseManager (handles campaign merging automatically)
            for user in users:
                self.firebase_manager.save_user(user, self.campaign_name)
            self.logger.info(f"✓ Saved {len(users)} users to Firebase")
            
            # Save events using FirebaseManager (handles campaign merging automatically)
            for event in events:
                self.firebase_manager.save_event(event, self.campaign_name)
            self.logger.info(f"✓ Saved {len(events)} events to Firebase")
            
            # Note: Matches and messages are already saved incrementally in run() method
            # via firebase_manager.save_match() and firebase_manager.save_message()
            
        except Exception as e:
            self.logger.error(f"Error saving campaign data: {e}")
            self.stats['errors'].append(f"Error saving campaign data: {str(e)}")

    def generate_report(self) -> Dict[str, Any]:
        """Generate final campaign report"""
        first_timers = sum(1 for u in getattr(self, '_processed_users', []) if u.get('eventCount', 0) == 0)
        few_events = sum(1 for u in getattr(self, '_processed_users', []) if 1 <= u.get('eventCount', 0) <= 2)
        
        report = {
            'campaign_id': self.campaign_id,
            'campaign_name': self.campaign_name,
            'run_date': datetime.now().isoformat(),
            'statistics': self.stats,
            'summary': {
                'total_newcomers_found': self.stats['users_processed'],
                'first_timers_count': first_timers,
                'few_events_count': few_events,
                'total_future_events': self.stats['events_processed'],
                'total_matches_created': self.stats['matches_created'],
                'total_messages_generated': self.stats['messages_generated'],
                'error_count': len(self.stats['errors'])
            },
            'errors': self.stats['errors']
        }

        return report

    def _save_local_output_files(self, users_data: Dict[str, Any], events_data: Dict[str, Any], 
                                  matches_data: Dict[str, Any], messages_data: Dict[str, Any]):
        """Save Firebase data structures to local output files"""
        try:
            # Save users
            users_file = os.path.join(self.data_output_dir, 'users.json')
            with open(users_file, 'w', encoding='utf-8') as f:
                json.dump(users_data, f, indent=2, default=str)
            self.logger.info(f"✓ Saved users to local output: {users_file}")
            
            # Save events
            events_file = os.path.join(self.data_output_dir, 'events.json')
            with open(events_file, 'w', encoding='utf-8') as f:
                json.dump(events_data, f, indent=2, default=str)
            self.logger.info(f"✓ Saved events to local output: {events_file}")
            
            # Save matches
            matches_file = os.path.join(self.data_output_dir, 'matches.json')
            with open(matches_file, 'w', encoding='utf-8') as f:
                json.dump(matches_data, f, indent=2, default=str)
            self.logger.info(f"✓ Saved matches to local output: {matches_file}")
            
            # Save messages
            messages_file = os.path.join(self.data_output_dir, 'messages.json')
            with open(messages_file, 'w', encoding='utf-8') as f:
                json.dump(messages_data, f, indent=2, default=str)
            self.logger.info(f"✓ Saved messages to local output: {messages_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving local output files: {e}")
            self.stats['errors'].append(f"Error saving local output files: {str(e)}")

    def _write_markdown_report(self, users: List[Dict[str, Any]], events: List[Dict[str, Any]],
                               matches: List[Dict[str, Any]], messages: List[Dict[str, Any]],
                               assessment: Optional[Dict[str, Any]] = None):
        """Write a concise markdown report to reports folder using shared generator."""
        try:
            reports_dir = os.path.join(self.script_dir, 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            report_file = os.path.join(reports_dir, f'seat_newcomers_report_{self.campaign_id}.md')

            goal = "Convert newcomers (0-2 events attended, recently joined) to RSVP to their first table by matching them with welcoming, beginner-friendly events."

            user_filtering_explanation = (
                "Users were filtered for being newcomers (0-2 events attended), having joined within the last 90 days, "
                "having complete profiles (at least 4 of 8 required fields: firstName, lastName, email, phone, "
                "gender, interests, occupation, homeNeighborhood), and having at least 1 interest. "
                "Users are ranked by newcomer score (event history priority + profile completeness + account recency)."
            )

            event_filtering_explanation = (
                "Events were filtered for being future public events. "
                "Events are sorted by participation percentage (preferring 50-80% range for beginner-friendliness) "
                "to provide welcoming, social-proof events for first-timers."
            )

            user_display_fields = {
                'newcomer_score': 'score',
                'eventCount': 'events',
                'days_since_join': 'days since join',
                'is_first_timer': 'status'
            }

            # Get prompts (should be set during matching/message generation)
            matching_prompt = self.matching_prompt_template or "Matching prompt not captured"
            message_prompt = self.message_generation_prompt_template or "Message generation prompt not captured"

            markdown_content = generate_report(
                users=users,
                events=events,
                matches=matches,
                messages=messages,
                goal=goal,
                campaign_id=self.campaign_id,
                campaign_name=self.campaign_name,
                user_filtering_explanation=user_filtering_explanation,
                event_filtering_explanation=event_filtering_explanation,
                matching_prompt=matching_prompt,
                message_generation_prompt=message_prompt,
                assessment=assessment,
                user_display_fields=user_display_fields
            )

            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            self.logger.info(f"✓ Wrote markdown report to {report_file}")
        except Exception as e:
            self.logger.error(f"Error writing markdown report: {e}")

    def run(self):
        """Main execution flow"""
        self.logger.info("=" * 80)
        self.logger.info(f"Starting Seat Newcomers Campaign: {self.campaign_id}")
        self.logger.info("=" * 80)

        try:
            # Step 1: Get top 34 newcomer users ranked by score
            self.logger.info("\n[Step 1] Fetching and ranking newcomer users...")
            top_newcomer_users = self.get_newcomer_users(limit=34)  # Process 34 users for 34 messages

            if not top_newcomer_users:
                self.logger.warning("No newcomer users found. Exiting.")
                return

            # Store for report generation
            self._processed_users = top_newcomer_users

            # Summaries are already included in enriched users from mongodb_pull
            # Save processed users to data/processed
            self._save_processed_users(top_newcomer_users)

            # Step 2: Get future events (preferring beginner-friendly)
            self.logger.info("\n[Step 2] Fetching future events...")
            future_events = self.get_future_events()

            if not future_events:
                self.logger.warning("No future events found. Exiting.")
                return

            # Summaries are already included in enriched events from mongodb_pull
            
            # Save processed events to data/processed
            self._save_processed_events(future_events)

            # Step 3: Match users to events (individual prompts per user)
            self.logger.info("\n[Step 3] Matching users to events (individual prompts)...")
            all_matches = []
            all_messages = []
            
            # Process each user individually
            matched_events = []  # Track which events were matched
            
            for user in top_newcomer_users:
                user_name = f"{user.get('firstName', '')} {user.get('lastName', '')}".strip()
                self.logger.info(f"\nProcessing user: {user_name}")

                # Get best match for this user
                match = self.get_best_match_for_user(user, future_events)
                
                if not match:
                    self.logger.warning(f"  ✗ No match found for {user_name}")
                    continue

                matched_event = match.get('event')
                if matched_event:
                    matched_events.append(matched_event)

                # Generate personalized message
                message_data = self.generate_message_for_user(user, matched_event, match.get('reasoning', ''))
                message_text = message_data.get('message_text', '')

                # Store match
                all_matches.append(match)
                self.stats['matches_created'] += 1
                
                # Save match using FirebaseManager
                self.firebase_manager.save_match(match)
                self.logger.info(f"  ✓ Saved match to Firebase: {user_name} → {match.get('event_name', '')}")

                # Store message
                first_name = user.get('firstName', '')
                last_name = user.get('lastName', '')
                user_name_full = f"{first_name} {last_name}".strip()
                matched_event = match.get('event')
                message_record = {
                    'user_name': user_name_full,
                    'event_name': match.get('event_name', ''),
                    'user_id': str(user.get('_id', '')),
                    'event_id': match.get('event_id', ''),
                    'user_email': user.get('email', ''),
                    'user_phone': user.get('phone', ''),
                    'user_summary': user.get('summary', ''),  # Include user summary
                    'event_summary': matched_event.get('summary', '') if matched_event else '',  # Include event summary
                    'message_text': message_text,
                    'personalization_notes': message_data.get('personalization_notes', ''),
                    'character_count': message_data.get('character_count', len(message_text)),
                    'similarity_score': match.get('confidence_percentage', 0),
                    'confidence_percentage': match.get('confidence_percentage', 0),
                    'reasoning': match.get('reasoning', ''),
                    'status': 'pending',
                    'generated_at': datetime.now(timezone.utc).isoformat(),
                    'campaign': 'seat-newcomers',
                    'updatedAt': datetime.now(timezone.utc).isoformat()
                }
                all_messages.append(message_record)
                
                # Save message using FirebaseManager
                self.firebase_manager.save_message(message_record)
                self.logger.info(f"  ✓ Saved message to Firebase for {user_name_full}")

                self.logger.info(f"  ✓ Matched {user_name_full} (confidence: {match.get('confidence_percentage', 0)}%)")

            # Step 4: Save campaign metadata to Firebase (matches and messages already saved incrementally)
            self.logger.info("\n[Step 4] Saving campaign metadata to Firebase...")
            # Only save matched events (not all future events)
            self.save_campaign_data_to_firebase(top_newcomer_users, matched_events, all_matches, all_messages)
            
            # Save matches and messages to data/processed
            self._save_processed_matches(all_matches)
            self._save_processed_messages(all_messages)

            # Step 5: Generate and save report
            self.logger.info("\n[Step 5] Generating final report...")
            report = self.generate_report()
            
            # Step 6: Generate automatic self-assessment using Claude API
            self.logger.info("\n[Step 6] Generating automatic self-assessment...")
            assessment = self._generate_self_assessment(top_newcomer_users, matched_events, all_matches, all_messages)
            
            # Write local markdown report with assessment (no longer saving to Firebase)
            self._write_markdown_report(top_newcomer_users, matched_events, all_matches, all_messages, assessment)

            # Print summary
            self.logger.info("\n" + "=" * 80)
            self.logger.info("CAMPAIGN COMPLETED SUCCESSFULLY")
            self.logger.info("=" * 80)
            self.logger.info(f"Users processed: {self.stats['users_processed']}")
            self.logger.info(f"Events processed: {self.stats['events_processed']}")
            self.logger.info(f"Matches created: {self.stats['matches_created']}")
            self.logger.info(f"Messages generated: {self.stats['messages_generated']}")
            self.logger.info(f"Errors encountered: {len(self.stats['errors'])}")
            self.logger.info("=" * 80)

            # Print report
            self.logger.info("\nFINAL REPORT:")
            self.logger.info(json.dumps(report, indent=2))
            
            # Print assessment
            if assessment:
                self.logger.info("\nAUTOMATIC SELF-ASSESSMENT:")
                self.logger.info(f"Assessment: {assessment.get('assessment', 'N/A')}")
                self.logger.info(f"Strengths: {assessment.get('strengths', [])}")
                self.logger.info(f"Recommendations: {assessment.get('recommendations', [])}")
                self.logger.info(f"Focus Areas: {assessment.get('focus_areas', [])}")

        except Exception as e:
            self.logger.error(f"Critical error in campaign execution: {e}")
            self.stats['errors'].append(f"Critical error: {str(e)}")
            raise
        finally:
            # Cleanup
            self.mongodb_pull.close()
            self.logger.info("\nCampaign execution finished.")


def main():
    """Main entry point"""
    # Set up logging (matching leo_automation.py)
    logger = setup_logging()
    
    try:
        # Create and run campaign
        campaign = SeatNewcomersCampaign(logger=logger)
        campaign.run()

    except KeyboardInterrupt:
        logger.info("\nCampaign interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()



