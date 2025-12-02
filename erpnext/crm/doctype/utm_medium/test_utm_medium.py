import frappe
from frappe.tests import IntegrationTestCase


class TestUTMMedium(IntegrationTestCase):
	def tearDown(self):
		frappe.delete_doc("UTM Medium", "_Test UTM Medium", ignore_missing=True)

	def test_can_create_medium_record(self):
		if frappe.db.exists("UTM Medium", "_Test UTM Medium"):
			frappe.delete_doc("UTM Medium", "_Test UTM Medium", ignore_missing=True)

		doc = frappe.get_doc(
			{
				"doctype": "UTM Medium",
				"name": "_Test UTM Medium",
				"description": "Automated test medium",
			}
		).insert(ignore_permissions=True)

		self.assertEqual(doc.description, "Automated test medium")
		self.assertTrue(frappe.db.exists("UTM Medium", "_Test UTM Medium"))
