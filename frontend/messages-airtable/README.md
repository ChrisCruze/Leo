# Messages Airtable - Human-in-the-Loop Control Panel

## Overview

A beautifully designed, flat HTML web application serving as a human-in-the-loop control panel for **Leo**, an LLM Agent whose mission is to craft text messages following best practices to users of Cuculi (a social dining platform) who are struggling to convert app downloads to actual dining event sign-ups.

## Mission

Help Leo send personalized, effective messages to Cuculi users to increase event sign-up conversion rates by providing:
- Review and approval workflow for AI-generated messages
- Message quality control and editing capabilities
- Analytics and insights on message effectiveness
- Clean, elegant interface for efficient human oversight

## Key Differences from messages-review.html

- **Data Source:** Pulls from **Airtable** instead of Firebase
- **Improved UX:** Fixes button click issues present in messages-review.html
- **Better Architecture:** Clean, modular code following best practices
- **Enhanced Features:** Dual view modes (table + card view) for better workflow

## Airtable Configuration

### Base Information
- **Base ID:** `appaquqFN7vvvZGcq` (Cuculi)
- **Table Name:** Messages
- **Table ID:** `tbljma5S4NhUn1OYl`
- **API Key:** `YOUR_AIRTABLE_API_KEY` (Replace with actual key - provided separately for security)

### Required Airtable Fields

The following fields must exist in the Airtable Messages table:

#### Core Message Fields
- **Message** (Long Text) - The text message content
- **User Name** (Single Line Text) - Name of the recipient user
- **User ID** (Single Line Text) - Unique identifier for the user
- **Event Name** (Single Line Text) - Name of the event being promoted
- **Event ID** (Single Line Text) - Unique identifier for the event

#### Context & Intelligence Fields
- **Reasoning** (Long Text) - AI's reasoning for the message approach
- **User Summary** (Long Text) - Summary of user profile and behavior
- **Event Summary** (Long Text) - Summary of event details and appeal

#### Workflow Fields
- **Status** (Single Select) - Approval status: `pending`, `approved`, `denied`, `sent`
- **Rejection Reason** (Single Select) - Category if denied: `tone`, `generic`, `incorrect`, `personalization`, `compliance`, `other`
- **Rejection Comment** (Long Text) - Optional feedback on rejection

#### Metadata Fields
- **Campaign** (Single Select) - Campaign type: `seat-newcomers`, `fill-the-table`, `return-to-table`
- **Confidence Score** (Number) - AI confidence percentage (0-100)
- **Created At** (Date/Time) - When message was generated
- **Reviewed At** (Date/Time) - When message was reviewed
- **Sent At** (Date/Time) - When message was sent

## Core Functionality

### 1. Table View (DataTables.js)
- **Search & Sort:** Full-text search across all message fields
- **Column Visibility:** Show/hide columns based on needs
- **Export:** Export filtered data to CSV/Excel
- **Pagination:** Handle large message volumes efficiently
- **Inline Actions:** Approve/deny buttons on each row
- **Status Filtering:** Filter by pending/approved/denied/sent

### 2. Card View (Product Hunt Style)
- **Visual Layout:** Clean card-based interface inspired by Product Hunt
- **Quick Scan:** Easy visual scanning of messages
- **Hover Effects:** Smooth interactions and animations
- **Action Buttons:** Clear approve/deny/edit actions on each card
- **Responsive:** Mobile-friendly grid layout

### 3. Detail Modal
Opens when clicking "View More" or clicking on a message card. Shows:
- **Message Text:** Full message with edit capability
- **User Summary:** Detailed user profile and behavior context
- **Event Summary:** Detailed event information
- **Reasoning:** AI's strategic reasoning for the message
- **Metadata:** Confidence score, campaign type, timestamps
- **Actions:** Approve, Deny (with reason), Edit, Send

### 4. Approval Workflow
- **Approve:** Mark message as approved and ready to send
- **Deny:** Reject message with mandatory reason selection
  - Tone/voice inappropriate
  - Message too generic
  - Incorrect information
  - Not personalized enough
  - Compliance issue
  - Other (with comment)
- **Edit & Approve:** Make inline edits before approving
- **Send:** Actually send the message via SMS (updates status to 'sent')

### 5. Status Management
Updates Airtable record's `Status` field:
- `pending` → `approved` (on approval)
- `pending` → `denied` (on rejection)
- `approved` → `sent` (after sending)

## Technical Architecture

### Technology Stack
- **HTML5** - Semantic markup
- **Tailwind CSS** - Utility-first styling via CDN
- **DataTables.js** - Advanced table functionality
- **Vanilla JavaScript** - No frameworks, pure JS for simplicity
- **Airtable API** - Direct REST API integration

### Design Principles
- **Flat HTML:** Single self-contained HTML file
- **No Build Process:** Direct browser execution
- **CDN Dependencies:** No local dependencies
- **Responsive Design:** Mobile-first approach
- **Accessibility:** ARIA labels and keyboard navigation
- **Performance:** Lazy loading and efficient rendering

### Code Organization
```javascript
// Configuration
const AIRTABLE_CONFIG = { ... }

// State Management
const appState = { messages: [], filters: {}, currentMessage: null }

// API Functions
async function fetchMessages() { ... }
async function updateMessageStatus() { ... }

// UI Rendering
function renderTableView() { ... }
function renderCardView() { ... }
function renderModal() { ... }

// Event Handlers
function handleApprove() { ... }
function handleDeny() { ... }
function handleSend() { ... }
```

