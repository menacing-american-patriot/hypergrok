"""Trading engine orchestration."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Optional

from hypergrok.clients import GrokClient, HyperliquidClient
from hypergrok.config import AppConfig
from hypergrok.models import PortfolioState
from hypergrok.risk import AggressiveRiskManager, RiskManager
from hypergrok.strategy import GrokHyperliquidStrategy
from hypergrok.wallet import WalletManager

logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._exit_stack = AsyncExitStack()
        self._strategy: Optional[GrokHyperliquidStrategy] = None

    async def __aenter__(self) -> "TradingEngine":
        await self._startup()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN201
        await self._exit_stack.aclose()

    async def _startup(self) -> None:
        grok = GrokClient(
            api_url=self._config.grok.api_url,
            api_key=self._config.grok.api_key,
            model=self._config.grok.model,
            temperature=self._config.grok.temperature,
            max_tokens=self._config.grok.max_tokens,
        )
        hyperliquid = HyperliquidClient(
            base_url=self._config.hyperliquid.base_url,
            api_key=self._config.hyperliquid.api_key,
            api_secret=self._config.hyperliquid.api_secret,
            subaccount=self._config.hyperliquid.subaccount,
            account_address=self._config.hyperliquid.account_address,
        )

        await self._exit_stack.enter_async_context(_ClosableContext(grok))
        await self._exit_stack.enter_async_context(_ClosableContext(hyperliquid))

        wallet = WalletManager(
            state=PortfolioState(balance=self._config.wallet.initial_balance),
            min_cash_reserve=self._config.wallet.min_cash_reserve,
        )
        if self._config.strategy.auto_max_profit:
            risk = AggressiveRiskManager()
        else:
            risk = RiskManager(config=self._config.risk)

        self._strategy = GrokHyperliquidStrategy(
            config=self._config,
            grok=grok,
            hyperliquid=hyperliquid,
            wallet=wallet,
            risk=risk,
        )

    async def run(self, *, cycles: Optional[int] = None) -> None:
        if not self._strategy:
            await self._startup()
        assert self._strategy
        iteration = 0
        while cycles is None or iteration < cycles:
            iteration += 1
            try:
                await self._strategy.run_cycle()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Trading cycle failed: %s", exc)
            await asyncio.sleep(self._config.strategy.poll_interval_seconds)


class _ClosableContext:
    def __init__(self, client) -> None:
        self._client = client

    async def __aenter__(self):  # noqa: ANN001, ANN201
        return self._client

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN201
        await getattr(self._client, "aclose")()
