"""Tests for ClientConfig and ClientBuilder."""
from __future__ import annotations

from solvela.config import ClientBuilder, ClientConfig


class TestClientConfig:
    def test_default_config(self) -> None:
        cfg = ClientConfig()
        assert cfg.gateway_url == "http://localhost:8402"
        assert cfg.rpc_url == "https://api.mainnet-beta.solana.com"
        assert cfg.prefer_escrow is False
        assert cfg.timeout == 180.0
        assert cfg.expected_recipient is None
        assert cfg.max_payment_amount is None
        assert cfg.enable_cache is False
        assert cfg.enable_sessions is False
        assert cfg.session_ttl == 1800.0
        assert cfg.enable_quality_check is False
        assert cfg.max_quality_retries == 1
        assert cfg.free_fallback_model is None


class TestClientBuilder:
    def test_builder_fluent(self) -> None:
        cfg = (
            ClientBuilder()
            .gateway_url("https://gw.example.com")
            .rpc_url("https://rpc.example.com")
            .prefer_escrow(True)
            .timeout(60.0)
            .expected_recipient("RecipABC")
            .max_payment_amount(500_000)
            .enable_cache(True)
            .enable_sessions(True)
            .session_ttl(3600.0)
            .enable_quality_check(True)
            .max_quality_retries(3)
            .free_fallback_model("gpt-4o-mini")
            .build()
        )
        assert cfg.gateway_url == "https://gw.example.com"
        assert cfg.rpc_url == "https://rpc.example.com"
        assert cfg.prefer_escrow is True
        assert cfg.timeout == 60.0
        assert cfg.expected_recipient == "RecipABC"
        assert cfg.max_payment_amount == 500_000
        assert cfg.enable_cache is True
        assert cfg.enable_sessions is True
        assert cfg.session_ttl == 3600.0
        assert cfg.enable_quality_check is True
        assert cfg.max_quality_retries == 3
        assert cfg.free_fallback_model == "gpt-4o-mini"

    def test_builder_default_matches_config_default(self) -> None:
        assert ClientBuilder().build() == ClientConfig()
