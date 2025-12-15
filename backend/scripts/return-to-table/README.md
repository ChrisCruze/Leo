# Return To Table Campaign - Implementation Plan

## Overview

The **Return To Table** campaign is designed to reactivate dormant users who haven't used the app in a while but have their interests filled out. The goal is to identify these users, understand their last event attendance, assess their profile completeness, and match them with perfect future events to drive RSVPs.

## Campaign Goal

**Primary Objective:** Reactivate dormant users by matching them with highly relevant future events based on their interests, location, and past attendance patterns, then send personalized SMS messages to encourage RSVP.

**Success Metrics:**
- Number of dormant users identified
- Number of users with complete profiles (personalization-ready)
- Number of matches created
- Number of messages generated
- RSVP conversion rate (tracked downstream)

## Campaign Flow

### Step 1: Identify and Rank Dormant Users
**Purpose:** Find users who are dormant (haven't been active recently) but have enough profile information to personalize messages, then rank them to identify the top 10 highest-value reactivation targets.

**Criteria:**
- `engagement_status` = "dormant" OR `days_inactive` between 31-90 days
- Must have `interests` array populated (at least 1 interest)
- Must have at least 4 of 8 required profile fields filled:
  - `firstName`, `lastName`, `email`, `phone`, `gender`, `interests`, `occupation`, `homeNeighborhood`
- Must have attended at least 1 event in the past (to understand their preferences)

**Ranking/Scoring System:**
Users should be ranked based on a composite score that prioritizes:
1. **Profile Completeness** (0-40 points): More fields filled = higher score
   - 8 fields filled = 40 points
   - 7 fields filled = 35 points
   - 6 fields filled = 30 points
   - 5 fields filled = 25 points
   - 4 fields filled = 20 points
2. **Dormancy Duration** (0-30 points): Longer dormant = higher priority (but still within 31-90 day window)
   - 90 days inactive = 30 points
   - 75 days inactive = 25 points
   - 60 days inactive = 20 points
   - 45 days inactive = 15 points
   - 31 days inactive = 10 points
3. **Event History** (0-30 points): More events attended = higher value
   - 20+ events = 30 points
   - 15-19 events = 25 points
   - 10-14 events = 20 points
   - 5-9 events = 15 points
   - 1-4 events = 10 points

**Total Score Calculation:**
```python
def calculate_reactivation_score(user: Dict[str, Any]) -> float:
    # Profile completeness (0-40)
    required_fields = ['firstName', 'lastName', 'email', 'phone', 'gender', 'interests', 'occupation', 'homeNeighborhood']
    filled_count = sum(1 for f in required_fields if user.get(f))
    completeness_score = min(40, filled_count * 5)  # 5 points per field, max 40
    
    # Dormancy duration (0-30) - longer = higher priority
    days_inactive = user.get('days_inactive', 0)
    if 31 <= days_inactive <= 90:
        dormancy_score = 10 + ((days_inactive - 31) / 59) * 20  # Linear scale 10-30
    else:
        dormancy_score = 0
    
    # Event history (0-30)
    event_count = user.get('eventCount', 0)
    if event_count >= 20:
        history_score = 30
    elif event_count >= 15:
        history_score = 25
    elif event_count >= 10:
        history_score = 20
    elif event_count >= 5:
        history_score = 15
    elif event_count >= 1:
        history_score = 10
    else:
        history_score = 0
    
    total_score = completeness_score + dormancy_score + history_score
    return total_score
```

**Selection:**
- Calculate reactivation score for all dormant users
- Sort by score (descending)
- Select top 10 users for this campaign run

**MongoDB Query Strategy:**
1. Fetch all users from `user` collection
2. Fetch all events from `event` collection
3. Build user-event map (check `participants` array and `ownerId` field)
4. For each user:
   - Calculate event count (events where user is participant or owner)
   - Find last event date (max `startDate` from user's events)
   - Calculate `days_inactive` = (now - last_event_date).days
   - Derive `engagement_status`:
     - `days_inactive <= 30` → "active"
     - `days_inactive <= 90` → "dormant"
     - `days_inactive > 90` → "churned" (if has events) or "new" (if no events)
   - Check profile completeness (at least 4 of 8 fields)
   - Check if `interests` array exists and has at least 1 item
5. Filter for:
   - `engagement_status` == "dormant"
   - `eventCount` >= 1 (has attended at least one event)
   - `personalization_ready` == True (profile complete enough)
   - `interests` array has at least 1 item

**Output:**
- List of dormant users with enriched attributes:
  - `eventCount`: Total events attended/created
  - `last_event_date`: ISO string of last event startDate
  - `days_inactive`: Days since last event
  - `engagement_status`: "dormant"
  - `personalization_ready`: True
  - `interests`: Array of interests
  - All original user fields

**Data Persistence:**
- Save raw users and events to `data/raw/users.json` and `data/raw/events.json`
- Save processed dormant users to `data/processed/dormant_users.json`

### Step 2: Get Future Events (Prefer Well-Attended Events)
**Purpose:** Identify future public events that can be matched to dormant users. **Unlike fill-the-table, prefer events with MORE participants** to ensure we're reactivating users with high-quality, engaging events.

**Criteria:**
- `startDate` > current_time (future events only)
- `type` == "public" (not private events)
- `active` == True
- `eventStatus` == "approved" (if field exists)
- **Preference for events with higher participation** (to show social proof and quality)

**MongoDB Query:**
```python
now = datetime.now(timezone.utc)
future_events = list(self.events_collection.find({
    "startDate": {"$gt": now},
    "type": "public",
    "active": True
}))
```

**Enrichment:**
- Calculate participation percentage: `(len(participants) / maxParticipants) * 100`
- Add `participantCount`, `participationPercentage`, `remaining_spots`
- Enrich with participant signals (top interests, occupations, neighborhoods) if available
- **Sort by participation percentage (descending)** to prioritize well-attended events

**Event Quality Scoring (for matching):**
- Higher participation = better (shows social proof)
- Events with 50-80% filled are ideal (good attendance, still has spots)
- Events with >80% filled are excellent (high demand, exclusive feel)
- Events with <30% filled are less ideal (but still acceptable if perfect match)

**Output:**
- List of future public events with participation metrics, sorted by participation (descending)

**Data Persistence:**
- Save processed events to `data/processed/future_events.json`

### Step 3: Generate User Summaries
**Purpose:** Create human-readable summaries for AI matching.

**Format:**
```
"{firstName} {lastName} is a {occupation} from {homeNeighborhood} who has attended {eventCount} events. 
Last attended: {last_event_date} ({days_inactive} days ago). 
Interests: {interests}. Engagement: {engagement_status}."
```

**Example:**
```
"Chris Cruz is an AI Specialist from hells-kitchen who has attended 13 events. 
Last attended: 2024-10-15 (65 days ago). 
Interests: travel, reading, music, fashion, clubbing, finance, outdoor. Engagement: dormant."
```

### Step 4: Generate Event Summaries
**Purpose:** Create human-readable summaries for AI matching.

**Format:**
```
"Event: {name} at {venueName} in {neighborhood}. 
Categories: {categories}. Features: {features}. 
Capacity: {maxParticipants}, Participants: {participantCount} ({participationPercentage:.1f}% full). 
Date: {startDate} UTC. {description}"
```

### Step 5: AI-Powered Matching (Individual Prompts Per User)
**Purpose:** Use Claude API to find the PERFECT event for each of the top 10 dormant users. **Each user gets their own individual prompt** to ensure the best possible match.

**Matching Strategy:**
- **One user at a time**: Create a dedicated prompt for each user with all available events
- **Find the single best match**: Return only the top 1 event per user (not multiple matches)
- **Quality over quantity**: Focus on finding the perfect event that will reactivate this specific user

**Matching Criteria (in order of importance):**
1. **Interest Alignment**: User interests match event categories/features (CRITICAL)
2. **Location Proximity**: User `homeNeighborhood` vs event `neighborhood` (high priority)
3. **Event Quality**: Prefer events with higher participation (50-100% filled) for social proof
4. **Reactivation Potential**: Events that align with user's past attendance patterns
5. **Event Timing**: Prefer events happening soon (urgency for reactivation)
6. **Welcome Back Vibe**: Consider events that feel welcoming for returning users

**Individual Prompt Structure (Per User):**
```
You are an expert user reactivation specialist focused on re-engaging dormant users.

PRIORITY: Find the SINGLE BEST event for this dormant user (31-90 days inactive) that will re-engage them and drive an RSVP.

USER CONTEXT:
This user has been dormant for {days_inactive} days. They have attended {event_count} events in the past.
Last event: {last_event_date}
Profile completeness: {profile_completeness}/8 fields filled
Interests: {interests}
Neighborhood: {homeNeighborhood}
Occupation: {occupation}

MATCHING CRITERIA (in order of importance):
1. Interest alignment: User interests MUST match event categories/features (this is critical)
2. Location proximity: Prefer events in or near user's neighborhood ({homeNeighborhood})
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
- 'event_name': The event name
- 'event_id': The event ID
- 'reasoning': Detailed explanation (3-4 sentences) focusing on:
  * Why this specific event will reactivate THIS user
  * How interests align
  * Why the event quality/participation makes it appealing
  * How location/timing work for reactivation
- 'confidence_percentage': Number 0-100 (should be 80+ for a good match)
- 'match_purpose': "reactivate_dormant_user"

Available Events: {json.dumps(event_data, default=str, indent=2)}

Return only the JSON object, no additional text.
```

**Processing:**
- For each of the top 10 users:
  1. Create individual prompt with that user's data + all available events
  2. Call Claude API
  3. Parse response to get single best match
  4. Store match with full user and event objects
  5. Save match incrementally to Firebase

**Output:**
- List of 10 matches (one per user) with:
  - `user_name`, `event_name`, `event_id`
  - `reasoning`, `confidence_percentage`, `match_purpose`
  - Full user and event objects
  - `matched_at`: ISO timestamp

**Firebase Persistence:**
- **Save top 10 users to `/Leo/users`**: 
  - Structure: `{ users: [...], count: 10, updatedAt: "..." }`
  - Each user includes `reactivation_score` field
  - Must be array (not object) for dashboard compatibility
- **Save matched events to `/Leo/events`**:
  - Structure: `{ events: [...], count: 10, updatedAt: "..." }`
  - Only save the 10 events that were matched (one per user)
  - Must be array (not object) for dashboard compatibility
- **Save matches to `/Leo/matches`**:
  - Use PATCH to append (preserve existing matches)
  - Structure: `{ matches: [...], count: N, updatedAt: "..." }`
  - Must be array (not object) for dashboard compatibility

**User Data Structure:**
```json
{
  "name": "Chris Cruz",
  "summary": "Chris Cruz is an AI Specialist...",
  "user_id": "631b60819007c60c89083db9",
  "interests": ["travel", "reading", "music"],
  "neighborhood": "hells-kitchen",
  "occupation": "AI Specialist",
  "event_count": 13,
  "last_event_date": "2024-10-15T00:00:00Z",
  "days_inactive": 65,
  "engagement_status": "dormant",
  "personalization_ready": true,
  "email": "cruzc09@gmail.com"
}
```

**Event Data Structure:**
```json
{
  "name": "Holiday Karaoke",
  "summary": "Event: Holiday Karaoke at...",
  "event_id": "6927d356eb4f0aa02a6d14a2",
  "neighborhood": "midtown-east",
  "categories": ["MUSIC", "BAR"],
  "features": ["karaoke", "groups"],
  "startDate": "2025-12-20T23:30:00.000Z",
  "capacity": 8,
  "participants_count": 3,
  "remaining_spots": 5,
  "fill_rate_percent": 37.5
}
```

**Output:**
- List of match dictionaries with:
  - `user_name`, `event_name`, `reasoning`, `confidence_percentage`, `match_purpose`
  - Full user and event objects attached

**Data Persistence:**
- Save matches to `data/processed/matches.json`
- Save matches incrementally to Firebase at `/Leo/matches` (using PATCH to append)

### Step 6: Generate Personalized Reactivation Messages
**Purpose:** Create SMS messages that welcome dormant users back and encourage RSVP.

**Message Guidelines:**
- **Length**: <180 chars total (including link)
- **Tone**: Warm, welcoming, friend-like (not pushy)
- **Structure**: 
  - [Greeting + Name]
  - [Welcome back hook - acknowledge time away]
  - [Event hook tied to interests/occupation/location]
  - [Spots left + time urgency + social proof]
  - [CTA + link at end]
- **Reactivation Elements**:
  - Acknowledge they haven't been around ("We miss you!", "Welcome back!")
  - Reference their interests explicitly
  - Create urgency with spots/time
  - Include social proof
  - Make it feel personal, not automated
- **Link**: Must end with `https://cuculi.net/events/{event_id}`

**Prompt Structure:**
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
- "Hey Sarah! 👋 We miss you! Ramen night Thu 7:30p near Midtown, 4 spots left—your favorite Japanese flavors. Welcome back! Tap to RSVP: https://cuculi.net/events/12345"
- "Hi Mike! It's been a while! Comedy + dinner near West Village tomorrow, only 3 seats—friends already in. Tap to RSVP: https://cuculi.net/events/12345"
- "Hi Priya! Welcome back! 🎉 Mexican supper near SoMa, 2 spots left; walkable from you. Tap to RSVP: https://cuculi.net/events/12345"

Match context:
{json.dumps(match_summary, default=str, indent=2)}

Return a JSON object:
- message_text (must end with {event_link})
- personalization_notes
- character_count
```

**Output:**
- List of message dictionaries with:
  - `user_name`, `user_email`, `user_phone`, `event_name`, `event_id`
  - `message_text` (with link at end)
  - `personalization_notes`, `character_count`
  - `similarity_score` (from match), `confidence_percentage`, `reasoning`
  - `status`: "pending" (for HITL dashboard review)
  - `generated_at`: ISO timestamp

**Data Persistence:**
- Save messages to `data/processed/messages.json`
- Save messages incrementally to Firebase at `/Leo/messages` (using PATCH to append)

### Step 7: Save Campaign Data to Firebase
**Purpose:** Persist all campaign data to Firebase for dashboard visibility and tracking.

**Firebase Structure:**
```
/Leo/
├── campaigns/
│   └── return-to-table-{timestamp}/
│       ├── metadata/
│       ├── users/
│       ├── events/
│       ├── matches/
│       └── messages/
├── users/          # Dashboard schema: { users: [...], count: 10, updatedAt: "..." } (PUT - top 10 users)
├── events/         # Dashboard schema: { events: [...], count: 10, updatedAt: "..." } (PUT - matched events)
├── matches/        # Dashboard schema: { matches: [...], count: N, updatedAt: "..." } (PATCH - append)
└── messages/      # Dashboard schema: { messages: [...], count: N, updatedAt: "..." } (PATCH - append)
```

**CRITICAL Firebase Schema Requirements (from dashboard.html):**
- All root paths (`/Leo/users`, `/Leo/events`, `/Leo/matches`, `/Leo/messages`) must have:
  - An array field (`users`, `events`, `matches`, `messages`)
  - A `count` field (number of items)
  - An `updatedAt` field (ISO timestamp)
- Arrays must be actual arrays, NOT objects with numeric keys
- Use PUT for users/events (replace), PATCH for matches/messages (append)

**Campaign Metadata:**
```json
{
  "id": "return-to-table-20251212-143022",
  "name": "return-to-table",
  "created_at": "2025-12-12T14:30:22.000Z",
  "stats": {
    "users_processed": 25,
    "events_processed": 15,
    "matches_created": 18,
    "messages_generated": 18,
    "errors": []
  }
}
```

**Users Schema (Dashboard) - MUST MATCH dashboard.html expectations:**
```json
{
  "users": [
    {
      "id": "631b60819007c60c89083db9",
      "_id": "631b60819007c60c89083db9",
      "firstName": "Chris",
      "lastName": "Cruz",
      "name": "Chris Cruz",
      "email": "cruzc09@gmail.com",
      "phone": "+19145890466",
      "interests": ["travel", "reading", "music"],
      "homeNeighborhood": "hells-kitchen",
      "occupation": "AI Specialist",
      "eventCount": 13,
      "event_count": 13,
      "engagement_status": "dormant",
      "days_inactive": 65,
      "last_event_date": "2024-10-15T00:00:00Z",
      "personalization_ready": true,
      "reactivation_score": 85.5,
      "summary": "Chris Cruz is an AI Specialist..."
    }
  ],
  "count": 10,
  "updatedAt": "2025-12-12T14:30:22.000Z"
}
```

**CRITICAL:** The dashboard expects:
- Root path: `/Leo/users`
- Structure: `{ users: [...], count: N, updatedAt: "..." }`
- `users` must be an array (not an object)
- Each user must have both `id` and `_id` fields (same value)
- Must include `eventCount` and `event_count` (for compatibility)

**Events Schema (Dashboard) - MUST MATCH dashboard.html expectations:**
```json
{
  "events": [
    {
      "id": "6927d356eb4f0aa02a6d14a2",
      "_id": "6927d356eb4f0aa02a6d14a2",
      "name": "Holiday Karaoke",
      "startDate": "2025-12-20T23:30:00.000Z",
      "maxParticipants": 8,
      "capacity": 8,
      "participants": ["email1@example.com"],
      "participantCount": 6,
      "participationPercentage": 75.0,
      "neighborhood": "midtown-east",
      "categories": ["MUSIC", "BAR"],
      "features": ["karaoke", "groups"],
      "venueName": "Karaoke Bar",
      "type": "public",
      "summary": "Event: Holiday Karaoke..."
    }
  ],
  "count": 10,
  "updatedAt": "2025-12-12T14:30:22.000Z"
}
```

**CRITICAL:** The dashboard expects:
- Root path: `/Leo/events`
- Structure: `{ events: [...], count: N, updatedAt: "..." }`
- `events` must be an array (not an object)
- Each event must have both `id` and `_id` fields (same value)
- Must include both `maxParticipants` and `capacity` (for compatibility)
- Must include `participantCount` and `participationPercentage`

**Matches Schema (Incremental) - MUST MATCH dashboard.html expectations:**
```json
{
  "matches": [
    {
      "user_name": "Chris Cruz",
      "event_name": "Holiday Karaoke",
      "user_id": "631b60819007c60c89083db9",
      "event_id": "6927d356eb4f0aa02a6d14a2",
      "confidence_percentage": 85,
      "reasoning": "This event is perfect for reactivating Chris...",
      "match_purpose": "reactivate_dormant_user",
      "strategy": "reactivate_dormant_user",
      "matched_at": "2025-12-12T14:30:22.000Z",
      "user": { /* full user object */ },
      "event": { /* full event object */ }
    }
  ],
  "count": 10,
  "updatedAt": "2025-12-12T14:30:22.000Z"
}
```

**CRITICAL:** The dashboard expects:
- Root path: `/Leo/matches`
- Structure: `{ matches: [...], count: N, updatedAt: "..." }`
- `matches` must be an array (not an object)
- Use PATCH to append (don't overwrite existing matches)
- Each match should include full `user` and `event` objects for context

**Messages Schema (Incremental):**
```json
{
  "messages": [
    {
      "user_name": "Chris Cruz",
      "user_email": "cruzc09@gmail.com",
      "user_phone": "+19145890466",
      "event_name": "Holiday Karaoke",
      "event_id": "6927d356eb4f0aa02a6d14a2",
      "message_text": "Hey Chris! 👋 We miss you! Karaoke night Thu 7:30p near Midtown, 4 spots left—your favorite music vibes. Welcome back! Tap to RSVP: https://cuculi.net/events/6927d356eb4f0aa02a6d14a2",
      "personalization_notes": "Acknowledged time away, referenced music interests, included welcome back message",
      "character_count": 178,
      "similarity_score": 85,
      "confidence_percentage": 85,
      "reasoning": "This event is perfect for reactivating Chris...",
      "status": "pending",
      "generated_at": "2025-12-12T14:30:22.000Z"
    }
  ],
  "count": 18,
  "updatedAt": "2025-12-12T14:30:22.000Z"
}
```

### Step 8: Generate Report
**Purpose:** Create comprehensive campaign report with statistics and recommendations.

**Report Structure:**
```json
{
  "campaign_id": "return-to-table-20251212-143022",
  "campaign_name": "return-to-table",
  "run_date": "2025-12-12T14:30:22.000Z",
  "statistics": {
    "users_processed": 25,
    "events_processed": 15,
    "matches_created": 18,
    "messages_generated": 18,
    "errors": []
  },
  "summary": {
    "total_dormant_users_found": 25,
    "total_users_with_complete_profiles": 25,
    "total_future_events": 15,
    "total_matches_created": 18,
    "total_messages_generated": 18,
    "average_days_inactive": 52.3,
    "average_confidence_score": 78.5,
    "error_count": 0
  },
  "errors": []
}
```

**Markdown Report:**
- Save to `reports/return_to_table_report_{campaign_id}.md`
- Include goal, run summary, users processed, events processed, matches, messages, recommendations

**Recommendations:**
- Focus on welcome-back messaging that acknowledges time away
- Prioritize interest alignment for reactivation
- Use urgency (spots left, time) to drive immediate action
- Consider proximity (neighborhood) for convenience
- Track reactivation success rate (RSVPs from dormant users)

## Technical Implementation Details

### MongoDB Connection
**Exact Pattern from fill_the_table.py:**
```python
mongo_username = os.getenv('MONGO_USERNAME', 'chriscruz')
mongo_password = os.getenv('MONGO_PASSWORD', '@LA69Gk9merja2N')
mongo_host = os.getenv('MONGO_HOST', 'cuculi-production.grwghw0.mongodb.net')
mongo_db_name = os.getenv('MONGO_DB_NAME', 'cuculi_production')

encoded_password = quote_plus(mongo_password)
mongo_uri = f"mongodb+srv://{mongo_username}:{encoded_password}@{mongo_host}/?retryWrites=true&w=majority"

self.mongo_client = MongoClient(
    mongo_uri,
    tls=True,
    tlsAllowInvalidCertificates=True
)
self.db = self.mongo_client.get_database(mongo_db_name)
self.users_collection = self.db['user']  # Singular name
self.events_collection = self.db['event']  # Singular name
```

### Firebase Connection
**Exact Pattern from fill_the_table.py:**
```python
self.firebase_url = os.getenv('FIREBASE_DATABASE_URL', 
    'https://cuculi-2c473.firebaseio.com').rstrip('/')
self.firebase_base_path = os.getenv('FIREBASE_BASE_PATH', 'Leo')

def _firebase_request(self, path: str, method: str = 'GET', data: Optional[Dict[str, Any]] = None):
    full_url = f"{self.firebase_url}/{self.firebase_base_path}/{path}.json"
    req_data = json.dumps(data).encode('utf-8') if data else None
    headers = {'Content-Type': 'application/json'}
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    req = Request(full_url, data=req_data, method=method, headers=headers)
    # ... handle response
```

### Logging Setup
**Exact Pattern from fill_the_table.py:**
```python
def setup_logging(log_dir: str = None) -> logging.Logger:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_dir, f"return_to_table_{timestamp}.log")
    
    logger = logging.getLogger('ReturnToTable')
    logger.setLevel(logging.INFO)
    logger.handlers = []
    
    # File handler (DEBUG level)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger
```

### Profile Completeness Check
**Exact Pattern from fill_the_table.py:**
```python
def _is_profile_complete(self, user: Dict[str, Any]) -> bool:
    required_fields = ['firstName', 'lastName', 'email', 'phone', 'gender', 'interests', 'occupation', 'homeNeighborhood']
    filled = sum(1 for f in required_fields if user.get(f))
    return filled >= 4
```

### Engagement Status Calculation
**Exact Pattern from fill_the_table.py:**
```python
def _derive_engagement(self, last_date: Optional[datetime]) -> Dict[str, Any]:
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
```

### Event Participation Calculation
**Exact Pattern from fill_the_table.py:**
```python
# Build user-event map
user_event_map = {}
for event in all_events:
    participants = [str(p) for p in event.get('participants', [])]
    owner_id = str(event.get('ownerId', ''))
    for uid in set([owner_id] + participants):
        if uid and uid != 'None':
            user_event_map.setdefault(uid, []).append(event)

# For each user
user_id = str(user.get('_id', ''))
user_events = user_event_map.get(user_id, [])
event_count = len(user_events)

# Find last event date
last_dates = []
for e in user_events:
    last_dt = self._parse_iso_date(e.get('startDate'))
    if last_dt:
        last_dates.append(last_dt)
last_event_dt = max(last_dates) if last_dates else None
```

### Date Parsing
**Exact Pattern from fill_the_table.py:**
```python
def _parse_iso_date(self, value: Any) -> Optional[datetime]:
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
```

### ObjectId Conversion
**Exact Pattern from fill_the_table.py:**
```python
def _convert_objectid(self, obj: Any) -> Any:
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: self._convert_objectid(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [self._convert_objectid(item) for item in obj]
    else:
        return obj
```

## File Structure

```
campaigns/return-to-table/
├── README.md                    # This file (implementation plan)
├── return_to_table.py           # Main campaign script
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (gitignored)
├── data/
│   ├── raw/
│   │   ├── users.json          # Raw user data from MongoDB
│   │   └── events.json         # Raw event data from MongoDB
│   └── processed/
│       ├── dormant_users.json  # Processed dormant users
│       ├── future_events.json  # Processed future events
│       ├── matches.json         # User-event matches
│       └── messages.json        # Generated messages
├── logs/
│   └── return_to_table_*.log   # Timestamped log files
└── reports/
    └── return_to_table_report_*.md  # Campaign reports
```

## Dependencies

**requirements.txt:**
```
pymongo>=4.0.0
anthropic>=0.18.0
python-dotenv>=1.0.0
```

## Environment Variables

```bash
# MongoDB
MONGO_USERNAME=chriscruz
MONGO_PASSWORD=@LA69Gk9merja2N
MONGO_HOST=cuculi-production.grwghw0.mongodb.net
MONGO_DB_NAME=cuculi_production

# Firebase
FIREBASE_DATABASE_URL=https://cuculi-2c473.firebaseio.com
FIREBASE_BASE_PATH=Leo

# Anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
```

## Key Differences from fill-the-table

1. **User Selection**: 
   - fill-the-table: Top users (most events attended)
   - return-to-table: Dormant users (31-90 days inactive, has interests, has attended at least 1 event)

2. **Event Selection**:
   - fill-the-table: Underfilled events (<50% capacity)
   - return-to-table: All future public events (broader matching)

3. **Matching Focus**:
   - fill-the-table: Fill low-participation events
   - return-to-table: Reactivate dormant users (interest alignment + reactivation potential)

4. **Message Tone**:
   - fill-the-table: Scarcity + urgency for filling events
   - return-to-table: Welcome back + interest alignment for reactivation

5. **Match Purpose**:
   - fill-the-table: "fill_low_participation"
   - return-to-table: "reactivate_dormant_user"

## Implementation Checklist

- [ ] Create `campaigns/return-to-table/` directory
- [ ] Create `return_to_table.py` with class structure matching `fill_the_table.py`
- [ ] Implement MongoDB connection (exact pattern from fill_the_table.py)
- [ ] Implement Firebase connection (exact pattern from fill_the_table.py)
- [ ] Implement logging setup (exact pattern from fill_the_table.py)
- [ ] Implement `get_dormant_users()` method:
  - [ ] Fetch all users and events
  - [ ] Build user-event map
  - [ ] Calculate engagement status
  - [ ] Filter for dormant users (31-90 days inactive)
  - [ ] Check profile completeness (at least 4 fields)
  - [ ] Check interests array (at least 1 interest)
  - [ ] Check event count (at least 1 event)
  - [ ] Enrich with last_event_date, days_inactive, engagement_status
- [ ] Implement `get_future_events()` method:
  - [ ] Query future events (startDate > now)
  - [ ] Filter for public events
  - [ ] Calculate participation metrics
- [ ] Implement summary generation methods
- [ ] Implement `create_matching_prompt()` for reactivation focus
- [ ] Implement `get_matches_from_ai()` using Claude API
- [ ] Implement `generate_message_for_user()` with reactivation tone
- [ ] Implement Firebase save methods (matching fill_the_table.py schema)
- [ ] Implement report generation
- [ ] Implement data persistence (raw and processed JSON files)
- [ ] Test with real MongoDB data
- [ ] Verify Firebase schema matches dashboard expectations
- [ ] Verify logging works correctly
- [ ] Create requirements.txt
- [ ] Update this README with any learnings

## Success Criteria

1. ✅ Correctly identifies dormant users (31-90 days inactive)
2. ✅ Only selects users with interests filled out
3. ✅ Only selects users who have attended at least 1 event
4. ✅ Correctly calculates last event date
5. ✅ Correctly calculates days_inactive and engagement_status
6. ✅ Matches users to events based on interests and reactivation potential
7. ✅ Generates welcome-back messages with reactivation tone
8. ✅ Saves data to Firebase in correct schema (matching dashboard)
9. ✅ Logs all operations correctly
10. ✅ Generates comprehensive reports

## Self-Critique of Plan

### Strengths
1. **Clear ranking system**: The reactivation score provides objective prioritization
2. **Individual prompts**: One prompt per user ensures personalized matching
3. **Quality focus**: Preferring well-attended events aligns with reactivation goals
4. **Firebase schema alignment**: Matches dashboard.html expectations
5. **Top 10 limit**: Manageable scope for first iteration

### Potential Issues & Solutions

**Issue 1: What if a user has no good match?**
- **Solution**: Set minimum confidence threshold (e.g., 70%). If no match meets threshold, log warning and skip that user.

**Issue 2: What if multiple users match to same event?**
- **Solution**: Allow it initially (event can have multiple participants). If needed later, add deduplication logic.

**Issue 3: Firebase schema conflicts with existing data**
- **Solution**: Use PATCH for matches/messages (append), but PUT for users/events (replace with campaign data). Document this clearly.

**Issue 4: Ranking might miss valuable users**
- **Solution**: Log all dormant users with scores for analysis. Can adjust weights later.

**Issue 5: Individual prompts are expensive (10 API calls)**
- **Solution**: Acceptable for top 10 users. If scaling, consider batching or caching.

**Issue 6: Event participation data might be stale**
- **Solution**: Always fetch fresh event data from MongoDB at campaign start.

**Issue 7: Dashboard might not show campaign-specific data**
- **Solution**: Save to both `/Leo/users` (dashboard) and `/campaigns/{campaign_id}/users` (tracking).

### Improvements for Future Iterations
1. Add A/B testing for different reactivation message tones
2. Track which events actually convert dormant users
3. Adjust ranking weights based on conversion data
4. Consider user feedback/preferences from past events
5. Add time-of-day optimization (when to send messages)
6. Consider user's past event categories to predict preferences

## Next Steps After Implementation

1. Run the campaign script
2. Review generated matches and messages in Firebase
3. **Verify data appears correctly in dashboard.html**
4. Use HITL dashboard to review and approve messages
5. Track RSVP conversion rate for dormant users
6. Analyze which users/events had highest conversion
7. Iterate on ranking weights and matching criteria based on results
8. A/B test different message tones for reactivation

