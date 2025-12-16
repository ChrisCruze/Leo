# Airtable Sync Script Plan

## Overview

This document outlines the implementation plan for `airtable_sync.py`, a script designed to synchronize MongoDB data (users, events, messages) with Airtable tables to enable tracking of user engagement and event participation rates.

## Objectives

- Update and sync Airtable tables for Users, Events, and Messages
- Enable tracking of user engagement and event participation rate
- Maintain a database in Airtable for insights such as:
  - Number of users by specific segment
  - Event type analysis
  - User engagement metrics

---

## Implementation Plan

### Phase 0: Research and Preparation

#### 0.1 Review pyairtable Documentation and Best Practices

**IMPORTANT:** Before implementing the airtable_sync script, review the official pyairtable documentation and best practices:

- **Official Documentation:** https://pyairtable.readthedocs.io/
- **GitHub Repository:** https://github.com/gtalarico/pyairtable
- **Key Topics to Review:**
  - API authentication and connection setup
  - Rate limiting and best practices
  - Batch operations for efficiency
  - Error handling patterns
  - Field type handling (dates, linked records, etc.)
  - Pagination for large datasets
  - Update vs create operations

**Note:** Understanding these best practices will help avoid common pitfalls and ensure efficient, reliable syncing.

---

### Phase 1: Setup and Connectivity Testing

#### 1.1 Install Python Airtable Library

```bash
pip install pyairtable
```

#### 1.2 Test Airtable Connectivity

**Objective:** Verify connection to Airtable API and access to the Cuculi base.

**Implementation Details:**
```python
from pyairtable import Api

# Hardcoded credentials (hardcode these in the script)
AIRTABLE_API_KEY = "patdMoOPya9xAXGLG.3a26ab9163b441fa24a5e1edc3d775c4608e447dd7c0ffa50d6de697d121c022"
BASE_ID = "appaquqFN7vvvZGcq"

# Initialize API
api = Api(AIRTABLE_API_KEY)
base = api.base(BASE_ID)

# Test connection
try:
    # Try to access each table
    users_table = base.table("tblQ0OHBit2AqaACy")
    events_table = base.table("tblrscr87h8fbtQTk")
    messages_table = base.table("tbljma5S4NhUn1OYl")

    # Test a simple query
    test_users = users_table.first()
    logger.info(f"✓ Successfully connected to Airtable")
    logger.info(f"✓ Test query returned: {test_users}")
except Exception as e:
    logger.error(f"✗ Failed to connect to Airtable: {e}")
```

---

### Phase 2: Pull and Cache Airtable Table Data

#### 2.1 Pull Data from Airtable Tables

**Objective:** Retrieve all existing records from Users, Events, and Messages tables and cache locally.

**Table IDs:**
- Users: `tblQ0OHBit2AqaACy`
- Events: `tblrscr87h8fbtQTk`
- Messages: `tbljma5S4NhUn1OYl`

**Implementation Details:**

```python
import os
import json

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

def pull_airtable_data(table, table_name):
    """
    Pull all records from an Airtable table with pagination.
    Save to local cache for future use.

    Args:
        table: Airtable table object
        table_name: Name for logging and file saving (users/events/messages)

    Returns:
        List of records with fields and IDs
    """
    cache_file = os.path.join(DATA_DIR, f'airtable_{table_name}.json')

    # Check if cached data exists
    if os.path.exists(cache_file):
        logger.info(f"✓ Loading cached Airtable data for {table_name} from {cache_file}")
        with open(cache_file, 'r') as f:
            records = json.load(f)
        logger.info(f"✓ Loaded {len(records)} {table_name} records from cache")
        return records

    # Pull fresh data from Airtable
    logger.info(f"Fetching {table_name} records from Airtable...")
    all_records = []

    # Use pagination for large datasets (especially Users with ~10,000 records)
    # Airtable returns max 100 records per page by default
    for page in table.iterate(page_size=100):
        all_records.extend(page)
        logger.debug(f"Fetched page of {len(page)} records (total: {len(all_records)})")

    logger.info(f"✓ Fetched {len(all_records)} {table_name} records from Airtable")

    # Log field analysis for first record
    if all_records:
        first_record = all_records[0]
        logger.info(f"Sample {table_name} record ID: {first_record['id']}")
        logger.info(f"Fields in {table_name}: {list(first_record['fields'].keys())}")

        # Log sample field values and types
        for field_name, field_value in list(first_record['fields'].items())[:5]:
            logger.info(f"  - {field_name}: {field_value} (type: {type(field_value).__name__})")

    # Save to cache
    with open(cache_file, 'w') as f:
        json.dump(all_records, f, indent=2)
    logger.info(f"✓ Cached {table_name} data to {cache_file}")

    return all_records

# Pull data for all tables
users_airtable_data = pull_airtable_data(users_table, 'users')
events_airtable_data = pull_airtable_data(events_table, 'events')
messages_airtable_data = pull_airtable_data(messages_table, 'messages')
```

