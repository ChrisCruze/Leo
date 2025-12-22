# V2 Pipeline - Messaging Campaign Automation System

## Overview

The V2 Pipeline is a comprehensive 5-step automated messaging campaign system that filters qualified users and events, enriches their profiles with calculated metrics and AI-generated summaries, matches users to ideal events using Claude AI, and generates personalized SMS messages optimized for conversion.

### Key Features

- **Automated User Qualification**: Filters users based on profile completeness and message history
- **Event Selection**: Identifies future, public events with available capacity
- **Profile Enrichment**: Calculates metrics, identifies social connections, and generates comprehensive summaries
- **AI-Powered Matching**: Uses Claude AI to match users to ideal events based on interests, location, and campaign strategy
- **Personalized Message Generation**: Creates witty, engaging SMS messages tailored to user profiles and campaign types
- **Quality Assurance**: Automated quality checking ensures messages meet SMS best practices and Twilio compliance
- **Airtable Integration**: Automatically uploads generated messages to Airtable for campaign management

## Pipeline Architecture

The pipeline consists of 5 sequential steps, each building upon the previous step's output:

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: User Selection                                          │
│ Input: users.json, messages.json                                │
│ Output: qualified_users.json                                    │
│ Filters: Message history, required profile fields              │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│ Step 2: Event Selection                                          │
│ Input: events.json                                               │
│ Output: qualified_events.json                                    │
│ Filters: Future dates, public type, active status, capacity    │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│ Step 3: User Profile Enrichment                                │
│ Input: qualified_users.json, events.json, users.json          │
│ Output: enriched_users.json                                     │
│ Enriches: Metrics, event history, friends, summaries          │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│ Step 4: Event Profile Enrichment                                │
│ Input: qualified_events.json, users.json                        │
│ Output: enriched_events.json                                     │
│ Enriches: Participant demographics, host info, summaries      │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│ Step 5: User-Event Matching & Message Generation               │
│ Input: enriched_users.json, enriched_events.json                │
│ Output: processed_messages.json, Airtable records               │
│ Process: AI matching, message generation, quality check, upload   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Raw Data** (`data/raw/`): Initial data from MongoDB
   - `users.json`: All user records
   - `events.json`: All event records
   - `messages.json`: Previously sent messages

2. **Processed Data** (`data/processed/`): Intermediate outputs
   - `qualified_users.json`: Filtered users ready for enrichment
   - `qualified_events.json`: Filtered events ready for enrichment
   - `enriched_users.json`: Users with calculated metrics and summaries
   - `enriched_events.json`: Events with participant insights and summaries
   - `processed_messages.json`: Final generated messages

3. **Logs** (`logs/`): Execution logs for each pipeline step

## Pipeline Steps

### Step 1: User Selection (`step1_user_selection.py`)

**Purpose**: Filter qualified users for messaging campaigns by removing users who have already received messages and users missing required profile fields.

**Input Files**:
- `data/raw/users.json`: All user records from MongoDB
- `data/raw/messages.json`: Previously sent messages

**Output Files**:
- `data/processed/qualified_users.json`: Filtered list of qualified users

**Key Functions**:
- `load_users()`: Loads user data from JSON file
- `load_messages()`: Loads message history from JSON file
- `filter_users_by_messages()`: Removes users who have already received messages
- `filter_users_by_profile_fields()`: Validates required profile fields

**Required Profile Fields**:
1. `interests` (array): Non-empty array of interest strings
2. `phone` (string): Non-empty phone number string
3. `email` (string): Non-empty email address string
4. `homeNeighborhood` (string): Non-empty neighborhood string
5. `occupation` (string): Non-empty occupation string
6. `gender` (string): Non-empty gender string
7. `relationshipStatus` (string): Non-empty relationship status string
8. `tableTypePreference` (string): Non-empty table preference string
9. `workNeighborhood` (string): Non-empty work neighborhood string

**Filtering Logic**:
1. **Message Filter**: Users whose `id` or `_id` appears in any message's `user_id` field are excluded to prevent duplicate messaging
2. **Field Validation**: Users missing any of the 9 required fields are excluded as they cannot be effectively personalized

