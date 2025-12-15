# Firebase Manager

Shared Firebase operations module for campaign scripts (`fill-the-table`, `return-to-table`, `seat-newcomers`).

## Purpose

Centralizes Firebase operations to:
- Reduce code duplication across campaign scripts
- Ensure consistent data structure
- Support local testing mode (save to files instead of Firebase)
- Handle campaign field merging for shared users/events
- Only save required fields (optimized for dashboard)

## Usage

### Basic Usage

```python
from helpers.firebase_manage.firebase_manager import FirebaseManager

# Initialize in campaign __init__
self.firebase_manager = FirebaseManager(
    firebase_url=self.firebase_url,
    base_path=self.firebase_base_path,
    save_local=False,  # Set to True for local testing
    local_data_dir=self.data_output_dir,
    logger_instance=self.logger
)

# Save users and events (handles campaign merging automatically)
self.firebase_manager.save_user(user, self.campaign_name)
self.firebase_manager.save_event(event, self.campaign_name)

# Save matches and messages (appends to arrays)
self.firebase_manager.save_match(match)
self.firebase_manager.save_message(message)
```

### Local Testing Mode

Enable local testing by setting `SAVE_LOCAL=true` environment variable:

```bash
export SAVE_LOCAL=true
python campaigns/fill-the-table/fill_the_table.py
```

When `save_local=True`, data is saved to:
- `{campaign_data_dir}/output/users.json` (object with user_id keys)
- `{campaign_data_dir}/output/events.json` (object with event_id keys)
- `{campaign_data_dir}/output/matches.json` (array structure matching Firebase)
- `{campaign_data_dir}/output/messages.json` (array structure matching Firebase)

## Features

### Campaign Field Merging

When a user or event is saved by multiple campaigns, the `campaign` field is automatically merged:
- If existing: `campaign: ['fill-the-table']`
- New save from `return-to-table`: `campaign: ['fill-the-table', 'return-to-table']`
- Handles both string and array formats

### Required Fields Only

Only saves fields needed by the dashboard:
- **Users**: id, firstName, lastName, name, email, homeNeighborhood, gender, occupation, interests, journey_stage, value_segment, event_count, summary, campaign, updatedAt
- **Events**: id, name, startDate, maxParticipants, participantCount, participationPercentage, neighborhood, categories, features, venueName, type, summary, campaign, updatedAt
- **Matches**: user_name, event_name, user_id, event_id, confidence_percentage, reasoning, matched_at, campaign, updatedAt
- **Messages**: message_text, user_name, user_email, user_phone, event_name, event_id, similarity_score/confidence_percentage, reasoning, status, campaign, generated_at, updatedAt

### Node Identifiers

- Users: Saved as `/Leo/users/{user_id}` (individual nodes)
- Events: Saved as `/Leo/events/{event_id}` (individual nodes)
- Matches: Saved as `/Leo/matches` (array structure)
- Messages: Saved as `/Leo/messages` (array structure)

## Methods

### `save_user(user, campaign_name)`
Save or update user node. Handles campaign merging automatically.

### `save_event(event, campaign_name)`
Save or update event node. Handles campaign merging automatically.

### `save_match(match)`
Append match to matches array. Ensures required fields are present.

### `save_message(message)`
Append message to messages array. Ensures required fields are present.

## Notes

- User and event summaries are ALWAYS included (required for reporting)
- Campaign field is always an array (supports multiple campaigns per user/event)
- Local mode saves data in same structure as Firebase for easy testing
- All methods handle ObjectId conversion automatically

