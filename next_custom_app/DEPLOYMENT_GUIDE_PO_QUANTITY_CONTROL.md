# Deployment Guide: PO Quantity Control & Supplier Comparison

## Complete Step-by-Step Installation Guide

**Target**: Production/Server Environment  
**Date**: January 5, 2026

---

## Prerequisites

- [ ] ERPNext installed and running
- [ ] `next_custom_app` installed on the site
- [ ] Bench access (SSH or terminal)
- [ ] Administrator access to site

---

## Step 1: Pull Latest Code

```bash
# Navigate to the app directory
cd /path/to/frappe-bench/apps/next_custom_app

# Pull latest changes
git pull origin main

# Or if you're pushing from local
git add .
git commit -m "Add PO Quantity Control and Supplier Comparison"
git push origin main
```

---

## Step 2: Migrate Database

```bash
# Navigate to bench directory
cd /path/to/frappe-bench

# Run migrate for your site
bench --site yoursite.com migrate

# This will:
# - Create new doctypes (Supplier Comparison, child tables)
# - Update existing doctypes
# - Run any patches
```

**Expected Output**:
```
Updating DocTypes for next_custom_app: [========================================] 100%
Migrating yoursite.com
Migration complete!
```

---

## Step 3: Setup Custom Fields on RFQ Item

```bash
# Open bench console
bench --site yoursite.com console
```

Then run this Python code:

```python
# Import the setup function
from next_custom_app.next_custom_app.utils.po_quantity_control import setup_rfq_quantity_fields

# Run setup
setup_rfq_quantity_fields()

# You should see: "RFQ quantity tracking fields created successfully!"
```

