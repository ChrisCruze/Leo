# AI Generate Utility

## Overview

This utility provides a centralized way for scripts in the `backend/scripts/` folder to interface with Claude AI API. Instead of each script managing its own Anthropic client and API calls, they can use these common functions.

## Executable Plan

### Phase 1: Create Core AI Generate Module

#### Step 1.1: Create `ai_generate.py` with Core Functions

Create `backend/utils/ai_generate/ai_generate.py` with the following components:

**Configuration:**
- Model: `claude-sonnet-4-20250514`
- API Key: Retrieved from environment variable `ANTHROPIC_API_KEY`
- Max Tokens: `4096`
- Default Temperature: `0.7` (can be overridden)

**Core Function 1: `ai_generate_meta_tag_parse()`**

```python
def ai_generate_meta_tag_parse(
    prompt: str,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
    temperature: float = 0.7,
    api_key: str = None
) -> dict:
    """
    Generate content from Claude and parse response from XML/JSON tags.

    Args:
        prompt: The prompt to send to Claude
        model: Claude model to use (default: claude-sonnet-4-20250514)
        max_tokens: Maximum tokens in response (default: 4096)
        temperature: Creativity level 0-1 (default: 0.7)
        api_key: Optional API key (defaults to ANTHROPIC_API_KEY env var)

    Returns:
        Parsed object/dict from the LLM response

    Raises:
        ValueError: If API key is not provided
        json.JSONDecodeError: If response cannot be parsed
    """
```

**Implementation details:**
1. Initialize Anthropic client with API key (from parameter or environment)
2. Call `messages.create()` with the prompt
3. Extract response text from `response.content[0].text`
4. Parse JSON using regex pattern: `r'\{[\s\S]*\}'` or `r'\[[\s\S]*\]'`
5. Return parsed dictionary/list object

**Core Function 2: `ai_generate_with_quality_check()`**

```python
def ai_generate_with_quality_check(
    initial_prompt: str,
    quality_check_prompt: str,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
    temperature: float = 0.7,
    api_key: str = None,
    max_iterations: int = 1
) -> dict:
    """
    Generate content and run quality check on the result.

    Args:
        initial_prompt: First prompt to generate content
        quality_check_prompt: Prompt template to critique the initial response
                             Use {initial_response} placeholder for the generated content
        model: Claude model to use
        max_tokens: Maximum tokens in response
        temperature: Creativity level 0-1
        api_key: Optional API key
        max_iterations: Number of quality check iterations (default: 1)

    Returns:
        Dictionary containing:
        - 'initial_response': The original generated content
        - 'quality_check_response': The critique/quality check response
        - 'iterations': Number of iterations performed
    """
```

**Implementation details:**
1. Call `ai_generate_meta_tag_parse()` with `initial_prompt`
2. Format `quality_check_prompt` by replacing `{initial_response}` placeholder with the generated content
3. Call `ai_generate_meta_tag_parse()` with the quality check prompt
4. Return dictionary with both responses

#### Step 1.2: Create `__init__.py`

Create `backend/utils/ai_generate/__init__.py` to expose the functions:

```python
from .ai_generate import (
    ai_generate_meta_tag_parse,
    ai_generate_with_quality_check
)

__all__ = [
    'ai_generate_meta_tag_parse',
    'ai_generate_with_quality_check'
]
```

### Phase 2: Update Existing Scripts to Use AI Generate Utility

#### Step 2.1: Update `fill_the_table.py`

**Location 1: Import Section (Lines 1-54)**

Add import after existing helper imports:
```python
from helpers.mongodb_pull import MongoDBPull
from utils.ai_generate import ai_generate_meta_tag_parse  # ADD THIS LINE
```

**Location 2: Remove Anthropic Initialization (Lines 219-231)**

Remove or comment out the `_init_anthropic()` method:
```python
# def _init_anthropic(self):
#     """Initialize Anthropic client for Cuculi MCP"""
#     try:
#         api_key = os.getenv('ANTHROPIC_API_KEY')
#         if not api_key:
#             raise ValueError("ANTHROPIC_API_KEY not set")
#
#         self.anthropic_client = Anthropic(api_key=api_key)
#         self.logger.info("Anthropic client initialized")
#     except Exception as e:
#         self.logger.error(f"Failed to initialize Anthropic client: {e}")
#         raise
```

**Location 3: Update `get_matches_from_ai()` (Lines 590-641)**

Replace the API call section (lines 603-636) with:
```python
try:
    self.logger.info("Requesting matches from Claude...")

    # Use ai_generate utility instead of direct API call
    matches = ai_generate_meta_tag_parse(
        prompt=prompt,
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        temperature=0.9
    )

    # Ensure matches is a list
    if not isinstance(matches, list):
        if isinstance(matches, dict) and 'matches' in matches:
            matches = matches['matches']
        else:
            matches = [matches] if matches else []

    self.logger.info(f"Received {len(matches)} matches from Claude")
    return matches

except Exception as e:
    self.logger.error(f"Failed to get matches: {e}")
    return []
```

