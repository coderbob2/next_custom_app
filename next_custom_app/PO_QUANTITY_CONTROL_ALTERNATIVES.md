# Purchase Order Quantity Control: Alternative Solutions

## Problem Statement

**Challenge**: After creating an RFQ, multiple Supplier Quotations (SQ) can be created from different suppliers. Since we need to allow multiple quotations for the same items (for competitive bidding), we cannot restrict quantities at the SQ level. However, we must ensure that the total Purchase Order (PO) quantity does not exceed what was specified in the original RFQ.

**Flow**: RFQ → Multiple SQs (Supplier A, B, C) → POs (must be controlled)

---

## Alternative Solutions

### ✅ **Solution 1: Track Ordered Quantity at RFQ Item Level** (RECOMMENDED)

**Concept**: Add a custom field `ordered_qty` to RFQ items that accumulates as POs are created.

#### Implementation:

1. **Add Custom Fields to RFQ Items**:
   ```python
   # In Request for Quotation Item (child table)
   - ordered_qty (Float, default=0, read_only=1)
   - remaining_qty (Float, computed, read_only=1)
   ```

2. **Update ordered_qty when PO is Created/Cancelled**:
   ```python
   def on_submit_purchase_order(doc, method):
       """Update RFQ ordered quantities when PO is submitted"""
       if doc.procurement_source_doctype == "Supplier Quotation":
           sq = frappe.get_doc("Supplier Quotation", doc.procurement_source_name)
           if sq.procurement_source_doctype == "Request for Quotation":
               update_rfq_ordered_qty(sq.procurement_source_name, doc.items, action="add")
   
   def on_cancel_purchase_order(doc, method):
       """Reverse quantity update when PO is cancelled"""
       if doc.procurement_source_doctype == "Supplier Quotation":
           sq = frappe.get_doc("Supplier Quotation", doc.procurement_source_name)
           if sq.procurement_source_doctype == "Request for Quotation":
               update_rfq_ordered_qty(sq.procurement_source_name, doc.items, action="subtract")
   ```

3. **Validation Function**:
   ```python
   def validate_po_against_rfq(doc):
       """Validate PO quantities against RFQ limits"""
       if doc.procurement_source_doctype != "Supplier Quotation":
           return
       
       sq = frappe.get_doc("Supplier Quotation", doc.procurement_source_name)
       if sq.procurement_source_doctype != "Request for Quotation":
           return
       
       rfq = frappe.get_doc("Request for Quotation", sq.procurement_source_name)
       
       for po_item in doc.items:
           # Find matching RFQ item
           rfq_item = next((i for i in rfq.items if i.item_code == po_item.item_code), None)
           if not rfq_item:
               continue
           
           # Calculate total that would be ordered after this PO
           total_ordered = rfq_item.ordered_qty + po_item.qty
           
           if total_ordered > rfq_item.qty:
               frappe.throw(f"""
                   ❌ Quantity Exceeded for {po_item.item_code}
                   
                   RFQ: {rfq.name}
                   Requested Quantity: {rfq_item.qty}
                   Already Ordered: {rfq_item.ordered_qty}
                   This PO: {po_item.qty}
                   Total Would Be: {total_ordered}
                   
                   ⚠️ Exceeds by: {total_ordered - rfq_item.qty}
                   
                   💡 Available to order: {rfq_item.qty - rfq_item.ordered_qty}
               """)
   ```

#### Pros:
- ✅ Simple and transparent - users can see ordered_qty directly in RFQ
- ✅ Real-time tracking - always up-to-date
- ✅ Works with partial orders across multiple suppliers
- ✅ Easy to display in UI (remaining quantities)
- ✅ Handles PO cancellations automatically

#### Cons:
- ⚠️ Requires custom field addition to RFQ Item doctype
- ⚠️ Need to handle race conditions if multiple users create POs simultaneously

---

### ✅ **Solution 2: Real-time Calculation (No Custom Fields)**

**Concept**: When validating PO, query all existing POs linked to the same RFQ and calculate total ordered quantity dynamically.

#### Implementation:

