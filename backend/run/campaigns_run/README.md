# Campaigns Run - Refactoring Plan

## Overview

This document provides detailed instructions for refactoring the three campaign scripts from `backend/scripts/` to work within the `backend/run/campaigns_run/` module structure. These scripts will be updated to use the centralized `backend/utils/` modules, update to Leo2 Firebase database, sync messages to Airtable instead of Firebase, and provide main functions that can be called from a central orchestrator.

---

## Scripts to Refactor

1. **fill_the_table.py** - Fill The Table Campaign
2. **return_to_table.py** - Return To Table Campaign
3. **seat_newcomers.py** - Seat Newcomers Campaign

---

## Refactoring Tasks

### Task 1: Update Import Paths

**Objective:** Update all helper module imports to point to `backend/utils/` instead of the old `helpers/` directory.

**Current Import Structure (in scripts/):**
```python
# Current imports from scripts folder
root_dir = os.path.join(script_dir, '../..')
sys.path.insert(0, root_dir)
from helpers.report_creation.report_generator import generate_report
from helpers.firebase_manage.firebase_manager import FirebaseManager
from helpers.mongodb_pull import MongoDBPull
```

**New Import Structure (for run/campaigns_run/):**
```python
# New imports from run/campaigns_run folder
# Add backend/utils to path
import os
import sys

# Get path to backend/utils
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')
utils_dir = os.path.join(backend_dir, 'utils')
sys.path.insert(0, backend_dir)

# Import from utils modules
from utils.report_creation.report_generator import generate_report
from utils.firebase_manage.firebase_manager import FirebaseManager
from utils.mongodb_pull.mongodb_pull import MongoDBPull
```

**Directory Structure Reference:**
```
backend/
├── run/
│   └── campaigns_run/
│       ├── README.md (this file)
│       ├── fill_the_table.py
│       ├── return_to_table.py
│       ├── seat_newcomers.py
│       └── run_campaigns.py (orchestrator)
├── scripts/
│   ├── fill-the-table/
│   ├── return-to-table/
│   └── seat-newcomers/
└── utils/
    ├── airtable_sync/
    ├── firebase_manage/
    ├── mongodb_pull/
    └── report_creation/
```

**Instructions:**
1. Copy each script from `backend/scripts/<script-name>/` to `backend/run/campaigns_run/`
2. Update the path calculation to account for new location (2 levels up to backend/)
3. Change import statements from `helpers.` to `utils.`
4. Ensure logging throughout all operations with INFO level for key steps and DEBUG for detailed operations

---

### Task 2: Update Firebase Database from "Leo" to "Leo2"

**Objective:** Update the Firebase base path configuration in `firebase_manager.py` to point to "Leo2" instead of "Leo" database.

**Location to Update:**
- File: `backend/utils/firebase_manage/firebase_manager.py`

**Current Configuration:**
```python
# In firebase_manager.py
self.firebase_base_path = os.getenv('FIREBASE_BASE_PATH', 'Leo')
```

**Updated Configuration:**
```python
# In firebase_manager.py
self.firebase_base_path = os.getenv('FIREBASE_BASE_PATH', 'Leo2')
```

**Alternative Approach (Environment Variable):**
If you want to keep the code flexible, update your `.env` file instead:
```bash
# In .env file
FIREBASE_BASE_PATH=Leo2
```

**Instructions:**
1. Open `backend/utils/firebase_manage/firebase_manager.py`
2. Locate the `firebase_base_path` initialization (likely in `__init__` method or `_init_firebase`)
3. Change default value from `'Leo'` to `'Leo2'`
4. Test Firebase connectivity to ensure Leo2 database is accessible
5. Add logging: `logger.info(f"Using Firebase database: {self.firebase_base_path}")`

---

### Task 3: Replace Firebase Message Updates with Airtable Message Table Updates

**Objective:** Where the scripts currently save messages to Firebase, update them to instead save to the Airtable messages table using the airtable_sync module.

**Current Firebase Message Save (in campaign scripts):**
```python
# Current code in campaign scripts
self.firebase_manager.save_message(message_record)
```

**New Airtable Message Save:**
```python
# New code using airtable_sync
from utils.airtable_sync.airtable_sync import AirtableSync

# Initialize in __init__
self.airtable_sync = AirtableSync(logger=self.logger)

# Replace firebase_manager.save_message() with:
self.airtable_sync.save_message(message_record)
```

**Airtable Connection Details (from airtable_sync README):**
- **Base ID:** `appaquqFN7vvvZGcq`
- **Messages Table ID:** `tbljma5S4NhUn1OYl`
- **API Key:** Store in environment variable `AIRTABLE_API_KEY`

