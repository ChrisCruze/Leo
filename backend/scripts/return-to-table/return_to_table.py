#!/usr/bin/env python3
"""
Return To Table Campaign Script

This script identifies dormant users (31-90 days inactive) with complete profiles,
ranks them by reactivation potential, and matches them with perfect future events
to drive RSVPs and reactivate engagement.
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

# Add root directory to path to import helpers
root_dir = os.path.join(script_dir, '../..')
sys.path.insert(0, root_dir)
from helpers.report_creation.report_generator import generate_report
from helpers.firebase_manage.firebase_manager import FirebaseManager
from helpers.mongodb_pull import MongoDBPull
from utils.ai_generate import ai_generate_meta_tag_parse

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
    log_file = os.path.join(log_dir, f"return_to_table_{timestamp}.log")
    
    # Configure logging
    logger = logging.getLogger('ReturnToTable')
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


class ReturnToTableCampaign:
    """Main campaign class for Return To Table initiative"""

    def __init__(self, logger: logging.Logger = None):
        """Initialize connections to MongoDB, Firebase, and Anthropic"""
        self.logger = logger or logging.getLogger('ReturnToTable')
        self.campaign_id = f"return-to-table-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.campaign_name = "return-to-table"
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
            self.firebase_base_path = os.getenv('FIREBASE_BASE_PATH', 'Leo')
            
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

    # def _init_anthropic(self):
    #     """Initialize Anthropic client for Cuculi MCP"""
    #     try:
    #         api_key = os.getenv('ANTHROPIC_API_KEY')
    #         if not api_key:
    #             raise ValueError("ANTHROPIC_API_KEY not set")
    #
    #         self.anthropic_client = Anthropic(api_key=api_key)
    #         self.logger.info("Anthropic client initialized")
    #     except Exception as e:
    #         self.logger.error(f"Failed to initialize Anthropic client: {e}")
    #         raise

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
            users_file = os.path.join(self.data_processed_dir, 'dormant_users.json')
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

    def get_dormant_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get dormant users (31-90 days inactive) with complete profiles, ranked by reactivation score.
        Uses mongodb_pull helper to get fully enriched users.

        Args:
            limit: Maximum number of users to return (default: 10)

        Returns:
            List of enriched user documents with reactivation scores, sorted by score (descending)
        """
        self.logger.info("Fetching dormant users with complete profiles using mongodb_pull...")

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

            # Filter for users who qualify for return-to-table campaign (dormant, has events, profile complete)
            dormant_users = [
                user for user in all_enriched_users
                if user.get('campaign_qualifications', {}).get('qualifies_return_to_table', False)
            ]
            
            self.logger.info(f"Found {len(dormant_users)} users qualified for return-to-table campaign")

            # Add eventCount for backward compatibility
            for user in dormant_users:
                user['eventCount'] = user.get('event_count', 0)

            # Sort by reactivation score (descending) - already calculated in enriched data
            dormant_users.sort(key=lambda x: x.get('reactivation_score', 0), reverse=True)

            # Get top users
            top_dormant_users = dormant_users[:limit]

            self.stats['users_processed'] = len(top_dormant_users)
            self.logger.info(f"Selected top {len(top_dormant_users)} dormant users by reactivation score")
            for i, user in enumerate(top_dormant_users, 1):
                name = f"{user.get('firstName', '')} {user.get('lastName', '')}".strip()
                score = user.get('reactivation_score', 0)
                days = user.get('days_inactive', 0)
                events = user.get('event_count', 0)
                self.logger.info(f"  {i}. {name}: score={score}, days_inactive={days}, events={events}")

            return top_dormant_users

        except Exception as e:
            self.logger.error(f"Error fetching dormant users: {e}")
            self.stats['errors'].append(f"Error fetching users: {str(e)}")
            return []

    def get_future_events(self) -> List[Dict[str, Any]]:
        """
        Get future public events, preferring well-attended events (unlike fill-the-table).
        Uses mongodb_pull helper to get fully enriched events.

        Returns:
            List of enriched event documents with participation percentage, sorted by participation (descending)
        """
        self.logger.info("Fetching future events (preferring well-attended) using mongodb_pull...")

        try:
            # Get fully enriched events from mongodb_pull
            all_enriched_events = self.mongodb_pull.events_pull(generate_report=False)
            self.logger.info(f"Found {len(all_enriched_events)} total enriched events")

            # Filter for events that qualify for return-to-table campaign (future, public, higher participation preferred)
            future_events = [
                event for event in all_enriched_events
                if event.get('campaign_qualifications', {}).get('qualifies_return_to_table', False)
            ]

            # Sort by participation percentage (descending - most attended first)
            future_events.sort(key=lambda x: x.get('participationPercentage', 0), reverse=True)

            self.stats['events_processed'] = len(future_events)
            self.logger.info(f"Found {len(future_events)} future public events")
            top_events_str = ', '.join([f"{e.get('name', 'N/A')} ({e.get('participationPercentage', 0):.1f}%)" for e in future_events[:5]])
            self.logger.info(f"Top 5 events by participation: {top_events_str}")

            return future_events

        except Exception as e:
            self.logger.error(f"Error fetching future events: {e}")
            self.stats['errors'].append(f"Error fetching events: {str(e)}")
            return []


    def create_individual_matching_prompt(self, user: Dict[str, Any], events: List[Dict[str, Any]]) -> str:
        """
        Create an individual prompt for matching a single user to the best event.

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
        prompt = f"""You are an expert user reactivation specialist focused on re-engaging dormant users.

