from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import frappe
from frappe import _

logger = logging.getLogger(__name__)


EVENT_TOKEN_KEY = "noslag_sendgrid_event_token"
INBOUND_TOKEN_KEY = "noslag_sendgrid_inbound_token"
SENDGRID_API_KEY = "noslag_sendgrid_api_key"
SENDGRID_DEFAULT_FROM = "noslag_sendgrid_default_from"


def _require_secret(key: str) -> str:
	value = frappe.conf.get(key)
	if not value:
		raise frappe.ValidationError(_(f"Set {key} in site_config.json to use SendGrid features."))
	return value


def _validate_token(expected_key: str):
	request_token = frappe.form_dict.get("token") or frappe.get_request_header("X-NoSlag-SendGrid-Token")
	expected = _require_secret(expected_key)
	if not request_token or request_token != expected:
		raise frappe.PermissionError("Invalid SendGrid webhook token")


def ensure_sendgrid_email_account(
	*,
	email_id: str | None = None,
	display_name: str | None = None,
	incoming: bool = False,
	default_outgoing: bool = True,
	default_incoming: bool = False,
) -> str:
	"""Create or update an Email Account configured for SendGrid SMTP.

	Uses credentials stored in site_config: username always "apikey" and password from `noslag_sendgrid_api_key`.
	"""

	api_key = _require_secret(SENDGRID_API_KEY)
	email_id = email_id or _require_secret(SENDGRID_DEFAULT_FROM)
	name = f"SendGrid - {email_id}"

	account = frappe.get_doc({
		"doctype": "Email Account",
		"email_id": email_id,
		"display_name": display_name or "NoSlag",
		"incoming_server": "imap.sendgrid.net",
		"incoming_port": 993,
		"incoming_use_ssl": 1,
		"enable_incoming": int(incoming),
		"default_incoming": int(default_incoming and incoming),
		"smtp_server": "smtp.sendgrid.net",
		"smtp_port": 587,
		"use_tls": 1,
		"login_id": "apikey",
		"password": api_key,
		"enable_outgoing": 1,
		"default_outgoing": int(default_outgoing),
		"add_signature": 0,
	})

	account.name = name
	if frappe.db.exists("Email Account", name):
		existing = frappe.get_doc("Email Account", name)
		for field, value in account.as_dict().items():
			setattr(existing, field, value)
		existing.save(ignore_permissions=True)
	else:
		account.insert(ignore_permissions=True)

	logger.info("SendGrid Email Account ensured: %s", name)
	return name


def _link_communication(custom_args: dict[str, Any]) -> str | None:
	comm_name = custom_args.get("communication") or custom_args.get("comm_id")
	if comm_name and frappe.db.exists("Communication", comm_name):
		return comm_name
	return None


def _link_tenant(custom_args: dict[str, Any]) -> str | None:
	tenant_name = custom_args.get("tenant") or custom_args.get("tenant_name")
	if tenant_name and frappe.db.exists("NoSlag Tenant", tenant_name):
		return tenant_name
	return None


def _log_email_event(event: dict[str, Any]):
	custom_args = event.get("custom_args") or {}
	timestamp = event.get("timestamp")
	ts = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else None
	communication = _link_communication(custom_args)
	tenant = _link_tenant(custom_args)

	doc = frappe.get_doc(
		{
			"doctype": "NoSlag Email Event",
			"event_type": event.get("event"),
			"email": event.get("email"),
			"status": event.get("event"),
			"reason": event.get("reason"),
			"timestamp": ts,
			"communication": communication,
			"tenant": tenant,
			"payload": json.dumps(event, default=str),
		}
	)
	doc.insert(ignore_permissions=True)

	if communication and event.get("event") in {"bounce", "dropped", "spamreport"}:
		frappe.db.set_value("Communication", communication, "delivery_status", "Error")


@frappe.whitelist(allow_guest=True)
def handle_sendgrid_event():
	"""Webhook endpoint for SendGrid Event Webhook (delivery, bounce, spam, etc.)."""

	_validate_token(EVENT_TOKEN_KEY)
	if frappe.request.content_type != "application/json":
		raise frappe.ValidationError("SendGrid events must be JSON")
	payload = frappe.request.get_json()
	if isinstance(payload, dict):
		events = [payload]
	elif isinstance(payload, list):
		events = payload
	else:
		raise frappe.ValidationError("Invalid SendGrid payload")

	for event in events:
		try:
			_log_email_event(event)
		except Exception:  # noqa: BLE001
			logger.exception("Failed to log SendGrid event")

	return {"received": True, "count": len(events)}


def _create_inbound_communication(mail: dict[str, Any]):
	from frappe.email.inbound import InboundMail

	parser = InboundMail(mail)
	parser.process()


@frappe.whitelist(allow_guest=True)
def handle_sendgrid_inbound():
	"""Endpoint for SendGrid Inbound Parse webhook (support replies)."""

	_validate_token(INBOUND_TOKEN_KEY)
	mail = frappe.form_dict.copy()
	if not mail:
		raise frappe.ValidationError("Empty inbound payload")
	_create_inbound_communication(mail)
	frappe.db.insert(
		{
			"doctype": "NoSlag Email Event",
			"event_type": "inbound",
			"email": mail.get("from"),
			"status": "received",
			"payload": json.dumps(mail, default=str),
		}
	)
	return {"received": True}
