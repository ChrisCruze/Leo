# Step 2: Table View & Actions

## Objective

Upgrade from the simple list to a full-featured DataTables.js table with search, sort, column visibility, export functionality, and implement the approval/denial workflow with a detailed modal view.

## What to Build

### 1. Integrate DataTables.js

Add DataTables.js dependencies to your HTML `<head>`:

```html
<!-- DataTables CSS -->
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
<link rel="stylesheet" href="https://cdn.datatables.net/buttons/2.4.1/css/buttons.dataTables.min.css">

<!-- jQuery (required for DataTables) -->
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>

<!-- DataTables JS -->
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>

<!-- DataTables Buttons for export -->
<script src="https://cdn.datatables.net/buttons/2.4.1/js/dataTables.buttons.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.4.1/js/buttons.html5.min.js"></script>
<script src="https://cdn.datatables.net/buttons/2.4.1/js/buttons.colVis.min.js"></script>
```

### 2. Update HTML Structure

Replace the simple list container with a table:

```html
<!-- In your main section -->
<div class="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
    <table id="messages-table" class="display" style="width:100%">
        <thead>
            <tr>
                <th>User</th>
                <th>Event</th>
                <th>Message</th>
                <th>Status</th>
                <th>Campaign</th>
                <th>Confidence</th>
                <th>Created</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            <!-- Rows will be populated by DataTables -->
        </tbody>
    </table>
</div>
```

### 3. Initialize DataTables

Replace the `renderMessages()` function with DataTables initialization:

```javascript
// ============================================
// DATATABLE INITIALIZATION
// ============================================

let dataTable = null;

function initializeDataTable() {
    // Destroy existing table if it exists
    if (dataTable) {
        dataTable.destroy();
    }

    // Prepare data for DataTables
    const tableData = appState.filteredMessages.map(msg => [
        escapeHtml(msg.userName),
        escapeHtml(msg.eventName),
        truncateText(escapeHtml(msg.message), 100),
        getStatusBadgeHtml(msg.status),
        msg.campaign ? escapeHtml(msg.campaign) : '-',
        msg.confidenceScore ? `${msg.confidenceScore}%` : '-',
        formatDate(msg.createdAt),
        getActionButtonsHtml(msg.id, msg.status)
    ]);

    // Initialize DataTable
    dataTable = $('#messages-table').DataTable({
        data: tableData,
        columns: [
            { title: 'User' },
            { title: 'Event' },
            { title: 'Message' },
            { title: 'Status', orderable: true },
            { title: 'Campaign' },
            { title: 'Confidence' },
            { title: 'Created', type: 'date' },
            { title: 'Actions', orderable: false }
        ],
        order: [[6, 'desc']], // Sort by created date descending
        pageLength: 25,
        lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, 'All']],
        dom: 'Bfrtip',
        buttons: [
            {
                extend: 'colvis',
                text: 'Column Visibility'
            },
            {
                extend: 'csv',
                text: 'Export CSV',
                exportOptions: {
                    columns: [0, 1, 2, 3, 4, 5, 6] // Exclude actions column
                }
            },
            {
                extend: 'excel',
                text: 'Export Excel',
                exportOptions: {
                    columns: [0, 1, 2, 3, 4, 5, 6]
                }
            }
        ],
        language: {
            search: 'Search messages:',
            lengthMenu: 'Show _MENU_ messages per page',
            info: 'Showing _START_ to _END_ of _TOTAL_ messages',
            infoEmpty: 'No messages found',
            infoFiltered: '(filtered from _MAX_ total messages)'
        },
        drawCallback: function() {
            // Re-attach event listeners after table redraw
            attachTableEventListeners();
        }
    });

    console.log('✓ DataTable initialized with', tableData.length, 'messages');
}

function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function getStatusBadgeHtml(status) {
    const badgeClass = getStatusBadgeClass(status);
    return `<span class="px-2 py-1 text-xs rounded-full ${badgeClass}">${status}</span>`;
}

function getActionButtonsHtml(messageId, status) {
    const isPending = status === 'pending';
    const isSent = status === 'sent';

    return `
        <div class="flex items-center gap-2">
            <button
                onclick="openMessageModal('${messageId}')"
                class="text-blue-600 hover:text-blue-800 text-sm"
                title="View Details">
                <i class="fas fa-eye"></i>
            </button>
            ${isPending ? `
                <button
                    onclick="approveMessage('${messageId}')"
                    class="text-green-600 hover:text-green-800 text-sm"
                    title="Approve">
                    <i class="fas fa-check"></i>
                </button>
                <button
                    onclick="openDenyModal('${messageId}')"
                    class="text-red-600 hover:text-red-800 text-sm"
                    title="Deny">
                    <i class="fas fa-times"></i>
                </button>
            ` : ''}
            ${isSent ? `
                <span class="text-xs text-gray-500">Sent</span>
            ` : ''}
        </div>
    `;
}

function attachTableEventListeners() {
    // Event listeners are handled via onclick in HTML for simplicity
    // Alternatively, use event delegation on the table container
}
```