**Location 4: Update `generate_message_for_user()` (Lines 643-781)**

Replace the API call section (lines 712-767) with:
```python
try:
    # Use ai_generate utility instead of direct API call
    message_data = ai_generate_meta_tag_parse(
        prompt=prompt,
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        temperature=0.9
    )

    message_text = message_data.get('message_text', '').strip()
    if not message_text:
        raise ValueError("No message_text in response")

    # Ensure the message ends with the event link
    if not message_text.endswith(event_link):
        if event_link not in message_text:
            message_text = f"{message_text} {event_link}"
        else:
            message_text = message_text.replace(event_link, '').strip()
            message_text = f"{message_text} {event_link}"

    self.logger.info(f"Generated message for user {user.get('_id')}: {message_text[:50]}...")
    self.stats['messages_generated'] += 1

    return {
        'message_text': message_text,
        'personalization_notes': message_data.get('personalization_notes', ''),
        'character_count': len(message_text)
    }

except Exception as e:
    self.logger.error(f"Failed to generate message: {e}")
    # Fallback message with event link
    event_title = event.get('name', 'an upcoming event')
    event_id = str(event.get('_id', ''))
    event_link = f"https://cucu.li/bookings/{event_id}"
    fallback = f"Hi {first_name}! We think you'd enjoy {event_title}. Join us? {event_link}"
    return {
        'message_text': fallback,
        'personalization_notes': 'Error fallback',
        'character_count': len(fallback)
    }
```

**Location 5: Update `__init__()` (Line 150)**

Remove call to `_init_anthropic()`:
```python
# Remove this line:
# self._init_anthropic()
```

#### Step 2.2: Update `return_to_table.py`

**Location 1: Import Section (Lines 1-54)**

Add import after existing helper imports:
```python
from helpers.mongodb_pull import MongoDBPull
from utils.ai_generate import ai_generate_meta_tag_parse  # ADD THIS LINE
```

**Location 2: Remove Anthropic Initialization (Lines 220-231)**

Remove or comment out the `_init_anthropic()` method (same as fill_the_table.py)

**Location 3: Update `get_best_match_for_user()` (Lines 477-573)**

Replace the API call section (lines 494-568) with:
```python
try:
    self.logger.info(f"Finding best match for user: {user.get('firstName', '')} {user.get('lastName', '')}")

    # Create individual prompt
    prompt = self.create_individual_matching_prompt(user, events)

    # Use ai_generate utility instead of direct API call
    match = ai_generate_meta_tag_parse(
        prompt=prompt,
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        temperature=0.7
    )

    # Ensure match is a dict (not list)
    if isinstance(match, list) and len(match) > 0:
        match = match[0]

    if not isinstance(match, dict):
        self.logger.error(f"Invalid match format: {type(match)}")
        return None

    # Find the actual event object
    event_id = match.get('event_id', '')
    event_name = match.get('event_name', '')

    # Try to find by ID first
    matched_event = next((e for e in events if str(e.get('_id', '')) == event_id), None)

    # Fallback to name if ID lookup fails
    if not matched_event and event_name:
        matched_event = next((e for e in events if e.get('name', '') == event_name), None)
        if matched_event:
            event_id = str(matched_event.get('_id', ''))
            self.logger.info(f"  Matched by name instead of ID: {event_name}")

    if not matched_event:
        self.logger.warning(f"Could not find event with ID: {event_id} or name: {event_name}")
        return None

    # Build full match record
    first_name = user.get('firstName', '')
    last_name = user.get('lastName', '')
    user_name = f"{first_name} {last_name}".strip()

    match_record = {
        'user_name': user_name,
        'event_name': match.get('event_name', ''),
        'user_id': str(user.get('_id', '')),
        'event_id': event_id,
        'confidence_percentage': match.get('confidence_percentage', 0),
        'reasoning': match.get('reasoning', ''),
        'match_purpose': match.get('match_purpose', 'reactivate_dormant_user'),
        'strategy': 'reactivate_dormant_user',
        'matched_at': datetime.now(timezone.utc).isoformat(),
        'campaign': 'return-to-table',
        'updatedAt': datetime.now(timezone.utc).isoformat(),
        'user': user,
        'event': matched_event
    }

    self.logger.info(f"  ✓ Found match: {user_name} → {match_record['event_name']} (confidence: {match_record['confidence_percentage']}%)")
    return match_record

except Exception as e:
    self.logger.error(f"Error getting match from AI: {e}")
    self.stats['errors'].append(f"Error getting AI match: {str(e)}")
    return None
```

**Location 4: Update `generate_message_for_user()` (Lines 575-713)**

Replace the API call section (lines 644-699) with the same pattern as fill_the_table.py

**Location 5: Update `__init__()` (Line 151)**

Remove call to `_init_anthropic()`

