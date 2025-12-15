# Seat Newcomers Campaign - Implementation Plan

## Overview

The **Seat Newcomers** campaign is designed to convert recently joined users who have never attended an event (or attended very few events) into active participants by matching them with perfect, welcoming events for their first table. The goal is to identify these newcomers, assess their profile completeness for personalization, and match them with beginner-friendly events that will drive their first RSVP.

## Campaign Goal

**Primary Objective:** Convert new users (0-2 events attended) to RSVP to their first table by matching them with welcoming, beginner-friendly events based on their interests and location, then send personalized SMS messages that encourage their first attendance.

**Success Metrics:**
- Number of newcomers identified (0 events vs 1-2 events)
- Number of users with complete profiles (personalization-ready)
- Number of matches created
- Number of messages generated
- First-time RSVP conversion rate (tracked downstream)

## Campaign Flow

### Step 1: Identify and Rank Newcomers
**Purpose:** Find users who are new to the app (recently joined) and have never attended an event or attended very few events, then rank them to identify the top candidates for first-time conversion.

**Criteria:**
- **Primary Target**: Users with `eventCount == 0` (never attended)
- **Secondary Target**: Users with `eventCount` between 1-2 (attended very few events)
- Must have `interests` array populated (at least 1 interest) for personalization
- Must have at least 4 of 8 required profile fields filled:
  - `firstName`, `lastName`, `email`, `phone`, `gender`, `interests`, `occupation`, `homeNeighborhood`
- Account must be relatively recent (joined within last 90 days) - to focus on true newcomers

**Ranking/Scoring System:**
Users should be ranked based on a composite score that prioritizes:
1. **Event History** (0-50 points): Never attended = highest priority
   - 0 events = 50 points (highest priority - first-timers)
   - 1 event = 30 points
   - 2 events = 15 points
   - 3+ events = 0 points (excluded)
2. **Profile Completeness** (0-30 points): More fields filled = better personalization
   - 8 fields filled = 30 points
   - 7 fields filled = 25 points
   - 6 fields filled = 20 points
   - 5 fields filled = 15 points
   - 4 fields filled = 10 points
3. **Account Recency** (0-20 points): More recent = higher priority (within 90 days)
   - Joined within last 7 days = 20 points
   - Joined within last 14 days = 18 points
   - Joined within last 30 days = 15 points
   - Joined within last 60 days = 12 points
   - Joined within last 90 days = 10 points
   - Older than 90 days = 0 points (excluded)

**Total Score Calculation:**
```python
def calculate_newcomer_score(user: Dict[str, Any]) -> float:
    # Event history (0-50) - never attended = highest priority
    event_count = user.get('eventCount', 0)
    if event_count == 0:
        history_score = 50  # First-timers get highest priority
    elif event_count == 1:
        history_score = 30
    elif event_count == 2:
        history_score = 15
    else:
        history_score = 0  # Exclude users with 3+ events
    
    # Profile completeness (0-30)
    required_fields = ['firstName', 'lastName', 'email', 'phone', 'gender', 'interests', 'occupation', 'homeNeighborhood']
    filled_count = sum(1 for f in required_fields if user.get(f))
    completeness_score = min(30, filled_count * 3.75)  # ~3.75 points per field, max 30
    
    # Account recency (0-20) - more recent = higher priority
    created_at = user.get('createdAt')
    if created_at:
        days_since_join = (now - parse_date(created_at)).days
        if days_since_join <= 7:
            recency_score = 20
        elif days_since_join <= 14:
            recency_score = 18
        elif days_since_join <= 30:
            recency_score = 15
        elif days_since_join <= 60:
            recency_score = 12
        elif days_since_join <= 90:
            recency_score = 10
        else:
            recency_score = 0  # Exclude users older than 90 days
    else:
        recency_score = 0
    
    total_score = history_score + completeness_score + recency_score
    return total_score
```

**Selection:**
- Calculate newcomer score for all eligible users
- Sort by score (descending)
- Select top 10-15 users for this campaign run
- Prioritize users with 0 events over users with 1-2 events

