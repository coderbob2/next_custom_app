# RFQ Pivot View - Supplier Price Comparison

## Overview

The **RFQ Pivot View** feature provides an intuitive interface for comparing and entering supplier prices in a matrix format. This allows users to quickly enter prices from multiple suppliers for all items in a Request for Quotation (RFQ), then automatically create Supplier Quotations for suppliers with entered prices.

**Version**: 1.0  
**Date**: November 28, 2025  
**Author**: Nextcore Technologies

---

## Table of Contents

1. [Purpose](#purpose)
2. [Features](#features)
3. [How It Works](#how-it-works)
4. [Usage Guide](#usage-guide)
5. [User Interface](#user-interface)
6. [Technical Implementation](#technical-implementation)
7. [API Reference](#api-reference)
8. [Installation](#installation)
9. [Examples](#examples)
10. [Troubleshooting](#troubleshooting)

---

## Purpose

### Business Need

In procurement processes, users often need to:
- Compare prices from multiple suppliers for the same items
- Enter quotes received from different suppliers
- Create multiple Supplier Quotations efficiently
- Avoid creating individual quotations one by one

### Solution

The RFQ Pivot View provides a spreadsheet-like interface where:
- Items are listed in rows
- Suppliers are listed in columns
- Users can enter prices for each item-supplier combination
- System automatically creates Supplier Quotations based on entered data

### Benefits

✅ **Time Saving**: Enter all supplier prices in one screen  
✅ **Easy Comparison**: See all prices side-by-side  
✅ **Bulk Creation**: Create multiple quotations at once  
✅ **Selective Processing**: Only create quotations for suppliers with prices  
✅ **Error Prevention**: Visual matrix prevents data entry mistakes  
✅ **Workflow Integration**: Seamlessly integrates with procurement workflow

---

## Features

### 1. Pivot Table Interface

- **Matrix Layout**: Items in rows, suppliers in columns
- **Input Fields**: Numeric input fields for each item-supplier combination
- **Visual Design**: Color-coded headers and responsive layout
- **Keyboard Navigation**: Tab/Enter to move between cells
- **Auto-formatting**: Prices automatically formatted to 2 decimal places

### 2. Smart Quotation Creation

- **Selective Processing**: Only creates quotations for suppliers with prices
- **Item Filtering**: Excludes items without prices from quotations
- **Automatic Linking**: Links quotations back to RFQ
- **Batch Processing**: Creates all quotations in one operation
- **Progress Indicator**: Shows creation progress

### 3. Confirmation Dialog

- **Summary Statistics**: Shows count of quotations to create
- **Supplier Breakdown**: Lists which suppliers will get quotations
- **Skip List**: Shows suppliers being skipped (no prices)
- **Item Counts**: Displays number of items per supplier
- **Cancellation Option**: User can cancel before creation

### 4. Bulk Submit

- **Optional Submission**: Submit all created quotations at once
- **Error Handling**: Continues even if some submissions fail
- **Success Tracking**: Reports which quotations were submitted
- **Error Reporting**: Shows detailed error messages

### 5. Result Dialog

- **Success Summary**: Lists all created quotations with links
- **Skipped Suppliers**: Shows suppliers that were skipped
- **Error Details**: Displays any errors that occurred
- **Next Steps**: Provides guidance on what to do next

---

## How It Works

### Workflow

```
1. User opens submitted RFQ
   ↓
2. Clicks "Supplier Price Comparison" button (under Create menu)
   ↓
3. Pivot view dialog opens with items × suppliers matrix
   ↓
4. User enters prices in the matrix
   ↓
5. User clicks "Create Supplier Quotations"
   ↓
6. Confirmation dialog shows summary
   ↓
7. User confirms creation
   ↓
8. System creates quotations for suppliers with prices
   ↓
9. Result dialog shows created quotations with links
   ↓
10. Optional: User can submit all quotations at once
```

### Data Flow

```
RFQ (name, items, suppliers)
   ↓
get_rfq_pivot_data() API
   ↓
Returns: {items: [...], suppliers: [...], rfq_name: "..."}
   ↓
User enters prices in matrix
   ↓
Collected as: {supplier: {item_code: {rate: X, qty: Y}}}
   ↓
create_supplier_quotations_from_pivot() API
   ↓
For each supplier with prices:
  - Filter items with rate > 0
  - Create Supplier Quotation
  - Link to RFQ
  - Insert document
   ↓
Returns: {created: [...], skipped: [...], errors: [...]}
   ↓
Display results to user
```

---

## Usage Guide

### Prerequisites

1. **RFQ Must Be Submitted**: Button only appears for submitted RFQs
2. **Items Required**: RFQ must have at least one item
3. **Suppliers Required**: RFQ must have at least one supplier
4. **Permissions**: User must have permission to create Supplier Quotations

### Step-by-Step Guide

#### Step 1: Open Submitted RFQ

Navigate to a submitted Request for Quotation document.

#### Step 2: Click Supplier Price Comparison Button

1. Click the **Create** dropdown button (top-right)
2. Select **Supplier Price Comparison**
3. Wait for pivot view to load

#### Step 3: Enter Prices

1. The matrix shows:
   - Items down the left side
   - Suppliers across the top
   - Input fields for each combination
2. Click on an input field
3. Enter the price offered by that supplier for that item
4. Use Tab or Enter to move to the next field
5. Leave blank if supplier didn't quote for that item

**Tips**:
- Fields highlight when focused
- Prices auto-format to 2 decimal places on blur
- You can use keyboard for fast data entry
- Only enter prices for items the supplier quoted

#### Step 4: Review and Confirm

1. Click **Create Supplier Quotations** button
2. Review the confirmation dialog:
   - Number of quotations to create
   - Number of suppliers to skip
   - Breakdown by supplier
3. Click **Yes** to proceed or **No** to cancel

#### Step 5: Review Results

The result dialog shows:
- ✅ Successfully created quotations (with clickable links)
- ℹ️ Skipped suppliers (no prices entered)
- ❌ Any errors that occurred

#### Step 6: Submit Quotations (Optional)

1. Click **Submit All Quotations** button in result dialog
2. Confirm submission
3. All created quotations will be submitted

**Or manually**:
- Click individual quotation links to review
- Submit each quotation individually

---

## User Interface

### Pivot Table Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Instructions: Enter prices for each item from each supplier... │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┬─────┬─────┬───────────┬───────────┬───────────┐
│ Item Code    │ Qty │ UOM │ Supplier1 │ Supplier2 │ Supplier3 │
│              │     │     │ (Price)   │ (Price)   │ (Price)   │
├──────────────┼─────┼─────┼───────────┼───────────┼───────────┤
│ ITEM-001     │ 100 │ Nos │ [100.00 ] │ [  95.00] │ [105.00 ] │
│ Widget A     │     │     │           │           │           │
├──────────────┼─────┼─────┼───────────┼───────────┼───────────┤
│ ITEM-002     │  50 │ Pcs │ [ 250.00] │ [       ] │ [240.00 ] │
│ Component B  │     │     │           │           │           │
└──────────────┴─────┴─────┴───────────┴───────────┴───────────┘

Note: Quotations created only for suppliers with at least one price.

[Close] [Create Supplier Quotations]
```

### Confirmation Dialog

```
┌─────────────────────────────────────────────────────────────────┐
│ Confirm Supplier Quotation Creation                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────────────┐  ┌──────────────────────────────┐  │
│  │        2              │  │           1                  │  │
│  │  Quotations to Create │  │  Suppliers to Skip           │  │
│  └───────────────────────┘  └──────────────────────────────┘  │
│                                                                  │
│  Quotations to Create:                                          │
│  • Supplier A - 2 items with prices                             │
│  • Supplier B - 1 item with prices                              │
│                                                                  │
│  Suppliers to Skip:                                              │
│  • Supplier C                                                    │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                              [No]  [Yes]        │
└─────────────────────────────────────────────────────────────────┘
```

### Result Dialog

```
┌─────────────────────────────────────────────────────────────────┐
│ Supplier Quotations Created                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✅ Successfully Created 2 Supplier Quotations                  │
│  • SQ-00001 (link)                                              │
│  • SQ-00002 (link)                                              │
│                                                                  │
│  ℹ️ Skipped 1 Supplier (No Prices Entered)                      │
│  • Supplier C                                                    │
│                                                                  │
│  💡 Next Step: Review quotations and submit individually,       │
│     or click below to submit all at once.                       │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                       [Submit All Quotations]   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technical Implementation

### Files Created/Modified

#### 1. Backend (Python)

**File**: [`next_custom_app/utils/procurement_workflow.py`](next_custom_app/next_custom_app/utils/procurement_workflow.py)

**New Functions**:

1. **`get_rfq_pivot_data(rfq_name)`**
   - Fetches RFQ items and suppliers
   - Returns formatted data for pivot view
   - Line: ~1229

2. **`create_supplier_quotations_from_pivot(rfq_name, pivot_data)`**
   - Creates Supplier Quotations from pivot data
   - Filters items with prices
   - Links to RFQ
   - Returns creation results
   - Line: ~1274

3. **`submit_supplier_quotations(sq_names)`**
   - Submits multiple quotations
   - Handles errors gracefully
   - Returns submission results
   - Line: ~1380

#### 2. Frontend (JavaScript)

**File**: [`next_custom_app/public/js/rfq_pivot_view.js`](next_custom_app/public/js/rfq_pivot_view.js) (598 lines)

**Key Functions**:

1. **`show_rfq_pivot_view(frm)`** - Opens pivot view dialog
2. **`render_pivot_dialog(frm, pivot_data)`** - Renders dialog
3. **`build_pivot_table_html(items, suppliers)`** - Builds matrix HTML
4. **`setup_pivot_table_events(dialog, items, suppliers)`** - Keyboard navigation
5. **`create_supplier_quotations_from_pivot(frm, dialog, pivot_data)`** - Initiates creation
6. **`show_confirmation_dialog(...)`** - Shows confirmation
7. **`create_quotations_with_progress(...)`** - Creates with progress
8. **`show_creation_result(frm, result)`** - Shows results
9. **`submit_all_quotations(frm, sq_names)`** - Submits all

#### 3. Hooks Registration

**File**: [`next_custom_app/hooks.py`](next_custom_app/hooks.py:74-83)

```python
doctype_js = {
    "Request for Quotation": [
        "public/js/procurement_custom_tabs.js",
        "public/js/rfq_pivot_view.js"  # Added
    ],
    ...
}
```

---

## API Reference

### Python API

#### 1. `get_rfq_pivot_data(rfq_name)`

**Description**: Get RFQ data formatted for pivot view

**Parameters**:
- `rfq_name` (str): RFQ document name

**Returns**:
```python
{
    "items": [
        {
            "item_code": "ITEM-001",
            "item_name": "Widget A",
            "qty": 100,
            "uom": "Nos",
            "description": "..."
        }
    ],
    "suppliers": [
        {
            "supplier": "SUP-001",
            "supplier_name": "Supplier A"
        }
    ],
    "rfq_name": "RFQ-00001",
    "company": "Company Name",
    "transaction_date": "2025-11-28",
    "schedule_date": "2025-12-05"
}
```

**Usage**:
```python
import frappe

frappe.call({
    'method': 'next_custom_app.next_custom_app.utils.procurement_workflow.get_rfq_pivot_data',
    'args': {'rfq_name': 'RFQ-00001'}
})
```

#### 2. `create_supplier_quotations_from_pivot(rfq_name, pivot_data)`

**Description**: Create Supplier Quotations from pivot table data

**Parameters**:
- `rfq_name` (str): RFQ document name
- `pivot_data` (dict/str): Pivot data as dict or JSON string

**Pivot Data Format**:
```python
{
    "SUP-001": {
        "ITEM-001": {"rate": 100.00, "qty": 10},
        "ITEM-002": {"rate": 200.00, "qty": 5}
    },
    "SUP-002": {
        "ITEM-001": {"rate": 95.00, "qty": 10}
    }
}
```

**Returns**:
```python
{
    "created": ["SQ-00001", "SQ-00002"],
    "skipped": ["SUP-003"],
    "errors": []
}
```

#### 3. `submit_supplier_quotations(sq_names)`

**Description**: Submit multiple Supplier Quotations

**Parameters**:
- `sq_names` (list/str): List of SQ names or JSON string

**Returns**:
```python
{
    "submitted": ["SQ-00001", "SQ-00002"],
    "errors": ["Error submitting SQ-00003: ..."]
}
```

### JavaScript API

All functions are in [`rfq_pivot_view.js`](next_custom_app/public/js/rfq_pivot_view.js)

---

## Installation

### Step 1: Install/Update App

```bash
# Update app
cd ~/frappe-bench/apps/next_custom_app
git pull

# Or install fresh
bench get-app next_custom_app
bench --site your-site.local install-app next_custom_app
```

### Step 2: Build Assets

```bash
bench build --app next_custom_app --force
```

### Step 3: Clear Cache

```bash
bench --site your-site.local clear-cache
```

### Step 4: Restart

```bash
bench restart
```

### Step 5: Verify Installation

1. Open any submitted RFQ
2. Check for **Supplier Price Comparison** button in Create menu
3. If not visible, check browser console for errors

---

## Examples

### Example 1: Simple RFQ with 2 Suppliers

**Scenario**:
- RFQ-001 has 3 items: ITEM-A, ITEM-B, ITEM-C
- 2 suppliers: Supplier X, Supplier Y
- Both suppliers quote all items

**Steps**:
1. Open RFQ-001
2. Click Supplier Price Comparison
3. Enter prices:

| Item   | Qty | Supplier X | Supplier Y |
|--------|-----|------------|------------|
| ITEM-A | 100 | 50.00     | 48.00      |
| ITEM-B | 50  | 125.00    | 130.00     |
| ITEM-C | 75  | 80.00     | 75.00      |

4. Create Quotations
5. Result: 2 Supplier Quotations created

### Example 2: Partial Quotes

**Scenario**:
- RFQ-002 has 5 items
- 3 suppliers, but each only quotes some items

**Steps**:
1. Open RFQ-002
2. Click Supplier Price Comparison
3. Enter prices (leave blank where not quoted):

| Item   | Supplier A | Supplier B | Supplier C |
|--------|------------|------------|------------|
| ITEM-1 | 100.00    | 95.00      |            |
| ITEM-2 | 200.00    |            | 190.00     |
| ITEM-3 |           | 150.00     | 145.00     |
| ITEM-4 | 300.00    | 295.00     | 290.00     |
| ITEM-5 |           |            | 400.00     |

4. Create Quotations
5. Result:
   - Supplier A: SQ with ITEM-1, ITEM-2, ITEM-4
   - Supplier B: SQ with ITEM-1, ITEM-3, ITEM-4
   - Supplier C: SQ with ITEM-2, ITEM-3, ITEM-4, ITEM-5

### Example 3: Skip Supplier

**Scenario**:
- One supplier doesn't respond to RFQ

**Steps**:
1. Open RFQ-003
2. Click Supplier Price Comparison
3. Enter prices only for responding suppliers
4. Leave entire column blank for non-responding supplier
5. Create Quotations
6. Result: Non-responding supplier skipped, no quotation created

---

## Troubleshooting

### Issue: Button Not Appearing

**Symptom**: Supplier Price Comparison button not visible

**Checklist**:
1. ✅ Is RFQ submitted? (docstatus = 1)
2. ✅ Does RFQ have items?
3. ✅ Does RFQ have suppliers?
4. ✅ Is JavaScript file loaded? (Check browser console)
5. ✅ Are assets built? (`bench build --app next_custom_app`)

**Solution**:
```bash
# Rebuild assets
bench build --app next_custom_app --force

# Clear cache
bench --site your-site.local clear-cache

# Hard refresh browser
Ctrl + Shift + R
```

### Issue: Pivot View Not Loading

**Symptom**: Error or blank dialog when opening pivot view

**Debug Steps**:
1. Open browser console (F12)
2. Look for JavaScript errors
3. Check network tab for failed API calls

**Common Causes**:
- Permission issues (check Company permissions)
- RFQ document corrupted
- Custom fields missing

**Solution**:
```python
# Check permissions
frappe.permissions.has_permission("Supplier Quotation", "create")

# Verify RFQ
rfq = frappe.get_doc("Request for Quotation", "RFQ-001")
print(rfq.items)
print(rfq.suppliers)
```

### Issue: Quotations Not Creating

**Symptom**: Click Create but nothing happens or error

**Check**:
1. Browser console for errors
2. Error log in ERPNext
3. Permission to create Supplier Quotation

**Common Issues**:
- Missing mandatory fields
- Validation errors
- Permission denied

**Debug**:
```python
# In bench console
from next_custom_app.next_custom_app.utils.procurement_workflow import get_rfq_pivot_data

data = get_rfq_pivot_data("RFQ-001")
print(data)
```

### Issue: Some Quotations Failed

**Symptom**: Some created, some failed in errors list

**This is normal** if:
- Supplier has validation rules
- Items have stock issues
- Price list mismatches

**Solution**:
- Review error messages in result dialog
- Fix issues individually
- Recreate failed quotations manually if needed

---

## Future Enhancements

Potential improvements for future versions:

1. **Import from Excel**: Upload supplier prices from spreadsheet
2. **Copy Previous Prices**: Auto-fill from previous RFQs
3. **Price History**: Show historical prices for comparison
4. **Conditional Formatting**: Highlight lowest prices
5. **Currency Conversion**: Support multi-currency quotes
6. **Approval Workflow**: Route created quotations for approval
7. **Email Integration**: Send quotations to suppliers directly
8. **Analytics Dashboard**: Compare supplier performance

---

## Support & Feedback

### Reporting Issues

- **Email**: info@nextcoretechnologies.com
- **GitHub**: Create issue with label "rfq-pivot-view"
- **Documentation**: See related files in `/next_custom_app/` directory

### Contributing

Pull requests welcome! Please:
1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Ensure no breaking changes

---

## Version History

### Version 1.0 (November 28, 2025)

**Initial Release**:
- ✅ Pivot table interface for price entry
- ✅ Automatic Supplier Quotation creation
- ✅ Selective processing (only suppliers with prices)
- ✅ Item filtering (exclude items without prices)
- ✅ Confirmation dialog with summary
- ✅ Result dialog with links
- ✅ Bulk submit functionality
- ✅ Keyboard navigation in matrix
- ✅ Progress indicators
- ✅ Error handling and reporting
- ✅ Integration with procurement workflow

---

**Document Version**: 1.0  
**Last Updated**: November 28, 2025  
**Maintained By**: Nextcore Technologies  
**License**: MIT