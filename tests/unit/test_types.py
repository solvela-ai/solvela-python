"""Tests for rustyclaw.types and rustyclaw.constants."""
from __future__ import annotations

from rustyclaw.constants import (
    MAX_TIMEOUT_SECONDS,
    PLATFORM_FEE_PERCENT,
    SOLANA_NETWORK,
    USDC_MINT,
    X402_VERSION,
)
from rustyclaw.types import (
    ChatChunk,
    ChatChunkChoice,
    ChatChoice,
    ChatDelta,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CostBreakdown,
    FunctionCall,
    FunctionCallDelta,
    FunctionDefinitionInner,
    ModelInfo,
    PaymentAccept,
    PaymentPayload,
    PaymentRequired,
    Resource,
    Role,
    SolanaPayload,
    ToolCall,
    ToolCallDelta,
    ToolDefinition,
    Usage,
)


# --- Constants ---


class TestConstants:
    def test_x402_version(self) -> None:
        assert X402_VERSION == 2

    def test_usdc_mint(self) -> None:
        assert USDC_MINT == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    def test_solana_network(self) -> None:
        assert SOLANA_NETWORK == "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"

    def test_max_timeout(self) -> None:
        assert MAX_TIMEOUT_SECONDS == 300

    def test_platform_fee(self) -> None:
        assert PLATFORM_FEE_PERCENT == 5


# --- Role ---


class TestRole:
    def test_all_values(self) -> None:
        assert Role.SYSTEM == "system"
        assert Role.USER == "user"
        assert Role.ASSISTANT == "assistant"
        assert Role.TOOL == "tool"
        assert Role.DEVELOPER == "developer"

    def test_role_is_str(self) -> None:
        assert isinstance(Role.SYSTEM, str)

    def test_role_count(self) -> None:
        assert len(Role) == 5


# --- ChatMessage ---


class TestChatMessage:
    def test_to_dict_minimal(self) -> None:
        msg = ChatMessage(role=Role.USER, content="hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "hello"}

    def test_to_dict_with_optional_fields(self) -> None:
        msg = ChatMessage(role=Role.ASSISTANT, content="hi", name="bot")
        d = msg.to_dict()
        assert d == {"role": "assistant", "content": "hi", "name": "bot"}

    def test_to_dict_omits_none(self) -> None:
        msg = ChatMessage(role=Role.USER, content="test")
        d = msg.to_dict()
        assert "name" not in d
        assert "tool_calls" not in d
        assert "tool_call_id" not in d

    def test_from_dict(self) -> None:
        msg = ChatMessage.from_dict({"role": "user", "content": "hello"})
        assert msg.role == Role.USER
        assert msg.content == "hello"
        assert msg.name is None

    def test_from_dict_with_tool_calls(self) -> None:
        data = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"city":"NYC"}'},
                }
            ],
        }
        msg = ChatMessage.from_dict(data)
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].function.name == "get_weather"


# --- ChatRequest ---


class TestChatRequest:
    def test_to_dict_includes_stream(self) -> None:
        req = ChatRequest(
            model="gpt-4",
            messages=[ChatMessage(role=Role.USER, content="hi")],
        )
        d = req.to_dict()
        assert "stream" in d
        assert d["stream"] is False

    def test_to_dict_stream_true(self) -> None:
        req = ChatRequest(
            model="gpt-4",
            messages=[ChatMessage(role=Role.USER, content="hi")],
            stream=True,
        )
        d = req.to_dict()
        assert d["stream"] is True

    def test_to_dict_omits_none_optional(self) -> None:
        req = ChatRequest(
            model="gpt-4",
            messages=[ChatMessage(role=Role.USER, content="hi")],
        )
        d = req.to_dict()
        assert "max_tokens" not in d
        assert "temperature" not in d
        assert "tools" not in d


# --- ChatResponse ---


class TestChatResponse:
    def test_from_dict_full(self) -> None:
        data = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        resp = ChatResponse.from_dict(data)
        assert resp.id == "chatcmpl-123"
        assert resp.model == "gpt-4"
        assert len(resp.choices) == 1
        assert resp.choices[0].message.content == "Hello!"
        assert resp.choices[0].finish_reason == "stop"
        assert resp.usage is not None
        assert resp.usage.total_tokens == 15

    def test_from_dict_no_usage(self) -> None:
        data = {
            "id": "chatcmpl-456",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "gpt-4",
            "choices": [],
        }
        resp = ChatResponse.from_dict(data)
        assert resp.usage is None


