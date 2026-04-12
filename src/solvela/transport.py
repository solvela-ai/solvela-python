"""Solvela transport — async HTTP + SSE streaming via httpx."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from solvela.errors import GatewayError
from solvela.errors import TimeoutError as RCTimeoutError
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

        Returns ChatResponse on 200, PaymentRequired on 402.
        Raises GatewayError on other status codes.
        """
        url = self._build_url("/v1/chat/completions")
        headers = self._build_headers(payment_signature, extra_headers)
        body = request.to_dict()
        body["stream"] = False

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(url, json=body, headers=headers)
            except httpx.TimeoutException:
                raise RCTimeoutError(self._timeout)

            if resp.status_code == 200:
                return ChatResponse.from_dict(resp.json())
            elif resp.status_code == 402:
                return PaymentRequired.from_dict(resp.json())
            else:
                try:
                    data = resp.json()
                    msg = data.get("error", resp.text)
                except Exception:
                    msg = resp.text
                raise GatewayError(status=resp.status_code, message=msg)

    async def send_chat_stream(
        self,
        request: ChatRequest,
        payment_signature: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Send streaming chat request. Yields ChatChunk objects from SSE stream.

        Raises PaymentRequiredError on 402, GatewayError on other non-200 status.
        """
        url = self._build_url("/v1/chat/completions")
        headers = self._build_headers(payment_signature, extra_headers)
        body = request.to_dict()
        body["stream"] = True

        from solvela.errors import PaymentRequiredError

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code == 402:
                    raw = await resp.aread()
                    pr = PaymentRequired.from_dict(json.loads(raw))
                    raise PaymentRequiredError(pr)
                if resp.status_code != 200:
                    raw = await resp.aread()
                    try:
                        data = json.loads(raw)
                        msg = data.get("error", raw.decode())
                    except Exception:
                        msg = raw.decode()
                    raise GatewayError(status=resp.status_code, message=msg)

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
            return resp.json().get("data", [])
