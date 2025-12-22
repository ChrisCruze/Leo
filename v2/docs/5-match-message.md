# User-Event Matching and Message Generation Pipeline - Step 5

## Overview

This document describes the user-event matching and message generation pipeline that matches enriched users to enriched events using Claude AI, generates personalized SMS messages, quality checks them, and uploads results to Airtable. The pipeline determines the appropriate campaign type for each user and generates engaging, witty messages optimized for conversion.

## Pipeline Workflow

The pipeline follows this step-by-step process:

1. **Load Data**: Load enriched users from `enriched_users.json` and enriched events from `enriched_events.json`
2. **Match User to Event**: For each user, use Claude AI to find the ideal event match and determine campaign type
3. **Generate Message**: Use Claude AI to generate a personalized, witty SMS message based on the match
4. **Quality Check**: Use Claude AI to validate the message for best practices and accuracy
5. **Save Results**: Save all processed messages to `processed_messages.json`
6. **Upload to Airtable**: Upload each message record to Airtable Messages table

## Prompts

All prompts are defined at the top of `step5_match_message.py` for easy modification.

### Matching Prompt

The matching prompt instructs Claude AI to:
- Find the SINGLE BEST event for the user
- Determine the appropriate campaign type based on user profile
- Consider interest alignment, location proximity, event quality, and timing
- Return JSON with `event_index`, `campaign`, `reasoning`, and `confidence`

**Key Features:**
- Analyzes user summary and all event summaries
- Determines campaign type based on user's event history
- Prioritizes interest alignment as the most critical factor
- Returns confidence score (0-100)

### Message Generation Prompt

The message generation prompt instructs Claude AI to:
- Generate a funny, witty, interesting SMS message
- Adapt tone based on campaign type
- Follow SMS best practices (length, structure, CTA)
- Comply with Twilio rules (banned words, emoji limits)
- Return JSON with `message`, `reasoning`, and `confidence`

**Key Features:**
- Campaign-specific tone:
  - "Seat The Newcomer": Warm, welcoming, encouraging
  - "Fill the Table": Urgent, scarcity-driven, social proof
  - "Return to Table": Warm, nostalgic, friend-like
- Personalization based on user interests, location, occupation
- Event link automatically appended (not included in generated message)
- Creative and engaging to stand out

### Quality Check Prompt

The quality check prompt instructs Claude AI to:
- Validate message length (<180 chars including link)
- Check tone matches campaign type and best practices
- Verify accuracy of all details (event name, date, venue)
- Ensure proper personalization and clarity
- Validate Twilio compliance
- Return JSON with `quality_score`, `approved`, `issues`, and `improved_message`

**Key Features:**
- Comprehensive checklist of SMS best practices
- Accuracy validation for event details
- Provides improved message if issues found
- Quality score (0-100) for tracking

## Campaign Types

The pipeline determines one of three campaign types for each user:

### "Seat The Newcomer"

**When Used:**
- User has attended 0-2 events (`event_count <= 2`)

**Objective:**
- Convert newcomers to their first event attendance
- Welcome them warmly and make them excited

**Event Selection:**
- Prefer events with good participation (50-80% filled) - shows quality without being exclusive
- Beginner-friendly events with welcoming descriptions
- Events in or near user's neighborhood for convenience

**Message Tone:**
- Warm, welcoming, encouraging
- Welcome them to the community
- Emphasize beginner-friendly nature
- Create excitement about first event

### "Fill the Table"

**When Used:**
- Event has low occupancy (`has_low_occupancy = true`)
- Goal is to fill underbooked events

**Objective:**
- Drive RSVPs to fill events that need more participants
- Create urgency and emphasize scarcity

**Event Selection:**
- Events with low participation that need filling
- Events starting soon (creates urgency)
- Interest alignment is still critical

**Message Tone:**
- Urgent, scarcity-driven
- Emphasize spots left and time urgency
- Use social proof (mention participants already in)
- Motivate immediate action

### "Return to Table"

**When Used:**
- User has been inactive for 31+ days (`days_since_last_event >= 31`)
- OR user has `hasnt_attended_in_60_days = true`

**Objective:**
- Re-engage dormant users
- Drive RSVPs to high-quality events

**Event Selection:**
- Prefer events with high participation (50-100% filled) - shows quality
- Events similar to user's past attendance patterns
- Events in or near user's neighborhood
- Events happening soon (creates urgency for reactivation)

**Message Tone:**
- Warm, welcoming, nostalgic
- Acknowledge time away without being pushy
- Highlight quality and social proof
- Welcome them back warmly

## Matching Logic

Claude AI determines the ideal event match using the following criteria (in order of importance):

1. **Interest Alignment** (Critical): User interests must align with event categories/features
2. **Campaign Appropriateness**: Campaign type must fit user's profile
3. **Location Proximity**: Prefer events in or near user's neighborhood
4. **Event Quality**: For reactivation and newcomers, prefer events with good participation
5. **Event Urgency**: For filling tables, prioritize low-occupancy events
6. **Event Timing**: Prefer events happening soon

The matching process:
1. Formats user summary and all event summaries as numbered list
2. Sends to Claude AI with matching prompt
3. Parses JSON response with `event_index`, `campaign`, `reasoning`, `confidence`
4. Returns matched event object and match result

