from __future__ import annotations

from datetime import datetime, timedelta, timezone

import frappe

from .exceptions import EbayAPIError


logger = frappe.logger("ebay_sync")

SYNC_TYPE_ORDER = "order"
SYNC_TYPE_LISTING = "listing"


def sync_orders(*, since: datetime | None = None, limit: int = 200) -> dict:
	"""Pull orders updated since the provided timestamp and return the API payload."""
	settings = frappe.get_single("eBay Settings")
	if not _connector_ready(settings):
		return {}
	client = settings.build_client()
	since = since or _default_since(settings.order_sync_window_hours)
	params = {
		"limit": min(limit, 200),
		"offset": 0,
	}
	if since:
		params["filter"] = f"lastmodifieddate:[{since.strftime('%Y-%m-%dT%H:%M:%SZ')}..]"
	log = _create_sync_log(SYNC_TYPE_ORDER, reference=None, parameters=params)
	try:
		payload = client.get_orders(**params)
		_update_sync_log(log, status="Success", response=payload)
		settings.db_set("last_order_sync_at", datetime.now(timezone.utc))
		return payload
	except EbayAPIError as exc:
		_update_sync_log(log, status="Failed", response=exc.as_dict())
		raise



def sync_listings(*, since: datetime | None = None, limit: int = 200) -> dict:
	settings = frappe.get_single("eBay Settings")
	if not _connector_ready(settings):
		return {}
	client = settings.build_client()
	since = since or _default_since(settings.listing_sync_window_hours)
	params = {
		"limit": min(limit, 200),
		"offset": 0,
	}
	if since:
		params["q"] = f"lastmodifieddate:[{since.strftime('%Y-%m-%dT%H:%M:%SZ')}..]"
	log = _create_sync_log(SYNC_TYPE_LISTING, reference=None, parameters=params)
	try:
		payload = client.get_listings(**params)
		_update_sync_log(log, status="Success", response=payload)
		settings.db_set("last_listing_sync_at", datetime.now(timezone.utc))
		return payload
	except EbayAPIError as exc:
		_update_sync_log(log, status="Failed", response=exc.as_dict())
		raise


def _default_since(hours: int | None) -> datetime | None:
	if not hours:
		return None
	return datetime.now(timezone.utc) - timedelta(hours=hours)


def _create_sync_log(sync_type: str, reference: str | None, parameters: dict | None):
	log_doc = frappe.get_doc(
		{
			"doctype": "eBay Sync Log",
			"sync_type": sync_type,
			"status": "Queued",
			"request_payload": frappe.as_json(parameters or {}),
		}
	)
	log_doc.insert(ignore_permissions=True)
	return log_doc


def _update_sync_log(log_doc, *, status: str, response: dict | None):
	log_doc.db_set("status", status)
	if response is not None:
		log_doc.db_set("response_payload", frappe.as_json(response))


def _connector_ready(settings) -> bool:
	if not settings.enabled:
		logger.info("Skipping eBay sync: connector disabled on %s", frappe.local.site)
		return False
	if not settings.refresh_token:
		logger.info("Skipping eBay sync: missing refresh token on %s", frappe.local.site)
		return False
	return True