**Statistics Tracked**:
- Total users loaded
- Users filtered by message history
- Users filtered by missing fields (per field)
- Final qualified user count

**Detailed Documentation**: See [`docs/1-user-selection.md`](docs/1-user-selection.md)

---

### Step 2: Event Selection (`step2_event_selection.py`)

**Purpose**: Filter qualified events for promotion by identifying future, public events with available capacity.

**Input Files**:
- `data/raw/events.json`: All event records from MongoDB

**Output Files**:
- `data/processed/qualified_events.json`: Filtered list of qualified events

**Key Functions**:
- `load_events()`: Loads event data from JSON file
- `parse_iso_date()`: Parses ISO 8601 date strings with 'Z' timezone
- `filter_future_events()`: Keeps only events with `startDate` in the future
- `filter_public_events()`: Keeps only events where `type == "public"`
- `filter_active_events()`: Removes events where `eventStatus == "canceled"`
- `filter_events_with_capacity()`: Keeps only events where `len(participants) < maxParticipants`

**Filtering Criteria**:
1. **Future Events**: `startDate` must be after current date/time (UTC)
2. **Public Events**: `type` must equal `"public"` (not `"private"`)
3. **Active Events**: `eventStatus` must not be `"canceled"`
4. **Available Capacity**: `len(participants) < maxParticipants`

**Date Parsing**:
- Handles ISO 8601 format: `"2019-08-05T17:00:00.000Z"`
- Converts 'Z' timezone to `+00:00` for Python `datetime.fromisoformat()` compatibility
- Filters out events with missing or invalid `startDate` values

**Statistics Tracked**:
- Total events loaded
- Past events filtered out
- Private events filtered out
- Canceled events filtered out
- Full events filtered out
- Final qualified event count

**Detailed Documentation**: See [`docs/2-event-selection.md`](docs/2-event-selection.md)

---

### Step 3: User Profile Enrichment (`step3_user_profile_enrich.py`)

**Purpose**: Transform qualified users into enriched profiles with calculated metrics, event associations, social connections, and comprehensive summaries for personalized messaging.

**Input Files**:
- `data/processed/qualified_users.json`: Filtered users from Step 1
- `data/raw/events.json`: All events for event history lookup
- `data/raw/users.json`: All users for host and friend lookup
- `data/processed/qualified_events.json`: Qualified events for invited events lookup

**Output Files**:
- `data/processed/enriched_users.json`: Enriched user profiles with calculated fields

**Key Functions**:
- `load_qualified_users()`: Loads qualified users
- `load_all_events()`: Loads all events for event history
- `load_all_users()`: Loads all users for lookup dictionaries
- `load_qualified_events()`: Loads qualified events for invited events
- `calculate_age()`: Calculates age from `birthDay` ISO 8601 date string
- `associate_user_events()`: Matches user email to event participants
- `extract_event_hosts()`: Looks up `ownerId` in users dictionary to get host names
- `identify_friends()`: Finds users who share 2+ events with target user
- `generate_user_summary()`: Creates human-readable summary sentence

**Enriched User Schema**:

**Core Identity Fields**:
- `id` (string): User identifier
- `name` (string): Full name (`firstName + " " + lastName`)
- `email` (string): Email address

**Profile Fields**:
- `interests` (array): User interests
- `cuisine_preferences` (array): Preferred cuisines (from `preferredCuisines`)
- `dietary_restrictions` (array): Dietary restrictions (from `allergies`)
- `table_type_preference` (string): Table preference
- `relationship_status` (string): Relationship status
- `occupation` (string): Occupation
- `gender` (string): Gender
- `homeNeighborhood` (string): Home neighborhood
- `workNeighborhood` (string): Work neighborhood

**Calculated Fields**:
- `age` (number|null): Age calculated from `birthDay`
- `event_count` (number): Number of events user has attended
- `last_event_date` (string|null): Most recent event `startDate` (ISO 8601)
- `days_since_last_event` (number|null): Days since last attended event
- `days_since_signup` (number|null): Days since account creation
- `historical_event_names` (array): List of event names user attended
- `event_hosts` (array): Unique host names from events user attended
- `invited_event_names` (array): Event names from `qualified_events.json` where user is in `invitedParticipants`
- `friends` (array): Friend names with shared event count, format: `"Name (count)"`

