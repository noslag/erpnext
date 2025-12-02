from __future__ import annotations

from typing import Iterable

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.erpnext_integrations.ebay.auth import EbayOAuthService
from erpnext.erpnext_integrations.ebay.constants import DEFAULT_SCOPES
from erpnext.erpnext_integrations.ebay.exceptions import EbayConfigurationError
from erpnext.erpnext_integrations.ebay.types import EbayCredentials, EbayToken


def _get_common_credentials() -> dict:
	conf = getattr(frappe.local, "conf", None) or {}
	return conf.get("ebay_app_credentials") or {}


class eBaySettings(Document):
	def validate(self):
		if not self.enabled:
			return
		missing = []
		if not self._resolve_client_id():
			missing.append("client_id")
		if not self._resolve_ru_name():
			missing.append("ru_name")
		if missing:
			raise EbayConfigurationError(_("Missing eBay credential fields: {0}").format(", ".join(missing)))
		if not self.auth_scopes:
			self.auth_scopes = "\n".join(DEFAULT_SCOPES)
		if not self.state_token:
			self.state_token = frappe.generate_hash(length=18)

	def build_client(self, scopes: Iterable[str] | None = None):
		credentials = self._build_credentials(require_secret=True)
		oauth_service = EbayOAuthService(credentials, default_scopes=scopes or self.get_scopes())
		token = None
		if self.access_token and self.access_token_expires_at:
			token = EbayToken(
				access_token=self.access_token,
				expires_at=self.access_token_expires_at,
				refresh_token=self.refresh_token,
				scope=self.get_scopes(),
			)

		from erpnext.erpnext_integrations.ebay.client import EbayClient

		return EbayClient(
			credentials=credentials,
			oauth_service=oauth_service,
			token=token,
			refresh_token=self.refresh_token,
			scopes=scopes or self.get_scopes(),
			on_token_refreshed=self._persist_token,
		)

	def build_oauth_service(
		self,
		scopes: Iterable[str] | None = None,
		*,
		require_secret: bool = True,
	) -> EbayOAuthService:
		credentials = self._build_credentials(require_secret=require_secret)
		return EbayOAuthService(credentials, default_scopes=scopes or self.get_scopes())

	def get_scopes(self) -> list[str]:
		return [scope.strip() for scope in (self.auth_scopes or "").splitlines() if scope.strip()]

	def _persist_token(self, token: EbayToken):
		self.db_set("access_token", token.access_token)
		self.db_set("access_token_expires_at", token.expires_at)
		if token.refresh_token:
			self.db_set("refresh_token", token.refresh_token)
		self.db_set("auth_scopes", "\n".join(token.scope))

	def generate_authorization_url(self, state: str | None = None) -> str:
		state = state or frappe.generate_hash(length=24)
		self.db_set("state_token", state)
		service = self.build_oauth_service(require_secret=False)
		return service.build_authorization_url(state).url

	def _build_credentials(self, *, require_secret: bool) -> EbayCredentials:
		client_id = self._resolve_client_id()
		ru_name = self._resolve_ru_name()
		client_secret = self._resolve_client_secret()
		environment = (self.environment or self._get_common_value("environment") or "production").lower()
		missing = []
		if not client_id:
			missing.append(_("Client ID"))
		if not ru_name:
			missing.append(_("RuName / Redirect Identifier"))
		if require_secret and not client_secret:
			missing.append(_("Client Secret"))
		if missing:
			raise EbayConfigurationError(_("Missing eBay credential fields: {0}").format(", ".join(missing)))
		return EbayCredentials(
			client_id=client_id,
			client_secret=client_secret or "",
			redirect_uri=ru_name,
			environment=environment,
		)

	def _resolve_client_id(self) -> str | None:
		return self.client_id or self._get_common_value("client_id")

	def _resolve_ru_name(self) -> str | None:
		return self.ru_name or self._get_common_value("redirect_uri")

	def _resolve_client_secret(self) -> str | None:
		return self.client_secret or self._get_common_value("client_secret")

	def _get_common_value(self, key: str) -> str | None:
		creds = _get_common_credentials()
		return creds.get(key)
