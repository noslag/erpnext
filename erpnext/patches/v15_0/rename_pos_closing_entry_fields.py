import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	if frappe.db.has_column("POS Closing Entry", "pos_transactions"):
		rename_field("POS Closing Entry", "pos_transactions", "pos_invoices")

	if (
		frappe.db.exists("DocType", "Sales Invoice Reference")
		and frappe.db.has_column("POS Closing Entry", "sales_invoice_transactions")
	):
		rename_field("POS Closing Entry", "sales_invoice_transactions", "sales_invoices")
