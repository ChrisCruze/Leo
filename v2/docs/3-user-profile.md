# User Profile Enrichment Pipeline - Step 3

## Overview

This document describes the user profile enrichment pipeline that transforms qualified users into enriched profiles with calculated metrics, event associations, social connections, and comprehensive summaries for personalized messaging. The pipeline filters to essential fields, calculates derived metrics, associates event history, identifies friends, and generates human-readable summaries.

## Enriched User Schema

The enriched user object contains the following fields, organized by category:

### Core Identity Fields

- **`id`** (string)
  - **Description**: User identifier (from `_id` or `id` field in raw user data)
  - **Type**: string
  - **Sample Value**: `"5de5a0d93946c65ee0f3b149"`
  - **Generation**: Direct mapping from `_id` or `id` field

- **`name`** (string)
  - **Description**: User's full name
  - **Type**: string
  - **Sample Value**: `"Aleksandar Tisinovic"`
  - **Generation**: Constructed from `firstName + " " + lastName`. Falls back to existing `name` field if firstName/lastName are missing.

- **`email`** (string)
  - **Description**: User's email address
  - **Type**: string
  - **Sample Value**: `"atisinovic@gmail.com"`
  - **Generation**: Direct mapping from `email` field

### Profile Fields

- **`interests`** (array of strings)
  - **Description**: User's interests for event matching
  - **Type**: array of strings
  - **Sample Value**: `["art", "music", "eatingOut", "travel"]`
  - **Generation**: Direct mapping from `interests` field

- **`cuisine_preferences`** (array of strings)
  - **Description**: User's preferred cuisines
  - **Type**: array of strings
  - **Sample Value**: `["Japanese", "Italian", "Mediterranean"]`
  - **Generation**: Direct mapping from `preferredCuisines` field. Empty array if field is missing.

- **`dietary_restrictions`** (array of strings)
  - **Description**: User's dietary restrictions/allergies
  - **Type**: array of strings
  - **Sample Value**: `["gluten-free", "vegetarian"]`
  - **Generation**: Direct mapping from `allergies` field. Empty array if field is missing.

- **`table_type_preference`** (string)
  - **Description**: User's preferred table type
  - **Type**: string
  - **Sample Value**: `"social"` or `"intimate"` or `"both"`
  - **Generation**: Direct mapping from `tableTypePreference` field

- **`relationship_status`** (string)
  - **Description**: User's relationship status
  - **Type**: string
  - **Sample Value**: `"single"` or `"married"` or `"other"`
  - **Generation**: Direct mapping from `relationshipStatus` field

- **`occupation`** (string)
  - **Description**: User's occupation
  - **Type**: string
  - **Sample Value**: `"Finance"` or `"Tech Founder"` or `"Professional"`
  - **Generation**: Direct mapping from `occupation` field

- **`gender`** (string)
  - **Description**: User's gender
  - **Type**: string
  - **Sample Value**: `"male"` or `"female"` or `"other"`
  - **Generation**: Direct mapping from `gender` field

- **`homeNeighborhood`** (string)
  - **Description**: User's home neighborhood
  - **Type**: string
  - **Sample Value**: `"midtown-east"` or `"hells-kitchen"` or `"west-village"`
  - **Generation**: Direct mapping from `homeNeighborhood` field

- **`workNeighborhood`** (string)
  - **Description**: User's work neighborhood
  - **Type**: string
  - **Sample Value**: `"financial-district"` or `"soho"`
  - **Generation**: Direct mapping from `workNeighborhood` field

### Calculated Fields

- **`age`** (number or null)
  - **Description**: User's age calculated from birthDay
  - **Type**: number or null
  - **Sample Value**: `29` or `null`
  - **Generation**: Calculated from `birthDay` ISO 8601 date string. Returns `null` if birthDay is missing or invalid. Age is adjusted if birthday hasn't occurred this year.

- **`event_count`** (number)
  - **Description**: Number of events user has attended
  - **Type**: number
  - **Sample Value**: `6` or `0`
  - **Generation**: Count of events where user's email appears in `participants` list

- **`last_event_date`** (string or null)
  - **Description**: Most recent event startDate in ISO 8601 format
  - **Type**: string (ISO 8601) or null
  - **Sample Value**: `"2025-11-18T20:00:00.000Z"` or `null`
  - **Generation**: Most recent `startDate` from user's associated events, sorted by date. Returns `null` if user has no events.

- **`days_since_last_event`** (number or null)
  - **Description**: Days since user's last attended event
  - **Type**: number or null
  - **Sample Value**: `15` or `null`
  - **Generation**: Calculated as difference between current date and `last_event_date`. Returns `null` if user has never attended events.

- **`days_since_signup`** (number or null)
  - **Description**: Days since user account creation
  - **Type**: number or null
  - **Sample Value**: `120` or `null`
  - **Generation**: Calculated from `createdAt` ISO 8601 date string. Returns `null` if createdAt is missing or invalid.