### 4. Approval/Denial Workflow

Implement functions to approve and deny messages:

```javascript
// ============================================
// APPROVAL WORKFLOW
// ============================================

async function approveMessage(messageId) {
    const message = appState.messages.find(m => m.id === messageId);
    if (!message) {
        showToast('Message not found', 'error');
        return;
    }

    if (!confirm(`Approve message to ${message.userName}?`)) {
        return;
    }

    try {
        // Update in Airtable
        await updateMessageInAirtable(messageId, {
            'Status': 'approved',
            'Reviewed At': new Date().toISOString()
        });

        showToast('Message approved successfully', 'success');

        // Refresh table
        await fetchMessagesFromAirtable();
        initializeDataTable();

    } catch (error) {
        console.error('Error approving message:', error);
        showToast('Failed to approve message', 'error');
    }
}

async function denyMessage(messageId, reason, comment) {
    try {
        // Update in Airtable
        await updateMessageInAirtable(messageId, {
            'Status': 'denied',
            'Rejection Reason': reason,
            'Rejection Comment': comment || '',
            'Reviewed At': new Date().toISOString()
        });

        showToast('Message denied', 'success');

        // Close deny modal
        closeDenyModal();

        // Refresh table
        await fetchMessagesFromAirtable();
        initializeDataTable();

    } catch (error) {
        console.error('Error denying message:', error);
        showToast('Failed to deny message', 'error');
    }
}
```

### 5. Detail Modal

Create a modal to show full message details:

