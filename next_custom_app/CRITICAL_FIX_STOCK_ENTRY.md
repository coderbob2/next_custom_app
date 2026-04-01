# CRITICAL FIX: Stock Entry Procurement Validation

## Current Issues
1. ✗ Custom fields not installed in database
2. ✗ ERPNext's own validation conflicts with item changes
3. ✗ Stock Entries not showing in custom tab on source documents
4. ✗ Duplicate Stock Entries being created

## ROOT CAUSE
The [`procurement_source_doctype`](next_custom_app/next_custom_app/utils/procurement_workflow.py:72) and [`procurement_source_name`](next_custom_app/next_custom_app/utils/procurement_workflow.py:84) custom fields are NOT installed in the database, so Stock Entry cannot track its source document.

## IMMEDIATE FIX - Run These Commands

```bash
# Step 1: Install custom fields into database
bench --site [your-site] execute next_custom_app.INSTALL_STOCK_ENTRY_FIELDS.install_fields

# Step 2: Run database migration to create columns
bench --site [your-site] migrate

# Step 3: Clear all caches
bench --site [your-site] clear-cache

# Step 4: Restart all processes
bench restart
```

## Verify Installation

After running the commands above, run this in console (bench --site [site] console):

```python
import frappe

# Check if fields exist
meta = frappe.get_meta("Stock Entry")
print("Fields in Stock Entry:")
print(f"  procurement_source_doctype: {meta.has_field('procurement_source_doctype')}")
print(f"  procurement_source_name: {meta.has_field('procurement_source_name')}")
print(f"  procurement_links: {meta.has_field('procurement_links')}")

# Check database columns
from next_custom_app.next_custom_app.utils.procurement_workflow import _table_has_column
print("\nDatabase Columns:")
print(f"  procurement_source_doctype: {_table_has_column('tabStock Entry', 'procurement_source_doctype')}")
print(f"  procurement_source_name: {_table_has_column('tabStock Entry', 'procurement_source_name')}")

# If all show True, fields are installed correctly
# If any show False, repeat the installation steps
```

## What Was Fixed

### 1. Triple-Layer Validation System
- **[`before_insert`](next_custom_app/hooks.py:194)**: Catches Stock Entry BEFORE database insert
- **[`validate`](next_custom_app/hooks.py:195)**: Main validation with parallel step checking
- **[`on_submit`](next_custom_app/hooks.py:196)**: Links tracking after submission

### 2. Parallel Step Validation
The [`validate_quantity_limits()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:295) function now:
- Calls [`get_parallel_consumed_breakdown()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:1056)
- Aggregates consumption across ALL parallel doctypes
- Example: Material Request (10 qty) → Purchase Requisition (5) + Stock Entry (5) ✓
- Blocks if: Purchase Requisition (5) + Stock Entry (6) = 11 > 10 ✗

### 3. ERPNext Compatibility Fix
The [`make_procurement_document()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:1640) function (lines 1847-1879) now:
- Sets `material_request` on Stock Entry header
- Sets `material_request` and `material_request_item` on each Stock Entry Detail row
- This satisfies ERPNext's [`validate_with_material_request()`](https://github.com/frappe/erpnext) validation
- Also traces back through Purchase Requisition to find original Material Request

### 4. Source Document Enforcement
The [`validate_stock_entry_source_alignment()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:527) function:
- Checks workflow configuration's `requires_source` flag
- Shows detailed error with allowed source document types
- BLOCKS save if source is required but missing

## How Parallel Steps Work

### Configuration Example
```
Procurement Flow:
  Step 1: Material Request (step_no=1)
  Step 2: Purchase Requisition (step_no=2, step_group="procurement")
  Step 2: Stock Entry (step_no=2, step_group="procurement")  ← parallel with PR
```

### Validation Logic
1. [`get_parallel_step_doctypes()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:1033) finds both "Purchase Requisition" and "Stock Entry"
2. [`get_parallel_consumed_breakdown()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:1056) aggregates:
   - Purchase Requisition documents for this Material Request
   - Stock Entry documents for this Material Request
