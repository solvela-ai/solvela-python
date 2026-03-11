"""RustyClaw client configuration and builder."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClientConfig:
    """Configuration for the RustyClaw client."""

    gateway_url: str = "http://localhost:8402"
    rpc_url: str = "https://api.mainnet-beta.solana.com"
    prefer_escrow: bool = False
    timeout: float = 180.0
    expected_recipient: str | None = None
    max_payment_amount: int | None = None
    enable_cache: bool = False
    enable_sessions: bool = False
    session_ttl: float = 1800.0
    enable_quality_check: bool = False
    max_quality_retries: int = 1
    free_fallback_model: str | None = None


class ClientBuilder:
    """Fluent builder for ClientConfig."""

    def __init__(self) -> None:
        self._config = ClientConfig()

    def gateway_url(self, value: str) -> ClientBuilder:
        self._config.gateway_url = value
        return self

    def rpc_url(self, value: str) -> ClientBuilder:
        self._config.rpc_url = value
        return self

    def prefer_escrow(self, value: bool) -> ClientBuilder:
        self._config.prefer_escrow = value
        return self

    def timeout(self, value: float) -> ClientBuilder:
        self._config.timeout = value
        return self

    def expected_recipient(self, value: str | None) -> ClientBuilder:
        self._config.expected_recipient = value
        return self

    def max_payment_amount(self, value: int | None) -> ClientBuilder:
        self._config.max_payment_amount = value
        return self

    def enable_cache(self, value: bool) -> ClientBuilder:
        self._config.enable_cache = value
        return self

    def enable_sessions(self, value: bool) -> ClientBuilder:
        self._config.enable_sessions = value
        return self

    def session_ttl(self, value: float) -> ClientBuilder:
        self._config.session_ttl = value
        return self

    def enable_quality_check(self, value: bool) -> ClientBuilder:
        self._config.enable_quality_check = value
        return self

    def max_quality_retries(self, value: int) -> ClientBuilder:
        self._config.max_quality_retries = value
        return self

    def free_fallback_model(self, value: str | None) -> ClientBuilder:
        self._config.free_fallback_model = value
        return self

    def build(self) -> ClientConfig:
        """Build and return the configuration."""
        return self._config
