"""
Airtable CRUD Utility

This module provides reusable functions for Airtable CRUD operations on the Messages table.
Scripts can use these functions instead of managing their own pyairtable clients.

PURPOSE:
--------
Reusable Airtable CRUD operations for Messages table across the pipeline.
Handles record creation, retrieval, updates, and deletion.

CONFIGURATION:
-------------
Uses credentials from airtable_sync.py:
- AIRTABLE_API_KEY: Airtable API key
- BASE_ID: Airtable base ID
- MESSAGES_TABLE_ID: Messages table ID

FIELD MAPPINGS:
--------------
MESSAGES_FIELD_MAPPING maps local field names to Airtable field names:
- user_name, event_name, user_id, event_id, user_email, user_phone
- user_summary, event_summary, confidence_percentage, reasoning, campaign, message
- And other fields as defined in airtable_sync.py

USAGE EXAMPLES:
--------------
See main() function at bottom for example usage patterns.

FUNCTIONS:
---------
- init_airtable_client(): Initializes Airtable API client
- create_message_record(): Creates a message record in Airtable
- get_message_record(): Gets a message record by ID
- update_message_record(): Updates a message record
- delete_message_record(): Deletes a message record
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Tuple
from pyairtable import Api

# Import constants from airtable_sync.py
# These are hardcoded in the original file, so we'll define them here too
# In production, these could be in a shared config file
AIRTABLE_API_KEY = "patdMoOPya9xAXGLG.3a26ab9163b441fa24a5e1edc3d775c4608e447dd7c0ffa50d6de697d121c022"
BASE_ID = "appaquqFN7vvvZGcq"
MESSAGES_TABLE_ID = "tbljma5S4NhUn1OYl"

# Field mapping for Messages table (from airtable_sync.py)
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
    'event_date': 'event_date',
    'message_text': 'message',
    'generated_message': 'message',
    'message': 'message',  # Direct mapping
    'personalization_notes': 'personalization_notes',
    'filled_message_prompt': 'personalization_notes',
    'message_reasoning': 'reasoning',
    'match_reasoning': 'reasoning',
    'reasoning': 'reasoning',
    'character_count': 'character_count',
    'similarity_score': 'similarity_score',
    'confidence_percentage': 'confidence_percentage',
    'match_confidence': 'confidence_percentage',
    'message_confidence': 'confidence_percentage',
    'status': 'status',
    'campaign': 'campaign',
    'generated_at': 'generated_at',
    'updatedAt': 'updatedAt',
}


def init_airtable_client():
    """
    Initialize Airtable API client.
    
    Returns:
        Tuple of (api, base, messages_table)
    """
    api = Api(AIRTABLE_API_KEY)
    base = api.base(BASE_ID)
    messages_table = base.table(MESSAGES_TABLE_ID)
    return api, base, messages_table


def map_fields(local_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map local record fields to Airtable field names.
    
    Args:
        local_record: Dictionary with local field names
        
    Returns:
        Dictionary with Airtable field names
    """
    mapped_fields = {}
    
    for local_field, airtable_field in MESSAGES_FIELD_MAPPING.items():
        if local_field in local_record:
            value = local_record[local_field]
            # Skip None values to avoid clearing existing data
            if value is not None:
                mapped_fields[airtable_field] = value
    
    return mapped_fields


def create_message_record(
    message_record: Dict[str, Any],
    logger: Optional[logging.Logger] = None
) -> Tuple[bool, Optional[str]]:
    """
    Create a message record in Airtable Messages table.
    
    Args:
        message_record: Dictionary containing message data with fields matching
                        MESSAGES_FIELD_MAPPING keys
        logger: Optional logger instance
        
    Returns:
        Tuple of (success: bool, record_id: Optional[str])
        - success: True if record was created successfully, False otherwise
        - record_id: Airtable record ID if successful, None otherwise
    """
    log = logger if logger else logging.getLogger('airtable_crud')
    
    try:
        # Initialize Airtable client
        api, base, messages_table = init_airtable_client()
        
        # Map fields from message_record to Airtable format
        mapped_fields = map_fields(message_record)
        
        if log:
            log.debug(f"Creating message record with fields: {list(mapped_fields.keys())}")
        
        # Create new record in Airtable
        created_record = messages_table.create(mapped_fields)
        record_id = created_record['id']
        
        if log:
            log.info(f"✓ Created message record in Airtable: {record_id}")
        
        return True, record_id
        
    except Exception as e:
        if log:
            log.error(f"✗ Failed to upload message to Airtable: {e}")
            log.error(f"Base ID: {BASE_ID}")
            log.error(f"Table ID: {MESSAGES_TABLE_ID}")
            log.error(f"Full message record attempted:")
            log.error(json.dumps(message_record, indent=2, default=str))
            log.error(f"Mapped fields that would have been uploaded:")
            try:
                mapped_fields = map_fields(message_record)
                log.error(json.dumps(mapped_fields, indent=2, default=str))
            except Exception as map_error:
                log.error(f"Failed to map fields: {map_error}")
        return False, None