**Output:**
- List of newcomer users with enriched attributes:
  - `eventCount`: 0, 1, or 2
  - `is_first_timer`: True if eventCount == 0
  - `days_since_join`: Days since account creation
  - `newcomer_score`: Calculated score
  - `personalization_ready`: True if profile complete enough
  - `interests`: Array of interests
  - All original user fields

**Data Persistence:**
- Save raw users and events to `data/raw/users.json` and `data/raw/events.json`
- Save processed newcomers to `data/processed/newcomer_users.json`

### Step 2: Get Future Events (Prefer Beginner-Friendly)
**Purpose:** Identify future public events that are welcoming and suitable for first-time attendees.

**Criteria:**
- `startDate` > current_time (future events only)
- `type` == "public" (not private events)
- `active` == True
- `eventStatus` == "approved" (if field exists)
- **Preference for events with good participation** (50-80% filled) to show social proof without being too exclusive
- **Preference for beginner-friendly features** (if available in event data)

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
- Identify beginner-friendly indicators:
  - Events with "groups" or "beginner-friendly" features
  - Events with moderate participation (50-80% filled) - good social proof, not too exclusive
  - Events with welcoming descriptions

**Event Suitability Scoring (for matching):**
- Higher participation (50-80% filled) = better (shows quality, not too empty)
- Events with >80% filled are less ideal (might feel exclusive for first-timers)
- Events with <30% filled are less ideal (might feel empty/unsuccessful)
- Events with welcoming descriptions/keywords = bonus

**Output:**
- List of future public events with participation metrics, sorted by suitability for newcomers

**Data Persistence:**
- Save processed events to `data/processed/future_events.json`

### Step 3: Generate User Summaries
**Purpose:** Create human-readable summaries for AI matching, emphasizing first-time status.

**Format:**
```
"{firstName} {lastName} is a {occupation} from {homeNeighborhood} who joined {days_since_join} days ago. 
{First-timer status: 'Never attended an event' OR 'Attended {eventCount} event(s) previously'}. 
Interests: {interests}. Profile: {profile_completeness}/8 fields filled."
```

**Example:**
```
"Sarah Johnson is a Software Engineer from soho who joined 12 days ago. 
Never attended an event. 
Interests: food, music, art. Profile: 7/8 fields filled."
```

### Step 4: Generate Event Summaries
**Purpose:** Create human-readable summaries for AI matching, emphasizing beginner-friendliness.

**Format:**
```
"Event: {name} at {venueName} in {neighborhood}. 
Categories: {categories}. Features: {features}. 
Capacity: {maxParticipants}, Participants: {participantCount} ({participationPercentage:.1f}% full). 
Date: {startDate} UTC. {description}"
```

### Step 5: AI-Powered Matching (Individual Prompts Per User)
**Purpose:** Use Claude API to find the PERFECT first event for each of the top newcomers. **Each user gets their own individual prompt** to ensure the best possible match for their first table.

**Matching Strategy:**
- **One user at a time**: Create a dedicated prompt for each user with all available events
- **Find the single best match**: Return only the top 1 event per user (not multiple matches)
- **First-time focus**: Emphasize welcoming, beginner-friendly events
- **Quality over quantity**: Focus on finding the perfect event that will convert this specific user

**Matching Criteria (in order of importance):**
1. **Interest Alignment**: User interests MUST match event categories/features (CRITICAL for first-timers)
2. **Location Proximity**: User `homeNeighborhood` vs event `neighborhood` (high priority for convenience)
3. **Event Welcomingness**: Prefer events with good participation (50-80% filled) - shows quality without exclusivity
4. **Beginner-Friendly**: Consider events with welcoming descriptions, group-friendly features
5. **Event Timing**: Prefer events happening soon (creates urgency for first RSVP)
6. **First-Time Appeal**: Events that feel welcoming and not intimidating for newcomers

