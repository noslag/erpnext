from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable

import frappe
from frappe import _

from .doctype.noslag_tenant.noslag_tenant import NoSlagTenant

logger = logging.getLogger(__name__)

try:
	import stripe
except ModuleNotFoundError:  # pragma: no cover - stripe is an optional dependency
	stripe = None  # type: ignore


ACTIVE_WEBHOOK_EVENTS = {
	"checkout.session.completed",
	"customer.subscription.created",
	"customer.subscription.updated",
	"customer.subscription.deleted",
}


def _require_stripe_dependency():
	if stripe is None:
		raise frappe.ValidationError(_("Stripe python package missing. Install 'stripe' to enable billing webhooks."))


def _init_stripe_api():
	_require_stripe_dependency()
	api_key = frappe.conf.get("noslag_stripe_secret_key") or frappe.conf.get("stripe_secret")
	if not api_key:
		raise frappe.ValidationError(_("Set noslag_stripe_secret_key in site_config.json to process Stripe events."))
	stripe.api_key = api_key
	return api_key


def _get_webhook_secret():
	secret = frappe.conf.get("noslag_stripe_webhook_secret")
	if not secret:
		raise frappe.ValidationError(_("Set noslag_stripe_webhook_secret in site_config.json to verify Stripe webhooks."))
	return secret


def _slugify(value: str) -> str:
	return re.sub(r"[^a-z0-9-]", "-", value.lower()).strip("-") or "tenant"


def _parse_list(value: str | None) -> list[str]:
	if not value:
		return []
	value = value.strip()
	if not value:
		return []
	if value.startswith("["):
		try:
			parsed = json.loads(value)
			if isinstance(parsed, list):
				return [str(item).strip() for item in parsed if str(item).strip()]
		except Exception:  # noqa: BLE001
			logger.warning("Invalid JSON metadata list: %s", value)
	return [item.strip() for item in value.split(",") if item.strip()]


def _find_tenant_by(field: str, value: str | None) -> NoSlagTenant | None:
	if not value:
		return None
	name = frappe.db.get_value("NoSlag Tenant", {field: value})
	return frappe.get_doc("NoSlag Tenant", name) if name else None


def _ensure_tenant(metadata: dict[str, Any]) -> NoSlagTenant:
	tenant_name = metadata.get("tenant_name")
	if not tenant_name:
		raise frappe.ValidationError("Stripe metadata missing tenant_name.")
	site_name = metadata.get("site_name") or _slugify(tenant_name)
	tenant = _find_tenant_by("site_name", site_name)
	if tenant:
		return tenant

	doc = frappe.get_doc(
		{
			"doctype": "NoSlag Tenant",
			"tenant_name": tenant_name,
			"site_name": site_name,
			"primary_domain": metadata.get("primary_domain"),
			"plan": metadata.get("plan") or "Growth",
			"billing_customer": metadata.get("billing_customer"),
		}
	).insert(ignore_permissions=True)
	logger.info("Created tenant %s via Stripe checkout metadata", doc.name)
	return doc


def _queue_provisioning(doc: NoSlagTenant, metadata: dict[str, Any]):
	install_apps = _parse_list(metadata.get("install_apps"))
	fixtures = _parse_list(metadata.get("fixtures"))
	doc.enqueue_provisioning(
		admin_password=metadata.get("admin_password"),
		mariadb_root_password=metadata.get("mariadb_root_password"),
		install_apps=install_apps,
		fixtures=fixtures,
	)


def _extract_price_id(obj: dict[str, Any]) -> str | None:
	if "items" in obj:
		items = obj.get("items", {}).get("data", [])
		if items:
			return items[0].get("price", {}).get("id")
	return None


def _apply_checkout_details(doc: NoSlagTenant, session: dict[str, Any]):
	customer_email = (session.get("customer_details") or {}).get("email")
	updates: dict[str, Any] = {}
	if customer_email:
		updates["billing_email"] = customer_email
	if portal_url := (session.get("metadata") or {}).get("billing_portal_url"):
		updates["billing_portal_url"] = portal_url
	if updates:
		doc.db_set(updates)


def _handle_checkout_session(payload: dict[str, Any]):
	metadata = payload.get("metadata") or {}
	doc = _ensure_tenant(metadata)
	queued = False
	if doc.provisioning_state in {"Ready", "Provisioning"}:
		logger.info("Tenant %s already provisioned/in progress; skipping queue", doc.name)
	else:
		_queue_provisioning(doc, metadata)
		doc.append_provisioning_log("Stripe checkout completed; provisioning queued.")
		queued = True
	doc.apply_stripe_subscription(
		customer_id=payload.get("customer"),
		subscription_id=payload.get("subscription"),
		price_id=metadata.get("price_id"),
		email=(payload.get("customer_details") or {}).get("email"),
	)
	_apply_checkout_details(doc, payload)
	if not queued:
		doc.append_provisioning_log("Stripe checkout acknowledged.")


def _handle_subscription_event(payload: dict[str, Any], *, deleted: bool = False):
	subscription_id = payload.get("id")
	doc = _find_tenant_by("stripe_subscription_id", subscription_id)
	if not doc:
		doc = _find_tenant_by("stripe_customer_id", payload.get("customer"))
	if not doc:
		logger.warning("Stripe subscription %s not mapped to any tenant", subscription_id)
		return
	doc.apply_stripe_subscription(
		customer_id=payload.get("customer"),
		subscription_id=subscription_id,
		price_id=_extract_price_id(payload),
		status="canceled" if deleted else payload.get("status"),
		trial_end=payload.get("trial_end"),
	)


@frappe.whitelist(allow_guest=True)
def handle_stripe_webhook():
	"""Entry point for Stripe webhook events (Checkout + Subscription lifecycle)."""

	_init_stripe_api()
	secret = _get_webhook_secret()
	payload = frappe.request.get_data()
	signature = frappe.get_request_header("Stripe-Signature")
	if not signature:
		raise frappe.PermissionError("Missing Stripe-Signature header")
	try:
		event = stripe.Webhook.construct_event(payload, signature, secret)
	except ValueError as exc:  # invalid payload
		logger.exception("Stripe webhook payload error")
		raise frappe.ValidationError(f"Invalid payload: {exc}") from exc
	except stripe.error.SignatureVerificationError as exc:
		logger.exception("Stripe webhook signature verification failed")
		raise frappe.PermissionError("Invalid Stripe signature") from exc

	event_type = event.get("type")
	obj = event.get("data", {}).get("object", {})
	if event_type not in ACTIVE_WEBHOOK_EVENTS:
		logger.info("Ignoring Stripe event %s", event_type)
		return {"received": True}

	logger.info("Processing Stripe event %s", event_type)
	if event_type == "checkout.session.completed":
		_handle_checkout_session(obj)
	elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
		_handle_subscription_event(obj)
	elif event_type == "customer.subscription.deleted":
		_handle_subscription_event(obj, deleted=True)

	return {"received": True}
