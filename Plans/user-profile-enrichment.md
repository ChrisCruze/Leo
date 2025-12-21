# Cuculi User Profile Enrichment Plan

## Overview

This plan outlines the design and implementation of a user profile enrichment system for personalized messaging. The system will process data from multiple sources (MongoDB and Airtable) to create enriched user profiles with comprehensive fields that enable intelligent message personalization and delivery decisions.

## Objectives

1. Define essential user fields for personalized messaging
2. Determine if a user should receive a new message
3. Generate detailed context for message personalization
4. Create a Python script that enriches user profiles by combining data from:
   - Users (MongoDB)
   - Orders (MongoDB)
   - Events (MongoDB)
   - Messages (Airtable)

## Data Sources

### MongoDB Collections
- **Users**: Core user profile data
- **Orders**: User purchase history
- **Events**: Event attendance data (with participants array)

### Airtable
- **Messages**: Message queue and sent message history

## User Profile Fields

### Default Fields (Stored in MongoDB)

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Unique user identifier |
| `email` | String | User email address |
| `interests` | Array[String] | User interests/hobbies |
| `cuisine_preference` | Array[String] | Preferred cuisine types |
| `dietary_restrictions` | Array[String] | Dietary needs (vegetarian, vegan, gluten-free, etc.) |
| `age` | Integer | User age |
| `gender` | String | User gender |
| `occupation` | String | User occupation |
| `relationship_status` | String | Relationship status |
| `table_type_preference` | String | Preferred table type (communal, private, etc.) |
| `home_neighborhood` | String | Home location |
| `work_neighborhood` | String | Work location |

### Calculated Fields (Computed by Script)

| Field | Type | Description |
|-------|------|-------------|
| `has_enough_fields_to_personalize` | Boolean | True if sufficient data exists for personalized messaging |
| `is_first_time_user` | Boolean | True if user has never attended an event |
| `should_request_more_details` | Boolean | True if lacking critical personalization fields |
| `is_healthy_active_user` | Boolean | True if user attends events frequently |
| `is_on_team` | Boolean | True if user is a team member |
| `personalization_score` | Integer | 0-100 score based on available fields |

### Calculated Fields from Events

These fields are derived by filtering events where the user's email appears in the `participants` array:

| Field | Type | Description |
|-------|------|-------------|
| `friends` | Array[String] | Names of participants who've attended multiple events with user |
| `event_history_hosts` | Array[String] | Host names from past events (for host preference prediction) |
| `event_history` | Array[Object] | Event details (name, date, venue) from past attendance |
| `venue_history` | Array[String] | Unique venue names from past events |
| `number_of_events_attended` | Integer | Total events attended |
| `last_event_date` | DateTime | Most recent event attendance date |
| `favorite_event_types` | Array[String] | Most frequently attended event types |
| `average_events_per_month` | Float | Event attendance frequency |
| `days_since_last_event` | Integer | Days elapsed since last event |

### Calculated Fields from Messages

| Field | Type | Description |
|-------|------|-------------|
| `has_queued_messages` | Boolean | True if messages are queued for user |
| `queued_message_count` | Integer | Number of pending messages |
| `has_sent_messages` | Boolean | True if messages have been sent previously |
| `last_message_sent_date` | DateTime | Most recent message send date |
| `days_since_last_message` | Integer | Days elapsed since last message |
| `total_messages_sent` | Integer | Total message count |
| `can_send_new_message` | Boolean | True if eligible for new message (respects cooldown) |

### Summary Field (Most Important)

| Field | Type | Description |
|-------|------|-------------|
| `summary` | String | Comprehensive user summary combining all key fields for AI-powered message generation. Includes: user background, interests, event history, preferences, and engagement patterns |

**Summary Field Generation Logic:**
```
The summary should be a natural language paragraph that includes:
- User demographics (age, occupation, neighborhood)
- Interests and preferences (cuisine, dietary restrictions, table preferences)
- Event engagement (frequency, last attendance, favorite venues/hosts)
- Social context (friends they attend with, relationship status)
- Current status (active/inactive, new/veteran, needs more info)

Example: "Sarah is a 32-year-old software engineer living in Mission District
who works in SOMA. She's a vegetarian interested in hiking and photography,
preferring communal table experiences. She's an active user who has attended
15 events over the past 6 months, most recently 5 days ago at The Vault with
her friends Mike and Jenny. She frequently attends events hosted by Chef Mario
and loves Italian and Thai cuisine venues."
```

## Python Script Architecture

### File Structure
```
user_profile_enrichment/
├── __init__.py
├── enrichment.py          # Main enrichment logic
├── data_loaders.py        # MongoDB and Airtable data loading
├── field_calculators.py   # Field calculation functions
├── models.py              # Data models/schemas
└── main.py                # Sample execution
```

### Core Function Signature

