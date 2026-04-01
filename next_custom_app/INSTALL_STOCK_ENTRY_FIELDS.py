#!/usr/bin/env python3
"""
CRITICAL: Install Stock Entry Custom Fields for Procurement Workflow
Run this immediately: bench --site [site_name] execute next_custom_app.INSTALL_STOCK_ENTRY_FIELDS.install_fields
"""

import frappe
from frappe import _

def install_fields():
	"""Install custom procurement fields for Stock Entry"""
	print("=" * 70)
	print("INSTALLING STOCK ENTRY PROCUREMENT CUSTOM FIELDS")
	print("=" * 70)
	
	try:
		# First, run the main setup
		from next_custom_app.next_custom_app.custom_fields import setup_all_custom_fields
		print("\n1. Running setup_all_custom_fields()...")
		result = setup_all_custom_fields()
		if result:
			print("   ✓ Custom fields setup completed")
		else:
			print("   ⚠ Custom fields setup had issues - check error log")
		
		# Clear cache
		print("\n2. Clearing cache...")
		frappe.clear_cache()
		print("   ✓ Cache cleared")
		
		# Verify installation
		print("\n3. Verifying installation...")
		meta = frappe.get_meta("Stock Entry")
		
		required_fields = [
			"procurement_section",
			"procurement_source_doctype",
			"procurement_source_name",
			"procurement_column_break",
			"procurement_links"
		]
		
		missing = []
		for field in required_fields:
			if meta.has_field(field):
				print(f"   ✓ {field}")
			else:
				print(f"   ✗ {field} MISSING")
				missing.append(field)
		
		# Check database columns
		print("\n4. Checking database columns...")
		db_fields = ["procurement_source_doctype", "procurement_source_name"]
		for field in db_fields:
			try:
				# Use the correct table name with space
				exists = frappe.db.sql(f"""
					SELECT COLUMN_NAME 
					FROM INFORMATION_SCHEMA.COLUMNS 
					WHERE TABLE_SCHEMA = DATABASE()
						AND TABLE_NAME = 'tabStock Entry'
						AND COLUMN_NAME = %s
				""", (field,))
				if exists:
					print(f"   ✓ DB Column: {field}")
				else:
					print(f"   ✗ DB Column: {field} MISSING - run migrate")
			except Exception as e:
				print(f"   ⚠ Cannot check {field}: {str(e)}")
		
		if missing and len(missing) < len(required_fields):
			print("\n⚠ WARNING: Some fields missing. Running field sync...")
			frappe.db.commit()
			
			# Try to sync fields
			try:
				frappe.get_doc("DocType", "Stock Entry").run_module_method("on_update")
				frappe.db.commit()
				print("   ✓ Field sync completed")
			except Exception as e:
				print(f"   ✗ Field sync failed: {str(e)}")
		
		print("\n" + "=" * 70)
		if not missing:
			print("✓ ALL FIELDS INSTALLED SUCCESSFULLY")
		else:
			print("⚠ INSTALLATION INCOMPLETE - Missing fields:")
			for field in missing:
				print(f"  - {field}")
			print("\nNext steps:")
			print("1. Run: bench --site [site] migrate")
			print("2. Run: bench --site [site] clear-cache")
			print("3. Re-run this script to verify")
		print("=" * 70)
		
		frappe.db.commit()
		
	except Exception as e:
		frappe.db.rollback()
		print(f"\n✗ ERROR: {str(e)}")
		import traceback
		traceback.print_exc()
		print("\nTroubleshooting:")
		print("1. Ensure app is installed: bench --site [site] install-app next_custom_app")
		print("2. Run migrate: bench --site [site] migrate")
		print("3. Clear cache: bench --site [site] clear-cache")
		print("4. Restart: bench restart")


if __name__ == "__main__":
	install_fields()
