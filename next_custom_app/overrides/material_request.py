import frappe
from erpnext.stock.doctype.material_request.material_request import MaterialRequest


class MaterialRequestOverride(MaterialRequest):
	"""Override Material Request to customize behavior for procurement workflow."""
	pass