**Individual Prompt Structure (Per User):**
```
You are an expert user onboarding specialist focused on converting new users to their first event attendance.

PRIORITY: Find the SINGLE BEST event for this newcomer ({first_timer_status}) that will convert them to RSVP to their FIRST table.

USER CONTEXT:
This user joined {days_since_join} days ago. {First-timer status}.
Profile completeness: {profile_completeness}/8 fields filled
Interests: {interests}
Neighborhood: {homeNeighborhood}
Occupation: {occupation}

MATCHING CRITERIA (in order of importance):
1. Interest alignment: User interests MUST match event categories/features (this is critical for first-timers)
2. Location proximity: Prefer events in or near user's neighborhood ({homeNeighborhood}) for convenience
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
- 'event_name': The event name
- 'event_id': The event ID
- 'reasoning': Detailed explanation (3-4 sentences) focusing on:
  * Why this specific event is perfect for THIS user's FIRST table
  * How interests align (critical for first-timers)
  * Why the event is welcoming and beginner-friendly
  * How location/timing work for first-time attendance
- 'confidence_percentage': Number 0-100 (should be 80+ for a good match)
- 'match_purpose': "convert_newcomer_first_table"

Available Events: {json.dumps(event_data, default=str, indent=2)}

Return only the JSON object, no additional text.
```

**Processing:**
- For each of the top 10-15 users:
  1. Create individual prompt with that user's data + all available events
  2. Call Claude API
  3. Parse response to get single best match
  4. Store match with full user and event objects
  5. Save match incrementally to Firebase

**Output:**
- List of matches (one per user) with:
  - `user_name`, `event_name`, `event_id`
  - `reasoning`, `confidence_percentage`, `match_purpose`
  - Full user and event objects
  - `matched_at`: ISO timestamp

**Firebase Persistence:**
- **Save top users to `/Leo/users`**: 
  - Structure: `{ users: [...], count: N, updatedAt: "..." }`
  - Each user includes `newcomer_score` and `is_first_timer` fields
  - Must be array (not object) for dashboard compatibility
- **Save matched events to `/Leo/events`**:
  - Structure: `{ events: [...], count: N, updatedAt: "..." }`
  - Only save the events that were matched
  - Must be array (not object) for dashboard compatibility
- **Save matches to `/Leo/matches`**:
  - Use PATCH to append (preserve existing matches)
  - Structure: `{ matches: [...], count: N, updatedAt: "..." }`
  - Must be array (not object) for dashboard compatibility

### Step 6: Generate Personalized First-Time Messages
**Purpose:** Create SMS messages that welcome newcomers and encourage their first RSVP.

**Message Guidelines:**
- **Length**: <180 chars total (including link)
- **Tone**: Warm, welcoming, encouraging (not pushy)
- **Structure**: 
  - [Greeting + Name]
  - [Welcome to the community hook]
  - [Event hook tied to interests/occupation/location]
  - [Spots left + time urgency + social proof]
  - [CTA + link at end]
- **First-Time Elements**:
  - Welcome them to the community ("Welcome to Cuculi!", "Ready for your first table?")
  - Acknowledge it's their first event (if applicable)
  - Make it feel special and exciting
  - Remove barriers (emphasize welcoming, beginner-friendly)
- **Link**: Must end with `https://cuculi.net/events/{event_id}`

**Prompt Structure:**
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
- "Hey Sarah! 👋 Welcome to Cuculi! Your first table: Ramen night Thu 7:30p near SoHo, 4 spots left—perfect for your food love. Join us! Tap to RSVP: https://cuculi.net/events/12345"
- "Hi Mike! Ready for your first table? Comedy + dinner near West Village tomorrow, only 3 seats—welcoming group waiting. Tap to RSVP: https://cuculi.net/events/12345"
- "Hi Priya! 🎉 Welcome! Mexican supper near SoMa, 2 spots left; walkable from you. Perfect first event! Tap to RSVP: https://cuculi.net/events/12345"

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

**CRITICAL: Firebase Schema Must Match dashboard.html**

The dashboard expects specific structures:
- `/Leo/users`: `{ users: [...], count: N, updatedAt: "..." }` - **ARRAY, not object**
- `/Leo/events`: `{ events: [...], count: N, updatedAt: "..." }` - **ARRAY, not object**
- `/Leo/matches`: `{ matches: [...], count: N, updatedAt: "..." }` - **ARRAY, not object**
- `/Leo/messages`: `{ messages: [...], count: N, updatedAt: "..." }` - **ARRAY, not object**

