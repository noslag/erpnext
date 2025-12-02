from __future__ import annotations

from typing import Any, Callable, Iterable
from urllib.parse import urljoin

import requests

from .auth import EbayOAuthService
from .constants import DEFAULT_TIMEOUT, get_environment, normalize_scopes
from .exceptions import EbayAPIError
from .types import EbayCredentials, EbayToken, TokenResponse

TokenCallback = Callable[[EbayToken], None]


class EbayClient:
	"""Thin wrapper above the Sell REST API with automatic token refresh."""

	def __init__(
		self,
		credentials: EbayCredentials,
		oauth_service: EbayOAuthService,
		token: EbayToken | None = None,
		refresh_token: str | None = None,
		scopes: Iterable[str] | None = None,
		session: requests.Session | None = None,
		on_token_refreshed: TokenCallback | None = None,
		timeout: int = DEFAULT_TIMEOUT,
	):
		self.credentials = credentials
		self.oauth_service = oauth_service
		self.token = token
		self.refresh_token = refresh_token
		self.scopes = normalize_scopes(scopes)
		self.session = session or requests.Session()
		self.on_token_refreshed = on_token_refreshed
		self.timeout = timeout
		self.environment = get_environment(credentials.environment)

	def request(
		self,
		method: str,
		path: str,
		*,
		params: dict[str, Any] | None = None,
		json: Any | None = None,
		data: Any | None = None,
		headers: dict[str, str] | None = None,
		parse_json: bool = True,
	) -> Any:
		access_token = self._ensure_access_token()
		url = urljoin(self.environment.api_base + "/", path.lstrip("/"))
		req_headers = {"Authorization": f"Bearer {access_token}"}
		if json is not None and "Content-Type" not in (headers or {}):
			req_headers["Content-Type"] = "application/json"
		if headers:
			req_headers.update(headers)
		response = self.session.request(
			method,
			url,
			params=params,
			json=json,
			data=data,
			headers=req_headers,
			timeout=self.timeout,
		)
		if response.status_code >= 400:
			raise EbayAPIError(
				f"eBay API request failed: {response.status_code}",
				status=response.status_code,
				payload=self._maybe_json(response),
			)
		return self._maybe_json(response) if parse_json else response

	def get_orders(self, **params: Any) -> dict[str, Any]:
		return self.request("GET", "/sell/fulfillment/v1/order", params=params)

	def get_listings(self, **params: Any) -> dict[str, Any]:
		return self.request("GET", "/sell/inventory/v1/inventory_item", params=params)

	def _maybe_json(self, response: requests.Response) -> Any:
		try:
			return response.json()
		except ValueError:
			return response.text

	def _ensure_access_token(self) -> str:
		if self.token and not self.token.is_expired():
			return self.token.access_token
		if not self.refresh_token:
			raise EbayAPIError("No refresh token available for eBay API call")
		new_token = self._refresh_token()
		self.token = new_token
		if self.on_token_refreshed:
			self.on_token_refreshed(new_token)
		return new_token.access_token

	def _refresh_token(self) -> EbayToken:
		response: TokenResponse = self.oauth_service.refresh_user_token(
			self.refresh_token,
			scopes=self.scopes,
		)
		token = response.to_token()
		return token


def build_client_from_credentials(
	credentials: EbayCredentials,
	*,
	refresh_token: str | None,
	token: EbayToken | None,
	scopes: Iterable[str] | None = None,
	on_token_refreshed: TokenCallback | None = None,
) -> EbayClient:
	oauth_service = EbayOAuthService(credentials, default_scopes=scopes)
	return EbayClient(
		credentials=credentials,
		oauth_service=oauth_service,
		token=token,
		refresh_token=refresh_token,
		scopes=scopes,
		on_token_refreshed=on_token_refreshed,
	)