**Message Field Mapping:**
```python
# Fields to sync to Airtable Messages table
# Note: These fields match the message_record structure from fill_the_table.py
MESSAGES_FIELD_MAPPING = {
    'id': 'id',
    'user_name': 'user_name',
    'event_name': 'event_name',
    'user_id': 'user_id',
    'event_id': 'event_id',
    'user_email': 'user_email',
    'user_phone': 'user_phone',
    'user_summary': 'user_summary',
    'event_summary': 'event_summary',
    'message_text': 'message',  # Note: 'message' field in Airtable
    'personalization_notes': 'personalization_notes',
    'character_count': 'character_count',
    'similarity_score': 'similarity_score',
    'confidence_percentage': 'confidence_percentage',
    'reasoning': 'reasoning',
    'status': 'status',
    'generated_at': 'createdAt',
    'campaign': 'campaign',
    'updatedAt': 'updatedAt',
}
```

**Implementation Steps:**
1. Create `AirtableSync` class in `backend/utils/airtable_sync/airtable_sync.py` with:
   - `save_message(message_record)` method
   - Connection to Airtable API using `pyairtable` library
   - Field mapping for message records
   - Error handling and logging

2. Update each campaign script's message saving:
   ```python
   # Instead of:
   self.firebase_manager.save_message(message_record)

   # Use:
   try:
       self.airtable_sync.save_message(message_record)
       self.logger.info(f"✓ Saved message to Airtable for {user_name}")
   except Exception as e:
       self.logger.error(f"✗ Failed to save message to Airtable: {e}")
       self.stats['errors'].append(f"Airtable save error: {str(e)}")
   ```

3. Install required library:
   ```bash
   pip install pyairtable
   ```

4. Add comprehensive logging for all Airtable operations:
   - Log connection establishment
   - Log each message save (success/failure)
   - Log batch statistics
   - Log any API errors with full context

---

### Task 4: Create Main Functions for Each Script

**Objective:** Refactor each campaign script to have a `main()` function that accepts inputs and returns a messages array, making them callable from an orchestrator script.

**Current Structure:**
```python
# Current: Scripts run directly with hardcoded logic
def run(self):
    # ... complex logic ...
    # No return value
```

**New Structure:**
```python
def main(users_data: List[Dict],
         events_data: List[Dict],
         matching_prompt: str,
         message_generation_prompt: str,
         logger: logging.Logger = None) -> List[Dict]:
    """
    Main function to run the campaign with provided data.

    Args:
        users_data: List of user dictionaries from MongoDB
        events_data: List of event dictionaries from MongoDB
        matching_prompt: Custom prompt template for user-event matching
        message_generation_prompt: Custom prompt template for message generation
        logger: Optional logger instance

    Returns:
        List of message dictionaries generated by the campaign
    """
    # Initialize campaign with provided data
    campaign = CampaignClass(logger=logger)

    # Use provided data instead of fetching
    campaign.users = users_data
    campaign.events = events_data

    # Use custom prompts
    campaign.matching_prompt_template = matching_prompt
    campaign.message_generation_prompt_template = message_generation_prompt

    # Run campaign logic
    messages = campaign.run_campaign()

    # Log summary with good detail
    logger.info(f"Campaign completed: {len(messages)} messages generated")

    return messages
```

**Instructions for Each Script:**

1. **Extract Main Logic to Reusable Function:**
   - Separate data fetching from processing
   - Accept users_data and events_data as parameters
   - Accept prompt templates as parameters
   - Return messages array instead of saving to Firebase/Airtable

2. **Update Campaign Class Constructor:**
   ```python
   def __init__(self,
                users_data: List[Dict] = None,
                events_data: List[Dict] = None,
                logger: logging.Logger = None):
       """
       Initialize campaign with optional pre-loaded data.
       If data not provided, fetch from MongoDB.
       """
       self.logger = logger or logging.getLogger(self.__class__.__name__)

       # Use provided data or fetch
       if users_data is not None and events_data is not None:
           self.users = users_data
           self.events = events_data
           self.logger.info("Using provided user and event data")
       else:
           self.logger.info("Fetching user and event data from MongoDB")
           self.users = self.get_users()
           self.events = self.get_events()
   ```

3. **Add Logging Throughout:**
   - Log at start of main function with parameters received
   - Log progress through major steps (matching, message generation)
   - Log statistics (matches created, messages generated)
   - Log errors with full context and stack traces
   - Log completion with summary stats

---

### Task 5: Create MongoDB Utility Script