```html
<!-- Add to your HTML body -->
<div id="message-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
    <div class="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        <!-- Modal Header -->
        <div class="sticky top-0 bg-white border-b border-gray-200 p-6 flex items-center justify-between">
            <h2 class="text-2xl font-semibold text-gray-900">Message Details</h2>
            <button onclick="closeMessageModal()" class="text-gray-400 hover:text-gray-600">
                <i class="fas fa-times text-xl"></i>
            </button>
        </div>

        <!-- Modal Body -->
        <div class="p-6 space-y-6">
            <!-- Message Text -->
            <div>
                <h3 class="text-sm font-medium text-gray-700 mb-2">Message</h3>
                <div id="modal-message-text" class="p-4 bg-gray-50 rounded-lg text-lg leading-relaxed"></div>
            </div>

            <!-- User & Event Info Side by Side -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- User Info -->
                <div>
                    <h3 class="text-sm font-medium text-gray-700 mb-2">User</h3>
                    <div id="modal-user-info" class="p-4 bg-blue-50 rounded-lg text-sm space-y-2"></div>
                </div>

                <!-- Event Info -->
                <div>
                    <h3 class="text-sm font-medium text-gray-700 mb-2">Event</h3>
                    <div id="modal-event-info" class="p-4 bg-green-50 rounded-lg text-sm space-y-2"></div>
                </div>
            </div>

            <!-- User Summary -->
            <div id="modal-user-summary-section" class="hidden">
                <h3 class="text-sm font-medium text-gray-700 mb-2">User Summary</h3>
                <div id="modal-user-summary" class="p-4 bg-purple-50 rounded-lg text-sm"></div>
            </div>

            <!-- Event Summary -->
            <div id="modal-event-summary-section" class="hidden">
                <h3 class="text-sm font-medium text-gray-700 mb-2">Event Summary</h3>
                <div id="modal-event-summary" class="p-4 bg-orange-50 rounded-lg text-sm"></div>
            </div>

            <!-- Reasoning -->
            <div id="modal-reasoning-section" class="hidden">
                <h3 class="text-sm font-medium text-gray-700 mb-2">AI Reasoning</h3>
                <div id="modal-reasoning" class="p-4 bg-yellow-50 rounded-lg text-sm"></div>
            </div>

            <!-- Metadata -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-gray-200">
                <div>
                    <p class="text-xs text-gray-500">Status</p>
                    <p id="modal-status" class="font-medium"></p>
                </div>
                <div>
                    <p class="text-xs text-gray-500">Campaign</p>
                    <p id="modal-campaign" class="font-medium"></p>
                </div>
                <div>
                    <p class="text-xs text-gray-500">Confidence</p>
                    <p id="modal-confidence" class="font-medium"></p>
                </div>
                <div>
                    <p class="text-xs text-gray-500">Created</p>
                    <p id="modal-created" class="font-medium"></p>
                </div>
            </div>
        </div>

        <!-- Modal Footer Actions -->
        <div class="sticky bottom-0 bg-white border-t border-gray-200 p-6 flex items-center justify-between">
            <button onclick="closeMessageModal()" class="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                Close
            </button>
            <div id="modal-actions" class="flex items-center gap-3">
                <!-- Action buttons populated dynamically -->
            </div>
        </div>
    </div>
</div>
```

Modal JavaScript functions:

```javascript
// ============================================
// MESSAGE DETAIL MODAL
// ============================================

function openMessageModal(messageId) {
    const message = appState.messages.find(m => m.id === messageId);
    if (!message) {
        showToast('Message not found', 'error');
        return;
    }

    appState.currentMessage = message;

    // Populate modal
    document.getElementById('modal-message-text').textContent = message.message;

    // User info
    document.getElementById('modal-user-info').innerHTML = `
        <p><strong>Name:</strong> ${escapeHtml(message.userName)}</p>
        <p><strong>ID:</strong> <code class="text-xs bg-gray-200 px-1 rounded">${escapeHtml(message.userId)}</code></p>
    `;

    // Event info
    document.getElementById('modal-event-info').innerHTML = `
        <p><strong>Name:</strong> ${escapeHtml(message.eventName)}</p>
        <p><strong>ID:</strong> <code class="text-xs bg-gray-200 px-1 rounded">${escapeHtml(message.eventId)}</code></p>
    `;

    // User summary (show if exists)
    const userSummarySection = document.getElementById('modal-user-summary-section');
    if (message.userSummary) {
        document.getElementById('modal-user-summary').textContent = message.userSummary;
        userSummarySection.classList.remove('hidden');
    } else {
        userSummarySection.classList.add('hidden');
    }

    // Event summary (show if exists)
    const eventSummarySection = document.getElementById('modal-event-summary-section');
    if (message.eventSummary) {
        document.getElementById('modal-event-summary').textContent = message.eventSummary;
        eventSummarySection.classList.remove('hidden');
    } else {
        eventSummarySection.classList.add('hidden');
    }

    // Reasoning (show if exists)
    const reasoningSection = document.getElementById('modal-reasoning-section');
    if (message.reasoning) {
        document.getElementById('modal-reasoning').textContent = message.reasoning;
        reasoningSection.classList.remove('hidden');
    } else {
        reasoningSection.classList.add('hidden');
    }

    // Metadata
    document.getElementById('modal-status').innerHTML = getStatusBadgeHtml(message.status);
    document.getElementById('modal-campaign').textContent = message.campaign || '-';
    document.getElementById('modal-confidence').textContent = message.confidenceScore ? `${message.confidenceScore}%` : '-';
    document.getElementById('modal-created').textContent = formatDate(message.createdAt);

    // Action buttons based on status
    const actionsHtml = getModalActionButtons(message);
    document.getElementById('modal-actions').innerHTML = actionsHtml;

    // Show modal
    document.getElementById('message-modal').classList.remove('hidden');
}

function closeMessageModal() {
    document.getElementById('message-modal').classList.add('hidden');
    appState.currentMessage = null;
}

function getModalActionButtons(message) {
    if (message.status === 'pending') {
        return `
            <button
                onclick="approveMessage('${message.id}')"
                class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                <i class="fas fa-check mr-2"></i>Approve
            </button>
            <button
                onclick="openDenyModal('${message.id}')"
                class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">
                <i class="fas fa-times mr-2"></i>Deny
            </button>
        `;
    } else if (message.status === 'approved') {
        return `
            <span class="text-green-600 font-medium">
                <i class="fas fa-check-circle mr-2"></i>Approved
            </span>
        `;
    } else if (message.status === 'denied') {
        return `
            <span class="text-red-600 font-medium">
                <i class="fas fa-times-circle mr-2"></i>Denied
            </span>
        `;
    } else if (message.status === 'sent') {
        return `
            <span class="text-blue-600 font-medium">
                <i class="fas fa-paper-plane mr-2"></i>Sent
            </span>
        `;
    }
    return '';
}

// Close modal on ESC key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeMessageModal();
        closeDenyModal();
    }
});
```

