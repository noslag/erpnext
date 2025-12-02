from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from .constants import get_environment, normalize_scopes


@dataclass(frozen=True)
class EbayCredentials:
	client_id: str
	client_secret: str
	redirect_uri: str
	environment: str = "production"


@dataclass
class EbayToken:
	access_token: str
	expires_at: datetime
	refresh_token: str | None = None
	scope: Sequence[str] = field(default_factory=list)

	def is_expired(self, buffer_seconds: int = 60) -> bool:
		buffered_now = datetime.now(timezone.utc) + timedelta(seconds=buffer_seconds)
		return buffered_now >= self.expires_at


@dataclass(frozen=True)
class EbayRequestContext:
	environment: str
	scopes: Sequence[str]

	@property
	def api_base(self) -> str:
		return get_environment(self.environment).api_base

	@property
	def identity_base(self) -> str:
		return get_environment(self.environment).identity_base


@dataclass(frozen=True)
class TokenResponse:
	access_token: str
	expires_in: int
	scope: Sequence[str]
	refresh_token: str | None = None

	def to_token(self) -> EbayToken:
		return EbayToken(
			access_token=self.access_token,
			expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.expires_in),
			refresh_token=self.refresh_token,
			scope=normalize_scopes(self.scope),
		)


def build_request_context(credentials: EbayCredentials, scopes: Iterable[str] | None = None) -> EbayRequestContext:
	return EbayRequestContext(
		environment=credentials.environment,
		scopes=normalize_scopes(scopes),
	)