## Implementation Plan

The build is divided into **3 testable steps**:

### Step 1: Foundation & Data Layer
**File:** `plans/step-1-foundation.md`
- Set up HTML structure and Tailwind CSS
- Implement Airtable API integration
- Create data fetching and state management
- Build basic message display (simple list)
- **Test:** Successfully fetch and display messages from Airtable

### Step 2: Table View & Actions
**File:** `plans/step-2-table-view.md`
- Integrate DataTables.js with column visibility
- Implement search, sort, and export functionality
- Add approval/denial workflow with status updates
- Create detail modal with full message context
- **Test:** Can search, filter, approve/deny messages, updates Airtable

### Step 3: Card View & Polish
**File:** `plans/step-3-card-view.md`
- Build Product Hunt-style card view
- Add view toggle between table and card modes
- Implement message editing functionality
- Add SMS sending integration (if applicable)
- Final design polish and responsive refinements
- **Test:** Both views work seamlessly, beautiful UI, full functionality

## User Interface Design

### Color Palette
- **Primary:** Orange (#F97316) - Cuculi brand, action buttons
- **Success:** Green (#10B981) - Approved status
- **Danger:** Red (#EF4444) - Denied status, delete actions
- **Info:** Blue (#3B82F6) - Informational elements
- **Neutral:** Gray scale (#F3F4F6, #6B7280, #1F2937) - UI elements

### Typography
- **Font Family:** Inter (Google Fonts)
- **Headings:** Font weight 600-700
- **Body:** Font weight 400-500
- **Code/IDs:** Monospace font

### Components
- **Cards:** Rounded corners (8px), subtle shadows, hover effects
- **Buttons:** Clear hierarchy (primary, secondary, danger)
- **Modals:** Centered overlay with backdrop blur
- **Tables:** Striped rows, sortable headers, sticky header
- **Forms:** Clean inputs with focus states

## Testing Checklist

### Data Integration
- [ ] Successfully connect to Airtable API
- [ ] Fetch all messages from Messages table
- [ ] Display all required fields correctly
- [ ] Handle empty/missing fields gracefully

### Table View
- [ ] DataTables initializes correctly
- [ ] Search works across all fields
- [ ] Column visibility toggle works
- [ ] Export to CSV/Excel works
- [ ] Sorting works on all columns
- [ ] Pagination handles large datasets

### Card View
- [ ] Cards display all key information
- [ ] Grid layout is responsive
- [ ] Hover effects are smooth
- [ ] Action buttons work correctly

### Approval Workflow
- [ ] Approve button updates status to 'approved'
- [ ] Deny button shows reason selection
- [ ] Rejection reason is saved to Airtable
- [ ] Status updates reflect immediately in UI
- [ ] Can approve from both table and card view

### Detail Modal
- [ ] Opens on "View More" click
- [ ] Displays all message details
- [ ] User/Event summaries are readable
- [ ] Edit functionality works
- [ ] Modal closes properly
- [ ] Actions update Airtable correctly

### Responsive Design
- [ ] Works on desktop (1920x1080)
- [ ] Works on tablet (768x1024)
- [ ] Works on mobile (375x667)
- [ ] Touch interactions work on mobile

### Performance
- [ ] Loads 100+ messages smoothly
- [ ] Filter/search response is instant
- [ ] No memory leaks on long sessions
- [ ] API calls are optimized (caching, debouncing)

## File Structure

```
frontend/messages-airtable/
├── README.md                      # This file
├── messages-airtable.html         # Main application (to be built)
├── plans/
│   ├── step-1-foundation.md      # Step 1: Foundation & Data Layer
│   ├── step-2-table-view.md      # Step 2: Table View & Actions
│   └── step-3-card-view.md       # Step 3: Card View & Polish
└── assets/                        # (Optional) Screenshots and docs
```

## Development Workflow

1. **Read the Plan:** Review this README and all step files
2. **Step-by-Step:** Complete each step in order (1 → 2 → 3)
3. **Test Each Step:** Verify functionality before moving to next step
4. **Iterate:** Refine based on testing and feedback
5. **Deploy:** Single HTML file is ready for deployment

## Future Enhancements

- **Analytics Dashboard:** Message performance metrics
- **A/B Testing:** Compare message variations
- **Template Library:** Save and reuse successful message patterns
- **Batch Actions:** Approve/deny multiple messages at once
- **AI Suggestions:** Real-time improvement suggestions
- **User Feedback:** Track user responses to messages

## Reference Materials

- **Airtable API Docs:** https://airtable.com/developers/web/api/introduction
- **DataTables.js Docs:** https://datatables.net/
- **Tailwind CSS Docs:** https://tailwindcss.com/docs
- **Existing App:** `frontend/messages-review/messages-review.html` (reference for functionality, but rebuild better)

## Notes

- The Airtable API key is hardcoded for simplicity (not production-ready)
- Messages are pulled from the backend script that populates Airtable
- Check `backend/utils/mongodb_pull/mongodb_pull.py` for field names and data structure
- This is a human-in-the-loop tool - Leo generates, humans approve/refine
- Focus on elegant, clean design - this is a professional tool used daily

---

**Built with ❤️ for Leo and Cuculi**