```python
def validate_po_against_rfq_dynamic(doc):
    """Dynamically calculate ordered quantities from existing POs"""
    if doc.procurement_source_doctype != "Supplier Quotation":
        return
    
    sq = frappe.get_doc("Supplier Quotation", doc.procurement_source_name)
    if sq.procurement_source_doctype != "Request for Quotation":
        return
    
    rfq = frappe.get_doc("Request for Quotation", sq.procurement_source_name)
    
    # Get all SQs from this RFQ
    all_sqs = frappe.get_all("Supplier Quotation",
        filters={
            "procurement_source_doctype": "Request for Quotation",
            "procurement_source_name": rfq.name,
            "docstatus": 1
        },
        pluck="name"
    )
    
    # Get all existing POs from these SQs (excluding current if amending)
    existing_pos = frappe.get_all("Purchase Order",
        filters={
            "procurement_source_doctype": "Supplier Quotation",
            "procurement_source_name": ["in", all_sqs],
            "docstatus": ["!=", 2],  # Exclude cancelled
            "name": ["!=", doc.name] if doc.name else ""
        },
        fields=["name"]
    )
    
    # Calculate already ordered quantities by item
    ordered_qtys = {}
    for po_name in [po.name for po in existing_pos]:
        po = frappe.get_doc("Purchase Order", po_name)
        for item in po.items:
            ordered_qtys[item.item_code] = ordered_qtys.get(item.item_code, 0) + item.qty
    
    # Validate current PO items
    for po_item in doc.items:
        rfq_item = next((i for i in rfq.items if i.item_code == po_item.item_code), None)
        if not rfq_item:
            continue
        
        already_ordered = ordered_qtys.get(po_item.item_code, 0)
        total_would_be = already_ordered + po_item.qty
        
        if total_would_be > rfq_item.qty:
            frappe.throw(f"""
                ❌ Purchase Order Quantity Exceeds RFQ Limit
                
                Item: {po_item.item_code}
                RFQ: {rfq.name} (Quantity: {rfq_item.qty})
                
                Already Ordered: {already_ordered}
                This PO: {po_item.qty}
                Total: {total_would_be}
                
                ✅ Available: {rfq_item.qty - already_ordered}
            """)
```

#### Pros:
- ✅ No custom fields needed
- ✅ Always accurate (real-time calculation)
- ✅ No need to update stored values
- ✅ Works with existing doctypes

#### Cons:
- ⚠️ More database queries (performance impact at scale)
- ⚠️ Slightly slower validation
- ⚠️ Cannot easily show "remaining" quantities in UI

---

### ✅ **Solution 3: RFQ Status Management with Item-Level Locking**

**Concept**: Add item-level status to RFQ items (`Open`, `Partially Ordered`, `Fully Ordered`, `Closed`) and prevent further PO creation for fully ordered items.

#### Implementation:

1. **Add Custom Fields**:
   ```python
   # In Request for Quotation Item
   - order_status (Select: Open, Partially Ordered, Fully Ordered, Closed)
   - ordered_qty (Float)
   - allow_over_order (Check, default=0)
   ```

2. **Update Status on PO Submit/Cancel**:
   ```python
   def update_rfq_item_status(rfq_name, item_code, qty_change):
       """Update RFQ item status based on ordered quantity"""
       rfq = frappe.get_doc("Request for Quotation", rfq_name)
       
       for item in rfq.items:
           if item.item_code == item_code:
               item.ordered_qty = (item.ordered_qty or 0) + qty_change
               
               # Update status
               if item.ordered_qty >= item.qty:
                   item.order_status = "Fully Ordered"
               elif item.ordered_qty > 0:
                   item.order_status = "Partially Ordered"
               else:
                   item.order_status = "Open"
               
               break
       
       rfq.save(ignore_permissions=True)
   ```

3. **Validation with Status Check**:
   ```python
   def validate_against_rfq_status(doc):
       """Prevent ordering items that are fully ordered"""
       sq = frappe.get_doc("Supplier Quotation", doc.procurement_source_name)
       rfq = frappe.get_doc("Request for Quotation", sq.procurement_source_name)
       
       for po_item in doc.items:
           rfq_item = next((i for i in rfq.items if i.item_code == po_item.item_code), None)
           if not rfq_item:
               continue
           
           # Check status
           if rfq_item.order_status == "Fully Ordered" and not rfq_item.allow_over_order:
               frappe.throw(f"""
                   🔒 Item Already Fully Ordered
                   
                   Item: {po_item.item_code}
                   RFQ: {rfq.name}
                   Status: {rfq_item.order_status}
                   
                   This item has been fully ordered from the RFQ.
                   Please contact the procurement team if you need to order more.
               """)
           
           # Check quantity
           available = rfq_item.qty - (rfq_item.ordered_qty or 0)
           if po_item.qty > available:
               frappe.throw(f"""
                   ❌ Quantity Exceeds Available
                   
                   Item: {po_item.item_code}
                   Available: {available}
                   Requested: {po_item.qty}
               """)
   ```

