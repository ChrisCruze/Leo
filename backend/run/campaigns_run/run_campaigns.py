#!/usr/bin/env python3
"""
Campaign Orchestrator Script

This script orchestrates all three campaigns (fill-the-table, return-to-table, seat-newcomers),
runs them, collects their results, combines and deduplicates the data, and saves to local files
for Airtable sync.
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')
sys.path.insert(0, backend_dir)

def setup_logging() -> logging.Logger:
    """Set up logging for the orchestrator"""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_dir, f"run_campaigns_{timestamp}.log")

    logger = logging.getLogger('CampaignOrchestrator')
    logger.setLevel(logging.INFO)
    logger.handlers = []

    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger


def collect_campaign_results(campaign_name: str, campaign_dir: str, logger: logging.Logger) -> Dict[str, List[Dict]]:
    """
    Collect results from a campaign's data/processed folder.

    Args:
        campaign_name: Name of the campaign (e.g., 'fill-the-table')
        campaign_dir: Directory of the campaign script
        logger: Logger instance

    Returns:
        Dict with 'messages', 'users', 'events' keys containing the campaign results
    """
    logger.info(f"Collecting results for {campaign_name}...")

    # Determine the campaign script directory based on campaign name
    if campaign_name == 'fill-the-table':
        script_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'fill-the-table')
    elif campaign_name == 'return-to-table':
        script_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'return-to-table')
    elif campaign_name == 'seat-newcomers':
        script_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'seat-newcomers')
    else:
        logger.error(f"Unknown campaign name: {campaign_name}")
        return {'messages': [], 'users': [], 'events': []}

    processed_dir = os.path.join(script_dir, 'data', 'processed')

    results = {'messages': [], 'users': [], 'events': []}

    # Load messages
    messages_file = os.path.join(processed_dir, 'messages.json')
    if os.path.exists(messages_file):
        with open(messages_file, 'r') as f:
            results['messages'] = json.load(f)
        logger.info(f"  Loaded {len(results['messages'])} messages")
    else:
        logger.warning(f"  No messages file found: {messages_file}")

    # Load users based on campaign type
    if campaign_name == 'fill-the-table':
        users_file = os.path.join(processed_dir, 'top_users.json')
    elif campaign_name == 'return-to-table':
        users_file = os.path.join(processed_dir, 'dormant_users.json')
    elif campaign_name == 'seat-newcomers':
        users_file = os.path.join(processed_dir, 'newcomer_users.json')
    else:
        users_file = None

    if users_file and os.path.exists(users_file):
        with open(users_file, 'r') as f:
            results['users'] = json.load(f)
        logger.info(f"  Loaded {len(results['users'])} users")
    else:
        logger.warning(f"  No users file found: {users_file}")

    # Load events based on campaign type
    if campaign_name == 'fill-the-table':
        events_file = os.path.join(processed_dir, 'underfilled_events.json')
    else:
        events_file = os.path.join(processed_dir, 'future_events.json')

    if events_file and os.path.exists(events_file):
        with open(events_file, 'r') as f:
            results['events'] = json.load(f)
        logger.info(f"  Loaded {len(results['events'])} events")
    else:
        logger.warning(f"  No events file found: {events_file}")

    return results


def combine_campaign_results(campaign_results: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Combine results from multiple campaigns, deduplicating while preserving campaign sources.

    Args:
        campaign_results: List of dicts with keys:
            - 'campaign_name': str (e.g., 'fill-the-table', 'return-to-table', 'seat-newcomers')
            - 'messages': List[Dict]
            - 'users': List[Dict]
            - 'events': List[Dict]

    Returns:
        Dict with keys 'messages', 'users', 'events', each containing deduplicated arrays
        where each item has a 'campaigns' field (list) showing all campaigns it came from
    """
    combined_messages = {}  # key: user_id, value: message dict
    combined_users = {}     # key: user_id, value: user dict
    combined_events = {}    # key: event_id, value: event dict

    for result in campaign_results:
        campaign_name = result['campaign_name']

        # Process messages - dedupe by user_id (one message per user)
        for msg in result['messages']:
            user_id = msg.get('user_id')
            if user_id:
                if user_id not in combined_messages:
                    # First time seeing this user - create new message
                    msg_copy = msg.copy()
                    msg_copy['campaigns'] = [campaign_name]
                    combined_messages[user_id] = msg_copy
                else:
                    # User already has a message - add campaign to list
                    if campaign_name not in combined_messages[user_id]['campaigns']:
                        combined_messages[user_id]['campaigns'].append(campaign_name)

        # Process users - dedupe by user_id
        for user in result['users']:
            # Try both 'id' and '_id' fields
            user_id = user.get('id') or user.get('_id')
            if user_id:
                user_id = str(user_id)
                if user_id not in combined_users:
                    user_copy = user.copy()
                    user_copy['campaigns'] = [campaign_name]
                    combined_users[user_id] = user_copy
                else:
                    if campaign_name not in combined_users[user_id]['campaigns']:
                        combined_users[user_id]['campaigns'].append(campaign_name)

        # Process events - dedupe by event_id
        for event in result['events']:
            # Try both 'id' and '_id' fields
            event_id = event.get('id') or event.get('_id')
            if event_id:
                event_id = str(event_id)
                if event_id not in combined_events:
                    event_copy = event.copy()
                    event_copy['campaigns'] = [campaign_name]
                    combined_events[event_id] = event_copy
                else:
                    if campaign_name not in combined_events[event_id]['campaigns']:
                        combined_events[event_id]['campaigns'].append(campaign_name)

    return {
        'messages': list(combined_messages.values()),
        'users': list(combined_users.values()),
        'events': list(combined_events.values())
    }


