# Procurement Document Creation Fix

## Problem Analysis

When creating a Custom Purchase Requisition from Material Request, two issues occur:

### Issue 1: Items Not Being Copied
**Problem:** The [`make_procurement_document()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:1213) function in procurement_workflow.py tries to use Frappe's `get_mapped_doc()` but the mapping configuration is incorrect for custom doctypes.

**Root Cause:**
1. Line 1294: Uses `f"{target_doctype} Item"` as the child table doctype name
2. For Purchase Requisition, this becomes "Purchase Requisition Item" 
3. The field mapping expects this exact doctype name to exist
4. The items are mapped but the configuration might not handle all fields properly

### Issue 2: "Source Document Required" Error
**Problem:** The error "This document requires a source document from the previous step" occurs when trying to manually create a Purchase Requisition.

**Root Cause:**
1. [`validate_step_order()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:198) at line 214-219 checks `requires_source`
2. If `requires_source` is true, it validates that `procurement_source_doctype` and `procurement_source_name` are set
3. When creating manually (not from source), these fields are empty, causing the error

## Current Implementation Flow

### Document Creation Flow:
```
User clicks "Create" button → show_custom_create_dialog() → 
make_procurement_document() → get_mapped_doc() → 
Returns mapped document → frappe.set_route() opens form
```

### Validation Flow:
```
User saves/submits → validate event fires → 
validate_procurement_document() → validate_step_order() → 
Checks requires_source → Throws error if source missing
```

## Solutions

### Solution 1: Fix Item Mapping in make_procurement_document()

The current implementation at lines 1266-1303 has the correct structure but may need refinement:

**Current Code Issues:**
- Line 1294: `f"{target_doctype} Item"` assumes standard naming
- The field mapping might not copy all necessary fields
- Need to ensure ALL items from source are copied

**Recommended Fix:**
1. Ensure the child table doctype name is correct
2. Add explicit field mappings for all item fields
3. Remove the validation filter that might skip items
4. Ensure quantity and other fields are properly mapped

### Solution 2: Handle Manual Document Creation

Two approaches:

#### Approach A: Make Source Optional (Recommended)
Modify the validation to allow manual creation:
```python
def validate_step_order(doc):
    # ...existing code...
    
    # Check if source is required
    if current_step.requires_source:
        # Allow manual creation if no items reference a source
        has_manual_items = any(not getattr(item, 'procurement_source', None) 
                              for item in doc.get(get_items_field_name(doc.doctype)) or [])
        
        if not doc.get("procurement_source_doctype") or not doc.get("procurement_source_name"):
            if not has_manual_items:
                frappe.throw(
                    _("This document requires a source document from the previous step. "
                      "Please create it from the appropriate source document.")
                )
```

#### Approach B: Use Procurement Flow Configuration
Add a checkbox in Procurement Flow Steps to "Allow Manual Creation" and check this setting during validation.

### Solution 3: Enhanced Item Mapping

Add a dedicated function to properly copy items:

```python
def copy_items_from_source(source_doc, target_doc, source_items_field, target_items_field):
    """
    Copy ALL items from source document to target document.
    Ensures no items are missed during document creation.
    """
    source_items = source_doc.get(source_items_field) or []
    
    for source_item in source_items:
        target_item = {
            "item_code": source_item.item_code,
            "item_name": getattr(source_item, 'item_name', None),
            "qty": source_item.qty,
            "uom": source_item.uom,
            "rate": getattr(source_item, 'rate', 0) or 0,
            "description": getattr(source_item, 'description', None) or source_item.item_code,
        }
        
        # Copy optional fields if they exist
        optional_fields = ['schedule_date', 'warehouse', 'project', 'cost_center', 
                          'conversion_factor', 'stock_uom', 'stock_qty']
        for field in optional_fields:
            if hasattr(source_item, field):
                target_item[field] = getattr(source_item, field)
        
        target_doc.append(target_items_field, target_item)
```

## Implementation Steps

### Step 1: Update make_procurement_document() Function

**File:** [`next_custom_app/next_custom_app/utils/procurement_workflow.py`](next_custom_app/next_custom_app/utils/procurement_workflow.py:1213)

**Changes Required:**
1. Remove the validation filter at line 1290 that checks docstatus
2. Simplify the field mapping to ensure all items are copied
3. Add explicit item field mapping
4. Call a helper function to copy items after mapping