**Objective:** Create a reusable MongoDB utility script in `backend/utils/mongodb_pull/` that provides functions to fetch users data and messages data.

**File:** `backend/utils/mongodb_pull/mongodb_utils.py`

**Functions to Implement:**

```python
#!/usr/bin/env python3
"""
MongoDB Utility Functions for Campaign Scripts

Provides reusable functions to fetch and enrich user and message data
from MongoDB for campaign scripts.
"""

import os
import sys
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import existing MongoDBPull class
from .mongodb_pull import MongoDBPull


class MongoDBUtils:
    """
    Utility class for fetching campaign-ready data from MongoDB.
    """

    def __init__(self, logger: logging.Logger = None):
        """Initialize MongoDB connection."""
        self.logger = logger or logging.getLogger('MongoDBUtils')
        self.mongodb_pull = MongoDBPull(logger=self.logger)

    def get_users_data(self,
                      campaign_type: str = None,
                      limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch enriched users data from MongoDB.

        Args:
            campaign_type: Filter users by campaign qualification
                          ('fill_the_table', 'return_to_table', 'seat_newcomers')
            limit: Maximum number of users to return

        Returns:
            List of enriched user dictionaries with all campaign fields
        """
        self.logger.info(f"Fetching users data (campaign_type={campaign_type}, limit={limit})")

        # Get fully enriched users from mongodb_pull
        all_users = self.mongodb_pull.users_pull(generate_report=False)
        self.logger.info(f"Retrieved {len(all_users)} total users from MongoDB")

        # Filter by campaign type if specified
        if campaign_type:
            qualification_field = f'qualifies_{campaign_type}'
            filtered_users = [
                user for user in all_users
                if user.get('campaign_qualifications', {}).get(qualification_field, False)
            ]
            self.logger.info(f"Filtered to {len(filtered_users)} users for {campaign_type}")
        else:
            filtered_users = all_users

        # Apply limit if specified
        if limit:
            filtered_users = filtered_users[:limit]
            self.logger.info(f"Limited to {len(filtered_users)} users")

        return filtered_users

    def get_events_data(self,
                       campaign_type: str = None,
                       limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch enriched events data from MongoDB.

        Args:
            campaign_type: Filter events by campaign qualification
                          ('fill_the_table', 'return_to_table', 'seat_newcomers')
            limit: Maximum number of events to return

        Returns:
            List of enriched event dictionaries with all campaign fields
        """
        self.logger.info(f"Fetching events data (campaign_type={campaign_type}, limit={limit})")

        # Get fully enriched events from mongodb_pull
        all_events = self.mongodb_pull.events_pull(generate_report=False)
        self.logger.info(f"Retrieved {len(all_events)} total events from MongoDB")

        # Filter by campaign type if specified
        if campaign_type:
            qualification_field = f'qualifies_{campaign_type}'
            filtered_events = [
                event for event in all_events
                if event.get('campaign_qualifications', {}).get(qualification_field, False)
            ]
            self.logger.info(f"Filtered to {len(filtered_events)} events for {campaign_type}")
        else:
            filtered_events = all_events

        # Apply limit if specified
        if limit:
            filtered_events = filtered_events[:limit]
            self.logger.info(f"Limited to {len(filtered_events)} events")

        return filtered_events

    def get_messages_data(self,
                         campaign: str = None,
                         status: str = None,
                         limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch messages data from MongoDB.

        Args:
            campaign: Filter by campaign name ('fill-the-table', 'return-to-table', 'seat-newcomers')
            status: Filter by message status ('pending', 'sent', 'failed')
            limit: Maximum number of messages to return

        Returns:
            List of message dictionaries
        """
        self.logger.info(f"Fetching messages (campaign={campaign}, status={status}, limit={limit})")

        # Build query filter
        query_filter = {}
        if campaign:
            query_filter['campaign'] = campaign
        if status:
            query_filter['status'] = status

        # Fetch from MongoDB messages collection
        db = self.mongodb_pull.connection.get_database()
        messages_collection = db['message']

        # Query messages
        cursor = messages_collection.find(query_filter)
        if limit:
            cursor = cursor.limit(limit)

        messages = list(cursor)
        self.logger.info(f"Retrieved {len(messages)} messages from MongoDB")

        # Convert ObjectId to string for JSON serialization
        for msg in messages:
            if '_id' in msg:
                msg['id'] = str(msg['_id'])

        return messages

    def close(self):
        """Close MongoDB connection."""
        self.mongodb_pull.close()
        self.logger.info("MongoDB connection closed")
```

