# Hypergrok Usage Guide

## Overview

Hypergrok connects the Grok AI model with the Hyperliquid exchange to propose and execute trades while enforcing configurable funding and risk controls. This guide explains how to configure the system via environment variables or JSON, run it locally, and operate it safely.

## Prerequisites

- Python 3.11 or higher
- Hyperliquid API key/secret with trading permissions
- Grok (xAI) API access
- Installed dependencies: `pip install -e .[dev]`

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and replace placeholder values:

```
cp .env.example .env
```

Key sections in the env file:

- **Wallet** (`WALLET_*`): custodied capital funding the exchange. Ensure `WALLET_INITIAL_BALANCE` represents off-exchange funds and `WALLET_MIN_CASH_RESERVE` leaves a safety buffer.
- **Risk** (`RISK_*`): absolute caps per trade and per day. Trades violating limits are rejected before submission.
- **Hyperliquid** (`HYPERLIQUID_*`): REST endpoint and credentials. Use testnet credentials when experimenting.
- **Grok** (`GROK_*`): endpoint, key, and optional inference parameters like `GROK_TEMPERATURE`.
- **Strategy** (`STRATEGY_*`): trading markets, polling cadence, and whether to enable live order placement (`STRATEGY_ENABLE_LIVE=true`). Leave `false` to simulate without funding or orders.

### JSON Configuration

As an alternative, create a JSON file with the same structure used by `AppConfig`. Example:

```json
{
  "wallet": {
    "base_asset": "USDC",
    "initial_balance": 100000,
    "min_cash_reserve": 10000
  },
  "risk": {
    "max_position_size": 5000,
    "max_leverage": 5,
    "max_daily_loss": 10000
  },
  "hyperliquid": {
    "base_url": "https://api.hyperliquid.xyz",
    "api_key": "your-hyperliquid-api-key",
    "api_secret": "your-hyperliquid-api-secret",
    "subaccount": "primary",
    "account_address": "0xYourHyperliquidAddress"
  },
  "grok": {
    "api_url": "https://api.x.ai",
    "api_key": "your-grok-api-key",
    "model": "grok-2-latest",
    "temperature": 0.15,
    "max_tokens": 512
  },
  "strategy": {
    "poll_interval_seconds": 5,
    "trading_pairs": ["BTC-PERP", "ETH-PERP"],
    "enable_live_trading": false
  }
}
```

## Running the Engine

### Environment-based configuration

```
python -m hypergrok.main --env .env --cycles 10
```

### JSON configuration

```
python -m hypergrok.main --config config.json --cycles 10
```

Omit `--cycles` to run continuously. Use `CTRL+C` to stop.

## Simulation vs Live Trading

- Keep `STRATEGY_ENABLE_LIVE=false` to run in deterministic simulation mode using the built-in `SimulatedHyperliquidClient` that generates synthetic prices and avoids real funding.
- Switch to `true` only after validating risk controls and wallet balances; the engine will attempt to fund the exchange wallet and submit market orders at the retrieved mark price.

## Funding Workflow

1. Wallet reserves (`WALLET_INITIAL_BALANCE`) hold off-exchange capital.
2. Before each trade, `WalletManager` calculates required collateral and transfers funds via `HyperliquidClient.transfer_from_wallet` if live trading is enabled.
3. Remaining reserves must stay above `WALLET_MIN_CASH_RESERVE`, otherwise the trade is blocked.

## Testing and Verification

- Run unit tests: `pytest`
- Extend tests in `tests/` to reflect custom strategies or additional risk checks.

## Safety Checklist

- Verify all API keys are stored securely (e.g., dotenv, secret managers).
- Limit API permissions during testing (read-only or paper trading keys when available).
- Monitor logs for rejected signals, funding transfers, and execution results.
- Review Hyperliquid fee schedules and slippage to adjust risk parameters accordingly.

## Troubleshooting

- **Invalid configuration**: check environment variables or JSON keys match the names shown above.
- **Grok parsing errors**: examine returned content; ensure Grok prompt constraints produce valid JSON.
- **Insufficient reserves**: increase wallet balance or decrease `RISK_MAX_POSITION` / leverage.

For deeper customization, inspect modules under `src/hypergrok/` and extend strategy logic, risk management, or external clients as needed.
