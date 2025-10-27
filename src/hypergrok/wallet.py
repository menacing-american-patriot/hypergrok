"""Wallet management for Hypergrok."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from hypergrok.models import OrderSide, PortfolioState, Position, TradeSignal


class ExchangeClient(Protocol):
    async def transfer_from_wallet(self, amount: float) -> dict:  # noqa: ANN201 - protocol signature
        ...


@dataclass
class WalletManager:
    state: PortfolioState
    min_cash_reserve: float

    async def top_up_exchange(self, *, client: ExchangeClient, target_balance: float) -> float:
        available = self.state.available_balance()
        delta = max(0.0, target_balance - available)
        if delta <= 0:
            return 0.0
        reserve_after = self.state.balance - delta
        if reserve_after < self.min_cash_reserve:
            raise RuntimeError("Insufficient reserves to fund exchange")
        self.state.balance -= delta
        await client.transfer_from_wallet(delta)
        return delta

    def apply_execution(self, *, signal: TradeSignal, execution_price: float) -> None:
        notional = execution_price * signal.size
        collateral = notional / (signal.leverage or 1.0)

        if collateral > self.state.balance:
            raise RuntimeError("Insufficient wallet balance for trade")

        self.state.balance -= collateral
        self.state.positions[signal.symbol] = Position(
            symbol=signal.symbol,
            side=signal.side,
            size=signal.size,
            entry_price=execution_price,
            leverage=signal.leverage or 1.0,
        )

    def close_position(self, symbol: str, exit_price: float) -> None:
        position = self.state.positions.pop(symbol, None)
        if not position:
            return
        notional = position.size * exit_price
        pnl = notional - position.size * position.entry_price
        if position.side is OrderSide.SELL:
            pnl *= -1
        collateral = position.size * position.entry_price / position.leverage
        self.state.balance += collateral + pnl