**Status Fields (Boolean)**:
- `is_new_user` (boolean): `true` if `days_since_signup <= 30`
- `has_never_attended_events` (boolean): `true` if `event_count == 0`
- `hasnt_attended_in_60_days` (boolean|null): `true` if `days_since_last_event > 60`
- `signed_up_online` (boolean): `true` if `role == "POTENTIAL"`
- `recently_attended_last_week` (boolean|null): `true` if `days_since_last_event <= 7`

**Status Fields (Categorical)**:
- `primary_status` (string): One of `"new_user"`, `"never_attended"`, `"dormant_60_days"`, `"active_recent"`, `"signed_up_online"`, `"active_regular"`
- `engagement_tier` (string): One of `"high"`, `"medium"`, `"low"`
- `user_segment` (string): One of `"new_online_signup"`, `"new_app_user"`, `"first_timer"`, `"active_regular"`, `"dormant"`, `"churned"`

**Summary Field**:
- `summary` (string): Human-readable summary sentence including name, age, gender, occupation, neighborhoods, join date, interests, cuisine preferences, dietary restrictions, table preference, event history, engagement status, preferred hosts, and invited events

**Event Association Logic**:
- Events are matched to users by email: user's `email` must appear in event's `participants` array
- Events are sorted by `startDate` descending (most recent first)

**Friends Identification**:
- Identifies other participants who share 2+ events with user
- Counts shared events and formats as `"Name (count)"`
- Sorted by frequency (most shared events first)

**Detailed Documentation**: See [`docs/3-user-profile.md`](docs/3-user-profile.md)

---

### Step 4: Event Profile Enrichment (`step4_event_enrich.py`)

**Purpose**: Transform qualified events into enriched profiles with participant insights, host information, low occupancy detection, and comprehensive summaries for personalized messaging.

**Input Files**:
- `data/processed/qualified_events.json`: Filtered events from Step 2
- `data/raw/users.json`: All users for participant lookup

**Output Files**:
- `data/processed/enriched_events.json`: Enriched event profiles with calculated fields

**Key Functions**:
- `load_qualified_events()`: Loads qualified events
- `load_all_users()`: Loads all users for participant lookup
- `parse_iso_date()`: Parses ISO 8601 date strings
- `clean_html()`: Removes HTML tags from descriptions using regex
- `get_day_of_week()`: Extracts day name from `startDate`
- `extract_host_name()`: Looks up `ownerId` in users dictionary
- `calculate_common_occupations()`: Counts occupation frequencies from participants
- `calculate_common_interests()`: Counts interest frequencies from participants
- `calculate_average_age()`: Calculates average age from participant `birthDay` fields
- `detect_low_occupancy()`: Determines if event has low occupancy (<30% or <3 participants with max >=10)
- `extract_participant_names()`: Formats participant names with occupations
- `generate_event_summary()`: Creates human-readable summary sentence

**Enriched Event Schema**:

**Core Identity Fields**:
- `id` (string): Event identifier
- `name` (string): Event name

**Date & Time Fields**:
- `startDate` (string): Event start date/time (ISO 8601)
- `endDate` (string): Event end date/time (ISO 8601)
- `day_of_week` (string): Day name extracted from `startDate` (e.g., `"Friday"`)

**Venue Fields**:
- `venueName` (string): Venue name
- `neighborhood` (string): Event neighborhood location

**Event Details Fields**:
- `categories` (array): Event categories
- `features` (array): Event features
- `maxParticipants` (number): Maximum participants allowed
- `participant_count` (number): Current participant count (`len(participants)`)
- `description` (string): Event description with HTML tags removed

