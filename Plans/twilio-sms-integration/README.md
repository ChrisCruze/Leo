# Leo AI Message Generation Improvement Plan

**Campaign:** Twilio SMS Integration & Message Quality Enhancement
**Status:** Planning Phase
**Created:** 2025-12-17
**Owner:** Leo AI Agent Team

---

## Executive Summary

The purpose of this document is to be strategic and smart about implementing a robust LLM agent to convince mobile app users to attend more social dining events. We're iterating and evolving quickly to improve our process.

Leo (AI Claude Agent) produced his first text batch of text messages to users of a social dining platform called Cuculi in an effort to get them to RSVP to a future dining event.

Leo ran into issues with Twilio driving us to do more research on prompting techniques and SMS best practices.

---

## Problem Statement

### Issues Encountered

1. **Twilio Content Filtering**
   - Messages containing prohibited words like "Poker" were blocked
   - No direct feedback from Twilio API - messages silently failed
   - Current implementation uses Cuculi notification API instead of direct Twilio REST API

2. **SMS Length & Formatting Issues**
   - Character limits not properly accounted for in prompts
   - Emojis consume more characters (up to 4 bytes in SMS encoding)
   - No validation before attempting to send

3. **Lack of Error Handling**
   - No immediate feedback when messages fail
   - Human-in-the-loop dashboard doesn't show Twilio-specific errors
   - Status not updated in Airtable when sends fail

4. **Current Architecture Gaps**
   - Messages sent through Cuculi notification API, not directly via Twilio
   - No integration with Twilio REST API in codebase
   - No status tracking for SMS delivery

---

## Research: Twilio SMS Policies & Best Practices

### Prohibited Content Categories

Based on Twilio's Acceptable Use Policy and Messaging Policy:

1. **Gambling & Gaming**
   - Words: poker, casino, betting, wagering, gambling
   - **Impact:** Social dining events with poker nights are prohibited
   - **Solution:** Use alternative phrasing like "card games" or "game night"

2. **Cannabis & Controlled Substances**
   - Direct or indirect references to marijuana, CBD (in some regions), etc.
   - **Impact:** Cannabis-themed dining events may be blocked
   - **Solution:** Generic phrasing or avoid mentioning entirely

3. **Debt Collection & Financial Services**
   - Aggressive payment language, debt collection
   - **Impact:** Not applicable to Cuculi use case

4. **Phishing & Fraud**
   - URLs that appear suspicious, typos in domain names
   - **Impact:** Ensure all links use trusted `cucu.li` domain
   - **Solution:** Validate URLs before sending

5. **High-Risk Financial**
   - Crypto, payday loans, get-rich-quick schemes
   - **Impact:** Not applicable

6. **Age-Restricted Content**
   - Alcohol, tobacco, firearms
   - **Impact:** Drinking events may require careful wording
   - **Solution:** Focus on social aspect, minimize alcohol emphasis

### SMS Character Limits & Encoding

1. **GSM-7 Encoding (Standard)**
   - **160 characters** per message segment
   - Uses basic Latin characters, numbers, and common symbols
   - Supports: `A-Z a-z 0-9 @ £ $ ¥ è é ù ì ò Ç Ø ø Å å Δ _ Φ Γ Λ Ω Π Ψ Σ Θ Ξ`

2. **UCS-2 Encoding (Unicode/Emoji)**
   - **70 characters** per message segment
   - Triggered by: Emojis, non-Latin characters, special symbols
   - **WARNING:** A single emoji reduces the entire message to 70 chars

3. **Multi-part Messages**
   - Messages split into segments (concatenated SMS)
   - Additional overhead per segment (6-7 characters for headers)
   - GSM-7: 153 chars per segment (160 - 7)
   - UCS-2: 67 chars per segment (70 - 3)

4. **Best Practices**
   - Target **<150 characters** for single-segment SMS (GSM-7)
   - If using emojis, target **<65 characters** for single-segment
   - Recommend **0-2 emojis maximum** to preserve character count
   - Always include URL at the end to maximize message space

### Twilio REST API Requirements

