import frappe


def execute():
	"""Ensure UTM Source DocType metadata lives in the ERPNext CRM module."""

	if not frappe.db.table_exists("DocType"):
		return

	frappe.reload_doc("crm", "doctype", "utm_source")

	if not frappe.db.exists("DocType", "UTM Source"):
		return

	update_values = {"module": "CRM"}

	if frappe.db.has_column("DocType", "app"):
		update_values["app"] = "erpnext"

	frappe.db.set_value("DocType", "UTM Source", update_values)
	frappe.clear_cache(doctype="UTM Source")