**Calculated Fields**:
- `host_name` (string|null): Full name of event host (from `ownerId` lookup)
- `common_occupations` (array): Top 3-5 most common occupations among participants
- `common_interests` (array): Top 3-5 most common interests among participants
- `average_age` (number|null): Average age of participants (rounded integer)
- `has_low_occupancy` (boolean): `true` if occupancy <30% or <3 participants with max >=10
- `participant_names` (array): Participant names with occupations, format: `"FirstName LastName (Occupation)"` or `"FirstName LastName"`

**Summary Field**:
- `summary` (string): Human-readable summary sentence including event name, category, day of week, date/time, venue, neighborhood, host name, participant count vs max capacity, participant names (first 3-5), low occupancy mention if applicable, common occupations, common interests, average age, and cleaned description

**HTML Cleaning Logic**:
- Uses regex pattern `r'<[^>]+>'` to remove HTML tags
- Cleans extra whitespace by splitting and rejoining with single spaces
- Returns empty string if description is missing or null

**Low Occupancy Detection**:
- Calculates occupancy ratio: `participant_count / maxParticipants`
- Low occupancy if:
  - `occupancy_ratio < 0.3` (less than 30% full), OR
  - `participant_count < 3` AND `maxParticipants >= 10`

**Participant Demographics**:
- **Common Occupations**: Extracts `occupation` from each participant user, counts frequencies, returns top 3-5
- **Common Interests**: Extracts `interests` array from each participant user, flattens all interests, counts frequencies, returns top 3-5
- **Average Age**: Extracts `birthDay` from each participant user, calculates age, averages all ages, rounds to integer

**Detailed Documentation**: See [`docs/4-event-profile.md`](docs/4-event-profile.md)

---

### Step 5: User-Event Matching & Message Generation (`step5_match_message.py`)

**Purpose**: Match enriched users to enriched events using Claude AI, generate personalized SMS messages, quality check them, and upload results to Airtable.

**Input Files**:
- `data/processed/enriched_users.json`: Enriched users from Step 3
- `data/processed/enriched_events.json`: Enriched events from Step 4
- `data/raw/users.json`: Raw users for phone number lookup

**Output Files**:
- `data/processed/processed_messages.json`: All generated messages
- Airtable Messages table: Uploaded message records

**Key Functions**:
- `load_enriched_users()`: Loads enriched users
- `load_enriched_events()`: Loads enriched events
- `load_raw_users()`: Loads raw users for phone lookup
- `create_phone_lookup()`: Creates email-to-phone mapping dictionary
- `match_user_to_event()`: Uses Claude AI to match user to ideal event
- `generate_message()`: Uses Claude AI to generate personalized SMS message
- `quality_check_message()`: Uses Claude AI to validate message quality
- `process_user()`: Processes single user through full pipeline
- `main()`: Orchestrates pipeline execution

**Workflow**:
1. Load enriched users and events
2. Create phone lookup dictionary from raw users
3. For each user:
   - Match user to ideal event using Claude AI (determines campaign type)
   - Generate personalized message using Claude AI
   - Quality check message using Claude AI
   - Create message record with all fields
   - Save to `processed_messages.json`
   - Upload to Airtable

**Prompts** (defined at top of script):

1. **Matching Prompt** (`MATCHING_PROMPT`):
   - Analyzes user summary and all event summaries
   - Determines campaign type based on user profile
   - Prioritizes interest alignment as most critical factor
   - Returns JSON with `event_index`, `campaign`, `reasoning`, `confidence`

2. **Message Generation Prompt** (`MESSAGE_GENERATION_PROMPT`):
   - Generates funny, witty, interesting SMS message
   - Adapts tone based on campaign type
   - Follows SMS best practices (length, structure, CTA)
   - Complies with Twilio rules (banned words, emoji limits)
   - Returns JSON with `message`, `reasoning`, `confidence`

3. **Quality Check Prompt** (`QUALITY_CHECK_PROMPT`):
   - Validates message length (<180 chars including link)
   - Checks tone matches campaign type and best practices
   - Verifies accuracy of all details
   - Ensures proper personalization and clarity
   - Validates Twilio compliance
   - Returns JSON with `quality_score`, `approved`, `issues`, `improved_message`

