"""Domain models for the Hypergrok trading system."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class MarketSnapshot(BaseModel):
    symbol: str
    mark_price: float = Field(..., gt=0)
    index_price: float = Field(..., gt=0)
    open_interest: Optional[float] = Field(default=None, ge=0)
    funding_rate: Optional[float] = None
    timestamp: datetime
    meta: Dict[str, Any] = Field(default_factory=dict)


class TradeSignal(BaseModel):
    symbol: str
    side: OrderSide
    size: float = Field(..., gt=0)
    leverage: Optional[float] = Field(default=None, gt=0)
    confidence: float = Field(default=0.5, ge=0, le=1)
    narrative: Optional[str] = None

    @field_validator("leverage")
    @classmethod
    def leverage_bounds(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value > 50:
            raise ValueError("Leverage must be <= 50 for safety")
        return value


class Position(BaseModel):
    symbol: str
    side: OrderSide
    size: float = Field(..., gt=0)
    entry_price: float = Field(..., gt=0)
    leverage: float = Field(default=1.0, gt=0)


class PortfolioState(BaseModel):
    balance: float = Field(..., ge=0)
    positions: Dict[str, Position] = Field(default_factory=dict)

    def available_balance(self) -> float:
        allocated = sum(pos.size * pos.entry_price / pos.leverage for pos in self.positions.values())
        return max(self.balance - allocated, 0.0)
