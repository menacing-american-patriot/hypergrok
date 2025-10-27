"""Risk management utilities."""

from __future__ import annotations

from dataclasses import dataclass

from hypergrok.config import RiskConfig
from hypergrok.models import PortfolioState, TradeSignal


@dataclass
class RiskManager:
    config: RiskConfig

    def validate_signal(self, *, portfolio: PortfolioState, signal: TradeSignal) -> None:
        notional = signal.size
        if notional > self.config.max_position_size:
            raise RuntimeError("Signal exceeds max position size")
        if signal.leverage and signal.leverage > self.config.max_leverage:
            raise RuntimeError("Signal leverage exceeds cap")

        potential_drawdown = notional * (signal.leverage or 1.0)
        if potential_drawdown > self.config.max_daily_loss:
            raise RuntimeError("Signal violates daily loss limit")

        if portfolio.available_balance() < notional / (signal.leverage or 1.0):
            raise RuntimeError("Insufficient available balance for signal")
