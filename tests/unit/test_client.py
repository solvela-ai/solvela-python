"""Unit tests for SolvelaClient — construction and basic properties."""
from __future__ import annotations

import pytest

from solvela.client import SolvelaClient
from solvela.config import ClientConfig
from solvela.constants import SOLANA_NETWORK, USDC_MINT
from solvela.errors import ClientError
from solvela.types import PaymentAccept
from solvela.wallet import Wallet


def _accept(
    *,
    network: str = SOLANA_NETWORK,
    asset: str = USDC_MINT,
    amount: str = "1000",
    pay_to: str = "RecipientPubkey111111111111111111111111111",
) -> PaymentAccept:
    return PaymentAccept(
        scheme="exact",
        network=network,
        amount=amount,
        asset=asset,
        pay_to=pay_to,
        max_timeout_seconds=300,
    )


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


class TestValidatePayment:
    """`_validate_payment` must catch network/asset spoofing before signing."""

    def _client(self) -> SolvelaClient:
        return SolvelaClient(config=ClientConfig(max_payment_amount=None))

    def test_accepts_canonical_solana_usdc(self) -> None:
        # Should not raise.
        self._client()._validate_payment(_accept())

    def test_rejects_unexpected_network(self) -> None:
        client = self._client()
        with pytest.raises(ClientError, match="payment network"):
            client._validate_payment(_accept(network="ethereum:1"))

    def test_rejects_unexpected_asset(self) -> None:
        client = self._client()
        # Use a fake mint — must be rejected even though all other fields match.
        bogus_mint = "So11111111111111111111111111111111111111112"
        with pytest.raises(ClientError, match="Unexpected payment asset"):
            client._validate_payment(_accept(asset=bogus_mint))

    def test_rejects_unexpected_asset_does_not_echo_value(self) -> None:
        # Defensive: malicious mint addresses must not be echoed back into logs.
        client = self._client()
        bogus_mint = "MaliciousMint1111111111111111111111111111111"
        try:
            client._validate_payment(_accept(asset=bogus_mint))
        except ClientError as exc:
            assert bogus_mint not in str(exc)
        else:
            pytest.fail("expected ClientError")


class TestQueryBalanceRpcDiscrimination:
    """`_query_balance` must distinguish ATA-not-found from real RPC errors.

    Returning 0.0 on every kind of failure silently trips the balance guard
    into the free-fallback path on transient infrastructure issues (rate
    limit, node down, malformed response). Only the explicit "account does
    not exist" signal — either an error message containing "could not find"
    / "not found" or a 200 with ``result.value == null`` — should map to 0.
    """

    _ADDRESS = "Sender1111111111111111111111111111111111111"
    _RPC_URL = "https://rpc.test.local"

    def _client(self) -> SolvelaClient:
        return SolvelaClient(config=ClientConfig(rpc_url=self._RPC_URL))

    @pytest.mark.asyncio
    async def test_zero_balance_for_existing_ata(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=self._RPC_URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "context": {"slot": 1},
                    "value": {
                        "amount": "0",
                        "decimals": 6,
                        "uiAmount": 0.0,
                        "uiAmountString": "0",
                    },
                },
            },
        )
        assert await self._client()._query_balance(self._ADDRESS) == 0.0

    @pytest.mark.asyncio
    async def test_positive_balance(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=self._RPC_URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "context": {"slot": 1},
                    "value": {
                        "amount": "5000000",
                        "decimals": 6,
                        "uiAmount": 5.0,
                        "uiAmountString": "5",
                    },
                },
            },
        )
        assert await self._client()._query_balance(self._ADDRESS) == 5.0

    @pytest.mark.asyncio
    async def test_ata_not_found_error_returns_zero(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=self._RPC_URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": -32602,
                    "message": "Invalid param: could not find account",
                },
            },
        )
        assert await self._client()._query_balance(self._ADDRESS) == 0.0

    @pytest.mark.asyncio
    async def test_ata_null_value_returns_zero(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        # Some providers signal absence with `result.value: null` on 200.
        httpx_mock.add_response(
            url=self._RPC_URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"context": {"slot": 1}, "value": None},
            },
        )
        assert await self._client()._query_balance(self._ADDRESS) == 0.0

    @pytest.mark.asyncio
    async def test_rate_limit_raises_not_zero(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        # 429 must not be silently coerced to "zero balance" — that would
        # transparently switch the caller to the free-fallback model on a
        # transient infra issue.
        httpx_mock.add_response(url=self._RPC_URL, status_code=429, json={})
        with pytest.raises(ClientError, match="HTTP 429"):
            await self._client()._query_balance(self._ADDRESS)

    @pytest.mark.asyncio
    async def test_generic_rpc_error_raises(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=self._RPC_URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32000, "message": "Internal error"},
            },
        )
        with pytest.raises(ClientError, match="Internal error"):
            await self._client()._query_balance(self._ADDRESS)

    @pytest.mark.asyncio
    async def test_malformed_response_shape_raises(self, httpx_mock) -> None:  # type: ignore[no-untyped-def]
        httpx_mock.add_response(
            url=self._RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "result": "not-an-object"},
        )
        with pytest.raises(ClientError, match="unexpected response shape"):
            await self._client()._query_balance(self._ADDRESS)