**Firebase Structure:**
```
/Leo/
├── campaigns/
│   └── seat-newcomers-{timestamp}/
│       ├── metadata/
│       ├── users/
│       ├── events/
│       ├── matches/
│       └── messages/
├── users/          # Dashboard schema: { users: [...], count: N, updatedAt: "..." } (PUT - top users)
├── events/         # Dashboard schema: { events: [...], count: N, updatedAt: "..." } (PUT - matched events)
├── matches/        # Dashboard schema: { matches: [...], count: N, updatedAt: "..." } (PATCH - append)
└── messages/      # Dashboard schema: { messages: [...], count: N, updatedAt: "..." } (PATCH - append)
```

**Save Strategy:**
1. **Users**: PUT to `/Leo/users` with top users (replaces existing for this campaign)
2. **Events**: PUT to `/Leo/events` with matched events (replaces existing for this campaign)
3. **Matches**: PATCH to `/Leo/matches` to append (preserves existing matches from other campaigns)
4. **Messages**: PATCH to `/Leo/messages` to append (preserves existing messages from other campaigns)

**Campaign Metadata:**
```json
{
  "id": "seat-newcomers-20251212-143022",
  "name": "seat-newcomers",
  "created_at": "2025-12-12T14:30:22.000Z",
  "stats": {
    "users_processed": 12,
    "events_processed": 15,
    "matches_created": 12,
    "messages_generated": 12,
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
      "firstName": "Sarah",
      "lastName": "Johnson",
      "name": "Sarah Johnson",
      "email": "sarah@example.com",
      "phone": "+19145890466",
      "interests": ["food", "music", "art"],
      "homeNeighborhood": "soho",
      "occupation": "Software Engineer",
      "eventCount": 0,
      "event_count": 0,
      "is_first_timer": true,
      "days_since_join": 12,
      "newcomer_score": 85.5,
      "personalization_ready": true,
      "summary": "Sarah Johnson is a Software Engineer..."
    }
  ],
  "count": 12,
  "updatedAt": "2025-12-12T14:30:22.000Z"
}
```

**CRITICAL:** The dashboard expects:
- Root path: `/Leo/users`
- Structure: `{ users: [...], count: N, updatedAt: "..." }`
- `users` must be an array (not an object)
- Each user must have both `id` and `_id` fields (same value)
- Must include `eventCount` and `event_count` (for compatibility)
- Must include `is_first_timer` and `newcomer_score` fields

**Events Schema (Dashboard) - MUST MATCH dashboard.html expectations:**
```json
{
  "events": [
    {
      "id": "6927d356eb4f0aa02a6d14a2",
      "_id": "6927d356eb4f0aa02a6d14a2",
      "name": "Welcome Ramen Night",
      "startDate": "2025-12-20T23:30:00.000Z",
      "maxParticipants": 8,
      "capacity": 8,
      "participants": ["email1@example.com"],
      "participantCount": 5,
      "participationPercentage": 62.5,
      "neighborhood": "soho",
      "categories": ["JAPANESE", "FOOD"],
      "features": ["groups", "beginner-friendly"],
      "venueName": "Ramen Bar",
      "type": "public",
      "summary": "Event: Welcome Ramen Night..."
    }
  ],
  "count": 12,
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
      "user_name": "Sarah Johnson",
      "event_name": "Welcome Ramen Night",
      "user_id": "631b60819007c60c89083db9",
      "event_id": "6927d356eb4f0aa02a6d14a2",
      "confidence_percentage": 88,
      "reasoning": "This event is perfect for Sarah's first table...",
      "match_purpose": "convert_newcomer_first_table",
      "strategy": "convert_newcomer_first_table",
      "matched_at": "2025-12-12T14:30:22.000Z",
      "user": { /* full user object */ },
      "event": { /* full event object */ }
    }
  ],
  "count": 12,
  "updatedAt": "2025-12-12T14:30:22.000Z"
}
```