PRIORITY: Find the SINGLE BEST event for this dormant user (31-90 days inactive) that will re-engage them and drive an RSVP.

MATCHING CRITERIA (in order of importance):
1. Interest alignment: User interests MUST match event categories/features (this is critical)
2. Location proximity: Prefer events in or near user's neighborhood
3. Event quality: Prefer events with HIGH participation (50-100% filled) to show social proof and quality
4. Reactivation potential: Events similar to their past attendance patterns
5. Event timing: Prefer events happening soon (creates urgency for reactivation)
6. Welcome back vibe: Events that feel welcoming for returning users

IMPORTANT:
- Return ONLY the SINGLE BEST match (not multiple)
- Prioritize events with higher participation (50-100% filled) over empty events
- The goal is to reactivate this user with a high-quality, engaging event
- Quality and relevance are more important than filling empty events

Return a JSON object (not array) with:
- 'event_name': The event name (exact match from list below)
- 'event_id': The event ID (REQUIRED - use the ID from the event list below)
- 'reasoning': Detailed explanation (3-4 sentences) focusing on why this specific event will reactivate THIS user, how interests align, why the event quality/participation makes it appealing, and why location/timing work for reactivation
- 'confidence_percentage': Number 0-100 (should be 80+ for a good match)
- 'match_purpose': "reactivate_dormant_user"

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

            # Use ai_generate utility instead of direct API call
            match = ai_generate_meta_tag_parse(
                prompt=prompt,
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                temperature=0.7
            )

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
                'match_purpose': match.get('match_purpose', 'reactivate_dormant_user'),
                'strategy': 'reactivate_dormant_user',
                'matched_at': datetime.now(timezone.utc).isoformat(),
                'campaign': 'return-to-table',
                'updatedAt': datetime.now(timezone.utc).isoformat(),
                'user': user,
                'event': matched_event
            }

            self.logger.info(f"  ✓ Found match: {user_name} → {match_record['event_name']} (confidence: {match_record['confidence_percentage']}%)")
            return match_record

        except Exception as e:
            self.logger.error(f"Error getting match from AI: {e}")
            self.stats['errors'].append(f"Error getting AI match: {str(e)}")
            return None

    def generate_message_for_user(self, user: Dict[str, Any], event: Dict[str, Any], match_reasoning: str) -> Dict[str, Any]:
        """
        Generate a personalized reactivation message for a user about an event (matching leo_automation.py)

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
                'engagement_status': user.get('engagement_status'),
                'days_inactive': user.get('days_inactive'),
                'personalization_ready': user.get('personalization_ready'),
                'last_event_date': user.get('last_event_date')
            }

            # Get event ID for link
            event_id = str(event.get('_id', ''))
            event_link = f"https://cucu.li/bookings/{event_id}"
            
            # Prompt with reactivation-focused best practices
            prompt = f"""You are an expert SMS copywriter specializing in user reactivation for a social dining app.