### 6. Deny Modal

Create a separate modal for denial with reason selection:

```html
<!-- Add to your HTML body -->
<div id="deny-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
    <div class="bg-white rounded-lg shadow-xl max-w-md w-full">
        <div class="p-6">
            <h2 class="text-xl font-semibold text-gray-900 mb-4">Deny Message</h2>

            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">
                        Reason for Denial <span class="text-red-500">*</span>
                    </label>
                    <select id="deny-reason" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
                        <option value="">Select a reason...</option>
                        <option value="tone">Tone/voice inappropriate</option>
                        <option value="generic">Message too generic</option>
                        <option value="incorrect">Incorrect information</option>
                        <option value="personalization">Not personalized enough</option>
                        <option value="compliance">Compliance issue</option>
                        <option value="other">Other</option>
                    </select>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">
                        Additional Comments (Optional)
                    </label>
                    <textarea
                        id="deny-comment"
                        rows="3"
                        class="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none"
                        placeholder="Provide additional feedback..."></textarea>
                </div>
            </div>

            <div class="mt-6 flex items-center justify-end gap-3">
                <button onclick="closeDenyModal()" class="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                    Cancel
                </button>
                <button onclick="submitDeny()" class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">
                    Submit Denial
                </button>
            </div>
        </div>
    </div>
</div>
```

Deny modal JavaScript:

```javascript
// ============================================
// DENY MODAL
// ============================================

let denyMessageId = null;

function openDenyModal(messageId) {
    denyMessageId = messageId;
    document.getElementById('deny-reason').value = '';
    document.getElementById('deny-comment').value = '';
    document.getElementById('deny-modal').classList.remove('hidden');
}

function closeDenyModal() {
    document.getElementById('deny-modal').classList.add('hidden');
    denyMessageId = null;
}

async function submitDeny() {
    const reason = document.getElementById('deny-reason').value;
    const comment = document.getElementById('deny-comment').value;

    if (!reason) {
        showToast('Please select a reason for denial', 'warning');
        return;
    }

    if (!denyMessageId) {
        showToast('No message selected', 'error');
        return;
    }

    await denyMessage(denyMessageId, reason, comment);
}
```

### 7. Update Initialization

Update the `init()` function to use DataTables:

