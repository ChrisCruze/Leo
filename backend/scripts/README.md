# Campaign Scripts Documentation

This directory contains three automated campaign scripts for user engagement and reactivation. Each script filters users and events differently, then uses AI-powered matching and message generation to create personalized outreach.

## Overview

| Script | Target Users | Target Events | Goal |
|--------|-------------|---------------|------|
| **fill_the_table.py** | Top engagers with complete profiles | Underfilled events (<50% participation) | Fill underbooked events with active users |
| **return_to_table.py** | Dormant users (31-90 days inactive) | Well-attended events (high participation) | Reactivate lapsed users with quality events |
| **seat_newcomers.py** | New users (0-2 events, <90 days old) | Beginner-friendly events (50-80% filled) | Convert newcomers to their first table |

---

## 1. fill_the_table.py

### Campaign Goal
Increase event participation by matching highly engaged users with underbooked events to fill empty seats.

### User Filtering

**Criteria:**
- **Profile Completeness**: At least 4 of 8 required fields (firstName, lastName, email, phone, gender, interests, occupation, homeNeighborhood)
- **Qualification**: Must have `campaign_qualifications.qualifies_fill_the_table = true` (from mongodb_pull enrichment)
- **Message Deduplication**: Excludes users who already have messages in Firebase

**Ranking:**
- Sorted by **event attendance count** (descending - most events attended first)
- Top 50 users selected

**Implementation:**
```python
# Location: fill_the_table.py lines 400-459
def get_top_users(self, limit: int = 10):
    # Get enriched users from mongodb_pull
    all_enriched_users = self.mongodb_pull.users_pull(generate_report=False)

    # Filter for qualified users
    qualified_users = [
        user for user in all_enriched_users
        if user.get('campaign_qualifications', {}).get('qualifies_fill_the_table', False)
    ]

    # Filter out users with existing messages
    existing_message_user_ids = self._get_existing_message_user_ids()
    qualified_users = self._exclude_users_with_messages(qualified_users, existing_message_user_ids)

    # Sort by event count (descending)
    qualified_users.sort(key=lambda x: x.get('event_count', 0), reverse=True)

    return qualified_users[:limit]
```

### Event Filtering

**Criteria:**
- **Future Events**: Event date is in the future
- **Public Events**: Event visibility is public
- **Low Participation**: Less than 50% of max participants
- **Qualification**: Must have `campaign_qualifications.qualifies_fill_the_table = true`

**Ranking:**
- Sorted by **participation percentage** (ascending - most underfilled first)

**Implementation:**
```python
# Location: fill_the_table.py lines 466-498
def get_underfilled_events(self):
    # Get enriched events from mongodb_pull
    all_enriched_events = self.mongodb_pull.events_pull(generate_report=False)

    # Filter for qualified underfilled events
    underfilled_events = [
        event for event in all_enriched_events
        if event.get('campaign_qualifications', {}).get('qualifies_fill_the_table', False)
    ]

    # Sort by participation percentage (ascending)
    underfilled_events.sort(key=lambda x: x.get('participationPercentage', 0))

    return underfilled_events
```

### Matching Prompt

**Location:** `fill_the_table.py` lines 500-564

**Strategy:** Event-centric matching (one event, multiple users)

**Prompt:**
```
You are an expert event marketer focused on filling underbooked events.

PRIORITY: Match users to this event which has LOW participation ({fill_rate}% full, {remaining} spots remaining). Your goal is to maximize attendance for events that need more participants.

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
Fill Rate: {fill_rate}% ({participants}/{max_participants} participants, {remaining} spots remaining)

Users:
{users_text}

Return only the JSON array, no additional text.
```

### Message Generation Prompt

**Location:** `fill_the_table.py` lines 679-706

**Prompt:**
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

## 2. return_to_table.py

### Campaign Goal
Reactivate dormant users (31-90 days inactive) by matching them with high-quality, well-attended events.

### User Filtering

**Criteria:**
- **Dormancy**: 31-90 days since last event attendance
- **Event History**: At least 1 event attended (not first-timers)
- **Profile Completeness**: At least 4 of 8 required fields
- **Interests**: At least 1 interest recorded
- **Qualification**: Must have `campaign_qualifications.qualifies_return_to_table = true`

**Ranking:**
- Sorted by **reactivation score** (descending)
- Reactivation score formula: profile completeness + dormancy duration + event history
- Top 16 users selected

**Implementation:**
```python
# Location: return_to_table.py lines 308-366
def get_dormant_users(self, limit: int = 10):
    # Get enriched users from mongodb_pull
    all_enriched_users = self.mongodb_pull.users_pull(generate_report=False)

    # Filter for qualified dormant users
    dormant_users = [
        user for user in all_enriched_users
        if user.get('campaign_qualifications', {}).get('qualifies_return_to_table', False)
    ]

    # Sort by reactivation score (descending)
    dormant_users.sort(key=lambda x: x.get('reactivation_score', 0), reverse=True)

    return dormant_users[:limit]
```

### Event Filtering

**Criteria:**
- **Future Events**: Event date is in the future
- **Public Events**: Event visibility is public
- **Qualification**: Must have `campaign_qualifications.qualifies_return_to_table = true`

**Ranking:**
- Sorted by **participation percentage** (descending - most attended first)
- **Strategy**: Prefer well-attended events (50-100% filled) to show quality and social proof

