"""
CRITICAL FIX: Install Stock Entry Custom Fields
Run: bench --site [site] execute next_custom_app.fix_stock_entry_fields.fix_now
"""

import frappe


def fix_now():
	"""Install/fix custom fields for Stock Entry immediately"""
	print("\n" + "="*70)
	print("CRITICAL FIX: Installing Stock Entry Custom Fields")
	print("="*70 + "\n")
	
	try:
		# Step 1: Check current state
		print("Step 1: Checking current state...")
		meta = frappe.get_meta("Stock Entry", cached=False)
		
		fields_status = {}
		for field in ["procurement_source_doctype", "procurement_source_name", "procurement_links"]:
			exists = meta.has_field(field)
			fields_status[field] = exists
			status = "✓" if exists else "✗"
			print(f"  {status} {field}: {exists}")
		
		# Step 2: Install custom fields
		print("\nStep 2: Installing custom fields...")
		from next_custom_app.next_custom_app.custom_fields import setup_all_custom_fields
		setup_all_custom_fields()
		
		# Step 3: Clear cache
		print("\nStep 3: Clearing cache...")
		frappe.clear_cache(doctype="Stock Entry")
		frappe.clear_cache()
		
		# Step 4: Reload metadata
		print("\nStep 4: Reloading metadata...")
		frappe.reload_doctype("Stock Entry")
		meta = frappe.get_meta("Stock Entry", cached=False)
		
		# Step 5: Check if columns exist in database
		print("\nStep 5: Checking database columns...")
		for field in ["procurement_source_doctype", "procurement_source_name"]:
			result = frappe.db.sql(f"""
				SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
				FROM INFORMATION_SCHEMA.COLUMNS 
				WHERE TABLE_SCHEMA = DATABASE()
					AND TABLE_NAME = 'tabStock Entry'
					AND COLUMN_NAME = %s
			""", (field,), as_dict=True)
			
			if result:
				print(f"  ✓ {field}: EXISTS ({result[0].DATA_TYPE})")
			else:
				print(f"  ✗ {field}: MISSING - needs migrate")
		
		# Step 6: Verify final state
		print("\nStep 6: Final verification...")
		all_good = True
		meta = frappe.get_meta("Stock Entry", cached=False)
		for field in ["procurement_source_doctype", "procurement_source_name"]:
			if not meta.has_field(field):
				print(f"  ✗ {field} still missing")
				all_good = False
			else:
				print(f"  ✓ {field} installed")
		
		print("\n" + "="*70)
		if all_good:
			print("✓ SUCCESS: All fields installed")
			print("\nNext steps:")
			print("1. Run: bench --site [site] migrate")
			print("2. Run: bench restart")
			print("3. Test Stock Entry creation from Material Request")
		else:
			print("⚠ PARTIAL: Fields added to meta but may need migrate")
			print("\nRequired steps:")
			print("1. Run: bench --site [site] migrate (REQUIRED)")
			print("2. Run: bench --site [site] clear-cache")
			print("3. Run: bench restart")
			print("4. Re-run this script to verify")
		print("="*70 + "\n")
		
		frappe.db.commit()
		return True
		
	except Exception as e:
		frappe.db.rollback()
		print(f"\n✗ ERROR: {str(e)}")
		import traceback
		traceback.print_exc()
		print("\nManual fix required:")
		print("1. Go to: Setup → Customize Form → Stock Entry")
		print("2. Add these custom fields manually:")
		print("   - procurement_source_doctype (Link → DocType)")
		print("   - procurement_source_name (Dynamic Link → procurement_source_doctype)")
		print("   - procurement_links (Table → Procurement Document Link)")
		print("3. Save and run: bench --site [site] migrate")
		return False


if __name__ == "__main__":
	fix_now()
