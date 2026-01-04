# Implementation Steps for Procurement Document Creation Fix

## Summary of Changes

Two critical issues have been fixed:

### ✅ Issue 1: Items Not Being Copied
**Fixed in:** [`make_procurement_document()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:1213)

**Changes Made:**
- Removed dependency on Frappe's `get_mapped_doc()` which had complex field mapping requirements
- Implemented direct item copying using `frappe.new_doc()` and `append()`
- Added validation to ensure ALL items are copied
- Added logging to track item copying process
- Improved error messages for debugging

### ✅ Issue 2: Source Document Required Error
**Fixed in:** [`validate_step_order()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:198)

**Changes Made:**
- Modified validation logic to allow manual document creation
- Only enforces source requirement when source fields are partially set
- If both `procurement_source_doctype` and `procurement_source_name` are empty, manual creation is allowed
- Added logging for manual creation cases

## Deployment Steps

### Step 1: Apply Code Changes ✅ DONE

The following files have been updated:
- [`next_custom_app/next_custom_app/utils/procurement_workflow.py`](next_custom_app/next_custom_app/utils/procurement_workflow.py)

### Step 2: Restart Frappe Services

After code changes, restart the Frappe bench:

```bash
# Stop all services
bench --site [your-site] frappe --stop

# Or use supervisor if running in production
sudo supervisorctl stop all

# Clear cache
bench --site [your-site] clear-cache

# Restart
bench --site [your-site] frappe --start

# Or use restart command (combines stop/start)
bench restart
```

### Step 3: Verify Custom Fields

Ensure procurement custom fields are created on all doctypes:

```bash
bench --site [your-site] execute next_custom_app.next_custom_app.utils.procurement_workflow.setup_custom_fields
```

Expected fields to be created:
- `procurement_section` - Section Break
- `procurement_source_doctype` - Link to DocType
- `procurement_source_name` - Dynamic Link
- `procurement_links` - Child Table

### Step 4: Verify Procurement Flow Configuration

1. Navigate to: **Procurement Workflow > Procurement Flow**
2. Check that an active flow exists (is_active = checked)
3. Verify flow steps configuration:

```
Step 1: Material Request
  └─ requires_source: unchecked (can be created manually)

Step 2: Purchase Requisition
  └─ requires_source: checked (prefers source, but allows manual)

Step 3: Request for Quotation
  └─ requires_source: checked (prefers source, but allows manual)

Step 4: Supplier Quotation
  └─ requires_source: checked (must be from RFQ for supplier validation)

Step 5: Purchase Order
  └─ requires_source: checked (prefers source, but allows manual)

Step 6: Purchase Receipt
  └─ requires_source: checked (should be from PO)

Step 7: Purchase Invoice
  └─ requires_source: checked (should be from PR or PO)
```

## Testing Procedure

### Test Case 1: Create Purchase Requisition from Material Request

**Prerequisites:**
- Material Request with items created and submitted

**Steps:**
1. Open a submitted Material Request (e.g., MR-00001)
2. Click **Create** button in the toolbar
3. Select **Custom: Purchase Requisition** from dropdown
4. Dialog should appear showing the creation confirmation
5. Click **Create Purchase Requisition**

**Expected Results:**
- ✅ New Purchase Requisition form opens
- ✅ ALL items from Material Request are copied
- ✅ Item quantities match source
- ✅ Item details (UOM, description, warehouse) are copied
- ✅ Fields auto-populated:
  - `procurement_source_doctype` = "Material Request"
  - `procurement_source_name` = "MR-00001"
  - `transaction_date` = today's date
  - `company` = source company
- ✅ Can save the document
- ✅ Can submit the document

**Validation:**
```sql
-- Verify items were copied
SELECT 
    pr.name as purchase_requisition,
    COUNT(pri.item_code) as item_count,
    pr.procurement_source_name
FROM `tabPurchase Requisition` pr
LEFT JOIN `tabPurchase Requisition Item` pri ON pri.parent = pr.name
WHERE pr.name = '[PR-NAME]'
GROUP BY pr.name;
```