def get_message_record(
    record_id: str,
    logger: Optional[logging.Logger] = None
) -> Optional[Dict[str, Any]]:
    """
    Get a message record from Airtable by ID.
    
    Args:
        record_id: Airtable record ID
        logger: Optional logger instance
        
    Returns:
        Record dictionary if found, None otherwise
    """
    log = logger if logger else logging.getLogger('airtable_crud')
    
    try:
        api, base, messages_table = init_airtable_client()
        record = messages_table.get(record_id)
        
        if log:
            log.info(f"✓ Retrieved message record: {record_id}")
        
        return record
        
    except Exception as e:
        if log:
            log.error(f"✗ Failed to get message record {record_id}: {e}")
        return None


def update_message_record(
    record_id: str,
    fields: Dict[str, Any],
    logger: Optional[logging.Logger] = None
) -> bool:
    """
    Update a message record in Airtable.
    
    Args:
        record_id: Airtable record ID
        fields: Dictionary of fields to update (using Airtable field names)
        logger: Optional logger instance
        
    Returns:
        True if update successful, False otherwise
    """
    log = logger if logger else logging.getLogger('airtable_crud')
    
    try:
        api, base, messages_table = init_airtable_client()
        messages_table.update(record_id, fields)
        
        if log:
            log.info(f"✓ Updated message record: {record_id}")
        
        return True
        
    except Exception as e:
        if log:
            log.error(f"✗ Failed to update message record {record_id}: {e}")
        return False


def delete_message_record(
    record_id: str,
    logger: Optional[logging.Logger] = None
) -> bool:
    """
    Delete a message record from Airtable.
    
    Args:
        record_id: Airtable record ID
        logger: Optional logger instance
        
    Returns:
        True if deletion successful, False otherwise
    """
    log = logger if logger else logging.getLogger('airtable_crud')
    
    try:
        api, base, messages_table = init_airtable_client()
        messages_table.delete(record_id)
        
        if log:
            log.info(f"✓ Deleted message record: {record_id}")
        
        return True
        
    except Exception as e:
        if log:
            log.error(f"✗ Failed to delete message record {record_id}: {e}")
        return False


def main():
    """
    Example usage of airtable_crud utility functions.
    
    This demonstrates how step5_match_message.py would use these functions.
    """
    import logging
    
    # Setup basic logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('airtable_crud_example')
    
    # Example: Create a message record
    logger.info("Example: Creating a message record")
    logger.info("=" * 80)
    
    message_record = {
        'user_name': 'John Doe',
        'event_name': 'Test Event',
        'user_id': 'test_user_123',
        'event_id': 'test_event_456',
        'user_email': 'john@example.com',
        'user_phone': '+1234567890',
        'user_summary': 'John is a test user',
        'event_summary': 'This is a test event',
        'message': 'Hi John! Join us for Test Event!',
        'reasoning': 'Test reasoning',
        'confidence_percentage': 85,
        'campaign': 'Fill the Table'
    }
    
    try:
        success, record_id = create_message_record(message_record, logger=logger)
        if success:
            logger.info(f"Successfully created record with ID: {record_id}")
            
            # Example: Get the record back
            logger.info("")
            logger.info("Example: Getting the record back")
            logger.info("=" * 80)
            retrieved = get_message_record(record_id, logger=logger)
            if retrieved:
                logger.info(f"Retrieved record: {retrieved.get('id')}")
            
            # Example: Update the record
            logger.info("")
            logger.info("Example: Updating the record")
            logger.info("=" * 80)
            update_success = update_message_record(
                record_id,
                {'status': 'sent'},
                logger=logger
            )
            if update_success:
                logger.info("Successfully updated record")
            
            # Example: Delete the record (commented out to avoid accidental deletion)
            # logger.info("")
            # logger.info("Example: Deleting the record")
            # logger.info("=" * 80)
            # delete_success = delete_message_record(record_id, logger=logger)
            # if delete_success:
            #     logger.info("Successfully deleted record")
        else:
            logger.error("Failed to create record")
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    main()