```python
def enrich_user_profiles(
    users: List[Dict],
    orders: List[Dict],
    events: List[Dict],
    messages: List[Dict]
) -> List[Dict]:
    """
    Enriches user profiles with calculated fields.

    Args:
        users: List of user documents from MongoDB
        orders: List of order documents from MongoDB
        events: List of event documents from MongoDB
        messages: List of message records from Airtable

    Returns:
        List of enriched user profiles with all calculated fields
    """
    enriched_users = []

    for user in users:
        # Filter related data
        user_orders = filter_orders_by_user(orders, user['id'])
        user_events = filter_events_by_user_email(events, user['email'])
        user_messages = filter_messages_by_user(messages, user['id'])

        # Calculate fields
        enriched_user = calculate_enriched_profile(
            user,
            user_orders,
            user_events,
            user_messages
        )

        enriched_users.append(enriched_user)

    return enriched_users
```

## Implementation Details

### 1. Data Loading Functions

```python
# data_loaders.py

def load_users_from_mongodb() -> List[Dict]:
    """Load all users from MongoDB users collection"""
    pass

def load_orders_from_mongodb() -> List[Dict]:
    """Load all orders from MongoDB orders collection"""
    pass

def load_events_from_mongodb() -> List[Dict]:
    """Load all events from MongoDB events collection"""
    pass

def load_messages_from_airtable() -> List[Dict]:
    """Load all messages from Airtable"""
    pass
```

### 2. Filtering Functions

```python
# field_calculators.py

def filter_orders_by_user(orders: List[Dict], user_id: str) -> List[Dict]:
    """Filter orders where order['user_id'] == user_id"""
    return [o for o in orders if o.get('user_id') == user_id]

def filter_events_by_user_email(events: List[Dict], user_email: str) -> List[Dict]:
    """
    Filter events where user_email is in event['participants'] array
    participants is a list of email addresses
    """
    return [
        e for e in events
        if user_email in e.get('participants', [])
    ]

def filter_messages_by_user(messages: List[Dict], user_id: str) -> List[Dict]:
    """Filter messages where message['user_id'] == user_id"""
    return [m for m in messages if m.get('user_id') == user_id]
```

### 3. Field Calculation Functions

```python
# field_calculators.py

def calculate_event_derived_fields(user_events: List[Dict]) -> Dict:
    """Calculate all event-derived fields"""
    return {
        'friends': extract_friends(user_events),
        'event_history_hosts': extract_hosts(user_events),
        'event_history': extract_event_history(user_events),
        'venue_history': extract_venues(user_events),
        'number_of_events_attended': len(user_events),
        'last_event_date': get_last_event_date(user_events),
        'favorite_event_types': get_favorite_event_types(user_events),
        'average_events_per_month': calculate_event_frequency(user_events),
        'days_since_last_event': calculate_days_since_last_event(user_events)
    }

def calculate_message_derived_fields(user_messages: List[Dict]) -> Dict:
    """Calculate all message-derived fields"""
    queued = [m for m in user_messages if m.get('status') == 'queued']
    sent = [m for m in user_messages if m.get('status') == 'sent']

    last_sent = max([m.get('sent_date') for m in sent]) if sent else None
    days_since = calculate_days_since(last_sent) if last_sent else None

    return {
        'has_queued_messages': len(queued) > 0,
        'queued_message_count': len(queued),
        'has_sent_messages': len(sent) > 0,
        'last_message_sent_date': last_sent,
        'days_since_last_message': days_since,
        'total_messages_sent': len(sent),
        'can_send_new_message': can_send_message(last_sent)
    }

def calculate_personalization_fields(user: Dict, user_events: List[Dict]) -> Dict:
    """Calculate personalization readiness fields"""
    required_fields = ['interests', 'cuisine_preference', 'age', 'occupation']
    filled_fields = sum(1 for f in required_fields if user.get(f))

    return {
        'has_enough_fields_to_personalize': filled_fields >= 3,
        'is_first_time_user': len(user_events) == 0,
        'should_request_more_details': filled_fields < 2,
        'is_healthy_active_user': len(user_events) >= 3,
        'personalization_score': calculate_personalization_score(user, user_events)
    }

def generate_summary(user: Dict, enriched_fields: Dict) -> str:
    """Generate comprehensive user summary for message personalization"""
    # Combine all relevant fields into natural language summary
    pass
```

### 4. Main Enrichment Function

```python
# enrichment.py

def calculate_enriched_profile(
    user: Dict,
    user_orders: List[Dict],
    user_events: List[Dict],
    user_messages: List[Dict]
) -> Dict:
    """
    Calculate all enriched fields for a single user
    """
    enriched = user.copy()

    # Calculate event-derived fields
    event_fields = calculate_event_derived_fields(user_events)
    enriched.update(event_fields)

    # Calculate message-derived fields
    message_fields = calculate_message_derived_fields(user_messages)
    enriched.update(message_fields)

    # Calculate personalization fields
    personalization_fields = calculate_personalization_fields(user, user_events)
    enriched.update(personalization_fields)

    # Calculate order-derived fields if needed
    enriched['total_orders'] = len(user_orders)

    # Generate summary (most important field)
    enriched['summary'] = generate_summary(user, enriched)

    return enriched
```

