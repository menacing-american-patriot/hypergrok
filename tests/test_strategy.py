from __future__ import annotations

from dataclasses import dataclass

import pytest

from hypergrok.clients.hyperliquid import SimulatedHyperliquidClient
from hypergrok.config import AppConfig, GrokConfig, HyperliquidConfig, RiskConfig, StrategyConfig, WalletConfig
from hypergrok.models import PortfolioState, TradeSignal, OrderSide
from hypergrok.risk import RiskManager
from hypergrok.strategy import GrokHyperliquidStrategy
from hypergrok.wallet import WalletManager


@dataclass
class FakeGrokClient:
    signal: TradeSignal

    async def generate_signal(self, _snapshots):
        return self.signal


@pytest.mark.asyncio
async def test_strategy_executes_signal_and_updates_wallet():
    config = AppConfig(
        wallet=WalletConfig(base_asset="USDC", initial_balance=10_000, min_cash_reserve=1_000),
        risk=RiskConfig(max_position_size=1000, max_leverage=5, max_daily_loss=5000),
        hyperliquid=HyperliquidConfig(
            base_url="https://api.example.com",
            api_key="a" * 16,
            api_secret="b" * 16,
            subaccount="test",
            account_address="0xabc",
        ),
        grok=GrokConfig(
            api_url="https://grok.example.com",
            api_key="c" * 16,
            model="grok",
            temperature=0.1,
            max_tokens=256,
        ),
        strategy=StrategyConfig(poll_interval_seconds=0.1, trading_pairs=["BTC-PERP"], enable_live_trading=False),
    )

    wallet = WalletManager(state=PortfolioState(balance=config.wallet.initial_balance), min_cash_reserve=1_000)
    risk = RiskManager(config=config.risk)
    hyperliquid = SimulatedHyperliquidClient()
    signal = TradeSignal(symbol="BTC-PERP", side=OrderSide.BUY, size=10, leverage=2, confidence=0.7)
    strategy = GrokHyperliquidStrategy(
        config=config,
        grok=FakeGrokClient(signal),
        hyperliquid=hyperliquid,
        wallet=wallet,
        risk=risk,
    )

    await strategy.run_cycle()

    assert "BTC-PERP" in wallet.state.positions
    assert wallet.state.balance < config.wallet.initial_balance


@pytest.mark.asyncio
async def test_strategy_blocks_when_risk_exceeded():
    config = AppConfig(
        wallet=WalletConfig(base_asset="USDC", initial_balance=5_000, min_cash_reserve=500),
        risk=RiskConfig(max_position_size=100, max_leverage=2, max_daily_loss=500),
        hyperliquid=HyperliquidConfig(
            base_url="https://api.example.com",
            api_key="a" * 16,
            api_secret="b" * 16,
        ),
        grok=GrokConfig(
            api_url="https://grok.example.com",
            api_key="c" * 16,
            model="grok",
            temperature=0.1,
            max_tokens=256,
        ),
        strategy=StrategyConfig(poll_interval_seconds=0.1, trading_pairs=["ETH-PERP"], enable_live_trading=False),
    )

    wallet = WalletManager(state=PortfolioState(balance=config.wallet.initial_balance), min_cash_reserve=500)
    risk = RiskManager(config=config.risk)
    hyperliquid = SimulatedHyperliquidClient()
    large_signal = TradeSignal(symbol="ETH-PERP", side=OrderSide.BUY, size=500, leverage=3, confidence=0.7)
    strategy = GrokHyperliquidStrategy(
        config=config,
        grok=FakeGrokClient(large_signal),
        hyperliquid=hyperliquid,
        wallet=wallet,
        risk=risk,
    )

    with pytest.raises(RuntimeError):
        await strategy.run_cycle()
