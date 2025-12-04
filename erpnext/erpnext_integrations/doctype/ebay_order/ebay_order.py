from __future__ import annotations

from datetime import datetime

import frappe
from frappe.model.document import Document


class eBayOrder(Document):
	@frappe.whitelist()
	def sync_from_ebay(self):
		if not self.ebay_order_id:
			frappe.throw("eBay Order ID is required to sync")

		settings = frappe.get_single("eBay Settings")
		client = settings.build_client()

		try:
			order = client.get_order(self.ebay_order_id)
			self.update_from_order(order)
			self.mark_sync_success(order)
			self.save()
			frappe.msgprint("Synced successfully")
		except Exception as e:
			self.mark_sync_failure(str(e))
			frappe.msgprint(f"Sync failed: {str(e)}")

	def update_from_order(self, order: dict):
		payment_status = order.get("orderPaymentStatus")
		fulfillment_status = order.get("orderFulfillmentStatus")
		cancel_status = order.get("cancelStatus", {}).get("cancelState")

		# Map eBay status to ERPNext Select options:
		# New, PartiallyFulfilled, Completed, Cancelled, OnHold, Failed
		
		if cancel_status in ["CANCELED_BY_BUYER", "CANCELED_BY_SELLER"]:
			self.order_status = "Cancelled"
		elif fulfillment_status == "FULFILLED":
			self.order_status = "Completed"
		elif fulfillment_status == "IN_PROGRESS":
			self.order_status = "PartiallyFulfilled"
		elif payment_status == "PAID":
			self.order_status = "New"
		elif payment_status == "FAILED":
			self.order_status = "Failed"
		else:
			self.order_status = "OnHold" # Default for NOT_PAID or other states

		self.buyer_username = order.get("buyer", {}).get("username")
		self.buyer_email = order.get("buyer", {}).get("email") # Added email
		
		pricing = order.get("pricingSummary", {})
		total = pricing.get("total", {})
		self.order_total = total.get("value")
		self.currency = total.get("currency")

		# Sync Line Items
		self.items = []
		for line_item in order.get("lineItems", []):
			item = self.append("items", {})
			item.sku = line_item.get("sku")
			item.title = line_item.get("title")
			item.quantity = line_item.get("quantity")
			
			cost = line_item.get("lineItemCost", {})
			item.price = cost.get("value")
			
			# Image handling
			image_data = line_item.get("image", {})
			image_url = image_data.get("imageUrl")
			
			if image_url:
				item.image_url = image_url
				item.image_html = f'<img src="{image_url}" style="max-height: 100px; max-width: 100px; object-fit: contain;" />'

	def mark_sync_success(self, payload: dict, *, change_token: str | None = None):
		self.db_set("raw_payload", frappe.as_json(payload))
		self.db_set("last_error", None)
		self.db_set("last_synced_at", datetime.utcnow())
		if change_token:
			self.db_set("change_token", change_token)

	def mark_sync_failure(self, error: str):
		self.db_set("last_error", error)
