"""Unit tests for Signer — interface contract and ATA derivation."""
from __future__ import annotations

import pytest
from solders.pubkey import Pubkey  # type: ignore[import-untyped]

from rustyclaw.constants import USDC_MINT
from rustyclaw.signer import KeypairSigner, Signer
from rustyclaw.wallet import Wallet


class TestSignerInterface:
    def test_signer_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            Signer()  # type: ignore[abstract]

    def test_keypair_signer_implements_signer(self) -> None:
        wallet, _ = Wallet.create()
        ks = KeypairSigner(wallet)
        assert isinstance(ks, Signer)


class TestDeriveAta:
    def test_derive_ata_deterministic(self) -> None:
        owner = Pubkey.from_string("11111111111111111111111111111111")
        mint = Pubkey.from_string(USDC_MINT)
        ata1 = KeypairSigner._derive_ata(owner, mint)
        ata2 = KeypairSigner._derive_ata(owner, mint)
        assert ata1 == ata2

    def test_derive_ata_differs_for_different_owners(self) -> None:
        mint = Pubkey.from_string(USDC_MINT)
        owner_a = Pubkey.from_string("11111111111111111111111111111111")
        owner_b = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        ata_a = KeypairSigner._derive_ata(owner_a, mint)
        ata_b = KeypairSigner._derive_ata(owner_b, mint)
        assert ata_a != ata_b