**Campaign Types**:

1. **"Seat The Newcomer"**:
   - **When**: User has `event_count <= 2`
   - **Objective**: Convert newcomers to their first event attendance
   - **Event Selection**: Prefer events with 50-80% filled (shows quality without being exclusive), beginner-friendly, in user's neighborhood
   - **Message Tone**: Warm, welcoming, encouraging, exciting about first event

2. **"Fill the Table"**:
   - **When**: Event has `has_low_occupancy = true`
   - **Objective**: Drive RSVPs to fill underbooked events
   - **Event Selection**: Low-occupancy events, events starting soon (creates urgency), interest alignment still critical
   - **Message Tone**: Urgent, scarcity-driven, emphasizes spots left and time urgency, uses social proof

3. **"Return to Table"**:
   - **When**: User has `days_since_last_event >= 31` OR `hasnt_attended_in_60_days = true`
   - **Objective**: Re-engage dormant users and drive RSVPs
   - **Event Selection**: Prefer events with 50-100% filled (shows quality), similar to user's past attendance patterns, in user's neighborhood, happening soon
   - **Message Tone**: Warm, welcoming, nostalgic, friend-like, acknowledges time away without being pushy

**Matching Logic**:
Claude AI determines ideal event match using criteria (in order of importance):
1. **Interest Alignment** (Critical): User interests must align with event categories/features
2. **Dietary Compatibility**: Event cuisine must not conflict with user dietary restrictions
3. **Location Proximity**: Prefer events in or near user's neighborhood
4. **Event Quality**: For "Return to Table" and "Seat The Newcomer", prefer events with good participation (50-80% filled)
5. **Event Urgency**: For "Fill the Table", prioritize events with low occupancy
6. **Event Timing**: Prefer events happening soon

**Message Generation**:
- Uses user summary, event summary, campaign context, and match reasoning
- Temperature: 0.9 (more creative for witty messages)
- Appends event link: `https://cucu.li/bookings/{event_id}`
- Message structure: [Greeting + Name] [Hook] [Event details + urgency + social proof] [CTA]

**Quality Check**:
- Validates length, tone, accuracy, personalization, clarity, CTA, Twilio compliance, engagement
- Temperature: 0.7 (more analytical)
- Uses improved message if provided and original wasn't approved

**Airtable Integration**:
- Uses `utils.airtable_crud.create_message_record()` to upload messages
- Field mapping handled by `MESSAGES_FIELD_MAPPING` dictionary
- Records include: user info, event info, message text, reasoning, confidence, campaign, quality check response

**Message Record Schema**:
- `user_name`, `event_name`, `user_id`, `event_id`
- `user_email`, `user_phone`
- `user_summary`, `event_summary`
- `message`: Generated SMS message text (with link appended)
- `match_reasoning`: Why this match was made
- `message_reasoning`: Why this message will work
- `confidence_percentage`: Confidence score (0-100)
- `campaign`: Campaign type
- `quality_check_response`: Quality check result

**Detailed Documentation**: See [`docs/5-match-message.md`](docs/5-match-message.md)

---

## Utility Modules

### `utils/ai_prompt.py`

Provides reusable functions for interfacing with Claude AI API.

**Functions**:

- **`call_claude(prompt, model, temperature, max_tokens, logger)`**:
  - Calls Claude AI API and returns raw response text
  - Default model: `"claude-sonnet-4-20250514"`
  - Default temperature: `0.7`
  - Default max_tokens: `4096`
  - Logs prompts and responses if logger provided
  - Raises `ValueError` if `ANTHROPIC_API_KEY` not found

- **`parse_json_response(response_text, logger)`**:
  - Parses JSON from Claude response text with multiple fallback strategies
  - Handles JSON objects and arrays
  - Uses regex patterns and balanced brace/bracket matching
  - Returns parsed JSON object (dict or list)
  - Raises `json.JSONDecodeError` if no valid JSON found

- **`generate_with_quality_check(initial_prompt, quality_check_prompt, model, temperature, max_tokens, logger)`**:
  - Generates content and runs quality check on the result
  - Uses `{initial_response}` placeholder in quality check prompt
  - Returns dictionary with `initial_response`, `quality_check_response`, `iterations`