def save_combined_results(combined_results: Dict[str, List[Dict]], output_dir: str, logger: logging.Logger):
    """
    Save combined results to local JSON files compatible with airtable_sync.py

    Args:
        combined_results: Dict with 'messages', 'users', 'events' keys
        output_dir: Directory to save files (should be backend/utils/mongodb_pull/data/)
        logger: Logger instance
    """
    os.makedirs(output_dir, exist_ok=True)

    # Save each array to separate JSON files
    for data_type in ['messages', 'users', 'events']:
        file_path = os.path.join(output_dir, f'{data_type}.json')
        with open(file_path, 'w') as f:
            json.dump(combined_results[data_type], f, indent=2, default=str)

        logger.info(f"✓ Saved {len(combined_results[data_type])} {data_type} to {file_path}")


def main():
    """Main entry point for campaign orchestrator"""
    logger = setup_logging()

    logger.info("=" * 80)
    logger.info("Starting Campaign Orchestrator")
    logger.info("=" * 80)

    try:
        # Step 1: Run each campaign
        script_dir = os.path.dirname(os.path.abspath(__file__))
        campaigns = [
            ('fill-the-table', os.path.join(script_dir, 'fill_the_table.py')),
            ('return-to-table', os.path.join(script_dir, 'return_to_table.py')),
            ('seat-newcomers', os.path.join(script_dir, 'seat_newcomers.py'))
        ]

        campaign_results = []

        for campaign_name, campaign_script in campaigns:
            logger.info(f"\n{'=' * 80}")
            logger.info(f"Running {campaign_name} campaign...")
            logger.info(f"{'=' * 80}\n")

            try:
                # Run the campaign script
                result = subprocess.run(
                    [sys.executable, campaign_script],
                    cwd=script_dir,
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    logger.error(f"✗ {campaign_name} failed with exit code {result.returncode}")
                    logger.error(f"STDOUT:\n{result.stdout}")
                    logger.error(f"STDERR:\n{result.stderr}")
                    # Continue with other campaigns even if one fails
                    continue
                else:
                    logger.info(f"STDOUT:\n{result.stdout}")

                # Collect results from the campaign's data/processed folder
                results = collect_campaign_results(
                    campaign_name,
                    script_dir,
                    logger
                )

                campaign_results.append({
                    'campaign_name': campaign_name,
                    'messages': results['messages'],
                    'users': results['users'],
                    'events': results['events']
                })

                logger.info(f"✓ {campaign_name} completed successfully")

            except Exception as e:
                logger.error(f"✗ Error running {campaign_name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Continue with other campaigns even if one fails
                continue

        # Step 2: Combine and deduplicate results
        logger.info(f"\n{'=' * 80}")
        logger.info("Combining and deduplicating campaign results...")
        logger.info(f"{'=' * 80}\n")

        combined_results = combine_campaign_results(campaign_results)

        logger.info(f"Combined results:")
        logger.info(f"  Messages: {len(combined_results['messages'])} (deduplicated by user_id)")
        logger.info(f"  Users: {len(combined_results['users'])} (deduplicated by user_id)")
        logger.info(f"  Events: {len(combined_results['events'])} (deduplicated by event_id)")

        # Step 3: Save combined results to backend/utils/mongodb_pull/data/
        output_dir = os.path.join(backend_dir, 'utils', 'mongodb_pull', 'data')
        save_combined_results(combined_results, output_dir, logger)

        logger.info(f"\n{'=' * 80}")
        logger.info("Campaign Orchestrator completed successfully!")
        logger.info(f"{'=' * 80}")
        logger.info(f"\nCombined results saved to: {output_dir}")
        logger.info(f"  - messages.json: {len(combined_results['messages'])} messages")
        logger.info(f"  - users.json: {len(combined_results['users'])} users")
        logger.info(f"  - events.json: {len(combined_results['events'])} events")
        logger.info(f"\nYou can now run airtable_sync.py to sync these results to Airtable.")

    except Exception as e:
        logger.error(f"Fatal error in orchestrator: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
