from __future__ import annotations

from datetime import datetime

import frappe
from frappe.model.document import Document


class EbayListing(Document):
	def mark_sync_success(self, payload: dict):
		self.db_set("raw_payload", frappe.as_json(payload))
		self.db_set("notes", None)
		self.db_set("last_synced_at", datetime.utcnow())

	def mark_sync_failure(self, error: str):
		self.db_set("notes", error)
