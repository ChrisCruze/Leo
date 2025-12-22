# Event Profile Enrichment Pipeline - Step 4

## Overview

This document describes the event profile enrichment pipeline that transforms qualified events into enriched profiles with calculated metrics, participant insights, and comprehensive summaries for personalized messaging. The pipeline filters to essential fields, calculates participant demographics, extracts host information, detects low occupancy, and generates human-readable summaries.

## Event Schema (Before Enrichment)

The `qualified_events.json` file contains event data from the event selection pipeline with the following schema:

### Core Identity Fields
- `_id` (string): MongoDB ObjectId as string
- `id` (string): Event identifier (typically same as `_id`)
- `name` (string): Event name

### Date & Time Fields
- `startDate` (string): Event start date/time in ISO 8601 format with 'Z' timezone (e.g., "2025-12-28T22:00:00.000Z")
- `endDate` (string): Event end date/time in ISO 8601 format with 'Z' timezone

### Event Type & Status Fields
- `type` (string): Event type - "public" or "private"
- `eventStatus` (string): Event approval status (e.g., "approved", "canceled", "pending")
- `active` (boolean): Whether event is active

### Participant Fields
- `maxParticipants` (number): Maximum number of participants allowed
- `minParticipants` (number): Minimum number of participants required
- `participants` (array): List of participant email addresses
- `ownerId` (string): Event owner/creator user ID (MongoDB ObjectId)

### Venue Fields
- `venueId` (string): Venue identifier
- `venueName` (string): Name of the venue
- `neighborhood` (string): Event neighborhood location

### Content Fields
- `description` (string, nullable): Event description (may contain HTML tags)
- `categories` (array, nullable): Event categories (e.g., ["KARAOKE", "MEDITERRANEAN"])
- `features` (array, nullable): Event features (e.g., ["groups", "live-music", "hot-and-new"])

### Additional Fields
- `invitedParticipants` (array, optional): List of invited participant email addresses
- `notes` (string, nullable): Additional notes (may contain HTML)
- Various other fields from MongoDB schema

## Enriched Event Schema (After Enrichment)

The enriched event object contains the following fields, organized by category:

### Core Identity Fields

- **`id`** (string)
  - **Description**: Event identifier
  - **Type**: string
  - **Sample Value**: `"6927d356eb4f0aa02a6d14a2"`
  - **Generation**: Direct mapping from `_id` or `id` field

- **`name`** (string)
  - **Description**: Event name
  - **Type**: string
  - **Sample Value**: `"Holiday Karaoke"`
  - **Generation**: Direct mapping from `name` field

### Date & Time Fields

- **`startDate`** (string)
  - **Description**: Event start date/time in ISO 8601 format
  - **Type**: string
  - **Sample Value**: `"2025-12-28T22:00:00.000Z"`
  - **Generation**: Direct mapping from `startDate` field

- **`endDate`** (string)
  - **Description**: Event end date/time in ISO 8601 format
  - **Type**: string
  - **Sample Value**: `"2025-12-29T04:59:59.999Z"`
  - **Generation**: Direct mapping from `endDate` field

- **`day_of_week`** (string)
  - **Description**: Day of week extracted from startDate
  - **Type**: string
  - **Sample Value**: `"Friday"` or `"Monday"` or `"Sunday"`
  - **Generation**: Extracted from `startDate` using `datetime.strftime('%A')`. Returns day name (e.g., "Monday", "Friday", "Sunday") or `null` if startDate is invalid.

### Venue Fields

- **`venueName`** (string)
  - **Description**: Name of the venue
  - **Type**: string
  - **Sample Value**: `"Muses 35 Bar & Karaoke"`
  - **Generation**: Direct mapping from `venueName` field

- **`neighborhood`** (string)
  - **Description**: Event neighborhood location
  - **Type**: string
  - **Sample Value**: `"midtown-west"` or `"west-village"`
  - **Generation**: Direct mapping from `neighborhood` field

### Event Details Fields

- **`categories`** (array of strings)
  - **Description**: Event categories
  - **Type**: array of strings
  - **Sample Value**: `["KARAOKE"]` or `["MEDITERRANEAN"]`
  - **Generation**: Direct mapping from `categories` field. Empty array if missing.

- **`features`** (array of strings)
  - **Description**: Event features
  - **Type**: array of strings
  - **Sample Value**: `["groups", "live-music", "hot-and-new"]`
  - **Generation**: Direct mapping from `features` field. Empty array if missing.

- **`maxParticipants`** (number)
  - **Description**: Maximum number of participants allowed
  - **Type**: number
  - **Sample Value**: `10` or `8` or `7`
  - **Generation**: Direct mapping from `maxParticipants` field

- **`participant_count`** (number)
  - **Description**: Number of current participants
  - **Type**: number
  - **Sample Value**: `9` or `2` or `6`
  - **Generation**: Calculated as `len(participants)` array. Returns 0 if participants is missing or empty.