**CRITICAL:** The dashboard expects:
- Root path: `/Leo/matches`
- Structure: `{ matches: [...], count: N, updatedAt: "..." }`
- `matches` must be an array (not an object)
- Use PATCH to append (don't overwrite existing matches)
- Each match should include full `user` and `event` objects for context

### Step 8: Generate Report and Automatic Self-Assessment
**Purpose:** Create comprehensive campaign report with statistics, then use Claude API to automatically self-assess the campaign results and generate actionable recommendations.

**Report Structure:**
```json
{
  "campaign_id": "seat-newcomers-20251212-143022",
  "campaign_name": "seat-newcomers",
  "run_date": "2025-12-12T14:30:22.000Z",
  "statistics": {
    "users_processed": 12,
    "events_processed": 15,
    "matches_created": 12,
    "messages_generated": 12,
    "errors": []
  },
  "summary": {
    "total_newcomers_found": 12,
    "first_timers_count": 8,
    "few_events_count": 4,
    "total_future_events": 15,
    "total_matches_created": 12,
    "total_messages_generated": 12,
    "average_newcomer_score": 78.5,
    "average_confidence_score": 85.2,
    "error_count": 0
  },
  "errors": []
}
```

**Markdown Report:**
- Save to `reports/seat_newcomers_report_{campaign_id}.md`
- Include goal, run summary, users processed (with first-timer breakdown), events processed, matches, messages
- **Include Assessment & Recommendations section** (generated automatically via Claude API self-assessment)

**Assessment & Recommendations Section:**
The report will automatically include an "Assessment & Recommendations" section at the end, just like the fill-the-table campaign. This section is generated by Claude API analyzing the campaign results and providing:
- Overall assessment of campaign performance
- Strengths (what worked well)
- Specific, actionable recommendations for improvement
- Focus areas for next iteration

This automatic self-assessment happens at the end of each campaign run, ensuring continuous improvement based on actual results.

**Automatic Self-Assessment Using Claude API:**
After generating the campaign report, the system will automatically use Claude API to analyze the campaign results and generate actionable recommendations.

**Self-Assessment Process:**
1. Collect campaign data:
   - User statistics (newcomer scores, first-timer vs few-events breakdown)
   - Match statistics (confidence scores, reasoning quality)
   - Message statistics (character counts, personalization notes)
   - Event statistics (participation rates, categories matched)
   - Any errors or issues encountered

2. Create self-assessment prompt for Claude:
```
You are an expert campaign analyst reviewing a "Seat Newcomers" campaign designed to convert new users (0-2 events attended) to their first table RSVP.

CAMPAIGN GOAL: Convert newcomers to RSVP to their first table by matching them with welcoming, beginner-friendly events.

CAMPAIGN RESULTS:
{json.dumps(campaign_data, default=str, indent=2)}

ANALYZE:
1. User Selection: Were the right newcomers selected? (0 events prioritized over 1-2 events? Good profile completeness?)
2. Event Matching: Were matches high-quality? (Interest alignment? Location proximity? Beginner-friendly events?)
3. Message Quality: Were messages welcoming and first-time focused? (Character count? Personalization? First-time language?)
4. Overall Performance: What worked well? What could be improved?

GENERATE RECOMMENDATIONS:
Provide 4-6 specific, actionable recommendations for improving first-time conversion rates. Focus on:
- User selection and ranking
- Event matching criteria
- Message tone and content
- First-time conversion strategies
- Any patterns you notice in successful vs unsuccessful matches

Return a JSON object with:
- 'assessment': Brief overall assessment (2-3 sentences)
- 'strengths': List of 2-3 things that worked well
- 'recommendations': List of 4-6 specific, actionable recommendations (each as a string)
- 'focus_areas': List of 2-3 areas to prioritize for next iteration

Return only the JSON object, no additional text.
```

3. Call Claude API with self-assessment prompt
4. Parse recommendations from Claude response
5. Save recommendations to:
   - Markdown report (under "Assessment & Recommendations" section)
   - Firebase at `/campaigns/seat-newcomers/recommendations`
   - Campaign metadata

**Recommendations Format:**
The automatically generated recommendations will be specific and actionable, such as:
- "Prioritize users with 0 events and 6+ profile fields filled for highest first-time conversion"
- "Focus on events with 60-75% participation rate - optimal balance of social proof and accessibility for first-timers"
- "Emphasize 'Welcome to Cuculi!' messaging in first 20 characters to create immediate community connection"
- "Match users to events within 2 neighborhoods of their home for easier first attendance"
- "Consider adding 'beginner-friendly' event tags to improve first-timer matching accuracy"

**Implementation:**
```python
def _generate_self_assessment(self, users: List[Dict], events: List[Dict], 
                              matches: List[Dict], messages: List[Dict]) -> Dict[str, Any]:
    """Use Claude API to automatically assess campaign results and generate recommendations."""
    # Prepare campaign data for analysis
    campaign_data = {
        'users_processed': len(users),
        'first_timers_count': sum(1 for u in users if u.get('eventCount', 0) == 0),
        'few_events_count': sum(1 for u in users if 1 <= u.get('eventCount', 0) <= 2),
        'average_newcomer_score': sum(u.get('newcomer_score', 0) for u in users) / len(users) if users else 0,
        'events_processed': len(events),
        'matches_created': len(matches),
        'average_confidence': sum(m.get('confidence_percentage', 0) for m in matches) / len(matches) if matches else 0,
        'messages_generated': len(messages),
        'average_message_length': sum(m.get('character_count', 0) for m in messages) / len(messages) if messages else 0,
        'sample_matches': matches[:3],  # Include sample matches for analysis
        'sample_messages': messages[:3],  # Include sample messages for analysis
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
    
    return assessment
```

**Benefits of Automatic Self-Assessment:**
- **Objective Analysis**: Claude analyzes patterns across all matches and messages
- **Actionable Insights**: Generates specific recommendations based on actual campaign data
- **Continuous Improvement**: Each campaign run learns from previous results
- **Time Savings**: No manual analysis required
- **Pattern Recognition**: Identifies trends in successful vs unsuccessful matches

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
    log_file = os.path.join(log_dir, f"seat_newcomers_{timestamp}.log")
    
    logger = logging.getLogger('SeatNewcomers')
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
campaigns/seat-newcomers/
├── README.md                    # This file (implementation plan)
├── seat_newcomers.py            # Main campaign script
├── requirements.txt              # Python dependencies
├── .env                         # Environment variables (gitignored)
├── data/
│   ├── raw/
│   │   ├── users.json          # Raw user data from MongoDB
│   │   └── events.json         # Raw event data from MongoDB
│   └── processed/
│       ├── newcomer_users.json  # Processed newcomer users
│       ├── future_events.json   # Processed future events
│       ├── matches.json         # User-event matches
│       └── messages.json        # Generated messages
├── logs/
│   └── seat_newcomers_*.log     # Timestamped log files
└── reports/
    └── seat_newcomers_report_*.md  # Campaign reports
```

## Dependencies

**requirements.txt:**
```
pymongo==4.6.1
anthropic==0.18.1
python-dotenv==1.0.1
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

## Key Differences from Other Campaigns

### vs fill-the-table:
1. **User Selection**: 
   - fill-the-table: Top users (most events attended)
   - seat-newcomers: Newcomers (0-2 events, recently joined)

2. **Event Selection**:
   - fill-the-table: Underfilled events (<50% capacity)
   - seat-newcomers: Well-attended events (50-80% filled) for social proof

3. **Matching Focus**:
   - fill-the-table: Fill low-participation events
   - seat-newcomers: Convert newcomers to first table (interest alignment + welcoming)

4. **Message Tone**:
   - fill-the-table: Scarcity + urgency for filling events
   - seat-newcomers: Welcome + encouragement for first-time attendance

5. **Match Purpose**:
   - fill-the-table: "fill_low_participation"
   - seat-newcomers: "convert_newcomer_first_table"

### vs return-to-table:
1. **User Selection**: 
   - return-to-table: Dormant users (31-90 days inactive, has attended events)
   - seat-newcomers: Newcomers (0-2 events, recently joined)

2. **Ranking**:
   - return-to-table: Profile completeness + dormancy duration + event history
   - seat-newcomers: Event history (0 events = highest) + profile completeness + account recency

3. **Matching Focus**:
   - return-to-table: Reactivate dormant users
   - seat-newcomers: Convert newcomers to first table

4. **Message Tone**:
   - return-to-table: Welcome back + reactivation
   - seat-newcomers: Welcome to community + first-time excitement

## Implementation Checklist

- [ ] Create `campaigns/seat-newcomers/` directory
- [ ] Create `seat_newcomers.py` with class structure matching `fill_the_table.py`
- [ ] Implement MongoDB connection (exact pattern from fill_the_table.py)
- [ ] Implement Firebase connection (exact pattern from fill_the_table.py)
- [ ] Implement logging setup (exact pattern from fill_the_table.py)
- [ ] Implement `get_newcomer_users()` method:
  - [ ] Fetch all users and events
  - [ ] Build user-event map
  - [ ] Filter for users with 0-2 events
  - [ ] Filter for users joined within last 90 days
  - [ ] Check profile completeness (at least 4 fields)
  - [ ] Check interests array (at least 1 interest)
  - [ ] Calculate `days_since_join` from `createdAt`
  - [ ] **Calculate newcomer_score for each user**
  - [ ] **Sort by newcomer_score (descending)**
  - [ ] **Select top 10-15 users (prioritize 0 events over 1-2 events)**
  - [ ] Enrich with `is_first_timer`, `days_since_join`, `newcomer_score`
- [ ] Implement `get_future_events()` method:
  - [ ] Query future events (startDate > now)
  - [ ] Filter for public events
  - [ ] Calculate participation metrics
  - [ ] **Sort by participation percentage (50-80% ideal range)**
- [ ] Implement summary generation methods (emphasizing first-time status)
- [ ] Implement `create_individual_matching_prompt(user, events)` method:
  - [ ] Takes single user + all events
  - [ ] Creates prompt focused on finding SINGLE BEST match for first table
  - [ ] Emphasizes interest alignment, location, welcoming events
- [ ] Implement `get_best_match_for_user(user, events)` method:
  - [ ] Calls Claude API with individual prompt
  - [ ] Returns single best match (not array)
  - [ ] Handles JSON parsing
- [ ] Implement `match_users_to_events()` method:
  - [ ] Iterates through top users
  - [ ] For each user, calls `get_best_match_for_user()`
  - [ ] Stores matches incrementally
- [ ] Implement `generate_message_for_user()` with first-time welcome tone
- [ ] Implement Firebase save methods:
  - [ ] **Save users to `/Leo/users` with `{ users: [...], count: N, updatedAt: "..." }` structure**
  - [ ] **Save events to `/Leo/events` with `{ events: [...], count: N, updatedAt: "..." }` structure**
  - [ ] **Save matches to `/Leo/matches` using PATCH to append (preserve existing)**
  - [ ] **Ensure arrays (not objects) for dashboard compatibility**
  - [ ] **Include both `id` and `_id` fields for all entities**
  - [ ] **Include `is_first_timer` and `newcomer_score` in user objects**
- [ ] Implement report generation with first-timer breakdown
- [ ] Implement `_get_recommendations()` method for first-time conversion
- [ ] Implement `_save_recommendations_to_firebase()` method
- [ ] Implement data persistence (raw and processed JSON files)
- [ ] Test with real MongoDB data
- [ ] **Verify Firebase schema matches dashboard.html expectations:**
  - [ ] `/Leo/users` has `users` array
  - [ ] `/Leo/events` has `events` array
  - [ ] `/Leo/matches` has `matches` array
  - [ ] All have `count` and `updatedAt` fields
- [ ] Verify logging works correctly
- [ ] Create requirements.txt
- [ ] Update this README with any learnings

## Success Criteria

1. ✅ Correctly identifies newcomers (0-2 events, joined within 90 days)
2. ✅ Prioritizes users with 0 events over users with 1-2 events
3. ✅ Only selects users with interests filled out
4. ✅ Correctly calculates days_since_join from createdAt
5. ✅ Correctly calculates newcomer_score
6. ✅ Matches users to events based on interests and first-time appeal
7. ✅ Generates welcome messages with first-time excitement
8. ✅ Saves data to Firebase in correct schema (matching dashboard)
9. ✅ Logs all operations correctly
10. ✅ Generates comprehensive reports with first-timer breakdown

## Assessment & Recommendations

**Automatic Self-Assessment:**
After each campaign run, the system automatically uses Claude API to analyze campaign results and generate actionable recommendations. This self-assessment:

1. **Analyzes Campaign Data:**
   - User selection quality (newcomer scores, first-timer vs few-events breakdown)
   - Match quality (confidence scores, interest alignment, location proximity)
   - Message quality (character counts, personalization, first-time language)
   - Event selection (participation rates, beginner-friendliness)
   - Overall performance metrics

2. **Generates Recommendations:**
   - Specific, actionable improvements for next iteration
   - Focus areas based on patterns in successful vs unsuccessful matches
   - Strengths identification (what worked well)
   - Areas for improvement

3. **Saves to Multiple Locations:**
   - Markdown report (under "Assessment & Recommendations" section)
   - Firebase at `/campaigns/seat-newcomers/recommendations`
   - Campaign metadata for tracking over time

**Example Recommendations (Auto-Generated):**
- "Prioritize users with 0 events and 6+ profile fields filled for highest first-time conversion"
- "Focus on events with 60-75% participation rate - optimal balance of social proof and accessibility"
- "Emphasize 'Welcome to Cuculi!' messaging in first 20 characters to create immediate community connection"
- "Match users to events within 2 neighborhoods of their home for easier first attendance"
- "Consider adding 'beginner-friendly' event tags to improve first-timer matching accuracy"

## Self-Critique of Plan

### Strengths
1. **Clear ranking system**: The newcomer score provides objective prioritization (0 events = highest)
2. **Individual prompts**: One prompt per user ensures personalized matching
3. **First-time focus**: Emphasizes welcoming, beginner-friendly events
4. **Firebase schema alignment**: Matches dashboard.html expectations
5. **Account recency filter**: Focuses on true newcomers (within 90 days)
6. **Automatic self-assessment**: Claude API analyzes results and generates recommendations automatically

### Potential Issues & Solutions

**Issue 1: What if a user has no good match?**
- **Solution**: Set minimum confidence threshold (e.g., 75%). If no match meets threshold, log warning and skip that user.

**Issue 2: What if multiple users match to same event?**
- **Solution**: Allow it initially (event can have multiple participants). If needed later, add deduplication logic.

**Issue 3: Firebase schema conflicts with existing data**
- **Solution**: Use PATCH for matches/messages (append), but PUT for users/events (replace with campaign data). Document this clearly.

**Issue 4: Ranking might miss valuable users**
- **Solution**: Log all newcomer users with scores for analysis. Can adjust weights later.

**Issue 5: Individual prompts are expensive (10-15 API calls)**
- **Solution**: Acceptable for top users. If scaling, consider batching or caching.

**Issue 6: Event participation data might be stale**
- **Solution**: Always fetch fresh event data from MongoDB at campaign start.

**Issue 7: Dashboard might not show campaign-specific data**
- **Solution**: Save to both `/Leo/users` (dashboard) and `/campaigns/{campaign_id}/users` (tracking).

**Issue 8: Account recency calculation might be inaccurate**
- **Solution**: Use `createdAt` field from user document. Handle missing or invalid dates gracefully.

### Improvements for Future Iterations
1. Add A/B testing for different first-time message tones
2. Track which events actually convert newcomers to first RSVP
3. Adjust ranking weights based on conversion data
4. Consider user's signup source/channel for personalization
5. Add time-of-day optimization (when to send messages)
6. Consider user's stated interests vs actual event categories for better matching
7. Track "first table" success rate separately from general RSVP rate

## Next Steps After Implementation

1. Run the campaign script
2. Review generated matches and messages in Firebase
3. **Verify data appears correctly in dashboard.html**
4. Review automatic self-assessment and recommendations in report
5. Use HITL dashboard to review and approve messages
6. Track first-time RSVP conversion rate for newcomers
7. Analyze which users/events had highest conversion
8. Compare first-timers (0 events) vs few-events (1-2 events) conversion rates
9. **Use Claude-generated recommendations to improve next campaign run**
10. Iterate on ranking weights and matching criteria based on self-assessment
11. A/B test different message tones for first-time conversion
12. Track recommendation effectiveness over multiple campaign runs