1. **Authentication**
   - Account SID (public identifier)
   - Auth Token (secret key)
   - Store in environment variables: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`

2. **Messaging API Endpoint**
   - `POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json`
   - Required fields:
     - `From`: Twilio phone number (E.164 format: +1234567890)
     - `To`: Recipient phone number (E.164 format)
     - `Body`: Message text

3. **Response Handling**
   - Success: Returns `201 Created` with message SID
   - Failure: Returns error code and message
   - Common errors:
     - `21610`: Unverified phone number (sandbox mode)
     - `21408`: Permission denied (numbers not allowed)
     - `30007`: Message filtered by carrier or Twilio (PROHIBITED CONTENT)
     - `30008`: Unknown destination handset

4. **Status Callbacks**
   - Twilio can POST delivery status updates to a webhook
   - Statuses: `queued`, `sending`, `sent`, `delivered`, `undelivered`, `failed`
   - Recommended: Implement webhook to update Airtable status

---

## Current System Architecture

### Message Generation Flow

```
1. Backend Campaign Scripts (Python)
   ├─ fill_the_table.py
   ├─ return_to_table.py
   └─ seat_newcomers.py
   │
   ├─ Fetch users & events from MongoDB
   ├─ Generate summaries using Claude AI
   ├─ Match users to events using Claude AI
   └─ Generate personalized messages using Claude AI
        └─ Prompts in: fill_the_table.py:682-709

2. Save to Firebase & Airtable
   └─ Messages saved with status: "pending"

3. Human-in-the-Loop Dashboard (Frontend)
   └─ frontend/messages-airtable/messages-airtable.html
   │
   ├─ Review messages
   ├─ Approve/Deny
   └─ Send via Cuculi Notification API
        └─ sendNotification() & sendSMS() functions (lines 680-717)
        └─ NOT using Twilio directly
```

### Key Files Identified

#### Backend (Python)
1. **`backend/run/campaigns_run/fill_the_table.py`** (lines 646-784)
   - `generate_message_for_user()` method
   - Message generation prompt (lines 682-709)
   - Currently targets <180 chars including link

2. **`backend/utils/ai_generate/ai_generate.py`**
   - `ai_generate_meta_tag_parse()` - calls Claude API
   - Used by campaign scripts for message generation

3. **`backend/utils/airtable_sync/airtable_sync.py`**
   - Syncs messages to Airtable for dashboard review

#### Frontend (JavaScript)
1. **`frontend/messages-airtable/messages-airtable.html`** (lines 643-678, 680-717)
   - `sendSMS()` function (lines 643-678)
   - `sendNotification()` function (lines 680-717)
   - Currently uses: `https://api.cuculi.com/notification`
   - **NO DIRECT TWILIO INTEGRATION**

---

## Implementation Plan

### Phase 1: Research & Requirements (CURRENT PHASE)

**Objective:** Understand Twilio policies and define requirements

- [x] Research Twilio Acceptable Use Policy
- [x] Document prohibited words and content categories
- [x] Research SMS character encoding (GSM-7 vs UCS-2)
- [x] Identify current architecture and code locations
- [x] Create this planning document

### Phase 2: Prompt Engineering Updates

**Objective:** Update message generation prompts to comply with Twilio policies

**Location:** `backend/run/campaigns_run/fill_the_table.py:682-709` (and similar files)

**Current Prompt Issues:**
```python
# Current prompt targets <180 chars but doesn't account for:
# 1. Emoji character consumption (reduces limit to 70)
# 2. Prohibited words (poker, casino, etc.)
# 3. Multi-part message overhead
```

**New Prompt Requirements:**

1. **Character Limits**
   ```
   - If using 0 emojis: Target <150 characters (GSM-7, single segment)
   - If using 1-2 emojis: Target <65 characters (UCS-2, single segment)
   - Always include event link at the end
   - Link format: https://cucu.li/bookings/{event_id}
   ```

2. **Prohibited Words Filter**
   ```
   NEVER use these words in messages:
   - poker, casino, gambling, betting, wagering
   - marijuana, cannabis, CBD, weed
   - crypto, cryptocurrency, Bitcoin

   Alternative phrasings:
   - "poker night" → "card game night" or "game night"
   - "casino themed" → "Vegas-style party"
   - "wine & weed pairing" → "wine tasting"
   ```

3. **Content Guidelines**
   ```
   - Focus on social connection, not alcohol
   - Avoid aggressive urgency ("LAST CHANCE", "ACT NOW")
   - Use clear, friendly language
   - Always include opt-out language periodically
   ```