### Test Case 2: Create Purchase Requisition Manually

**Steps:**
1. Navigate to: **Purchase Requisition List**
2. Click **New** button
3. Fill in required fields:
   - Purpose: Purchase
   - Company: [Select Company]
   - Transaction Date: [Auto-filled]
4. Add items manually
5. Leave source fields empty
6. Click **Save**

**Expected Results:**
- ✅ Document saves successfully
- ✅ No "source document required" error
- ✅ `procurement_source_doctype` and `procurement_source_name` are empty
- ✅ Can add items manually
- ✅ Can submit the document
- ✅ Can use this document as source for next step (RFQ)

### Test Case 3: Create Request for Quotation from Purchase Requisition

**Prerequisites:**
- Purchase Requisition created (from MR or manually) and submitted

**Steps:**
1. Open submitted Purchase Requisition (e.g., PR-00001)
2. Click **Create** → **Custom: Request for Quotation**
3. Confirm creation in dialog

**Expected Results:**
- ✅ New RFQ form opens with all items copied
- ✅ Source fields populated correctly
- ✅ Can add suppliers
- ✅ Can save and submit

### Test Case 4: Quantity Validation

**Prerequisites:**
- Material Request with Item A: Qty 100 submitted
- Purchase Requisition created from MR with Item A: Qty 60 submitted

**Steps:**
1. Try to create another Purchase Requisition from same MR
2. Add Item A with qty 50
3. Try to save

**Expected Results:**
- ✅ Error message appears
- ✅ Error shows:
  - Source Quantity: 100
  - Already Processed: 60
  - Available: 40
  - Your Request: 50 (❌ exceeds available)
- ✅ Error details show which document consumed the qty
- ✅ Cannot save until qty is reduced to 40 or less

### Test Case 5: Document Chain Verification

**Steps:**
1. Open any document in the procurement chain
2. Check the custom section at top of form
3. Click **Document Flow** button

**Expected Results:**
- ✅ Dialog shows complete document tree
- ✅ Current document is highlighted
- ✅ Source documents shown (backward links)
- ✅ Child documents shown (forward links)
- ✅ Can click on any document to navigate
- ✅ Document count badges are accurate

## Troubleshooting

### Problem: Items Not Showing After Creation

**Check:**
1. Browser console for JavaScript errors
2. Frappe error log: `bench --site [site] logs`
3. Item table field name matches:
   - Material Request: `items`
   - Purchase Requisition: `items`
   - RFQ: `items`

**Debug:**
```python
# In Frappe console
bench --site [your-site] console

# Test item field detection
from next_custom_app.next_custom_app.utils.procurement_workflow import get_items_field_name

print(get_items_field_name("Material Request"))
print(get_items_field_name("Purchase Requisition"))
```

### Problem: "Source Document Required" Error Still Appears

**Check:**
1. Procurement Flow is active
2. Step configuration for requires_source
3. Both source fields are empty (not just one)

**Debug:**
```python
# Check active flow
from next_custom_app.next_custom_app.utils.procurement_workflow import get_active_flow

flow = get_active_flow()
print(flow)

# Check step configuration
from next_custom_app.next_custom_app.utils.procurement_workflow import get_current_step

step = get_current_step("Purchase Requisition")
print(step.requires_source if step else "No step found")
```

### Problem: Quantity Validation Not Working

**Check:**
1. Source document is submitted
2. Custom fields exist on all doctypes
3. Items have same item_code in source and target

**Debug:**
```python
# Check consumed quantities
from next_custom_app.next_custom_app.utils.procurement_workflow import get_consumed_quantities

consumed = get_consumed_quantities(
    "Material Request",
    "MR-00001",
    "Purchase Requisition"
)
print(consumed)
```

## Verification Queries

### Check Document Linkage

```sql
SELECT 
    pr.name as purchase_requisition,
    pr.procurement_source_doctype,
    pr.procurement_source_name,
    pr.docstatus,
    COUNT(pri.item_code) as item_count
FROM `tabPurchase Requisition` pr
LEFT JOIN `tabPurchase Requisition Item` pri ON pri.parent = pr.name
WHERE pr.procurement_source_name IS NOT NULL
GROUP BY pr.name
ORDER BY pr.creation DESC
LIMIT 10;
```

