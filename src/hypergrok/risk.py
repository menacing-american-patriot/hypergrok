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


@dataclass
class AggressiveRiskManager:
    def validate_signal(self, *, portfolio: PortfolioState, signal: TradeSignal) -> None:
        if signal.size <= 0:
            raise RuntimeError("Signal size must be positive")
        if signal.leverage is not None and signal.leverage <= 0:
            raise RuntimeError("Signal leverage must be positive")
        if portfolio.available_balance() <= 0:
            raise RuntimeError("No available balance to allocate")
