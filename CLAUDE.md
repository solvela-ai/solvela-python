# CLAUDE.md

This file provides guidance to Claude Code when working with the rustyclaw-python SDK.

## Build / Test / Lint Commands

```bash
# Install (editable, with dev dependencies)
pip install -e ".[dev]"

# Run all tests (unit + integration)
pytest tests/unit/ tests/integration/ -v

# Run a single test file
pytest tests/unit/test_client.py -v

# Run tests matching a pattern
pytest tests/unit/ -k "test_cache_hit" -v

# Live contract tests (requires running RustyClawRouter gateway)
RUSTYCLAW_LIVE_TESTS=1 pytest tests/live/ -v

# Linting
ruff check src/ tests/
ruff format --check src/ tests/

# Type checking
mypy src/
```

## Architecture

Python SDK for RustyClawRouter — enables AI agents to pay for LLM API calls with USDC-SPL tokens on Solana via the x402 protocol. This is the client SDK; the server is RustyClawRouter (Rust/Axum).

### Module Map

```
src/rustyclaw/
  client.py        # RustyClawClient — high-level 7-step smart chat flow
  config.py        # ClientConfig dataclass + ClientBuilder (fluent API)
  transport.py     # Async HTTP + SSE streaming via httpx
  types.py         # Wire-format dataclasses — OpenAI-compatible chat + x402 payment types
  errors.py        # Error hierarchy (ClientError base, 8 domain subtypes)
  wallet.py        # Solana keypair management with BIP39 mnemonic support
  signer.py        # Pluggable payment signing — Signer ABC + KeypairSigner (SPL transfer)
  balance.py       # BalanceMonitor — background USDC-SPL balance poller with low-balance callback
  cache.py         # LRU ResponseCache with TTL + dedup window (thread-safe)
  session.py       # SessionStore with TTL + three-strike escalation (thread-safe)
  quality.py       # Degraded response detection (4 heuristics: empty, error phrase, repetition, truncation)
  openai_compat.py # OpenAI-compatible wrapper (openai.chat.completions.create interface)
  constants.py     # Protocol constants (x402 version, USDC mint, network, fee percent)
```

### Smart Chat Flow (client.py)

The `RustyClawClient.chat()` method runs a 7-step pipeline:
1. Balance guard — fallback to free model when USDC balance is zero
2. Session lookup — derive session from messages, track conversation state
3. Cache check — after model finalization to prevent cross-model pollution
4. Send request — with automatic x402 payment signing on 402 responses
5. Quality check — detect degraded responses, retry if enabled
6. Cache store
7. Session update

### Payment Flow (x402 protocol)

1. Client sends chat request to gateway
2. Gateway returns 402 with `PaymentRequired` (cost breakdown + accepted payment schemes)
3. Client selects scheme (prefer "exact", fallback to "escrow")
4. `Signer` builds and signs a Solana SPL Token transfer transaction
5. Client retries with `Payment-Signature` header (base64-encoded JSON payload)
6. Gateway verifies payment and returns chat completion

## Code Conventions

- **Python 3.10+** — uses `X | Y` union syntax, no `from __future__ import annotations` needed (but present for consistency)
- **Async-first** — all I/O is async via `httpx.AsyncClient`; tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- **Dataclasses for types** — all wire-format types are `@dataclass` with `to_dict()` / `from_dict()` classmethods
- **Thread-safe caches** — `ResponseCache` and `SessionStore` use `threading.Lock`
- **Error hierarchy** — `ClientError` base, never raise bare `Exception`
- **No mutation of inputs** — build new `ChatRequest` with overrides rather than modifying the original
- **Pluggable signing** — `Signer` ABC allows custom implementations; `KeypairSigner` is the default
- **Ruff lint rules** — `E, F, I, N, UP, B, SIM, TCH` selected; line length 100
- **Mypy strict mode** — `strict = true` in pyproject.toml
- **Test layout** — `tests/unit/` (mocked, fast), `tests/integration/` (httpx mocked transport), `tests/live/` (real gateway, gated by env var)
- **Solders for Solana** — `solders` crate bindings for keypair, pubkey, transaction construction
- **USDC amounts in atomic units** — 1 USDC = 1,000,000 atomic units (6 decimals)
