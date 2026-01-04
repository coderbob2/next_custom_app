# Custom Tab Implementation Summary - Document Flow Visualization

## Overview
This document describes the enhanced custom tab implementation for procurement workflow documents. The implementation provides a visual tree-based document flow diagram that shows the complete procurement chain from root to all branches.

---

## Key Changes Made

### 1. **Compact Custom Tab Section**
**Location**: Top of all procurement document forms

**Changes**:
- ✅ Removed verbose title and description to save vertical space
- ✅ Changed to horizontal layout for connected document buttons
- ✅ Buttons now display inline with proper spacing
- ✅ "Document Flow" button positioned at bottom-right
- ✅ "View Analysis" button added for source documents only (documents without parent)

**Visual Structure**:
```
┌──────────────────────────────────────────────────────────┐
│ [MR (1)] [PR (2)] [RFQ (1)]        [View Analysis] [Document Flow] │
└──────────────────────────────────────────────────────────┘
```

---

### 2. **Document Flow Dialog**

#### **Button Name Changed**
- **Old**: "Open Custom Tab"
- **New**: "Document Flow"

#### **Complete Tree Visualization**
The document flow now shows:

1. **Complete Document Tree from Root**
   - Starts from the topmost source document (e.g., Material Request)
   - Shows all child documents recursively
   - Displays all branches, not just direct children

2. **Current Path Highlighting**
   - Documents in the current document's path are shown in their doctype colors
   - Current document is highlighted with blue color
   - Unrelated branches are grayed out

3. **Horizontal Layout for Same Doctype**
   - Multiple documents of the same type (e.g., 2 PRs from 1 MR) are shown side-by-side
   - Main path document shown first, branches shown after
   - Connected with horizontal lines

4. **Visual Connectors**
   - Vertical lines connect parent to children
   - Horizontal line spans across sibling documents
   - Arrow (▼) shows flow direction between levels

#### **Example Flow**:

**Scenario**: Viewing RFQ-00001, showing complete tree from root with current path highlighted

```
┌────────────────────────────────────────────────────────────────┐
│                    Material Request: MR-00001                   │ ← Root (Purple - in path)
│                         [Submitted]                             │
└────────────────────────────────────────────────────────────────┘
                              |
                              ▼
        ┌─────────────────────┴─────────────────────┐
        |                                           |
┌───────────────────┐                     ┌───────────────────┐
│  PR-00001         │  ← Main Path        │  PR-00002         │  ← Branch
│  [Submitted]      │  (Blue - in path)   │  [Submitted]      │  (Gray - not in path)
└───────────────────┘                     └───────────────────┘
        |
        ▼
┌───────────────────┐
│  RFQ-00001        │  ← Current Document
│  [Draft]          │  (Blue - highlighted)
└───────────────────┘
```

