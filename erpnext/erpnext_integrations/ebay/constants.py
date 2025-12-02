from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Sequence

DEFAULT_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class EbayEnvironment:
	"""Container describing the API endpoints for a given eBay environment."""

	key: str
	api_base: str
	identity_base: str
	authorize_base: str


_ENVIRONMENTS: Dict[str, EbayEnvironment] = {
	"production": EbayEnvironment(
		key="production",
		api_base="https://api.ebay.com",
		identity_base="https://api.ebay.com",
		authorize_base="https://auth.ebay.com",
	),
	"sandbox": EbayEnvironment(
		key="sandbox",
		api_base="https://api.sandbox.ebay.com",
		identity_base="https://api.sandbox.ebay.com",
		authorize_base="https://auth.sandbox.ebay.com",
	),
}

DEFAULT_SCOPES: Sequence[str] = (
	"https://api.ebay.com/oauth/api_scope",
	"https://api.ebay.com/oauth/api_scope/sell.fulfillment",
	"https://api.ebay.com/oauth/api_scope/sell.inventory",
)

ORDER_SCOPES: Sequence[str] = (
	"https://api.ebay.com/oauth/api_scope/sell.fulfillment",
)

LISTING_SCOPES: Sequence[str] = (
	"https://api.ebay.com/oauth/api_scope/sell.inventory",
	"https://api.ebay.com/oauth/api_scope/sell.marketing",
)


def normalize_scopes(scopes: Iterable[str] | None) -> list[str]:
	return [scope.strip() for scope in (scopes or DEFAULT_SCOPES) if scope and scope.strip()]


def get_environment(key: str | None) -> EbayEnvironment:
	if not key:
		return _ENVIRONMENTS["production"]
	try:
		return _ENVIRONMENTS[key.lower()]
	except KeyError as exc:  # pragma: no cover - defensive guard
		raise ValueError(f"Unsupported eBay environment: {key}") from exc