**Environment Requirements**:
- `ANTHROPIC_API_KEY`: Must be set in `.env` file at root or as environment variable
- `python-dotenv`: Optional but recommended for `.env` file support

**Usage Example**:
```python
from utils.ai_prompt import call_claude, parse_json_response

response_text = call_claude("Return JSON: {'test': 123}")
parsed = parse_json_response(response_text)
```

---

### `utils/airtable_crud.py`

Provides reusable functions for Airtable CRUD operations on the Messages table.

**Functions**:

- **`init_airtable_client()`**:
  - Initializes Airtable API client
  - Returns tuple of `(api, base, messages_table)`

- **`create_message_record(message_record, logger)`**:
  - Creates a message record in Airtable Messages table
  - Maps fields using `MESSAGES_FIELD_MAPPING`
  - Returns tuple of `(success: bool, record_id: Optional[str])`

- **`get_message_record(record_id, logger)`**:
  - Gets a message record from Airtable by ID
  - Returns record dictionary if found, `None` otherwise

- **`update_message_record(record_id, fields, logger)`**:
  - Updates a message record in Airtable
  - Fields dictionary uses Airtable field names
  - Returns `True` if successful, `False` otherwise

- **`delete_message_record(record_id, logger)`**:
  - Deletes a message record from Airtable
  - Returns `True` if successful, `False` otherwise

**Configuration**:
- `AIRTABLE_API_KEY`: Hardcoded in module (should be moved to environment variable in production)
- `BASE_ID`: Airtable base ID
- `MESSAGES_TABLE_ID`: Messages table ID
- `MESSAGES_FIELD_MAPPING`: Maps local field names to Airtable field names

**Field Mapping**:
- Maps fields like `user_name`, `event_name`, `user_id`, `event_id`, `user_email`, `user_phone`
- Maps `user_summary`, `event_summary`, `message`, `reasoning`, `confidence_percentage`, `campaign`
- Handles multiple field name variations (e.g., `message_reasoning`, `match_reasoning` → `reasoning`)

**Usage Example**:
```python
from utils.airtable_crud import create_message_record

message_record = {
    'user_name': 'John Doe',
    'event_name': 'Test Event',
    'message': 'Hi John! Join us for Test Event!',
    'campaign': 'Fill the Table'
}

success, record_id = create_message_record(message_record, logger=logger)
```

---

## Data Schemas

### Input Schemas

#### `users.json` (MongoDB User Schema)
- `_id` (string): MongoDB ObjectId
- `id` (string): User identifier
- `firstName`, `lastName` (string): User name
- `email` (string): Email address
- `phone` (string): Phone number (format: "+1...")
- `interests` (array): Array of interest strings
- `homeNeighborhood`, `workNeighborhood` (string): Neighborhood locations
- `occupation` (string): Occupation
- `gender` (string): Gender
- `relationshipStatus` (string): Relationship status
- `tableTypePreference` (string): Table preference
- `birthDay` (string): ISO 8601 date string
- `createdAt` (string): ISO 8601 date string
- `role` (string): User role ("POTENTIAL", "REGULAR", "ADMIN", etc.)
- `preferredCuisines` (array, optional): Preferred cuisines
- `allergies` (array, optional): Dietary restrictions

#### `events.json` (MongoDB Event Schema)
- `_id` (string): MongoDB ObjectId
- `id` (string): Event identifier
- `name` (string): Event name
- `startDate`, `endDate` (string): ISO 8601 date strings with 'Z' timezone
- `type` (string): Event type ("public" or "private")
- `eventStatus` (string): Event status ("approved", "canceled", "pending")
- `maxParticipants`, `minParticipants` (number): Participant limits
- `participants` (array): List of participant email addresses
- `ownerId` (string): Event owner/creator user ID
- `venueName` (string): Venue name
- `neighborhood` (string): Event neighborhood
- `categories` (array, optional): Event categories
- `features` (array, optional): Event features
- `description` (string, optional): Event description (may contain HTML)
- `invitedParticipants` (array, optional): List of invited participant emails

