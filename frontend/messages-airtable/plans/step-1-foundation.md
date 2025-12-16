# Step 1: Foundation & Data Layer

## Objective

Build the foundational structure of `messages-airtable.html` with Airtable API integration, state management, and basic message display. By the end of this step, you should successfully fetch messages from Airtable and display them in a simple list.

## What to Build

### 1. HTML Structure

Create `messages-airtable.html` with the following sections:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Messages Review · Leo AI Agent</title>

    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- Font Awesome for icons -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">

    <!-- Google Fonts - Inter -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <!-- Header -->
    <header>
        <!-- App title and navigation -->
    </header>

    <!-- Main Content -->
    <main>
        <!-- Filters section -->
        <!-- View toggle (Table/Card) -->
        <!-- Messages container -->
    </main>

    <!-- Loading state -->
    <div id="loading">
        <!-- Spinner -->
    </div>

    <script>
        // JavaScript code here
    </script>
</body>
</html>
```

**Key Elements:**
- Clean semantic HTML5
- Tailwind CSS via CDN
- Font Awesome for icons
- Google Fonts (Inter) for typography
- Custom styling for specific components

### 2. Airtable Configuration

Set up Airtable API configuration at the top of your JavaScript:

```javascript
// ============================================
// AIRTABLE CONFIGURATION
// ============================================

const AIRTABLE_CONFIG = {
    apiKey: 'YOUR_AIRTABLE_API_KEY', // Replace with actual Airtable Personal Access Token
    baseId: 'appaquqFN7vvvZGcq',
    tableName: 'Messages',
    tableId: 'tbljma5S4NhUn1OYl'
};

const AIRTABLE_API_URL = `https://api.airtable.com/v0/${AIRTABLE_CONFIG.baseId}/${AIRTABLE_CONFIG.tableId}`;

// Headers for Airtable API requests
const AIRTABLE_HEADERS = {
    'Authorization': `Bearer ${AIRTABLE_CONFIG.apiKey}`,
    'Content-Type': 'application/json'
};
```

### 3. State Management

Create a global state object to manage application data:

```javascript
// ============================================
// STATE MANAGEMENT
// ============================================

const appState = {
    messages: [],           // All messages from Airtable
    filteredMessages: [],   // Messages after applying filters
    currentView: 'table',   // 'table' or 'card'
    currentMessage: null,   // Currently selected message for modal
    filters: {
        status: 'all',      // 'all', 'pending', 'approved', 'denied', 'sent'
        campaign: 'all',    // 'all', 'seat-newcomers', 'fill-the-table', etc.
        search: ''          // Search query
    },
    isLoading: false,
    error: null
};
```

### 4. Airtable API Functions

Implement functions to interact with Airtable:

#### 4.1 Fetch Messages

```javascript
// ============================================
// AIRTABLE API FUNCTIONS
// ============================================

/**
 * Fetch all messages from Airtable with pagination
 * Airtable returns max 100 records per request
 */