**Updated Prompt Template:**

```python
SMS_GENERATION_PROMPT = f"""You are an expert SMS copywriter for a social dining app.

CRITICAL TWILIO COMPLIANCE RULES:
1. NEVER use these words: poker, casino, gambling, betting, wagering, marijuana, cannabis, CBD
2. Use alternatives: "card games" instead of "poker", "game night" instead of "casino night"
3. If event has prohibited content, use generic social framing

SMS TECHNICAL CONSTRAINTS:
1. Character limit depends on emoji usage:
   - 0 emojis: <150 chars total (including link)
   - 1-2 emojis: <65 chars total (including link)
2. Emoji count: Use 0-2 emojis maximum, only if contextually relevant
3. Link placement: Always at the very end of message
4. Encoding: Use simple punctuation (avoid fancy quotes, dashes, special symbols)

GOAL: Drive RSVPs to underfilled events with personalized, compliant SMS.

STRUCTURE:
[Greeting + First Name] [Hook: interest/location match] [Urgency: spots left] [CTA: "RSVP:" + link]

EXAMPLES (compliant, optimized):
- "Hi Sarah! Ramen Thu 7:30p Midtown, 4 spots left. RSVP: https://cucu.li/bookings/abc123"
- "Hey Mike! Comedy dinner tomorrow West Village, 3 seats. RSVP: https://cucu.li/bookings/abc123"

USER CONTEXT:
Name: {first_name}
Interests: {user_interests}
Location: {user_neighborhood}
Engagement: {engagement_status}

EVENT CONTEXT:
Name: {event_name}
Type: {event_type}
Location: {event_neighborhood}
Date/Time: {event_datetime}
Spots remaining: {spots_remaining}
Link: {event_link}

IMPORTANT: If event name/type contains prohibited words, rephrase generically.

Return JSON:
{{
  "message_text": "Your SMS here (must end with {event_link})",
  "character_count": <actual count>,
  "emoji_count": <0, 1, or 2>,
  "encoding_type": "GSM-7" or "UCS-2",
  "compliance_check": "PASS" or "FAIL: reason",
  "personalization_notes": "Brief explanation"
}}
"""
```

**Files to Update:**
- `backend/run/campaigns_run/fill_the_table.py:generate_message_for_user()`
- `backend/run/campaigns_run/return_to_table.py:generate_message_for_user()`
- `backend/run/campaigns_run/seat_newcomers.py:generate_message_for_user()`

### Phase 3: Backend - Twilio REST API Integration

**Objective:** Implement direct Twilio REST API integration for sending SMS

**3.1 Create Twilio Utility Module**

**New File:** `backend/utils/twilio_sms/twilio_sms.py`