**Important Notes:**
- Users table has ~10,000 records, so pagination is necessary
- Airtable API returns max 100 records per page
- Use `table.iterate()` method for automatic pagination
- Cache data locally to avoid repeated API calls during development
- If cache exists, use it instead of querying Airtable

---

### Phase 3: Load Local MongoDB Data

#### 3.1 Load MongoDB JSON Files

**Objective:** Load the local JSON data files generated by `mongodb_pull.py`.

**Data Location:**
- Users: `backend/utils/mongodb_pull/data/users.json`
- Events: `backend/utils/mongodb_pull/data/events.json`
- Messages: *To be confirmed - may need to check mongodb_pull data folder*

**Implementation Details:**

```python
def load_local_mongodb_data(data_type):
    """
    Load local MongoDB data from JSON files.

    Args:
        data_type: 'users', 'events', or 'messages'

    Returns:
        List of records
    """
    mongodb_data_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'mongodb_pull',
        'data'
    )
    file_path = os.path.join(mongodb_data_dir, f'{data_type}.json')

    logger.info(f"Loading local MongoDB {data_type} data from {file_path}")

    if not os.path.exists(file_path):
        logger.error(f"✗ File not found: {file_path}")
        return []

    with open(file_path, 'r') as f:
        records = json.load(f)

    logger.info(f"✓ Loaded {len(records)} {data_type} records from MongoDB data")

    # Log field analysis
    if records:
        first_record = records[0]
        logger.info(f"Fields in MongoDB {data_type}: {list(first_record.keys())}")

    return records

# Load MongoDB data
users_mongodb = load_local_mongodb_data('users')
events_mongodb = load_local_mongodb_data('events')
messages_mongodb = load_local_mongodb_data('messages')
```

---

### Phase 4: Match Local Records with Airtable Records

#### 4.1 Create Matching Functions

**Objective:** Determine if a local MongoDB record already exists in Airtable based on unique identifiers.

**Matching Criteria:**
- **Users:** Match on `email` field
- **Events:** Match on `name` field
- **Messages:** Match on `message` field

**Implementation Details:**

```python
def create_airtable_lookup(airtable_records, match_field):
    """
    Create a lookup dictionary for O(1) matching.

    Args:
        airtable_records: List of Airtable records
        match_field: Field name to use as key (e.g., 'email', 'name', 'message')

    Returns:
        Dict mapping match_field value -> full Airtable record (including ID)
    """
    lookup = {}
    for record in airtable_records:
        fields = record.get('fields', {})
        key_value = fields.get(match_field)

        if key_value:
            # Normalize key (lowercase, strip whitespace) for better matching
            normalized_key = str(key_value).strip().lower()
            lookup[normalized_key] = record

    logger.info(f"✓ Created lookup with {len(lookup)} entries for field '{match_field}'")
    return lookup

def match_record(local_record, airtable_lookup, local_match_field, normalize=True):
    """
    Find matching Airtable record for a local MongoDB record.

    Args:
        local_record: MongoDB record dictionary
        airtable_lookup: Lookup dictionary from create_airtable_lookup()
        local_match_field: Field name in local record to match on
        normalize: Whether to normalize the match key

    Returns:
        Tuple of (airtable_record_id, airtable_record_fields) if found, else (None, None)
    """
    local_value = local_record.get(local_match_field)

    if not local_value:
        return None, None

    # Normalize for matching
    if normalize:
        match_key = str(local_value).strip().lower()
    else:
        match_key = local_value

    airtable_record = airtable_lookup.get(match_key)

    if airtable_record:
        return airtable_record['id'], airtable_record.get('fields', {})

    return None, None

# Create lookups for each table
users_lookup = create_airtable_lookup(users_airtable_data, 'email')
events_lookup = create_airtable_lookup(events_airtable_data, 'Name')  # Note: Capital 'N'
messages_lookup = create_airtable_lookup(messages_airtable_data, 'message')
```

