"""Clients for interacting with Hyperliquid exchange."""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, Optional

import httpx

from hypergrok.models import MarketSnapshot, OrderSide


class HyperliquidClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        api_secret: str,
        subaccount: Optional[str] = None,
        account_address: Optional[str] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret
        self._subaccount = subaccount
        self._account_address = account_address
        self._client = httpx.AsyncClient(timeout=20.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_market_snapshots(self, symbols: Iterable[str]) -> Dict[str, MarketSnapshot]:
        snapshots: Dict[str, MarketSnapshot] = {}
        for symbol in symbols:
            response = await self._client.get(f"{self._base_url}/markets/{symbol}", headers=self._auth_headers())
            response.raise_for_status()
            payload = response.json()
            snapshots[symbol] = MarketSnapshot(
                symbol=symbol,
                mark_price=float(payload["markPrice"]),
                index_price=float(payload.get("indexPrice", payload["markPrice"])),
                open_interest=float(payload.get("openInterest", 0)),
                funding_rate=float(payload.get("fundingRate", 0)),
                timestamp=_now_ts(),
                meta={k: v for k, v in payload.items() if k not in {"markPrice", "indexPrice", "openInterest", "fundingRate"}},
            )
        return snapshots

    async def fetch_account_balance(self) -> float:
        response = await self._client.get(f"{self._base_url}/wallet/balance", headers=self._auth_headers())
        response.raise_for_status()
        payload = response.json()
        return float(payload["available"])

    async def transfer_from_wallet(self, amount: float) -> Dict[str, Any]:
        response = await self._client.post(
            f"{self._base_url}/wallet/deposit",
            headers=self._auth_headers(),
            json={"amount": amount, "address": self._account_address, "subaccount": self._subaccount},
        )
        response.raise_for_status()
        return response.json()

    async def place_order(
        self,
        *,
        symbol: str,
        side: OrderSide,
        size: float,
        price: Optional[float] = None,
        leverage: Optional[float] = None,
    ) -> Dict[str, Any]:
        order_payload: Dict[str, Any] = {
            "symbol": symbol,
            "side": side.value,
            "size": size,
            "type": "market" if price is None else "limit",
        }
        if price is not None:
            order_payload["price"] = price
        if leverage is not None:
            order_payload["leverage"] = leverage
        if self._subaccount:
            order_payload["subaccount"] = self._subaccount

        response = await self._client.post(
            f"{self._base_url}/orders",
            headers=self._auth_headers(),
            json=order_payload,
        )
        response.raise_for_status()
        return response.json()

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "X-API-KEY": self._api_key,
            "X-API-SECRET": self._api_secret,
            "Content-Type": "application/json",
        }


class SimulatedHyperliquidClient(HyperliquidClient):
    def __init__(self, initial_balance: float = 1_000.0) -> None:
        self._balance = initial_balance
        self._executed_orders: list[Dict[str, Any]] = []

    async def aclose(self) -> None:
        return None

    async def fetch_market_snapshots(self, symbols: Iterable[str]) -> Dict[str, MarketSnapshot]:  # type: ignore[override]
        return {
            symbol: MarketSnapshot(
                symbol=symbol,
                mark_price=100.0,
                index_price=100.0,
                open_interest=1_000.0,
                funding_rate=0.0001,
                timestamp=_now_ts(),
                meta={},
            )
            for symbol in symbols
        }

    async def fetch_account_balance(self) -> float:  # type: ignore[override]
        return self._balance

    async def transfer_from_wallet(self, amount: float) -> Dict[str, Any]:  # type: ignore[override]
        self._balance += amount
        return {"status": "success", "balance": self._balance}

    async def place_order(  # type: ignore[override]
        self,
        *,
        symbol: str,
        side: OrderSide,
        size: float,
        price: Optional[float] = None,
        leverage: Optional[float] = None,
    ) -> Dict[str, Any]:
        notional = (price or 100.0) * size
        if side is OrderSide.BUY:
            self._balance -= notional / (leverage or 1)
        else:
            self._balance += notional / (leverage or 1)
        order = {
            "symbol": symbol,
            "side": side.value,
            "size": size,
            "price": price,
            "leverage": leverage,
            "balance": self._balance,
        }
        self._executed_orders.append(order)
        return order

    @property
    def executed_orders(self) -> list[Dict[str, Any]]:
        return self._executed_orders


def _now_ts() -> float:
    return time.time()