# --- ChatChunk ---


class TestChatChunk:
    def test_from_dict(self) -> None:
        data = {
            "id": "chatcmpl-chunk-1",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Hi"},
                    "finish_reason": None,
                }
            ],
        }
        chunk = ChatChunk.from_dict(data)
        assert chunk.id == "chatcmpl-chunk-1"
        assert len(chunk.choices) == 1
        assert chunk.choices[0].delta.content == "Hi"
        assert chunk.choices[0].finish_reason is None


# --- PaymentRequired ---


class TestPaymentRequired:
    def test_from_dict(self) -> None:
        data = {
            "x402_version": 2,
            "resource": {"url": "https://gw.example.com/v1/chat/completions", "method": "POST"},
            "accepts": [
                {
                    "scheme": "exact",
                    "network": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
                    "amount": "50000",
                    "asset": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "pay_to": "RecipientWallet111111111111111111111111111",
                    "max_timeout_seconds": 300,
                }
            ],
            "cost_breakdown": {
                "provider_cost": "45000",
                "platform_fee": "5000",
                "total": "50000",
                "currency": "USDC",
                "fee_percent": 5,
            },
            "error": "Payment required",
        }
        pr = PaymentRequired.from_dict(data)
        assert pr.x402_version == 2
        assert pr.resource.url == "https://gw.example.com/v1/chat/completions"
        assert len(pr.accepts) == 1
        assert pr.accepts[0].amount == "50000"
        assert pr.cost_breakdown.total == "50000"
        assert pr.error == "Payment required"


# --- PaymentPayload ---


class TestPaymentPayload:
    def test_to_dict_solana(self) -> None:
        payload = PaymentPayload(
            x402_version=2,
            resource=Resource(url="https://gw.example.com/v1/chat/completions", method="POST"),
            accepted=PaymentAccept(
                scheme="exact",
                network="solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
                amount="50000",
                asset="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                pay_to="RecipientWallet111111111111111111111111111",
                max_timeout_seconds=300,
            ),
            payload=SolanaPayload(transaction="base64encodedtx=="),
        )
        d = payload.to_dict()
        assert d["x402_version"] == 2
        assert d["payload"]["transaction"] == "base64encodedtx=="


# --- ModelInfo ---


class TestModelInfo:
    def test_from_dict(self) -> None:
        data = {
            "id": "gpt-4",
            "provider": "openai",
            "model_id": "gpt-4-0125-preview",
            "display_name": "GPT-4 Turbo",
            "input_cost_per_million": 10000,
            "output_cost_per_million": 30000,
            "context_window": 128000,
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": True,
            "reasoning": False,
            "supports_structured_output": True,
            "supports_batch": False,
            "max_output_tokens": 4096,
        }
        info = ModelInfo.from_dict(data)
        assert info.id == "gpt-4"
        assert info.provider == "openai"
        assert info.context_window == 128000
        assert info.supports_streaming is True
        assert info.max_output_tokens == 4096

    def test_from_dict_defaults(self) -> None:
        data = {
            "id": "test-model",
            "provider": "test",
            "model_id": "test-1",
            "display_name": "Test Model",
            "input_cost_per_million": 1000,
            "output_cost_per_million": 2000,
            "context_window": 4096,
        }
        info = ModelInfo.from_dict(data)
        assert info.supports_streaming is False
        assert info.supports_tools is False
        assert info.reasoning is False
        assert info.max_output_tokens is None


# --- Cache key determinism ---


class TestCacheKey:
    def test_same_input_deterministic(self) -> None:
        req1 = ChatRequest(
            model="gpt-4",
            messages=[ChatMessage(role=Role.USER, content="hello")],
        )
        req2 = ChatRequest(
            model="gpt-4",
            messages=[ChatMessage(role=Role.USER, content="hello")],
        )
        assert req1.cache_key() == req2.cache_key()

    def test_different_model_different_key(self) -> None:
        req1 = ChatRequest(
            model="gpt-4",
            messages=[ChatMessage(role=Role.USER, content="hello")],
        )
        req2 = ChatRequest(
            model="gpt-3.5-turbo",
            messages=[ChatMessage(role=Role.USER, content="hello")],
        )
        assert req1.cache_key() != req2.cache_key()