```python
#!/usr/bin/env python3
"""
Twilio SMS Utility

Handles direct integration with Twilio REST API for sending SMS messages.
Provides error handling, status tracking, and compliance validation.
"""

import os
import re
import logging
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException
except ImportError:
    raise ImportError("Twilio SDK not installed. Run: pip install twilio")


# Prohibited words that will cause Twilio to block messages
PROHIBITED_WORDS = [
    'poker', 'casino', 'gambling', 'betting', 'wagering',
    'marijuana', 'cannabis', 'cbd', 'weed',
    'crypto', 'cryptocurrency', 'bitcoin'
]


class TwilioSMSManager:
    """Manager for sending SMS via Twilio REST API"""

    def __init__(self, account_sid: str = None, auth_token: str = None,
                 from_number: str = None, logger: logging.Logger = None):
        """
        Initialize Twilio client.

        Args:
            account_sid: Twilio Account SID (default: env TWILIO_ACCOUNT_SID)
            auth_token: Twilio Auth Token (default: env TWILIO_AUTH_TOKEN)
            from_number: Twilio phone number (default: env TWILIO_FROM_NUMBER)
            logger: Logger instance
        """
        self.account_sid = account_sid or os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = auth_token or os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = from_number or os.getenv('TWILIO_FROM_NUMBER')
        self.logger = logger or logging.getLogger('TwilioSMS')

        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError(
                "Missing Twilio credentials. Set TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER environment variables."
            )

        # Initialize Twilio client
        self.client = Client(self.account_sid, self.auth_token)
        self.logger.info("Twilio SMS Manager initialized")

    def validate_message(self, message_text: str) -> Dict[str, Any]:
        """
        Validate message for Twilio compliance.

        Returns:
            Dict with 'valid' (bool), 'errors' (list), 'warnings' (list)
        """
        errors = []
        warnings = []

        # Check for prohibited words
        message_lower = message_text.lower()
        found_prohibited = [word for word in PROHIBITED_WORDS if word in message_lower]
        if found_prohibited:
            errors.append(f"Contains prohibited words: {', '.join(found_prohibited)}")

        # Check character count
        char_count = len(message_text)
        has_emoji = bool(re.search(r'[^\x00-\x7F]', message_text))

        if has_emoji and char_count > 70:
            warnings.append(
                f"Message with emojis exceeds 70 chars ({char_count}). "
                "Will be sent as multi-part SMS."
            )
        elif not has_emoji and char_count > 160:
            warnings.append(
                f"Message exceeds 160 chars ({char_count}). "
                "Will be sent as multi-part SMS."
            )

        # Check for valid URL
        if 'http://' in message_text or 'https://' in message_text:
            if 'cucu.li' not in message_text:
                warnings.append("URL does not use cucu.li domain. May appear suspicious.")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def send_sms(self, to_number: str, message_text: str,
                 status_callback: str = None) -> Dict[str, Any]:
        """
        Send SMS via Twilio REST API.

        Args:
            to_number: Recipient phone (E.164 format: +1234567890)
            message_text: SMS body
            status_callback: Optional webhook URL for delivery status

        Returns:
            Dict with send result:
            {
                'success': bool,
                'message_sid': str (if success),
                'status': str (queued, sent, failed, etc.),
                'error_code': str (if failed),
                'error_message': str (if failed),
                'sent_at': ISO timestamp
            }
        """
        # Validate message
        validation = self.validate_message(message_text)
        if not validation['valid']:
            return {
                'success': False,
                'error_code': 'VALIDATION_FAILED',
                'error_message': '; '.join(validation['errors']),
                'status': 'failed'
            }

        # Log warnings
        for warning in validation['warnings']:
            self.logger.warning(f"SMS Warning: {warning}")

        try:
            # Send via Twilio
            params = {
                'to': to_number,
                'from_': self.from_number,
                'body': message_text
            }

            if status_callback:
                params['status_callback'] = status_callback

            message = self.client.messages.create(**params)

            self.logger.info(
                f"✓ SMS sent successfully. SID: {message.sid}, "
                f"To: {to_number}, Status: {message.status}"
            )

            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,  # 'queued' or 'sent'
                'to_number': to_number,
                'sent_at': datetime.now().isoformat()
            }

        except TwilioRestException as e:
            self.logger.error(f"Twilio API Error: {e.code} - {e.msg}")

            return {
                'success': False,
                'error_code': str(e.code),
                'error_message': e.msg,
                'status': 'failed',
                'to_number': to_number,
                'sent_at': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Unexpected error sending SMS: {e}")

            return {
                'success': False,
                'error_code': 'UNKNOWN_ERROR',
                'error_message': str(e),
                'status': 'failed'
            }
```

**3.2 Update Airtable Schema**

Add new fields to Airtable "Messages" table:

- `twilio_message_sid` (Single line text) - Twilio message identifier
- `twilio_status` (Single select) - queued, sending, sent, delivered, undelivered, failed
- `twilio_error_code` (Single line text) - Error code if failed
- `twilio_error_message` (Long text) - Error description
- `send_flow` (Single select) - "direct_twilio" or "cuculi_api"

**3.3 Update Airtable Sync Module**

**File:** `backend/utils/airtable_sync/airtable_sync.py`

Add method to update SMS send status:

```python
def update_message_send_status(self, record_id: str, send_result: Dict[str, Any]):
    """
    Update message record with Twilio send result.

    Args:
        record_id: Airtable record ID
        send_result: Dict from TwilioSMSManager.send_sms()
    """
    fields_to_update = {
        'send_flow': 'direct_twilio',
        'sent_at': send_result.get('sent_at')
    }

    if send_result['success']:
        fields_to_update.update({
            'status': 'sent',
            'twilio_message_sid': send_result['message_sid'],
            'twilio_status': send_result['status']
        })
    else:
        fields_to_update.update({
            'status': 'failed',
            'twilio_error_code': send_result.get('error_code'),
            'twilio_error_message': send_result.get('error_message'),
            'twilio_status': 'failed'
        })

    # Update in Airtable
    self.update_record('Messages', record_id, fields_to_update)
```