#### `messages.json` (Message History Schema)
- `user_id` (string): User identifier
- `user_name`, `user_email`, `user_phone` (string): User contact info
- `event_id`, `event_name`, `event_date` (string): Event info
- `message` (string): Generated SMS message text
- `campaign` (string): Campaign type
- `airtable_id` (string, optional): Airtable record ID

### Output Schemas

#### `qualified_users.json`
Array of user objects matching the input `users.json` schema, filtered to only include users who:
- Have not received messages (not in `messages.json`)
- Have all 9 required profile fields filled

#### `qualified_events.json`
Array of event objects matching the input `events.json` schema, filtered to only include events that:
- Have `startDate` in the future
- Have `type == "public"`
- Have `eventStatus != "canceled"`
- Have `len(participants) < maxParticipants`

#### `enriched_users.json`
Array of enriched user objects with additional calculated fields (see Step 3 documentation for full schema).

#### `enriched_events.json`
Array of enriched event objects with additional calculated fields (see Step 4 documentation for full schema).

#### `processed_messages.json`
Array of message record objects:
- `user_name`, `event_name`, `user_id`, `event_id`
- `user_email`, `user_phone`
- `user_summary`, `event_summary`
- `message`: Generated SMS message text (with link appended)
- `match_reasoning`: Why this match was made
- `message_reasoning`: Why this message will work
- `confidence_percentage`: Confidence score (0-100)
- `campaign`: Campaign type
- `quality_check_response`: Quality check result dictionary

---

## Setup & Execution

### Environment Variables

Create a `.env` file at the root of the `v2/` directory (or set as environment variables):

```bash
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

**Note**: `AIRTABLE_API_KEY`, `BASE_ID`, and `MESSAGES_TABLE_ID` are currently hardcoded in `utils/airtable_crud.py`. In production, these should be moved to environment variables.

### Python Dependencies

Install required packages:

```bash
pip install anthropic pyairtable python-dotenv
```

**Required Packages**:
- `anthropic`: Claude AI API client
- `pyairtable`: Airtable API client
- `python-dotenv`: Environment variable management (optional but recommended)

**Standard Library** (no installation needed):
- `json`, `logging`, `os`, `pathlib`, `datetime`, `typing`, `collections`, `re`

### Directory Structure

```
v2/
├── pipeline/
│   ├── step1_user_selection.py
│   ├── step2_event_selection.py
│   ├── step3_user_profile_enrich.py
│   ├── step4_event_enrich.py
│   └── step5_match_message.py
├── utils/
│   ├── __init__.py
│   ├── ai_prompt.py
│   └── airtable_crud.py
├── docs/
│   ├── 1-user-selection.md
│   ├── 2-event-selection.md
│   ├── 3-user-profile.md
│   ├── 4-event-profile.md
│   └── 5-match-message.md
├── data/
│   ├── raw/
│   │   ├── users.json
│   │   ├── events.json
│   │   └── messages.json
│   └── processed/
│       ├── qualified_users.json
│       ├── qualified_events.json
│       ├── enriched_users.json
│       ├── enriched_events.json
│       └── processed_messages.json
├── logs/
│   └── (log files generated by each step)
└── README.md
```

### Execution Order

Run the pipeline steps in sequential order:

```bash
# Step 1: User Selection
python pipeline/step1_user_selection.py

# Step 2: Event Selection
python pipeline/step2_event_selection.py

# Step 3: User Profile Enrichment
python pipeline/step3_user_profile_enrich.py

# Step 4: Event Profile Enrichment
python pipeline/step4_event_enrich.py

