"""Live contract tests — require a running RustyClaw gateway."""
from __future__ import annotations

import pytest

from rustyclaw.errors import PaymentRequiredError
from rustyclaw.types import ChatMessage, ChatRequest, Role


@pytest.mark.asyncio
async def test_live_chat_402_without_wallet(live_client):
    """Without a wallet/signer, a chat request should return 402."""
    req = ChatRequest(
        model="gpt-4o",
        messages=[ChatMessage(role=Role.USER, content="Hello")],
    )
    with pytest.raises(PaymentRequiredError):
        await live_client.chat(req)


@pytest.mark.asyncio
async def test_live_models_list(live_client):
    """The gateway should return at least one model."""
    models = await live_client.models()
    assert len(models) > 0
