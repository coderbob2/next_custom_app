# Payment Entry SSP Currency Exchange Rate Fix

## Problem Statement

When creating a Payment Entry from a Payment Request with SSP currency through the procurement workflow, the system was experiencing the following issues:

1. **Wrong paid_from account**: Using USD cash account instead of SSP cash account
2. **Missing target_exchange_rate**: Exchange rate showing as 0.000000
3. **No USD conversion**: Paid Amount (USD) showing as $0.00 instead of the converted amount

## Root Cause Analysis

### Issue 1: Wrong Cash Account Selection
**Location**: `next_custom_app/next_custom_app/utils/procurement_workflow.py:2266`

The `_set_reference_fields()` function was calling `_get_company_cash_account(company)` **without passing the currency parameter**. This caused it to always return the default USD cash account instead of the currency-specific SSP cash account.

```python
# BEFORE (Wrong):
paid_from_account = _get_company_cash_account(company)

# AFTER (Fixed):
paid_from_account = _get_company_cash_account(company, currency=currency)
```

### Issue 2: Exchange Rate Not Being Set
**Location**: Multiple locations in `payment_request_utils.py` and `payment_entry.js`

The exchange rates were not being properly calculated and set during Payment Entry creation. The system needs:

- **source_exchange_rate**: paid_from currency → company currency (SSP → USD = 0.000160000)
- **target_exchange_rate**: paid_to currency → paid_from currency (SSP → SSP = 1.0)

### Issue 3: Base Amount Not Calculated
ERPNext's Payment Entry calculates `base_paid_amount` (USD amount) using:
```
base_paid_amount = paid_amount * source_exchange_rate
```

For example:
- Paid Amount: 4,486,060.00 SSP
- Source Exchange Rate: 0.000160000 (SSP to USD)
- Base Paid Amount: 4,486,060.00 * 0.000160000 = 717.77 USD

## Solution Implemented

### 1. Enhanced `_get_company_cash_account()` Function
**File**: `next_custom_app/next_custom_app/utils/payment_request_utils.py`

Added currency parameter to find currency-specific cash accounts:

```python
def _get_company_cash_account(company, currency=None):
    """
    Resolve company cash account, optionally filtered by currency.
    
    If currency is provided and differs from company currency, try to find
    a currency-specific cash account. Otherwise, fall back to default.
    """
    if not company:
        return None

    # Get company currency
    company_currency = frappe.db.get_value("Company", company, "default_currency")
    
    # If currency is specified and differs from company currency, look for currency-specific account
    if currency and currency != company_currency:
        # Try to find a cash account with the specific currency
        currency_cash_account = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "account_type": "Cash",
                "account_currency": currency,
                "is_group": 0,
                "disabled": 0,
            },
            "name",
        )
        if currency_cash_account:
            return currency_cash_account
    
    # Fall back to default cash account
    default_cash_account = frappe.db.get_value(
        "Company", company, "default_cash_account"
    )
    if default_cash_account:
        return default_cash_account

    # Final fallback: any cash account for the company
    return frappe.db.get_value(
        "Account",
        {
            "company": company,
            "account_type": "Cash",
            "is_group": 0,
            "disabled": 0,
        },
        "name",
    )
```

### 2. Updated `_set_reference_fields()` in Procurement Workflow
**File**: `next_custom_app/next_custom_app/utils/procurement_workflow.py`

Modified to pass currency when getting cash account and set exchange rates immediately:

```python
# CRITICAL FIX: Pass currency to get currency-specific cash account (SSP cash for SSP payments)
paid_from_account = _get_company_cash_account(company, currency=currency)

# Set exchange rates immediately after accounts are set
if target_doc.get("paid_from_account_currency") and target_doc.get("paid_to_account_currency"):
    from next_custom_app.next_custom_app.utils.payment_request_utils import _set_payment_entry_exchange_rates
    _set_payment_entry_exchange_rates(target_doc, company=company)
```

### 3. Enhanced `_set_payment_entry_exchange_rates()` Function
**File**: `next_custom_app/next_custom_app/utils/payment_request_utils.py`

Improved to handle same-currency transfers and ensure proper rate calculation:

