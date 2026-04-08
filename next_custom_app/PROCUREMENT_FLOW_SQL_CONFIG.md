# Procurement Flow SQL Configuration

This document contains the SQL statements to set up the Procurement Flow configuration
on a fresh ERPNext instance with the `next_custom_app` installed.

## Prerequisites

1. The `next_custom_app` must be installed and migrated (`bench --site <site> migrate`)
2. The `Procurement Flow` and `Procurement Flow Steps` doctypes must exist
3. Run `bench --site <site> execute next_custom_app.next_custom_app.custom_fields.setup_all_custom_fields` to create custom fields

## Expected Workflow

```
Step 1: Material Request
    ├── Step 2: Purchase Requisition (if item not available → purchase path)
    │       └── Step 3: Request for Quotation
    │               └── Step 4: Supplier Quotation
    │                       └── Step 5: Purchase Order
    │                               ├── Step 6 [receipt]: Purchase Receipt
    │                               │       └── Step 7 [receipt]: Purchase Invoice
    │                               │               └── Step 8: Stock Entry (final)
    │                               └── Step 6 [payment]: Payment Request
    │                                       └── Step 7 [payment]: Payment Entry
    │                                               └── Step 8: Stock Entry (final)
    └── Step 2: Stock Entry (if item available → direct issue/transfer, final)
```

## SQL Statements

### Step 1: Delete existing flow (if re-configuring)

```sql
-- WARNING: This will delete the existing flow and all its steps.
-- Only run this if you want to start fresh.
DELETE FROM `tabProcurement Flow Steps` WHERE parent = 'Purchase Control';
DELETE FROM `tabProcurement Flow` WHERE name = 'Purchase Control';
```

### Step 2: Create the Procurement Flow

```sql
INSERT INTO `tabProcurement Flow` (
    name, creation, modified, modified_by, owner,
    docstatus, flow_name, is_active
) VALUES (
    'Purchase Control',
    NOW(), NOW(), 'Administrator', 'Administrator',
    0, 'Purchase Control', 1
);
```

### Step 3: Create the Flow Steps