GOAL: Re-engage dormant users (31-90 days inactive) and drive RSVPs to future events.

SMS BEST PRACTICES:
1) LENGTH: <180 chars total (including link). Be concise.
2) TONE: Warm, welcoming, friend-like. Acknowledge time away without being pushy.
3) STRUCTURE: [Greeting + Name] [Welcome back hook] [Event hook by interests/occupation/location] [Spots left + time urgency + social proof] [CTA + link at end].
4) REACTIVATION: Acknowledge they haven't been around ("We miss you!", "Welcome back!", "It's been a while!").
5) PERSONALIZATION: Reference specific interests, neighborhood convenience, occupation if relevant.
6) SCARCITY: Make spots left/time explicit; create urgency for reactivation.
7) SOCIAL PROOF: Mention participants already in if available.
8) CTA: Tie directly to link ("Tap to RSVP: {event_link}"); link must be last.
9) AVOID: ALL CAPS, multiple questions, generic hype, long sentences, excessive punctuation.

EXAMPLES (with links):
- "Hey Sarah! 👋 We miss you! Ramen night Thu 7:30p near Midtown, 4 spots left—your favorite Japanese flavors. Welcome back! Tap to RSVP: https://cucu.li/bookings/12345"
- "Hi Mike! It's been a while! Comedy + dinner near West Village tomorrow, only 3 seats—friends already in. Tap to RSVP: https://cucu.li/bookings/12345"
- "Hi Priya! Welcome back! 🎉 Mexican supper near SoMa, 2 spots left; walkable from you. Tap to RSVP: https://cucu.li/bookings/12345"

Match context:
{json.dumps(match_summary, default=str, indent=2)}