### Check Item Quantities

```sql
SELECT 
    mr.name as material_request,
    mri.item_code,
    mri.qty as requested_qty,
    COALESCE(SUM(pri.qty), 0) as processed_qty,
    mri.qty - COALESCE(SUM(pri.qty), 0) as remaining_qty
FROM `tabMaterial Request` mr
INNER JOIN `tabMaterial Request Item` mri ON mri.parent = mr.name
LEFT JOIN `tabPurchase Requisition` pr ON pr.procurement_source_name = mr.name AND pr.docstatus != 2
LEFT JOIN `tabPurchase Requisition Item` pri ON pri.parent = pr.name AND pri.item_code = mri.item_code
WHERE mr.name = 'MR-00001'
GROUP BY mr.name, mri.item_code;
```

### Check Backward Links

```sql
SELECT 
    source_doctype,
    source_docname,
    target_doctype,
    target_docname,
    link_date
FROM `tabProcurement Document Link`
WHERE source_docname = 'MR-00001'
ORDER BY link_date DESC;
```

## Rollback Procedure

If issues occur, rollback steps:

### 1. Revert Code Changes

```bash
# Navigate to app directory
cd /path/to/bench/apps/next_custom_app

# Check git status
git status

# Revert changes
git checkout next_custom_app/next_custom_app/utils/procurement_workflow.py

# Restart bench
bench restart
```

### 2. Check for Orphaned Documents

```sql
-- Find documents with source but source not found
SELECT 
    pr.name,
    pr.procurement_source_doctype,
    pr.procurement_source_name
FROM `tabPurchase Requisition` pr
WHERE pr.procurement_source_name IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM `tabMaterial Request` mr 
    WHERE mr.name = pr.procurement_source_name
);
```

### 3. Clear Cache

```bash
bench --site [your-site] clear-cache
bench --site [your-site] clear-website-cache
```

## Performance Considerations

### Expected Performance:
- Document creation: < 1 second
- Item copying (100 items): < 2 seconds
- Validation: < 500ms
- Document flow query: < 1 second

### Optimization Tips:
1. Ensure database indexes exist on:
   - `procurement_source_name`
   - `procurement_source_doctype`
   - `item_code` in item child tables

2. Cache active flow result (already implemented)

3. Use batch operations for multiple documents:
```python
# Instead of creating one by one
for mr in material_requests:
    create_purchase_requisition(mr)

# Use batch create
batch_create_purchase_requisitions(material_requests)
```

## Monitoring

### Key Metrics to Track:
1. Document creation success rate
2. Item copy accuracy (source count vs target count)
3. Validation error frequency
4. Document chain depth (avg number of linked docs)

### Log Messages to Watch:
```
# Success
"{doctype} {name}: Manual creation allowed - no source fields set"
"Creating {target} from {source} with {count} items"
"Copied {count} items to {target}"

# Warnings
"Warning: Expected {expected} items but copied {actual}"

# Errors (should not see after fix)
"Source document required error"
"Failed to copy items from source document"
```

## Support Resources

### Documentation:
- [PROCUREMENT_DOCUMENT_CREATION_FIX.md](next_custom_app/PROCUREMENT_DOCUMENT_CREATION_FIX.md)
- [RFQ_QUANTITY_VALIDATION_FIX.md](next_custom_app/RFQ_QUANTITY_VALIDATION_FIX.md)

### Code References:
- [`make_procurement_document()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:1213)
- [`validate_step_order()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:198)
- [`validate_quantity_limits()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:233)

### Frappe Console Commands:
```python
# Test document creation
from next_custom_app.next_custom_app.utils.procurement_workflow import make_procurement_document

doc = make_procurement_document("MR-00001", "Purchase Requisition")
print(f"Created: {doc['name']}, Items: {len(doc['items'])}")
```