```sql
-- Step 1: Material Request (starting point, no source required)
INSERT INTO `tabProcurement Flow Steps` (
    name, parent, parenttype, parentfield, idx,
    step_no, doctype_name, requires_source, is_final_step, step_group
) VALUES (
    CONCAT('step_', SUBSTRING(MD5(RAND()), 1, 10)),
    'Purchase Control', 'Procurement Flow', 'flow_steps', 1,
    1, 'Material Request', 0, 0, NULL
);

-- Step 2a: Purchase Requisition (from Material Request, purchase path)
INSERT INTO `tabProcurement Flow Steps` (
    name, parent, parenttype, parentfield, idx,
    step_no, doctype_name, requires_source, is_final_step, step_group
) VALUES (
    CONCAT('step_', SUBSTRING(MD5(RAND()), 1, 10)),
    'Purchase Control', 'Procurement Flow', 'flow_steps', 2,
    2, 'Purchase Requisition', 1, 0, NULL
);

-- Step 2b: Stock Entry (from Material Request, direct issue/transfer if available)
INSERT INTO `tabProcurement Flow Steps` (
    name, parent, parenttype, parentfield, idx,
    step_no, doctype_name, requires_source, is_final_step, step_group
) VALUES (
    CONCAT('step_', SUBSTRING(MD5(RAND()), 1, 10)),
    'Purchase Control', 'Procurement Flow', 'flow_steps', 3,
    2, 'Stock Entry', 1, 1, NULL
);

-- Step 3: Request for Quotation (from Purchase Requisition)
INSERT INTO `tabProcurement Flow Steps` (
    name, parent, parenttype, parentfield, idx,
    step_no, doctype_name, requires_source, is_final_step, step_group
) VALUES (
    CONCAT('step_', SUBSTRING(MD5(RAND()), 1, 10)),
    'Purchase Control', 'Procurement Flow', 'flow_steps', 4,
    3, 'Request for Quotation', 1, 0, NULL
);

-- Step 4: Supplier Quotation (from RFQ)
INSERT INTO `tabProcurement Flow Steps` (
    name, parent, parenttype, parentfield, idx,
    step_no, doctype_name, requires_source, is_final_step, step_group
) VALUES (
    CONCAT('step_', SUBSTRING(MD5(RAND()), 1, 10)),
    'Purchase Control', 'Procurement Flow', 'flow_steps', 5,
    4, 'Supplier Quotation', 1, 0, NULL
);

-- Step 5: Purchase Order (from Supplier Quotation)
INSERT INTO `tabProcurement Flow Steps` (
    name, parent, parenttype, parentfield, idx,
    step_no, doctype_name, requires_source, is_final_step, step_group
) VALUES (
    CONCAT('step_', SUBSTRING(MD5(RAND()), 1, 10)),
    'Purchase Control', 'Procurement Flow', 'flow_steps', 6,
    5, 'Purchase Order', 1, 0, NULL
);

-- Step 6a: Purchase Receipt (from Purchase Order, receipt branch)
INSERT INTO `tabProcurement Flow Steps` (
    name, parent, parenttype, parentfield, idx,
    step_no, doctype_name, requires_source, is_final_step, step_group
) VALUES (
    CONCAT('step_', SUBSTRING(MD5(RAND()), 1, 10)),
    'Purchase Control', 'Procurement Flow', 'flow_steps', 7,
    6, 'Purchase Receipt', 1, 0, 'receipt'
);

-- Step 6b: Payment Request (from Purchase Order, payment branch)
INSERT INTO `tabProcurement Flow Steps` (
    name, parent, parenttype, parentfield, idx,
    step_no, doctype_name, requires_source, is_final_step, step_group
) VALUES (
    CONCAT('step_', SUBSTRING(MD5(RAND()), 1, 10)),
    'Purchase Control', 'Procurement Flow', 'flow_steps', 8,
    6, 'Payment Request', 1, 0, 'payment'
);

-- Step 7a: Payment Entry (from Payment Request, payment branch)
-- requires_source=0 because Payment Entry can come from various sources
INSERT INTO `tabProcurement Flow Steps` (
    name, parent, parenttype, parentfield, idx,
    step_no, doctype_name, requires_source, is_final_step, step_group
) VALUES (
    CONCAT('step_', SUBSTRING(MD5(RAND()), 1, 10)),
    'Purchase Control', 'Procurement Flow', 'flow_steps', 9,
    7, 'Payment Entry', 0, 0, 'payment'
);

-- Step 7b: Purchase Invoice (from Purchase Receipt, receipt branch)
INSERT INTO `tabProcurement Flow Steps` (
    name, parent, parenttype, parentfield, idx,
    step_no, doctype_name, requires_source, is_final_step, step_group
) VALUES (
    CONCAT('step_', SUBSTRING(MD5(RAND()), 1, 10)),
    'Purchase Control', 'Procurement Flow', 'flow_steps', 10,
    7, 'Purchase Invoice', 1, 0, 'receipt'
);

-- Step 8: Stock Entry (final step, from Purchase Invoice or Payment Entry)
INSERT INTO `tabProcurement Flow Steps` (
    name, parent, parenttype, parentfield, idx,
    step_no, doctype_name, requires_source, is_final_step, step_group
) VALUES (
    CONCAT('step_', SUBSTRING(MD5(RAND()), 1, 10)),
    'Purchase Control', 'Procurement Flow', 'flow_steps', 11,
    8, 'Stock Entry', 1, 1, NULL
);
```

### Step 4: Backfill existing Payment Requests (optional)

If you have existing Payment Requests that were created before the `procurement_source_doctype`
and `procurement_source_name` fields were added, run this to backfill them:

```sql
-- Backfill Payment Request procurement_source from reference fields
UPDATE `tabPayment Request`
SET procurement_source_doctype = reference_doctype,
    procurement_source_name = reference_name
WHERE reference_doctype IS NOT NULL
  AND reference_name IS NOT NULL
  AND (procurement_source_doctype IS NULL OR procurement_source_doctype = '');

-- Backfill Payment Entry procurement_source from reference_no (Payment Request name)
UPDATE `tabPayment Entry` pe
INNER JOIN `tabPayment Request` pr ON pr.name = pe.reference_no
SET pe.procurement_source_doctype = 'Payment Request',
    pe.procurement_source_name = pe.reference_no
WHERE pe.reference_no IS NOT NULL
  AND (pe.procurement_source_doctype IS NULL OR pe.procurement_source_doctype = '');
```

### Step 5: Create backward links for existing submitted documents (optional)

Run this via bench console to create backward links for existing submitted Payment Requests
and Payment Entries:

