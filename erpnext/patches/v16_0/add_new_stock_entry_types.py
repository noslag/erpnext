import frappe


def execute():
	for stock_entry_type in [
		"Receive from Customer",
		"Return Raw Material to Customer",
		"Subcontracting Delivery",
		"Subcontracting Return",
	]:
		if not frappe.db.exists("Stock Entry Type", stock_entry_type):
			doc = frappe.new_doc("Stock Entry Type")
			doc.purpose = stock_entry_type
			doc.is_standard = 1
			doc.insert(set_name=stock_entry_type, ignore_permissions=True)
