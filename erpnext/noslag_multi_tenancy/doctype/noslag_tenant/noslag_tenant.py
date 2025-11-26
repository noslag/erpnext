from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


DOMAIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-\.]+$")


STRIPE_ACTIVE_STATUSES = {"trialing", "active"}
STRIPE_PAST_DUE_STATUSES = {"past_due", "unpaid", "incomplete"}
STRIPE_CANCELED_STATUSES = {"canceled", "incomplete_expired"}


class NoSlagTenant(Document):
	"""Tracks SaaS tenants and orchestrates provisioning lifecycle."""

	def validate(self):
		self._normalize_names()
		self._validate_domain()
		self._sync_status_state()

	def _normalize_names(self):
		if self.tenant_name:
			self.tenant_name = self.tenant_name.strip()
		if self.site_name:
			self.site_name = self.site_name.strip().lower()

	def _validate_domain(self):
		if self.site_name and not DOMAIN_PATTERN.match(self.site_name):
			raise frappe.ValidationError(_("Site Name must contain only lowercase letters, digits, dashes, or dots."))
		if self.primary_domain and not DOMAIN_PATTERN.match(self.primary_domain.lower()):
			raise frappe.ValidationError(_("Primary Domain contains invalid characters."))

	def _sync_status_state(self):
		if self.status == "Active" and self.provisioning_state != "Ready":
			self.provisioning_state = "Ready"
		elif self.status == "Pending Activation" and self.provisioning_state == "Ready":
			self.status = "Active"

	def enqueue_provisioning(
		self,
		*,
		admin_password: str | None = None,
		mariadb_root_password: str | None = None,
		install_apps: Iterable[str] | None = None,
		fixtures: Iterable[str] | None = None,
	):
		from erpnext.noslag_multi_tenancy import provisioning

		return provisioning.enqueue_provisioning(
			self.name,
			admin_password=admin_password,
			mariadb_root_password=mariadb_root_password,
			install_apps=list(install_apps or []),
			fixtures=list(fixtures or []),
		)

	def append_provisioning_log(self, message: str):
		timestamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
		entry = f"[{timestamp}] {message.strip()}"
		log = (self.provisioning_log or "").splitlines()
		log.append(entry)
		self.db_set("provisioning_log", "\n".join(log), update_modified=False)

	def to_provisioning_payload(self) -> dict[str, str | int | None]:
		return {
			"tenant": self.name,
			"site_name": self.site_name,
			"primary_domain": self.primary_domain,
			"plan": self.plan,
			"status": self.status,
			"provisioning_state": self.provisioning_state,
			"queue_group": self.queue_group,
			"enforce_isolation": bool(self.enforce_isolation),
			"max_background_workers": self.max_background_workers,
		}

	def apply_stripe_subscription(
		self,
		*,
		customer_id: str | None = None,
		subscription_id: str | None = None,
		price_id: str | None = None,
		status: str | None = None,
		trial_end: int | None = None,
		email: str | None = None,
	):
		updates: dict[str, object] = {}
		if customer_id:
			updates["stripe_customer_id"] = customer_id
		if subscription_id:
			updates["stripe_subscription_id"] = subscription_id
			updates.setdefault("billing_subscription_id", subscription_id)
		if price_id:
			updates["stripe_price_id"] = price_id
		if email:
			updates["billing_email"] = email
		if trial_end:
			updates["trial_ends_on"] = getdate(datetime.fromtimestamp(trial_end, tz=timezone.utc))
		if status:
			updates["stripe_status"] = status
			if status in STRIPE_ACTIVE_STATUSES:
				updates["status"] = "Active"
			elif status in STRIPE_PAST_DUE_STATUSES:
				updates["status"] = "Suspended"
			elif status in STRIPE_CANCELED_STATUSES:
				updates["status"] = "Cancelled"
		if updates:
			self.db_set(updates)
			self.append_provisioning_log(f"Stripe subscription synced: {status or 'updated'}")
