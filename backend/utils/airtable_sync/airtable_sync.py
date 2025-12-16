"""
Airtable Sync Script

Synchronizes MongoDB data (users, events, messages) with Airtable tables
to enable tracking of user engagement and event participation rates.

Implementation follows the plan outlined in README.md
"""

import os
import json
import logging
from datetime import datetime
from pyairtable import Api

# ============================================================================
# CONFIGURATION
# ============================================================================

# Hardcoded Airtable credentials
AIRTABLE_API_KEY = "patdMoOPya9xAXGLG.3a26ab9163b441fa24a5e1edc3d775c4608e447dd7c0ffa50d6de697d121c022"
BASE_ID = "appaquqFN7vvvZGcq"

# Table IDs
USERS_TABLE_ID = "tblQ0OHBit2AqaACy"
EVENTS_TABLE_ID = "tblrscr87h8fbtQTk"
MESSAGES_TABLE_ID = "tbljma5S4NhUn1OYl"

# Directories
SCRIPT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')
REPORTS_DIR = os.path.join(SCRIPT_DIR, 'reports')
MONGODB_DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'mongodb_pull', 'data')

# ============================================================================
# LOGGING SETUP
# ============================================================================

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(os.path.join(REPORTS_DIR, 'airtable_sync.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('AirtableSync')

# ============================================================================
# FIELD MAPPINGS
# ============================================================================

# Field mapping for Users table
USERS_FIELD_MAPPING = {
    'id': 'id',
    'email': 'email',
    'firstName': 'firstName',
    'lastName': 'lastName',
    'phone': 'phone',
    'role': 'role',
    'gender': 'gender',
    'birthDay': 'birthDay',
    'occupation': 'occupation',
    'homeNeighborhood': 'homeNeighborhood',
    'interests': 'interests',
    'tableTypePreference': 'tableTypePreference',
    'event_count': 'event_count',
    'order_count': 'order_count',
    'total_spent': 'total_spent',
    'last_active': 'last_active',
    'days_inactive': 'days_inactive',
    'engagement_status': 'engagement_status',
    'journey_stage': 'journey_stage',
    'value_segment': 'value_segment',
    'user_segment': 'user_segment',
    'churn_risk': 'churn_risk',
    'profile_completeness': 'profile_completeness',
    'profile_ready': 'profile_ready',
    'summary': 'summary',
    'createdAt': 'createdAt',
    'updatedAt': 'updatedAt',
}

# Field mapping for Events table
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
    'participantCount': 'participantCount',
    'participationPercentage': 'participationPercentage',
    'participant_top_interests': 'participant_top_interests',
    'participant_top_occupations': 'participant_top_occupations',
    'qualifies_seat_newcomers': 'qualifies_seat_newcomers',
    'qualifies_fill_the_table': 'qualifies_fill_the_table',
    'summary': 'summary',
    'createdAt': 'createdAt',
    'updatedAt': 'updatedAt',
}

# Field mapping for Messages table
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
    'message_text': 'message',
    'personalization_notes': 'personalization_notes',
    'character_count': 'character_count',
    'similarity_score': 'similarity_score',
    'confidence_percentage': 'confidence_percentage',
    'reasoning': 'reasoning',
    'status': 'status',
    'generated_at': 'createdAt',
    'campaign': 'campaign',
    'updatedAt': 'updatedAt',
}

# ============================================================================
# PHASE 1: CONNECTIVITY TESTING
# ============================================================================

def test_airtable_connectivity():
    """Test connection to Airtable API and access to tables."""
    logger.info("="*80)
    logger.info("PHASE 1: Testing Airtable Connectivity")
    logger.info("="*80)

    try:
        # Initialize API
        api = Api(AIRTABLE_API_KEY)
        base = api.base(BASE_ID)

        # Access tables
        users_table = base.table(USERS_TABLE_ID)
        events_table = base.table(EVENTS_TABLE_ID)
        messages_table = base.table(MESSAGES_TABLE_ID)

        # Test query
        test_user = users_table.first()
        logger.info(f"✓ Successfully connected to Airtable")
        logger.info(f"✓ Test query returned: {test_user['id'] if test_user else 'No records'}")

        return api, base, users_table, events_table, messages_table
    except Exception as e:
        logger.error(f"✗ Failed to connect to Airtable: {e}")
        raise

# ============================================================================
# PHASE 2: PULL AND CACHE AIRTABLE DATA
# ============================================================================

def pull_airtable_data(table, table_name):
    """
    Pull all records from an Airtable table with pagination.
    Save to local cache for future use.
    """
    logger.info(f"\nFetching {table_name} records from Airtable...")
    cache_file = os.path.join(DATA_DIR, f'airtable_{table_name}.json')

    # Check if cached data exists
    if os.path.exists(cache_file):
        logger.info(f"✓ Loading cached Airtable data for {table_name} from {cache_file}")
        with open(cache_file, 'r') as f:
            records = json.load(f)
        logger.info(f"✓ Loaded {len(records)} {table_name} records from cache")
        return records

    # Pull fresh data from Airtable
    all_records = []

    try:
        # Use pagination for large datasets
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
    except Exception as e:
        logger.error(f"✗ Failed to fetch {table_name} records: {e}")
        return []

# ============================================================================
# PHASE 3: LOAD LOCAL MONGODB DATA
# ============================================================================

def load_local_mongodb_data(data_type):
    """Load local MongoDB data from JSON files."""
    file_path = os.path.join(MONGODB_DATA_DIR, f'{data_type}.json')

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

# ============================================================================
# PHASE 4: MATCHING FUNCTIONS
# ============================================================================