## Message Generation Logic

Claude AI generates personalized messages using:

1. **User Context**: User summary with interests, location, occupation, event history
2. **Event Context**: Event summary with details, participants, host, timing
3. **Campaign Context**: Campaign type and objective
4. **Match Reasoning**: Why this match was made

The message generation process:
1. Formats message generation prompt with all context
2. Calls Claude AI with temperature 0.9 (more creative for witty messages)
3. Parses JSON response with `message`, `reasoning`, `confidence`
4. Appends event link: `https://cucu.li/bookings/{event_id}`
5. Returns message result

**Message Structure:**
- Greeting + Name
- Hook tied to interests/occupation/location/campaign
- Event details + urgency + social proof
- Clear CTA (link appended automatically)

## Quality Check Logic

Claude AI validates messages by checking:

1. **Length**: Under 180 characters (accounting for appended link)
2. **Tone**: Matches campaign type and SMS best practices
3. **Accuracy**: All details correct (event name, date, venue, etc.)
4. **Personalization**: References user interests, location, or relevant details
5. **Clarity**: Message is clear and easy to understand
6. **CTA**: Ends with clear call-to-action
7. **Twilio Compliance**: No banned words, proper length for emoji count
8. **Engagement**: Message is funny, witty, interesting, or engaging

The quality check process:
1. Formats quality check prompt with message and context
2. Calls Claude AI with temperature 0.7 (more analytical)
3. Parses JSON response with `quality_score`, `approved`, `issues`, `improved_message`
4. Uses improved message if provided and original wasn't approved
5. Returns quality check result

## Airtable Integration

Messages are uploaded to Airtable using the `airtable_crud` utility.

### Field Mappings

The following fields are mapped from message records to Airtable:

| Local Field | Airtable Field | Description |
|-------------|----------------|-------------|
| `user_name` | `user_name` | User's full name |
| `event_name` | `event_name` | Event name |
| `user_id` | `user_id` | User ID |
| `event_id` | `event_id` | Event ID |
| `user_email` | `user_email` | User email |
| `user_phone` | `user_phone` | User phone |
| `user_summary` | `user_summary` | User summary |
| `event_summary` | `event_summary` | Event summary |
| `message` | `message` | Generated message text |
| `reasoning` | `reasoning` | Match reasoning |
| `match_reasoning` | `reasoning` | Match reasoning (alternative) |
| `message_reasoning` | `reasoning` | Message generation reasoning |
| `confidence_percentage` | `confidence_percentage` | Confidence score |
| `campaign` | `campaign` | Campaign type |

### Upload Process

1. Message record is created with all required fields
2. Fields are mapped using `MESSAGES_FIELD_MAPPING`
3. Record is created in Airtable Messages table via `create_message_record()`
4. Success status and record ID are returned

## Utility Scripts

The pipeline uses two utility scripts for reusability:

### `utils/ai_prompt.py`

Provides reusable functions for Claude AI operations:
- `call_claude()`: Calls Claude AI API and returns response text
- `parse_json_response()`: Parses JSON from Claude response with fallbacks
- `generate_with_quality_check()`: Generates content and runs quality check

**Features:**
- Handles API key from environment (`ANTHROPIC_API_KEY`)
- Comprehensive JSON parsing with multiple fallback strategies
- Logging integration for prompts and responses
- Error handling for API calls

### `utils/airtable_crud.py`

Provides reusable functions for Airtable CRUD operations:
- `create_message_record()`: Creates a message record in Airtable
- `get_message_record()`: Gets a message record by ID
- `update_message_record()`: Updates a message record
- `delete_message_record()`: Deletes a message record

**Features:**
- Field mapping according to `MESSAGES_FIELD_MAPPING`
- Error handling for API calls
- Logging integration
- Uses credentials from airtable_sync.py constants

## Data Persistence

### Processed Messages JSON

All processed messages are saved to `data/processed/processed_messages.json` in addition to being uploaded to Airtable.

**File Format:**
- JSON array of message record objects
- Each record contains all fields: user info, event info, message, match details, campaign, quality check response
- Saved after all users are processed

**Purpose:**
- Local backup of all generated messages
- Easy access for analysis and debugging
- Version control of message generation results

## Results

*Results from pipeline execution will be updated after script execution*

### Pipeline Statistics

*To be populated after running the pipeline*

### Sample Message Records

*To be populated after running the pipeline*

## Environment Setup

### Required Environment Variables

- `ANTHROPIC_API_KEY`: Must be set at root level for Claude AI API access

### Dependencies

- Standard library: `json`, `logging`, `os`, `pathlib`, `datetime`, `typing`
- External: `anthropic`, `pyairtable`
- Internal utilities: `utils.ai_prompt`, `utils.airtable_crud`

## Execution

Run the pipeline with:

```bash
cd leo-dev
python pipeline/step5_match_message.py
```

The script will:
1. Load enriched users and events
2. Process each user through the full pipeline
3. Save all processed messages to `processed_messages.json`
4. Upload messages to Airtable
5. Generate comprehensive log file in `logs/` folder