---

### Phase 5: Field Mapping Dictionaries

#### 5.1 Define Field Mappings

**Objective:** Map MongoDB field names to Airtable field names and specify which fields to sync.

**Important Notes:**
- Only fields in the mapping dictionary will be synced
- This prevents errors from attempting to update non-existent or incompatible fields
- Airtable field names may differ from MongoDB (e.g., capitalization)
- Fields not in Airtable should be excluded

**Implementation Details:**

```python
# Field mapping for Users table
# Format: 'mongodb_field': 'airtable_field'
USERS_FIELD_MAPPING = {
    # Basic identity fields
    'id': 'id',
    'email': 'email',
    'firstName': 'firstName',
    'lastName': 'lastName',
    'phone': 'phone',
    'role': 'role',

    # Profile fields
    'gender': 'gender',
    'birthDay': 'birthDay',
    'occupation': 'occupation',
    'homeNeighborhood': 'homeNeighborhood',
    'interests': 'interests',
    'tableTypePreference': 'tableTypePreference',

    # Engagement metrics (enriched by mongodb_pull.py)
    'event_count': 'event_count',
    'order_count': 'order_count',
    'total_spent': 'total_spent',
    'last_active': 'last_active',
    'days_inactive': 'days_inactive',
    'engagement_status': 'engagement_status',

    # Journey & segmentation (enriched by mongodb_pull.py)
    'journey_stage': 'journey_stage',
    'value_segment': 'value_segment',
    'user_segment': 'user_segment',
    'churn_risk': 'churn_risk',

    # Profile completeness
    'profile_completeness': 'profile_completeness',
    'profile_ready': 'profile_ready',

    # Summary (generated by mongodb_pull.py)
    'summary': 'summary',

    # Timestamps
    'createdAt': 'createdAt',
    'updatedAt': 'updatedAt',
}

# Field mapping for Events table
# Note: Refer to mongodb_pull.py for event fields
EVENTS_FIELD_MAPPING = {
    'id': 'id',
    'name': 'Name',  # Note: Capital 'N' in Airtable
    'description': 'description',
    'startDate': 'startDate',
    'endDate': 'endDate',
    'location': 'location',
    'eventType': 'eventType',
    'cuisine': 'cuisine',
    'tableType': 'tableType',
    'maxCapacity': 'maxCapacity',
    'price': 'price',

    # Participant metrics (enriched by mongodb_pull.py)
    'participantCount': 'participantCount',
    'participationPercentage': 'participationPercentage',
    'participant_top_interests': 'participant_top_interests',
    'participant_top_occupations': 'participant_top_occupations',

    # Campaign qualification
    'qualifies_seat_newcomers': 'qualifies_seat_newcomers',
    'qualifies_fill_the_table': 'qualifies_fill_the_table',

    # Summary (generated by mongodb_pull.py)
    'summary': 'summary',

    # Timestamps
    'createdAt': 'createdAt',
    'updatedAt': 'updatedAt',
}

# Field mapping for Messages table
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
    'generated_at': 'createdAt',  # Maps to createdAt in Airtable
    'campaign': 'campaign',
    'updatedAt': 'updatedAt',
}

def map_fields(local_record, field_mapping):
    """
    Map MongoDB record fields to Airtable field names.
    Only includes fields that exist in the mapping.

    Args:
        local_record: MongoDB record dictionary
        field_mapping: Field mapping dictionary

    Returns:
        Dictionary with Airtable field names and values
    """
    mapped_fields = {}

    for mongodb_field, airtable_field in field_mapping.items():
        if mongodb_field in local_record:
            value = local_record[mongodb_field]

            # Handle special cases (e.g., convert dates, lists, etc.)
            # Add data type conversion logic here if needed

            mapped_fields[airtable_field] = value

    return mapped_fields
```

---

### Phase 6: Create and Update Functions

