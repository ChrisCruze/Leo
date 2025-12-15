# Messages Review App

A focused, streamlined web application for reviewing and managing messages from the Message Queue. Built with a Product Hunt-inspired design (simple, sleek, minimal) and focused exclusively on message review, approval, rejection, and sending functionality.

## Features

- **Message-First Display**: Text message is prominently displayed as the main focus
- **Essential Information**: User name, event name, and campaign name are clearly visible
- **Quick Actions**: Send button for approved messages, View More for details
- **Detailed Modal**: Full message details with user, event, and campaign information
- **Reject with Feedback**: Ability to reject messages with structured feedback
- **Real-Time Updates**: Polls Firebase every 5 seconds for new messages
- **Search & Filter**: Search messages and filter by status (pending, approved, denied, sent)
- **Product Hunt Design**: Clean, minimal aesthetic with generous whitespace

## Usage

### Opening the App

Simply open `messages-review.html` in a web browser:

```bash
# From the messages-review directory
open messages-review.html

# Or navigate to the file in your browser
# File path: apps/messages-review/messages-review.html
```

### Navigation

- **From Dashboard**: Click "Open Messages Review" button in the Message Queue section
- **From Index**: Click "Messages Review" link in the Architecture section sidebar
- **Back to Dashboard**: Click "Back to Dashboard" link in the header

## Features

### Message Cards

Each message card displays:
- **Message text** (large, prominent)
- **User name** (with icon)
- **Event name** (with icon)
- **Campaign badge** (orange badge)
- **Status badge** (color-coded: pending, approved, denied, sent)
- **Actions**: "View More" button and "Send" button (if approved)

### Message Modal

Click "View More" to see:
- Full message text
- User details (name, email, phone)
- Event details
- Campaign name
- Confidence score (if available)
- Reasoning (if available)
- Actions: Approve, Reject, Send

### Rejecting Messages

1. Click "View More" on a pending message
2. Click "Reject" button
3. Select rejection reason (required):
   - Tone/voice inappropriate
   - Message too generic
   - Incorrect information
   - Not personalized enough
   - Compliance issue
   - Other
4. Add optional comments
5. Click "Submit Rejection"

### Sending Messages

1. Message must be approved first
2. Click "Send" button (on card or in modal)
3. Confirm send action
4. Message status updates to "sent" after successful send

## Technology Stack

- **Frontend**: Vanilla HTML/CSS/JavaScript (flat HTML web app)
- **Styling**: Tailwind CSS (CDN)
- **Icons**: Font Awesome 6.4.0 (CDN)
- **Backend**: Firebase Realtime Database (REST API)
- **Notification API**: REST API endpoint for sending SMS

## Configuration

All configuration is hard-coded in the HTML file:
- Firebase configuration
- Notification API endpoint and authentication
- Polling interval (5 seconds)

## Best Practices

This app follows best practices for flat HTML web apps:
- Code organized into logical sections
- Comprehensive error handling
- Loading states for async operations
- Toast notifications for user feedback
- Empty states handled gracefully
- Accessibility (ARIA labels, keyboard navigation)
- Performance optimization (debouncing, efficient DOM updates)
- Security (XSS prevention, input validation)

## Browser Compatibility

- Modern browsers: Chrome, Firefox, Safari, Edge (latest 2 versions)
- No IE support: Uses modern JavaScript (ES6+)
- Mobile: Responsive design, touch-friendly buttons

## Related Files

- `apps/dashboard/dashboard.html` - Full HITL dashboard
- `index.html` - Project documentation with navigation links