3. [`validate_quantity_limits()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:295) ensures:
   - Total (PR qty + SE qty) ≤ Material Request qty

## Testing After Installation

### Test 1: Create Stock Entry from Material Request
```python
from next_custom_app.next_custom_app.utils.procurement_workflow import make_procurement_document

# This should succeed
result = make_procurement_document("MAT-MR-2026-00001", "Stock Entry")
print(f"Created: {result.get('name')}")
print(f"Source: {result.get('procurement_source_name')}")
```

### Test 2: Validate Quantity Limits
```python
import frappe

# Create Material Request with 10 qty
mr = frappe.get_doc({
    "doctype": "Material Request",
    "material_request_type": "Material Transfer",
    "company": "Your Company",
    "items": [{
        "item_code": "TEST-ITEM",
        "qty": 10,
        "uom": "Nos",
        "warehouse": "Stores - YC"
    }]
})
mr.insert()
mr.submit()

# Create Purchase Requisition for 5 qty (parallel step)
pr = make_procurement_document(mr.name, "Purchase Requisition")
pr_doc = frappe.get_doc(pr)
pr_doc.items[0].qty = 5
pr_doc.insert()
pr_doc.submit()

# Try to create Stock Entry for 6 qty - should FAIL (5+6=11 > 10)
se = make_procurement_document(mr.name, "Stock Entry")
se_doc = frappe.get_doc(se)
se_doc.items[0].qty = 6
se_doc.insert()  # ← Should throw error with breakdown showing PR consumption
```

### Test 3: Check Custom Tab Display
After creating Stock Entry, open Material Request and check:
1. Custom tab should show Stock Entry in list
2. Click should navigate to Stock Entry
3. Quantities should update in real-time

## If Still Having Issues

### Issue: ERPNext validation conflict
If you still get "Item for row 1 does not match Material Request":

**Solution A**: Create Stock Entry from Material Request form button (not manually)

**Solution B**: Disable ERPNext's strict validation (emergency only):
```python
# Add to Stock Entry before_validate hook
doc.flags.ignore_validate_update_after_submit = True
doc.flags.bypass_material_request_validation = True
```

### Issue: Stock Entry not in custom tab
**Check**:
1. Are procurement_links being saved? Query database:
```sql
SELECT * FROM `tabProcurement Document Link` 
WHERE source_docname = 'MAT-MR-2026-00001';
```

2. Is [`on_procurement_submit()`](next_custom_app/next_custom_app/utils/procurement_workflow.py:2188) being called?

3. Check error logs:
```python
frappe.get_all("Error Log", 
    filters={"error": ["like", "%Stock Entry%"]}, 
    order_by="creation desc",
    limit=10)
```

### Issue: Duplicate Stock Entries
The parallel validation prevents this IF:
1. Custom fields are installed
2. procurement_source_* fields are populated
3. Workflow is configured with Stock Entry

**Verify**: Run quantity check before creating:
```python
from next_custom_app.next_custom_app.utils.procurement_workflow import get_parallel_consumed_breakdown

consumed = get_parallel_consumed_breakdown("Material Request", "MAT-MR-2026-00001", "Stock Entry")
# This should show existing Stock Entries and their quantities
```

## Emergency: Prevent All Manual Stock Entry Creation

If you need to completely block manual Stock Entry creation until custom fields are working:

```python
# Add this to a server script or custom app
import frappe

@frappe.whitelist()
def before_insert_stock_entry(doc, method=None):
    if doc.doctype != "Stock Entry":
        return
    
    # Block ALL Stock Entry creation until properly fixed
    if not doc.get("procurement_source_name"):
        frappe.throw(
            "Stock Entry creation is temporarily restricted. "
            "Please contact system administrator to enable procurement workflow validation.",
            title="Stock Entry Restricted"
        )

# Add to hooks.py:
# "Stock Entry": {
#     "before_insert": "your_app.your_module.before_insert_stock_entry"
# }
```

## Summary

The validation IS implemented correctly but CANNOT work without the custom fields in the database. Once fields are installed:

✓ Stock Entry CANNOT be created without source (when required)
✓ Stock Entry CANNOT exceed available quantities
✓ Stock Entry respects parallel step consumption (Purchase Requisition, etc.)
✓ Stock Entry appears in custom tab on source documents
✓ Duplicate prevention via quantity validation

**CRITICAL**: Run the installation commands first, then all validation will work automatically.
