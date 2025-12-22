"""
Step 1: User Selection Pipeline

This script loads user and message data, combines them, and filters users based on:
1. Users who have already received messages
2. Users missing required profile fields for personalization

Required fields: interests, phone, email, homeNeighborhood, occupation, gender,
relationshipStatus, tableTypePreference, workNeighborhood
"""

import json
import logging
from datetime import datetime
from pathlib import Path


def load_users(filepath):
    """
    Load users from JSON file.
    
    Args:
        filepath: Path to users.json file
        
    Returns:
        List of user dictionaries
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        users = json.load(f)
    return users


def load_messages(filepath):
    """
    Load messages from JSON file.
    
    Args:
        filepath: Path to messages.json file
        
    Returns:
        List of message dictionaries
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        messages = json.load(f)
    return messages


def filter_users_by_messages(users, messages):
    """
    Filter out users who have received messages.
    
    Args:
        users: List of user dictionaries
        messages: List of message dictionaries
        
    Returns:
        Tuple of (filtered_users, statistics_dict)
        statistics_dict contains:
        - total_users: int
        - users_with_messages: int
        - filtered_count: int
        - user_ids_with_messages: set
    """
    total_users = len(users)
    
    # Extract all unique user_ids from messages
    user_ids_with_messages = set()
    for message in messages:
        user_id = message.get('user_id')
        if user_id:
            user_ids_with_messages.add(user_id)
    
    # Filter users: keep only those whose id or _id is NOT in user_ids_with_messages
    filtered_users = []
    for user in users:
        user_id = user.get('id')
        user_id_alt = user.get('_id')
        
        # Check if user received a message
        if user_id not in user_ids_with_messages and user_id_alt not in user_ids_with_messages:
            filtered_users.append(user)
    
    users_with_messages = total_users - len(filtered_users)
    
    statistics = {
        'total_users': total_users,
        'users_with_messages': users_with_messages,
        'filtered_count': len(filtered_users),
        'user_ids_with_messages': user_ids_with_messages
    }
    
    return filtered_users, statistics