**Alternative method** (if above doesn't work):

```python
# Manual field creation
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

custom_fields = {
    "Request for Quotation Item": [
        {
            "fieldname": "column_break_qty_tracking",
            "fieldtype": "Column Break",
            "insert_after": "qty"
        },
        {
            "fieldname": "ordered_qty",
            "label": "Ordered Quantity",
            "fieldtype": "Float",
            "default": "0",
            "read_only": 1,
            "insert_after": "column_break_qty_tracking"
        },
        {
            "fieldname": "remaining_qty",
            "label": "Remaining Quantity",
            "fieldtype": "Float",
            "read_only": 1,
            "insert_after": "ordered_qty"
        }
    ]
}

create_custom_fields(custom_fields, update=True)
frappe.db.commit()
print("Custom fields created!")
```

---

## Step 4: Clear Cache & Restart

```bash
# Clear all caches
bench --site yoursite.com clear-cache

# Build JS/CSS assets
bench build --app next_custom_app

# Restart bench
bench restart
```

---

## Step 5: Verify Installation

### 5.1 Check Custom Fields

1. Open any RFQ in the system
2. Go to Menu → Customize Form
3. Search for "ordered_qty"
4. Verify these fields exist in RFQ Item table:
   - `ordered_qty` (Float, Read Only)
   - `remaining_qty` (Float, Read Only)

### 5.2 Check Buttons in RFQ

1. Create a new RFQ
2. Add items and suppliers
3. Submit the RFQ
4. **Check for these buttons**:
   - Under `Create`: "Supplier Price Comparison"
   - Under `Actions`: "Compare & Award Suppliers"

### 5.3 Check Purchase Order Scripts

1. Create a new Purchase Order
2. Open browser console (F12)
3. Look for: `"=== Purchase Order Quantity Control Script Loaded ==="`

---

## Step 6: Test the Workflow

### Test Case 1: Basic Functionality

```
1. Create RFQ:
   - Item: TEST-ITEM-001, Qty: 100
   - Suppliers: Supplier A, Supplier B

2. Submit RFQ

3. Create SQs via Pivot:
   - Click Create → Supplier Price Comparison
   - Enter prices:
     * Supplier A: $10
     * Supplier B: $ 9
   - Confirm creation
   - Submit all SQs

4. Compare & Award:
   - Click Actions → Compare & Award Suppliers
   - Verify Supplier B wins (lower total)
   - Click "Award Supplier B"
   - Verify PO created with:
     * Supplier: Supplier B ✓
     * Items: TEST-ITEM-001, Qty: 100 ✓
     * Schedule dates set ✓

5. Save & Submit PO:
   - Save PO → should work ✓
   - Submit PO → should work ✓
   - Go back to RFQ
   - Verify ordered_qty = 100, remaining_qty = 0 ✓

6. Try to create another PO:
   - From Supplier A's SQ
   - Try to save with qty > 0
   - Should block with styled error message ✓
```

---

## Troubleshooting

### Issue 1: "Compare & Award" Button Not Showing

**Symptoms**: Button missing in RFQ Actions dropdown

**Solutions**:

```bash
# 1. Rebuild JS/CSS
bench build --app next_custom_app

# 2. Clear browser cache
# In browser: Ctrl + Shift + R (hard refresh)

# 3. Check if JS file is loaded
# In browser console:
# Should see: "=== RFQ Comparison Script Loaded ==="

# 4. Verify hooks.py registered correctly
grep -A 10 "doctype_js" apps/next_custom_app/next_custom_app/hooks.py

# Should show:
# "Request for Quotation": [
#     "public/js/procurement_custom_tabs.js",
#     "public/js/rfq_pivot_view.js",
#     "public/js/rfq_comparison.js"
# ]
```

---

### Issue 2: Custom Fields Not Visible

**Symptoms**: RFQ items table missing `ordered_qty` and `remaining_qty` columns

**Solutions**:

```bash
# Method 1: Re-run setup
bench --site yoursite.com console
>>> from next_custom_app.next_custom_app.utils.po_quantity_control import setup_rfq_quantity_fields
>>> setup_rfq_quantity_fields()

# Method 2: Check if fields exist
>>> import frappe
>>> frappe.db.sql("""
...     SELECT name, label, fieldtype 
...     FROM `tabCustom Field` 
...     WHERE dt = 'Request for Quotation Item' 
...     AND fieldname IN ('ordered_qty', 'remaining_qty')
... """, as_dict=True)

# Should return 2 rows

# Method 3: Delete and recreate
>>> frappe.db.sql("DELETE FROM `tabCustom Field` WHERE dt = 'Request for Quotation Item' AND fieldname IN ('ordered_qty', 'remaining_qty')")
>>> frappe.db.commit()
>>> setup_rfq_quantity_fields()

# Method 4: Clear cache
>>> frappe.clear_cache()
```

---

### Issue 3: Quantity Not Updating After PO Submit

**Symptoms**: `ordered_qty` still 0 after submitting PO

**Check**:

```python
# In bench console
import frappe

# Get a submitted PO
po = frappe.get_doc("Purchase Order", "PO-XXX")

# Check source linkage
print(f"PO Source: {po.procurement_source_doctype} - {po.procurement_source_name}")

# Should show: "PO Source: Supplier Quotation - SQ-XXX"

# Get the SQ
sq = frappe.get_doc(po.procurement_source_doctype, po.procurement_source_name)
print(f"SQ Source: {sq.procurement_source_doctype} - {sq.procurement_source_name}")

# Should show: "SQ Source: Request for Quotation - RFQ-XXX"

# Check RFQ
rfq = frappe.get_doc(sq.procurement_source_doctype, sq.procurement_source_name)
for item in rfq.items:
    print(f"{item.item_code}: ordered={item.ordered_qty}, remaining={item.remaining_qty}")

# Should show updated quantities
```

**Fix**:

```bash
# Check if hooks are registered
grep -A 20 "doc_events" apps/next_custom_app/next_custom_app/hooks.py | grep -A 10 "Purchase Order"

# Should show:
# "Purchase Order": {
#     "validate": [..., "next_custom_app.next_custom_app.utils.po_quantity_control.on_po_validate"],
#     "on_submit": [..., "next_custom_app.next_custom_app.utils.po_quantity_control.on_po_submit"],
#     "on_cancel": "next_custom_app.next_custom_app.utils.po_quantity_control.on_po_cancel"
# }

# If not there, hooks aren't registered  # Restart bench
bench restart
```

---

### Issue 4: Supplier Not Auto-Filling in PO

**Symptoms**: PO supplier field empty after award

**Solutions**:

```bash
# 1. Check PO client script loaded
# In browser console (on PO form):
# Should see: "=== Purchase Order Quantity Control Script Loaded ==="

# 2. Rebuild to ensure JS is compiled
bench build --app next_custom_app

# 3. Manually check if validation works
bench --site yoursite.com console

>>> import frappe
>>> po = frappe.new_doc("Purchase Order")
>>> po.procurement_source_doctype = "Supplier Quotation"
>>> po.procurement_source_name = "SQ-XXX"  # Use real SQ
>>> po.items = []
>>> from next_custom_app.next_custom_app.utils.po_quantity_control import validate_supplier_matches_sq
>>> validate_supplier_matches_sq(po)
>>> print(f"Supplier auto-set to: {po.supplier}")

# Should auto-set supplier from SQ
```

---

### Issue 5: Comparison Dialog Shows No Data

**Symptoms**: "No submitted Supplier Quotations found" message

**Check**:

```python
# In bench console
import frappe

rfq_name = "RFQ-XXX"  # Your RFQ name

# Get SQs
sqs = frappe.get_all("Supplier Quotation",
    filters={
        "procurement_source_doctype": "Request for Quotation",
        "procurement_source_name": rfq_name,
        "docstatus": 1
    },
    fields=["name", "supplier", "grand_total"]
)

print(f"Found {len(sqs)} submitted SQs:")
for sq in sqs:
    print(f"  - {sq.name}: {sq.supplier} = {sq.grand_total}")

# If empty, SQs aren't linked to RFQ properly
```

**Fix Source Linkage**:

```python
# Check an SQ
sq = frappe.get_doc("Supplier Quotation", "SQ-XXX")
print(f"Source: {sq.procurement_source_doctype} - {sq.procurement_source_name}")

# If source is empty or wrong, fix it:
sq.procurement_source_doctype = "Request for Quotation"
sq.procurement_source_name = "RFQ-XXX"
sq.save()
```

---

## Server-Specific Setup

### For Multi-Tenantench Setups

If you have multiple sites on same bench:

```bash
# Run setup for EACH site
bench --site site1.com migrate
bench --site site1.com console
>>> from next_custom_app.next_custom_app.utils.po_quantity_control import setup_rfq_quantity_fields
>>> setup_rfq_quantity_fields()

bench --site site2.com migrate
bench --site site2.com console
>>> from next_custom_app.next_custom_app.utils.po_quantity_control import setup_rfq_quantity_fields
>>> setup_rfq_quantity_fields()

# Clear cache for all sites
bench --site site1.com clear-cache
bench --site site2.com clear-cache

# Rebuild once (applies to all sites)
bench build --app next_custom_app

# Restart
bench restart
```

---

### For Production Servers (with Supervisor/Nginx)

```bash
# 1. Stop services
sudo supervisorctl stop all

# 2. Update code
cd /path/to/frappe-bench/apps/next_custom_app
git pull origin main

# 3. Migrate
cd /path/to/frappe-bench
bench --site yoursite.com migrate

# 4. Setup custom fields
bench --site yoursite.com console << EOF
from next_custom_app.next_custom_app.utils.po_quantity_control import setup_rfq_quantity_fields
setup_rfq_quantity_fields()
exit()
EOF

# 5. Clear cache
bench --site yoursite.com clear-cache

# 6. Build assets
bench build --app next_custom_app

# 7. Restart services
sudo supervisorctl start all
```

---

## Verification Checklist

After deployment, verify each component:

### ✅ Backend Verification

```python
# In bench console
import frappe

# 1. Check if doctypes exist
print("Supplier Comparison exists:", frappe.db.exists("DocType", "Supplier Comparison"))
print("Supplier Comparison Supplier exists:", frappe.db.exists("DocType", "Supplier Comparison Supplier"))
print(" Supplier Comparison Item exists:", frappe.db.exists("DocType", "Supplier Comparison Item"))

# 2. Check if custom fields exist
custom_fields = frappe.get_all("Custom Field", 
    filters={
        "dt": "Request for Quotation Item",
        "fieldname": ["in", ["ordered_qty", "remaining_qty"]]
    },
    fields=["fieldname", "label"]
)
print(f"Custom fields on RFQ Item: {custom_fields}")
# Should show 2 fields

# 3. Test Python API
from next_custom_app.next_custom_app.utils.po_quantity_control import get_rfq_available_quantities

# Use a real RFQ name
rfq_quantities = get_rfq_available_quantities("RFQ-XXX")
print(f"RFQ quantities: {rfq_quantities}")
```

### ✅ Frontend Verification

**In Browser**:

1. **Check Console for Scripts**:
   - Open RFQ form
   - Press F12 → Console tab
   - Look for:
     * "=== RFQ Comparison Script Loaded ==="
     * "=== RFQ Pivot View Script Loaded ==="

2. **Check Buttons**:
   - Submit an RFQ
   - Verify dropdowns have:
     * Create → "Supplier Price Comparison"
     * Actions → "Compare & Award Suppliers"

3. **Check PO Form**:
   - Open any PO form
   - Console should show:
     * "=== Purchase Order Quantity Control Script Loaded ==="

---

## Common Issues & Fixes

### Issue: "Module not found" Error

```
ModuleNotFoundError: No module named 'next_custom_app.next_custom_app.utils.po_quantity_control'
```

**Fix**:
```bash
# Restart Python processes
bench restart

# If that doesn't work, check file exists
ls -la apps/next_custom_app/next_custom_app/utils/po_quantity_control.py

# If file is missing, re-pull code
cd apps/next_custom_app
git pull origin main
```

---

### Issue: Hooks Not Working

**Symptoms**: Validation not running, quantities not updating

**Fix**:
```bash
# 1. Verify hooks.py syntax
python3 -c "import sys; sys.path.insert(0, 'apps/next_custom_app'); import next_custom_app.hooks"

# 2. If error, check hooks.py for syntax issues

# 3. Restart to reload hooks
bench restart

# 4. Test a single hook manually
bench --site yoursite.com console
>>> import frappe
>>> po = frappe.get_doc("Purchase Order", "PO-XXX")
>>> from next_custom_app.next_custom_app.utils.po_quantity_control import on_po_validate
>>> on_po_validate(po)
# Should run validation
```

---

### Issue: JS Files Not Loading

**Symptoms**: Buttons missing, scripts not in console

**Fix**:
```bash
# 1. Build with force flag
bench build --app next_custom_app --force

# 2. Clear Redis cache
bench --site yoursite.com clear-cache

# 3. Clear browser cache
# Ctrl + Shift + Delete → Clear cached files

# 4. Check if files exist
ls -la apps/next_custom_app/next_custom_app/public/js/rfq_comparison.js
ls -la apps/next_custom_app/next_custom_app/public/js/purchase_order_po_control.js

# 5. Verify hooks.py has them
grep -A 15 "doctype_js" apps/next_custom_app/next_custom_app/hooks.py
```

---

## Database Cleanup (If Needed)

If you need to start fresh:

```python
# In bench console - USE WITH CAUTION!

import frappe

# Remove custom fields
frappe.db.sql("""
    DELETE FROM `tabCustom Field` 
    WHERE dt = 'Request for Quotation Item' 
    AND fieldname IN ('ordered_qty', 'remaining_qty', 'column_break_qty_tracking')
""")

# Remove doctypes (if needed)
# frappe.delete_doc("DocType", "Supplier Comparison", force=1)
# frappe.delete_doc("DocType", "Supplier Comparison Supplier", force=1)
# frappe.delete_doc("DocType", "Supplier Comparison Item", force=1)

frappe.db.commit()

# Then re-run setup
from next_custom_app.next_custom_app.utils.po_quantity_control import setup_rfq_quantity_fields
setup_rfq_quantity_fields()
```

---

## Performance Optimization

### For Large Sites

```python
# Add database indexes for faster queries
import frappe

# Index on procurement source fields
queries = [
    """
    CREATE INDEX idx_po_source 
    ON `tabPurchase Order` (procurement_source_doctype, procurement_source_name)
    """,
    """
    CREATE INDEX idx_sq_source 
    ON `tabSupplier Quotation` (procurement_source_doctype, procurement_source_name, docstatus)
    """
]

for query in queries:
    try:
        frappe.db.sql(query)
        print(f"Index created: {query[:50]}...")
    except Exception as e:
        print(f"Index might already exist: {str(e)}")

frappe.db.commit()
```

---

## Rollback Plan

If something goes wrong:

```bash
# 1. Revert code
cd apps/next_custom_app
git reset --hard HEAD~1

# 2. Restart
bench restart

# 3. If database was modified, restore backup
bench --site yoursite.com restore /path/to/backup/file.sql.gz
```

---

## Production Deployment Checklist

Before deploying to production:

- [ ] Tested on staging/development site
- [ ] Database backup taken
- [ ] All custom fields created successfully
- [ ] All buttons visible in RFQ
- [ ] Comparison works with test data
- [ ] PO creation works from award
- [ ] Quantity validation blocks over-ordering
- [ ] Supplier auto-fills correctly
- [ ] No JavaScript errors in console
- [ ] Error messages display properly
- [ ] Cache cleared
- [ ] Services restarted

---

## Post-Deployment Monitoring

### Check Logs

```bash
# Watch for errors
tail -f sites/yoursite.com/logs/web.log

# Check for specific errors
grep -i "po_quantity_control" sites/yoursite.com/logs/web.log
grep -i "supplier_comparison" sites/yoursite.com/logs/web.log
```

### Monitor Performance

```python
# In bench console
import frappe

# Check query performance
frappe.db.sql("""
    SELECT 
        COUNT(*) as po_count,
        procurement_source_doctype,
        procurement_source_name
    FROM `tabPurchase Order`
    WHERE procurement_source_doctype = 'Supplier Quotation'
    GROUP BY procurement_source_name
    ORDER BY po_count DESC
    LIMIT 10
""", as_dict=True)

# Shows which SQs have most POs (potential bottleneck)
```

---

## Support

**If issues persist**:

1. **Collect Information**:
   ```bash
   # Get versions
   bench version
   
   # Get site details
   bench --site yoursite.com doctor
   
   # Export error log
   tail -n 500 sites/yoursite.com/logs/web.log > error_log.txt
   ```

2. **Contact**: info@nextcoretechnologies.com

3. **Include**:
   - ERPNext version
   - Bench version
   - Error logs
   - Screenshots
   - Steps to reproduce

---

## File Locations Reference

```
next_custom_app/
├── hooks.py  (line 74-85, 207-221)
├── next_custom_app/
│   ├── install.py
│   ├── utils/
│   │   ├── po_quantity_control.py  (NEW - 380 lines)
│   │   └── procurement_workflow.py  (MODIFIED)
│   └── doctype/
│       └── supplier_comparison/
│           ├── supplier_comparison.json
│           ├── supplier_comparison.py
│           └── [child tables...]
└── public/
    └── js/
        ├── rfq_comparison.js  (NEW - 335 lines)
        └── purchase_order_po_control.js  (NEW - 147 lines)
```

---

**Document Version**: 1.0  
**Last Updated**: January 5, 2026  
**For**: Production Deployment  
**Status**: ✅ Production Ready