**Usage Example:**
```python
from utils.mongodb_pull.mongodb_utils import MongoDBUtils

# Initialize
mongo_utils = MongoDBUtils(logger=logger)

# Get users for specific campaign
users = mongo_utils.get_users_data(
    campaign_type='fill_the_table',
    limit=50
)

# Get events for specific campaign
events = mongo_utils.get_events_data(
    campaign_type='fill_the_table'
)

# Get existing messages
messages = mongo_utils.get_messages_data(
    campaign='fill-the-table',
    status='pending'
)

# Close when done
mongo_utils.close()
```

**Instructions:**
1. Create `mongodb_utils.py` in `backend/utils/mongodb_pull/`
2. Implement the three main functions: `get_users_data()`, `get_events_data()`, `get_messages_data()`
3. Add comprehensive error handling and logging
4. Test with each campaign type
5. Add logging for:
   - Connection establishment
   - Query parameters
   - Number of records fetched
   - Filter results
   - Any errors encountered

---

## Campaign Prompts

### Fill The Table Campaign

#### Matching Prompt
```
You are an expert event marketer focused on filling underbooked events.

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

Return only the JSON array, no additional text.
```

#### Message Generation Prompt
```
You are an expert SMS copywriter specializing in high-conversion, personalized messages for a social dining app.

GOAL: Drive RSVPs and attendance (fill underbooked events). Motivate immediate action.

SMS BEST PRACTICES:
1) LENGTH: <180 chars total (including link). Be concise.
2) TONE: Friendly, concise, 0–2 relevant emojis.
3) STRUCTURE: [Greeting + Name] [Hook tied to interests/occupation/location] [Spots left + time urgency + social proof] [CTA + link at end].
4) SCARCITY: Make spots left/time explicit; small-group feel when true.
5) SOCIAL PROOF: Mention participants already in if available.
6) PROXIMITY: Call out neighborhood convenience explicitly.
7) CTA: Tie directly to link ("Tap to RSVP: {event_link}"); link must be last.
8) PERSONALIZATION: Adjust tone for age/gender/role; if engagement_status is dormant/churned or days_inactive > 30, add a warm welcome-back/reunion vibe and nod to time away. If active, keep momentum.
9) AVOID: ALL CAPS, multiple questions, generic hype, long sentences, excessive punctuation.

EXAMPLES (with links):
- "Hey Sarah! 🍜 Ramen night Thu 7:30p near Midtown, 4 spots left—cozy group, Japanese flavors you love. Tap to RSVP: https://cucu.li/bookings/12345"
- "Hi Mike! Comedy + dinner near West Village tomorrow, only 3 seats—friends already in. Tap to RSVP: https://cucu.li/bookings/12345"
- "Hi Priya! Mexican supper near SoMa, 2 spots left; walkable from you. Tap to RSVP: https://cucu.li/bookings/12345"

Match context:
{match_summary}

Return a JSON object:
- message_text (must end with {event_link})
- personalization_notes
- character_count
```

---

### Return To Table Campaign

#### Matching Prompt
```
You are an expert user reactivation specialist focused on re-engaging dormant users.

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

Return only the JSON object, no additional text.
```

#### Message Generation Prompt
```
You are an expert SMS copywriter specializing in user reactivation for a social dining app.

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
{match_summary}

Return a JSON object:
- message_text (must end with {event_link})
- personalization_notes
- character_count
```

---

### Seat Newcomers Campaign

#### Matching Prompt
```
You are an expert user onboarding specialist focused on converting new users to their first event attendance.

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

Return only the JSON object, no additional text.
```

#### Message Generation Prompt
```
You are an expert SMS copywriter specializing in converting new users to their first event attendance.

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
{match_summary}

Return a JSON object:
- message_text (must end with {event_link})
- personalization_notes
- character_count
```

---

## Logging Requirements

### Comprehensive Logging Throughout

**All scripts must include comprehensive logging at INFO and DEBUG levels:**

#### INFO Level Logging:
- Script initialization and configuration
- Data fetching operations (users, events, messages)
- Number of records retrieved
- Campaign qualification filtering results
- Matching operations start/completion
- Each match created (user → event)
- Message generation for each user
- Airtable/Firebase save operations
- Summary statistics (matches created, messages generated, errors)
- Campaign completion status

#### DEBUG Level Logging:
- Detailed MongoDB query parameters
- Field mapping operations
- API request/response details
- Data transformation steps
- Cache hits/misses
- Validation checks

