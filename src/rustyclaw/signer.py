"""RustyClaw signer — pluggable payment signing interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from rustyclaw.errors import SignerError
from rustyclaw.types import PaymentAccept, PaymentPayload, Resource, SolanaPayload
from rustyclaw.wallet import Wallet
from rustyclaw.constants import USDC_MINT, X402_VERSION


class Signer(ABC):
    """Abstract signer interface. Implement this to customize payment signing."""

    @abstractmethod
    async def sign_payment(
        self,
        amount_atomic: int,
        recipient: str,
        resource: Resource,
        accepted: PaymentAccept,
    ) -> PaymentPayload:
        """Build and sign a payment transaction, return PaymentPayload."""
        ...


class KeypairSigner(Signer):
    """Default signer that builds real Solana USDC-SPL transfer transactions."""

    def __init__(
        self,
        wallet: Wallet,
        rpc_url: str = "https://api.mainnet-beta.solana.com",
    ) -> None:
        self._wallet = wallet
        self._rpc_url = rpc_url

    async def sign_payment(
        self,
        amount_atomic: int,
        recipient: str,
        resource: Resource,
        accepted: PaymentAccept,
    ) -> PaymentPayload:
        """Build and sign a USDC-SPL transfer transaction."""
        try:
            import base64

            import httpx
            from solders.hash import Hash as Blockhash
            from solders.instruction import AccountMeta, Instruction
            from solders.keypair import Keypair as SoldersKeypair
            from solders.message import Message
            from solders.pubkey import Pubkey
            from solders.transaction import Transaction

            sender = self._wallet.pubkey()
            recipient_pubkey = Pubkey.from_string(recipient)
            mint = Pubkey.from_string(USDC_MINT)

            # SPL Token program
            token_program = Pubkey.from_string(
                "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
            )

            # Derive ATAs
            sender_ata = self._derive_ata(sender, mint)
            recipient_ata = self._derive_ata(recipient_pubkey, mint)

            # Get recent blockhash
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self._rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getLatestBlockhash",
                        "params": [{"commitment": "finalized"}],
                    },
                )
                data = resp.json()
                blockhash_str = data["result"]["value"]["blockhash"]
                blockhash = Blockhash.from_string(blockhash_str)

            # Build SPL Token transfer instruction
            # Transfer instruction = index 3, data = amount as little-endian u64
            transfer_data = bytes([3]) + amount_atomic.to_bytes(8, "little")
            transfer_ix = Instruction(
                program_id=token_program,
                accounts=[
                    AccountMeta(
                        pubkey=sender_ata, is_signer=False, is_writable=True
                    ),
                    AccountMeta(
                        pubkey=recipient_ata, is_signer=False, is_writable=True
                    ),
                    AccountMeta(
                        pubkey=sender, is_signer=True, is_writable=False
                    ),
                ],
                data=transfer_data,
            )

            # Build and sign transaction
            msg = Message.new_with_blockhash([transfer_ix], sender, blockhash)
            kp_bytes = self._wallet.to_keypair_bytes()
            solders_kp = SoldersKeypair.from_bytes(kp_bytes)
            tx = Transaction.new_unsigned(msg)
            tx.sign([solders_kp], blockhash)

            tx_b64 = base64.b64encode(bytes(tx)).decode()

            return PaymentPayload(
                x402_version=X402_VERSION,
                resource=resource,
                accepted=accepted,
                payload=SolanaPayload(transaction=tx_b64),
            )
        except SignerError:
            raise
        except Exception as e:
            raise SignerError(f"Failed to sign payment: {e}") from e

    @staticmethod
    def _derive_ata(owner: "Pubkey", mint: "Pubkey") -> "Pubkey":
        """Derive Associated Token Account address."""
        from solders.pubkey import Pubkey

        ata_program = Pubkey.from_string(
            "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
        )
        token_program = Pubkey.from_string(
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        )
        # PDA: seeds = [owner, token_program, mint], program = ata_program
        derived, _bump = Pubkey.find_program_address(
            [bytes(owner), bytes(token_program), bytes(mint)],
            ata_program,
        )
        return derived
