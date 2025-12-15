# MongoDB Pull and Enrichment Helper

A comprehensive Python module for MongoDB data retrieval, user enrichment, event transformation, and summary generation. This module consolidates functionality from multiple campaign scripts into a single reusable helper.

## Overview

The `mongodb_pull` module provides:

- **MongoDB Connection Management**: Simplified connection to MongoDB with hardcoded credentials
- **Data Retrieval**: Fetch users, events, and orders from MongoDB collections
- **User Enrichment**: Transform raw user data with calculated fields, segments, scores, and social connections
- **Event Transformation**: Enrich events with participant analysis and demographics
- **Campaign Qualification**: Determine user and event eligibility for marketing campaigns
- **Summary Generation**: Create human-readable summaries for personalization
- **Report Generation**: Generate timestamped markdown reports with aggregate metrics and segment distributions

## Installation

### Requirements

- Python 3.7+
- `pymongo` library
- MongoDB connection credentials (hardcoded in module)

### Setup

```bash
# Install dependencies
pip install pymongo

# The module is ready to use - credentials are hardcoded
```

## Quick Start

```python
from helpers.mongodb_pull import MongoDBPull

# Initialize the pull helper
pull = MongoDBPull()

# Get enriched users
users = pull.users_pull(limit=100)

# Get enriched events
events = pull.events_pull(limit=50)

# Close connection when done
pull.close()
```

## API Reference

### Main Class: `MongoDBPull`

The main orchestrator class that provides high-level methods for data retrieval and enrichment.

#### `users_pull(filter=None, limit=None, generate_report=True)`

Get fully transformed and enriched users.

**Parameters:**
- `filter` (dict, optional): MongoDB filter for users (e.g., `{"role": "REGULAR"}`)
- `limit` (int, optional): Maximum number of users to return
- `generate_report` (bool, default=True): Generate timestamped markdown report in `reports/` folder

**Returns:**
- `List[Dict[str, Any]]`: List of fully enriched user dictionaries

**Example:**
```python
# Get all active users
active_users = pull.users_pull(filter={"engagement_status": "active"})

# Get top 100 users by event count
top_users = pull.users_pull(limit=100)

# Get users without generating report
users = pull.users_pull(generate_report=False)
```

#### `events_pull(filter=None, limit=None, generate_report=True)`

Get fully transformed and enriched events.

**Parameters:**
- `filter` (dict, optional): MongoDB filter for events (e.g., `{"type": "public"}`)
- `limit` (int, optional): Maximum number of events to return
- `generate_report` (bool, default=True): Generate timestamped markdown report in `reports/` folder

**Returns:**
- `List[Dict[str, Any]]`: List of fully enriched event dictionaries

**Example:**
```python
# Get future public events
future_events = pull.events_pull(
    filter={"type": "public", "startDate": {"$gt": datetime.now().isoformat()}}
)

# Get underfilled events
underfilled = pull.events_pull(
    filter={"participationPercentage": {"$lt": 50}}
)
```

#### `close()`

Close the MongoDB connection.

```python
pull.close()
```

## Field Documentation

### `users_pull()` Output Fields

Each user dictionary returned by `users_pull()` contains:

#### Raw Fields (from MongoDB 'user' collection)

All original MongoDB fields are preserved:
- `id`, `_id`: User identifier
- `email`: Email address
- `firstName`, `lastName`: User name
- `role`: User role ("ADMIN", "REGULAR", "POTENTIAL")
- `interests`: List of user interests
- `occupation`: User's occupation
- `homeNeighborhood`: User's neighborhood
- `gender`: User's gender
- `phone`: Phone number
- `birthDay`: Birthday (ISO 8601 format)
- `tableTypePreference`: Preferred table type
- `createdAt`: Account creation date (ISO 8601)
- And all other MongoDB fields

#### Derived/Transformed Fields

##### 1. Engagement & Activity Fields

