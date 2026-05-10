"""Solvela transport — async HTTP + SSE streaming via httpx."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from solvela.errors import GatewayError
from solvela.errors import TimeoutError as SolvelaTimeoutError
from solvela.types import ChatChunk, ChatRequest, ChatResponse, PaymentRequired


class Transport:
    """Async HTTP transport for the Solvela gateway."""

    def __init__(self, base_url: str, timeout: float = 180.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _build_url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _build_headers(
        self,
        payment_signature: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if payment_signature is not None:
            headers["Payment-Signature"] = payment_signature
        if extra_headers:
            headers.update(extra_headers)
        return headers

    async def send_chat(
        self,
        request: ChatRequest,
        payment_signature: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> ChatResponse | PaymentRequired:
        """Send non-streaming chat request.

        Returns ``ChatResponse`` on 200 and ``PaymentRequired`` *as a value*
        on 402. Raises ``GatewayError`` on any other status. Note the
        deliberate asymmetry with :meth:`send_chat_stream`, which **raises**
        ``PaymentRequiredError`` on 402 instead of returning it — direct
        callers of ``Transport`` must handle the two surfaces differently.
        """
        url = self._build_url("/v1/chat/completions")
        headers = self._build_headers(payment_signature, extra_headers)
        body = request.to_dict()
        body["stream"] = False

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(url, json=body, headers=headers)
            except httpx.TimeoutException as err:
                raise SolvelaTimeoutError(self._timeout) from err

            if resp.status_code == 200:
                return ChatResponse.from_dict(_decode_json(resp))
            elif resp.status_code == 402:
                return PaymentRequired.from_dict(_decode_json(resp))
            else:
                raise GatewayError(
                    status=resp.status_code,
                    message=_extract_error_message(resp),
                )

    async def send_chat_stream(
        self,
        request: ChatRequest,
        payment_signature: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Send streaming chat request. Yields ChatChunk objects from SSE stream.

        Raises ``PaymentRequiredError`` on 402 and ``GatewayError`` on any
        other non-200 status. Unlike :meth:`send_chat`, the 402 case is
        **raised** rather than returned — direct callers must catch
        ``PaymentRequiredError`` to discover the payment challenge.
        """
        url = self._build_url("/v1/chat/completions")
        headers = self._build_headers(payment_signature, extra_headers)
        body = request.to_dict()
        body["stream"] = True

        from solvela.errors import PaymentRequiredError

        async with (
            httpx.AsyncClient(timeout=self._timeout) as client,
            client.stream("POST", url, json=body, headers=headers) as resp,
        ):
            if resp.status_code == 402:
                raw = await resp.aread()
                pr = PaymentRequired.from_dict(_decode_json_bytes(raw))
                raise PaymentRequiredError(pr)
            if resp.status_code != 200:
                raw = await resp.aread()
                raise GatewayError(
                    status=resp.status_code,
                    message=_extract_error_message_bytes(raw),
                )

            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    yield ChatChunk.from_dict(json.loads(data_str))

    async def fetch_models(self) -> list[dict]:
        """Fetch model list from gateway."""
        url = self._build_url("/v1/models")
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise GatewayError(status=resp.status_code, message=resp.text)
            return _decode_json(resp).get("data", [])


# --- Module-level decode helpers ---------------------------------------------
#
# Centralizing JSON decoding keeps the response-handling fan-in small and
# guarantees a non-200 HTML body or truncated JSON does not silently escape
# as an unhandled JSONDecodeError. Each helper translates decode failures
# into a typed Solvela error with the original exception chained via
# ``__cause__`` so the offending bytes are not echoed into log messages.


def _decode_json(resp: httpx.Response) -> Any:  # noqa: ANN401  # JSON shape varies
    try:
        return resp.json()
    except json.JSONDecodeError as err:
        raise GatewayError(
            status=resp.status_code,
            message="malformed JSON body",
        ) from err


def _decode_json_bytes(raw: bytes) -> Any:  # noqa: ANN401
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise GatewayError(
            status=0,
            message="malformed JSON body",
        ) from err


def _extract_error_message(resp: httpx.Response) -> str:
    """Best-effort error message for a non-200 response.

    Falls back to the raw body text when the response is not JSON, but
    never raises — this is the *secondary* error path and must not mask
    the original status with a JSON-decode failure of its own.
    """
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return resp.text
    if isinstance(data, dict):
        msg = data.get("error", resp.text)
        return msg if isinstance(msg, str) else resp.text
    return resp.text


def _extract_error_message_bytes(raw: bytes) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode(errors="replace")
    if isinstance(data, dict):
        msg = data.get("error")
        if isinstance(msg, str):
            return msg
    return raw.decode(errors="replace")
