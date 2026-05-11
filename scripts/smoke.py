"""Manual smoke test — exercises the real wire contract before release.

Run before tagging a release to verify the SDK still agrees with a live
Solvela gateway. Catches wire-format drift that unit/integration tests
cannot (header names, JSON field renames, accepts-array ordering, new
required fields).

Usage:
    SOLVELA_GATEWAY_URL=https://staging.solvela.ai \
    .venv/bin/python scripts/smoke.py

Defaults to http://localhost:8402 if SOLVELA_GATEWAY_URL is unset.

Exit codes:
    0 — all assertions passed
    1 — an assertion failed or the gateway is unreachable
"""

from __future__ import annotations

import asyncio
import os
import sys

from solvela.client import SolvelaClient
from solvela.config import ClientConfig
from solvela.errors import ClientError, PaymentRequiredError
from solvela.types import ChatMessage, ChatRequest, Role


async def main() -> int:
    gateway_url = os.environ.get("SOLVELA_GATEWAY_URL", "http://localhost:8402")
    print(f"Smoke test against: {gateway_url}\n")

    try:
        client = SolvelaClient(config=ClientConfig(gateway_url=gateway_url))
    except ClientError as exc:
        print(f"FAIL: client construction rejected gateway URL: {exc}")
        return 1

    # 1. models() reaches the gateway and parses the response.
    try:
        models = await client.models()
    except Exception as exc:
        print(f"FAIL: models() raised {type(exc).__name__}: {exc}")
        return 1
    print(f"  models()           -> {len(models)} model(s) returned")
    if not models:
        print("FAIL: expected at least one model from the gateway")
        return 1
    sample_model = models[0]
    print(f"  sample model       -> id={sample_model.id!r}")

    # 2. Unsigned chat returns 402 with a parseable PaymentRequired body.
    req = ChatRequest(
        model=sample_model.id,
        messages=[ChatMessage(role=Role.USER, content="ping")],
    )
    try:
        await client.chat(req)
    except PaymentRequiredError as exc:
        pr = exc.payment_required
        total = pr.cost_breakdown.total
        currency = pr.cost_breakdown.currency
        schemes = [a.scheme for a in pr.accepts]
        print(f"  chat() unsigned    -> 402 OK (total={total} {currency}, schemes={schemes})")
        # Sanity-check the schemes parsed cleanly into the Literal type.
        if not pr.accepts:
            print("FAIL: 402 response had empty accepts array")
            return 1
    except Exception as exc:
        print(f"FAIL: chat() raised {type(exc).__name__} (expected PaymentRequiredError): {exc}")
        return 1
    else:
        print("FAIL: chat() returned a response with no signer configured (expected 402)")
        return 1

    print("\nSmoke test PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
