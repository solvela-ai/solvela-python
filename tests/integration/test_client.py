"""Integration tests for SolvelaClient — HTTP mocking via pytest-httpx."""
from __future__ import annotations

import json

import pytest

from solvela.client import SolvelaClient
from solvela.config import ClientConfig
from solvela.errors import PaymentRequiredError
from solvela.types import ChatMessage, ChatRequest, ChatResponse, Role

GATEWAY_URL = "https://gw.test.local"


def _chat_request(model: str = "gpt-4o") -> ChatRequest:
    return ChatRequest(
        model=model,
        messages=[ChatMessage(role=Role.USER, content="Hello")],
    )


def _chat_response_json(model: str = "gpt-4o") -> dict:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1700000000,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hi there!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 3,
            "total_tokens": 8,
        },
    }


def _payment_required_json() -> dict:
    return {
        "x402_version": 2,
        "resource": {"url": f"{GATEWAY_URL}/v1/chat/completions", "method": "POST"},
        "accepts": [
            {
                "scheme": "exact",
                "network": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
                "amount": "1000",
                "asset": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "pay_to": "RecipientPubkey111111111111111111111111111",
                "max_timeout_seconds": 300,
            }
        ],
        "cost_breakdown": {
            "provider_cost": "950",
            "platform_fee": "50",
            "total": "1000",
            "currency": "USDC",
            "fee_percent": 5,
        },
        "error": "Payment required",
    }


@pytest.mark.asyncio
async def test_chat_success(httpx_mock) -> None:
    """Mock 200 response, verify returns ChatResponse."""
    httpx_mock.add_response(
        url=f"{GATEWAY_URL}/v1/chat/completions",
        json=_chat_response_json(),
        status_code=200,
    )
    config = ClientConfig(gateway_url=GATEWAY_URL)
    client = SolvelaClient(config=config)
    response = await client.chat(_chat_request())
    assert isinstance(response, ChatResponse)
    assert response.id == "chatcmpl-1"
    assert response.choices[0].message.content == "Hi there!"


@pytest.mark.asyncio
async def test_chat_with_cache(httpx_mock) -> None:
    """Enable cache, send same request twice, verify only 1 HTTP call."""
    httpx_mock.add_response(
        url=f"{GATEWAY_URL}/v1/chat/completions",
        json=_chat_response_json(),
        status_code=200,
    )
    config = ClientConfig(gateway_url=GATEWAY_URL, enable_cache=True)
    client = SolvelaClient(config=config)

    req = _chat_request()
    resp1 = await client.chat(req)
    resp2 = await client.chat(req)

    assert resp1.id == resp2.id
    # Only one HTTP request should have been made
    assert len(httpx_mock.get_requests()) == 1


@pytest.mark.asyncio
async def test_chat_quality_retry(httpx_mock) -> None:
    """First response degraded (empty content), second good, verify retries."""
    degraded_response = {
        "id": "chatcmpl-degraded",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": ""},
                "finish_reason": "stop",
            }
        ],
    }
    good_response = _chat_response_json()

    httpx_mock.add_response(
        url=f"{GATEWAY_URL}/v1/chat/completions",
        json=degraded_response,
        status_code=200,
    )
    httpx_mock.add_response(
        url=f"{GATEWAY_URL}/v1/chat/completions",
        json=good_response,
        status_code=200,
    )

    config = ClientConfig(
        gateway_url=GATEWAY_URL,
        enable_quality_check=True,
        max_quality_retries=1,
    )
    client = SolvelaClient(config=config)
    response = await client.chat(_chat_request())

    assert response.choices[0].message.content == "Hi there!"
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.asyncio
async def test_chat_402_without_signer(httpx_mock) -> None:
    """Mock 402, verify raises PaymentRequiredError when no signer configured."""
    httpx_mock.add_response(
        url=f"{GATEWAY_URL}/v1/chat/completions",
        json=_payment_required_json(),
        status_code=402,
    )
    config = ClientConfig(gateway_url=GATEWAY_URL)
    client = SolvelaClient(config=config)

    with pytest.raises(PaymentRequiredError):
        await client.chat(_chat_request())


@pytest.mark.asyncio
async def test_chat_balance_guard_fallback(httpx_mock) -> None:
    """Set _last_balance=0, free_fallback_model set, verify model swapped."""
    httpx_mock.add_response(
        url=f"{GATEWAY_URL}/v1/chat/completions",
        json=_chat_response_json(model="free-model"),
        status_code=200,
    )
    config = ClientConfig(
        gateway_url=GATEWAY_URL,
        free_fallback_model="free-model",
    )
    client = SolvelaClient(config=config)
    client._last_balance = 0.0

    await client.chat(_chat_request(model="gpt-4o"))

    # Verify the request sent to the gateway used the fallback model
    request = httpx_mock.get_requests()[0]
    body = json.loads(request.content)
    assert body["model"] == "free-model"
