"""Unit tests for SolvelaClient — construction and basic properties."""
from __future__ import annotations

from solvela.client import SolvelaClient
from solvela.config import ClientConfig
from solvela.wallet import Wallet


class TestClientCreation:
    def test_client_creation(self) -> None:
        config = ClientConfig(gateway_url="https://example.com")
        client = SolvelaClient(config=config)
        assert client._config.gateway_url == "https://example.com"
        assert client._wallet is None
        assert client._signer is None

    def test_client_creation_with_wallet(self) -> None:
        wallet, _ = Wallet.create()
        config = ClientConfig()
        client = SolvelaClient(config=config, wallet=wallet)
        assert client._wallet is wallet

    def test_client_last_known_balance_initially_none(self) -> None:
        client = SolvelaClient()
        assert client.last_known_balance() is None

    def test_client_debug_redacts(self) -> None:
        client = SolvelaClient()
        r = repr(client)
        assert "REDACTED" in r
        assert "wallet" not in r.replace("wallet=REDACTED", "")


class TestBalanceStateSetter:
    def test_balance_state_setter_updates_balance(self) -> None:
        client = SolvelaClient()
        setter = client.balance_state_setter()
        assert client.last_known_balance() is None
        setter(42.5)
        assert client.last_known_balance() == 42.5
        setter(0.0)
        assert client.last_known_balance() == 0.0
