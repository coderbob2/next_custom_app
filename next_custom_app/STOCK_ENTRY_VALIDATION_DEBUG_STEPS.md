# Stock Entry Validation Debug Steps

## Critical Issues Identified
1. Stock Entry can be saved without source document when it's required
2. Duplicate Stock Entries are being created for the same source
3. Parallel step validation not working properly
4. Procurement source fields may not be saving to database

## Debug Steps

### Step 1: Verify Custom Fields Exist in Database
Run this in ERPNext Console (bench --site [site_name] console):

```python
import frappe

# Check if custom fields exist in Stock Entry doctype
stock_entry_meta = frappe.get_meta("Stock Entry")
fields_to_check = ["procurement_source_doctype", "procurement_source_name", "procurement_links"]

for field in fields_to_check:
    if stock_entry_meta.has_field(field):
        print(f"✓ Field '{field}' exists")
    else:
        print(f"✗ Field '{field}' MISSING - Run setup_custom_fields()")

# Check database columns
for field in ["procurement_source_doctype", "procurement_source_name"]:
    exists = frappe.db.has_column("tabStock Entry", field)
    print(f"DB Column '{field}': {'EXISTS' if exists else 'MISSING'}")
```

### Step 2: Run Custom Fields Setup
If fields are missing:

```bash
bench --site [site_name] execute next_custom_app.next_custom_app.utils.procurement_workflow.setup_custom_fields
```

### Step 3: Test Procurement Source Normalization
```python
import frappe
from next_custom_app.next_custom_app.utils.procurement_workflow import normalize_procurement_source

# Test with a Stock Entry
se = frappe.get_doc("Stock Entry", "[STOCK_ENTRY_NAME]")
print(f"Before normalization:")
print(f"  procurement_source_doctype: {se.get('procurement_source_doctype')}")
print(f"  procurement_source_name: {se.get('procurement_source_name')}")

normalize_procurement_source(se)

print(f"After normalization:")
print(f"  procurement_source_doctype: {se.get('procurement_source_doctype')}")
print(f"  procurement_source_name: {se.get('procurement_source_name')}")
```

### Step 4: Check Active Procurement Flow
```python
import frappe
from next_custom_app.next_custom_app.utils.procurement_workflow import get_active_flow, get_current_step

active_flow = get_active_flow()
if active_flow:
    print(f"Active Flow: {active_flow.name} - {active_flow.flow_name}")
    
    stock_entry_step = get_current_step("Stock Entry", active_flow.name)
    if stock_entry_step:
        print(f"Stock Entry Step:")
        print(f"  Step No: {stock_entry_step.step_no}")
        print(f"  Requires Source: {stock_entry_step.requires_source}")
        print(f"  Step Group: {getattr(stock_entry_step, 'step_group', 'None')}")
    else:
        print("Stock Entry NOT configured in workflow")
else:
    print("No active procurement flow - validation will be skipped!")
```

### Step 5: Test Parallel Step Detection
```python
import frappe
from next_custom_app.next_custom_app.utils.procurement_workflow import (
    get_parallel_step_doctypes,
    get_active_flow
)

active_flow = get_active_flow()
if active_flow:
    # Test parallel steps for Stock Entry
    parallel_doctypes = get_parallel_step_doctypes(
        "Material Request",  # source
        "Stock Entry",       # target
        active_flow.name
    )
    print(f"Parallel doctypes for Stock Entry: {parallel_doctypes}")
    
    # This should include Stock Entry AND any other doctypes in the same step
    # e.g., ["Stock Entry", "Purchase Requisition"] if they're in same step
```

### Step 6: Test Consumed Quantities
```python
import frappe
from next_custom_app.next_custom_app.utils.procurement_workflow import (
    get_parallel_consumed_breakdown
)

# Test with actual Material Request and check consumption
mr_name = "[MATERIAL_REQUEST_NAME]"
consumed = get_parallel_consumed_breakdown(
    "Material Request",
    mr_name,
    "Stock Entry"
)

print(f"Consumed breakdown for MR {mr_name}:")
for item_code, info in consumed.items():
    print(f"  {item_code}:")
    print(f"    Total consumed: {info['total']}")
    print(f"    Documents: {len(info['documents'])}")
    for doc in info['documents']:
        print(f"      - {doc['doctype']}: {doc['name']} ({doc['qty']})")
```

### Step 7: Check Existing Stock Entries for a Material Request
```python
import frappe

mr_name = "[MATERIAL_REQUEST_NAME]"

# Method 1: Via procurement_source fields
se_list_1 = frappe.get_all(
    "Stock Entry",
    filters={
        "procurement_source_doctype": "Material Request",
        "procurement_source_name": mr_name,
        "docstatus": ["!=", 2]
    },
    fields=["name", "docstatus", "procurement_source_name"]
)
print(f"Stock Entries via procurement_source: {len(se_list_1)}")
for se in se_list_1:
    print(f"  - {se.name} (docstatus: {se.docstatus})")

# Method 2: Via material_request references
rows = frappe.db.sql("""
    SELECT DISTINCT se.name, se.docstatus
    FROM `tabStock Entry` se
    INNER JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
    LEFT JOIN `tabMaterial Request Item` mri ON mri.name = sed.material_request_item
    WHERE se.docstatus != 2
        AND (
            sed.material_request = %(mr)s
            OR mri.parent = %(mr)s
            OR se.material_request = %(mr)s
            OR se.material_request_no = %(mr)s
        )
""", {"mr": mr_name}, as_dict=True)
print(f"Stock Entries via material_request refs: {len(rows)}")
for row in rows:
    print(f"  - {row.name} (docstatus: {row.docstatus})")
```