def filter_users_by_profile_fields(users):
    """
    Filter out users missing required profile fields.
    
    Required fields:
    - interests: non-empty array/list
    - phone: non-empty string
    - email: non-empty string
    - homeNeighborhood: non-empty string
    - occupation: non-empty string
    - gender: non-empty string
    - relationshipStatus: non-empty string
    - tableTypePreference: non-empty string
    - workNeighborhood: non-empty string
    
    Args:
        users: List of user dictionaries
        
    Returns:
        Tuple of (filtered_users, statistics_dict)
        statistics_dict contains:
        - total_users: int
        - missing_interests: int
        - missing_phone: int
        - missing_email: int
        - missing_homeNeighborhood: int
        - missing_occupation: int
        - missing_gender: int
        - missing_relationshipStatus: int
        - missing_tableTypePreference: int
        - missing_workNeighborhood: int
        - filtered_count: int
        - users_missing_fields: dict mapping field names to lists of user ids
    """
    total_users = len(users)
    
    # Track users missing each field
    users_missing_fields = {
        'interests': [],
        'phone': [],
        'email': [],
        'homeNeighborhood': [],
        'occupation': [],
        'gender': [],
        'relationshipStatus': [],
        'tableTypePreference': [],
        'workNeighborhood': []
    }
    
    filtered_users = []
    
    for user in users:
        user_id = user.get('id') or user.get('_id', 'unknown')
        is_qualified = True
        
        # Check interests (must be non-empty array/list)
        interests = user.get('interests')
        if not interests or not isinstance(interests, list) or len(interests) == 0:
            users_missing_fields['interests'].append(user_id)
            is_qualified = False
        
        # Check phone (must be non-empty string)
        phone = user.get('phone')
        if not phone or not isinstance(phone, str) or len(phone.strip()) == 0:
            users_missing_fields['phone'].append(user_id)
            is_qualified = False
        
        # Check email (must be non-empty string)
        email = user.get('email')
        if not email or not isinstance(email, str) or len(email.strip()) == 0:
            users_missing_fields['email'].append(user_id)
            is_qualified = False
        
        # Check homeNeighborhood (must be non-empty string)
        homeNeighborhood = user.get('homeNeighborhood')
        if not homeNeighborhood or not isinstance(homeNeighborhood, str) or len(homeNeighborhood.strip()) == 0:
            users_missing_fields['homeNeighborhood'].append(user_id)
            is_qualified = False
        
        # Check occupation (must be non-empty string)
        occupation = user.get('occupation')
        if not occupation or not isinstance(occupation, str) or len(occupation.strip()) == 0:
            users_missing_fields['occupation'].append(user_id)
            is_qualified = False
        
        # Check gender (must be non-empty string)
        gender = user.get('gender')
        if not gender or not isinstance(gender, str) or len(gender.strip()) == 0:
            users_missing_fields['gender'].append(user_id)
            is_qualified = False
        
        # Check relationshipStatus (must be non-empty string)
        relationshipStatus = user.get('relationshipStatus')
        if not relationshipStatus or not isinstance(relationshipStatus, str) or len(relationshipStatus.strip()) == 0:
            users_missing_fields['relationshipStatus'].append(user_id)
            is_qualified = False
        
        # Check tableTypePreference (must be non-empty string)
        tableTypePreference = user.get('tableTypePreference')
        if not tableTypePreference or not isinstance(tableTypePreference, str) or len(tableTypePreference.strip()) == 0:
            users_missing_fields['tableTypePreference'].append(user_id)
            is_qualified = False
        
        # Check workNeighborhood (must be non-empty string)
        workNeighborhood = user.get('workNeighborhood')
        if not workNeighborhood or not isinstance(workNeighborhood, str) or len(workNeighborhood.strip()) == 0:
            users_missing_fields['workNeighborhood'].append(user_id)
            is_qualified = False
        
        if is_qualified:
            filtered_users.append(user)
    
    statistics = {
        'total_users': total_users,
        'missing_interests': len(users_missing_fields['interests']),
        'missing_phone': len(users_missing_fields['phone']),
        'missing_email': len(users_missing_fields['email']),
        'missing_homeNeighborhood': len(users_missing_fields['homeNeighborhood']),
        'missing_occupation': len(users_missing_fields['occupation']),
        'missing_gender': len(users_missing_fields['gender']),
        'missing_relationshipStatus': len(users_missing_fields['relationshipStatus']),
        'missing_tableTypePreference': len(users_missing_fields['tableTypePreference']),
        'missing_workNeighborhood': len(users_missing_fields['workNeighborhood']),
        'filtered_count': len(filtered_users),
        'users_missing_fields': users_missing_fields
    }
    
    return filtered_users, statistics


def setup_logging(log_dir):
    """
    Set up logging to both console and file.
    
    Args:
        log_dir: Directory path for log files
        
    Returns:
        Logger instance
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'user_selection_{timestamp}.log'
    
    logger = logging.getLogger('user_selection')
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger, log_file


def save_qualified_users(users, output_path):
    """
    Save qualified users to JSON file.
    
    Args:
        users: List of qualified user dictionaries
        output_path: Path to output JSON file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)
    
    return output_path