#### 6.1 Implement Create and Update Operations

**Objective:** Create functions to create new Airtable records and update existing ones.

**Implementation Details:**

```python
def records_are_equal(local_fields, airtable_fields):
    """
    Compare local record fields with Airtable fields to detect changes.

    Args:
        local_fields: Mapped fields from local record
        airtable_fields: Fields from existing Airtable record

    Returns:
        True if all fields match, False if any field differs
    """
    for field_name, local_value in local_fields.items():
        airtable_value = airtable_fields.get(field_name)

        # Handle type mismatches (e.g., int vs float, None vs missing)
        if local_value != airtable_value:
            # Allow for minor type differences
            if local_value is None and airtable_value is None:
                continue
            if str(local_value) != str(airtable_value):
                return False

    return True

def create_airtable_record(table, fields, record_type):
    """
    Create a new record in Airtable.

    Args:
        table: Airtable table object
        fields: Dictionary of field names and values
        record_type: 'users', 'events', or 'messages' (for logging)

    Returns:
        Created record ID or None if failed
    """
    try:
        created_record = table.create(fields)
        record_id = created_record['id']
        logger.info(f"✓ Created new {record_type} record: {record_id}")
        return record_id
    except Exception as e:
        logger.error(f"✗ Failed to create {record_type} record: {e}")
        logger.debug(f"Fields attempted: {fields}")
        return None

def update_airtable_record(table, record_id, fields, airtable_fields, record_type):
    """
    Update an existing Airtable record.
    Skip update if values are the same.

    Args:
        table: Airtable table object
        record_id: Airtable record ID
        fields: New field values to update
        airtable_fields: Current Airtable field values
        record_type: 'users', 'events', or 'messages' (for logging)

    Returns:
        True if updated, False if skipped or failed
    """
    # Skip if no changes
    if records_are_equal(fields, airtable_fields):
        logger.debug(f"⊘ Skipped {record_type} record {record_id} (no changes)")
        return False

    try:
        table.update(record_id, fields)
        logger.info(f"✓ Updated {record_type} record: {record_id}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to update {record_type} record {record_id}: {e}")
        logger.debug(f"Fields attempted: {fields}")
        return False
```

---

### Phase 7: Sync Process

#### 7.1 Implement Sync Logic

**Objective:** Iterate through local MongoDB records and sync to Airtable (create or update).

**Sync Order:**
1. Users (first, because Events and Messages reference Users)
2. Events (second, because Messages reference Events)
3. Messages (last, depends on both Users and Events)

**Implementation Details:**

```python
def sync_table(local_records, airtable_lookup, table, field_mapping, match_field, table_name):
    """
    Sync local records to Airtable table.

    Args:
        local_records: List of MongoDB records
        airtable_lookup: Lookup dictionary for matching
        table: Airtable table object
        field_mapping: Field mapping dictionary
        match_field: Field to match on (e.g., 'email', 'name')
        table_name: Name for logging ('users', 'events', 'messages')

    Returns:
        Dict with sync statistics
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Starting sync for {table_name.upper()}")
    logger.info(f"{'='*60}")

    stats = {
        'total': len(local_records),
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0
    }

    for idx, local_record in enumerate(local_records, 1):
        # Map fields
        mapped_fields = map_fields(local_record, field_mapping)

        # Find matching Airtable record
        airtable_id, airtable_fields = match_record(
            local_record,
            airtable_lookup,
            match_field
        )

        if airtable_id:
            # Update existing record
            updated = update_airtable_record(
                table,
                airtable_id,
                mapped_fields,
                airtable_fields,
                table_name
            )
            if updated:
                stats['updated'] += 1
            else:
                stats['skipped'] += 1
        else:
            # Create new record
            created_id = create_airtable_record(table, mapped_fields, table_name)
            if created_id:
                stats['created'] += 1
                # Add to lookup for linked records
                match_value = str(local_record.get(match_field, '')).strip().lower()
                airtable_lookup[match_value] = {'id': created_id, 'fields': mapped_fields}
            else:
                stats['errors'] += 1

        # Log progress
        if idx % 100 == 0:
            logger.info(f"Progress: {idx}/{stats['total']} records processed")

    logger.info(f"\n{table_name.upper()} Sync Complete:")
    logger.info(f"  Total: {stats['total']}")
    logger.info(f"  Created: {stats['created']}")
    logger.info(f"  Updated: {stats['updated']}")
    logger.info(f"  Skipped: {stats['skipped']}")
    logger.info(f"  Errors: {stats['errors']}")

    return stats

# Execute sync in order
logger.info("="*80)
logger.info("AIRTABLE SYNC STARTING")
logger.info("="*80)

# 1. Sync Users first
users_stats = sync_table(
    users_mongodb,
    users_lookup,
    users_table,
    USERS_FIELD_MAPPING,
    'email',
    'users'
)

# 2. Sync Events second
events_stats = sync_table(
    events_mongodb,
    events_lookup,
    events_table,
    EVENTS_FIELD_MAPPING,
    'name',
    'events'
)

# 3. Sync Messages last
messages_stats = sync_table(
    messages_mongodb,
    messages_lookup,
    messages_table,
    MESSAGES_FIELD_MAPPING,
    'message',
    'messages'
)
```