- **`description`** (string)
  - **Description**: Event description with HTML tags removed
  - **Type**: string
  - **Sample Value**: `"The best way to spread Christmas cheer is singing loud for all to hear!! Come celebrate Christmas and the holidays with us!! 🎶🎤🎄🎅🤶🌲🎁"`
  - **Generation**: HTML tags removed from original `description` field using regex pattern `r'<[^>]+>'`, then extra whitespace cleaned. Returns empty string if description is missing or null.

### Calculated Fields

- **`host_name`** (string)
  - **Description**: Full name of event host
  - **Type**: string or null
  - **Sample Value**: `"Sarah Johnson"` or `"John Smith"`
  - **Generation**: 
    1. Extract `ownerId` from event
    2. Look up `ownerId` in users lookup dictionary (keyed by `_id`)
    3. Extract `firstName` and `lastName` from host user object
    4. Construct full name: "FirstName LastName"
    5. Returns `null` if ownerId is missing or host user not found

- **`common_occupations`** (array of strings)
  - **Description**: Most common occupations among event participants
  - **Type**: array of strings
  - **Sample Value**: `["Finance", "Tech", "Consulting"]` or `["Product Designer", "Software Engineer"]`
  - **Generation**: 
    1. For each email in `participants` list, look up user in users_lookup_by_email
    2. Extract `occupation` field from each participant user
    3. Count occupation frequencies (excluding null/empty values)
    4. Return top 3-5 most common occupations
    5. Returns empty array if no participants or no occupations found

- **`common_interests`** (array of strings)
  - **Description**: Most common interests among event participants
  - **Type**: array of strings
  - **Sample Value**: `["live music", "karaoke", "socializing"]` or `["art", "music", "eatingOut"]`
  - **Generation**: 
    1. For each email in `participants` list, look up user in users_lookup_by_email
    2. Extract `interests` array from each participant user
    3. Flatten all interests into a single list
    4. Count interest frequencies across all participants (excluding null/empty values)
    5. Return top 3-5 most common interests
    6. Returns empty array if no participants or no interests found