- **`historical_event_names`** (array of strings)
  - **Description**: List of event names user has attended
  - **Type**: array of strings
  - **Sample Value**: `["Holiday Karaoke", "Mexican Brunch", "NYE Dinner"]`
  - **Generation**: Extracted from `name` field of all events where user's email appears in `participants` list

- **`event_hosts`** (array of strings)
  - **Description**: List of unique host names for events user has attended
  - **Type**: array of strings
  - **Sample Value**: `["Sarah Johnson", "Mike Chen"]`
  - **Generation**: For each event user attended, looks up `ownerId` in users lookup dictionary, extracts firstName + lastName, and returns unique host names

- **`invited_event_names`** (array of strings)
  - **Description**: List of event names from qualified_events.json where user appears in invitedParticipants
  - **Type**: array of strings
  - **Sample Value**: `["Holiday Karaoke", "NYE Dinner + Midnight Champagne Toast"]`
  - **Generation**: Checks each qualified event's `invitedParticipants` list for user's email, extracts event `name` for matches

- **`friends`** (array of strings)
  - **Description**: List of friend names with shared event count in parentheses
  - **Type**: array of strings
  - **Sample Value**: `["John Smith (3)", "Sarah Johnson (2)"]`
  - **Generation**: Identifies other participants who share 2+ events with user, counts shared events, formats as "Name (count)". Sorted by frequency (most shared events first).

### User Status Fields (Boolean)

- **`is_new_user`** (boolean)
  - **Description**: Whether user signed up within last 30 days
  - **Type**: boolean
  - **Sample Value**: `true` or `false`
  - **Generation**: `true` if `days_since_signup <= 30`, `false` otherwise

- **`has_never_attended_events`** (boolean)
  - **Description**: Whether user has never attended any events
  - **Type**: boolean
  - **Sample Value**: `true` or `false`
  - **Generation**: `true` if `event_count == 0`, `false` otherwise

- **`hasnt_attended_in_60_days`** (boolean or null)
  - **Description**: Whether user hasn't attended an event in over 60 days
  - **Type**: boolean or null
  - **Sample Value**: `true` or `false` or `null`
  - **Generation**: `true` if `days_since_last_event > 60`, `false` if `days_since_last_event <= 60`, `null` if user has never attended events

- **`signed_up_online`** (boolean)
  - **Description**: Whether user signed up online (indicated by role == "POTENTIAL")
  - **Type**: boolean
  - **Sample Value**: `true` or `false`
  - **Generation**: `true` if `role == "POTENTIAL"`, `false` otherwise

- **`recently_attended_last_week`** (boolean or null)
  - **Description**: Whether user attended an event within last 7 days
  - **Type**: boolean or null
  - **Sample Value**: `true` or `false` or `null`
  - **Generation**: `true` if `days_since_last_event <= 7`, `false` if `days_since_last_event > 7`, `null` if user has never attended events

### User Status Fields (Categorical)

- **`primary_status`** (string)
  - **Description**: Primary user status indicating most relevant user state
  - **Type**: string (one of: "new_user", "never_attended", "dormant_60_days", "active_recent", "signed_up_online", "active_regular")
  - **Sample Value**: `"active_regular"` or `"new_user"` or `"dormant_60_days"`
  - **Generation**: Determined by priority order:
    1. `"signed_up_online"` if `signed_up_online == true`
    2. `"new_user"` if `is_new_user == true`
    3. `"never_attended"` if `has_never_attended_events == true`
    4. `"active_recent"` if `recently_attended_last_week == true`
    5. `"dormant_60_days"` if `hasnt_attended_in_60_days == true`
    6. `"active_regular"` (default)

- **`engagement_tier`** (string)
  - **Description**: User's engagement level
  - **Type**: string (one of: "high", "medium", "low")
  - **Sample Value**: `"high"` or `"medium"` or `"low"`
  - **Generation**: 
    - `"high"`: `event_count >= 10` OR `recently_attended_last_week == true`
    - `"medium"`: `event_count >= 3` OR (`event_count > 0` AND `days_since_last_event <= 30`)
    - `"low"`: `event_count == 0` OR `days_since_last_event > 60`

- **`user_segment`** (string)
  - **Description**: Combined user segment for messaging strategy
  - **Type**: string (one of: "new_online_signup", "new_app_user", "first_timer", "active_regular", "dormant", "churned")
  - **Sample Value**: `"active_regular"` or `"new_online_signup"` or `"dormant"`
  - **Generation**: 
    - `"new_online_signup"`: `signed_up_online == true` AND `is_new_user == true`
    - `"new_app_user"`: `is_new_user == true` AND `signed_up_online == false`
    - `"first_timer"`: `has_never_attended_events == true` AND `is_new_user == false`
    - `"active_regular"`: `recently_attended_last_week == true` OR (`event_count >= 3` AND `days_since_last_event <= 30`)
    - `"dormant"`: `hasnt_attended_in_60_days == true` AND `event_count > 0`
    - `"churned"`: `hasnt_attended_in_60_days == true` AND `event_count == 0`
    - `"active_regular"` (default)