```python
def _set_payment_entry_exchange_rates(doc, company=None):
    """
    Set Payment Entry exchange rates and fail fast when required rates are missing.
    
    For SSP payments (or any non-company currency), this ensures:
    1. source_exchange_rate: paid_from currency -> company currency
    2. target_exchange_rate: paid_to currency -> paid_from currency
    """
    posting_date = doc.get("posting_date") or frappe.utils.today()
    paid_from_currency = doc.get("paid_from_account_currency")
    paid_to_currency = doc.get("paid_to_account_currency")

    company = company or doc.get("company")
    if not company and doc.get("paid_from"):
        company = frappe.db.get_value("Account", doc.get("paid_from"), "company")
    if not company and doc.get("paid_to"):
        company = frappe.db.get_value("Account", doc.get("paid_to"), "company")

    company_currency = None
    if company:
        company_currency = frappe.db.get_value("Company", company, "default_currency")

    # Source: paid_from -> company currency (ERPNext standard expectation)
    if paid_from_currency and company_currency:
        if paid_from_currency == company_currency:
            doc.source_exchange_rate = 1.0
        else:
            source_rate = _get_currency_exchange_rate(paid_from_currency, company_currency, posting_date)
            if source_rate is None:
                frappe.throw(
                    _("Currency Exchange rate not found for {0} to {1} on {2}.").format(
                        paid_from_currency,
                        company_currency,
                        posting_date or _("selected date"),
                    )
                )
            doc.source_exchange_rate = source_rate

    # Target: paid_to -> paid_from currency (what Payment Entry UI expects)
    if paid_to_currency and paid_from_currency:
        if paid_to_currency == paid_from_currency:
            doc.target_exchange_rate = 1.0
        else:
            target_rate = _get_currency_exchange_rate(paid_to_currency, paid_from_currency, posting_date)
            if target_rate is None:
                frappe.throw(
                    _("Currency Exchange rate not found for {0} to {1} on {2}.").format(
                        paid_to_currency,
                        paid_from_currency,
                        posting_date or _("selected date"),
                    )
                )
            doc.target_exchange_rate = target_rate
        return

    # Fallback when paid_from currency is unavailable: use company currency for target
    if paid_to_currency and company_currency:
        if paid_to_currency == company_currency:
            doc.target_exchange_rate = 1.0
        else:
            target_rate = _get_currency_exchange_rate(paid_to_currency, company_currency, posting_date)
            if target_rate is None:
                frappe.throw(
                    _("Currency Exchange rate not found for {0} to {1} on {2}.").format(
                        paid_to_currency,
                        company_currency,
                        posting_date or _("selected date"),
                    )
                )
            doc.target_exchange_rate = target_rate
```

### 4. Client-Side Exchange Rate Setting
**File**: `next_custom_app/public/js/payment_entry.js`

The client-side script already had logic to set exchange rates, which now works correctly with the server-side fixes.

## Expected Behavior After Fix

When creating a Payment Entry from a Payment Request with SSP currency:

1. **Account Paid From**: Mosses Yugu SSP - NC&GTP (SSP account)
2. **Account Paid To**: Abraham SSP - NC&GTP (SSP suspense account)
3. **Account Currency (From)**: SSP
4. **Account Currency (To)**: SSP
5. **Paid Amount (SSP)**: 4,486,060.00
6. **Received Amount (SSP)**: 4,486,060.00
7. **Source Exchange Rate**: 0.000160000 (SSP to USD)
8. **Target Exchange Rate**: 1.0 (SSP to SSP)
9. **Paid Amount (USD)**: 717.77 (calculated as 4,486,060.00 * 0.000160000)

## Testing Steps

1. Create a Payment Request with SSP currency
2. Click "Create" → "Payment Entry" from the Payment Request
3. Verify:
   - Both accounts are SSP accounts
   - Source exchange rate is correct (SSP to USD)
   - Target exchange rate is 1.0 (same currency)
   - Base amount (USD) is calculated correctly

## Files Modified

1. `next_custom_app/next_custom_app/utils/payment_request_utils.py`
   - Enhanced `_get_company_cash_account()` to support currency parameter
   - Improved `_set_payment_entry_exchange_rates()` for same-currency handling
   - Updated `on_payment_entry_validate()` to use currency-aware account selection

2. `next_custom_app/next_custom_app/utils/procurement_workflow.py`
   - Modified `_set_reference_fields()` to pass currency to `_get_company_cash_account()`
   - Added immediate exchange rate setting after account assignment

## Related Issues

- Payment Entry not getting target_exchange_rate when currency differs from company currency
- SSP payments using USD accounts instead of SSP accounts
- Amount not being converted to company currency (USD)

## Date
2026-04-30