**Key Points**:
- Each document is **centered relative to its direct parent only**
- PR-00001 and PR-00002 are both children of MR-00001 (siblings shown horizontally)
- RFQ-00001 is **only** a child of PR-00001 (aligned directly under PR-00001)
- PR-00002 branch is grayed out (not in current document's path)
- Current document (RFQ-00001) is highlighted in blue
- Vertical arrows show parent → child relationships

**Color Coding**:
- **Purple**: Material Request
- **Blue**: Purchase Requisition (and current document)
- **Orange**: Request for Quotation
- **Teal**: Supplier Quotation
- **Dark Gray**: Purchase Order
- **Green**: Purchase Receipt
- **Red**: Purchase Invoice
- **Gray**: Unrelated branches (not in current path)

---

### 3. **View Analysis Dialog**

**Availability**: Only for source documents (documents without `procurement_source_name`)

**Features**:
1. **Summary Metrics** (4 cards):
   - Total Child Documents
   - Total Items
   - Total Quantity
   - Completion Rate (percentage of consumed quantity)

2. **Items Breakdown Table**:
   - Item code
   - Source quantity
   - Consumed quantity
   - Available quantity (color-coded: green if available, red if exhausted)
   - Visual progress bar showing percentage used
   - Color indicates status: green (< 80%), yellow (80-99%), red (100%+)

---

## Technical Implementation

### **Frontend Files**

#### 1. [`procurement_custom_tabs.js`](public/js/procurement_custom_tabs.js)

**Key Functions**:

```javascript
// Compact section with horizontal buttons
add_custom_section(frm)
  ├─ Creates compact layout
  ├─ Adds connected document buttons horizontally
  ├─ Positions "Document Flow" button at bottom-right
  └─ Adds "View Analysis" button for source docs

// Document flow visualization
show_custom_tab_dialog(frm)
  └─ Opens dialog and loads flow data

render_document_flow(flow_data, container)
  ├─ Maps doctypes to unique colors
  ├─ Renders nodes in tree structure
  ├─ Shows branches horizontally
  ├─ Connects nodes with visual lines
  └─ Applies grayed-out style to unrelated branches

// Analysis dialog
show_analysis_dialog(frm)
  └─ Opens analysis dialog

render_analysis(analysis_data, container)
  ├─ Renders summary cards
  └─ Renders item breakdown table with progress bars
```

**Doctype Color Map**:
```javascript
const doctypeColors = {
    'Material Request': { main: '#8e44ad', light: '#e8d5f0', border: '#8e44ad' },
    'Purchase Requisition': { main: '#3498db', light: '#d6eaf8', border: '#3498db' },
    'Request for Quotation': { main: '#e67e22', light: '#fdebd0', border: '#e67e22' },
    'Supplier Quotation': { main: '#16a085', light: '#d1f2eb', border: '#16a085' },
    'Purchase Order': { main: '#2c3e50', light: '#d5dbdb', border: '#2c3e50' },
    'Purchase Receipt': { main: '#27ae60', light: '#d5f4e6', border: '#27ae60' },
    'Purchase Invoice': { main: '#c0392b', light: '#f5d6d3', border: '#c0392b' }
};
```

### **Backend Files**

#### 2. [`procurement_workflow.py`](next_custom_app/utils/procurement_workflow.py)

**New Functions**:

```python
@frappe.whitelist()
def get_document_flow_with_statuses(doctype, docname):
    """
    Get complete document tree from root with current path highlighted.
    Returns hierarchical structure with all documents and branches.
    """
    # 1. Find root document by traversing backward
    # 2. Get path from root to current document
    # 3. Build complete tree marking current path
    # 4. Gray out unrelated branches

def find_root_document(doctype, docname):
    """Find the topmost document by traversing procurement_source fields."""
    # Traverse backward until no parent found
    # Returns (root_doctype, root_docname)

def get_path_to_document(target_doctype, target_docname):
    """Get set of all documents in path from root to target."""
    # Returns: set(['Material Request::MR-001', 'Purchase Requisition::PR-001', ...])

def build_complete_tree(nodes_list, doctype, docname, current_path, processed, target_dt, target_name):
    """
    Recursively build complete document tree.
    Marks documents as:
    - is_current: The document being viewed
    - is_in_path: Part of the path to current document
    - is_grayed: Unrelated branch
    """
    # 1. Get all forward documents
    # 2. Identify which is in current path
    # 3. Add main node with branches
    # 4. Recursively process children

@frappe.whitelist()
def get_procurement_analysis(doctype, docname):
    """
    Get procurement analysis for source document.
    Returns:
    - Summary metrics
    - Item-wise breakdown
    """
```

---

## Usage Guide

### **Viewing Document Flow**

1. Open any procurement document (MR, PR, RFQ, SQ, PO, GRN, PI)
2. See compact section at top with connected documents
3. Click "Document Flow" button (bottom-right)
4. View complete tree:
   - Your document's path is highlighted in color
   - Current document is blue
   - Unrelated branches are grayed out
   - Click any node to navigate to that document

### **Viewing Analysis** (Source Documents Only)

1. Open a source document (e.g., Material Request without parent)
2. Document must be submitted (docstatus = 1)
3. Click "View Analysis" button
4. Review:
   - Total statistics
   - Item-wise consumption
   - Available quantities
   - Visual progress bars

---

## Benefits

### **For Users**:
1. ✅ **Complete Visibility**: See entire procurement chain, not just direct links
2. ✅ **Path Clarity**: Instantly understand document relationships
3. ✅ **Branch Awareness**: See all parallel paths (multiple PRs from one MR)
4. ✅ **Space Efficient**: Compact UI doesn't overwhelm the form
5. ✅ **Visual Analysis**: Understand consumption patterns at a glance

### **For Developers**:
1. ✅ **Recursive Tree Building**: Handles complex document hierarchies
2. ✅ **Performance**: Prevents infinite loops with processed document tracking
3. ✅ **Extensible**: Easy to add new doctypes to color map
4. ✅ **Error Handling**: Comprehensive logging and graceful fallbacks

---

## Technical Details

### **Algorithm for Tree Building**

```
1. START with current document (doctype, docname)
2. FIND ROOT:
   - Traverse backward using procurement_source fields
   - Stop when no parent found
   - Result: (root_doctype, root_docname)

3. GET CURRENT PATH:
   - Traverse backward from current document
   - Build set of all documents in path
   - Result: Set of "DocType::DocName" strings

4. BUILD TREE:
   - Start from root
   - For each level:
     a. Get all forward documents
     b. Identify which is in current path (main node)
     c. Others become branches
     d. Mark as grayed if not in path
     e. Recursively process main node's children
   - Result: Complete tree with path highlighting
```

### **Data Structure**

```javascript
{
    "nodes": [
        {
            "doctype": "Material Request",
            "name": "MR-00001",
            "is_current": false,
            "is_in_path": true,
            "is_grayed": false,
            "is_submitted": true,
            "status": "Submitted",
            "workflow_state": null,
            "branches": []  // Other MRs (if any)
        },
        {
            "doctype": "Purchase Requisition",
            "name": "PR-00001",
            "is_current": true,
            "is_in_path": true,
            "is_grayed": false,
            "is_submitted": true,
            "status": "Submitted",
            "workflow_state": null,
            "branches": [
                {
                    "doctype": "Purchase Requisition",
                    "name": "PR-00002",
                    "is_current": false,
                    "is_in_path": false,
                    "is_grayed": true,  // Not in current doc's path
                    "is_submitted": true
                }
            ]
        }
    ]
}
```

---

## Testing Checklist

- [x] Compact section appears on all procurement doctypes
- [x] Connected document buttons display horizontally
- [x] "Document Flow" button shows at bottom-right
- [x] "View Analysis" button appears only for source documents
- [x] Document flow shows complete tree from root
- [x] Current path is highlighted properly
- [x] Unrelated branches are grayed out
- [x] Clicking nodes navigates correctly
- [x] Analysis shows correct metrics and breakdowns
- [x] Color coding is consistent across all doctypes
- [x] Tree handles multiple branches correctly
- [x] Recursive traversal works for deep hierarchies

---

## Files Modified

1. **[`public/js/procurement_custom_tabs.js`](public/js/procurement_custom_tabs.js)** (619 lines)
   - Compact UI layout
   - Tree visualization rendering
   - Analysis rendering
   - Color management

2. **[`next_custom_app/utils/procurement_workflow.py`](next_custom_app/utils/procurement_workflow.py)** (955+ lines)
   - Tree building algorithms
   - Root finding logic
   - Path tracking
   - Analysis calculations

---

## Version History

**Version 2.0.0** (2025-11-27)
- Complete tree visualization from root
- Current path highlighting
- Grayed-out unrelated branches
- Compact horizontal layout
- Doctype-specific color coding
- Recursive tree building
- Analysis dashboard for source documents

**Version 1.0.0** (2025-11-27)
- Initial implementation
- Basic linked documents display
- Custom create button
- Quantity validation

---

## Support

For issues or questions:
- **Email**: info@nextcoretechnologies.com
- **Documentation**: See related files in `/next_custom_app/` directory

---

**Developed by**: Nextcore Technologies  
**Last Updated**: November 27, 2025  
**Compatible with**: ERPNext 15.x