Return a JSON object:
- message_text (must end with {event_link})
- personalization_notes
- character_count"""

            # Store prompt template for reporting (only need to capture once)
            if not self.message_generation_prompt_template:
                self.message_generation_prompt_template = prompt

            # Use ai_generate utility instead of direct API call
            message_data = ai_generate_meta_tag_parse(
                prompt=prompt,
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                temperature=0.9
            )

            message_text = message_data.get('message_text', '').strip()
            if not message_text:
                raise ValueError("No message_text in response")

            # Ensure the message ends with the event link
            if not message_text.endswith(event_link):
                if event_link not in message_text:
                    message_text = f"{message_text} {event_link}"
                else:
                    message_text = message_text.replace(event_link, '').strip()
                    message_text = f"{message_text} {event_link}"

            self.logger.info(f"Generated message for user {user.get('_id')}: {message_text[:50]}...")
            self.stats['messages_generated'] += 1

            return {
                'message_text': message_text,
                'personalization_notes': message_data.get('personalization_notes', ''),
                'character_count': len(message_text)
            }

        except Exception as e:
            self.logger.error(f"Error generating message: {e}")
            # Fallback message with event link
            first_name = user.get('firstName', 'there')
            event_title = event.get('name', 'an upcoming event')
            event_id = str(event.get('_id', ''))
            event_link = f"https://cucu.li/bookings/{event_id}"
            fallback = f"Hi {first_name}! 👋 We miss you! Check out {event_title}. Welcome back! Tap to RSVP: {event_link}"
            return {
                'message_text': fallback,
                'personalization_notes': 'Error fallback',
                'character_count': len(fallback)
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
        report = {
            'campaign_id': self.campaign_id,
            'campaign_name': self.campaign_name,
            'run_date': datetime.now().isoformat(),
            'statistics': self.stats,
            'summary': {
                'total_dormant_users_found': self.stats['users_processed'],
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

    def _get_recommendations(self) -> List[str]:
        """Return the latest assessment & recommendations list for reactivation campaigns."""
        return [
            "Welcome-back messaging: Acknowledge time away ('We miss you!', 'Welcome back!') without being pushy; creates emotional connection.",
            "Interest alignment is critical: Prioritize events that directly match user interests for highest reactivation success.",
            "Social proof matters: Prefer well-attended events (50-100% filled) to show quality and community engagement.",
            "Location convenience: Explicitly mention neighborhood proximity for easy return to the app.",
            "Urgency for reactivation: Use time-sensitive language ('tonight', 'this week') to create immediate action.",
            "Event quality over quantity: Better to match with one perfect event than multiple mediocre ones.",
        ]

    def _write_markdown_report(self, users: List[Dict[str, Any]], events: List[Dict[str, Any]],
                               matches: List[Dict[str, Any]], messages: List[Dict[str, Any]]):
        """Write a concise markdown report to reports folder using shared generator."""
        try:
            reports_dir = os.path.join(self.script_dir, 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            report_file = os.path.join(reports_dir, f'return_to_table_report_{self.campaign_id}.md')

            goal = "Reactivate dormant users (31-90 days inactive) by matching them with perfect future events based on interests, location, and past attendance patterns."

            user_filtering_explanation = (
                "Users were filtered for being dormant (31-90 days inactive), having attended at least 1 event, "
                "having complete profiles (at least 4 of 8 required fields: firstName, lastName, email, phone, "
                "gender, interests, occupation, homeNeighborhood), and having at least 1 interest. "
                "Users are ranked by reactivation score (profile completeness + dormancy duration + event history)."
            )

            event_filtering_explanation = (
                "Events were filtered for being future public events. "
                "Events are sorted by participation percentage (descending - most attended first) "
                "to prioritize high-quality events for reactivation."
            )

            user_display_fields = {
                'reactivation_score': 'score',
                'days_inactive': 'days inactive',
                'eventCount': 'events'
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
                recommendations=self._get_recommendations(),
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
        self.logger.info(f"Starting Return To Table Campaign: {self.campaign_id}")
        self.logger.info("=" * 80)

        try:
            # Step 1: Get top 16 dormant users ranked by reactivation score
            self.logger.info("\n[Step 1] Fetching and ranking dormant users...")
            top_dormant_users = self.get_dormant_users(limit=16)  # Process all 16 available users

            if not top_dormant_users:
                self.logger.warning("No dormant users found. Exiting.")
                return

            # Summaries are already included in enriched users from mongodb_pull
            # Save processed users to data/processed
            self._save_processed_users(top_dormant_users)

            # Step 2: Get future events (preferring well-attended)
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
            
            for user in top_dormant_users:
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
                    'campaign': 'return-to-table',
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
            self.save_campaign_data_to_firebase(top_dormant_users, matched_events, all_matches, all_messages)
            
            # Save matches and messages to data/processed
            self._save_processed_matches(all_matches)
            self._save_processed_messages(all_messages)

            # Step 5: Generate and save report
            self.logger.info("\n[Step 5] Generating final report...")
            report = self.generate_report()
            # Write local markdown report (no longer saving to Firebase)
            self._write_markdown_report(top_dormant_users, matched_events, all_matches, all_messages)

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
        campaign = ReturnToTableCampaign(logger=logger)
        campaign.run()

    except KeyboardInterrupt:
        logger.info("\nCampaign interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