async function fetchMessagesFromAirtable() {
    try {
        appState.isLoading = true;
        showLoading(true);

        let allRecords = [];
        let offset = null;

        do {
            // Build URL with pagination
            let url = `${AIRTABLE_API_URL}?pageSize=100`;
            if (offset) {
                url += `&offset=${offset}`;
            }

            // Fetch from Airtable
            const response = await fetch(url, {
                method: 'GET',
                headers: AIRTABLE_HEADERS
            });

            if (!response.ok) {
                throw new Error(`Airtable API error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();

            // Add records from this page
            allRecords = allRecords.concat(data.records);

            // Check if there are more pages
            offset = data.offset || null;

        } while (offset);

        console.log(`✓ Fetched ${allRecords.length} messages from Airtable`);

        // Transform Airtable records to our format
        appState.messages = allRecords.map(transformAirtableRecord);
        appState.filteredMessages = [...appState.messages];

        appState.isLoading = false;
        appState.error = null;
        showLoading(false);

        return appState.messages;

    } catch (error) {
        console.error('Error fetching messages:', error);
        appState.isLoading = false;
        appState.error = error.message;
        showLoading(false);
        showToast('Failed to load messages from Airtable', 'error');
        return [];
    }
}

/**
 * Transform Airtable record format to our app format
 */
function transformAirtableRecord(airtableRecord) {
    const fields = airtableRecord.fields;

    return {
        // Airtable metadata
        id: airtableRecord.id,          // Airtable record ID
        createdTime: airtableRecord.createdTime,

        // Message fields
        message: fields['Message'] || '',
        userName: fields['User Name'] || 'Unknown User',
        userId: fields['User ID'] || '',
        eventName: fields['Event Name'] || 'Unknown Event',
        eventId: fields['Event ID'] || '',

        // Context fields
        reasoning: fields['Reasoning'] || '',
        userSummary: fields['User Summary'] || '',
        eventSummary: fields['Event Summary'] || '',

        // Workflow fields
        status: fields['Status'] || 'pending',
        rejectionReason: fields['Rejection Reason'] || '',
        rejectionComment: fields['Rejection Comment'] || '',

        // Metadata
        campaign: fields['Campaign'] || '',
        confidenceScore: fields['Confidence Score'] || 0,
        createdAt: fields['Created At'] || airtableRecord.createdTime,
        reviewedAt: fields['Reviewed At'] || null,
        sentAt: fields['Sent At'] || null
    };
}
```

#### 4.2 Update Message Status

```javascript
/**
 * Update a message record in Airtable
 */
async function updateMessageInAirtable(recordId, updates) {
    try {
        const response = await fetch(`${AIRTABLE_API_URL}/${recordId}`, {
            method: 'PATCH',
            headers: AIRTABLE_HEADERS,
            body: JSON.stringify({
                fields: updates
            })
        });

        if (!response.ok) {
            throw new Error(`Failed to update: ${response.status}`);
        }

        const updatedRecord = await response.json();
        console.log('✓ Updated record in Airtable:', recordId);

        // Update local state
        const index = appState.messages.findIndex(m => m.id === recordId);
        if (index !== -1) {
            appState.messages[index] = transformAirtableRecord(updatedRecord);
            applyFilters(); // Refresh filtered view
        }

        return updatedRecord;

    } catch (error) {
        console.error('Error updating message:', error);
        showToast('Failed to update message', 'error');
        throw error;
    }
}
```

### 5. Basic UI Functions

#### 5.1 Loading State

```javascript
// ============================================
// UI UTILITY FUNCTIONS
// ============================================

function showLoading(show) {
    const loadingEl = document.getElementById('loading');
    if (loadingEl) {
        loadingEl.style.display = show ? 'flex' : 'none';
    }
}

function showToast(message, type = 'info') {
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 px-6 py-3 rounded-lg shadow-lg text-white z-50 ${getToastClass(type)}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    // Fade out and remove after 3 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function getToastClass(type) {
    const classes = {
        'success': 'bg-green-500',
        'error': 'bg-red-500',
        'warning': 'bg-yellow-500',
        'info': 'bg-blue-500'
    };
    return classes[type] || classes['info'];
}
```

#### 5.2 Simple List Display

For Step 1, create a simple list display to verify data fetching:

```javascript
// ============================================
// RENDERING FUNCTIONS
// ============================================

function renderMessages() {
    const container = document.getElementById('messages-container');

    if (!container) return;

    // Clear container
    container.innerHTML = '';

    if (appState.filteredMessages.length === 0) {
        container.innerHTML = `
            <div class="text-center py-12">
                <i class="fas fa-inbox text-gray-400 text-4xl mb-4"></i>
                <p class="text-gray-600">No messages found</p>
            </div>
        `;
        return;
    }

    // Create simple list (will be replaced with table/card view in later steps)
    const listHtml = appState.filteredMessages.map(msg => `
        <div class="bg-white border border-gray-200 rounded-lg p-4 mb-3 shadow-sm">
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <p class="font-medium text-gray-900">${escapeHtml(msg.userName)} → ${escapeHtml(msg.eventName)}</p>
                    <p class="text-sm text-gray-600 mt-1">${escapeHtml(msg.message)}</p>
                </div>
                <span class="px-2 py-1 text-xs rounded-full ${getStatusBadgeClass(msg.status)}">
                    ${msg.status}
                </span>
            </div>
            <div class="mt-2 text-xs text-gray-500">
                ${msg.campaign ? `<span class="mr-3">📋 ${msg.campaign}</span>` : ''}
                ${msg.confidenceScore ? `<span>💯 ${msg.confidenceScore}%</span>` : ''}
            </div>
        </div>
    `).join('');

    container.innerHTML = listHtml;
}

function getStatusBadgeClass(status) {
    const classes = {
        'pending': 'bg-yellow-100 text-yellow-800',
        'approved': 'bg-green-100 text-green-800',
        'denied': 'bg-red-100 text-red-800',
        'sent': 'bg-blue-100 text-blue-800'
    };
    return classes[status] || classes['pending'];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
```

### 6. Filter Functions

```javascript
// ============================================
// FILTER FUNCTIONS
// ============================================

function applyFilters() {
    let filtered = [...appState.messages];

    // Filter by status
    if (appState.filters.status !== 'all') {
        filtered = filtered.filter(m => m.status === appState.filters.status);
    }

    // Filter by campaign
    if (appState.filters.campaign !== 'all') {
        filtered = filtered.filter(m => m.campaign === appState.filters.campaign);
    }

    // Filter by search query
    if (appState.filters.search) {
        const searchLower = appState.filters.search.toLowerCase();
        filtered = filtered.filter(m =>
            m.message.toLowerCase().includes(searchLower) ||
            m.userName.toLowerCase().includes(searchLower) ||
            m.eventName.toLowerCase().includes(searchLower)
        );
    }

    appState.filteredMessages = filtered;
    renderMessages();
    updateMessageCount();
}

function updateMessageCount() {
    const countEl = document.getElementById('message-count');
    if (countEl) {
        countEl.textContent = `${appState.filteredMessages.length} messages`;
    }
}
```

### 7. Event Listeners

```javascript
// ============================================
// EVENT LISTENERS
// ============================================

function initializeEventListeners() {
    // Status filter
    const statusFilter = document.getElementById('filter-status');
    if (statusFilter) {
        statusFilter.addEventListener('change', (e) => {
            appState.filters.status = e.target.value;
            applyFilters();
        });
    }

    // Campaign filter
    const campaignFilter = document.getElementById('filter-campaign');
    if (campaignFilter) {
        campaignFilter.addEventListener('change', (e) => {
            appState.filters.campaign = e.target.value;
            applyFilters();
        });
    }

    // Search input with debounce
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                appState.filters.search = e.target.value;
                applyFilters();
            }, 300);
        });
    }
}
```

### 8. Initialization

```javascript
// ============================================
// INITIALIZATION
// ============================================

async function init() {
    console.log('Initializing Messages Airtable App...');

    // Set up event listeners
    initializeEventListeners();

    // Load messages from Airtable
    await fetchMessagesFromAirtable();

    // Render initial view
    renderMessages();
    updateMessageCount();

    console.log('✓ App initialized successfully');
}

// Run on page load
document.addEventListener('DOMContentLoaded', init);
```

## Testing Checklist

After completing Step 1, verify the following:

### Data Fetching
- [ ] Page loads without JavaScript errors
- [ ] Console shows successful fetch from Airtable
- [ ] All messages are displayed in the list
- [ ] Message count is accurate

### Field Display
- [ ] User Name displays correctly
- [ ] Event Name displays correctly
- [ ] Message text displays correctly
- [ ] Status badge shows with correct color
- [ ] Campaign and confidence score display (if present)

### Filters
- [ ] Status filter dropdown works
- [ ] Campaign filter dropdown works
- [ ] Search input filters messages correctly
- [ ] Message count updates when filtering
- [ ] Clearing filters shows all messages again

### Error Handling
- [ ] Shows loading spinner while fetching
- [ ] Shows error toast if Airtable fetch fails
- [ ] Handles empty message list gracefully
- [ ] No console errors during normal operation

### Performance
- [ ] Page loads in under 2 seconds
- [ ] Search is responsive (no lag)
- [ ] Can handle 100+ messages smoothly

## Common Issues & Solutions

### Issue: CORS Error when fetching from Airtable
**Solution:** Airtable API should support CORS. Ensure API key and base ID are correct. Check browser console for exact error.

### Issue: Messages not displaying
**Solution:** Check:
1. Field names match exactly (case-sensitive)
2. `transformAirtableRecord()` handles missing fields
3. Console logs show data structure

### Issue: Filters not working
**Solution:** Verify:
1. Filter dropdowns have correct IDs
2. Event listeners are attached after DOM load
3. `applyFilters()` is called after state changes

## Next Step

Once Step 1 is complete and tested, proceed to **Step 2: Table View & Actions** where you'll:
- Integrate DataTables.js
- Add approval/denial workflow
- Create detail modal
- Implement message editing

---

**Checkpoint:** You should now have a working app that fetches messages from Airtable and displays them in a simple, filtered list. 🎉