```python
# Run via: bench --site <site> console
import frappe

# Create backward links: Purchase Order -> Payment Request
prs = frappe.db.sql("""
    SELECT name, procurement_source_doctype, procurement_source_name
    FROM `tabPayment Request`
    WHERE docstatus = 1
      AND procurement_source_doctype IS NOT NULL
      AND procurement_source_name IS NOT NULL
""", as_dict=1)

for pr in prs:
    exists = frappe.db.exists("Procurement Document Link", {
        "parent": pr.procurement_source_name,
        "target_doctype": "Payment Request",
        "target_docname": pr.name
    })
    if not exists:
        count = frappe.db.count("Procurement Document Link", {"parent": pr.procurement_source_name})
        frappe.db.sql("""
            INSERT INTO `tabProcurement Document Link`
            (name, parent, parenttype, parentfield, idx,
             source_doctype, source_docname, target_doctype, target_docname, link_date)
            VALUES (%s, %s, %s, 'procurement_links', %s,
                    %s, %s, 'Payment Request', %s, NOW())
        """, (
            frappe.generate_hash(length=10),
            pr.procurement_source_name,
            pr.procurement_source_doctype,
            count + 1,
            pr.procurement_source_doctype,
            pr.procurement_source_name,
            pr.name
        ))
        print(f"  Created link: {pr.procurement_source_name} -> Payment Request/{pr.name}")

# Create backward links: Payment Request -> Payment Entry
pes = frappe.db.sql("""
    SELECT name, procurement_source_doctype, procurement_source_name
    FROM `tabPayment Entry`
    WHERE docstatus = 1
      AND procurement_source_doctype = 'Payment Request'
      AND procurement_source_name IS NOT NULL
""", as_dict=1)

for pe in pes:
    exists = frappe.db.exists("Procurement Document Link", {
        "parent": pe.procurement_source_name,
        "target_doctype": "Payment Entry",
        "target_docname": pe.name
    })
    if not exists:
        count = frappe.db.count("Procurement Document Link", {"parent": pe.procurement_source_name})
        frappe.db.sql("""
            INSERT INTO `tabProcurement Document Link`
            (name, parent, parenttype, parentfield, idx,
             source_doctype, source_docname, target_doctype, target_docname, link_date)
            VALUES (%s, %s, 'Payment Request', 'procurement_links', %s,
                    'Payment Request', %s, 'Payment Entry', %s, NOW())
        """, (
            frappe.generate_hash(length=10),
            pe.procurement_source_name,
            count + 1,
            pe.procurement_source_name,
            pe.name
        ))
        print(f"  Created link: {pe.procurement_source_name} -> Payment Entry/{pe.name}")

frappe.db.commit()
print("Done!")
```

## Verification

After running the SQL, verify the configuration:

```sql
-- Check the flow
SELECT name, flow_name, is_active FROM `tabProcurement Flow`;

-- Check the steps
SELECT step_no, doctype_name, requires_source, is_final_step, step_group
FROM `tabProcurement Flow Steps`
WHERE parent = 'Purchase Control'
ORDER BY step_no, doctype_name;
```

Expected output:

| step_no | doctype_name           | requires_source | is_final_step | step_group |
|---------|------------------------|-----------------|---------------|------------|
| 1       | Material Request       | 0               | 0             | NULL       |
| 2       | Purchase Requisition   | 1               | 0             | NULL       |
| 2       | Stock Entry            | 1               | 1             | NULL       |
| 3       | Request for Quotation  | 1               | 0             | NULL       |
| 4       | Supplier Quotation     | 1               | 0             | NULL       |
| 5       | Purchase Order         | 1               | 0             | NULL       |
| 6       | Payment Request        | 1               | 0             | payment    |
| 6       | Purchase Receipt       | 1               | 0             | receipt    |
| 7       | Payment Entry          | 0               | 0             | payment    |
| 7       | Purchase Invoice       | 1               | 0             | receipt    |
| 8       | Stock Entry            | 1               | 1             | NULL       |

## Step Group Explanation

The `step_group` field controls which "Create" buttons appear on each document:

- **No group** (NULL): All next-step doctypes are shown as create buttons
- **`receipt` group**: Purchase Receipt → Purchase Invoice (receipt processing branch)
- **`payment` group**: Payment Request → Payment Entry (payment processing branch)

This ensures:
- From **Purchase Order** (no group): Shows both "Create Purchase Receipt" and "Create Payment Request"
- From **Purchase Receipt** (receipt group): Shows only "Create Purchase Invoice"
- From **Payment Request** (payment group): Shows only "Create Payment Entry"
- From **Purchase Invoice** (receipt group): Shows "Create Stock Entry" (final step has no group)
- From **Payment Entry** (payment group): Shows "Create Stock Entry" (final step has no group)