#### Example Logging Pattern:
```python
# Start of operation
self.logger.info("=" * 80)
self.logger.info(f"Starting {self.campaign_name} Campaign: {self.campaign_id}")
self.logger.info("=" * 80)

# Data operations
self.logger.info(f"Fetching users for {self.campaign_name}...")
users = self.get_users()
self.logger.info(f"✓ Retrieved {len(users)} qualified users")
self.logger.debug(f"User IDs: {[u.get('id') for u in users[:5]]}")

# Processing
for idx, user in enumerate(users, 1):
    self.logger.info(f"Processing user {idx}/{len(users)}: {user.get('firstName')} {user.get('lastName')}")
    # ... processing ...

# Results
self.logger.info(f"✓ Created {len(matches)} matches")
self.logger.info(f"✓ Generated {len(messages)} messages")

# Errors
if errors:
    self.logger.error(f"✗ Encountered {len(errors)} errors:")
    for error in errors:
        self.logger.error(f"  - {error}")

# Completion
self.logger.info("=" * 80)
self.logger.info("CAMPAIGN COMPLETED SUCCESSFULLY")
self.logger.info("=" * 80)
```

---

## Implementation Checklist

### For Each Script (fill_the_table.py, return_to_table.py, seat_newcomers.py):

- [ ] Copy script from `backend/scripts/<script-name>/` to `backend/run/campaigns_run/`
- [ ] Update import paths (Task 1)
  - [ ] Update path calculation for new location
  - [ ] Change `from helpers.` to `from utils.`
  - [ ] Test all imports resolve correctly
- [ ] Update Firebase to Leo2 (Task 2)
  - [ ] Update firebase_manager.py or .env
  - [ ] Test Firebase connectivity
- [ ] Replace Firebase message saves with Airtable (Task 3)
  - [ ] Import AirtableSync class
  - [ ] Replace firebase_manager.save_message() calls
  - [ ] Add error handling for Airtable operations
- [ ] Create main() function (Task 4)
  - [ ] Accept users_data, events_data, prompts as parameters
  - [ ] Return messages array
  - [ ] Make constructor accept optional pre-loaded data
- [ ] Add comprehensive logging (Throughout)
  - [ ] INFO level for major operations
  - [ ] DEBUG level for detailed operations
  - [ ] Error logging with full context
  - [ ] Summary statistics logging
- [ ] Test script independently
- [ ] Test script via orchestrator

### Additional Tasks:

- [ ] Create `mongodb_utils.py` in `backend/utils/mongodb_pull/` (Task 5)
  - [ ] Implement get_users_data()
  - [ ] Implement get_events_data()
  - [ ] Implement get_messages_data()
  - [ ] Add comprehensive logging
  - [ ] Test with each campaign type

- [ ] Create orchestrator script `run_campaigns.py` in `backend/run/campaigns_run/`
  - [ ] Import all three campaign scripts
  - [ ] Use mongodb_utils to fetch data once
  - [ ] Call each campaign's main() function
  - [ ] Collect and combine results
  - [ ] Generate combined report

---

## Testing Plan

### Unit Testing:
1. Test import paths resolve correctly
2. Test MongoDB data fetching
3. Test Airtable connection and message saving
4. Test main() functions with sample data
5. Test logging outputs

### Integration Testing:
1. Run each campaign script independently
2. Verify messages saved to Airtable
3. Verify Leo2 Firebase updates
4. Check log files for completeness
5. Validate message format and content

### End-to-End Testing:
1. Run orchestrator script with all three campaigns
2. Verify all campaigns complete successfully
3. Check Airtable for all messages
4. Review combined reports
5. Monitor for errors and edge cases

---

## Environment Variables Required

```bash
# MongoDB
MONGODB_URI=mongodb+srv://...

# Firebase
FIREBASE_DATABASE_URL=https://cuculi-2c473.firebaseio.com
FIREBASE_BASE_PATH=Leo2

# Airtable
AIRTABLE_API_KEY=patdMoOPya9xAXGLG...
AIRTABLE_BASE_ID=appaquqFN7vvvZGcq

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Optional
SAVE_LOCAL=false
LOG_LEVEL=INFO
```

---

## Next Steps

1. Review this README thoroughly
2. Begin with Task 1 (Update import paths) for one script
3. Test thoroughly before proceeding to next task
4. Complete all tasks for one script before moving to next
5. Create orchestrator script last
6. Run end-to-end testing
7. Deploy to production

---

## Notes

- Always maintain backward compatibility where possible
- Keep original scripts in `backend/scripts/` as backup
- Test each change incrementally
- Document any deviations from this plan
- Add comprehensive logging at every step
- Handle errors gracefully and log with full context

---

*Last Updated: 2025-12-16*