### Phase 4: Frontend - Dashboard Updates

**Objective:** Update human-in-the-loop dashboard to use Twilio integration

**File:** `frontend/messages-airtable/messages-airtable.html`

**4.1 Create New Twilio Send Endpoint**

Since frontend is static HTML/JS, we need a backend API endpoint.

**New File:** `backend/api/send_sms.py`

```python
#!/usr/bin/env python3
"""
SMS Send API Endpoint

Simple Flask API to send SMS via Twilio from frontend dashboard.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys

# Add utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.twilio_sms.twilio_sms import TwilioSMSManager
from utils.airtable_sync.airtable_sync import AirtableSync

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Initialize managers
twilio_manager = TwilioSMSManager()
airtable_sync = AirtableSync()


@app.route('/api/send-sms', methods=['POST'])
def send_sms():
    """
    Send SMS via Twilio.

    Request body:
    {
        "record_id": "recXXXXXXXXXXXXXX",
        "to_number": "+1234567890",
        "message_text": "Your message here"
    }
    """
    try:
        data = request.json
        record_id = data.get('record_id')
        to_number = data.get('to_number')
        message_text = data.get('message_text')

        if not all([record_id, to_number, message_text]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        # Send via Twilio
        result = twilio_manager.send_sms(to_number, message_text)

        # Update Airtable
        airtable_sync.update_message_send_status(record_id, result)

        return jsonify(result), 200 if result['success'] else 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/validate-message', methods=['POST'])
def validate_message():
    """
    Validate message for Twilio compliance without sending.
    """
    try:
        data = request.json
        message_text = data.get('message_text')

        if not message_text:
            return jsonify({'error': 'message_text required'}), 400

        validation = twilio_manager.validate_message(message_text)
        return jsonify(validation), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

**4.2 Update Frontend Send Function**

**File:** `frontend/messages-airtable/messages-airtable.html` (around line 1226)

Replace `sendMessage()` function:

```javascript
async function sendMessage(messageId) {
    const message = appState.messages.find(m => m.id === messageId);
    if (!message) {
        showToast('Message not found', 'error');
        return;
    }

    const messageText = message.message;
    const toNumber = message.userPhone;  // Must be E.164 format

    if (!toNumber) {
        showToast('User phone number is missing. Cannot send SMS.', 'error');
        return;
    }

    if (!messageText) {
        showToast('Message text is missing. Cannot send SMS.', 'error');
        return;
    }

    if (!confirm(`Send SMS to ${message.userName || 'user'} (${toNumber})?\n\n${messageText}`)) {
        return;
    }

    const sendBtn = document.getElementById('modal-send-btn');
    const originalHTML = sendBtn ? sendBtn.innerHTML : '';
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.classList.add('opacity-75', 'cursor-not-allowed');
        sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Sending via Twilio...';
    }

    try {
        // Call backend API to send via Twilio
        const response = await fetch('http://localhost:5000/api/send-sms', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                record_id: message.id,
                to_number: toNumber,
                message_text: messageText
            })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`SMS sent successfully! SID: ${result.message_sid}`, 'success');

            // Refresh data
            await fetchMessagesFromAirtable();
            if (appState.currentView === 'table') {
                initializeDataTable();
            } else {
                renderCardView();
            }
            updateHeaderStats();
            closeMessageModal();
        } else {
            showToast(`Failed to send: ${result.error_message}`, 'error');

            // Show detailed error in console
            console.error('Twilio Send Error:', result);

            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.classList.remove('opacity-75', 'cursor-not-allowed');
                sendBtn.innerHTML = originalHTML;
            }
        }

    } catch (error) {
        console.error('Error sending SMS:', error);
        showToast('Network error: Failed to send SMS', 'error');

        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.classList.remove('opacity-75', 'cursor-not-allowed');
            sendBtn.innerHTML = originalHTML;
        }
    }
}
```

**4.3 Add Real-time Validation**

Add validation when viewing messages in modal:

```javascript
async function validateMessageInModal(messageText) {
    try {
        const response = await fetch('http://localhost:5000/api/validate-message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message_text: messageText })
        });

        const validation = await response.json();

        // Display validation results in modal
        const validationDiv = document.getElementById('validation-results');
        if (validationDiv) {
            if (!validation.valid) {
                validationDiv.innerHTML = `
                    <div class="bg-red-50 border border-red-200 rounded-lg p-3 mt-4">
                        <p class="text-red-800 font-medium mb-2">⚠️ Validation Errors:</p>
                        <ul class="list-disc list-inside text-red-700 text-sm">
                            ${validation.errors.map(err => `<li>${err}</li>`).join('')}
                        </ul>
                    </div>
                `;
            } else if (validation.warnings.length > 0) {
                validationDiv.innerHTML = `
                    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mt-4">
                        <p class="text-yellow-800 font-medium mb-2">⚠️ Warnings:</p>
                        <ul class="list-disc list-inside text-yellow-700 text-sm">
                            ${validation.warnings.map(warn => `<li>${warn}</li>`).join('')}
                        </ul>
                    </div>
                `;
            } else {
                validationDiv.innerHTML = `
                    <div class="bg-green-50 border border-green-200 rounded-lg p-3 mt-4">
                        <p class="text-green-800 font-medium">✓ Message passes validation</p>
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Validation error:', error);
    }
}
```

### Phase 5: Testing & Deployment

**5.1 Testing Checklist**

- [ ] Test prompt with various event types (poker, wine tasting, casual dining)
- [ ] Verify prohibited words are filtered/replaced
- [ ] Test character counting (with and without emojis)
- [ ] Test Twilio API integration in sandbox mode
- [ ] Verify Airtable status updates correctly
- [ ] Test error handling for invalid phone numbers
- [ ] Test error handling for content policy violations
- [ ] Verify dashboard shows Twilio errors

**5.2 Environment Setup**

```bash
# Backend Python dependencies
pip install twilio flask flask-cors

# Environment variables (.env file)
TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+1234567890

# Existing vars
ANTHROPIC_API_KEY=sk-...
MONGODB_URI=mongodb+srv://...
FIREBASE_DATABASE_URL=https://...
AIRTABLE_API_KEY=pat...
AIRTABLE_BASE_ID=app...
```

**5.3 Deployment Steps**

1. **Backend API Deployment**
   - Deploy Flask API (`backend/api/send_sms.py`) to production server
   - Use Gunicorn/uWSGI for production
   - Set up HTTPS endpoint
   - Configure CORS for frontend domain

2. **Frontend Updates**
   - Update API endpoint URL in `messages-airtable.html`
   - Deploy updated frontend

3. **Twilio Configuration**
   - Upgrade from sandbox to production account
   - Purchase phone number
   - Configure status callback webhook (optional)
   - Set up message filtering settings

---

## Team Communication Plan

### Updated Prompt & Process Documentation

**Audience:** Product, Marketing, Engineering teams

**Document:** `docs/sms-best-practices.md`

**Contents:**
1. Overview of Twilio content policies
2. Prohibited words and alternative phrasing guide
3. Character limits and emoji usage
4. Examples of compliant vs non-compliant messages
5. Process for reviewing and approving messages
6. Dashboard usage guide

**Sample Content:**

```markdown
# SMS Best Practices for Leo AI Agent

## Prohibited Content

Twilio blocks messages containing certain words related to:
- Gambling: poker, casino, betting
- Controlled substances: marijuana, cannabis, CBD
- High-risk financial: crypto, cryptocurrency

## Alternative Phrasing

| ❌ Don't Use | ✅ Use Instead |
|-------------|---------------|
| Poker night | Card game night, Game night |
| Casino themed | Vegas-style, Games & entertainment |
| Wine & weed | Wine tasting, Social gathering |

## Character Limits

- **Without emojis:** Keep under 150 characters
- **With emojis (1-2 max):** Keep under 65 characters
- Always include event link at the end

## Example Messages

✅ **Good:**
"Hi Sarah! Ramen Thu 7:30p Midtown, 4 spots left. RSVP: https://cucu.li/bookings/abc123"
(Character count: 85, No emojis, Compliant)

✅ **Good with emoji:**
"Hey Mike! 🍜 Dinner tomorrow West Village, 3 seats. RSVP: https://cucu.li/bookings/abc123"
(Character count: 68, 1 emoji, Compliant)

❌ **Bad:**
"Last chance! Poker night at downtown casino, only 2 spots left!! Sign up NOW: https://cucu.li/bookings/abc123"
(Issues: Prohibited words "poker" and "casino", aggressive tone, too long)

```

### Dashboard Improvements Communicated

**For Human Reviewers:**

1. **New Validation Indicators**
   - Messages now show real-time validation status
   - Red warnings for prohibited content
   - Yellow warnings for character overruns
   - Green checkmark for compliant messages

2. **Improved Error Feedback**
   - If send fails, specific Twilio error shown
   - Error codes explained in plain language
   - Suggested fixes provided

3. **Status Tracking**
   - New status field shows Twilio delivery status
   - Can track: queued → sending → sent → delivered
   - Failed messages show specific reason

---

## Success Metrics

### Key Performance Indicators (KPIs)

1. **Message Compliance**
   - Target: >99% of messages pass Twilio validation
   - Measure: Validation errors / total messages generated

2. **Delivery Success Rate**
   - Target: >95% of approved messages successfully sent
   - Measure: Twilio status = "delivered" / total sent

3. **Message Quality**
   - Target: <5% message edit rate by human reviewers
   - Measure: Messages edited / total messages generated

4. **Response Efficiency**
   - Target: Immediate error feedback to dashboard
   - Measure: Time from send failure to dashboard update (<30 seconds)

5. **RSVP Conversion**
   - Target: >10% RSVP rate from SMS recipients
   - Measure: Event bookings / messages sent

---

## Risk Mitigation

### Potential Issues & Contingencies

1. **Twilio Account Suspension**
   - **Risk:** Too many policy violations
   - **Mitigation:** Pre-validate all messages, gradual rollout
   - **Contingency:** Maintain Cuculi API as backup

2. **Message Filtering Too Aggressive**
   - **Risk:** Legitimate messages blocked
   - **Mitigation:** Test thoroughly, maintain whitelist of safe phrases
   - **Contingency:** Manual review queue for borderline cases

3. **API Rate Limits**
   - **Risk:** Twilio API throttling during batch sends
   - **Mitigation:** Implement rate limiting (1 msg/sec), queue management
   - **Contingency:** Retry logic with exponential backoff

4. **Phone Number Verification**
   - **Risk:** Invalid/unverified numbers in database
   - **Mitigation:** Validate format before sending, use Twilio Lookup API
   - **Contingency:** Fallback to in-app notifications

---

## Next Steps

### Immediate Actions (Week 1)

- [ ] Set up Twilio sandbox account
- [ ] Create test dataset with prohibited content
- [ ] Implement prompt updates in one campaign script
- [ ] Test prompt with various scenarios
- [ ] Document results

### Short-term Actions (Weeks 2-3)

- [ ] Implement Twilio utility module
- [ ] Update Airtable schema with new fields
- [ ] Create backend API endpoint
- [ ] Update frontend dashboard
- [ ] Integration testing

### Medium-term Actions (Week 4+)

- [ ] Deploy to staging environment
- [ ] Conduct team training on new process
- [ ] Production deployment
- [ ] Monitor metrics and iterate

---

## Appendix

### Code File Locations

| Component | File Path | Key Functions/Lines |
|-----------|-----------|---------------------|
| Message Generation Prompt | `backend/run/campaigns_run/fill_the_table.py` | Lines 682-709 |
| AI Generate Utility | `backend/utils/ai_generate/ai_generate.py` | `ai_generate_meta_tag_parse()` |
| Frontend Send Function | `frontend/messages-airtable/messages-airtable.html` | Lines 1226-1300 |
| Airtable Sync | `backend/utils/airtable_sync/airtable_sync.py` | All methods |

### Resources

- [Twilio Messaging Policy](https://www.twilio.com/en-us/legal/messaging-policy)
- [Twilio REST API Docs](https://www.twilio.com/docs/sms/api)
- [SMS Character Encoding Guide](https://www.twilio.com/docs/glossary/what-is-gsm-7-character-encoding)
- [Twilio Error Codes](https://www.twilio.com/docs/api/errors)

---

## Document Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-17 | Leo AI Agent | Initial plan created |

---

**End of Plan Document**