---

### Phase 8: Handle Linked Fields

#### 8.1 Understand Linked Field Requirements

**Objective:** Handle Airtable linked record fields that reference other tables.

**Linked Field Structure:**
- **Messages** has linked fields:
  - `Users` field: References Users table (takes Airtable User record IDs)
  - `Events` field: References Events table (takes Airtable Event record IDs)

**Challenge:** MongoDB data contains MongoDB IDs (e.g., `senderId`, `eventId`), but Airtable needs Airtable record IDs.

#### 8.2 Implementation Strategy for Linked Fields

```python
def create_id_mapping(mongodb_records, airtable_lookup, mongodb_id_field, match_field):
    """
    Create mapping from MongoDB ID to Airtable record ID.

    Args:
        mongodb_records: List of MongoDB records
        airtable_lookup: Airtable lookup dictionary
        mongodb_id_field: Field containing MongoDB ID (e.g., 'id')
        match_field: Field used for matching (e.g., 'email', 'name')

    Returns:
        Dict mapping mongodb_id -> airtable_record_id
    """
    id_mapping = {}

    for record in mongodb_records:
        mongodb_id = record.get(mongodb_id_field)
        match_value = str(record.get(match_field, '')).strip().lower()

        if mongodb_id and match_value in airtable_lookup:
            airtable_id = airtable_lookup[match_value]['id']
            id_mapping[mongodb_id] = airtable_id

    logger.info(f"✓ Created ID mapping: {len(id_mapping)} MongoDB IDs -> Airtable IDs")
    return id_mapping

# Create ID mappings after syncing Users and Events
users_id_mapping = create_id_mapping(users_mongodb, users_lookup, 'id', 'email')
events_id_mapping = create_id_mapping(events_mongodb, events_lookup, 'id', 'name')

# Enhanced field mapping for Messages with linked fields
def map_message_fields(message_record, field_mapping, users_id_mapping, events_id_mapping):
    """
    Map message fields including linked record fields.

    Args:
        message_record: MongoDB message record
        field_mapping: Standard field mapping
        users_id_mapping: MongoDB user ID -> Airtable user ID
        events_id_mapping: MongoDB event ID -> Airtable event ID

    Returns:
        Dictionary with mapped fields including linked records
    """
    # Start with standard field mapping
    mapped_fields = map_fields(message_record, field_mapping)

    # Handle linked User field
    sender_id = message_record.get('senderId')
    if sender_id and sender_id in users_id_mapping:
        # Airtable linked fields expect a list of record IDs
        mapped_fields['Users'] = [users_id_mapping[sender_id]]

    # Handle linked Event field
    event_id = message_record.get('eventId')
    if event_id and event_id in events_id_mapping:
        # Airtable linked fields expect a list of record IDs
        mapped_fields['Events'] = [events_id_mapping[event_id]]

    return mapped_fields
```

#### 8.3 Fields Not in Airtable but in MongoDB

**Strategy:** Identify fields in MongoDB data that don't exist in Airtable and document them.