def main():
    """
    Main function to run the user selection pipeline.
    """
    # Define paths
    base_dir = Path(__file__).parent.parent
    users_path = base_dir / 'data' / 'raw' / 'users.json'
    messages_path = base_dir / 'data' / 'raw' / 'messages.json'
    output_path = base_dir / 'data' / 'processed' / 'qualified_users.json'
    log_dir = base_dir / 'logs'
    
    # Setup logging
    logger, log_file = setup_logging(log_dir)
    
    logger.info("=" * 80)
    logger.info("USER SELECTION PIPELINE - STEP 1")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    # Step 1: Load users
    logger.info("STEP 1: Loading users...")
    users = load_users(users_path)
    logger.info(f"Loaded {len(users)} users from {users_path}")
    logger.info("")
    
    # Step 2: Load messages
    logger.info("STEP 2: Loading messages...")
    messages = load_messages(messages_path)
    logger.info(f"Loaded {len(messages)} messages from {messages_path}")
    logger.info("")
    
    # Step 3: Filter users who received messages
    logger.info("STEP 3: Filtering users who received messages...")
    users_after_message_filter, message_stats = filter_users_by_messages(users, messages)
    logger.info(f"Total users: {message_stats['total_users']}")
    logger.info(f"Users who received messages: {message_stats['users_with_messages']}")
    logger.info(f"Users remaining after message filter: {message_stats['filtered_count']}")
    logger.info("")
    
    # Step 4: Filter users missing required fields
    logger.info("STEP 4: Filtering users missing required profile fields...")
    qualified_users, field_stats = filter_users_by_profile_fields(users_after_message_filter)
    logger.info(f"Total users before field filter: {field_stats['total_users']}")
    logger.info("")
    logger.info("Users missing required fields:")
    logger.info(f"  - Missing interests: {field_stats['missing_interests']}")
    logger.info(f"  - Missing phone: {field_stats['missing_phone']}")
    logger.info(f"  - Missing email: {field_stats['missing_email']}")
    logger.info(f"  - Missing homeNeighborhood: {field_stats['missing_homeNeighborhood']}")
    logger.info(f"  - Missing occupation: {field_stats['missing_occupation']}")
    logger.info(f"  - Missing gender: {field_stats['missing_gender']}")
    logger.info(f"  - Missing relationshipStatus: {field_stats['missing_relationshipStatus']}")
    logger.info(f"  - Missing tableTypePreference: {field_stats['missing_tableTypePreference']}")
    logger.info(f"  - Missing workNeighborhood: {field_stats['missing_workNeighborhood']}")
    logger.info("")
    logger.info(f"Qualified users: {field_stats['filtered_count']}")
    logger.info("")
    
    # Step 5: Save qualified users
    logger.info("STEP 5: Saving qualified users...")
    save_qualified_users(qualified_users, output_path)
    logger.info(f"Saved {len(qualified_users)} qualified users to {output_path}")
    logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total users loaded: {len(users)}")
    logger.info(f"Users filtered out (received messages): {message_stats['users_with_messages']}")
    total_missing_fields = (
        field_stats['missing_interests'] +
        field_stats['missing_phone'] +
        field_stats['missing_email'] +
        field_stats['missing_homeNeighborhood'] +
        field_stats['missing_occupation'] +
        field_stats['missing_gender'] +
        field_stats['missing_relationshipStatus'] +
        field_stats['missing_tableTypePreference'] +
        field_stats['missing_workNeighborhood']
    )
    logger.info(f"Users filtered out (missing fields): {total_missing_fields}")
    logger.info(f"FINAL QUALIFIED USERS: {len(qualified_users)}")
    logger.info("")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Output file: {output_path}")
    logger.info("=" * 80)
    
    # Log detailed statistics to file
    logger.info("")
    logger.info("DETAILED STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Users missing interests (first 10): {field_stats['users_missing_fields']['interests'][:10]}")
    logger.info(f"Users missing phone (first 10): {field_stats['users_missing_fields']['phone'][:10]}")
    logger.info(f"Users missing email (first 10): {field_stats['users_missing_fields']['email'][:10]}")
    logger.info(f"Users missing homeNeighborhood (first 10): {field_stats['users_missing_fields']['homeNeighborhood'][:10]}")
    logger.info(f"Users missing occupation (first 10): {field_stats['users_missing_fields']['occupation'][:10]}")
    logger.info(f"Users missing gender (first 10): {field_stats['users_missing_fields']['gender'][:10]}")
    logger.info(f"Users missing relationshipStatus (first 10): {field_stats['users_missing_fields']['relationshipStatus'][:10]}")
    logger.info(f"Users missing tableTypePreference (first 10): {field_stats['users_missing_fields']['tableTypePreference'][:10]}")
    logger.info(f"Users missing workNeighborhood (first 10): {field_stats['users_missing_fields']['workNeighborhood'][:10]}")
    
    return len(qualified_users)


if __name__ == '__main__':
    qualified_count = main()
    print(f"\n✓ Pipeline completed. Qualified users: {qualified_count}")