## Sample Data Structure for Testing

### Sample User
```python
sample_user = {
    'id': 'user_001',
    'email': 'sarah.chen@email.com',
    'interests': ['hiking', 'photography', 'cooking'],
    'cuisine_preference': ['Italian', 'Thai', 'Japanese'],
    'dietary_restrictions': ['vegetarian'],
    'age': 32,
    'gender': 'Female',
    'occupation': 'Software Engineer',
    'relationship_status': 'Single',
    'table_type_preference': 'communal',
    'home_neighborhood': 'Mission District',
    'work_neighborhood': 'SOMA'
}
```

### Sample Events
```python
sample_events = [
    {
        'id': 'event_001',
        'name': 'Italian Wine Tasting',
        'date': '2024-01-15',
        'venue': 'The Vault',
        'host': 'Chef Mario',
        'participants': ['sarah.chen@email.com', 'mike.jones@email.com', 'jenny.kim@email.com'],
        'event_type': 'wine_tasting'
    },
    {
        'id': 'event_002',
        'name': 'Thai Cooking Class',
        'date': '2024-01-22',
        'venue': 'Culinary Studio',
        'host': 'Chef Ploy',
        'participants': ['sarah.chen@email.com', 'mike.jones@email.com'],
        'event_type': 'cooking_class'
    },
    {
        'id': 'event_003',
        'name': 'Farm to Table Dinner',
        'date': '2024-02-05',
        'venue': 'The Vault',
        'host': 'Chef Mario',
        'participants': ['sarah.chen@email.com', 'jenny.kim@email.com', 'alex.wong@email.com'],
        'event_type': 'dinner'
    }
]
```

### Sample Orders
```python
sample_orders = [
    {
        'id': 'order_001',
        'user_id': 'user_001',
        'event_id': 'event_001',
        'amount': 75.00,
        'date': '2024-01-10'
    },
    {
        'id': 'order_002',
        'user_id': 'user_001',
        'event_id': 'event_002',
        'amount': 85.00,
        'date': '2024-01-18'
    }
]
```

### Sample Messages
```python
sample_messages = [
    {
        'id': 'msg_001',
        'user_id': 'user_001',
        'content': 'Hey Sarah! Chef Mario is hosting another Italian dinner...',
        'status': 'sent',
        'sent_date': '2024-01-25'
    },
    {
        'id': 'msg_002',
        'user_id': 'user_001',
        'content': 'New Thai cooking class with Chef Ploy...',
        'status': 'queued',
        'created_date': '2024-02-10'
    }
]
```

### Expected Enriched Output
```python
enriched_user = {
    # Original fields
    'id': 'user_001',
    'email': 'sarah.chen@email.com',
    'interests': ['hiking', 'photography', 'cooking'],
    # ... all original fields ...

    # Event-derived fields
    'friends': ['Mike Jones', 'Jenny Kim'],  # Attended 2+ events together
    'event_history_hosts': ['Chef Mario', 'Chef Ploy'],
    'event_history': [
        {'name': 'Italian Wine Tasting', 'date': '2024-01-15', 'venue': 'The Vault'},
        {'name': 'Thai Cooking Class', 'date': '2024-01-22', 'venue': 'Culinary Studio'},
        {'name': 'Farm to Table Dinner', 'date': '2024-02-05', 'venue': 'The Vault'}
    ],
    'venue_history': ['The Vault', 'Culinary Studio'],
    'number_of_events_attended': 3,
    'last_event_date': '2024-02-05',
    'days_since_last_event': 5,

    # Message-derived fields
    'has_queued_messages': True,
    'queued_message_count': 1,
    'has_sent_messages': True,
    'last_message_sent_date': '2024-01-25',
    'days_since_last_message': 16,
    'total_messages_sent': 1,
    'can_send_new_message': True,

    # Personalization fields
    'has_enough_fields_to_personalize': True,
    'is_first_time_user': False,
    'should_request_more_details': False,
    'is_healthy_active_user': True,
    'is_on_team': False,
    'personalization_score': 85,

    # Summary field
    'summary': "Sarah is a 32-year-old software engineer living in Mission District who works in SOMA. She's a vegetarian interested in hiking, photography, and cooking, preferring communal table experiences. She's an active user who has attended 3 events, most recently 5 days ago at The Vault. She frequently attends events hosted by Chef Mario and enjoys Italian and Thai cuisine venues. She often attends with her friends Mike Jones and Jenny Kim."
}
```