| Field | Type | Description | Logic |
|-------|------|-------------|-------|
| `event_count` | int | Count of events where user is participant OR owner | `len(event_map.get(user_id, []))` where event_map indexes by both participants and ownerId |
| `order_count` | int | Count of orders where userId matches user | `len(order_map.get(user_id, []))` |
| `total_order_amount` | float | Total amount spent across all orders | Sum of `order.price.total` (if dict) or `order.price` (if numeric) |
| `total_spent` | float | Alias for `total_order_amount` (backward compatibility) | Same as `total_order_amount` |
| `last_active` | str (ISO 8601) | Most recent activity date | `max(max(event.startDate), max(order.createdAt))` |
| `days_inactive` | int | Days since last activity | `(now - last_active).days` if exists, else `9999` |
| `engagement_status` | str | Engagement classification | `days_inactive <= 30` → "active"<br>`days_inactive <= 90` → "dormant"<br>`days_inactive == 9999` → "new"<br>else → "churned" |
| `is_active` | bool | Active user flag | `True` if `engagement_status == "active"` |

##### 2. Journey & Segmentation Fields

| Field | Type | Description | Logic |
|-------|------|-------------|-------|
| `journey_stage` | str | User journey stage | Priority order:<br>1. `role == "POTENTIAL"` → "Signed Up Online"<br>2. `event_count == 0` → "Downloaded App"<br>3. `event_count >= 1 and total_spent == 0` → "Joined Table"<br>4. `total_spent > 0 and event_count > 1` → "Returned"<br>5. `total_spent > 0` → "Attended"<br>6. Else → "Downloaded App" |
| `value_segment` | str | Value classification | `total_spent >= 2000` → "VIP"<br>`total_spent >= 500` → "High Value"<br>`total_spent > 0` → "Regular"<br>else → "Low Value" |
| `social_role` | str | Social participation level | `event_count >= 50` → "social_leader"<br>`event_count >= 20` → "active_participant"<br>else → "observer" |
| `churn_risk` | str | Churn risk assessment | `days_inactive >= 180` → "high"<br>`days_inactive >= 90` → "medium"<br>else → "low" |
| `user_segment` | str | User segmentation category | Priority-based classification:<br>1. Dead (no events/orders, old account)<br>2. Campaign (2025 account, no details)<br>3. Fresh (≤30 days inactive, has events)<br>4. Active (≤90 days inactive, has events)<br>5. Dormant (≤180 days inactive, has events)<br>6. Inactive (has history)<br>7. New (default) |
| `cohort` | str | Registration cohort | `createdAt[:7]` (YYYY-MM format) |
| `days_since_registration` | int | Days since account creation | `(now - parse_iso_date(createdAt)).days` |

##### 3. Profile Completeness Fields

| Field | Type | Description | Logic |
|-------|------|-------------|-------|
| `profile_completeness` | str | Completeness score string | Count filled fields from [firstName, lastName, email, phone, gender, interests, occupation, homeNeighborhood]<br>Format: `"{filled}/8 ({percentage}%)"` |
| `personalization_ready` | bool | Profile ready for personalization | `True` if at least 4 of 8 required fields filled |

##### 4. Scoring Fields

| Field | Type | Description | Logic |
|-------|------|-------------|-------|
| `newcomer_score` | float (0-100) | Score for newcomer users | **Event history (0-50pts):**<br>0 events = 50pts<br>1 event = 30pts<br>2 events = 10pts<br>3+ = 0pts<br><br>**Profile completeness (0-30pts):**<br>`(filled_count / 8) * 30`<br><br>**Account recency (0-20pts):**<br>Within 90 days = 20pts<br>Within 180 days = 10pts<br>Else = 0pts |
| `reactivation_score` | float (0-100) | Score for dormant users | **Profile completeness (0-40pts):**<br>`(filled_count / 8) * 40`<br><br>**Dormancy duration (0-30pts):**<br>31-90 days inactive = 30-20pts<br><br>**Event history (0-30pts):**<br>≥5 events = 30pts<br>≥3 events = 20pts<br>≥1 event = 10pts |

