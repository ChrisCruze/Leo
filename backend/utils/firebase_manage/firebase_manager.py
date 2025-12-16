"""
Firebase Manager - Shared Firebase operations for campaign scripts

Provides centralized Firebase operations with support for local testing mode.
"""

import os
import json
import logging
import ssl
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from bson import ObjectId

logger = logging.getLogger(__name__)


class FirebaseManager:
    """Centralized Firebase manager for campaign scripts with local testing support"""
    
    def __init__(self, firebase_url: str, base_path: str = 'Leo2',
                 save_local: bool = False, local_data_dir: str = None,
                 logger_instance: logging.Logger = None):
        """
        Initialize Firebase Manager

        Args:
            firebase_url: Firebase database URL
            base_path: Base path in Firebase (default: 'Leo2')
            save_local: If True, save to local files instead of Firebase
            local_data_dir: Directory for local files (campaign's data/output folder)
            logger_instance: Optional logger instance
        """
        self.firebase_url = firebase_url.rstrip('/')
        self.base_path = base_path
        self.save_local = save_local
        self.local_data_dir = local_data_dir
        self.logger = logger_instance or logger
        
        if self.save_local and not self.local_data_dir:
            raise ValueError("local_data_dir required when save_local=True")
        
        if self.save_local:
            os.makedirs(self.local_data_dir, exist_ok=True)
            self.logger.info(f"Firebase Manager initialized in LOCAL MODE: {self.local_data_dir}")
        else:
            self.logger.info(f"Firebase Manager initialized: {self.firebase_url}/{self.base_path}")
    
    def _firebase_request(self, path: str, method: str = 'GET', 
                         data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Internal method to handle all Firebase HTTP requests"""
        full_url = f"{self.firebase_url}/{self.base_path}/{path}.json"
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
    
    def _convert_objectid(self, obj: Any) -> Any:
        """Helper function to convert ObjectId to string for JSON serialization"""
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_objectid(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_objectid(item) for item in obj]
        else:
            return obj
    
    def _merge_campaign_field(self, existing_campaign: Any, new_campaign: str) -> List[str]:
        """Merge campaign field - convert string to array and append if needed"""
        if existing_campaign:
            if isinstance(existing_campaign, str):
                campaigns = [existing_campaign]
            elif isinstance(existing_campaign, list):
                campaigns = existing_campaign.copy()
            else:
                campaigns = [str(existing_campaign)]
            
            if new_campaign not in campaigns:
                campaigns.append(new_campaign)
            return campaigns
        else:
            return [new_campaign]
    
    def save_user(self, user: Dict[str, Any], campaign_name: str):
        """
        Save or update user node using user_id as identifier
        
        Args:
            user: User document with _id and required fields
            campaign_name: Campaign name to add to campaign array
        """
        user_id = str(user.get('_id', ''))
        if not user_id:
            self.logger.warning("User missing _id, skipping save")
            return
        
        # Get existing user data
        existing = None
        if not self.save_local:
            existing = self._firebase_request(f'users/{user_id}', 'GET')
        else:
            # Load from local file
            users_file = os.path.join(self.local_data_dir, 'users.json')
            if os.path.exists(users_file):
                with open(users_file, 'r', encoding='utf-8') as f:
                    users_data = json.load(f)
                    existing = users_data.get(user_id)
        
        # Prepare minimal user data (only required fields)
        first_name = user.get('firstName', '')
        last_name = user.get('lastName', '')
        user_data = {
            'id': user_id,
            '_id': user_id,
            'firstName': first_name,
            'lastName': last_name,
            'name': f"{first_name} {last_name}".strip(),
            'email': user.get('email'),
            'homeNeighborhood': user.get('homeNeighborhood'),
            'gender': user.get('gender'),
            'occupation': user.get('occupation'),
            'interests': user.get('interests', []),
            'journey_stage': user.get('journey_stage'),
            'value_segment': user.get('value_segment'),
            'event_count': user.get('eventCount', 0),
            'eventCount': user.get('eventCount', 0),  # Keep both for compatibility
            'summary': user.get('summary', ''),  # ALWAYS include
            'updatedAt': datetime.now(timezone.utc).isoformat()
        }
        
        # Handle campaign field merging
        existing_campaign = existing.get('campaign') if existing else None
        user_data['campaign'] = self._merge_campaign_field(existing_campaign, campaign_name)
        
        # Save to Firebase or local
        if self.save_local:
            self._save_user_local(user_id, user_data)
        else:
            self._firebase_request(f'users/{user_id}', 'PUT', user_data)
            self.logger.debug(f"Saved user to Firebase: {user_id}")
    
    def save_event(self, event: Dict[str, Any], campaign_name: str):
        """
        Save or update event node using event_id as identifier
        
        Args:
            event: Event document with _id and required fields
            campaign_name: Campaign name to add to campaign array
        """
        event_id = str(event.get('_id', ''))
        if not event_id:
            self.logger.warning("Event missing _id, skipping save")
            return
        
        # Get existing event data
        existing = None
        if not self.save_local:
            existing = self._firebase_request(f'events/{event_id}', 'GET')
        else:
            # Load from local file
            events_file = os.path.join(self.local_data_dir, 'events.json')
            if os.path.exists(events_file):
                with open(events_file, 'r', encoding='utf-8') as f:
                    events_data = json.load(f)
                    existing = events_data.get(event_id)
        
        # Prepare minimal event data (only required fields)
        event_data = {
            'id': event_id,
            '_id': event_id,
            'name': event.get('name'),
            'startDate': event.get('startDate'),
            'maxParticipants': event.get('maxParticipants', 0),
            'participantCount': event.get('participantCount', 0),
            'participationPercentage': event.get('participationPercentage', 0),
            'neighborhood': event.get('neighborhood'),
            'categories': event.get('categories', []),
            'features': event.get('features', []),
            'venueName': event.get('venueName') or (event.get('venue', {}).get('name') if isinstance(event.get('venue'), dict) else None),
            'type': event.get('type', ''),
            'summary': event.get('summary', ''),  # ALWAYS include
            'updatedAt': datetime.now(timezone.utc).isoformat()
        }
        
        # Handle campaign field merging
        existing_campaign = existing.get('campaign') if existing else None
        event_data['campaign'] = self._merge_campaign_field(existing_campaign, campaign_name)
        
        # Save to Firebase or local
        if self.save_local:
            self._save_event_local(event_id, event_data)
        else:
            self._firebase_request(f'events/{event_id}', 'PUT', event_data)
            self.logger.debug(f"Saved event to Firebase: {event_id}")
    
    def save_match(self, match: Dict[str, Any]):
        """
        Append match to matches array
        
        Args:
            match: Match document with required fields
        """
        # Ensure match has required fields
        match_data = {
            'user_name': match.get('user_name', ''),
            'event_name': match.get('event_name', ''),
            'user_id': match.get('user_id', ''),
            'event_id': match.get('event_id', ''),
            'confidence_percentage': match.get('confidence_percentage', 0),
            'reasoning': match.get('reasoning', ''),
            'matched_at': match.get('matched_at', datetime.now(timezone.utc).isoformat()),
            'campaign': match.get('campaign', ''),
            'updatedAt': datetime.now(timezone.utc).isoformat()
        }
        
        if self.save_local:
            self._append_to_local_array('matches', match_data)
        else:
            # Get existing matches
            existing_data = self._firebase_request('matches', 'GET') or {}
            existing_matches = existing_data.get('matches', []) if isinstance(existing_data, dict) else []
            
            # Append new match
            existing_matches.append(match_data)
            
            # Save back
            matches_upload = {
                'matches': existing_matches,
                'count': len(existing_matches),
                'updatedAt': datetime.now(timezone.utc).isoformat()
            }
            self._firebase_request('matches', 'PUT', matches_upload)
            self.logger.debug(f"Saved match to Firebase")
    
    def save_message(self, message: Dict[str, Any]):
        """
        Append message to messages array
        
        Args:
            message: Message document with required fields
        """
        # Ensure message has required fields
        message_data = {
            'message_text': message.get('message_text', ''),
            'user_name': message.get('user_name', ''),
            'user_id': message.get('user_id', ''),  # Include user_id
            'user_email': message.get('user_email', ''),
            'user_phone': message.get('user_phone', ''),
            'user_summary': message.get('user_summary', ''),  # Include user summary
            'event_name': message.get('event_name', ''),
            'event_id': message.get('event_id', ''),
            'event_summary': message.get('event_summary', ''),  # Include event summary
            'similarity_score': message.get('similarity_score') or message.get('confidence_percentage', 0),
            'confidence_percentage': message.get('confidence_percentage', 0),
            'reasoning': message.get('reasoning', ''),
            'status': message.get('status', 'pending'),
            'campaign': message.get('campaign', ''),
            'generated_at': message.get('generated_at', datetime.now(timezone.utc).isoformat()),
            'updatedAt': datetime.now(timezone.utc).isoformat()
        }
        
        if self.save_local:
            self._append_to_local_array('messages', message_data)
        else:
            # Get existing messages
            existing_data = self._firebase_request('messages', 'GET') or {}
            existing_messages = existing_data.get('messages', []) if isinstance(existing_data, dict) else []
            
            # Append new message
            existing_messages.append(message_data)
            
            # Save back
            messages_upload = {
                'messages': existing_messages,
                'count': len(existing_messages),
                'updatedAt': datetime.now(timezone.utc).isoformat()
            }
            self._firebase_request('messages', 'PUT', messages_upload)
            self.logger.debug(f"Saved message to Firebase")

    def get_message_user_ids(self) -> Set[str]:
        """
        Return the set of user_ids that already have generated messages.

        Supports both Firebase (HTTP) and local file modes. Returns an empty
        set if messages are missing or the payload is malformed.
        """
        try:
            if self.save_local:
                file_path = os.path.join(self.local_data_dir, 'messages.json')
                if not os.path.exists(file_path):
                    return set()
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = self._firebase_request('messages', 'GET') or {}

            # Messages can either be in { "messages": [...] } or a bare list
            raw_messages = []
            if isinstance(data, dict) and isinstance(data.get('messages'), list):
                raw_messages = data.get('messages', [])
            elif isinstance(data, list):
                raw_messages = data

            user_ids = {
                str(m.get('user_id') or m.get('userId') or '')
                for m in raw_messages
                if isinstance(m, dict) and (m.get('user_id') or m.get('userId'))
            }
            return {uid for uid in user_ids if uid}
        except Exception as e:
            self.logger.error(f"Error fetching messages from Firebase: {e}")
            return set()
    
    def _save_user_local(self, user_id: str, user_data: Dict[str, Any]):
        """Save user to local JSON file"""
        users_file = os.path.join(self.local_data_dir, 'users.json')
        
        # Load existing users
        users_data = {}
        if os.path.exists(users_file):
            with open(users_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
        
        # Update user
        users_data[user_id] = user_data
        
        # Save back
        with open(users_file, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, indent=2, default=str)
    
    def _save_event_local(self, event_id: str, event_data: Dict[str, Any]):
        """Save event to local JSON file"""
        events_file = os.path.join(self.local_data_dir, 'events.json')
        
        # Load existing events
        events_data = {}
        if os.path.exists(events_file):
            with open(events_file, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
        
        # Update event
        events_data[event_id] = event_data
        
        # Save back
        with open(events_file, 'w', encoding='utf-8') as f:
            json.dump(events_data, f, indent=2, default=str)
    
    def _append_to_local_array(self, entity_type: str, item: Dict[str, Any]):
        """Append item to local array file (matches Firebase structure)"""
        file_path = os.path.join(self.local_data_dir, f'{entity_type}.json')
        
        # Load existing data (match Firebase structure: {entity_type: [...], count: N, updatedAt: ...})
        key = entity_type  # 'matches' or 'messages'
        data = {key: [], 'count': 0, 'updatedAt': datetime.now(timezone.utc).isoformat()}
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                if isinstance(existing, dict) and key in existing:
                    data = existing
                elif isinstance(existing, list):
                    data = {key: existing, 'count': len(existing), 'updatedAt': datetime.now(timezone.utc).isoformat()}
        
        # Append item
        data[key].append(item)
        data['count'] = len(data[key])
        data['updatedAt'] = datetime.now(timezone.utc).isoformat()
        
        # Save back
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

