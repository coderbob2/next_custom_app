# Procurement Custom Tabs - Complete Documentation

## Overview

This document describes the custom enhancements added to **ALL procurement workflow doctypes** in the Next Custom App. These enhancements provide better visibility into procurement workflows, improved document tracking, and enhanced validation with detailed error messages.

**Applies to:**
- Material Request
- Purchase Requisition
- Request for Quotation
- Supplier Quotation
- Purchase Order
- Purchase Receipt
- Purchase Invoice

---

## Table of Contents

1. [Features Overview](#features-overview)
2. [Custom Tab Section](#custom-tab-section)
3. [Connected Documents Display](#connected-documents-display)
4. [Create Button Enhancement](#create-button-enhancement)
5. [Enhanced Quantity Validation](#enhanced-quantity-validation)
6. [Technical Implementation](#technical-implementation)
7. [Installation & Configuration](#installation--configuration)
8. [Usage Guide](#usage-guide)
9. [Troubleshooting](#troubleshooting)

---

## Features Overview

### 1. Custom Tab Section (All Procurement Doctypes)
- Visual section displayed below the form header on **all procurement documents**
- Shows connected procurement documents (backward and forward chains)
- Provides quick access to related documents
- Consistent interface across all procurement doctypes

### 2. Real-Time Document Tracking
- Tracks documents **immediately upon save** (not just on submit)
- Shows source documents (backward chain)
- Shows child documents (forward chain)
- Interactive buttons with document counts

### 3. Enhanced Create Button
- Appears under "Create" dropdown when document is submitted
- Shows next document type in workflow
- Opens custom dialog with document information

### 4. Detailed Quantity Validation
- Comprehensive error messages with breakdown
- Shows exactly which documents consumed quantities
- Clickable document links in error messages
- Professional styling with clear information hierarchy

---

## Custom Tab Section

### Location
The custom tab section appears at the top of **any procurement document form**, directly below the main header. This includes:
- Material Request
- Purchase Requisition
- Request for Quotation
- Supplier Quotation
- Purchase Order
- Purchase Receipt
- Purchase Invoice

### Visual Elements

```
┌─────────────────────────────────────────────────────────┐
│ Custom Tab Section - Connected Documents                │
├─────────────────────────────────────────────────────────┤
│ This section shows connected procurement documents.     │
│                                                          │
│ Source Documents:                                        │
│ [Material Request (1)]                                   │
│                                                          │
│ Child Documents:                                         │
│ [Purchase Requisition (2)] [Request for Quotation (1)]  │
│                                                          │
│ [Open Custom Tab]                                        │
└─────────────────────────────────────────────────────────┘
```

### Features
- **Background**: Light gray (#f8f9fa)
- **Border**: 1px solid border with rounded corners
- **Padding**: 20px for comfortable spacing
- **Auto-refresh**: Updates after save operations

---

## Connected Documents Display

### Document Buttons

**Source Documents (Backward Chain)**:
- Blue background (#e3f2fd)
- Shows documents that this document was created from
- Example: If PR was created from MR, MR appears here

**Child Documents (Forward Chain)**:
- Yellow background (#fff3cd)
- Shows documents created from this document
- Example: PRs created from this MR

### Button Format
```
[Document Type (count)]
```
Example: `Purchase Requisition (2)`

### Click Behavior
- **Single document**: Opens that document directly
- **Multiple documents**: Opens filtered list view showing all documents

### Real-Time Tracking
Documents appear **immediately after saving**, even in draft state. No need to submit!

---

## Create Button Enhancement

### Location
Appears in the "Create" dropdown menu (top-right of form) when:
- Document is submitted (docstatus === 1)
- There's a next step defined in the active procurement workflow

### Button Text
```
Custom: [Next Document Type]
```
Example: `Custom: Purchase Requisition`

### Click Action
Opens a custom dialog showing:
- Action being performed
- Source document name
- Target document type
- Confirmation button to create

### Console Logging
All actions are logged to browser console for debugging:
- `*** CUSTOM CREATE BUTTON CLICKED ***`
- `*** Target doctype: [name]`
- `*** Document created successfully: [name]`

---

## Enhanced Quantity Validation

### Overview
The system now provides detailed, styled error messages when quantity limits are exceeded or invalid items are detected.

### Quantity Exceeded Error

When a user tries to request more quantity than available, they see:

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Quantity Exceeds Requested Stock for Item ABC        │
├─────────────────────────────────────────────────────────┤
│ Source Quantity:      100                                │
│ Already Processed:     60                                │
│ Available:             40                                │
│ Your Request:          50                                │
├─────────────────────────────────────────────────────────┤
│ 📋 Already Processed In:                                 │
│  • 30 (PR-00001)                                         │
│  • 30 (PR-00002)                                         │
├─────────────────────────────────────────────────────────┤
│ 💡 Tip: Reduce quantity to 40 or less                   │
│ View Material Request →                                  │
└─────────────────────────────────────────────────────────┘
```

**Features**:
- Clean white background with red border
- Clear table showing all quantities
- Document breakdown with clickable links
- Helpful tip with exact available quantity
- Link to source document

### Invalid Item Error

When an item doesn't exist in the source document:

```
┌─────────────────────────────────────────────────────────┐
│ ❌ Invalid Item                                          │
├─────────────────────────────────────────────────────────┤
│ Item XYZ does not exist in the source document.         │
│                                                          │
│ Source Document: Material Request: MR-00001 →           │
│ Please select items that exist in the source document.  │
└─────────────────────────────────────────────────────────┘
```

**Features**:
- Yellow background for visibility
- Bold item name in red
- Clickable source document link
- Clear instructions

---

## Technical Implementation

### Files Modified/Created

#### 1. `next_custom_app/public/js/procurement_custom_tabs.js`
**Purpose**: Client-side JavaScript for **ALL procurement workflow doctypes**

**Applies to**: Material Request, Purchase Requisition, Request for Quotation, Supplier Quotation, Purchase Order, Purchase Receipt, Purchase Invoice

**Key Functions**:
```javascript
// Registered for all procurement doctypes
const PROCUREMENT_DOCTYPES = [
    'Material Request',
    'Purchase Requisition',
    'Request for Quotation',
    'Supplier Quotation',
    'Purchase Order',
    'Purchase Receipt',
    'Purchase Invoice'
];

// Main event handlers (applied to all doctypes)
PROCUREMENT_DOCTYPES.forEach(function(doctype) {
    frappe.ui.form.on(doctype, {
        refresh: function(frm) { ... }      // Sets up custom features
        after_save: function(frm) { ... }   // Refreshes after save
    });
});

// Custom section management
add_custom_section(frm)                  // Creates the visual section
load_linked_documents(frm, container)    // Fetches and displays links
create_linked_doc_button(link, direction) // Creates interactive buttons

// Create button functionality
add_custom_create_button(frm)            // Adds Create button
show_custom_create_dialog(frm, next_doctype) // Shows confirmation dialog

// Tab dialog
show_custom_tab_dialog(frm)              // Opens custom tab info
```

**Console Logging**:
All major operations are logged with clear markers:
- `===` for events
- `>>>` for functions
- `***` for important actions

#### 2. `next_custom_app/next_custom_app/utils/procurement_workflow.py`
**Purpose**: Backend Python logic for procurement workflow

**Key Functions Added/Modified**:

```python
# Enhanced quantity tracking
get_consumed_quantities_detailed(source_doctype, source_name, target_doctype, exclude_doc)
    """
    Returns detailed breakdown of consumed quantities with document info.
    Format: {item_code: {"total": qty, "documents": [{"name": doc, "qty": qty}]}}
    """

# Improved validation
validate_quantity_limits(doc)
    """
    Validates quantities with detailed error messages.
    Uses database queries to find ALL child documents.
    """

# Enhanced document tracking
get_linked_documents_with_counts(doctype, docname)
    """
    Searches database directly for connected documents.
    Includes draft documents, not just submitted ones.
    """
```

**Key Changes**:
1. **Database Queries**: Now queries database directly instead of relying on `procurement_links` table
2. **Immediate Tracking**: Creates backward links on save, not just on submit
3. **Detailed Breakdown**: Tracks which specific documents consumed quantities
4. **Styled Errors**: HTML-formatted error messages with tables and links

#### 3. `next_custom_app/hooks.py`
**Purpose**: Register the custom JavaScript file for all procurement doctypes

**Addition**:
```python
doctype_js = {
    "Material Request": "public/js/procurement_custom_tabs.js",
    "Purchase Requisition": "public/js/procurement_custom_tabs.js",
    "Request for Quotation": "public/js/procurement_custom_tabs.js",
    "Supplier Quotation": "public/js/procurement_custom_tabs.js",
    "Purchase Order": "public/js/procurement_custom_tabs.js",
    "Purchase Receipt": "public/js/procurement_custom_tabs.js",
    "Purchase Invoice": "public/js/procurement_custom_tabs.js"
}
```

**Note**: All procurement doctypes use the same JavaScript file, providing consistent functionality across the entire procurement workflow.

---

## Installation & Configuration

### Step 1: Ensure Custom Fields Exist

The procurement workflow custom fields must be set up:

```bash
bench --site your-site.local console
```

```python
from next_custom_app.next_custom_app.utils.procurement_workflow import setup_custom_fields
setup_custom_fields()
```

### Step 2: Clear Cache and Restart

```bash
bench clear-cache
bench build --app next_custom_app
bench restart
```

### Step 3: Verify Active Procurement Flow

Ensure you have an active Procurement Flow configured:
1. Navigate to **Procurement Flow**
2. Check that one flow is marked as "Is Active"
3. Verify all required doctypes are included in the flow steps

---

## Usage Guide

### Using Custom Features in Any Procurement Document

#### 1. Create Any Procurement Document
```
1. Go to [Any Procurement DocType] → New
   (Material Request, Purchase Requisition, etc.)
2. Add items with quantities
3. Save the document
   ↓
   Custom section appears (may show "No connected documents")
4. Submit the document
   ↓
   "Create" button appears with next doctype
```

#### 2. Viewing Connected Documents

Open any existing procurement document:
- **Custom section loads automatically**
- Shows source documents (if created from another document)
- Shows child documents (if any were created from this)
- Click any button to navigate to those documents

#### 3. Creating Child Documents

**Option A: Using Standard Workflow**
1. Open any submitted procurement document
2. Click "Create" dropdown
3. Select the next document type in workflow

**Option B: Using Custom Button**
1. Open any submitted procurement document
2. Click "Create" dropdown
3. Select "Custom: [Next DocType]"
4. Review dialog and confirm

**Works for all transitions:**
- Material Request → Purchase Requisition
- Purchase Requisition → Request for Quotation
- Request for Quotation → Supplier Quotation
- Supplier Quotation → Purchase Order
- Purchase Order → Purchase Receipt / Purchase Invoice

#### 4. Handling Quantity Validation

If you try to exceed available quantities:
```
1. System shows detailed error message
2. Review "Already Processed In" section
3. Note the available quantity
4. Adjust your request accordingly
5. Save again
```

---

## Advanced Features

### Query All Related Documents

From the custom tab section, you can quickly see all related documents:

**Scenario**: Material Request with multiple child documents
```
Material Request: MR-00001
  ↓
  ├─ Purchase Requisition: PR-00001 (qty: 30)
  ├─ Purchase Requisition: PR-00002 (qty: 30)
  └─ Purchase Requisition: PR-00003 (qty: 20)
```

The custom section shows:
```
Child Documents:
[Purchase Requisition (3)]
```

Click the button → see filtered list of all 3 PRs

### Document Chain Tracking

The system tracks complete document chains:
```
Material Request
  → Purchase Requisition
    → Request for Quotation
      → Supplier Quotation
        → Purchase Order
          → Purchase Receipt
          → Purchase Invoice
```

Each document's custom section shows its position in the chain.

---

## Troubleshooting

### Issue: Custom Section Not Appearing

**Solution 1**: Check if document is saved
- Custom section only shows for saved documents (not new/unsaved)

**Solution 2**: Clear browser cache
```bash
Ctrl + Shift + R  # Hard refresh
```

**Solution 3**: Check JavaScript console
```
F12 → Console tab
Look for: "=== Procurement Custom Tabs Script Initializing ==="
```

### Issue: Console Logs Not Showing

**Problem**: Browser console might be closed or filtered

**Solution**:
1. Press F12 to open developer tools
2. Click "Console" tab
3. Clear any filters
4. Reload the page
5. Look for logs starting with `===`, `>>>`, or `***`

### Issue: Connected Documents Not Showing

**Possible Causes**:
1. **No documents created yet**: Create a child document from the current document
2. **Not saved yet**: Save the child document (doesn't need to be submitted)
3. **Cache issue**: Refresh the page

**Debug Steps**:
```javascript
// In browser console:
console.log(cur_frm.doc.procurement_links);  // Check links table
```

### Issue: Quantity Validation Not Working

**Check**:
1. Is there an active Procurement Flow?
2. Is the source document properly set?
3. Check console for validation errors

**Debug**:
```python
# In bench console:
from next_custom_app.next_custom_app.utils.procurement_workflow import get_active_flow
flow = get_active_flow()
print(flow)  # Should show active flow
```

### Issue: Create Button Not Showing

**Requirements**:
- Document must be submitted (docstatus === 1)
- There must be a next step in the workflow
- Procurement flow must be active

**Check Console**:
```
Look for: "=== Document is SUBMITTED, adding custom create button ==="
or: "*** No next step found in workflow"
```

---

## Performance Considerations

### Database Queries
The system now queries the database directly for linked documents. This is efficient because:
- Uses indexed fields (`procurement_source_doctype`, `procurement_source_name`)
- Filters for non-cancelled documents only
- Returns only required fields

### Caching
- Document links are fetched on page load
- Refreshed automatically after save
- No continuous polling

---

## Security & Permissions

### Document Access
- Users can only see documents they have permission to view
- Document links respect standard ERPNext permissions
- No elevated permissions required

### Validation
- All quantity validations run server-side
- Cannot be bypassed from client side
- Error messages don't expose sensitive data

---

## Future Enhancements

Potential improvements that could be added:

1. **Batch Operations**: Create multiple child documents at once
2. **Quantity Warnings**: Show warnings before hard limits
3. **Visual Charts**: Graphical view of consumed quantities
4. **Export**: Export document chain to PDF/Excel
5. **Notifications**: Alert when quantities are getting low
6. **History**: Track all changes to linked documents

---

## API Reference

### Client-Side Functions

```javascript
// Load linked documents
load_linked_documents(frm, container)

// Create document button
create_linked_doc_button(link, direction)
// Parameters:
//   link: {doctype: "Purchase Requisition", count: 2, documents: ["PR-001", "PR-002"]}
//   direction: "backward" or "forward"

// Add custom section
add_custom_section(frm)

// Show create dialog
show_custom_create_dialog(frm, next_doctype)
```

### Server-Side Functions

```python
# Get detailed consumed quantities
get_consumed_quantities_detailed(source_doctype, source_name, target_doctype, exclude_doc)
# Returns: {item_code: {"total": qty, "documents": [...]}}

# Get linked documents with counts
get_linked_documents_with_counts(doctype, docname)
# Returns: {"backward": [...], "forward": [...]}

# Validate quantity limits (called automatically)
validate_quantity_limits(doc)
```

---

## Version History

### Version 1.1.0 (2025-11-27)
- **Extended to all procurement doctypes**: Material Request, Purchase Requisition, Request for Quotation, Supplier Quotation, Purchase Order, Purchase Receipt, Purchase Invoice
- Unified JavaScript file for consistent behavior across all doctypes
- Updated documentation to reflect universal applicability

### Version 1.0.0 (2025-11-27)
- Initial implementation of custom tab section for Material Request
- Added connected documents display
- Implemented enhanced quantity validation
- Added real-time document tracking
- Created detailed error messages with styling

---

## Support & Contact

For issues, questions, or feature requests:
- **Email**: info@nextcoretechnologies.com
- **Documentation**: See [PROCUREMENT_WORKFLOW_GUIDE.md](PROCUREMENT_WORKFLOW_GUIDE.md)

---

## License

MIT License - See [license.txt](license.txt)

---

**Developed by**: Nextcore Technologies  
**Last Updated**: November 27, 2025  
**Compatible with**: ERPNext 15.x