##### 5. Campaign Qualification Fields

| Field | Type | Description |
|-------|------|-------------|
| `campaign_qualifications` | Dict | Campaign qualification flags and reasons |
| `campaign_qualifications.qualifies_seat_newcomers` | bool | `True` if: event_count 0-2, profile complete, has interests, joined ≤90 days |
| `campaign_qualifications.qualifies_fill_the_table` | bool | `True` if: profile complete |
| `campaign_qualifications.qualifies_return_to_table` | bool | `True` if: event_count ≥1, profile complete, has interests, dormant (31-90 days inactive) |
| `campaign_qualifications.campaign_qualification_reasons` | Dict[str, List[str]] | Reasons for each campaign qualification |

##### 6. Social Connection Fields

| Field | Type | Description |
|-------|------|-------------|
| `social_connections` | List[Dict] | Users this user has attended events with<br>Format: `[{"user_id": str, "shared_event_count": int, "last_shared_event_date": str}]` |
| `event_history` | List[Dict] | Past events user has attended/owned (sorted by recency, most recent first) |
| `interest_analysis` | Dict | Analyzed interests from event history<br>Format: `{"top_categories": List[str], "top_features": List[str], "top_venues": List[str], "event_type_preference": str, "time_patterns": Dict}` |

##### 7. Summary Field

| Field | Type | Description |
|-------|------|-------------|
| `summary` | str | Comprehensive summary incorporating personalization details and narrative synthesis<br>Includes: name, age, gender, relationship status, occupation, neighborhood, event count, interests, cuisines, table type preference, journey stage, engagement status, total spent, value segment, and registration year<br>Format: "User {name} is a {age}-year-old {gender} {occupation} from {neighborhood}. They joined in {year}. They are in the {journey_stage} stage ({engagement_status}) with {event_count} events and ${total_spent} spent. Classified as {value_segment}. Relationship status: {relationship_status}. Interests: {interests}. Preferred cuisines: {cuisines}. Table preference: {table_type_preference}." |

---

### `events_pull()` Output Fields

Each event dictionary returned by `events_pull()` contains:

#### Raw Fields (from MongoDB 'event' collection)

All original MongoDB fields are preserved:
- `id`, `_id`: Event identifier
- `name`: Event name
- `startDate`, `endDate`: Event dates (ISO 8601)
- `type`: Event type ("public", "private")
- `eventStatus`: Event approval status
- `maxParticipants`, `minParticipants`: Participant limits
- `participants`: List of participant user IDs
- `ownerId`: Event owner/creator ID
- `venueName`: Venue name
- `neighborhood`: Event neighborhood
- `categories`: Event categories
- `features`: Event features
- `description`: Event description (may contain HTML)
- `createdAt`: Event creation date (ISO 8601)
- And all other MongoDB fields

#### Derived/Transformed Fields

##### 1. Participation Fields

| Field | Type | Description | Logic |
|-------|------|-------------|-------|
| `participantCount` | int | Number of participants | `len(event.get('participants', []))` |
| `participationPercentage` | float | Percentage of capacity filled | `(participantCount / maxParticipants) * 100` if `maxParticipants > 0`, else `0` |

##### 2. Participant Demographics Fields

| Field | Type | Description | Logic |
|-------|------|-------------|-------|
| `participant_profiles_enriched` | bool | Participant analysis completed | `True` if participant analysis completed |
| `participant_count` | int | Number of participants with profile data | Count of participants found in user_lookup |
| `participant_top_interests` | List[Tuple[str, int]] | Top 5 interests from participants | Count interests from all participant profiles, sort by count, take top 5<br>Format: `[("art", 5), ("music", 4), ("food", 3)]` |
| `participant_top_occupations` | List[Tuple[str, int]] | Top 5 occupations from participants | Count occupations from all participant profiles, sort by count, take top 5 |
| `participant_top_neighborhoods` | List[Tuple[str, int]] | Top 5 neighborhoods from participants | Count neighborhoods from all participant profiles, sort by count, take top 5 |

