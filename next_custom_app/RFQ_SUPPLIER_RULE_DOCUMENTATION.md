# RFQ Supplier Rule Documentation

## Overview

The **RFQ Supplier Rule** system enforces minimum supplier requirements for Request for Quotations (RFQs) based on the total purchase amount. This ensures compliance with procurement policies that require a specific number of competitive quotations for different value ranges.

**Version**: 1.0  
**Date**: November 28, 2025  
**Author**: Nextcore Technologies

---

## Table of Contents

1. [Purpose](#purpose)
2. [Features](#features)
3. [DocType Structure](#doctype-structure)
4. [Business Logic](#business-logic)
5. [Usage Guide](#usage-guide)
6. [Validation Rules](#validation-rules)
7. [API Reference](#api-reference)
8. [Installation](#installation)
9. [Examples](#examples)
10. [Troubleshooting](#troubleshooting)

---

## Purpose

### Business Need

Organizations often have procurement policies that require:
- **Small purchases**: 2 quotations
- **Medium purchases**: 3 quotations
- **Large purchases**: 5 quotations

This system automates the enforcement of these requirements based on the RFQ's total amount.

### Benefits

✅ **Compliance**: Automatically enforces procurement policies  
✅ **Transparency**: Clear rules visible to all users  
✅ **Flexibility**: Different rules for different amount ranges  
✅ **Validation**: Prevents submission of non-compliant RFQs  
✅ **Auditability**: Track which rules apply to which RFQs

---

## Features

### 1. Amount-Based Rules
- Define minimum suppliers required for specific amount ranges
- Example: $0-$10,000 requires 2 suppliers, $10,000-$50,000 requires 3 suppliers

### 2. Overlap Detection
- System prevents creating rules with overlapping amount ranges
- Shows detailed error message with conflicting rules
- Ensures clear, unambiguous rule application

### 3. Priority System
- When ranges could overlap, priority determines which rule applies
- Lower priority number = higher priority
- Useful for special cases or temporary rules

### 4. Active/Inactive Status
- Rules can be activated or deactivated
- Inactive rules don't apply to RFQs
- Allows temporary rule suspension without deletion

### 5. Real-Time Validation
- Validates supplier count when RFQ is saved/submitted
- Shows clear error messages with rule details
- Prevents non-compliant submissions

---

## DocType Structure

### Fields

#### Basic Information
| Field | Type | Description |
|-------|------|-------------|
| [`rule_name`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.json:13) | Data | Unique name for the rule (used as document name) |
| [`is_active`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.json:19) | Check | Whether this rule is currently active |
| [`priority`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.json:57) | Int | Priority for overlapping ranges (lower = higher priority) |

#### Amount Range
| Field | Type | Description |
|-------|------|-------------|
| [`amount_from`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.json:26) | Currency | Starting amount of the range (inclusive) |
| [`amount_to`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.json:32) | Currency | Ending amount of the range (exclusive) |

#### Requirements
| Field | Type | Description |
|-------|------|-------------|
| [`min_suppliers`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.json:38) | Int | Minimum number of suppliers required |

#### Documentation
| Field | Type | Description |
|-------|------|-------------|
| [`description`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.json:44) | Text | Optional description of the rule |

### Permissions

| Role | Read | Write | Create | Delete |
|------|------|-------|--------|--------|
| System Manager | ✅ | ✅ | ✅ | ✅ |
| Purchase Manager | ✅ | ✅ | ✅ | ✅ |
| Purchase User | ✅ | ❌ | ❌ | ❌ |

---

## Business Logic

### Rule Application Algorithm

```python
1. Calculate RFQ total amount = Sum of (item.rate × item.qty) for all items
2. Find all active rules where:
   - rule.amount_from <= total_amount < rule.amount_to
3. If multiple rules match:
   - Select rule with lowest priority number (highest priority)
4. If rule found:
   - Count suppliers in RFQ
   - If supplier_count < rule.min_suppliers:
     - Block submission with detailed error
5. If no rule found:
   - Allow submission (no restrictions)
```

### Validation Sequence

#### On Save (RFQ Supplier Rule)
1. **[`validate_amount_range()`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.py:16)**: Ensure amount_from < amount_to
2. **[`validate_min_suppliers()`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.py:30)**: Ensure min_suppliers >= 1
3. **[`validate_no_overlaps()`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.py:38)**: Check for overlapping ranges with other active rules

#### On Save/Submit (RFQ)
1. **[`validate_rfq_on_submit()`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.py:203)**: Validate supplier count against applicable rule
2. **[`get_applicable_rule()`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.py:110)**: Find the matching rule for the RFQ amount
3. Compare supplier count vs. required count
4. Block if insufficient suppliers

---

## Usage Guide

### Creating RFQ Supplier Rules

#### Step 1: Navigate to RFQ Supplier Rule List
```
Home → Procurement → RFQ Supplier Rule → New
```

#### Step 2: Fill in Rule Details

**Example: Small Purchase Rule**
```
Rule Name: Small Purchases
Is Active: ✅
Priority: 10
Amount From: 0.00
Amount To: 10,000.00
Minimum Suppliers: 2
Description: Small purchases require 2 competitive quotes
```

**Example: Medium Purchase Rule**
```
Rule Name: Medium Purchases
Is Active: ✅
Priority: 20
Amount From: 10,000.00
Amount To: 50,000.00
Minimum Suppliers: 3
Description: Medium purchases require 3 competitive quotes
```

**Example: Large Purchase Rule**
```
Rule Name: Large Purchases
Is Active: ✅
Priority: 30
Amount From: 50,000.00
Amount To: 999,999,999.00
Minimum Suppliers: 5
Description: Large purchases require 5 competitive quotes
```

#### Step 3: Save
- System validates for overlaps
- If overlap detected, shows error with conflicting rules
- Adjust ranges or priorities as needed

### Using Rules with RFQs

#### Creating an RFQ

1. **Create RFQ** with items and rates
2. **Add suppliers** to the RFQ
3. **Save** or **Submit**
4. System automatically:
   - Calculates total amount
   - Finds applicable rule
   - Validates supplier count
   - Shows error if insufficient suppliers

#### Error Handling

If validation fails, you'll see:

```
┌─────────────────────────────────────────────────┐
│ Minimum Supplier Requirement Not Met            │
├─────────────────────────────────────────────────┤
│ This RFQ requires at least 3 suppliers but      │
│ only 2 selected.                                │
│                                                  │
│ Total Amount:        $25,000.00                 │
│ Applicable Rule:     Medium Purchases           │
│ Amount Range:        $10,000.00 - $50,000.00    │
│ Required Suppliers:  3                          │
│ Current Suppliers:   2                          │
│                                                  │
│ Please add at least 1 more supplier(s).        │
└─────────────────────────────────────────────────┘
```

**Solution**: Add more suppliers to meet the requirement.

---

## Validation Rules

### 1. Amount Range Validation

**Rule**: `amount_from` must be less than `amount_to`

**Example Error**:
```
Invalid Amount Range
Amount From ($50,000.00) must be less than Amount To ($10,000.00)
```

**Fix**: Ensure the "from" amount is smaller than the "to" amount.

### 2. Minimum Suppliers Validation

**Rule**: `min_suppliers` must be at least 1

**Example Error**:
```
Invalid Minimum Suppliers
Minimum Suppliers must be at least 1
```

**Fix**: Set minimum suppliers to 1 or more.

### 3. Overlap Detection

**Rule**: Active rules cannot have overlapping amount ranges

**Example Error**:
```
┌─────────────────────────────────────────────────────────┐
│ Overlapping Amount Ranges                                │
├─────────────────────────────────────────────────────────┤
│ This rule's range overlaps with:                        │
│                                                          │
│ Rule Name         Amount Range            Min Suppliers │
│ Small Purchases  $0.00 - $10,000.00              2      │
│ Medium Purchases $10,000.00 - $50,000.00         3      │
│                                                          │
│ Your Range: $5,000.00 - $15,000.00                      │
│                                                          │
│ Please adjust the range to avoid overlaps.             │
└─────────────────────────────────────────────────────────┘
```

**Fix Options**:
1. Adjust amount ranges to not overlap
2. Deactivate one of the conflicting rules
3. Ensure ranges are contiguous: [0-10k], [10k-50k], [50k-∞]

### 4. RFQ Supplier Count Validation

**Rule**: RFQ must have at least the minimum required suppliers

**Triggered**: When saving/submitting an RFQ

**Example Error**: (Shown above in "Error Handling" section)

**Fix**: Add more suppliers to the RFQ

---

## API Reference

### Python Functions

#### `get_applicable_rule(total_amount)`
**Location**: [`rfq_supplier_rule.py`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.py:110)

**Purpose**: Find the applicable rule for a given amount

**Parameters**:
- `total_amount` (float): Total RFQ amount

**Returns**:
```python
{
    "name": "RFQ-RULE-001",
    "rule_name": "Medium Purchases",
    "amount_from": 10000.00,
    "amount_to": 50000.00,
    "min_suppliers": 3,
    "priority": 20
}
```
Or `None` if no rule applies.

**Usage**:
```python
from next_custom_app.next_custom_app.doctype.rfq_supplier_rule.rfq_supplier_rule import get_applicable_rule

rule = get_applicable_rule(25000.00)
if rule:
    print(f"Minimum suppliers required: {rule['min_suppliers']}")
```

#### `validate_rfq_suppliers(doctype, docname)`
**Location**: [`rfq_supplier_rule.py`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.py:154)

**Purpose**: Validate if an RFQ meets supplier requirements

**Parameters**:
- `doctype` (str): Document type (should be "Request for Quotation")
- `docname` (str): Document name

**Returns**:
```python
{
    "valid": False,
    "message": "This RFQ requires at least 3 suppliers...",
    "total_amount": 25000.00,
    "required_suppliers": 3,
    "current_suppliers": 2,
    "rule_name": "Medium Purchases"
}
```

**Usage**:
```python
from next_custom_app.next_custom_app.doctype.rfq_supplier_rule.rfq_supplier_rule import validate_rfq_suppliers

result = validate_rfq_suppliers("Request for Quotation", "RFQ-00001")
if not result["valid"]:
    print(result["message"])
```

#### `validate_rfq_on_submit(doc, method=None)`
**Location**: [`rfq_supplier_rule.py`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.py:203)

**Purpose**: Hook function called automatically when RFQ is validated

**Parameters**:
- `doc` (Document): RFQ Document object
- `method` (str): Method name (optional)

**Raises**: `frappe.ValidationError` if supplier count is insufficient

**Usage**: Automatically called via hooks, no manual invocation needed.

---

## Installation

### Step 1: Install the App
```bash
bench get-app next_custom_app
bench --site your-site.local install-app next_custom_app
```

### Step 2: Migrate Database
```bash
bench --site your-site.local migrate
```

### Step 3: Build Assets
```bash
bench build --app next_custom_app
```

### Step 4: Restart
```bash
bench restart
```

### Step 5: Verify Installation
1. Navigate to **Procurement** module
2. Look for **RFQ Supplier Rule** in the list
3. Create a test rule
4. Create a test RFQ and verify validation works

---

## Examples

### Example 1: Standard Procurement Policy

**Scenario**: Company policy requires:
- Under $10k: 2 quotes
- $10k-$100k: 3 quotes
- Over $100k: 5 quotes

**Implementation**:

**Rule 1: Small Purchases**
```
Rule Name: Small Purchases
Amount From: 0.00
Amount To: 10,000.00
Min Suppliers: 2
Priority: 10
Is Active: Yes
```

**Rule 2: Medium Purchases**
```
Rule Name: Medium Purchases
Amount From: 10,000.00
Amount To: 100,000.00
Min Suppliers: 3
Priority: 20
Is Active: Yes
```

**Rule 3: Large Purchases**
```
Rule Name: Large Purchases
Amount From: 100,000.00
Amount To: 999,999,999.00
Min Suppliers: 5
Priority: 30
Is Active: Yes
```

### Example 2: Temporary Exception Rule

**Scenario**: During vendor shortage, temporarily reduce requirements for $20k-$30k range

**Implementation**:

**Temporary Rule**
```
Rule Name: Temporary COVID Relief
Amount From: 20,000.00
Amount To: 30,000.00
Min Suppliers: 2
Priority: 1  ← High priority to override Medium Purchases
Is Active: Yes
Description: Temporary reduction due to vendor availability
```

When crisis ends, simply deactivate this rule.

### Example 3: Testing Different Amounts

**Create test RFQ with different amounts**:

| Items Total | Applicable Rule | Required Suppliers |
|-------------|-----------------|-------------------|
| $5,000 | Small Purchases | 2 |
| $25,000 | Medium Purchases | 3 |
| $150,000 | Large Purchases | 5 |

---

## Troubleshooting

### Issue: Rule Not Applying

**Symptoms**: RFQ allows submission even though rule should apply

**Checklist**:
1. ✅ Is the rule active? Check `is_active` field
2. ✅ Does the RFQ total fall within the range?
3. ✅ Are item rates filled in? (Total is calculated from rates)
4. ✅ Check browser console for errors
5. ✅ Verify hook is registered in [`hooks.py`](next_custom_app/hooks.py:188)

**Debug**:
```python
# In Frappe console
from next_custom_app.next_custom_app.doctype.rfq_supplier_rule.rfq_supplier_rule import get_applicable_rule

# Check what rule applies for amount
rule = get_applicable_rule(25000.00)
print(rule)
```

### Issue: Overlap Error When None Exists

**Symptoms**: Getting overlap error but ranges don't seem to overlap

**Cause**: Ranges use `<` comparison, not `<=`

**Example**:
- Rule A: 0 - 10,000 ✅ Covers [0, 10000)
- Rule B: 10,000 - 50,000 ✅ Covers [10000, 50000)
- These DON'T overlap! 10,000 is exact boundary

**But**:
- Rule A: 0 - 10,001 ❌ Covers [0, 10001)
- Rule B: 10,000 - 50,000 ❌ Covers [10000, 50000)
- These DO overlap! [10000, 10001) is in both

**Fix**: Use exact boundaries without overlap:
```
Rule A: amount_to = 10000.00
Rule B: amount_from = 10000.00
```

### Issue: Validation Not Blocking Submission

**Symptoms**: RFQ submits even with insufficient suppliers

**Checklist**:
1. ✅ Clear cache: `bench clear-cache`
2. ✅ Rebuild: `bench build --app next_custom_app`
3. ✅ Restart: `bench restart`
4. ✅ Check error log for exceptions
5. ✅ Verify hook is called (add debug print statements)

**Check Hook Registration**:
```python
# In hooks.py
doc_events = {
    "Request for Quotation": {
        "validate": [
            "next_custom_app.next_custom_app.utils.procurement_workflow.validate_procurement_document",
            "next_custom_app.next_custom_app.doctype.rfq_supplier_rule.rfq_supplier_rule.validate_rfq_on_submit"
        ],
        ...
    }
}
```

---

## Files Created/Modified

### New Files
1. [`next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.json`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.json) - DocType definition
2. [`next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.py`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/rfq_supplier_rule.py) - Python controller with validation logic
3. [`next_custom_app/next_custom_app/doctype/rfq_supplier_rule/__init__.py`](next_custom_app/next_custom_app/doctype/rfq_supplier_rule/__init__.py) - Module initialization
4. [`next_custom_app/RFQ_SUPPLIER_RULE_DOCUMENTATION.md`](next_custom_app/RFQ_SUPPLIER_RULE_DOCUMENTATION.md) - This documentation

### Modified Files
1. [`next_custom_app/hooks.py`](next_custom_app/hooks.py) - Added RFQ validation hook and fixture

---

## Future Enhancements

### Planned Features
1. **Email Notifications**: Alert procurement team when rules are bypassed
2. **Approval Workflow**: Allow managers to approve exceptions
3. **Analytics Dashboard**: Track rule compliance rates
4. **Supplier Category Rules**: Different rules for different supplier categories
5. **Time-Based Rules**: Different requirements during specific periods
6. **Multi-Currency Support**: Handle different currencies in rules

---

## Support

### Reporting Issues
- **Email**: info@nextcoretechnologies.com
- **Documentation**: See related files in `/next_custom_app/` directory

### Contributing
Pull requests welcome! Please:
1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Ensure all validations pass

---

## Version History

### Version 1.0 (November 28, 2025)
- ✅ Initial implementation
- ✅ Amount-based supplier requirements
- ✅ Overlap detection and prevention
- ✅ Priority system for overlapping ranges
- ✅ Active/inactive status control
- ✅ Real-time validation on RFQ save/submit
- ✅ Detailed error messages with styling
- ✅ API functions for rule application
- ✅ Comprehensive documentation

---

**Document Version**: 1.0  
**Last Updated**: November 28, 2025  
**Maintained By**: Nextcore Technologies  
**License**: MIT