**Implementation:**
```python
# Location: return_to_table.py lines 368-402
def get_future_events(self):
    # Get enriched events from mongodb_pull
    all_enriched_events = self.mongodb_pull.events_pull(generate_report=False)

    # Filter for qualified future events
    future_events = [
        event for event in all_enriched_events
        if event.get('campaign_qualifications', {}).get('qualifies_return_to_table', False)
    ]

    # Sort by participation percentage (descending - most attended first)
    future_events.sort(key=lambda x: x.get('participationPercentage', 0), reverse=True)

    return future_events
```

### Matching Prompt

**Location:** `return_to_table.py` lines 405-475

**Strategy:** User-centric matching (one user, best event)

**Prompt:**
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

### Message Generation Prompt

**Location:** `return_to_table.py` lines 611-638

**Prompt:**
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

## 3. seat_newcomers.py

### Campaign Goal
Convert new users (0-2 events attended) to their first table by matching them with welcoming, beginner-friendly events.

### User Filtering

**Criteria:**
- **Newcomer Status**: 0-2 events attended
- **Account Age**: Joined within the last 90 days
- **Profile Completeness**: At least 4 of 8 required fields
- **Interests**: At least 1 interest recorded
- **Qualification**: Must have `campaign_qualifications.qualifies_seat_newcomers = true`

**Ranking:**
- Sorted by **newcomer score** (descending)
- Newcomer score formula: event history priority (0 events > 1-2 events) + profile completeness + account recency
- **Priority**: Users with 0 events attended are prioritized over users with 1-2 events
- Top 34 users selected

**Implementation:**
```python
# Location: seat_newcomers.py lines 308-373
def get_newcomer_users(self, limit: int = 10):
    # Get enriched users from mongodb_pull
    all_enriched_users = self.mongodb_pull.users_pull(generate_report=False)

    # Filter for qualified newcomer users
    newcomer_users = [
        user for user in all_enriched_users
        if user.get('campaign_qualifications', {}).get('qualifies_seat_newcomers', False)
    ]

    # Add first-timer flag
    for user in newcomer_users:
        event_count = user.get('event_count', 0)
        user['is_first_timer'] = (event_count == 0)

    # Sort by newcomer score (descending)
    newcomer_users.sort(key=lambda x: x.get('newcomer_score', 0), reverse=True)

    return newcomer_users[:limit]
```

### Event Filtering

**Criteria:**
- **Future Events**: Event date is in the future
- **Public Events**: Event visibility is public
- **Beginner-Friendly Participation**: 50-80% filled (ideal range)
- **Qualification**: Must have `campaign_qualifications.qualifies_seat_newcomers = true`

**Ranking:**
- **Custom Sort**: Prioritizes events in the 50-80% participation range
- Events closest to 65% participation (middle of ideal range) are ranked highest
- Events outside the ideal range receive a penalty

**Implementation:**
```python
# Location: seat_newcomers.py lines 375-425
def get_future_events(self):
    # Get enriched events from mongodb_pull
    all_enriched_events = self.mongodb_pull.events_pull(generate_report=False)

    # Filter for qualified beginner-friendly events
    future_events = [
        event for event in all_enriched_events
        if event.get('campaign_qualifications', {}).get('qualifies_seat_newcomers', False)
    ]

    # Custom sort key: prioritize 50-80% participation range
    def sort_key(e):
        pct = e.get('participationPercentage', 0)
        if 50 <= pct <= 80:
            return abs(65 - pct)  # Prefer events near 65%
        elif pct < 50:
            return 1000 + (50 - pct)  # Penalty for underfilled
        else:
            return 1000 + (pct - 80)  # Penalty for overfilled

    future_events.sort(key=sort_key)

    return future_events
```

### Matching Prompt

**Location:** `seat_newcomers.py` lines 428-497

**Strategy:** User-centric matching (one user, best first event)

**Prompt:**
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

### Message Generation Prompt

**Location:** `seat_newcomers.py` lines 633-661

**Prompt:**
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

## Key Differences Summary

### User Filtering Philosophy
- **fill_the_table**: Most engaged users (highest event count) → maximize likelihood of attendance
- **return_to_table**: Dormant but previously engaged users → reactivation opportunity
- **seat_newcomers**: Brand new users (0-2 events) → conversion opportunity

### Event Filtering Philosophy
- **fill_the_table**: Underfilled events (<50%) → fill empty seats
- **return_to_table**: Well-attended events (high %) → show quality to win back users
- **seat_newcomers**: Moderately filled events (50-80%) → welcoming but not exclusive

### Matching Strategy
- **fill_the_table**: Event-centric (5-10 users per event) → batch filling
- **return_to_table**: User-centric (1 perfect event per user) → personalized reactivation
- **seat_newcomers**: User-centric (1 perfect first event per user) → critical first impression

### Message Tone
- **fill_the_table**: Energetic, scarcity-focused, action-oriented
- **return_to_table**: Warm, welcoming back, nostalgic
- **seat_newcomers**: Encouraging, welcoming, first-time friendly

---

## Technical Implementation

All scripts use:
- **MongoDB**: User and event data storage
- **Firebase**: Campaign data and message storage
- **Anthropic Claude API**: AI-powered matching and message generation
- **MongoDBPull Helper**: Enriched user/event data with campaign qualifications
- **FirebaseManager**: Centralized Firebase operations

## Data Flow

1. **Pull & Enrich**: Get users/events from MongoDB via `mongodb_pull` helper
2. **Filter**: Apply campaign-specific qualification filters
3. **Rank**: Sort by campaign-specific scoring (event_count, reactivation_score, newcomer_score)
4. **Match**: Generate AI-powered matches using Claude API
5. **Message**: Generate personalized SMS messages using Claude API
6. **Store**: Save matches and messages to Firebase
7. **Report**: Generate markdown report with campaign results