## Main Function Implementation

```python
# main.py

def main():
    """
    Demonstration of user profile enrichment with sample data
    """
    # Sample data (as defined above)
    users = [sample_user]
    orders = sample_orders
    events = sample_events
    messages = sample_messages

    print("=" * 80)
    print("USER PROFILE ENRICHMENT - SAMPLE RUN")
    print("=" * 80)

    print("\n📊 Input Data:")
    print(f"  Users: {len(users)}")
    print(f"  Orders: {len(orders)}")
    print(f"  Events: {len(events)}")
    print(f"  Messages: {len(messages)}")

    # Enrich profiles
    enriched_users = enrich_user_profiles(users, orders, events, messages)

    # Display results for each user
    for enriched_user in enriched_users:
        print("\n" + "=" * 80)
        print(f"👤 User: {enriched_user['email']}")
        print("=" * 80)

        print("\n📋 Default Fields:")
        for field in ['age', 'occupation', 'home_neighborhood', 'interests', 'cuisine_preference']:
            print(f"  {field}: {enriched_user.get(field)}")

        print("\n📅 Event-Derived Fields:")
        print(f"  Number of events attended: {enriched_user['number_of_events_attended']}")
        print(f"  Last event date: {enriched_user['last_event_date']}")
        print(f"  Days since last event: {enriched_user['days_since_last_event']}")
        print(f"  Friends: {enriched_user['friends']}")
        print(f"  Favorite hosts: {enriched_user['event_history_hosts']}")
        print(f"  Venue history: {enriched_user['venue_history']}")

        print("\n💬 Message-Derived Fields:")
        print(f"  Has queued messages: {enriched_user['has_queued_messages']}")
        print(f"  Queued message count: {enriched_user['queued_message_count']}")
        print(f"  Last message sent: {enriched_user.get('last_message_sent_date')}")
        print(f"  Can send new message: {enriched_user['can_send_new_message']}")

        print("\n🎯 Personalization Fields:")
        print(f"  Has enough fields to personalize: {enriched_user['has_enough_fields_to_personalize']}")
        print(f"  Is first time user: {enriched_user['is_first_time_user']}")
        print(f"  Should request more details: {enriched_user['should_request_more_details']}")
        print(f"  Is healthy active user: {enriched_user['is_healthy_active_user']}")
        print(f"  Personalization score: {enriched_user['personalization_score']}/100")

        print("\n📝 Summary:")
        print(f"  {enriched_user['summary']}")

        print("\n✅ Messaging Decision:")
        if enriched_user['can_send_new_message'] and enriched_user['has_enough_fields_to_personalize']:
            print("  → SEND PERSONALIZED MESSAGE")
        elif enriched_user['should_request_more_details']:
            print("  → REQUEST MORE USER DETAILS")
        else:
            print("  → WAIT (cooldown period or insufficient data)")

if __name__ == '__main__':
    main()
```

## Implementation Steps

1. **Phase 1: Data Models & Loading**
   - Define Pydantic models for User, Order, Event, Message
   - Implement MongoDB connection and data loading
   - Implement Airtable connection and data loading
   - Write unit tests for data loading

2. **Phase 2: Filtering Functions**
   - Implement order filtering by user_id
   - Implement event filtering by participant email
   - Implement message filtering by user_id
   - Write unit tests for filtering

3. **Phase 3: Field Calculators**
   - Implement event-derived field calculators
   - Implement message-derived field calculators
   - Implement personalization field calculators
   - Write unit tests for each calculator

4. **Phase 4: Summary Generation**
   - Implement summary field generation logic
   - Create templates for different user types
   - Test summary quality with various user profiles

5. **Phase 5: Main Enrichment Function**
   - Implement `enrich_user_profiles()` function
   - Implement `calculate_enriched_profile()` function
   - Integration testing with sample data

6. **Phase 6: Sample Data & Main Function**
   - Create comprehensive sample datasets
   - Implement main() demonstration function
   - Add formatted output and logging

7. **Phase 7: Documentation & Testing**
   - Add docstrings to all functions
   - Create README with usage examples
   - Write integration tests
   - Performance testing with large datasets

## Success Criteria

- ✅ Script successfully loads data from MongoDB and Airtable
- ✅ All filtering functions correctly match users to their data
- ✅ All calculated fields are accurately computed
- ✅ Summary field provides comprehensive, readable user context
- ✅ Main function demonstrates enrichment with sample data
- ✅ Script can process 1000+ users efficiently
- ✅ Code is well-documented and maintainable
- ✅ Unit test coverage > 80%

## Future Enhancements

- Add machine learning for event recommendation scores
- Implement caching for frequently accessed users
- Add support for batch processing
- Create API endpoint for real-time enrichment
- Add monitoring and alerting for data quality issues
- Implement A/B testing framework for message personalization
