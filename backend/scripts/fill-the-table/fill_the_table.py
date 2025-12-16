#!/usr/bin/env python3
"""
Fill The Table Campaign Script

This script identifies users who have attended the most events and have complete profiles,
then matches them with events that have less than 50% participation to encourage attendance.
"""

import os
import sys
import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set
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
    log_file = os.path.join(log_dir, f"fill_the_table_{timestamp}.log")
    
    # Configure logging
    logger = logging.getLogger('FillTheTable')
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


class FillTheTableCampaign:
    """Main campaign class for Fill The Table initiative"""

    def __init__(self, logger: logging.Logger = None):
        """Initialize connections to MongoDB, Firebase, and Anthropic"""
        self.logger = logger or logging.getLogger('FillTheTable')
        self.campaign_id = f"fill-the-table-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.campaign_name = "fill-the-table"
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
            users_file = os.path.join(self.data_processed_dir, 'top_users.json')
            users_serializable = self._convert_objectid(users)
            with open(users_file, 'w', encoding='utf-8') as f:
                json.dump(users_serializable, f, indent=2, ensure_ascii=False, default=str)
            self.logger.info(f"✓ Saved {len(users)} processed users to {users_file}")
        except Exception as e:
            self.logger.error(f"Error saving processed users: {e}")

    def _save_processed_events(self, events: List[Dict[str, Any]]):
        """Save processed events to JSON file in data/processed folder"""
        try:
            events_file = os.path.join(self.data_processed_dir, 'underfilled_events.json')
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

    def _write_markdown_report(self, users: List[Dict[str, Any]], events: List[Dict[str, Any]],
                               matches: List[Dict[str, Any]], messages: List[Dict[str, Any]]):
        """Write a concise markdown report to reports folder using shared generator."""
        try:
            reports_dir = os.path.join(self.script_dir, 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            report_file = os.path.join(reports_dir, f'fill_the_table_report_{self.campaign_id}.md')

            goal = "Increase user engagement by moving users from passive sign-ups to active event attendance via personalized SMS that drive RSVPs."

            user_filtering_explanation = (
                "Users were filtered for having complete profiles (at least 4 of 8 required fields: "
                "firstName, lastName, email, phone, gender, interests, occupation, homeNeighborhood) "
                "and ranked by event attendance count (highest first). Top 50 users with most events attended were selected."
            )

            event_filtering_explanation = (
                "Events were filtered for being future public events with less than 50% participation. "
                "Events are sorted by participation percentage (ascending - most underfilled first)."
            )

            user_display_fields = {
                'event_count': 'events'
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

    def _get_recommendations(self) -> List[str]:
        """Return the latest assessment & recommendations list."""
        return [
            "Push scarcity harder (explicit spots left, time); combine with social proof (participants already in).",
            "Tailor hooks by user interests/occupation; include neighborhood convenience explicitly.",
            "CTA: always tie to link; keep <180 chars even with link; move link to end.",
            "Consider age/gender/role when relevant (e.g., tone, venue vibe).",
        ]


    @staticmethod
    def _exclude_users_with_messages(users: List[Dict[str, Any]], message_user_ids: Set[str]) -> List[Dict[str, Any]]:
        """
        Remove users who already have messages in Firebase.

        Args:
            users: Candidate users to filter.
            message_user_ids: Set of user_ids that already have messages.

        Returns:
            Filtered list of users without existing messages.
        """
        if not message_user_ids:
            return users

        message_ids = {str(uid) for uid in message_user_ids if uid}
        return [u for u in users if str(u.get('_id', '')) not in message_ids]

    def _get_existing_message_user_ids(self) -> Set[str]:
        """
        Fetch user_ids from Firebase messages to avoid duplicate generation.
        """
        try:
            message_user_ids = self.firebase_manager.get_message_user_ids()
            self.logger.info(f"Found {len(message_user_ids)} users with existing messages in Firebase")
            return message_user_ids
        except Exception as e:
            self.logger.error(f"Error fetching message user_ids: {e}")
            self.stats['errors'].append(f"Error fetching message user_ids: {str(e)}")
            return set()

    def get_top_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get users who have attended the most events and have complete profiles.
        Uses mongodb_pull helper to get fully enriched users.

        Args:
            limit: Maximum number of users to return

        Returns:
            List of enriched user documents with event attendance counts
        """
        self.logger.info("Fetching top users with complete profiles using mongodb_pull...")

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

            # Filter for users who qualify for fill-the-table campaign (profile complete)
            qualified_users = [
                user for user in all_enriched_users
                if user.get('campaign_qualifications', {}).get('qualifies_fill_the_table', False)
            ]
            
            self.logger.info(f"Found {len(qualified_users)} users qualified for fill-the-table campaign")

            initial_user_count = len(qualified_users)

            # Filter out users who already have messages in Firebase
            existing_message_user_ids = self._get_existing_message_user_ids()

            if existing_message_user_ids:
                qualified_users = self._exclude_users_with_messages(qualified_users, existing_message_user_ids)
                filtered_out = initial_user_count - len(qualified_users)
                self.logger.info(
                    f"Filtered out {filtered_out} users with existing messages; {len(qualified_users)} users remain"
                )
            else:
                self.logger.info("No existing messages found in Firebase; no users filtered")

            self.logger.info(f"Found {len(qualified_users)} users with complete profiles (before filtering: {initial_user_count})")

            # Sort by event count (descending) - use event_count from enriched data
            qualified_users.sort(key=lambda x: x.get('event_count', 0), reverse=True)

            # Get top users
            top_users = qualified_users[:limit]

            self.stats['users_processed'] = len(top_users)
            self.logger.info(f"Selected {len(top_users)} top users")

            return top_users

        except Exception as e:
            self.logger.error(f"Error fetching top users: {e}")
            self.stats['errors'].append(f"Error fetching users: {str(e)}")
            return []

    def get_underfilled_events(self) -> List[Dict[str, Any]]:
        """
        Get public events with less than 50% participation.
        Uses mongodb_pull helper to get fully enriched events.

        Returns:
            List of enriched event documents with participation percentage
        """
        self.logger.info("Fetching underfilled events using mongodb_pull...")

        try:
            # Get fully enriched events from mongodb_pull
            all_enriched_events = self.mongodb_pull.events_pull(generate_report=False)
            self.logger.info(f"Found {len(all_enriched_events)} total enriched events")

            # Filter for events that qualify for fill-the-table campaign (underfilled, future, public)
            underfilled_events = [
                event for event in all_enriched_events
                if event.get('campaign_qualifications', {}).get('qualifies_fill_the_table', False)
            ]

            # Sort by participation percentage (ascending - most underfilled first)
            underfilled_events.sort(key=lambda x: x.get('participationPercentage', 0))

            self.stats['events_processed'] = len(underfilled_events)
            self.logger.info(f"Found {len(underfilled_events)} underfilled events")

            return underfilled_events

        except Exception as e:
            self.logger.error(f"Error fetching underfilled events: {e}")
            self.stats['errors'].append(f"Error fetching events: {str(e)}")
            return []

    def create_matching_prompt(self, event: Dict[str, Any], users: List[Dict[str, Any]]) -> str:
        """
        Create a prompt for matching users to an event (simplified format)

        Args:
            event: Event document with summary
            users: List of user documents with summaries

        Returns:
            Prompt string for the AI
        """
        # Prepare simplified user data - just name and summary
        user_list = []
        for u in users:
            user_name = f"{u.get('firstName', '')} {u.get('lastName', '')}".strip()
            user_summary = u.get('summary', '')
            user_list.append(f"- {user_name}: {user_summary}")
        
        users_text = "\n".join(user_list)
        
        # Get event name and summary
        event_name = event.get('name', '')
        event_summary = event.get('summary', 'Event summary not available')
        
        # Get event capacity info for context
        max_participants = event.get('maxParticipants', 0)
        participants = len(event.get('participants', []))
        remaining = max(max_participants - participants, 0)
        fill_rate = (participants / max_participants * 100) if max_participants > 0 else 0

        # Simplified prompt
        prompt = f"""You are an expert event marketer focused on filling underbooked events.

PRIORITY: Match users to this event which has LOW participation ({fill_rate:.1f}% full, {remaining} spots remaining). Your goal is to maximize attendance for events that need more participants.

MATCHING CRITERIA (in order of importance):
1. Spots left and urgency (event starts soon)
2. Interest alignment between user interests and event categories/features
3. Location proximity (user neighborhood vs event neighborhood)
4. User engagement history (event attendance count + recency)
5. Professional background relevance

Return a JSON array of match objects. Each object must contain:
- 'user_name': The user's full name (exact match from list below)
- 'event_name': "{event_name}"
- 'reasoning': Brief explanation focusing on why this match helps fill the event AND why the user would be interested
- 'confidence_percentage': Number 0-100 (prioritize matches for low-fill events)
- 'match_purpose': "fill_low_participation"

Select the best 5-10 matches for this event. Higher confidence scores should go to better matches.

Event:
Name: {event_name}
Summary: {event_summary}
Fill Rate: {fill_rate:.1f}% ({participants}/{max_participants} participants, {remaining} spots remaining)

Users:
{users_text}

Return only the JSON array, no additional text."""

        # Store prompt template for reporting
        self.matching_prompt_template = prompt

        return prompt

    def save_prompt_to_firebase(self, prompt: str, event_id: str) -> str:
        """Save prompt to Firebase under leo/prompts"""
        try:
            prompt_id = f"prompt-{event_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            prompt_data = {
                'id': prompt_id,
                'campaign': self.campaign_name,
                'event_id': event_id,
                'prompt': prompt,
                'created_at': datetime.now().isoformat(),
                'campaign_run_id': self.campaign_id
            }

            self._firebase_request(f'prompts/{prompt_id}', 'PUT', prompt_data)
            self.logger.info(f"Saved prompt to Firebase: {prompt_id}")

            return prompt_id

        except Exception as e:
            self.logger.error(f"Error saving prompt to Firebase: {e}")
            self.stats['errors'].append(f"Error saving prompt: {str(e)}")
            return ""

    def get_matches_from_ai(self, prompt: str) -> List[Dict[str, Any]]:
        """
        Get user-event matches from Claude using the prompt (matching leo_automation.py)

        Args:
            prompt: The matching prompt

        Returns:
            List of match dictionaries
        """
        try:
            self.logger.info("Requesting matches from Claude...")

            # Use ai_generate utility instead of direct API call
            matches = ai_generate_meta_tag_parse(
                prompt=prompt,
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                temperature=0.9
            )

            # Ensure matches is a list
            if not isinstance(matches, list):
                if isinstance(matches, dict) and 'matches' in matches:
                    matches = matches['matches']
                else:
                    matches = [matches] if matches else []

            self.logger.info(f"Received {len(matches)} matches from Claude")
            return matches

        except Exception as e:
            self.logger.error(f"Failed to get matches: {e}")
            return []

    def generate_message_for_user(self, user: Dict[str, Any], event: Dict[str, Any], match_reasoning: str) -> Dict[str, Any]:
        """
        Generate a personalized message for a user about an event (matching leo_automation.py)

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
            
            # Prompt with conversion-focused best practices, scarcity + social proof, proximity, and CTA/link placement
            prompt = f"""You are an expert SMS copywriter specializing in high-conversion, personalized messages for a social dining app.

GOAL: Drive RSVPs and attendance (fill underbooked events). Motivate immediate action.

SMS BEST PRACTICES:
1) LENGTH: <180 chars total (including link). Be concise.
2) TONE: Friendly, concise, 0–2 relevant emojis.
3) STRUCTURE: [Greeting + Name] [Hook tied to interests/occupation/location] [Spots left + time urgency + social proof] [CTA + link at end].
4) SCARCITY: Make spots left/time explicit; small-group feel when true.
5) SOCIAL PROOF: Mention participants already in if available.
6) PROXIMITY: Call out neighborhood convenience explicitly.
7) CTA: Tie directly to link (“Tap to RSVP: {event_link}”); link must be last.
8) PERSONALIZATION: Adjust tone for age/gender/role; if engagement_status is dormant/churned or days_inactive > 30, add a warm welcome-back/reunion vibe and nod to time away. If active, keep momentum.
9) AVOID: ALL CAPS, multiple questions, generic hype, long sentences, excessive punctuation.

EXAMPLES (with links):
- "Hey Sarah! 🍜 Ramen night Thu 7:30p near Midtown, 4 spots left—cozy group, Japanese flavors you love. Tap to RSVP: https://cucu.li/bookings/12345"
- "Hi Mike! Comedy + dinner near West Village tomorrow, only 3 seats—friends already in. Tap to RSVP: https://cucu.li/bookings/12345"
- "Hi Priya! Mexican supper near SoMa, 2 spots left; walkable from you. Tap to RSVP: https://cucu.li/bookings/12345"

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
            fallback = f"Hi {first_name}! We think you'd enjoy {event_title}. Join us? {event_link}"
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
                'total_users_analyzed': self.stats['users_processed'],
                'total_events_analyzed': self.stats['events_processed'],
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

    def run(self):
        """Main execution flow"""
        self.logger.info("=" * 80)
        self.logger.info(f"Starting Fill The Table Campaign: {self.campaign_id}")
        self.logger.info("=" * 80)

        try:
            # Step 1: Get top users with complete profiles
            self.logger.info("\n[Step 1] Fetching top users...")
            all_top = self.get_top_users(limit=50)  # Process 50 users for 50 messages
            top_users = all_top[:50]

            if not top_users:
                self.logger.warning("No users found. Exiting.")
                return

            # Summaries are already included in enriched users from mongodb_pull
            # Save processed users to data/processed
            self._save_processed_users(top_users)

            # Step 2: Get underfilled events
            self.logger.info("\n[Step 2] Fetching underfilled events...")
            underfilled_events = self.get_underfilled_events()

            if not underfilled_events:
                self.logger.warning("No underfilled events found. Exiting.")
                return

            # Summaries are already included in enriched events from mongodb_pull
            
            # Save processed events to data/processed
            self._save_processed_events(underfilled_events)

            # Step 3: Match users to events
            self.logger.info("\n[Step 3] Matching users to events...")
            all_matches = []
            all_messages = []
            
            # Process each event separately with its own matching prompt
            events_to_process = underfilled_events

            for event in events_to_process:
                event_id = str(event.get('_id', ''))
                event_title = event.get('name', 'Unknown')

                self.logger.info(f"\nProcessing event: {event_title}")

                # Create matching prompt
                prompt = self.create_matching_prompt(event, top_users)

                # Save prompt to Firebase
                prompt_id = self.save_prompt_to_firebase(prompt, event_id)

                # Get matches from AI
                matches = self.get_matches_from_ai(prompt)

                # Process each match (matching leo_automation.py structure)
                for match in matches:
                    user_name = match.get('user_name', '')
                    event_name = match.get('event_name', '')
                    confidence_percentage = match.get('confidence_percentage', 0)
                    reasoning = match.get('reasoning', '')
                    
                    # Find user by name (matching leo_automation.py approach)
                    user = next(
                        (u for u in top_users if f"{u.get('firstName', '')} {u.get('lastName', '')}".strip() == user_name),
                        None
                    )
                    
                    # Also try matching by user_id if name match fails
                    if not user:
                        user_id = match.get('user_id', '')
                        user = next((u for u in top_users if str(u.get('_id', '')) == user_id), None)
                    
                    if not user:
                        self.logger.warning(f"Could not find user for match: {user_name}")
                        continue
                    
                    # Verify event matches
                    if event_name != event_title:
                        self.logger.warning(f"Event name mismatch: {event_name} != {event_title}")
                    
                    # Generate personalized message
                    message_data = self.generate_message_for_user(user, event, reasoning)
                    message_text = message_data.get('message_text', '')

                    # Store match (matching leo_automation.py format)
                    match_record = {
                        'user_name': user_name,
                        'event_name': event_name,
                        'user_id': str(user.get('_id', '')),
                        'event_id': event_id,
                        'confidence_percentage': confidence_percentage,
                        'reasoning': reasoning,
                        'match_purpose': match.get('match_purpose', 'fill_low_participation'),
                        'strategy': 'fill_low_participation',
                        'matched_at': datetime.now(timezone.utc).isoformat(),
                        'campaign': 'fill-the-table',
                        'updatedAt': datetime.now(timezone.utc).isoformat(),
                        'user': user,  # Include full user object
                        'event': event  # Include full event object
                    }
                    all_matches.append(match_record)
                    self.stats['matches_created'] += 1
                    
                    # Save match using FirebaseManager
                    self.firebase_manager.save_match(match_record)
                    self.logger.info(f"  ✓ Saved match to Firebase: {user_name} → {event_name}")

                    # Store message (matching leo_automation.py format with reasoning)
                    first_name = user.get('firstName', '')
                    last_name = user.get('lastName', '')
                    user_name_full = f"{first_name} {last_name}".strip()
                    message_record = {
                        'user_name': user_name_full,
                        'event_name': event_name,
                        'user_id': str(user.get('_id', '')),
                        'event_id': event_id,
                        'user_email': user.get('email', ''),
                        'user_phone': user.get('phone', ''),
                        'user_summary': user.get('summary', ''),  # Include user summary
                        'event_summary': event.get('summary', ''),  # Include event summary
                        'message_text': message_text,
                        'personalization_notes': message_data.get('personalization_notes', ''),
                        'character_count': message_data.get('character_count', len(message_text)),
                        'similarity_score': confidence_percentage,
                        'confidence_percentage': confidence_percentage,
                        'reasoning': reasoning,  # Include reasoning for dashboard
                        'status': 'pending',  # Matching leo_automation.py (dashboard will show as pending_review)
                        'generated_at': datetime.now(timezone.utc).isoformat(),
                        'campaign': 'fill-the-table',
                        'updatedAt': datetime.now(timezone.utc).isoformat()
                    }
                    all_messages.append(message_record)
                    
                    # Save message using FirebaseManager
                    self.firebase_manager.save_message(message_record)
                    self.logger.info(f"  ✓ Saved message to Firebase for {user_name_full}")

                    self.logger.info(f"  ✓ Matched {user_name_full} (confidence: {confidence_percentage}%)")

            # Step 4: Save campaign metadata to Firebase (matches and messages already saved incrementally)
            self.logger.info("\n[Step 4] Saving campaign metadata to Firebase...")
            self.save_campaign_data_to_firebase(top_users, underfilled_events, all_matches, all_messages)
            
            # Save matches and messages to data/processed
            self._save_processed_matches(all_matches)
            self._save_processed_messages(all_messages)

            # Step 5: Generate and save report
            self.logger.info("\n[Step 5] Generating final report...")
            report = self.generate_report()
            # Write local markdown report (no longer saving to Firebase)
            self._write_markdown_report(top_users, underfilled_events, all_matches, all_messages)

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
        campaign = FillTheTableCampaign(logger=logger)
        campaign.run()

    except KeyboardInterrupt:
        logger.info("\nCampaign interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
