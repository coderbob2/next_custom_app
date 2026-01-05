app_name = "next_custom_app"
app_title = "Next Custom App"
app_publisher = "Nextcore Technologies"
app_description = "Next Custom App for custom requirements"
app_email = "info@nextcoretechnologies.com"
app_license = "mit"
# Fixtures
# --------
# Doctype fixtures ensure correct import order (child tables first)
fixtures = [
	{
		"dt": "DocType",
		"filters": [
			["name", "in", [
				"Purchase Requisition Item",
				"Purchase Requisition",
				"Procurement Document Link",
				"Procurement Flow Steps",
				"Procurement Rule Set",
				"Procurement Flow",
				"RFQ Supplier Rule"
			]]
		]
	},
	{
		"dt": "Workspace",
		"filters": [
			["name", "in", ["Procurement Workflow"]]
		]
	}
]


# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "next_custom_app",
# 		"logo": "/assets/next_custom_app/logo.png",
# 		"title": "Next Custom App",
# 		"route": "/next_custom_app",
# 		"has_permission": "next_custom_app.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = ["/assets/next_custom_app/css/procurement_workflow.css"]
# Removed global procurement_workflow.js to prevent duplicate event handlers
# procurement_custom_tabs.js is loaded per-doctype and handles all functionality
# app_include_js = ["/assets/next_custom_app/js/procurement_workflow.js"]

# include js, css files in header of web template
# web_include_css = "/assets/next_custom_app/css/next_custom_app.css"
# web_include_js = "/assets/next_custom_app/js/next_custom_app.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "next_custom_app/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Material Request": "public/js/procurement_custom_tabs.js",
	"Purchase Requisition": "public/js/procurement_custom_tabs.js",
	"Request for Quotation": [
		"public/js/procurement_custom_tabs.js",
		"public/js/rfq_pivot_view.js",
		"public/js/rfq_comparison.js"
	],
	"Supplier Quotation": "public/js/procurement_custom_tabs.js",
	"Purchase Order": [
		"public/js/procurement_custom_tabs.js",
		"public/js/purchase_order_po_control.js"
	],
	"Purchase Receipt": "public/js/procurement_custom_tabs.js",
	"Purchase Invoice": "public/js/procurement_custom_tabs.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "next_custom_app/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "next_custom_app.utils.jinja_methods",
# 	"filters": "next_custom_app.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "next_custom_app.install.before_install"
after_install = "next_custom_app.next_custom_app.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "next_custom_app.uninstall.before_uninstall"
# after_uninstall = "next_custom_app.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "next_custom_app.utils.before_app_install"
# after_app_install = "next_custom_app.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "next_custom_app.utils.before_app_uninstall"
# after_app_uninstall = "next_custom_app.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "next_custom_app.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Material Request": {
		"validate": "next_custom_app.next_custom_app.utils.procurement_workflow.validate_procurement_document",
		"on_submit": "next_custom_app.next_custom_app.utils.procurement_workflow.on_procurement_submit",
		"before_cancel": "next_custom_app.next_custom_app.utils.procurement_workflow.check_can_cancel"
	},
	"Purchase Requisition": {
		"validate": "next_custom_app.next_custom_app.utils.procurement_workflow.validate_procurement_document",
		"on_submit": "next_custom_app.next_custom_app.utils.procurement_workflow.on_procurement_submit",
		"before_cancel": "next_custom_app.next_custom_app.utils.procurement_workflow.check_can_cancel"
	},
	"Request for Quotation": {
		"validate": [
			"next_custom_app.next_custom_app.utils.procurement_workflow.validate_procurement_document",
			"next_custom_app.next_custom_app.doctype.rfq_supplier_rule.rfq_supplier_rule.validate_rfq_on_submit"
		],
		"on_submit": "next_custom_app.next_custom_app.utils.procurement_workflow.on_procurement_submit",
		"before_cancel": "next_custom_app.next_custom_app.utils.procurement_workflow.check_can_cancel"
	},
	"Supplier Quotation": {
		"validate": "next_custom_app.next_custom_app.utils.procurement_workflow.validate_procurement_document",
		"on_submit": "next_custom_app.next_custom_app.utils.procurement_workflow.on_procurement_submit",
		"before_cancel": "next_custom_app.next_custom_app.utils.procurement_workflow.check_can_cancel"
	},
	"Purchase Order": {
		"validate": [
			"next_custom_app.next_custom_app.utils.procurement_workflow.validate_procurement_document",
			"next_custom_app.next_custom_app.utils.po_quantity_control.on_po_validate"
		],
		"on_submit": [
			"next_custom_app.next_custom_app.utils.procurement_workflow.on_procurement_submit",
			"next_custom_app.next_custom_app.utils.po_quantity_control.on_po_submit"
		],
		"on_cancel": "next_custom_app.next_custom_app.utils.po_quantity_control.on_po_cancel",
		"before_cancel": "next_custom_app.next_custom_app.utils.procurement_workflow.check_can_cancel"
	},
	"Purchase Receipt": {
		"validate": "next_custom_app.next_custom_app.utils.procurement_workflow.validate_procurement_document",
		"on_submit": "next_custom_app.next_custom_app.utils.procurement_workflow.on_procurement_submit",
		"before_cancel": "next_custom_app.next_custom_app.utils.procurement_workflow.check_can_cancel"
	},
	"Purchase Invoice": {
		"validate": "next_custom_app.next_custom_app.utils.procurement_workflow.validate_procurement_document",
		"on_submit": "next_custom_app.next_custom_app.utils.procurement_workflow.on_procurement_submit",
		"before_cancel": "next_custom_app.next_custom_app.utils.procurement_workflow.check_can_cancel"
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"next_custom_app.tasks.all"
# 	],
# 	"daily": [
# 		"next_custom_app.tasks.daily"
# 	],
# 	"hourly": [
# 		"next_custom_app.tasks.hourly"
# 	],
# 	"weekly": [
# 		"next_custom_app.tasks.weekly"
# 	],
# 	"monthly": [
# 		"next_custom_app.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "next_custom_app.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "next_custom_app.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "next_custom_app.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["next_custom_app.utils.before_request"]
# after_request = ["next_custom_app.utils.after_request"]

# Job Events
# ----------
# before_job = ["next_custom_app.utils.before_job"]
# after_job = ["next_custom_app.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"next_custom_app.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