```javascript
async function init() {
    console.log('Initializing Messages Airtable App...');

    // Set up event listeners
    initializeEventListeners();

    // Load messages from Airtable
    await fetchMessagesFromAirtable();

    // Initialize DataTable instead of simple render
    initializeDataTable();
    updateMessageCount();

    console.log('✓ App initialized successfully');
}
```

Update `applyFilters()` to refresh DataTable:

```javascript
function applyFilters() {
    let filtered = [...appState.messages];

    // Apply filters (same as before)
    if (appState.filters.status !== 'all') {
        filtered = filtered.filter(m => m.status === appState.filters.status);
    }

    if (appState.filters.campaign !== 'all') {
        filtered = filtered.filter(m => m.campaign === appState.filters.campaign);
    }

    if (appState.filters.search) {
        const searchLower = appState.filters.search.toLowerCase();
        filtered = filtered.filter(m =>
            m.message.toLowerCase().includes(searchLower) ||
            m.userName.toLowerCase().includes(searchLower) ||
            m.eventName.toLowerCase().includes(searchLower)
        );
    }

    appState.filteredMessages = filtered;

    // Re-initialize DataTable with filtered data
    initializeDataTable();
    updateMessageCount();
}
```

## Testing Checklist

After completing Step 2, verify the following:

### DataTables Integration
- [ ] Table displays all messages correctly
- [ ] Columns are sortable (click headers)
- [ ] Search box filters across all columns
- [ ] Pagination works (navigate pages)
- [ ] Page length selector works (10/25/50/100/All)
- [ ] Column visibility button shows/hides columns
- [ ] Export CSV downloads correct data
- [ ] Export Excel downloads correct data

### Actions & Workflow
- [ ] Eye icon opens detail modal
- [ ] Approve button (checkmark) works from table
- [ ] Deny button (X) opens deny modal
- [ ] Approve updates status in Airtable
- [ ] Deny with reason updates Airtable correctly
- [ ] Table refreshes after approve/deny
- [ ] Status badges update after action

### Detail Modal
- [ ] Modal opens with correct message data
- [ ] Message text displays fully
- [ ] User info (name, ID) displays correctly
- [ ] Event info (name, ID) displays correctly
- [ ] User summary shows (if exists)
- [ ] Event summary shows (if exists)
- [ ] Reasoning shows (if exists)
- [ ] Metadata (status, campaign, confidence, created) displays
- [ ] Action buttons match message status
- [ ] Approve/Deny from modal works
- [ ] Modal closes on Close button
- [ ] Modal closes on ESC key

### Deny Modal
- [ ] Opens when clicking Deny
- [ ] Reason dropdown is required
- [ ] Comment is optional
- [ ] Validates reason before submitting
- [ ] Updates Airtable with reason and comment
- [ ] Closes after successful denial
- [ ] Closes on Cancel button
- [ ] Closes on ESC key

### Integration
- [ ] Filters work with DataTables search
- [ ] Status filter updates table correctly
- [ ] Campaign filter updates table correctly
- [ ] Search input works alongside DataTables search
- [ ] Message count updates correctly

## Common Issues & Solutions

### Issue: DataTables buttons not showing
**Solution:** Ensure all button plugin scripts are loaded (JSZip, buttons.html5, buttons.colVis)

### Issue: Table not refreshing after update
**Solution:** Call `dataTable.destroy()` before re-initializing with new data

### Issue: Action buttons not working
**Solution:** Ensure onclick handlers are global functions (not inside other scopes)

### Issue: Modal not closing
**Solution:** Check z-index conflicts and ensure event listeners are attached

## Next Step

Once Step 2 is complete and tested, proceed to **Step 3: Card View & Polish** where you'll:
- Build Product Hunt-style card view
- Add view toggle (Table ↔ Card)
- Implement message editing
- Final design polish

---

**Checkpoint:** You should now have a fully functional table view with DataTables, approval/denial workflow, and detailed modal views. 🎉