### Summary Field

- **`summary`** (string)
  - **Description**: Human-readable summary sentence including all most relevant fields for matching users to events and generating messages
  - **Type**: string
  - **Sample Value**: `"Alex is a 29-year-old male product designer in Williamsburg who joined in March 2024. He enjoys live music and fitness, prefers Japanese and Italian food, and typically likes communal tables. He has attended 6 events, most recently on Nov 18, 2025, and is an active regular user. He frequently attends events hosted by Sarah Johnson and has been invited to 2 upcoming events."`
  - **Generation**: Constructed natural language sentence including:
    - Name, age, gender, occupation, neighborhood(s), join date
    - Interests (up to 3, with count if more)
    - Cuisine preferences (up to 3, with count if more)
    - Dietary restrictions (if any)
    - Table preference
    - Event count and last event date
    - Engagement status (user_segment)
    - Preferred hosts (if any, up to 2)
    - Invited events context (if any)
  - **Purpose**: Provides comprehensive context for event matching and message personalization

## Field Mapping

### Raw to Enriched Field Mappings

| Raw Field | Enriched Field | Transformation |
|-----------|---------------|----------------|
| `_id` or `id` | `id` | Direct mapping |
| `firstName + lastName` | `name` | Concatenation with space |
| `email` | `email` | Direct mapping |
| `interests` | `interests` | Direct mapping |
| `preferredCuisines` | `cuisine_preferences` | Direct mapping (empty array if missing) |
| `allergies` | `dietary_restrictions` | Direct mapping (empty array if missing) |
| `tableTypePreference` | `table_type_preference` | Direct mapping |
| `relationshipStatus` | `relationship_status` | Direct mapping |
| `occupation` | `occupation` | Direct mapping |
| `gender` | `gender` | Direct mapping |
| `homeNeighborhood` | `homeNeighborhood` | Direct mapping |
| `workNeighborhood` | `workNeighborhood` | Direct mapping |

## Event Association Logic

### How Events are Matched to Users

Events are associated with users by matching the user's email address with the `participants` list in each event:

1. **Email Matching**: For each event, check if user's email appears in the event's `participants` array
2. **Sorting**: Associated events are sorted by `startDate` in descending order (most recent first)
3. **Result**: Returns list of all events where user email is found in participants

### Event Host Extraction

Event hosts are identified by:

1. **Owner ID Lookup**: For each event user attended, extract `ownerId` field
2. **User Lookup**: Look up `ownerId` in users lookup dictionary (keyed by `_id`)
3. **Name Construction**: Extract `firstName` and `lastName` from host user object
4. **Deduplication**: Return unique list of host names

### Invited Events Extraction

Invited events are identified by:

1. **Email Matching**: For each qualified event, check if user's email appears in `invitedParticipants` array
2. **Name Extraction**: Extract event `name` for matching events
3. **Result**: Returns list of invited event names from qualified_events.json

## Friends Identification Logic

Friends are identified based on shared event frequency:

1. **Event Association**: Find all events user attended (using email matching)
2. **Participant Extraction**: For each event, get all other participants (excluding user)
3. **Frequency Counting**: Count how many times each other participant appears across all user's events
4. **Threshold Filtering**: Keep only participants who share 2+ events with user
5. **Formatting**: Format as "Name (count)" where count is number of shared events
6. **Sorting**: Sort by frequency (most shared events first)

**Example**: If user attended 5 events with "John Smith" and 3 events with "Sarah Johnson", friends list would be: `["John Smith (5)", "Sarah Johnson (3)"]`

## Summary Generation Logic

The summary field is generated by constructing a natural language sentence that includes all most relevant fields for event matching and message personalization:

### Summary Components (in order):

1. **Introduction**: Name, age, gender, occupation, neighborhood(s), join date
2. **Interests**: Up to 3 interests, with count if more (e.g., "art, music, travel and 2 more")
3. **Cuisine Preferences**: Up to 3 cuisines, with count if more
4. **Dietary Restrictions**: All restrictions listed if any
5. **Table Preference**: Table type preference
6. **Event History**: Event count and last event date
7. **Engagement Status**: User segment description (e.g., "an active regular user")
8. **Preferred Hosts**: Up to 2 host names, with count if more
9. **Invited Events**: Count of invited events if any

### Summary Generation Rules:

- Fields are included only if they have values
- Lists are truncated to 3 items with count if longer
- Dates are formatted as "Nov 18, 2025"
- Join dates are formatted as "March 2024"
- Handles missing fields gracefully

## Results

*Results from pipeline execution will be updated after script execution*

### Enrichment Statistics

*To be populated after running the pipeline*

### Sample Enriched User Objects

*To be populated after running the pipeline*