## Common Issues and Solutions

### Issue 1: Custom Fields Not Saving
**Symptom:** procurement_source fields are empty after save
**Solution:**
1. Run setup_custom_fields() again
2. Clear cache: `bench --site [site_name] clear-cache`
3. Migrate: `bench --site [site_name] migrate`
4. Verify field properties allow editing (not read_only)

### Issue 2: Validation Not Triggering
**Symptom:** Stock Entry saves without validation
**Solution:**
1. Check hooks.py has validate hook for Stock Entry
2. Verify workflow is active: `get_active_flow()` returns a flow
3. Check Stock Entry step has `requires_source = 1`
4. Verify validation function is not returning early

### Issue 3: Duplicate Stock Entries
**Symptom:** Multiple Stock Entries created for same Material Request
**Solution:**
1. Use get_parallel_consumed_breakdown() to check existing
2. Enforce source requirement in workflow configuration
3. Check consumed quantities before creating new Stock Entry
4. Add unique constraint checking in validation

### Issue 4: Parallel Step Validation Not Working
**Symptom:** Stock Entry ignores Purchase Requisition quantities
**Solution:**
1. Ensure both doctypes have same step_no OR same step_group
2. Verify get_parallel_step_doctypes() returns both doctypes
3. Check get_parallel_consumed_breakdown() aggregates correctly

## Verification Script
Run this complete verification:

```python
import frappe
from next_custom_app.next_custom_app.utils.procurement_workflow import *

def verify_stock_entry_validation():
    print("=" * 60)
    print("STOCK ENTRY VALIDATION VERIFICATION")
    print("=" * 60)
    
    # 1. Check custom fields
    print("\n1. Custom Fields Check:")
    meta = frappe.get_meta("Stock Entry")
    for field in ["procurement_source_doctype", "procurement_source_name"]:
        exists = meta.has_field(field)
        db_exists = frappe.db.has_column("tabStock Entry", field)
        status = "✓" if (exists and db_exists) else "✗"
        print(f"   {status} {field}: Meta={exists}, DB={db_exists}")
    
    # 2. Check workflow configuration
    print("\n2. Workflow Configuration:")
    active_flow = get_active_flow()
    if active_flow:
        print(f"   ✓ Active Flow: {active_flow.name}")
        step = get_current_step("Stock Entry", active_flow.name)
        if step:
            print(f"   ✓ Stock Entry Step No: {step.step_no}")
            print(f"   ✓ Requires Source: {step.requires_source}")
            if step.requires_source:
                print("   ⚠ Source document IS REQUIRED")
            else:
                print("   ⚠ Source document NOT required - manual creation allowed")
        else:
            print("   ✗ Stock Entry NOT in workflow")
    else:
        print("   ✗ No active workflow")
    
    # 3. Check hooks
    print("\n3. Validation Hooks:")
    print("   Check hooks.py for:")
    print("     - validate: validate_procurement_document")
    print("     - on_submit: on_procurement_submit")
    
    print("\n" + "=" * 60)
    print("Verification Complete")
    print("=" * 60)

# Run verification
verify_stock_entry_validation()
```

## Force Strict Validation
If validation is still bypassed, check these emergency fixes:

1. **Make procurement_source fields mandatory** (temporary):
```python
# In Stock Entry doctype customization
field = frappe.get_doc("Custom Field", "Stock Entry-procurement_source_name")
field.reqd = 1
field.save()
```

2. **Add before_insert hook** (catches before save):
```python
# In hooks.py, add:
"Stock Entry": {
    "before_insert": "next_custom_app.next_custom_app.utils.procurement_workflow.validate_stock_entry_before_insert",
}

# In procurement_workflow.py:
def validate_stock_entry_before_insert(doc, method=None):
    """Emergency validation before insert"""
    validate_stock_entry_source_alignment(doc)
```

3. **Database trigger** (last resort):
```sql
-- This prevents any insert without source (use carefully)
DELIMITER $$
CREATE TRIGGER check_stock_entry_source
BEFORE INSERT ON `tabStock Entry`
FOR EACH ROW
BEGIN
    IF NEW.procurement_source_doctype IS NULL 
        OR NEW.procurement_source_doctype = ''
        OR NEW.procurement_source_name IS NULL 
        OR NEW.procurement_source_name = '' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Stock Entry requires procurement source document';
    END IF;
END$$
DELIMITER ;
```