#### Pros:
- ✅ Clear visual status for users
- ✅ Extra safety with status locking
- ✅ Can override with `allow_over_order` flag for emergencies
- ✅ Good for audit trail

#### Cons:
- ⚠️ More complex state management
- ⚠️ Requires custom fields
- ⚠️ Status can get out of sync if not handled carefully

---

### ✅ **Solution 4: Purchase Order Allocation/Reservation System**

**Concept**: When PO is saved (but not submitted), "reserve" quantities from RFQ. Only decrement on cancellation.

#### Implementation:

1. **Add Custom Fields**:
   ```python
   # In Request for Quotation Item
   - reserved_qty (Float, default=0)
   - ordered_qty (Float, default=0)
   ```

2. **Reserve on PO Save**:
   ```python
   def on_save_purchase_order(doc, method):
       """Reserve quantities when PO is saved"""
       if doc.docstatus == 0:  # Draft
           reserve_rfq_quantity(doc, action="reserve")
   
   def on_submit_purchase_order(doc, method):
       """Move reserved to ordered when submitted"""
       reserve_rfq_quantity(doc, action="submit")
   
   def on_cancel_purchase_order(doc, method):
       """Release reserved quantities when cancelled"""
       reserve_rfq_quantity(doc, action="cancel")
   ```

3. **Validation**:
   ```python
   def validate_with_reservation(doc):
       """Check both reserved and ordered quantities"""
       rfq = get_source_rfq(doc)
       
       for po_item in doc.items:
           rfq_item = find_rfq_item(rfq, po_item.item_code)
           
           # Calculate truly available (not reserved by others)
           available = rfq_item.qty - rfq_item.ordered_qty - rfq_item.reserved_qty
           
           if po_item.qty > available:
               frappe.throw(f"""
                   ⚠️ Quantity Not Available
                   
                   Item: {po_item.item_code}
                   Requested: {po_item.qty}
                   Available: {available}
                   
                   (Ordered: {rfq_item.ordered_qty}, Reserved by others: {rfq_item.reserved_qty})
               """)
   ```

#### Pros:
- ✅ Prevents race conditions (two users creating POs simultaneously)
- ✅ Reserves quantities during draft stage
- ✅ Most robust solution

#### Cons:
- ⚠️ Most complex to implement
- ⚠️ Need to handle abandoned drafts (cleanup job)
- ⚠️ Requires careful transaction management

---

### ✅ **Solution 5: Dual-Phase Approval with Quantity Manager**

**Concept**: Add an intermediate "PO Approval" step where procurement manager reviews all POs against RFQ before submission.

#### Implementation:

1. **Workflow**:
   ```
   RFQ → Multiple SQs → Multiple Draft POs → Procurement Manager Reviews → Approve Selected POs
   ```

2. **Custom Dashboard**:
   ```python
   def get_rfq_po_overview(rfq_name):
       """Dashboard showing all pending POs for an RFQ"""
       return {
           "rfq": rfq,
           "pending_pos": [list of draft POs],
           "total_quantities": {item: total_qty},
           "warnings": [items where total > rfq_qty]
       }
   ```

3. **Bulk Approval Function**:
   ```python
   def approve_pos_for_rfq(rfq_name, selected_pos):
       """Approve multiple POs ensuring total doesn't exceed RFQ"""
       validate_total_quantities(rfq_name, selected_pos)
       for po_name in selected_pos:
           po = frappe.get_doc("Purchase Order", po_name)
           po.submit()
   ```

#### Pros:
- ✅ Human oversight ensures correctness
- ✅ Manager can split orders across suppliers strategically
- ✅ Less technical complexity

#### Cons:
- ⚠️ Adds manual step (slower process)
- ⚠️ Requires manager availability
- ⚠️ Not fully automated

---

## 🏆 Recommended Approach

### **Hybrid: Solution 1 + Solution 2**

Combine real-time storage with dynamic validation for maximum reliability:

1. **Add `ordered_qty` to RFQ Item** (Solution 1) for UI display and quick checks
2. **Add dynamic validation** (Solution 2) as a safety net to catch any sync issues
3. **Update ordered_qty via hooks** when PO is submitted/cancelled