def create_airtable_lookup(airtable_records, match_field):
    """Create a lookup dictionary for O(1) matching."""
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
    """Find matching Airtable record for a local MongoDB record."""
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

# ============================================================================
# PHASE 5: FIELD MAPPING
# ============================================================================

def map_fields(local_record, field_mapping):
    """Map MongoDB record fields to Airtable field names."""
    mapped_fields = {}

    for mongodb_field, airtable_field in field_mapping.items():
        if mongodb_field in local_record:
            value = local_record[mongodb_field]
            # Skip None values to avoid clearing existing data
            if value is not None:
                mapped_fields[airtable_field] = value

    return mapped_fields

def identify_unmapped_fields(mongodb_records, field_mapping, table_name):
    """Identify MongoDB fields that aren't mapped to Airtable."""
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

# ============================================================================
# PHASE 6: CREATE AND UPDATE FUNCTIONS
# ============================================================================

def records_are_equal(local_fields, airtable_fields):
    """Compare local record fields with Airtable fields to detect changes."""
    for field_name, local_value in local_fields.items():
        airtable_value = airtable_fields.get(field_name)

        # Handle type mismatches and None values
        if local_value != airtable_value:
            # Allow for minor type differences
            if local_value is None and airtable_value is None:
                continue
            # Convert to strings for comparison
            if str(local_value) != str(airtable_value):
                return False

    return True

def create_airtable_record(table, fields, record_type):
    """Create a new record in Airtable."""
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
    """Update an existing Airtable record. Skip update if values are the same."""
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

# ============================================================================
# PHASE 7: SYNC PROCESS
# ============================================================================

def sync_table(local_records, airtable_lookup, table, field_mapping, match_field, table_name):
    """Sync local records to Airtable table."""
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

# ============================================================================
# PHASE 8: LINKED FIELDS
# ============================================================================

def create_id_mapping(mongodb_records, airtable_lookup, mongodb_id_field, match_field):
    """Create mapping from MongoDB ID to Airtable record ID."""
    id_mapping = {}

    for record in mongodb_records:
        mongodb_id = record.get(mongodb_id_field)
        match_value = str(record.get(match_field, '')).strip().lower()

        if mongodb_id and match_value in airtable_lookup:
            airtable_id = airtable_lookup[match_value]['id']
            id_mapping[mongodb_id] = airtable_id

    logger.info(f"✓ Created ID mapping: {len(id_mapping)} MongoDB IDs -> Airtable IDs")
    return id_mapping

# ============================================================================
# PHASE 9: REPORTING
# ============================================================================

def generate_sync_report(users_stats, events_stats, messages_stats,
                         users_unmapped, events_unmapped, messages_unmapped,
                         errors_log):
    """Generate markdown report of sync operation."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = os.path.join(REPORTS_DIR, f'sync_report_{timestamp}.md')

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

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    logger.info("="*80)
    logger.info("AIRTABLE SYNC STARTING")
    logger.info("="*80)

    errors_log = []

    try:
        # Phase 1: Test connectivity
        api, base, users_table, events_table, messages_table = test_airtable_connectivity()

        # Phase 2: Pull Airtable data
        logger.info("\n" + "="*80)
        logger.info("PHASE 2: Pulling Airtable Data")
        logger.info("="*80)
        users_airtable_data = pull_airtable_data(users_table, 'users')
        events_airtable_data = pull_airtable_data(events_table, 'events')
        messages_airtable_data = pull_airtable_data(messages_table, 'messages')

        # Phase 3: Load MongoDB data
        logger.info("\n" + "="*80)
        logger.info("PHASE 3: Loading MongoDB Data")
        logger.info("="*80)
        users_mongodb = load_local_mongodb_data('users')
        events_mongodb = load_local_mongodb_data('events')
        messages_mongodb = load_local_mongodb_data('messages')

        # Phase 4: Create lookups
        logger.info("\n" + "="*80)
        logger.info("PHASE 4: Creating Lookups")
        logger.info("="*80)
        users_lookup = create_airtable_lookup(users_airtable_data, 'email')
        events_lookup = create_airtable_lookup(events_airtable_data, 'Name')
        messages_lookup = create_airtable_lookup(messages_airtable_data, 'message')

        # Phase 5: Identify unmapped fields
        logger.info("\n" + "="*80)
        logger.info("PHASE 5: Identifying Unmapped Fields")
        logger.info("="*80)
        users_unmapped = identify_unmapped_fields(users_mongodb, USERS_FIELD_MAPPING, 'users')
        events_unmapped = identify_unmapped_fields(events_mongodb, EVENTS_FIELD_MAPPING, 'events')
        messages_unmapped = identify_unmapped_fields(messages_mongodb, MESSAGES_FIELD_MAPPING, 'messages')

        # Phase 7: Sync tables
        logger.info("\n" + "="*80)
        logger.info("PHASE 7: Syncing Tables")
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
            'message_text',  # Note: local field is 'message_text'
            'messages'
        )

        # Phase 9: Generate report
        logger.info("\n" + "="*80)
        logger.info("PHASE 9: Generating Report")
        logger.info("="*80)
        report_file = generate_sync_report(
            users_stats, events_stats, messages_stats,
            users_unmapped, events_unmapped, messages_unmapped,
            errors_log
        )

        logger.info("\n" + "="*80)
        logger.info("AIRTABLE SYNC COMPLETED SUCCESSFULLY")
        logger.info("="*80)
        logger.info(f"Report: {report_file}")

    except Exception as e:
        logger.error(f"✗ Fatal error during sync: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