### Step 2: Update validate_step_order() Function

**File:** [`next_custom_app/next_custom_app/utils/procurement_workflow.py`](next_custom_app/next_custom_app/utils/procurement_workflow.py:198)

**Changes Required:**
1. Add check to allow manual creation when appropriate
2. Only enforce source requirement when creating from workflow
3. Add a way to distinguish between manual and workflow creation

### Step 3: Add Item Copy Helper Function

**File:** [`next_custom_app/next_custom_app/utils/procurement_workflow.py`](next_custom_app/next_custom_app/utils/procurement_workflow.py)

**Add New Function:**
- Insert after `make_procurement_document()` function
- Ensures all items are copied with all their properties

### Step 4: Update Client-Side Script

**File:** [`next_custom_app/public/js/procurement_custom_tabs.js`](next_custom_app/public/js/procurement_custom_tabs.js:140)

**Changes Required:**
1. Ensure the created document has items before redirecting
2. Add validation to check if items were copied
3. Show a warning if no items in the created document

## Testing Checklist

After implementing fixes:

- [ ] Create Purchase Requisition from Material Request
  - [ ] Verify ALL items are copied
  - [ ] Verify quantities match
  - [ ] Verify item details (UOM, warehouse, etc.) are copied
  
- [ ] Create Purchase Requisition manually
  - [ ] Should work without source document error
  - [ ] Can add items manually
  - [ ] Can save and submit
  
- [ ] Create Request for Quotation from Purchase Requisition
  - [ ] Verify items are copied correctly
  - [ ] Verify source tracking works
  
- [ ] Quantity validation
  - [ ] Cannot exceed source quantities
  - [ ] Error message shows correct breakdown
  
- [ ] Document chain
  - [ ] Source reference is set correctly
  - [ ] Backward links work
  - [ ] Forward links work

## Code Changes Summary

### File 1: procurement_workflow.py

#### Change 1: Update make_procurement_document()
- **Location:** Lines 1213-1333
- **Purpose:** Fix item mapping to copy ALL items
- **Priority:** HIGH

#### Change 2: Update validate_step_order()
- **Location:** Lines 198-231
- **Purpose:** Allow manual document creation
- **Priority:** HIGH

#### Change 3: Add copy_items_from_source()
- **Location:** After make_procurement_document()
- **Purpose:** Ensure complete item copying
- **Priority:** MEDIUM

### File 2: procurement_custom_tabs.js

#### Change 1: Update show_custom_create_dialog()
- **Location:** Lines 140-187
- **Purpose:** Add validation for created document
- **Priority:** LOW

## Configuration Requirements

### Procurement Flow Setup

Ensure Procurement Flow is configured correctly:

1. Go to: **Procurement Workflow > Procurement Flow**
2. Check active flow settings
3. Verify steps are in correct order:
   - Material Request (Step 1)
   - Purchase Requisition (Step 2, requires_source = checked)
   - Request for Quotation (Step 3, requires_source = checked)
   - etc.

### Custom Fields Setup

Ensure custom fields exist:

Run this command after app installation:
```bash
bench --site [your-site] execute next_custom_app.next_custom_app.utils.procurement_workflow.setup_custom_fields
```

This creates:
- `procurement_source_doctype`
- `procurement_source_name`
- `procurement_links` (child table)

## Expected Behavior After Fix

### Creating from Source Document:
1. User opens submitted Material Request
2. Clicks "Create" → "Custom: Purchase Requisition"
3. System creates Purchase Requisition with:
   - ALL items copied from Material Request
   - Source fields auto-populated
   - Quantities preserved
   - Item details preserved
4. User can modify quantities (within limits)
5. Can save and submit

### Creating Manually:
1. User creates new Purchase Requisition directly
2. Can add items manually
3. No source document error
4. Can save and submit
5. Validation only checks:
   - Required fields
   - Item details
   - Business logic
   - NOT source document requirement

### Validation Rules:
1. When created from source:
   - Items must exist in source
   - Quantities cannot exceed available
   - Source tracking enabled
   
2. When created manually:
   - No source validation
   - Normal business rules apply
   - Can be used as source for next step

## Notes

- The `requires_source` setting in Procurement Flow should be advisory, not mandatory
- Manual creation should always be possible for flexibility
- Validation should focus on data integrity, not workflow enforcement
- Users should be able to bypass workflow when needed (with proper permissions)