##### 3. Campaign Qualification Fields

| Field | Type | Description |
|-------|------|-------------|
| `campaign_qualifications` | Dict | Campaign qualification flags and reasons |
| `campaign_qualifications.qualifies_seat_newcomers` | bool | `True` if: future event, public, `maxParticipants > 0`, participation 50-80% |
| `campaign_qualifications.qualifies_fill_the_table` | bool | `True` if: future event, public, participation <50%, `maxParticipants > 0` |
| `campaign_qualifications.qualifies_return_to_table` | bool | `True` if: future event, public, `maxParticipants > 0`, participation >60% |
| `campaign_qualifications.campaign_qualification_reasons` | Dict[str, List[str]] | Reasons for each campaign qualification |

##### 4. Summary Fields

| Field | Type | Description |
|-------|------|-------------|
| `summary` | str | Generated event summary<br>Format: "Event: {name} at {venueName} in {neighborhood}. Categories: {categories}. Features: {features}. Capacity: {maxParticipants}, Participants: {count} ({percentage}% full). Date: {formatted_date}."<br>HTML tags removed from description if included |

## Report Generation

When `generate_report=True` (default), the module automatically generates timestamped markdown reports in the `reports/` folder.

### Users Report

The users report (`users_report_YYYYMMDD-HHMMSS.md`) includes:

- **Aggregate Metrics**: Total users, events, orders, spending, averages
- **Segment Distributions**: Tables showing counts and percentages for:
  - Journey Stage
  - Engagement Status
  - Value Segment
  - Social Role
  - User Segment
  - Churn Risk
  - Profile Completeness
  - Campaign Qualifications
- **Field Definitions**: Documentation of all raw and derived fields
- **Key Insights**: Summary statistics and observations

### Events Report

The events report (`events_report_YYYYMMDD-HHMMSS.md`) includes:

- **Aggregate Metrics**: Total events, participants, capacity, average participation
- **Segment Distributions**: Tables showing counts and percentages for:
  - Event Type
  - Event Status
  - Participation Percentage Ranges
  - Campaign Qualifications
- **Field Definitions**: Documentation of all raw and derived fields
- **Campaign Qualification Criteria**: Detailed criteria for each campaign
- **Key Insights**: Summary statistics and observations

## Architecture

The module is organized into several classes:

### Main Classes

- **`MongoDBPull`**: Main orchestrator class providing `users_pull()` and `events_pull()` methods
- **`MongoDBConnection`**: Handles MongoDB client and database connections, raw data retrieval
- **`UserEnrichment`**: User-specific calculations, enrichment, and transformation
- **`EventTransformation`**: Event-specific enrichment and participant analysis
- **`CampaignQualification`**: Campaign qualification logic for users and events
- **`SummaryGeneration`**: Human-readable summary generation for users and events
- **`SocialConnection`**: Social network analysis and event history
- **`ReportGeneration`**: Markdown report generation with metrics and distributions

### Utility Functions

- `parse_iso_date(date_str)`: Parse ISO 8601 date strings
- `is_profile_complete(user)`: Check if user profile is complete
- `setup_logging()`: Configure logging to file and console
- `calculate_newcomer_score(user)`: Calculate newcomer score (0-100)
- `calculate_reactivation_score(user)`: Calculate reactivation score (0-100)

## Examples

### Example 1: Get All Enriched Users

```python
from helpers.mongodb_pull import MongoDBPull

pull = MongoDBPull()
users = pull.users_pull()

# Access enriched fields
for user in users[:5]:
    print(f"{user['firstName']} {user['lastName']}")
    print(f"  Journey Stage: {user['journey_stage']}")
    print(f"  Engagement: {user['engagement_status']}")
    print(f"  Events: {user['event_count']}, Spent: ${user['total_spent']:.2f}")
    print(f"  Value Segment: {user['value_segment']}")
    print(f"  Campaign Qualified: {user['campaign_qualifications']}")
    print()

pull.close()
```