#### Step 2.3: Update `seat_newcomers.py`

**Location 1: Import Section (Lines 1-54)**

Add import after existing helper imports:
```python
from helpers.mongodb_pull import MongoDBPull
from utils.ai_generate import ai_generate_meta_tag_parse  # ADD THIS LINE
```

**Location 2: Remove Anthropic Initialization (Lines 220-231)**

Remove or comment out the `_init_anthropic()` method (same as other scripts)

**Location 3: Update `get_best_match_for_user()` (Lines 499-595)**

Replace the API call section with the same pattern as return_to_table.py (lines 516-590)

**Location 4: Update `generate_message_for_user()` (Lines 597-736)**

Replace the API call section (lines 667-722) with the same pattern as fill_the_table.py

**Location 5: Update `_generate_self_assessment()` (Lines 738-834)**

Replace the API call section (lines 804-817) with:
```python
# Use ai_generate utility instead of direct API call
assessment = ai_generate_meta_tag_parse(
    prompt=prompt,
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0.7
)

self.logger.info("✓ Generated self-assessment with recommendations")
return assessment
```

**Location 6: Update `__init__()` (Line 151)**

Remove call to `_init_anthropic()`

### Phase 3: Testing and Validation

#### Step 3.1: Create Test Script

Create `backend/utils/ai_generate/test_ai_generate.py`:
```python
#!/usr/bin/env python3
"""Test script for AI generate utilities"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from utils.ai_generate import ai_generate_meta_tag_parse, ai_generate_with_quality_check

def test_basic_generation():
    """Test basic AI generation with JSON parsing"""
    prompt = """Return a JSON object with:
    - name: "Test User"
    - email: "test@example.com"
    - age: 25

    Return only the JSON object."""

    result = ai_generate_meta_tag_parse(prompt)
    print("Basic generation result:", result)
    assert isinstance(result, dict)
    assert result.get('name') == 'Test User'
    print("✓ Basic generation test passed")

def test_quality_check():
    """Test quality check functionality"""
    initial_prompt = """Write a short welcome message for a new user joining a social dining app."""

    quality_check_prompt = """Review this welcome message and provide feedback:

{initial_response}

Return a JSON object with:
- score: number 1-10
- feedback: string with improvement suggestions
- approved: boolean
"""

    result = ai_generate_with_quality_check(
        initial_prompt=initial_prompt,
        quality_check_prompt=quality_check_prompt
    )

    print("Quality check result:", result)
    assert 'initial_response' in result
    assert 'quality_check_response' in result
    print("✓ Quality check test passed")

if __name__ == '__main__':
    print("Testing AI Generate Utilities...")
    test_basic_generation()
    test_quality_check()
    print("\nAll tests passed!")
```

#### Step 3.2: Run Tests

1. Test the utility module:
   ```bash
   cd backend/utils/ai_generate
   python test_ai_generate.py
   ```

2. Test each updated script:
   ```bash
   # Test fill_the_table.py
   cd backend/scripts/fill-the-table
   python fill_the_table.py

   # Test return_to_table.py
   cd backend/scripts/return-to-table
   python return_to_table.py

   # Test seat_newcomers.py
   cd backend/scripts/seat-newcomers
   python seat_newcomers.py
   ```

### Phase 4: Documentation and Cleanup

#### Step 4.1: Update Script READMEs

Add a note to each script's README mentioning the use of the shared AI generate utility.

#### Step 4.2: Remove Anthropic Import

In all three scripts, remove the direct Anthropic import if no longer needed:
```python
# Remove or comment out:
# from anthropic import Anthropic
```

## API Configuration Reference

Based on the existing scripts, here are the API configurations currently in use:

**API Key:**
- Environment Variable: `ANTHROPIC_API_KEY`
- Loaded from `.env` file in script directories or parent directory

**Model:**
- `claude-sonnet-4-20250514`

**Common Parameters:**
- Max Tokens: `4096`
- Temperature:
  - `0.9` for message generation (higher creativity)
  - `0.7` for matching and analysis (more consistent)

**Response Parsing:**
- Uses regex pattern `r'\{[\s\S]*\}'` for JSON objects
- Uses regex pattern `r'\[[\s\S]*\]'` for JSON arrays
- Handles both list and dict responses with fallback logic

## Benefits of This Refactoring

1. **Centralized API Management**: All Claude API calls go through one utility
2. **Consistent Error Handling**: Shared error handling and fallback logic
3. **Easier Testing**: Can mock the utility functions instead of Anthropic client
4. **DRY Principle**: Eliminates code duplication across scripts
5. **Future Flexibility**: Easy to swap AI providers or add caching/rate limiting
6. **Quality Assurance**: Built-in quality check function for improved outputs

## Future Enhancements

- Add response caching to reduce API costs
- Implement rate limiting for API calls
- Add logging for all API interactions
- Support for streaming responses
- Batch processing capabilities
- Cost tracking per script
