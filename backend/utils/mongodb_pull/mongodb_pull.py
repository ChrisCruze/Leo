"""
MongoDB Pull and Enrichment Helper

This module provides comprehensive MongoDB connection, data retrieval, user enrichment,
event transformation, and summary generation functions. It consolidates functionality
from multiple campaign scripts into a single reusable helper.

All MongoDB credentials are hardcoded for local system use.

================================================================================
FIELD DOCUMENTATION: users_pull() and events_pull()
================================================================================

USERS_PULL() OUTPUT FIELDS
--------------------------

users_pull() returns a list of enriched user dictionaries. Each user dictionary contains:

RAW FIELDS (from MongoDB 'user' collection):
- All original MongoDB fields are preserved (id, email, firstName, lastName, role, 
  interests, occupation, homeNeighborhood, gender, phone, birthDay, tableTypePreference,
  createdAt, etc.)

DERIVED/TRANSFORMED FIELDS:

1. Engagement & Activity Fields:
   - event_count (int): Count of events where user is participant OR owner
     Logic: len(event_map.get(user_id, [])) where event_map indexes events by both
     participants and ownerId
   
   - order_count (int): Count of orders where userId matches user
     Logic: len(order_map.get(user_id, [])) where order_map indexes orders by userId
   
   - total_order_amount (float): Total amount spent across all orders
     Logic: Sum of order.price.total (if dict) or order.price (if numeric)
     Handles both formats: {"total": 10.5} or 10.5
   
   - total_spent (float): Alias for total_order_amount (backward compatibility)
   
   - last_active (str, ISO 8601): Most recent activity date
     Logic: max(max(event.startDate for event in user_events), 
                max(order.createdAt for order in user_orders))
     Uses most recent timestamp from either events or orders
   
   - days_inactive (int): Days since last activity (9999 if never active)
     Logic: (now - last_active).days if last_active exists, else 9999
   
   - engagement_status (str): One of "active", "dormant", "churned", "new"
     Logic: days_inactive <= 30 → "active"
            days_inactive <= 90 → "dormant"
            days_inactive == 9999 → "new"
            else → "churned"
   
   - is_active (bool): True if engagement_status == "active"

2. Journey & Segmentation Fields:
   - journey_stage (str): User journey stage
     Logic (if-elif chain, exact order matters):
       1. If user.role == "POTENTIAL" → "Signed Up Online"
       2. Else if event_count == 0 → "Downloaded App"
       3. Else if event_count >= 1 and total_spent == 0 → "Joined Table"
       4. Else if total_spent > 0 and event_count > 1 → "Returned"
       5. Else if total_spent > 0 → "Attended"
       6. Else → "Downloaded App" (fallback)
     Requires BOTH event participation AND order spending data
   
   - value_segment (str): Value classification
     Logic: total_spent >= 2000 → "VIP"
            total_spent >= 500 → "High Value"
            total_spent > 0 → "Regular"
            else → "Low Value"
   
   - social_role (str): Social participation level
     Logic: event_count >= 50 → "social_leader"
            event_count >= 20 → "active_participant"
            else → "observer"
   
   - churn_risk (str): Churn risk assessment
     Logic: days_inactive >= 180 → "high"
            days_inactive >= 90 → "medium"
            else → "low"
   
   - user_segment (str): User segmentation category
     Logic (priority-based):
       1. If event_count == 0 and order_count == 0 and createdAt.year < 2025 → "Dead"
       2. Else if createdAt.year == 2025 and not has_details → "Campaign"
       3. Else if days_inactive <= 30 and event_count > 0 → "Fresh"
       4. Else if days_inactive <= 90 and event_count > 0 → "Active"
       5. Else if days_inactive <= 180 and event_count > 0 → "Dormant"
       6. Else if event_count > 0 or order_count > 0 → "Inactive"
       7. Else → "New"
   
   - cohort (str): Registration cohort in YYYY-MM format
     Logic: createdAt[:7] if createdAt exists
   
   - days_since_registration (int): Days since account creation
     Logic: (now - parse_iso_date(createdAt)).days

3. Profile Completeness Fields:
   - profile_completeness (str): Completeness score string
     Logic: Count filled fields from [interests, tableTypePreference, homeNeighborhood, 
            gender, relationship_status]
            Format: "{filled}/5 ({percentage}%)"
   
   - personalization_ready (bool): True if at least 4 of 5 required fields filled
     Logic: filled >= 4

4. Scoring Fields:
   - newcomer_score (float, 0-100): Score for newcomer users
     Logic: Event history score (0-50): 0 events = 50pts, 1 event = 30pts, 
            2 events = 10pts, 3+ = 0pts
            Profile completeness score (0-30): (filled_count / 8) * 30
            Account recency score (0-20): within 90 days = 20pts, 
            within 180 days = 10pts, else = 0pts
   
   - reactivation_score (float, 0-100): Score for dormant users
     Logic: Profile completeness score (0-40): (filled_count / 8) * 40
            Dormancy duration score (0-30): 31-90 days inactive = 30-20pts
            Event history score (0-30): >=5 events = 30pts, >=3 = 20pts, >=1 = 10pts

5. Campaign Qualification Fields:
   - campaign_qualifications (Dict): Campaign qualification flags and reasons
     Contains:
       - qualifies_seat_newcomers (bool): True if event_count 0-2, profile complete,
         has interests, joined <=90 days
       - qualifies_fill_the_table (bool): True if profile complete
       - qualifies_return_to_table (bool): True if event_count >=1, profile complete,
         has interests, dormant (31-90 days inactive)
       - campaign_qualification_reasons (Dict[str, List[str]]): Reasons for each campaign

6. Social Connection Fields:
   - social_connections (List[Dict]): Users this user has attended events with
     Logic: Find all events user attended/owned, extract all other participants,
            count shared events per connection, track most recent shared event date
     Format: [{"user_id": str, "shared_event_count": int, "last_shared_event_date": str}]
   
   - event_history (List[Dict]): Past events user has attended/owned
     Logic: All past events (startDate < now) sorted by recency (most recent first)
   
   - interest_analysis (Dict): Analyzed interests from event history
     Logic: Extract categories, features, venues from event history
     Format: {"top_categories": List[str], "top_features": List[str], 
              "top_venues": List[str], "event_type_preference": str,
              "time_patterns": Dict}

7. Summary Field:
   - summary (str): Comprehensive summary for personalization and event matching
     Logic: Combines personalization details with narrative synthesis.
            Includes: name, age (from birthDay), gender, relationship status,
            occupation, neighborhood, event count, interests, cuisines, 
            table type preference, journey stage, engagement status, total spent,
            value segment, and registration year.
            Format: "User {name} is a {age}-year-old {gender} {occupation} from {neighborhood}.
            They joined in {year}. They are in the {journey_stage} stage ({engagement_status})
            with {event_count} events and ${total_spent} spent. Classified as {value_segment}.
            Relationship status: {relationship_status}. Interests: {interests}.
            Preferred cuisines: {cuisines}. Table preference: {table_type_preference}."


EVENTS_PULL() OUTPUT FIELDS
----------------------------

events_pull() returns a list of enriched event dictionaries. Each event dictionary contains:

RAW FIELDS (from MongoDB 'event' collection):
- All original MongoDB fields are preserved (id, name, startDate, endDate, type,
  eventStatus, maxParticipants, minParticipants, participants, ownerId, venueName,
  neighborhood, categories, features, description, createdAt, etc.)

DERIVED/TRANSFORMED FIELDS:

1. Participation Fields:
   - participantCount (int): Number of participants
     Logic: len(event.get('participants', []))
   
   - participationPercentage (float): Percentage of capacity filled
     Logic: (participantCount / maxParticipants) * 100 if maxParticipants > 0, else 0

2. Participant Demographics Fields:
   - participant_profiles_enriched (bool): True if participant analysis completed
   
   - participant_count (int): Number of participants with profile data available
     Logic: Count of participants found in user_lookup
   
   - participant_top_interests (List[Tuple[str, int]]): Top 5 interests from participants
     Logic: Count interests from all participant profiles, sort by count, take top 5
     Format: [("art", 5), ("music", 4), ("food", 3)]
   
   - participant_top_occupations (List[Tuple[str, int]]): Top 5 occupations from participants
     Logic: Count occupations from all participant profiles, sort by count, take top 5
   
   - participant_top_neighborhoods (List[Tuple[str, int]]): Top 5 neighborhoods from participants
     Logic: Count neighborhoods from all participant profiles, sort by count, take top 5

3. Campaign Qualification Fields:
   - campaign_qualifications (Dict): Campaign qualification flags and reasons
     Contains:
       - qualifies_seat_newcomers (bool): True if future event, public, maxParticipants >0,
         participationPercentage 50-80%
       - qualifies_fill_the_table (bool): True if future event, public, 
         participationPercentage <50%, maxParticipants >0
       - qualifies_return_to_table (bool): True if future event, public, 
         maxParticipants >0, participationPercentage >60%
       - campaign_qualification_reasons (Dict[str, List[str]]): Reasons for each campaign

4. Summary Fields:
   - summary (str): Generated event summary
     Logic: "Event: {name} at {venueName} in {neighborhood}. Categories: {categories}.
             Features: {features}. Capacity: {maxParticipants}, Participants: {count}
             ({percentage}% full). Date: {formatted_date}."
     HTML tags removed from description if included

================================================================================
"""

import logging
import os
import sys
import json
from pymongo import MongoClient
from pymongo.database import Database
from datetime import datetime, timezone
from urllib.parse import quote_plus
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from bson import ObjectId
import re


# ============================================================================
# MongoDB Connection Configuration (Hardcoded)
# ============================================================================

MONGO_USERNAME = "chriscruz"
MONGO_PASSWORD = "@LA69Gk9merja2N"
MONGO_HOST = "cuculi-production.grwghw0.mongodb.net"
MONGO_DATABASE = "cuculi_production"

# Connection string
MONGO_CONNECTION_STRING = f"mongodb+srv://{MONGO_USERNAME}:{quote_plus(MONGO_PASSWORD)}@{MONGO_HOST}/?retryWrites=true&w=majority"


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(log_dir: Optional[str] = None, logger_name: str = 'MongoDBPull') -> logging.Logger:
    """
    Set up comprehensive logging to both file and console.
    
    Args:
        log_dir: Directory for log files (default: 'logs' in module directory)
        logger_name: Name for the logger
        
    Returns:
        Configured logger instance
    """
    if log_dir is None:
        # Create logs directory in the helpers/mongodb_pull directory
        module_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(module_dir, 'logs')
    
    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Create timestamped log file
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_dir, f"mongodb_pull_{timestamp}.log")
    
    # Configure logging
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers = []
    
    # File handler (DEBUG level for detailed logs)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler (INFO level for user visibility)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger


# ============================================================================
# MongoDB Connection Class
# ============================================================================

