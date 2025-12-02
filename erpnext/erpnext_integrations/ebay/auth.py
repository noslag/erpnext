from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlencode

import requests

from .constants import get_environment, normalize_scopes
from .types import EbayCredentials, TokenResponse


@dataclass(frozen=True)
class AuthorizationState:
	state: str
	url: str
	generated_at: datetime


class EbayOAuthService:
	"""Helper responsible for generating URLs and exchanging tokens."""

	def __init__(
		self,
		credentials: EbayCredentials,
		session: requests.Session | None = None,
		default_scopes: Iterable[str] | None = None,
	):
		self.credentials = credentials
		self.session = session or requests.Session()
		self.scopes = normalize_scopes(default_scopes)
		self.environment = get_environment(credentials.environment)

	def build_authorization_url(self, state: str, scopes: Iterable[str] | None = None) -> AuthorizationState:
		scope_param = " ".join(normalize_scopes(scopes) or self.scopes)
		query = urlencode(
			{
				"client_id": self.credentials.client_id,
				"response_type": "code",
				"redirect_uri": self.credentials.redirect_uri,
				"scope": scope_param,
				"state": state,
			}
		)
		url = f"{self.environment.authorize_base}/oauth2/authorize?{query}"
		return AuthorizationState(state=state, url=url, generated_at=datetime.now(timezone.utc))

	def exchange_authorization_code(
		self,
		code: str,
		*,
		scopes: Iterable[str] | None = None,
	) -> TokenResponse:
		data = {
			"grant_type": "authorization_code",
			"code": code,
			"redirect_uri": self.credentials.redirect_uri,
			"scope": " ".join(normalize_scopes(scopes) or self.scopes),
		}
		return self._request_token(data)

	def refresh_user_token(
		self,
		refresh_token: str,
		*,
		scopes: Iterable[str] | None = None,
	) -> TokenResponse:
		data = {
			"grant_type": "refresh_token",
			"refresh_token": refresh_token,
			"scope": " ".join(normalize_scopes(scopes) or self.scopes),
		}
		return self._request_token(data)

	def _request_token(self, data: dict[str, str]) -> TokenResponse:
		endpoint = f"{self.environment.identity_base}/identity/v1/oauth2/token"
		headers = {
			"Authorization": f"Basic {self._basic_auth_secret()}",
			"Content-Type": "application/x-www-form-urlencoded",
		}
		response = self.session.post(endpoint, data=data, headers=headers, timeout=30)
		response.raise_for_status()
		payload = response.json()
		return TokenResponse(
			access_token=payload["access_token"],
			expires_in=payload["expires_in"],
			scope=(payload.get("scope") or "").split(" "),
			refresh_token=payload.get("refresh_token"),
		)

	def _basic_auth_secret(self) -> str:
		secret = f"{self.credentials.client_id}:{self.credentials.client_secret}".encode()
		return base64.b64encode(secret).decode()