```python
def identify_unmapped_fields(mongodb_records, field_mapping, table_name):
    """
    Identify MongoDB fields that aren't mapped to Airtable.

    Args:
        mongodb_records: List of MongoDB records
        field_mapping: Field mapping dictionary
        table_name: Table name for logging

    Returns:
        Set of unmapped field names
    """
    all_mongodb_fields = set()

    # Collect all fields from MongoDB records
    for record in mongodb_records[:100]:  # Sample first 100 records
        all_mongodb_fields.update(record.keys())

    # Find unmapped fields
    mapped_fields = set(field_mapping.keys())
    unmapped_fields = all_mongodb_fields - mapped_fields

    if unmapped_fields:
        logger.info(f"\n{table_name.upper()} - Fields in MongoDB but not mapped to Airtable:")
        for field in sorted(unmapped_fields):
            logger.info(f"  - {field}")

    return unmapped_fields

# Run field analysis
users_unmapped = identify_unmapped_fields(users_mongodb, USERS_FIELD_MAPPING, 'users')
events_unmapped = identify_unmapped_fields(events_mongodb, EVENTS_FIELD_MAPPING, 'events')
messages_unmapped = identify_unmapped_fields(messages_mongodb, MESSAGES_FIELD_MAPPING, 'messages')
```

---

### Phase 9: Logging and Reporting

#### 9.1 Implement Comprehensive Logging

**Objective:** Log all operations with sufficient detail for debugging and monitoring.

**Implementation Details:**

```python
import logging
from datetime import datetime

# Setup logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), 'reports', 'airtable_sync.log')
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('AirtableSync')

# Key logging points:
# 1. Connection testing
# 2. Number of records pulled from Airtable (per table)
# 3. Sample Airtable record fields
# 4. Number of local MongoDB records loaded
# 5. Sync progress (every 100 records)
# 6. Create/update/skip/error counts
# 7. Unmapped fields
# 8. Final summary statistics
```

#### 9.2 Generate Markdown Report

**Objective:** Create a comprehensive markdown report summarizing the sync operation.

**Implementation Details:**

```python
def generate_sync_report(users_stats, events_stats, messages_stats,
                         users_unmapped, events_unmapped, messages_unmapped,
                         errors_log):
    """
    Generate markdown report of sync operation.

    Args:
        users_stats: User sync statistics
        events_stats: Event sync statistics
        messages_stats: Message sync statistics
        users_unmapped: Unmapped user fields
        events_unmapped: Unmapped event fields
        messages_unmapped: Unmapped message fields
        errors_log: List of error messages

    Returns:
        Path to generated report
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = os.path.join(
        os.path.dirname(__file__),
        'reports',
        f'sync_report_{timestamp}.md'
    )

    total_created = users_stats['created'] + events_stats['created'] + messages_stats['created']
    total_updated = users_stats['updated'] + events_stats['updated'] + messages_stats['updated']
    total_errors = users_stats['errors'] + events_stats['errors'] + messages_stats['errors']

    markdown = f"""# Airtable Sync Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

- **Total Created:** {total_created}
- **Total Updated:** {total_updated}
- **Total Errors:** {total_errors}

## Users Sync

- Total Records: {users_stats['total']}
- Created: {users_stats['created']}
- Updated: {users_stats['updated']}
- Skipped (no changes): {users_stats['skipped']}
- Errors: {users_stats['errors']}

### Unmapped Fields
{chr(10).join(f'- `{field}`' for field in sorted(users_unmapped)) if users_unmapped else '- None'}

## Events Sync

- Total Records: {events_stats['total']}
- Created: {events_stats['created']}
- Updated: {events_stats['updated']}
- Skipped (no changes): {events_stats['skipped']}
- Errors: {events_stats['errors']}

### Unmapped Fields
{chr(10).join(f'- `{field}`' for field in sorted(events_unmapped)) if events_unmapped else '- None'}

## Messages Sync

- Total Records: {messages_stats['total']}
- Created: {messages_stats['created']}
- Updated: {messages_stats['updated']}
- Skipped (no changes): {messages_stats['skipped']}
- Errors: {messages_stats['errors']}

### Unmapped Fields
{chr(10).join(f'- `{field}`' for field in sorted(messages_unmapped)) if messages_unmapped else '- None'}

## Errors

{chr(10).join(f'- {error}' for error in errors_log) if errors_log else 'No errors encountered.'}

## Notes

- Records are matched using: Users (email), Events (name), Messages (message)
- Linked fields in Messages table reference Users and Events by Airtable record IDs
- Unmapped fields exist in MongoDB but are not synced to Airtable
- Skipped records had no changes between local and Airtable data

---
*Report generated by airtable_sync.py*
"""

    with open(report_file, 'w') as f:
        f.write(markdown)

    logger.info(f"✓ Generated sync report: {report_file}")
    return report_file
```