#### Why This Works Best:
- ✅ Fast validation (check stored value first)
- ✅ Safety net (dynamically recalculate if needed)
- ✅ User-friendly (shows remaining quantities in UI)
- ✅ Handles edge cases (race conditions, cancelled POs)
- ✅ Audit trail (see ordered_qty history)

---

## Implementation Priority

### Phase 1: Core Validation (Week 1)
1. Add `ordered_qty` custom field to RFQ Item
2. Implement validation function in `validate_po_against_rfq()`
3. Add hooks for PO submit/cancel to update ordered_qty

### Phase 2: UI Enhancement (Week 2)
4. Display remaining quantities in PO form
5. Add indicator in RFQ showing which items are fully/partially ordered
6. Create custom button "Create PO from RFQ" that pre-fills with available quantities

### Phase 3: Advanced Features (Week 3)
7. Add dashboard showing all POs per RFQ
8. Implement automatic RFQ item status updates
9. Add email notifications when RFQ items are fully ordered

---

## Code Implementation Guide

### File: `next_custom_app/next_custom_app/utils/po_quantity_control.py`

Create a new module with these functions:
1. `validate_po_against_rfq(doc)` - Main validation
2. `update_rfq_ordered_qty(rfq_name, items, action)` - Update stored quantities
3. `get_rfq_available_quantities(rfq_name)` - For UI display
4. `calculate_rfq_ordered_quantities(rfq_name)` - Dynamic calculation (fallback)

### File: `next_custom_app/hooks.py`

Add these hooks:
```python
doc_events = {
    "Purchase Order": {
        "validate": "next_custom_app.next_custom_app.utils.po_quantity_control.validate_po_against_rfq",
        "on_submit": "next_custom_app.next_custom_app.utils.po_quantity_control.on_submit",
        "on_cancel": "next_custom_app.next_custom_app.utils.po_quantity_control.on_cancel",
    }
}
```

### File: `next_custom_app/public/js/purchase_order.js`

Add client-side validation and UI enhancements:
```javascript
frappe.ui.form.on('Purchase Order', {
    refresh: function(frm) {
        if (frm.doc.procurement_source_doctype === "Supplier Quotation") {
            show_rfq_quantity_status(frm);
        }
    }
});
```

---

## Testing Strategy

### Test Case 1: Basic Validation
- Create RFQ with 100 units
- Create PO with 60 units → ✅ Success
- Create PO with 50 units → ❌ Fail (total 110)

### Test Case 2: Multiple Items
- RFQ with Item A (100), Item B (200)
- PO1 with A(50), B(100)
- PO2 with A(50), B(100)
- PO3 with A(10) → ❌ Fail (A exceeds)

### Test Case 3: Cancellation
- Create PO with 60 units → Ordered: 60
- Cancel PO → Ordered: 0
- Create new PO with 100 units → ✅ Success

### Test Case 4: Concurrent Creation
- Two users create PO simultaneously
- System should prevent double-allocation

---

## Database Migration

```python
# Migration script to add custom fields
def execute():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    
    custom_fields = {
        "Request for Quotation Item": [
            {
                "fieldname": "ordered_qty",
                "label": "Ordered Quantity",
                "fieldtype": "Float",
                "default": "0",
                "read_only": 1,
                "insert_after": "qty"
            },
            {
                "fieldname": "remaining_qty",
                "label": "Remaining Quantity",
                "fieldtype": "Float",
                "read_only": 1,
                "insert_after": "ordered_qty",
                "depends_on": "eval: doc.qty > 0",
                "description": "Calculated as: Qty - Ordered Qty"
            }
        ]
    }
    
    create_custom_fields(custom_fields)
```

---

## Questions to Consider

1. **Should partial orders be allowed?** 
   - Multiple POs for the same RFQ (yes, recommended)
   
2. **What happens to ordered_qty when PO is amended?**
   - Amendment should adjust quantities accordingly
   
3. **Should we allow over-ordering with approval?**
   - Add `allow_over_order` flag for emergency situations
   
4. **Time limit for creating POs from RFQ?**
   - Optional: Auto-close RFQ after X days

5. **What if RFQ quantity is increased after POs exist?**
   - Allow editing RFQ qty, but validate against ordered_qty

---

**Document Version**: 1.0  
**Date**: January 5, 2026  
**Author**: Nextcore Technologies