- **`average_age`** (number or null)
  - **Description**: Average age of event participants (rounded to nearest integer)
  - **Type**: number or null
  - **Sample Value**: `32` or `28` or `null`
  - **Generation**: 
    1. For each email in `participants` list, look up user in users_lookup_by_email
    2. Extract `birthDay` field from each participant user
    3. Calculate age from birthDay (using current date, adjusted if birthday hasn't occurred this year)
    4. Calculate average of all participant ages
    5. Return rounded average age (integer) or `null` if no participants with valid ages

- **`has_low_occupancy`** (boolean)
  - **Description**: Whether event has very low occupancy
  - **Type**: boolean
  - **Sample Value**: `true` or `false`
  - **Generation**: 
    1. Calculate occupancy ratio: `participant_count / maxParticipants`
    2. Consider low occupancy if:
       - `occupancy_ratio < 0.3` (less than 30% full), OR
       - `participant_count < 3` AND `maxParticipants >= 10`
    3. Returns `true` if low occupancy, `false` otherwise

- **`participant_names`** (array of strings)
  - **Description**: List of participant names with occupations in parentheses if available
  - **Type**: array of strings
  - **Sample Value**: `["John Smith (Finance)", "Jane Doe (Tech)", "Bob Johnson"]` or `["Sarah Johnson", "Mike Chen"]`
  - **Generation**: 
    1. For each email in `participants` list, look up user in users_lookup_by_email
    2. Extract `firstName` and `lastName` from each participant user
    3. Construct full name: "FirstName LastName"
    4. If `occupation` is available and not empty, append in parentheses: "FirstName LastName (Occupation)"
    5. Returns array of formatted participant name strings
    6. Returns empty array if no participants or no names found

### Summary Field

- **`summary`** (string)
  - **Description**: Human-readable summary sentence including all most relevant fields for matching events to users and generating messages
  - **Type**: string
  - **Sample Value**: `"Holiday Karaoke is a karaoke event on Friday, Dec 28, 2025 at 10:00 PM at Muses 35 Bar & Karaoke in midtown-west, hosted by Sarah Johnson. The event has 9 participants out of 10 max capacity, including John Smith (Finance), Jane Doe (Tech), and Bob Johnson (Consulting). Common occupations of attendees include Finance, Tech, and Consulting. Common interests include live music, karaoke, and socializing. The average age of attendees is 32. The best way to spread Christmas cheer is singing loud for all to hear!! Come celebrate Christmas and the holidays with us!!"`
  - **Generation**: Constructed natural language sentence including:
    - Event name, day of week, date/time, venue, neighborhood, host name
    - Participant count vs max capacity
    - Participant names (first 3-5) with occupations in parentheses if available
    - Low occupancy mention if applicable (e.g., "This event currently has low attendance with only 2 participants")
    - Common occupations (top 3, with count if more)
    - Common interests (top 3, with count if more)
    - Average age of attendees
    - Cleaned description (truncated to 200 characters if long)
  - **Purpose**: Provides comprehensive context for event matching and message personalization

## Field Mapping

### Raw to Enriched Field Mappings

| Raw Field | Enriched Field | Transformation |
|-----------|---------------|----------------|
| `_id` or `id` | `id` | Direct mapping |
| `name` | `name` | Direct mapping |
| `startDate` | `startDate` | Direct mapping |
| `startDate` | `day_of_week` | Extract day name using datetime.strftime('%A') |
| `endDate` | `endDate` | Direct mapping |
| `venueName` | `venueName` | Direct mapping |
| `neighborhood` | `neighborhood` | Direct mapping |
| `categories` | `categories` | Direct mapping (empty array if missing) |
| `features` | `features` | Direct mapping (empty array if missing) |
| `maxParticipants` | `maxParticipants` | Direct mapping |
| `len(participants)` | `participant_count` | Calculate length of participants array |
| `description` | `description` | Remove HTML tags and clean whitespace |
| `ownerId` → user lookup | `host_name` | Look up ownerId in users, extract firstName + lastName |
| `participants` → user lookups | `common_occupations` | Extract occupations, count frequencies, return top 3-5 |
| `participants` → user lookups | `common_interests` | Extract interests, flatten, count frequencies, return top 3-5 |
| `participants` → user lookups | `average_age` | Extract birthDay, calculate ages, average and round |
| `participants` → user lookups | `participant_names` | Extract names and occupations, format as "Name (Occupation)" |
| `participant_count`, `maxParticipants` | `has_low_occupancy` | Calculate occupancy ratio, apply low occupancy criteria |

## HTML Cleaning Logic

HTML tags are removed from the `description` field using the following process:

1. **Regex Pattern**: Use regex pattern `r'<[^>]+>'` to match and remove all HTML tags
2. **Whitespace Cleaning**: Clean up extra whitespace by splitting on whitespace and rejoining with single spaces
3. **Null Handling**: Return empty string if description is missing or null

**Example**:
- Input: `"<p>The best way to spread Christmas cheer is singing loud for all to hear!!</p><p><br></p><p>Come celebrate Christmas and the holidays with us!! 🎶🎤🎄🎅🤶🌲🎁</p>"`
- Output: `"The best way to spread Christmas cheer is singing loud for all to hear!! Come celebrate Christmas and the holidays with us!! 🎶🎤🎄🎅🤶🌲🎁"`

## Host Name Extraction Logic

Event host names are extracted by:

1. **Owner ID Extraction**: Get `ownerId` field from event (MongoDB ObjectId string)
2. **User Lookup**: Look up `ownerId` in users lookup dictionary (keyed by `_id`)
3. **Name Construction**: Extract `firstName` and `lastName` from host user object
4. **Full Name**: Construct full name as "FirstName LastName"
5. **Fallback**: If firstName or lastName is missing, use available name or existing `name` field
6. **Result**: Return host name string or `null` if ownerId is missing or host user not found

## Common Occupations Calculation Logic

Common occupations are calculated from event participants:

1. **Participant Iteration**: For each email in event's `participants` list
2. **User Lookup**: Look up email in users_lookup_by_email dictionary
3. **Occupation Extraction**: Extract `occupation` field from participant user
4. **Filtering**: Keep only non-null, non-empty occupation strings
5. **Frequency Counting**: Count how many times each occupation appears
6. **Top Selection**: Return top 3-5 most common occupations (sorted by frequency)
7. **Result**: Returns array of occupation strings, or empty array if no occupations found

**Example**: If 5 participants have occupations ["Finance", "Tech", "Finance", "Consulting", "Tech"], result would be `["Finance", "Tech", "Consulting"]` (Finance and Tech appear twice, Consulting once).

## Common Interests Calculation Logic

Common interests are calculated from event participants:

1. **Participant Iteration**: For each email in event's `participants` list
2. **User Lookup**: Look up email in users_lookup_by_email dictionary
3. **Interests Extraction**: Extract `interests` array from participant user
4. **Flattening**: Flatten all interests from all participants into a single list
5. **Filtering**: Keep only non-null, non-empty interest strings
6. **Frequency Counting**: Count how many times each interest appears across all participants
7. **Top Selection**: Return top 3-5 most common interests (sorted by frequency)
8. **Result**: Returns array of interest strings, or empty array if no interests found

**Example**: If 3 participants have interests [["music", "art"], ["music", "travel"], ["art", "food"]], flattened list is ["music", "art", "music", "travel", "art", "food"], and result would be `["music", "art", "travel", "food"]` (music and art appear twice, travel and food once).

## Average Age Calculation Logic

Average age is calculated from event participants:

1. **Participant Iteration**: For each email in event's `participants` list
2. **User Lookup**: Look up email in users_lookup_by_email dictionary
3. **Birthday Extraction**: Extract `birthDay` field from participant user (ISO 8601 date string)
4. **Age Calculation**: Calculate age from birthDay:
   - Parse birthDay to datetime object
   - Get current date/time
   - Calculate years difference
   - Adjust if birthday hasn't occurred this year (subtract 1)
5. **Age Collection**: Collect all valid ages (non-null)
6. **Average Calculation**: Calculate average of all participant ages
7. **Rounding**: Round to nearest integer
8. **Result**: Returns rounded average age (integer) or `null` if no participants with valid ages

## Low Occupancy Detection Logic

Low occupancy is determined using the following criteria:

1. **Occupancy Ratio Calculation**: Calculate `participant_count / maxParticipants`
2. **Low Occupancy Conditions**: Event has low occupancy if:
   - `occupancy_ratio < 0.3` (less than 30% full), OR
   - `participant_count < 3` AND `maxParticipants >= 10`
3. **Result**: Returns `true` if low occupancy, `false` otherwise

**Examples**:
- Event with 2 participants and maxParticipants of 10: `2/10 = 0.2 < 0.3` → `has_low_occupancy = true`
- Event with 2 participants and maxParticipants of 5: `2/5 = 0.4 >= 0.3` AND `2 >= 3` is false → `has_low_occupancy = false`
- Event with 1 participant and maxParticipants of 10: `1 < 3` AND `10 >= 10` → `has_low_occupancy = true`

## Day of Week Extraction Logic

Day of week is extracted from startDate:

1. **Date Parsing**: Parse `startDate` ISO 8601 string to datetime object
2. **Day Extraction**: Use `datetime.strftime('%A')` to get day name
3. **Result**: Returns day name string (e.g., "Monday", "Friday", "Sunday") or `null` if startDate is invalid

**Example**: 
- Input: `"2025-12-28T22:00:00.000Z"` (December 28, 2025)
- Output: `"Sunday"` (December 28, 2025 is a Sunday)

## Participant Names Extraction Logic

Participant names are extracted with occupations:

1. **Participant Iteration**: For each email in event's `participants` list
2. **User Lookup**: Look up email in users_lookup_by_email dictionary
3. **Name Extraction**: Extract `firstName` and `lastName` from participant user
4. **Name Construction**: Construct full name as "FirstName LastName"
5. **Occupation Check**: If `occupation` is available and not empty:
   - Format as "FirstName LastName (Occupation)"
6. **Otherwise**: Format as "FirstName LastName"
7. **Result**: Returns array of formatted participant name strings

**Example**: 
- Participant 1: firstName="John", lastName="Smith", occupation="Finance" → `"John Smith (Finance)"`
- Participant 2: firstName="Jane", lastName="Doe", occupation=null → `"Jane Doe"`
- Result: `["John Smith (Finance)", "Jane Doe"]`

## Summary Generation Logic

The summary field is generated by constructing a natural language sentence that includes all most relevant fields for event matching and message personalization:

### Summary Components (in order):

1. **Introduction**: Event name, category, day of week, date/time, venue, neighborhood, host name
2. **Participant Information**: Participant count vs max capacity, participant names (first 3-5) with occupations
3. **Low Occupancy Mention**: If applicable, mention low attendance
4. **Common Occupations**: Top 3 occupations, with count if more
5. **Common Interests**: Top 3 interests, with count if more
6. **Average Age**: Average age of attendees
7. **Description**: Cleaned description (truncated to 200 characters if long)

### Summary Generation Rules:

- Fields are included only if they have values
- Lists are truncated to 3-5 items with count if longer
- Dates are formatted as "Friday, Dec 28, 2025 at 10:00 PM"
- Participant names include up to 5 names with occupations in parentheses if available
- Description is truncated to 200 characters if too long
- Handles missing fields gracefully

### Example Summary:

"Holiday Karaoke is a karaoke event on Friday, Dec 28, 2025 at 10:00 PM at Muses 35 Bar & Karaoke in midtown-west, hosted by Sarah Johnson. The event has 9 participants out of 10 max capacity, including John Smith (Finance), Jane Doe (Tech), and Bob Johnson (Consulting). Common occupations of attendees include Finance, Tech, and Consulting. Common interests include live music, karaoke, and socializing. The average age of attendees is 32. The best way to spread Christmas cheer is singing loud for all to hear!! Come celebrate Christmas and the holidays with us!!"

## Results

*Results from pipeline execution will be updated after script execution*

### Enrichment Statistics

*To be populated after running the pipeline*

### Sample Enriched Event Objects

*To be populated after running the pipeline*