# Step 5: User-Event Matching & Message Generation
python pipeline/step5_match_message.py
```

**Note**: Each step expects the previous step's output files to exist. Ensure you run them in order.

### Logging

Each pipeline step generates detailed log files in the `logs/` directory:
- `user_selection_YYYYMMDD_HHMMSS.log`
- `event_selection_YYYYMMDD_HHMMSS.log`
- `user_profile_enrich_YYYYMMDD_HHMMSS.log`
- `event_enrich_YYYYMMDD_HHMMSS.log`
- `match_message_YYYYMMDD_HHMMSS.log`

Logs include:
- Execution timestamps
- Step-by-step progress
- Statistics and filtering results
- Error messages (if any)
- Claude AI prompts and responses (Step 5)

---

## Campaign Types

The pipeline determines one of three campaign types for each user-event match:

### "Seat The Newcomer"

**Target Users**: Users with `event_count <= 2` (newcomers)

**Objective**: Convert newcomers to their first event attendance

**Event Selection Strategy**:
- Prefer events with 50-80% filled (shows quality without being exclusive)
- Beginner-friendly events with welcoming descriptions
- Events in or near user's neighborhood for convenience

**Message Tone**: Warm, welcoming, encouraging, exciting about first event

**Example Message**:
> "Hey Sarah! 👋 Welcome to the community! We'd love to have you at our Beginner Salsa Lesson on Jan 17th - perfect for first-timers. Join us! https://cucu.li/bookings/..."

---

### "Fill the Table"

**Target Users**: Any user matched to event with `has_low_occupancy = true`

**Objective**: Drive RSVPs to fill underbooked events

**Event Selection Strategy**:
- Events with low participation that need filling
- Events starting soon (creates urgency)
- Interest alignment is still critical

**Message Tone**: Urgent, scarcity-driven, emphasizes spots left and time urgency, uses social proof

**Example Message**:
> "Hi Mike! Only 2 spots left for Holiday Karaoke this Friday - 9 people already in! Your love of live music makes this perfect. Grab your spot: https://cucu.li/bookings/..."

---

### "Return to Table"

**Target Users**: Users with `days_since_last_event >= 31` OR `hasnt_attended_in_60_days = true` (dormant users)

**Objective**: Re-engage dormant users and drive RSVPs

**Event Selection Strategy**:
- Prefer events with 50-100% filled (shows quality)
- Events similar to user's past attendance patterns
- Events in or near user's neighborhood
- Events happening soon (creates urgency for reactivation)

**Message Tone**: Warm, welcoming, nostalgic, friend-like, acknowledges time away without being pushy

**Example Message**:
> "Hey Alex! 👋 It's been a while! We've missed you. There's a cozy dinner on Dec 25th that's right up your alley - 8 spots filled already. Come back and join us! https://cucu.li/bookings/..."

---

## References

### Detailed Documentation

- **[User Selection Documentation](docs/1-user-selection.md)**: Complete details on user filtering logic, required fields, and statistics
- **[Event Selection Documentation](docs/2-event-selection.md)**: Complete details on event filtering criteria and date parsing
- **[User Profile Enrichment Documentation](docs/3-user-profile.md)**: Complete schema, field mappings, and calculation logic
- **[Event Profile Enrichment Documentation](docs/4-event-profile.md)**: Complete schema, participant demographics, and summary generation
- **[Matching & Message Generation Documentation](docs/5-match-message.md)**: Complete workflow, prompts, campaign types, and Airtable integration

### Code Files

- **Pipeline Scripts**: `pipeline/step1_user_selection.py` through `pipeline/step5_match_message.py`
- **Utility Modules**: `utils/ai_prompt.py`, `utils/airtable_crud.py`

### External Resources

- **Claude AI API**: [Anthropic Documentation](https://docs.anthropic.com/)
- **Airtable API**: [Airtable API Documentation](https://airtable.com/api)
- **Twilio SMS**: [Twilio SMS Best Practices](https://www.twilio.com/docs/sms)

---

## Notes

- All pipeline steps are designed to be run independently, but they must be executed in order as each step depends on the previous step's output
- Log files are generated for each execution, making it easy to debug issues or review execution history
- The pipeline is designed to handle missing or invalid data gracefully, logging warnings and continuing execution
- Claude AI prompts can be modified at the top of `step5_match_message.py` to adjust matching logic, message generation, or quality checking criteria
- Airtable credentials are currently hardcoded in `utils/airtable_crud.py` and should be moved to environment variables in production