---

## Summary of Script Flow

1. **Setup & Test Connection**
   - Install `pyairtable`
   - Test API connection with hardcoded credentials
   - Verify access to all three tables

2. **Pull Airtable Data**
   - Fetch all records from Users, Events, Messages tables
   - Use pagination for large datasets (especially Users)
   - Cache locally in `data/` folder
   - Reuse cache if it exists

3. **Load MongoDB Data**
   - Load users.json, events.json, messages.json from `../mongodb_pull/data/`
   - Analyze fields present in MongoDB data

4. **Create Lookups & Match Records**
   - Build lookup dictionaries for O(1) matching
   - Match on: email (Users), name (Events), message (Messages)
   - Retrieve Airtable record IDs for updates

5. **Map Fields**
   - Use mapping dictionaries to translate field names
   - Only sync fields present in mapping (avoids errors)
   - Identify unmapped fields for documentation

6. **Sync Records**
   - Sync Users first (create/update)
   - Sync Events second (create/update)
   - Sync Messages last with linked fields (create/update)
   - Skip updates if no changes detected

7. **Handle Linked Fields**
   - Create ID mappings (MongoDB ID → Airtable ID)
   - For Messages: map senderId → Users field, eventId → Events field
   - Use Airtable record IDs in linked field lists

8. **Log & Report**
   - Comprehensive logging throughout
   - Generate markdown report with statistics
   - Document unmapped fields and errors

---

## File Structure

```
backend/utils/airtable_sync/
├── README.md                 # This file
├── airtable_sync.py         # Main sync script (to be implemented)
├── data/
│   ├── airtable_users.json   # Cached Airtable users data
│   ├── airtable_events.json  # Cached Airtable events data
│   └── airtable_messages.json # Cached Airtable messages data
└── reports/
    ├── airtable_sync.log     # Log file
    └── sync_report_*.md      # Generated sync reports
```

---

## Next Steps

1. **Review pyairtable documentation and best practices** (see Phase 0.1 above)
2. Implement `airtable_sync.py` following this plan
   - **IMPORTANT:** Hardcode the Airtable API key in the script: `"patdMoOPya9xAXGLG.3a26ab9163b441fa24a5e1edc3d775c4608e447dd7c0ffa50d6de697d121c022"`
3. Test connectivity and data pulling
4. Verify field mappings with actual Airtable schema
5. Test sync with a small subset of data first
6. Run full sync and review reports
7. Schedule regular syncs (e.g., daily cron job)

---

## Important Considerations

### API Key Configuration
- **IMPORTANT:** The Airtable API key must be hardcoded in the script
- API Key: `"patdMoOPya9xAXGLG.3a26ab9163b441fa24a5e1edc3d775c4608e447dd7c0ffa50d6de697d121c022"`
- Base ID: `"appaquqFN7vvvZGcq"`
- Do not use environment variables for the API key - hardcode it directly in the script

### Field Mapping Accuracy
- **ACTION REQUIRED:** Verify Airtable field names match the mapping dictionaries
- Field names in Airtable are case-sensitive
- Some fields may use different names (e.g., 'Name' vs 'name')

### Data Types
- Ensure data types match Airtable field types
- Convert dates to ISO 8601 format if needed
- Handle arrays/lists appropriately for multi-select fields

### Linked Fields
- Linked fields require Airtable record IDs, not MongoDB IDs
- Must sync Users and Events before Messages
- Handle missing references gracefully

### Error Handling
- Log all errors with context
- Continue processing even if individual records fail
- Review error logs in markdown report

### Performance
- Users table has ~10,000 records - may take several minutes
- Use pagination to avoid memory issues
- Consider batching updates (Airtable API supports batch operations)

### API Rate Limits
- Airtable has rate limits (5 requests/second per base)
- Add rate limiting/throttling if needed
- Consider using batch operations to reduce API calls