class MongoDBConnection:
    """Handles MongoDB connection and basic data retrieval."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize MongoDB connection.
        
        Args:
            logger: Optional logger instance. If None, creates a default logger.
        """
        self.logger = logger or setup_logging()
        self._client: Optional[MongoClient] = None
        self._database: Optional[Database] = None
    
    def get_client(self) -> MongoClient:
        """
        Get MongoDB client with hardcoded credentials.
        
        Returns:
            MongoClient instance configured for cuculi_production database.
        """
        if self._client is None:
            self.logger.info("Establishing MongoDB connection...")
            self.logger.debug(f"Connecting to: {MONGO_HOST} (database: {MONGO_DATABASE})")
            self._client = MongoClient(
                MONGO_CONNECTION_STRING,
                connectTimeoutMS=30000,
                serverSelectionTimeoutMS=30000,
                tls=True,
                tlsAllowInvalidCertificates=True
            )
            self.logger.info("✓ MongoDB connection established successfully")
        return self._client
    
    def get_database(self) -> Database:
        """
        Get MongoDB database instance.
        
        Returns:
            Database instance for 'cuculi_production'.
        """
        if self._database is None:
            client = self.get_client()
            self._database = client[MONGO_DATABASE]
            self.logger.debug(f"Accessing database: {MONGO_DATABASE}")
        return self._database
    
    def get_users(self, filter: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query user collection from MongoDB.
        
        Args:
            filter: Optional MongoDB filter dictionary (e.g., {"role": "REGULAR"})
            limit: Optional limit on number of results
            
        Returns:
            List of user documents from 'user' collection.
        """
        self.logger.info(f"Fetching users from MongoDB (filter: {filter}, limit: {limit})...")
        db = self.get_database()
        query = db['user'].find(filter or {})
        if limit:
            query = query.limit(limit)
        users = list(query)
        self.logger.info(f"✓ Fetched {len(users)} users from 'user' collection")
        return users
    
    def get_events(self, filter: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query event collection from MongoDB.
        
        Args:
            filter: Optional MongoDB filter dictionary
            limit: Optional limit on number of results
            
        Returns:
            List of event documents from 'event' collection.
        """
        self.logger.info(f"Fetching events from MongoDB (filter: {filter}, limit: {limit})...")
        db = self.get_database()
        query = db['event'].find(filter or {})
        if limit:
            query = query.limit(limit)
        events = list(query)
        self.logger.info(f"✓ Fetched {len(events)} events from 'event' collection")
        return events
    
    def get_orders(self, filter: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query order collection from MongoDB.
        
        Args:
            filter: Optional MongoDB filter dictionary
            limit: Optional limit on number of results
            
        Returns:
            List of order documents from 'order' collection.
        """
        self.logger.info(f"Fetching orders from MongoDB (filter: {filter}, limit: {limit})...")
        db = self.get_database()
        query = db['order'].find(filter or {})
        if limit:
            query = query.limit(limit)
        orders = list(query)
        self.logger.info(f"✓ Fetched {len(orders)} orders from 'order' collection")
        return orders
    
    def close(self):
        """Close MongoDB connection."""
        if self._client:
            self.logger.debug("Closing MongoDB connection...")
            self._client.close()
            self._client = None
            self._database = None
            self.logger.info("✓ MongoDB connection closed")


# ============================================================================
# Utility Functions
# ============================================================================

def parse_iso_date(value: Any) -> Optional[datetime]:
    """
    Parse ISO 8601 date strings safely into datetime (UTC).
    
    Args:
        value: ISO 8601 string, datetime object, or None
        
    Returns:
        datetime object in UTC timezone, or None if invalid/missing.
    """
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None
    return None


def is_profile_complete(user: Dict[str, Any]) -> bool:
    """
    Check if user profile is complete (at least 4 of 5 required fields).
    
    Required fields: interests, tableTypePreference, homeNeighborhood, gender, relationship_status
    
    Args:
        user: User dictionary
        
    Returns:
        True if at least 4 of 5 required fields are filled.
    """
    required_fields = ['interests', 'tableTypePreference', 'homeNeighborhood', 'gender', 'relationship_status']
    
    filled = 0
    for field in required_fields:
        value = user.get(field)
        if value is not None:
            if field == 'interests':
                # For interests, check if it's a non-empty list with non-empty values
                if isinstance(value, list) and len(value) > 0:
                    # Check if list has at least one non-empty value
                    if any(item for item in value if item):
                        filled += 1
            elif isinstance(value, str):
                # For strings, check if non-empty after stripping whitespace
                if value.strip():
                    filled += 1
            else:
                # For other types (numbers, etc.), just check if truthy
                if value:
                    filled += 1
    
    return filled >= 4


def _convert_objectid(obj: Any) -> Any:
    """
    Convert ObjectId to string for JSON serialization.
    Handles nested dicts and lists recursively.
    
    Args:
        obj: Object to convert (may be ObjectId, dict, list, or other)
        
    Returns:
        Object with ObjectIds converted to strings.
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: _convert_objectid(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_objectid(item) for item in obj]
    else:
        return obj


# ============================================================================
# User Enrichment Class
# ============================================================================

class UserEnrichment:
    """Handles user enrichment, transformation, and segment analysis."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize UserEnrichment.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger('MongoDBPull.UserEnrichment')
    
    def index_data_by_user(self, events: List[Dict[str, Any]], orders: List[Dict[str, Any]]) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
        """
        Create O(1) lookup maps for events and orders indexed by user ID.
        
        Purpose: Combine events and orders for every user to enable calculations like derive_engagement.
        
        Args:
            events: List of event documents
            orders: List of order documents
            
        Returns:
            Tuple of (event_map, order_map):
            - event_map: Dict mapping user_id -> list of events (where user is participant OR owner)
            - order_map: Dict mapping user_id -> list of orders
        """
        self.logger.info("Indexing events and orders by user ID for efficient O(1) lookups...")
        self.logger.debug(f"Processing {len(events)} events and {len(orders)} orders")
        
        event_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        order_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Index events by participant and owner
        for event in events:
            participants = [str(p) for p in event.get('participants', [])]
            owner_id = str(event.get('ownerId', ''))
            
            # Add event to both owner and all participants
            for uid in set([owner_id] + participants):
                if uid and uid != 'None':
                    event_map[uid].append(event)
        
        # Index orders by userId
        for order in orders:
            uid = str(order.get('userId', ''))
            if uid and uid != 'None':
                order_map[uid].append(order)
        
        self.logger.info(f"✓ Created index maps: {len(event_map)} users with events, {len(order_map)} users with orders")
        return dict(event_map), dict(order_map)
    
    def calculate_stats(self, events: List[Dict[str, Any]], orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate statistics from user's events and orders.
        
        Args:
            events: List of event documents for the user
            orders: List of order documents for the user
            
        Returns:
            Dictionary with:
            - event_count: int
            - order_count: int
            - total_spent: float
            - last_active: Optional[datetime]
            - days_inactive: int
        """
        now = datetime.now(timezone.utc)
        
        # Calculate total spent from orders
        spent = 0.0
        for order in orders:
            price = order.get('price')
            if isinstance(price, dict):
                spent += price.get('total', 0)
            elif isinstance(price, (int, float)):
                spent += price
        
        # Get all timestamps
        dates = []
        for event in events:
            start_date = event.get('startDate')
            if start_date:
                dates.append(parse_iso_date(start_date))
        for order in orders:
            created_at = order.get('createdAt')
            if created_at:
                dates.append(parse_iso_date(created_at))
        
        # Find most recent activity
        valid_dates = [d for d in dates if d is not None]
        last_active = max(valid_dates) if valid_dates else None
        
        # Calculate days inactive
        days_inactive = 9999
        if last_active:
            try:
                days_inactive = (now - last_active).days
            except Exception:
                pass
        
        return {
            'event_count': len(events),
            'order_count': len(orders),
            'total_spent': round(spent, 2),
            'last_active': last_active,
            'days_inactive': days_inactive
        }
    
    def derive_segments(self, user: Dict[str, Any], stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Derive user segments based on business rules.
        
        Args:
            user: User document
            stats: Statistics dictionary from calculate_stats()
            
        Returns:
            Dictionary with segments:
            - journey_stage: str
            - engagement_status: str
            - value_segment: str
            - social_role: str
            - churn_risk: str
            - user_segment: str
            - cohort: str
            - days_since_registration: int
        """
        event_count = stats['event_count']
        total_spent = stats['total_spent']
        days_inactive = stats['days_inactive']
        
        # Journey Stage (exact logic from transform_data.py)
        if user.get('role') == 'POTENTIAL':
            journey_stage = "Signed Up Online"
        elif event_count == 0:
            journey_stage = "Downloaded App"
        elif event_count >= 1 and total_spent == 0:
            journey_stage = "Joined Table"
        elif total_spent > 0 and event_count > 1:
            journey_stage = "Returned"
        elif total_spent > 0:
            journey_stage = "Attended"
        else:
            journey_stage = "Downloaded App"  # Fallback
        
        # Engagement Status
        engagement_result = self.derive_engagement(stats.get('last_active'))
        engagement_status = engagement_result['engagement_status']
        
        # Value Segment
        if total_spent >= 2000:
            value_segment = "VIP"
        elif total_spent >= 500:
            value_segment = "High Value"
        elif total_spent > 0:
            value_segment = "Regular"
        else:
            value_segment = "Low Value"
        
        # Social Role
        if event_count >= 50:
            social_role = "social_leader"
        elif event_count >= 20:
            social_role = "active_participant"
        else:
            social_role = "observer"
        
        # Churn Risk
        if days_inactive >= 180:
            churn_risk = "high"
        elif days_inactive >= 90:
            churn_risk = "medium"
        else:
            churn_risk = "low"
        
        # User Segment (simplified version - full logic would check team IDs, etc.)
        created_at = user.get('createdAt')
        created_year = None
        if created_at:
            try:
                created_dt = parse_iso_date(created_at)
                if created_dt:
                    created_year = created_dt.year
            except Exception:
                pass
        
        has_details = bool(user.get('interests') or user.get('occupation') or user.get('homeNeighborhood'))
        
        if event_count == 0 and stats['order_count'] == 0 and created_year and created_year < 2025:
            user_segment = "Dead"
        elif created_year == 2025 and not has_details:
            user_segment = "Campaign"
        elif days_inactive <= 30 and event_count > 0:
            user_segment = "Fresh"
        elif days_inactive <= 90 and event_count > 0:
            user_segment = "Active"
        elif days_inactive <= 180 and event_count > 0:
            user_segment = "Dormant"
        elif event_count > 0 or stats['order_count'] > 0:
            user_segment = "Inactive"
        else:
            user_segment = "New"
        
        # Cohort
        cohort = None
        if created_at:
            try:
                cohort = created_at[:7]  # YYYY-MM format
            except Exception:
                pass
        
        # Days since registration
        days_since_registration = 0
        if created_at:
            try:
                created_dt = parse_iso_date(created_at)
                if created_dt:
                    days_since_registration = (datetime.now(timezone.utc) - created_dt).days
            except Exception:
                pass
        
        return {
            'journey_stage': journey_stage,
            'engagement_status': engagement_status,
            'value_segment': value_segment,
            'social_role': social_role,
            'churn_risk': churn_risk,
            'user_segment': user_segment,
            'cohort': cohort,
            'days_since_registration': days_since_registration
        }
    
    def derive_engagement(self, last_date: Optional[datetime]) -> Dict[str, Any]:
        """
        Derive engagement stats based on recency.
        
        Uses indexed data from Phase 5 (index_data_by_user).
        
        Args:
            last_date: Most recent activity date (from events or orders)
            
        Returns:
            Dictionary with:
            - days_inactive: int (9999 if never active)
            - engagement_status: str ("active", "dormant", "churned", "new")
            - is_active: bool
        """
        now = datetime.now(timezone.utc)
        days_inactive = 9999
        
        if last_date:
            try:
                days_inactive = (now - last_date).days
            except Exception:
                pass
        
        if days_inactive <= 30:
            engagement = "active"
        elif days_inactive <= 90:
            engagement = "dormant"
        else:
            engagement = "churned" if days_inactive != 9999 else "new"
        
        return {
            "days_inactive": days_inactive,
            "engagement_status": engagement,
            "is_active": engagement == "active"
        }
    
    def calculate_completeness(self, user: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Calculate profile completeness score.
        
        Args:
            user: User document
            
        Returns:
            Tuple of (completeness_score_string, is_ready_boolean)
        """
        required_fields = ['interests', 'tableTypePreference', 'homeNeighborhood', 'gender', 'relationship_status']
        
        filled = 0
        for field in required_fields:
            value = user.get(field)
            if value is not None:
                if field == 'interests':
                    # For interests, check if it's a non-empty list with non-empty values
                    if isinstance(value, list) and len(value) > 0:
                        # Check if list has at least one non-empty value
                        if any(item for item in value if item):
                            filled += 1
                elif isinstance(value, str):
                    # For strings, check if non-empty after stripping whitespace
                    if value.strip():
                        filled += 1
                else:
                    # For other types (numbers, etc.), just check if truthy
                    if value:
                        filled += 1
        
        total = len(required_fields)
        percentage = int((filled / total) * 100) if total > 0 else 0
        score_str = f"{filled}/{total} ({percentage}%)"
        is_ready = filled >= 4
        return score_str, is_ready
    
    def generate_narrative(self, user: Dict[str, Any], stats: Dict[str, Any], segs: Dict[str, Any], reg_date: Optional[str]) -> str:
        """
        Generate human-readable narrative biography for user.
        
        Args:
            user: User document
            stats: Statistics dictionary
            segs: Segments dictionary
            reg_date: Registration date string
            
        Returns:
            Narrative string
        """
        # Calculate age
        age_str = ""
        birth_day = user.get('birthDay')
        if birth_day:
            try:
                birth_dt = parse_iso_date(birth_day)
                if birth_dt:
                    age_years = (datetime.now(timezone.utc) - birth_dt).days // 365
                    age_str = f"{age_years}-year-old "
            except Exception:
                pass
        
        first_name = user.get('firstName', '')
        last_name = user.get('lastName', '')
        gender = user.get('gender', 'person')
        occupation = user.get('occupation', 'Professional')
        neighborhood = user.get('homeNeighborhood', 'New York')
        reg_year = str(reg_date)[:4] if reg_date else "unknown"
        
        return (
            f"User {first_name} {last_name} is a {age_str}{gender} "
            f"{occupation} from {neighborhood}. "
            f"They joined in {reg_year}. They are in the {segs['journey_stage']} stage ({segs['engagement_status']}) "
            f"with {stats['event_count']} events and ${stats['total_spent']} spent. Classified as {segs['value_segment']}."
        )
    
    def enrich_user_profile(self, user: Dict[str, Any], events: List[Dict[str, Any]], orders: List[Dict[str, Any]], campaign_qualifier: Optional['CampaignQualification'] = None) -> Dict[str, Any]:
        """
        Enrich a single user profile with calculated metrics, segments, and narrative.
        
        Args:
            user: User document from MongoDB
            events: List of events associated with the user (as participant or owner)
            orders: List of orders associated with the user
            campaign_qualifier: Optional CampaignQualification instance for adding campaign qualifications
            
        Returns:
            Enriched user dictionary with all calculated fields.
        """
        uid = str(user.get('_id', ''))
        
        # Calculate statistics
        stats = self.calculate_stats(events, orders)
        
        # Derive segments
        segs = self.derive_segments(user, stats)
        
        # Calculate completeness
        comp_score, is_ready = self.calculate_completeness(user)
        
        # Get engagement details
        engagement_result = self.derive_engagement(stats.get('last_active'))
        
        # Build enriched user
        enriched_user = {
            **user,  # Preserve all original fields
            "id": uid,
            "event_count": stats['event_count'],
            "order_count": stats['order_count'],
            "total_order_amount": stats['total_spent'],
            "total_spent": stats['total_spent'],  # Alias for compatibility
            "last_active": stats['last_active'].isoformat() if stats['last_active'] else None,
            "days_inactive": stats['days_inactive'],
            "journey_stage": segs['journey_stage'],
            "engagement_status": segs['engagement_status'],
            "is_active": engagement_result['is_active'],
            "value_segment": segs['value_segment'],
            "social_role": segs['social_role'],
            "churn_risk": segs['churn_risk'],
            "user_segment": segs['user_segment'],
            "cohort": segs['cohort'],
            "days_since_registration": segs['days_since_registration'],
            "profile_completeness": comp_score,
            "personalization_ready": is_ready
        }
        
        # Add campaign qualifications (integrated as part of enrichment)
        if campaign_qualifier:
            campaign_qualifier.add_campaign_qualifications_to_user(enriched_user, events)
        
        return enriched_user
    
    def transform_users(self, users: List[Dict[str, Any]], events: List[Dict[str, Any]], orders: List[Dict[str, Any]], campaign_qualifier: Optional['CampaignQualification'] = None) -> List[Dict[str, Any]]:
        """
        Transform all users by enriching each with their events and orders.
        
        Args:
            users: List of user documents
            events: List of all event documents
            orders: List of all order documents
            campaign_qualifier: Optional CampaignQualification instance for adding campaign qualifications
            
        Returns:
            List of enriched user dictionaries.
        """
        self.logger.info(f"Starting user transformation for {len(users)} users...")
        self.logger.debug(f"Using {len(events)} events and {len(orders)} orders for enrichment")
        self.logger.debug("Purpose: Calculate statistics, derive segments, add campaign qualifications for each user")
        
        # Create lookup maps
        event_map, order_map = self.index_data_by_user(events, orders)
        
        # Enrich each user
        enriched_users = []
        total = len(users)
        
        for idx, user in enumerate(users, 1):
            uid = str(user.get('_id', ''))
            user_events = event_map.get(uid, [])
            user_orders = order_map.get(uid, [])
            
            if idx % 100 == 0 or idx == total:
                self.logger.info(f"Processing user {idx}/{total} ({(idx/total)*100:.1f}%)...")
            
            enriched_user = self.enrich_user_profile(user, user_events, user_orders, campaign_qualifier)
            enriched_users.append(enriched_user)
        
        self.logger.info(f"✓ Completed transformation of {len(enriched_users)} users")
        
        # Log segment distributions
        self._log_segment_distributions(enriched_users)
        
        return enriched_users
    
    def _log_segment_distributions(self, users: List[Dict[str, Any]]):
        """
        Log distribution of users across different segments for insights.
        
        Args:
            users: List of enriched user dictionaries
        """
        self.logger.info("=" * 80)
        self.logger.info("USER SEGMENT DISTRIBUTIONS")
        self.logger.info("=" * 80)
        
        # Journey Stage Distribution
        journey_counts = defaultdict(int)
        for user in users:
            journey_counts[user.get('journey_stage', 'Unknown')] += 1
        
        self.logger.info("\nJourney Stage Distribution:")
        for stage, count in sorted(journey_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(users)) * 100
            self.logger.info(f"  {stage}: {count} ({percentage:.1f}%)")
        
        # Engagement Status Distribution
        engagement_counts = defaultdict(int)
        for user in users:
            engagement_counts[user.get('engagement_status', 'Unknown')] += 1
        
        self.logger.info("\nEngagement Status Distribution:")
        for status, count in sorted(engagement_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(users)) * 100
            self.logger.info(f"  {status}: {count} ({percentage:.1f}%)")
        
        # Value Segment Distribution
        value_counts = defaultdict(int)
        for user in users:
            value_counts[user.get('value_segment', 'Unknown')] += 1
        
        self.logger.info("\nValue Segment Distribution:")
        for segment, count in sorted(value_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(users)) * 100
            self.logger.info(f"  {segment}: {count} ({percentage:.1f}%)")
        
        # Social Role Distribution
        social_counts = defaultdict(int)
        for user in users:
            social_counts[user.get('social_role', 'Unknown')] += 1
        
        self.logger.info("\nSocial Role Distribution:")
        for role, count in sorted(social_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(users)) * 100
            self.logger.info(f"  {role}: {count} ({percentage:.1f}%)")
        
        # User Segment Distribution
        user_seg_counts = defaultdict(int)
        for user in users:
            user_seg_counts[user.get('user_segment', 'Unknown')] += 1
        
        self.logger.info("\nUser Segment Distribution:")
        for segment, count in sorted(user_seg_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(users)) * 100
            self.logger.info(f"  {segment}: {count} ({percentage:.1f}%)")
        
        # Profile Completeness Distribution
        completeness_counts = defaultdict(int)
        for user in users:
            completeness = user.get('profile_completeness', '0/8 (0%)')
            filled = int(completeness.split('/')[0]) if '/' in completeness else 0
            completeness_counts[f"{filled}/8"] += 1
        
        self.logger.info("\nProfile Completeness Distribution:")
        for comp, count in sorted(completeness_counts.items(), key=lambda x: int(x[0].split('/')[0]), reverse=True):
            percentage = (count / len(users)) * 100
            self.logger.info(f"  {comp}: {count} ({percentage:.1f}%)")
        
        # Personalization Ready Count
        ready_count = sum(1 for user in users if user.get('personalization_ready', False))
        self.logger.info(f"\nPersonalization Ready: {ready_count}/{len(users)} ({(ready_count/len(users))*100:.1f}%)")
        
        self.logger.info("=" * 80)


# ============================================================================
# Scoring Functions
# ============================================================================

def calculate_newcomer_score(user: Dict[str, Any]) -> float:
    """
    Calculate newcomer score for a user (0-100).
    
    Scoring breakdown:
    - Event history: 0-50 points (0 events = 50pts, 1 event = 30pts, 2 events = 10pts)
    - Profile completeness: 0-30 points (based on filled fields)
    - Account recency: 0-20 points (within 90 days = 20pts, decays linearly)
    
    Args:
        user: Enriched user dictionary
        
    Returns:
        Score from 0-100.
    """
    event_count = user.get('event_count', 0)
    days_since_registration = user.get('days_since_registration', 999)
    
    # Event history score (0-50 points)
    if event_count == 0:
        event_score = 50
    elif event_count == 1:
        event_score = 30
    elif event_count == 2:
        event_score = 10
    else:
        event_score = 0
    
    # Profile completeness score (0-30 points)
    profile_completeness = user.get('profile_completeness', '0/8 (0%)')
    filled_count = int(profile_completeness.split('/')[0]) if '/' in profile_completeness else 0
    completeness_score = min(30, (filled_count / 8) * 30)
    
    # Account recency score (0-20 points)
    if days_since_registration <= 90:
        recency_score = 20
    elif days_since_registration <= 180:
        recency_score = 10
    else:
        recency_score = 0
    
    return event_score + completeness_score + recency_score


def calculate_reactivation_score(user: Dict[str, Any]) -> float:
    """
    Calculate reactivation score for a user (0-100).
    
    Scoring breakdown:
    - Profile completeness: 0-40 points (based on filled fields)
    - Dormancy duration: 0-30 points (31-90 days inactive = higher score)
    - Event history: 0-30 points (more events = higher score)
    
    Args:
        user: Enriched user dictionary
        
    Returns:
        Score from 0-100.
    """
    days_inactive = user.get('days_inactive', 9999)
    event_count = user.get('event_count', 0)
    
    # Profile completeness score (0-40 points)
    profile_completeness = user.get('profile_completeness', '0/8 (0%)')
    filled_count = int(profile_completeness.split('/')[0]) if '/' in profile_completeness else 0
    completeness_score = min(40, (filled_count / 8) * 40)
    
    # Dormancy duration score (0-30 points)
    if 31 <= days_inactive <= 90:
        dormancy_score = 30 - ((days_inactive - 31) / 59 * 10)  # 30 to 20 points
    elif days_inactive < 31:
        dormancy_score = 15  # Less dormant, lower score
    else:
        dormancy_score = 5  # Too dormant, very low score
    
    # Event history score (0-30 points)
    if event_count >= 5:
        history_score = 30
    elif event_count >= 3:
        history_score = 20
    elif event_count >= 1:
        history_score = 10
    else:
        history_score = 0
    
    return completeness_score + dormancy_score + history_score


# ============================================================================
# Campaign Qualification Class
# ============================================================================

class CampaignQualification:
    """Handles campaign qualification checks for users and events."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize CampaignQualification.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger('MongoDBPull.CampaignQualification')
    
    def check_user_campaign_qualifications(self, user: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check if user qualifies for various campaigns.
        
        Args:
            user: Enriched user dictionary
            events: List of events associated with user (for context)
            
        Returns:
            Dictionary with qualification flags and reasons:
            - qualifies_seat_newcomers: bool
            - qualifies_fill_the_table: bool
            - qualifies_return_to_table: bool
            - campaign_qualification_reasons: Dict[str, List[str]]
        """
        event_count = user.get('event_count', 0)
        personalization_ready = user.get('personalization_ready', False)
        has_interests = bool(user.get('interests'))
        days_since_registration = user.get('days_since_registration', 999)
        engagement_status = user.get('engagement_status', '')
        days_inactive = user.get('days_inactive', 9999)
        
        reasons = {
            'seat_newcomers': [],
            'fill_the_table': [],
            'return_to_table': []
        }
        
        # Check seat-newcomers qualification
        qualifies_seat_newcomers = (
            event_count <= 2 and
            personalization_ready and
            has_interests and
            days_since_registration <= 90
        )
        if qualifies_seat_newcomers:
            reasons['seat_newcomers'].append(f"Event count: {event_count} (0-2)")
            reasons['seat_newcomers'].append("Profile complete")
            reasons['seat_newcomers'].append("Has interests")
            reasons['seat_newcomers'].append(f"Joined within 90 days ({days_since_registration} days ago)")
        else:
            if event_count > 2:
                reasons['seat_newcomers'].append(f"Event count too high: {event_count}")
            if not personalization_ready:
                reasons['seat_newcomers'].append("Profile incomplete")
            if not has_interests:
                reasons['seat_newcomers'].append("No interests")
            if days_since_registration > 90:
                reasons['seat_newcomers'].append(f"Joined too long ago ({days_since_registration} days)")
        
        # Check fill-the-table qualification
        qualifies_fill_the_table = personalization_ready
        if qualifies_fill_the_table:
            reasons['fill_the_table'].append("Profile complete")
        else:
            reasons['fill_the_table'].append("Profile incomplete")
        
        # Check return-to-table qualification
        qualifies_return_to_table = (
            event_count >= 1 and
            personalization_ready and
            has_interests and
            engagement_status == 'dormant' and
            31 <= days_inactive <= 90
        )
        if qualifies_return_to_table:
            reasons['return_to_table'].append(f"Event count: {event_count} (≥1)")
            reasons['return_to_table'].append("Profile complete")
            reasons['return_to_table'].append("Has interests")
            reasons['return_to_table'].append(f"Dormant ({days_inactive} days inactive)")
        else:
            if event_count < 1:
                reasons['return_to_table'].append(f"Event count too low: {event_count}")
            if not personalization_ready:
                reasons['return_to_table'].append("Profile incomplete")
            if not has_interests:
                reasons['return_to_table'].append("No interests")
            if engagement_status != 'dormant':
                reasons['return_to_table'].append(f"Not dormant (status: {engagement_status})")
            if not (31 <= days_inactive <= 90):
                reasons['return_to_table'].append(f"Days inactive out of range: {days_inactive}")
        
        return {
            'qualifies_seat_newcomers': qualifies_seat_newcomers,
            'qualifies_fill_the_table': qualifies_fill_the_table,
            'qualifies_return_to_table': qualifies_return_to_table,
            'campaign_qualification_reasons': reasons
        }
    
    def add_campaign_qualifications_to_user(self, user: Dict[str, Any], events: List[Dict[str, Any]]) -> None:
        """
        Add campaign qualification fields to user dictionary (modifies in place).
        
        Args:
            user: User dictionary (will be modified)
            events: List of events associated with user
        """
        qualifications = self.check_user_campaign_qualifications(user, events)
        user['campaign_qualifications'] = qualifications
        
        # Log qualification status
        if qualifications['qualifies_seat_newcomers'] or qualifications['qualifies_fill_the_table'] or qualifications['qualifies_return_to_table']:
            campaigns = []
            if qualifications['qualifies_seat_newcomers']:
                campaigns.append('seat-newcomers')
            if qualifications['qualifies_fill_the_table']:
                campaigns.append('fill-the-table')
            if qualifications['qualifies_return_to_table']:
                campaigns.append('return-to-table')
            self.logger.debug(f"User {user.get('id')} qualifies for: {', '.join(campaigns)}")
    
    def check_event_campaign_qualifications(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if event qualifies for various campaigns.
        
        Args:
            event: Event dictionary (should have participantCount and participationPercentage if enriched)
            
        Returns:
            Dictionary with qualification flags and reasons.
        """
        start_date = parse_iso_date(event.get('startDate'))
        event_type = event.get('type', '')
        max_participants = event.get('maxParticipants') or 0
        participant_count = event.get('participantCount', len(event.get('participants', [])))
        participation_percentage = event.get('participationPercentage', 0)
        
        # Calculate participation percentage if not already calculated
        if participation_percentage == 0 and max_participants > 0:
            participation_percentage = (participant_count / max_participants) * 100
        
        now = datetime.now(timezone.utc)
        is_future = start_date and start_date > now if start_date else False
        is_public = event_type == 'public'
        
        reasons = {
            'seat_newcomers': [],
            'fill_the_table': [],
            'return_to_table': []
        }
        
        # Check seat-newcomers qualification
        qualifies_seat_newcomers = (
            is_future and
            is_public and
            max_participants > 0 and
            50 <= participation_percentage <= 80
        )
        if qualifies_seat_newcomers:
            reasons['seat_newcomers'].append("Future event")
            reasons['seat_newcomers'].append("Public event")
            reasons['seat_newcomers'].append(f"Good participation ({participation_percentage:.1f}%)")
        else:
            if not is_future:
                reasons['seat_newcomers'].append("Not a future event")
            if not is_public:
                reasons['seat_newcomers'].append(f"Not public (type: {event_type})")
            if max_participants == 0:
                reasons['seat_newcomers'].append("No max participants")
            if not (50 <= participation_percentage <= 80):
                reasons['seat_newcomers'].append(f"Participation out of range ({participation_percentage:.1f}%)")
        
        # Check fill-the-table qualification
        qualifies_fill_the_table = (
            is_future and
            is_public and
            participation_percentage < 50 and
            max_participants > 0
        )
        if qualifies_fill_the_table:
            reasons['fill_the_table'].append("Future event")
            reasons['fill_the_table'].append("Public event")
            reasons['fill_the_table'].append(f"Underfilled ({participation_percentage:.1f}%)")
        else:
            if not is_future:
                reasons['fill_the_table'].append("Not a future event")
            if not is_public:
                reasons['fill_the_table'].append(f"Not public (type: {event_type})")
            if participation_percentage >= 50:
                reasons['fill_the_table'].append(f"Not underfilled ({participation_percentage:.1f}%)")
            if max_participants == 0:
                reasons['fill_the_table'].append("No max participants")
        
        # Check return-to-table qualification
        qualifies_return_to_table = (
            is_future and
            is_public and
            max_participants > 0 and
            participation_percentage > 60  # Prefers higher participation
        )
        if qualifies_return_to_table:
            reasons['return_to_table'].append("Future event")
            reasons['return_to_table'].append("Public event")
            reasons['return_to_table'].append(f"Good participation ({participation_percentage:.1f}%)")
        else:
            if not is_future:
                reasons['return_to_table'].append("Not a future event")
            if not is_public:
                reasons['return_to_table'].append(f"Not public (type: {event_type})")
            if max_participants == 0:
                reasons['return_to_table'].append("No max participants")
            if participation_percentage <= 60:
                reasons['return_to_table'].append(f"Participation too low ({participation_percentage:.1f}%)")
        
        return {
            'qualifies_seat_newcomers': qualifies_seat_newcomers,
            'qualifies_fill_the_table': qualifies_fill_the_table,
            'qualifies_return_to_table': qualifies_return_to_table,
            'campaign_qualification_reasons': reasons
        }
    
    def add_campaign_qualifications_to_event(self, event: Dict[str, Any]) -> None:
        """
        Add campaign qualification fields to event dictionary (modifies in place).
        
        Args:
            event: Event dictionary (will be modified)
        """
        qualifications = self.check_event_campaign_qualifications(event)
        event['campaign_qualifications'] = qualifications


# ============================================================================
# Summary Generation Class
# ============================================================================

class SummaryGeneration:
    """Handles generation of user and event summaries."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize SummaryGeneration.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger('MongoDBPull.SummaryGeneration')
    
    def generate_user_summary(self, user: Dict[str, Any]) -> str:
        """
        Generate comprehensive user summary for personalization and event matching.
        
        Includes: name, age, gender, relationship status, occupation, neighborhood,
        event count, interests, cuisines, table preferences, journey stage, engagement status,
        total spent, value segment, and registration year (narrative synthesis).
        
        Args:
            user: User dictionary (enriched or raw)
            
        Returns:
            Summary string incorporating both personalization details and narrative synthesis
        """
        try:
            first_name = user.get('firstName', '')
            last_name = user.get('lastName', '')
            name = f"{first_name} {last_name}".strip() or 'Unknown'
            interests = user.get('interests', [])
            occupation = user.get('occupation', 'Professional')
            neighborhood = user.get('homeNeighborhood', 'Unknown')
            gender = user.get('gender', '')
            relationship_status = user.get('relationshipStatus', '')
            cuisines = user.get('cuisines', [])
            table_type_preference = user.get('tableTypePreference', '')
            event_count = user.get('eventCount') or user.get('event_count', 0)
            
            # Get enriched fields for narrative synthesis
            journey_stage = user.get('journey_stage', '')
            engagement_status = user.get('engagement_status', '')
            total_spent = user.get('total_spent', 0)
            value_segment = user.get('value_segment', '')
            createdAt = user.get('createdAt', '')
            reg_year = str(createdAt)[:4] if createdAt else "unknown"
            
            # Calculate age from birthDay
            age = None
            age_str = ""
            birth_day = user.get('birthDay')
            if birth_day:
                try:
                    birth_dt = parse_iso_date(birth_day)
                    if birth_dt:
                        today = datetime.now(timezone.utc)
                        age = today.year - birth_dt.year - ((today.month, today.day) < (birth_dt.month, birth_dt.day))
                        age_str = f"{age}-year-old "
                except Exception:
                    pass
            
            interests_str = ', '.join(interests) if isinstance(interests, list) else str(interests)
            cuisines_str = ', '.join(cuisines) if isinstance(cuisines, list) else str(cuisines) if cuisines else ''
            
            # Build comprehensive summary with personalization details
            parts = []
            
            # Start with narrative synthesis format
            gender_display = gender if gender else 'person'
            occupation_display = occupation if occupation != 'Professional' else 'Professional'
            neighborhood_display = neighborhood if neighborhood != 'Unknown' else 'New York'
            
            parts.append(f"User {name} is a {age_str}{gender_display} {occupation_display} from {neighborhood_display}.")
            
            # Add registration and journey information
            if reg_year != "unknown":
                parts.append(f"They joined in {reg_year}.")
            
            if journey_stage and engagement_status:
                parts.append(f"They are in the {journey_stage} stage ({engagement_status})")
                if event_count > 0 or total_spent > 0:
                    parts.append(f"with {event_count} events and ${total_spent:.2f} spent.")
                else:
                    parts.append(".")
            
            if value_segment:
                parts.append(f"Classified as {value_segment}.")
            
            # Add personalization details
            if relationship_status:
                parts.append(f"Relationship status: {relationship_status}.")
            
            if interests_str:
                parts.append(f"Interests: {interests_str}.")
            
            if cuisines_str:
                parts.append(f"Preferred cuisines: {cuisines_str}.")
            
            if table_type_preference:
                parts.append(f"Table preference: {table_type_preference}.")
            
            summary = " ".join(parts)
            return summary.strip()
            
        except Exception as e:
            self.logger.error(f"Error generating user summary: {e}")
            first_name = user.get('firstName', '')
            last_name = user.get('lastName', '')
            name = f"{first_name} {last_name}".strip() or 'Unknown'
            return f"User: {name}"
    
    def format_event_start_date(self, start_date: Any) -> str:
        """
        Parse and format an event start date into a human-readable string.
        
        Parses ISO 8601 date strings and formats them as:
        "Monday, Dec 15, 2025 at 7:30 PM"
        
        Args:
            start_date: ISO 8601 date string (e.g., "2019-08-05T17:00:00.000Z"),
                       datetime object, or None/empty value
                       
        Returns:
            Formatted date string (e.g., "Monday, Aug 5, 2019 at 5 PM"),
            or 'TBD' if the date is invalid/missing, or the original string
            if parsing fails but a value was provided.
            
        Examples:
            Input: "2019-08-05T17:00:00.000Z"
            Output: "Monday, Aug 5, 2019 at 5 PM"
            
            Input: "2025-12-15T19:30:00.000Z"
            Output: "Monday, Dec 15, 2025 at 7:30 PM"
            
            Input: None or ""
            Output: "TBD"
            
            Input: "invalid-date"
            Output: "invalid-date"
        """
        if not start_date:
            return 'TBD'
        
        try:
            event_dt = parse_iso_date(start_date)
            if event_dt:
                # Convert UTC to local time if timezone-aware
                if event_dt.tzinfo is not None:
                    event_dt = event_dt.astimezone()  # Convert to local timezone
                
                # Format: "Monday, Dec 15, 2025 at 7:30 PM"
                day_of_week = event_dt.strftime('%A')
                month_abbr = event_dt.strftime('%b')
                day = event_dt.strftime('%d').lstrip('0')
                year = event_dt.strftime('%Y')
                
                # Format time in 12-hour format with AM/PM (using local time)
                hour = event_dt.hour
                minute = event_dt.minute
                if minute == 0:
                    if hour == 0:
                        time_str = "12 AM"
                    elif hour < 12:
                        time_str = f"{hour} AM"
                    elif hour == 12:
                        time_str = "12 PM"
                    else:
                        time_str = f"{hour - 12} PM"
                else:
                    if hour == 0:
                        time_str = f"12:{minute:02d} AM"
                    elif hour < 12:
                        time_str = f"{hour}:{minute:02d} AM"
                    elif hour == 12:
                        time_str = f"12:{minute:02d} PM"
                    else:
                        time_str = f"{hour - 12}:{minute:02d} PM"
                
                return f"{day_of_week}, {month_abbr} {day}, {year} at {time_str}"
            else:
                # If parsing returns None but we have a value, return it as string
                return str(start_date)
        except Exception:
            # If parsing fails with exception but we have a value, return it as string
            return str(start_date)
    
    def generate_event_summary(self, event: Dict[str, Any]) -> str:
        """
        Generate event summary, removing HTML tags from description.
        
        Args:
            event: Event dictionary
            
        Returns:
            Summary string
        """
        try:
            event_name = event.get('name', 'Unknown Event')
            description = event.get('description', '')
            start_date = event.get('startDate', '')
            venue = event.get('venue', {})
            venue_name = venue.get('name', 'N/A') if isinstance(venue, dict) else event.get('venueName', 'N/A')
            neighborhood = event.get('neighborhood', 'N/A')
            categories = event.get('categories', [])
            features = event.get('features', [])
            participation_pct = event.get('participationPercentage', 0)
            max_participants = event.get('maxParticipants') or 0
            participant_count = event.get('participantCount', len(event.get('participants', [])))
            
            # Calculate participation percentage if not set
            if participation_pct == 0 and max_participants > 0:
                participation_pct = (participant_count / max_participants) * 100
            
            # Format date with day of week and better time format
            date_str = self.format_event_start_date(start_date)
            
            categories_str = ", ".join([str(c) for c in categories[:3]]) if categories else "None"
            features_str = ", ".join([str(f) for f in features[:3]]) if features else "None"
            
            # Remove HTML tags from description
            if description:
                clean_description = re.sub(r'<[^>]+>', '', description)
                clean_description = ' '.join(clean_description.split())
            else:
                clean_description = ''
            
            summary = (
                f"Event: {event_name} at {venue_name} in {neighborhood}. "
                f"Categories: {categories_str}. Features: {features_str}. "
                f"Capacity: {max_participants}, Participants: {participant_count} ({participation_pct:.1f}% full). "
                f"Date: {date_str}."
            )
            
            if clean_description:
                summary += f" {clean_description}"
            
            return summary.strip()
            
        except Exception as e:
            self.logger.error(f"Error generating event summary: {e}")
            return f"Event: {event.get('name', 'Unknown Event')}"


# ============================================================================
# Event Transformation Class
# ============================================================================

class EventTransformation:
    """Handles event enrichment with participant analysis."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize EventTransformation.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger('MongoDBPull.EventTransformation')
    
    def enrich_event_with_participants(self, event: Dict[str, Any], user_lookup: Dict[str, Dict[str, Any]]) -> None:
        """
        Enrich event with participant analysis (modifies event in place).
        
        Args:
            event: Event dictionary (will be modified)
            user_lookup: Dictionary mapping user_id -> user document
        """
        participants = event.get('participants', []) or []
        participant_profiles = []
        interest_counter = defaultdict(int)
        occupation_counter = defaultdict(int)
        neighborhood_counter = defaultdict(int)
        
        for pid in participants:
            user = user_lookup.get(str(pid))
            if not user:
                continue
            participant_profiles.append(user)
            
            # Count interests
            for interest in user.get('interests', []):
                interest_counter[str(interest).lower()] += 1
            
            # Count occupations
            occ = user.get('occupation')
            if occ:
                occupation_counter[str(occ).lower()] += 1
            
            # Count neighborhoods
            hood = user.get('homeNeighborhood')
            if hood:
                neighborhood_counter[str(hood).lower()] += 1
        
        # Calculate participant count and participation percentage
        # Use len(participants) to count ALL participants, not just those found in user_lookup
        participant_count = len(participants)
        max_participants = event.get('maxParticipants') or 0
        participation_percentage = (participant_count / max_participants * 100) if max_participants > 0 else 0
        
        # Top signals
        top_interests = sorted(interest_counter.items(), key=lambda x: x[1], reverse=True)[:5]
        top_occupations = sorted(occupation_counter.items(), key=lambda x: x[1], reverse=True)[:5]
        top_neighborhoods = sorted(neighborhood_counter.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Add fields to event
        event['participant_profiles_enriched'] = True
        event['participant_count'] = participant_count
        event['participantCount'] = participant_count
        event['participationPercentage'] = participation_percentage
        event['participant_top_interests'] = top_interests
        event['participant_top_occupations'] = top_occupations
        event['participant_top_neighborhoods'] = top_neighborhoods
        
        self.logger.debug(f"Enriched event '{event.get('name', 'Unknown')}' with {participant_count} participant profiles")
    
    def transform_events(self, events: List[Dict[str, Any]], user_lookup: Dict[str, Dict[str, Any]], campaign_qualifier: 'CampaignQualification', summary_gen: 'SummaryGeneration') -> List[Dict[str, Any]]:
        """
        Transform all events by enriching with participant data.
        
        Args:
            events: List of event documents
            user_lookup: Dictionary mapping user_id -> user document
            campaign_qualifier: CampaignQualification instance
            summary_gen: SummaryGeneration instance
            
        Returns:
            List of enriched event dictionaries
        """
        self.logger.info(f"Starting event transformation for {len(events)} events...")
        self.logger.debug(f"Using user lookup with {len(user_lookup)} users")
        
        enriched_events = []
        total = len(events)
        
        for idx, event in enumerate(events, 1):
            if idx % 100 == 0 or idx == total:
                self.logger.info(f"Processing event {idx}/{total} ({(idx/total)*100:.1f}%)...")
            
            self.enrich_event_with_participants(event, user_lookup)
            campaign_qualifier.add_campaign_qualifications_to_event(event)
            event['summary'] = summary_gen.generate_event_summary(event)
            enriched_events.append(event)
        
        self.logger.info(f"✓ Completed transformation of {len(enriched_events)} events")
        
        # Log event distributions
        self._log_event_distributions(enriched_events)
        
        return enriched_events
    
    def _log_event_distributions(self, events: List[Dict[str, Any]]):
        """
        Log distribution of events across different characteristics for insights.
        
        Args:
            events: List of enriched event dictionaries
        """
        self.logger.info("=" * 80)
        self.logger.info("EVENT DISTRIBUTIONS")
        self.logger.info("=" * 80)
        
        # Event Type Distribution
        type_counts = defaultdict(int)
        for event in events:
            type_counts[event.get('type', 'Unknown')] += 1
        
        self.logger.info("\nEvent Type Distribution:")
        for event_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(events)) * 100
            self.logger.info(f"  {event_type}: {count} ({percentage:.1f}%)")
        
        # Participation Percentage Distribution
        participation_ranges = {
            '0-25%': 0,
            '25-50%': 0,
            '50-75%': 0,
            '75-100%': 0,
            '100%+': 0
        }
        for event in events:
            pct = event.get('participationPercentage', 0)
            if pct < 25:
                participation_ranges['0-25%'] += 1
            elif pct < 50:
                participation_ranges['25-50%'] += 1
            elif pct < 75:
                participation_ranges['50-75%'] += 1
            elif pct <= 100:
                participation_ranges['75-100%'] += 1
            else:
                participation_ranges['100%+'] += 1
        
        self.logger.info("\nParticipation Percentage Distribution:")
        for range_name, count in participation_ranges.items():
            percentage = (count / len(events)) * 100
            self.logger.info(f"  {range_name}: {count} ({percentage:.1f}%)")
        
        # Campaign Qualification Distribution
        campaign_counts = {
            'seat_newcomers': 0,
            'fill_the_table': 0,
            'return_to_table': 0
        }
        for event in events:
            quals = event.get('campaign_qualifications', {})
            if quals.get('qualifies_seat_newcomers'):
                campaign_counts['seat_newcomers'] += 1
            if quals.get('qualifies_fill_the_table'):
                campaign_counts['fill_the_table'] += 1
            if quals.get('qualifies_return_to_table'):
                campaign_counts['return_to_table'] += 1
        
        self.logger.info("\nCampaign Qualification Distribution:")
        for campaign, count in campaign_counts.items():
            percentage = (count / len(events)) * 100
            self.logger.info(f"  {campaign}: {count} ({percentage:.1f}%)")
        
        self.logger.info("=" * 80)


# ============================================================================
# Social Connection Class
# ============================================================================

class SocialConnection:
    """Handles social connection analysis for users."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize SocialConnection.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger('MongoDBPull.SocialConnection')
    
    def get_user_social_connections(self, user_id: str, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Get users this user has attended events with.
        
        Args:
            user_id: User ID string
            events: List of all event documents
            
        Returns:
            List of connection dictionaries with user_id, shared_event_count, last_shared_event_date
        """
        self.logger.debug(f"Finding social connections for user {user_id}...")
        
        user_events = []
        for event in events:
            participants = [str(p) for p in event.get('participants', [])]
            owner_id = str(event.get('ownerId', ''))
            if user_id in participants or user_id == owner_id:
                user_events.append(event)
        
        # Find all other participants
        connection_map = defaultdict(lambda: {'count': 0, 'last_date': None})
        for event in user_events:
            participants = [str(p) for p in event.get('participants', [])]
            owner_id = str(event.get('ownerId', ''))
            all_participants = set(participants + [owner_id])
            all_participants.discard(user_id)
            all_participants.discard('None')
            
            event_date = parse_iso_date(event.get('startDate'))
            for other_user_id in all_participants:
                connection_map[other_user_id]['count'] += 1
                if event_date and (connection_map[other_user_id]['last_date'] is None or event_date > connection_map[other_user_id]['last_date']):
                    connection_map[other_user_id]['last_date'] = event_date
        
        # Convert to list format
        connections = []
        for other_user_id, data in connection_map.items():
            connections.append({
                'user_id': other_user_id,
                'shared_event_count': data['count'],
                'last_shared_event_date': data['last_date'].isoformat() if data['last_date'] else None
            })
        
        # Sort by shared event count (descending)
        connections.sort(key=lambda x: x['shared_event_count'], reverse=True)
        
        self.logger.debug(f"Found {len(connections)} social connections for user {user_id}")
        return connections
    
    def get_user_event_history(self, user_id: str, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Get past events user has attended/owned, sorted by recency.
        
        Args:
            user_id: User ID string
            events: List of all event documents
            
        Returns:
            List of event documents sorted by recency (most recent first)
        """
        self.logger.debug(f"Retrieving event history for user {user_id}...")
        
        user_events = []
        now = datetime.now(timezone.utc)
        
        for event in events:
            participants = [str(p) for p in event.get('participants', [])]
            owner_id = str(event.get('ownerId', ''))
            if user_id in participants or user_id == owner_id:
                event_date = parse_iso_date(event.get('startDate'))
                if event_date and event_date < now:  # Only past events
                    user_events.append(event)
        
        # Sort by startDate (most recent first)
        user_events.sort(key=lambda e: parse_iso_date(e.get('startDate')) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        
        self.logger.debug(f"Found {len(user_events)} past events for user {user_id}")
        return user_events
    
    def analyze_user_interests_from_events(self, user_id: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze user interests from their event history.
        
        Args:
            user_id: User ID string
            events: List of all event documents
            
        Returns:
            Dictionary with top_categories, top_features, top_venues, event_type_preference, time_patterns
        """
        self.logger.debug(f"Analyzing interests from event history for user {user_id}...")
        
        user_events = self.get_user_event_history(user_id, events)
        
        category_counter = defaultdict(int)
        feature_counter = defaultdict(int)
        venue_counter = defaultdict(int)
        type_counter = defaultdict(int)
        day_counter = defaultdict(int)
        hour_counter = defaultdict(int)
        
        for event in user_events:
            # Categories
            categories = event.get('categories') or []
            for cat in categories:
                if cat:
                    category_counter[str(cat).lower()] += 1
            
            # Features
            features = event.get('features') or []
            for feat in features:
                if feat:
                    feature_counter[str(feat).lower()] += 1
            
            # Venues
            venue_name = event.get('venueName') or (event.get('venue', {}).get('name') if isinstance(event.get('venue'), dict) else None)
            if venue_name:
                venue_counter[str(venue_name)] += 1
            
            # Type
            event_type = event.get('type', '')
            if event_type:
                type_counter[event_type] += 1
            
            # Time patterns
            start_date = parse_iso_date(event.get('startDate'))
            if start_date:
                day_counter[start_date.strftime('%A')] += 1
                hour_counter[start_date.hour] += 1
        
        # Get top items
        top_categories = [cat for cat, _ in sorted(category_counter.items(), key=lambda x: x[1], reverse=True)[:10]]
        top_features = [feat for feat, _ in sorted(feature_counter.items(), key=lambda x: x[1], reverse=True)[:10]]
        top_venues = [venue for venue, _ in sorted(venue_counter.items(), key=lambda x: x[1], reverse=True)[:10]]
        
        # Event type preference
        event_type_preference = max(type_counter.items(), key=lambda x: x[1])[0] if type_counter else 'public'
        
        # Time patterns
        preferred_days = [day for day, _ in sorted(day_counter.items(), key=lambda x: x[1], reverse=True)[:3]]
        preferred_hours = sorted(hour_counter.items(), key=lambda x: x[1], reverse=True)[:3]
        preferred_times = []
        for hour, _ in preferred_hours:
            if hour < 12:
                preferred_times.append('morning')
            elif hour < 17:
                preferred_times.append('afternoon')
            elif hour < 21:
                preferred_times.append('evening')
            else:
                preferred_times.append('night')
        
        return {
            'top_categories': top_categories,
            'top_features': top_features,
            'top_venues': top_venues,
            'event_type_preference': event_type_preference,
            'time_patterns': {
                'preferred_days': preferred_days,
                'preferred_times': list(set(preferred_times))
            }
        }


# ============================================================================
# Report Generation Class
# ============================================================================

class ReportGeneration:
    """Handles generation of markdown reports for users and events."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize ReportGeneration.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger('MongoDBPull.ReportGeneration')
        self.module_dir = os.path.dirname(os.path.abspath(__file__))
        self.reports_dir = os.path.join(self.module_dir, 'reports')
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def generate_users_report(self, users: List[Dict[str, Any]]) -> str:
        """
        Generate comprehensive markdown report for users.
        
        Args:
            users: List of enriched user dictionaries
            
        Returns:
            Path to generated report file
        """
        self.logger.info("Generating users markdown report...")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_file = os.path.join(self.reports_dir, f"users_report_{timestamp}.md")
        
        # Calculate aggregate metrics
        total_users = len(users)
        total_events = sum(u.get('event_count', 0) for u in users)
        total_orders = sum(u.get('order_count', 0) for u in users)
        total_spent = sum(u.get('total_spent', 0) for u in users)
        avg_events_per_user = total_events / total_users if total_users > 0 else 0
        avg_spent_per_user = total_spent / total_users if total_users > 0 else 0
        
        # Calculate segment distributions
        journey_counts = defaultdict(int)
        engagement_counts = defaultdict(int)
        value_counts = defaultdict(int)
        social_counts = defaultdict(int)
        user_seg_counts = defaultdict(int)
        churn_counts = defaultdict(int)
        completeness_counts = defaultdict(int)
        campaign_qual_counts = {
            'seat_newcomers': 0,
            'fill_the_table': 0,
            'return_to_table': 0
        }
        
        for user in users:
            journey_counts[user.get('journey_stage', 'Unknown')] += 1
            engagement_counts[user.get('engagement_status', 'Unknown')] += 1
            value_counts[user.get('value_segment', 'Unknown')] += 1
            social_counts[user.get('social_role', 'Unknown')] += 1
            user_seg_counts[user.get('user_segment', 'Unknown')] += 1
            churn_counts[user.get('churn_risk', 'Unknown')] += 1
            
            completeness = user.get('profile_completeness', '0/8 (0%)')
            filled = int(completeness.split('/')[0]) if '/' in completeness else 0
            completeness_counts[f"{filled}/8"] += 1
            
            quals = user.get('campaign_qualifications', {})
            if quals.get('qualifies_seat_newcomers'):
                campaign_qual_counts['seat_newcomers'] += 1
            if quals.get('qualifies_fill_the_table'):
                campaign_qual_counts['fill_the_table'] += 1
            if quals.get('qualifies_return_to_table'):
                campaign_qual_counts['return_to_table'] += 1
        
        # Generate markdown content
        markdown = []
        markdown.append("# Users Data Report")
        markdown.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        markdown.append(f"\n**Total Users:** {total_users}")
        
        # Aggregate Metrics
        markdown.append("\n## Aggregate Metrics\n")
        markdown.append("| Metric | Value |")
        markdown.append("|--------|-------|")
        markdown.append(f"| Total Users | {total_users:,} |")
        markdown.append(f"| Total Events Attended | {total_events:,} |")
        markdown.append(f"| Total Orders | {total_orders:,} |")
        markdown.append(f"| Total Spent | ${total_spent:,.2f} |")
        markdown.append(f"| Avg Events per User | {avg_events_per_user:.2f} |")
        markdown.append(f"| Avg Spent per User | ${avg_spent_per_user:.2f} |")
        
        # Segment Distributions
        markdown.append("\n## Segment Distributions\n")
        
        # Journey Stage
        markdown.append("### Journey Stage Distribution\n")
        markdown.append("| Journey Stage | Count | Percentage |")
        markdown.append("|--------------|-------|------------|")
        for stage, count in sorted(journey_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_users) * 100
            markdown.append(f"| {stage} | {count:,} | {pct:.1f}% |")
        
        # Engagement Status
        markdown.append("\n### Engagement Status Distribution\n")
        markdown.append("| Engagement Status | Count | Percentage |")
        markdown.append("|-------------------|-------|------------|")
        for status, count in sorted(engagement_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_users) * 100
            markdown.append(f"| {status} | {count:,} | {pct:.1f}% |")
        
        # Value Segment
        markdown.append("\n### Value Segment Distribution\n")
        markdown.append("| Value Segment | Count | Percentage |")
        markdown.append("|---------------|-------|------------|")
        for segment, count in sorted(value_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_users) * 100
            markdown.append(f"| {segment} | {count:,} | {pct:.1f}% |")
        
        # Social Role
        markdown.append("\n### Social Role Distribution\n")
        markdown.append("| Social Role | Count | Percentage |")
        markdown.append("|------------|-------|------------|")
        for role, count in sorted(social_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_users) * 100
            markdown.append(f"| {role} | {count:,} | {pct:.1f}% |")
        
        # User Segment
        markdown.append("\n### User Segment Distribution\n")
        markdown.append("| User Segment | Count | Percentage |")
        markdown.append("|--------------|-------|------------|")
        for segment, count in sorted(user_seg_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_users) * 100
            markdown.append(f"| {segment} | {count:,} | {pct:.1f}% |")
        
        # Churn Risk
        markdown.append("\n### Churn Risk Distribution\n")
        markdown.append("| Churn Risk | Count | Percentage |")
        markdown.append("|------------|-------|------------|")
        for risk, count in sorted(churn_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_users) * 100
            markdown.append(f"| {risk} | {count:,} | {pct:.1f}% |")
        
        # Profile Completeness
        markdown.append("\n### Profile Completeness Distribution\n")
        markdown.append("| Completeness | Count | Percentage |")
        markdown.append("|--------------|-------|------------|")
        for comp, count in sorted(completeness_counts.items(), key=lambda x: int(x[0].split('/')[0]), reverse=True):
            pct = (count / total_users) * 100
            markdown.append(f"| {comp} | {count:,} | {pct:.1f}% |")
        
        # Campaign Qualifications
        markdown.append("\n### Campaign Qualification Distribution\n")
        markdown.append("| Campaign | Qualified Users | Percentage |")
        markdown.append("|----------|-----------------|------------|")
        for campaign, count in campaign_qual_counts.items():
            pct = (count / total_users) * 100
            markdown.append(f"| {campaign.replace('_', '-')} | {count:,} | {pct:.1f}% |")
        
        # Field Definitions
        markdown.append("\n## Field Definitions\n")
        markdown.append("\n### Raw Fields (from MongoDB)\n")
        markdown.append("""
| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `_id` | ObjectId | Unique user identifier | MongoDB `user` collection |
| `id` | str | String representation of `_id` | MongoDB |
| `email` | str | User's email address | MongoDB |
| `firstName` | str | User's first name | MongoDB |
| `lastName` | str | User's last name | MongoDB |
| `role` | str | User role ("ADMIN", "REGULAR", "POTENTIAL") | MongoDB |
| `interests` | list | Array of user interests | MongoDB |
| `occupation` | str | User's occupation | MongoDB |
| `homeNeighborhood` | str | User's neighborhood | MongoDB |
| `gender` | str | User's gender | MongoDB |
| `phone` | str | Phone number | MongoDB |
| `birthDay` | str/None | User's birthday (ISO 8601) | MongoDB |
| `tableTypePreference` | str | Preferred table type | MongoDB |
| `createdAt` | str (ISO 8601) | When user account was created | MongoDB |
""")
        
        markdown.append("\n### Derived/Transformed Fields\n")
        markdown.append("""
| Field | Type | Derivation | Function |
|-------|------|------------|----------|
| `event_count` | int | Count of events where user is participant OR owner | `calculate_stats()` |
| `order_count` | int | Count of orders where `userId` matches user | `calculate_stats()` |
| `total_spent` | float | Sum of order prices (handles dict and numeric formats) | `calculate_stats()` |
| `days_inactive` | int | Days since last activity (9999 if never active) | `calculate_stats()` → `derive_engagement()` |
| `journey_stage` | str | **Calculation:** If `role == "POTENTIAL"` → "Signed Up Online"; Else if `event_count == 0` → "Downloaded App"; Else if `event_count >= 1 and total_spent == 0` → "Joined Table"; Else if `total_spent > 0 and event_count > 1` → "Returned"; Else if `total_spent > 0` → "Attended"; Else → "Downloaded App" | `derive_segments()` |
| `engagement_status` | str | **Calculation:** `days_inactive <= 30` → "active"; `days_inactive <= 90` → "dormant"; `days_inactive == 9999` → "new"; Else → "churned" | `derive_engagement()` |
| `value_segment` | str | **Calculation:** `total_spent >= 2000` → "VIP"; `total_spent >= 500` → "High Value"; `total_spent > 0` → "Regular"; Else → "Low Value" | `derive_segments()` |
| `social_role` | str | **Calculation:** `event_count >= 50` → "social_leader"; `event_count >= 20` → "active_participant"; Else → "observer" | `derive_segments()` |
| `churn_risk` | str | **Calculation:** `days_inactive >= 180` → "high"; `days_inactive >= 90` → "medium"; Else → "low" | `derive_segments()` |
| `user_segment` | str | Priority-based classification: "Dead", "Campaign", "Fresh", "Active", "Dormant", "Inactive", "New" | `derive_segments()` |
| `profile_completeness` | str | Count of filled required fields: "{filled}/5 ({percentage}%)" | `calculate_completeness()` |
| `personalization_ready` | bool | `True` if at least 4 of 5 required fields are filled (interests, tableTypePreference, homeNeighborhood, gender, relationship_status) | `calculate_completeness()` |
| `newcomer_score` | float (0-100) | Event history (0-50) + Profile completeness (0-30) + Account recency (0-20) | `calculate_newcomer_score()` |
| `reactivation_score` | float (0-100) | Profile completeness (0-40) + Dormancy duration (0-30) + Event history (0-30) | `calculate_reactivation_score()` |
| `campaign_qualifications` | Dict | Qualification flags and reasons for seat-newcomers, fill-the-table, return-to-table | `check_user_campaign_qualifications()` |
| `summary` | str | Comprehensive summary incorporating personalization details and narrative synthesis (journey stage, engagement status, value segment, registration year, etc.) | `generate_user_summary()` |
| `social_connections` | List[Dict] | Users this user has attended events with | `get_user_social_connections()` |
| `event_history` | List[Dict] | Past events user has attended/owned | `get_user_event_history()` |
| `interest_analysis` | Dict | Analyzed interests from event history | `analyze_user_interests_from_events()` |
""")
        
        # Insights
        markdown.append("\n## Key Insights\n")
        ready_count = sum(1 for u in users if u.get('personalization_ready', False))
        active_count = sum(1 for u in users if u.get('is_active', False))
        vip_count = sum(1 for u in users if u.get('value_segment') == 'VIP')
        
        markdown.append(f"- **Personalization Ready:** {ready_count:,} users ({ready_count/total_users*100:.1f}%) have complete profiles ready for personalization")
        markdown.append(f"- **Active Users:** {active_count:,} users ({active_count/total_users*100:.1f}%) are currently active (≤30 days inactive)")
        markdown.append(f"- **VIP Users:** {vip_count:,} users ({vip_count/total_users*100:.1f}%) are VIPs (≥$2000 spent)")
        markdown.append(f"- **Average Engagement:** Users average {avg_events_per_user:.1f} events and ${avg_spent_per_user:.2f} in spending")
        
        # Write report
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(markdown))
        
        self.logger.info(f"✓ Generated users report: {report_file}")
        return report_file
    
    def generate_events_report(self, events: List[Dict[str, Any]]) -> str:
        """
        Generate comprehensive markdown report for events.
        
        Args:
            events: List of enriched event dictionaries
            
        Returns:
            Path to generated report file
        """
        self.logger.info("Generating events markdown report...")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_file = os.path.join(self.reports_dir, f"events_report_{timestamp}.md")
        
        # Calculate aggregate metrics
        total_events = len(events)
        total_participants = sum(e.get('participantCount', len(e.get('participants', []))) for e in events)
        total_capacity = sum(e.get('maxParticipants') or 0 for e in events)
        avg_participation = (total_participants / total_capacity * 100) if total_capacity > 0 else 0
        
        # Calculate segment distributions
        type_counts = defaultdict(int)
        status_counts = defaultdict(int)
        participation_ranges = {
            '0-25%': 0,
            '25-50%': 0,
            '50-75%': 0,
            '75-100%': 0,
            '100%+': 0
        }
        campaign_qual_counts = {
            'seat_newcomers': 0,
            'fill_the_table': 0,
            'return_to_table': 0
        }
        
        for event in events:
            type_counts[event.get('type', 'Unknown')] += 1
            status_counts[event.get('eventStatus', 'Unknown')] += 1
            
            pct = event.get('participationPercentage', 0)
            if pct < 25:
                participation_ranges['0-25%'] += 1
            elif pct < 50:
                participation_ranges['25-50%'] += 1
            elif pct < 75:
                participation_ranges['50-75%'] += 1
            elif pct <= 100:
                participation_ranges['75-100%'] += 1
            else:
                participation_ranges['100%+'] += 1
            
            quals = event.get('campaign_qualifications', {})
            if quals.get('qualifies_seat_newcomers'):
                campaign_qual_counts['seat_newcomers'] += 1
            if quals.get('qualifies_fill_the_table'):
                campaign_qual_counts['fill_the_table'] += 1
            if quals.get('qualifies_return_to_table'):
                campaign_qual_counts['return_to_table'] += 1
        
        # Generate markdown content
        markdown = []
        markdown.append("# Events Data Report")
        markdown.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        markdown.append(f"\n**Total Events:** {total_events}")
        
        # Aggregate Metrics
        markdown.append("\n## Aggregate Metrics\n")
        markdown.append("| Metric | Value |")
        markdown.append("|--------|-------|")
        markdown.append(f"| Total Events | {total_events:,} |")
        markdown.append(f"| Total Participants | {total_participants:,} |")
        markdown.append(f"| Total Capacity | {total_capacity:,} |")
        markdown.append(f"| Average Participation Rate | {avg_participation:.1f}% |")
        
        # Segment Distributions
        markdown.append("\n## Segment Distributions\n")
        
        # Event Type
        markdown.append("### Event Type Distribution\n")
        markdown.append("| Event Type | Count | Percentage |")
        markdown.append("|------------|-------|------------|")
        for event_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_events) * 100
            markdown.append(f"| {event_type} | {count:,} | {pct:.1f}% |")
        
        # Event Status
        markdown.append("\n### Event Status Distribution\n")
        markdown.append("| Event Status | Count | Percentage |")
        markdown.append("|--------------|-------|------------|")
        for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_events) * 100
            markdown.append(f"| {status} | {count:,} | {pct:.1f}% |")
        
        # Participation Percentage
        markdown.append("\n### Participation Percentage Distribution\n")
        markdown.append("| Participation Range | Count | Percentage |")
        markdown.append("|---------------------|-------|------------|")
        for range_name, count in participation_ranges.items():
            pct = (count / total_events) * 100
            markdown.append(f"| {range_name} | {count:,} | {pct:.1f}% |")
        
        # Campaign Qualifications
        markdown.append("\n### Campaign Qualification Distribution\n")
        markdown.append("| Campaign | Qualified Events | Percentage |")
        markdown.append("|----------|------------------|------------|")
        for campaign, count in campaign_qual_counts.items():
            pct = (count / total_events) * 100
            markdown.append(f"| {campaign.replace('_', '-')} | {count:,} | {pct:.1f}% |")
        
        # Field Definitions
        markdown.append("\n## Field Definitions\n")
        markdown.append("\n### Raw Fields (from MongoDB)\n")
        markdown.append("""
| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `_id` | ObjectId | Unique event identifier | MongoDB `event` collection |
| `id` | str | String representation of `_id` | MongoDB |
| `name` | str | Event name | MongoDB |
| `startDate` | str (ISO 8601) | Event start date/time | MongoDB |
| `endDate` | str (ISO 8601) | Event end date/time | MongoDB |
| `type` | str | Event type ("public", "private") | MongoDB |
| `eventStatus` | str | Event approval status ("approved", etc.) | MongoDB |
| `maxParticipants` | int | Maximum number of participants | MongoDB |
| `minParticipants` | int | Minimum number of participants | MongoDB |
| `participants` | list | List of participant user IDs | MongoDB |
| `ownerId` | str | ID of the event owner/creator | MongoDB |
| `venueName` | str | Name of the venue | MongoDB |
| `neighborhood` | str | Event neighborhood | MongoDB |
| `categories` | list | Event categories | MongoDB |
| `features` | list | Event features | MongoDB |
| `description` | str | Event description (may contain HTML) | MongoDB |
| `createdAt` | str (ISO 8601) | When the event was created | MongoDB |
""")
        
        markdown.append("\n### Derived/Transformed Fields\n")
        markdown.append("""
| Field | Type | Derivation | Function |
|-------|------|------------|----------|
| `participantCount` | int | Number of participants: `len(event.get('participants', []))` | `enrich_event_with_participants()` |
| `participationPercentage` | float | Percentage of capacity: `(participantCount / maxParticipants) * 100` | `enrich_event_with_participants()` |
| `participant_profiles_enriched` | bool | `True` if participant analysis completed | `enrich_event_with_participants()` |
| `participant_top_interests` | List[Tuple[str, int]] | Top 5 interests from participants with counts | `enrich_event_with_participants()` |
| `participant_top_occupations` | List[Tuple[str, int]] | Top 5 occupations from participants with counts | `enrich_event_with_participants()` |
| `participant_top_neighborhoods` | List[Tuple[str, int]] | Top 5 neighborhoods from participants with counts | `enrich_event_with_participants()` |
| `campaign_qualifications` | Dict | Qualification flags and reasons for seat-newcomers, fill-the-table, return-to-table | `check_event_campaign_qualifications()` |
| `summary` | str | Generated event summary with venue, categories, features, participation | `generate_event_summary()` |
""")
        
        # Campaign Qualification Criteria
        markdown.append("\n### Campaign Qualification Criteria\n")
        markdown.append("""
#### seat-newcomers
- Future event (`startDate > now`)
- Public event (`type == "public"`)
- Has capacity (`maxParticipants > 0`)
- Good participation (50-80% filled)

#### fill-the-table
- Future event (`startDate > now`)
- Public event (`type == "public"`)
- Underfilled (`participationPercentage < 50%`)
- Has capacity (`maxParticipants > 0`)

#### return-to-table
- Future event (`startDate > now`)
- Public event (`type == "public"`)
- Has capacity (`maxParticipants > 0`)
- Prefers higher participation (>60%)
""")
        
        # Insights
        markdown.append("\n## Key Insights\n")
        underfilled = sum(1 for e in events if e.get('participationPercentage', 0) < 50)
        well_filled = sum(1 for e in events if 50 <= e.get('participationPercentage', 0) <= 80)
        overfilled = sum(1 for e in events if e.get('participationPercentage', 0) > 100)
        public_events = sum(1 for e in events if e.get('type') == 'public')
        
        markdown.append(f"- **Underfilled Events:** {underfilled:,} events ({underfilled/total_events*100:.1f}%) have <50% participation")
        markdown.append(f"- **Well-Filled Events:** {well_filled:,} events ({well_filled/total_events*100:.1f}%) have 50-80% participation")
        markdown.append(f"- **Overfilled Events:** {overfilled:,} events ({overfilled/total_events*100:.1f}%) have >100% participation")
        markdown.append(f"- **Public Events:** {public_events:,} events ({public_events/total_events*100:.1f}%) are public")
        markdown.append(f"- **Average Participation:** {avg_participation:.1f}% across all events")
        
        # Write report
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(markdown))
        
        self.logger.info(f"✓ Generated events report: {report_file}")
        return report_file


# ============================================================================
# Main MongoDBPull Class
# ============================================================================

class MongoDBPull:
    """Main class orchestrating MongoDB data retrieval and enrichment."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize MongoDBPull.
        
        Args:
            logger: Optional logger instance. If None, creates a default logger.
        """
        self.logger = logger or setup_logging()
        self.connection = MongoDBConnection(self.logger)
        self.user_enrichment = UserEnrichment(self.logger)
        self.event_transformation = EventTransformation(self.logger)
        self.campaign_qualification = CampaignQualification(self.logger)
        self.summary_generation = SummaryGeneration(self.logger)
        self.social_connection = SocialConnection(self.logger)
        self.report_generation = ReportGeneration(self.logger)
    
    def _save_data_to_file(self, data: List[Dict[str, Any]], data_type: str) -> str:
        """
        Save data to a timestamped JSON file in the data folder.
        
        Args:
            data: List of dictionaries to save
            data_type: Type of data ('users' or 'events')
            
        Returns:
            Path to the saved file
        """
        # Get the directory of this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(current_dir, 'data')
        
        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # Generate timestamp
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = f"{data_type}_{timestamp}.json"
        filepath = os.path.join(data_dir, filename)
        
        # Convert ObjectId to string for JSON serialization
        def convert_objectid(obj):
            if isinstance(obj, ObjectId):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_objectid(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_objectid(item) for item in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            return obj
        
        serializable_data = convert_objectid(data)
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"✓ Data saved to: {filepath} ({len(data)} {data_type})")
        return filepath
    
    def users_pull(self, filter: Optional[Dict[str, Any]] = None, limit: Optional[int] = None, generate_report: bool = True, save_data: bool = True, users: Optional[List[Dict[str, Any]]] = None, events: Optional[List[Dict[str, Any]]] = None, orders: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Get fully transformed and enriched users.
        
        This is the high-level function that:
        1. Fetches users, events, and orders from MongoDB (or uses provided data)
        2. Transforms and enriches all users
        3. Adds summaries, social connections, event history, interest analysis
        4. Generates markdown report (if generate_report=True)
        5. Returns complete user objects ready for use
        
        Args:
            filter: Optional MongoDB filter for users (only used if users not provided)
            limit: Optional limit on number of users (only used if users not provided)
            generate_report: If True, generates timestamped markdown report in reports/ folder
            save_data: If True, saves the enriched user data to a timestamped JSON file in data/ folder
            users: Optional pre-fetched users list. If provided, filter and limit are ignored.
            events: Optional pre-fetched events list. If not provided, fetches all events.
            orders: Optional pre-fetched orders list. If not provided, fetches all orders.
            
        Returns:
            List of fully enriched user dictionaries with the following fields:
            
            RAW FIELDS (from MongoDB):
            - All original user collection fields (id, email, firstName, lastName, role,
              interests, occupation, homeNeighborhood, gender, phone, birthDay,
              tableTypePreference, createdAt, etc.)
            
            DERIVED FIELDS:
            - event_count: Count of events (participant OR owner)
            - order_count: Count of orders
            - total_spent: Total spending amount
            - days_inactive: Days since last activity
            - engagement_status: "active", "dormant", "churned", or "new"
            - journey_stage: "Signed Up Online", "Downloaded App", "Joined Table", 
              "Attended", or "Returned"
            - value_segment: "VIP", "High Value", "Regular", or "Low Value"
            - social_role: "social_leader", "active_participant", or "observer"
            - churn_risk: "high", "medium", or "low"
            - user_segment: "Dead", "Campaign", "Fresh", "Active", "Dormant", 
              "Inactive", or "New"
            - profile_completeness: Completeness score string (e.g., "8/8 (100%)")
            - personalization_ready: Boolean indicating if profile is complete
            - newcomer_score: Score 0-100 for newcomer users
            - reactivation_score: Score 0-100 for dormant users
            - campaign_qualifications: Dict with qualification flags and reasons
            - social_connections: List of users attended events with
            - event_history: List of past events attended/owned
            - interest_analysis: Dict with analyzed interests from event history
            - summary: Comprehensive summary string incorporating personalization details
              and narrative synthesis (journey stage, engagement status, value segment, etc.)
            
            See module docstring for detailed field definitions and derivation logic.
        """
        self.logger.info("=" * 80)
        self.logger.info("STARTING USER PULL OPERATION")
        self.logger.info("=" * 80)
        self.logger.info(f"Purpose: Fetch and enrich users with complete profile data, segments, and campaign qualifications")
        
        # Fetch data (use provided data if available, otherwise fetch from MongoDB)
        self.logger.info("\nStep 1: Fetching raw data from MongoDB...")
        if users is None:
            users = self.connection.get_users(filter=filter, limit=limit)
        else:
            self.logger.info(f"  Using provided users list ({len(users)} users)")
            # Apply filter and limit if provided and users were pre-fetched
            if filter is not None:
                # Note: Simple filter application - for complex filters, filter before passing
                pass
            if limit is not None and len(users) > limit:
                users = users[:limit]
        
        if events is None:
            events = self.connection.get_events()
        else:
            self.logger.info(f"  Using provided events list ({len(events)} events)")
        
        if orders is None:
            orders = self.connection.get_orders()
        else:
            self.logger.info(f"  Using provided orders list ({len(orders)} orders)")
        
        self.logger.info(f"\nStep 2: Transforming and enriching {len(users)} users...")
        self.logger.info("  - Calculating statistics (event count, order count, spending)")
        self.logger.info("  - Deriving segments (journey stage, engagement status, value segment)")
        self.logger.info("  - Calculating profile completeness")
        self.logger.info("  - Generating narratives")
        self.logger.info("  - Adding campaign qualifications")
        
        # Transform users
        enriched_users = self.user_enrichment.transform_users(users, events, orders, self.campaign_qualification)
        
        # Create user lookup for social connections
        user_lookup = {str(u.get('_id', '')): u for u in enriched_users}
        
        self.logger.info(f"\nStep 3: Adding additional enrichment to {len(enriched_users)} users...")
        self.logger.info("  - Generating summaries")
        self.logger.info("  - Finding social connections")
        self.logger.info("  - Retrieving event history")
        self.logger.info("  - Analyzing interests from events")
        self.logger.info("  - Calculating scores (newcomer, reactivation)")
        
        # Add additional enrichment
        total = len(enriched_users)
        for idx, user in enumerate(enriched_users, 1):
            uid = str(user.get('_id', ''))
            
            # Add campaign qualifications (ensure it's there)
            user_events = [e for e in events if uid in [str(p) for p in e.get('participants', [])] or uid == str(e.get('ownerId', ''))]
            self.campaign_qualification.add_campaign_qualifications_to_user(user, user_events)
            
            # Add summary
            user['summary'] = self.summary_generation.generate_user_summary(user)
            
            # Add social connections
            user['social_connections'] = self.social_connection.get_user_social_connections(uid, events)
            
            # Add event history
            user['event_history'] = self.social_connection.get_user_event_history(uid, events)
            
            # Add interest analysis
            user['interest_analysis'] = self.social_connection.analyze_user_interests_from_events(uid, events)
            
            # Add scores
            user['newcomer_score'] = calculate_newcomer_score(user)
            user['reactivation_score'] = calculate_reactivation_score(user)
            
            if idx % 100 == 0 or idx == total:
                self.logger.info(f"  Enriched {idx}/{total} users ({(idx/total)*100:.1f}%)")
        
        self.logger.info("\n" + "=" * 80)
        self.logger.info(f"✓ USER PULL COMPLETED: {len(enriched_users)} users fully enriched")
        self.logger.info("=" * 80)
        
        # Generate report if requested
        if generate_report:
            self.logger.info("\nGenerating users markdown report...")
            report_path = self.report_generation.generate_users_report(enriched_users)
            self.logger.info(f"✓ Report saved to: {report_path}")
        
        # Save data if requested
        if save_data:
            self.logger.info("\nSaving users data to JSON file...")
            data_path = self._save_data_to_file(enriched_users, 'users')
        
        return enriched_users
    
    def events_pull(self, filter: Optional[Dict[str, Any]] = None, limit: Optional[int] = None, generate_report: bool = True, save_data: bool = True, users: Optional[List[Dict[str, Any]]] = None, events: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Get fully transformed and enriched events.
        
        This is the high-level function that:
        1. Fetches events and users from MongoDB (or uses provided data)
        2. Transforms and enriches all events with participant analysis
        3. Adds summaries, campaign qualifications
        4. Generates markdown report (if generate_report=True)
        5. Returns complete event objects ready for use
        
        Args:
            filter: Optional MongoDB filter for events (only used if events not provided)
            limit: Optional limit on number of events (only used if events not provided)
            generate_report: If True, generates timestamped markdown report in reports/ folder
            save_data: If True, saves the enriched event data to a timestamped JSON file in data/ folder
            users: Optional pre-fetched users list. If not provided, fetches all users.
            events: Optional pre-fetched events list. If provided, filter and limit are ignored.
            
        Returns:
            List of fully enriched event dictionaries with the following fields:
            
            RAW FIELDS (from MongoDB):
            - All original event collection fields (id, name, startDate, endDate, type,
              eventStatus, maxParticipants, minParticipants, participants, ownerId,
              venueName, neighborhood, categories, features, description, createdAt, etc.)
            
            DERIVED FIELDS:
            - participantCount: Number of participants
            - participationPercentage: Percentage of capacity filled
            - participant_profiles_enriched: Boolean indicating participant analysis completed
            - participant_count: Number of participants with profile data available
            - participant_top_interests: Top 5 interests from participants with counts
            - participant_top_occupations: Top 5 occupations from participants with counts
            - participant_top_neighborhoods: Top 5 neighborhoods from participants with counts
            - campaign_qualifications: Dict with qualification flags and reasons for
              seat-newcomers, fill-the-table, return-to-table campaigns
            - summary: Generated event summary with venue, categories, features, participation
            
            See module docstring for detailed field definitions and derivation logic.
        """
        self.logger.info("=" * 80)
        self.logger.info("STARTING EVENT PULL OPERATION")
        self.logger.info("=" * 80)
        self.logger.info(f"Purpose: Fetch and enrich events with participant analysis and campaign qualifications")
        
        # Fetch data (use provided data if available, otherwise fetch from MongoDB)
        self.logger.info("\nStep 1: Fetching raw data from MongoDB...")
        if events is None:
            events = self.connection.get_events(filter=filter, limit=limit)
        else:
            self.logger.info(f"  Using provided events list ({len(events)} events)")
            # Apply filter and limit if provided and events were pre-fetched
            if filter is not None:
                # Note: Simple filter application - for complex filters, filter before passing
                pass
            if limit is not None and len(events) > limit:
                events = events[:limit]
        
        if users is None:
            users = self.connection.get_users()
        else:
            self.logger.info(f"  Using provided users list ({len(users)} users)")
        
        self.logger.info(f"\nStep 2: Creating user lookup for participant analysis...")
        # Create user lookup
        user_lookup = {str(u.get('_id', '')): u for u in users}
        self.logger.info(f"  Created lookup with {len(user_lookup)} users")
        
        self.logger.info(f"\nStep 3: Transforming and enriching {len(events)} events...")
        self.logger.info("  - Analyzing participant demographics (interests, occupations, neighborhoods)")
        self.logger.info("  - Calculating participation percentages")
        self.logger.info("  - Adding campaign qualifications")
        self.logger.info("  - Generating summaries")
        
        # Transform events
        enriched_events = self.event_transformation.transform_events(
            events, 
            user_lookup, 
            self.campaign_qualification,
            self.summary_generation
        )
        
        self.logger.info("\n" + "=" * 80)
        self.logger.info(f"✓ EVENT PULL COMPLETED: {len(enriched_events)} events fully enriched")
        self.logger.info("=" * 80)
        
        # Generate report if requested
        if generate_report:
            self.logger.info("\nGenerating events markdown report...")
            report_path = self.report_generation.generate_events_report(enriched_events)
            self.logger.info(f"✓ Report saved to: {report_path}")
        
        # Save data if requested
        if save_data:
            self.logger.info("\nSaving events data to JSON file...")
            data_path = self._save_data_to_file(enriched_events, 'events')
        
        return enriched_events
    
    def users_events_pull(self, users_filter: Optional[Dict[str, Any]] = None, users_limit: Optional[int] = None, events_filter: Optional[Dict[str, Any]] = None, events_limit: Optional[int] = None, generate_report: bool = True, save_data: bool = True) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Get fully transformed and enriched users and events in a single operation.
        
        This function optimizes data fetching by querying MongoDB once for users and events,
        then passing the data to both users_pull() and events_pull() methods. This avoids
        duplicate database queries when both users and events are needed.
        
        This is the high-level function that:
        1. Fetches users, events, and orders from MongoDB (once)
        2. Calls users_pull() with pre-fetched data
        3. Calls events_pull() with pre-fetched data
        4. Returns both enriched users and events
        
        Args:
            users_filter: Optional MongoDB filter for users
            users_limit: Optional limit on number of users
            events_filter: Optional MongoDB filter for events
            events_limit: Optional limit on number of events
            generate_report: If True, generates timestamped markdown reports in reports/ folder
            save_data: If True, saves the enriched data to timestamped JSON files in data/ folder
            
        Returns:
            Tuple of (enriched_users, enriched_events):
            - enriched_users: List of fully enriched user dictionaries (see users_pull() docstring)
            - enriched_events: List of fully enriched event dictionaries (see events_pull() docstring)
        """
        self.logger.info("=" * 80)
        self.logger.info("STARTING USERS AND EVENTS PULL OPERATION")
        self.logger.info("=" * 80)
        self.logger.info(f"Purpose: Fetch and enrich both users and events with optimized data retrieval")
        
        # Fetch data once
        self.logger.info("\nStep 1: Fetching raw data from MongoDB (single query for efficiency)...")
        users = self.connection.get_users(filter=users_filter, limit=users_limit)
        events = self.connection.get_events(filter=events_filter, limit=events_limit)
        orders = self.connection.get_orders()
        
        self.logger.info(f"  ✓ Fetched {len(users)} users")
        self.logger.info(f"  ✓ Fetched {len(events)} events")
        self.logger.info(f"  ✓ Fetched {len(orders)} orders")
        
        # Call users_pull with pre-fetched data
        self.logger.info("\n" + "=" * 80)
        self.logger.info("Processing users with pre-fetched data...")
        self.logger.info("=" * 80)
        enriched_users = self.users_pull(
            filter=None,  # Already filtered
            limit=None,  # Already limited
            generate_report=generate_report,
            save_data=save_data,
            users=users,
            events=events,
            orders=orders
        )
        
        # Call events_pull with pre-fetched data
        self.logger.info("\n" + "=" * 80)
        self.logger.info("Processing events with pre-fetched data...")
        self.logger.info("=" * 80)
        enriched_events = self.events_pull(
            filter=None,  # Already filtered
            limit=None,  # Already limited
            generate_report=generate_report,
            save_data=save_data,
            users=users,
            events=events
        )
        
        self.logger.info("\n" + "=" * 80)
        self.logger.info(f"✓ USERS AND EVENTS PULL COMPLETED")
        self.logger.info(f"  - {len(enriched_users)} users enriched")
        self.logger.info(f"  - {len(enriched_events)} events enriched")
        self.logger.info("=" * 80)
        
        return enriched_users, enriched_events
    
    def close(self):
        """Close MongoDB connection."""
        self.connection.close()