### Example 2: Filter Users by Campaign Qualification

```python
from helpers.mongodb_pull import MongoDBPull

pull = MongoDBPull()
all_users = pull.users_pull()

# Filter for seat-newcomers qualified users
newcomers = [
    user for user in all_users
    if user.get('campaign_qualifications', {}).get('qualifies_seat_newcomers', False)
]

print(f"Found {len(newcomers)} users qualified for seat-newcomers campaign")
for user in newcomers[:10]:
    print(f"  {user['firstName']} {user['lastName']} - Score: {user.get('newcomer_score', 0):.1f}")

pull.close()
```

### Example 3: Get Underfilled Events

```python
from helpers.mongodb_pull import MongoDBPull
from datetime import datetime

pull = MongoDBPull()
all_events = pull.events_pull()

# Filter for underfilled future events
now = datetime.now(timezone.utc).isoformat()
underfilled = [
    event for event in all_events
    if event.get('type') == 'public'
    and event.get('startDate', '') > now
    and event.get('participationPercentage', 0) < 50
]

print(f"Found {len(underfilled)} underfilled future public events")
for event in underfilled[:10]:
    print(f"  {event['name']} - {event.get('participationPercentage', 0):.1f}% full")

pull.close()
```

### Example 4: Analyze User Social Connections

```python
from helpers.mongodb_pull import MongoDBPull

pull = MongoDBPull()
users = pull.users_pull(limit=100)

# Find users with most social connections
users_with_connections = [
    (user, len(user.get('social_connections', [])))
    for user in users
    if user.get('social_connections')
]
users_with_connections.sort(key=lambda x: x[1], reverse=True)

print("Top 10 users by social connections:")
for user, conn_count in users_with_connections[:10]:
    print(f"  {user['firstName']} {user['lastName']}: {conn_count} connections")

pull.close()
```

### Example 5: Generate Reports Only

```python
from helpers.mongodb_pull import MongoDBPull

pull = MongoDBPull()

# Generate reports without processing data
users = pull.users_pull(generate_report=True)
events = pull.events_pull(generate_report=True)

# Reports are saved in helpers/mongodb_pull/reports/
print("Reports generated successfully")

pull.close()
```

## Logging

The module provides comprehensive logging to both file and console:

- **Log Files**: Saved in `helpers/mongodb_pull/logs/` with timestamped filenames
- **Console Output**: Real-time progress and insights
- **Segment Distributions**: Logged after user transformation showing counts for all segments

Example log output:
```
INFO - ================================================================================
INFO - STARTING USER PULL OPERATION
INFO - ================================================================================
INFO - Step 1: Fetching raw data from MongoDB...
INFO - Step 2: Transforming and enriching 1000 users...
INFO - Journey Stage Distribution:
INFO -   Active: 450 (45.0%)
INFO -   Dormant: 300 (30.0%)
...
```

## MongoDB Configuration

The module uses hardcoded MongoDB credentials for local system use:

- **Database**: `cuculi_production`
- **Collections**: `user`, `event`, `order`
- **Connection**: MongoDB Atlas connection string

**Note**: Credentials are hardcoded in the module. For production use, consider using environment variables or a configuration file.

## Directory Structure

```
helpers/mongodb_pull/
├── __init__.py              # Package initialization and exports
├── mongodb_pull.py          # Main module with all classes and functions
├── README.md                # This file
├── logs/                    # Log files (auto-created)
│   └── mongodb_pull_*.log
└── reports/                 # Generated markdown reports (auto-created)
    ├── users_report_*.md
    └── events_report_*.md
```

## Contributing

When adding new fields or modifying existing logic:

1. Update the field documentation in this README
2. Update the module docstring in `mongodb_pull.py`
3. Update the report generation to include new fields in distributions
4. Add logging for new segment distributions
5. Update examples if needed

## License

Internal use only.

