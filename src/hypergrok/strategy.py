"""Trading strategy orchestration."""

from __future__ import annotations

import logging
from typing import Iterable

from hypergrok.clients import GrokClient, HyperliquidClient
from hypergrok.config import AppConfig
from hypergrok.models import MarketSnapshot, TradeSignal
from hypergrok.risk import RiskManager
from hypergrok.wallet import WalletManager

logger = logging.getLogger(__name__)


class GrokHyperliquidStrategy:
    def __init__(
        self,
        *,
        config: AppConfig,
        grok: GrokClient,
        hyperliquid: HyperliquidClient,
        wallet: WalletManager,
        risk: RiskManager,
    ) -> None:
        self._config = config
        self._grok = grok
        self._hyperliquid = hyperliquid
        self._wallet = wallet
        self._risk = risk

    async def run_cycle(self) -> TradeSignal:
        logger.info("Fetching market snapshots for %s", self._config.strategy.trading_pairs)
        snapshots = await self._hyperliquid.fetch_market_snapshots(self._config.strategy.trading_pairs)
        signal = await self._generate_signal(snapshots.values())
        self._risk.validate_signal(portfolio=self._wallet.state, signal=signal)

        collateral = self._collateral_required(signal, snapshots[signal.symbol])
        if self._config.strategy.enable_live_trading:
            await self._wallet.top_up_exchange(client=self._hyperliquid, target_balance=collateral)
            await self._hyperliquid.place_order(
                symbol=signal.symbol,
                side=signal.side,
                size=signal.size,
                price=snapshots[signal.symbol].mark_price,
                leverage=signal.leverage,
            )
        execution_price = snapshots[signal.symbol].mark_price
        self._wallet.apply_execution(signal=signal, execution_price=execution_price)
        logger.info("Executed signal %s at price %.2f", signal, execution_price)
        return signal

    async def _generate_signal(self, snapshots: Iterable[MarketSnapshot]) -> TradeSignal:
        signal = await self._grok.generate_signal(snapshots)
        logger.info("Received Grok signal: %s", signal)
        return signal

    def _collateral_required(self, signal: TradeSignal, snapshot: MarketSnapshot) -> float:
        notional = snapshot.mark_price * signal.size
        leverage = signal.leverage or 1.0
        return notional / leverage
