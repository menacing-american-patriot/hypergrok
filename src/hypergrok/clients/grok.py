"""HTTP client for interacting with the Grok AI trading model."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable

import httpx

from hypergrok.models import MarketSnapshot, TradeSignal, OrderSide


class GrokClient:
    def __init__(self, *, api_url: str, api_key: str, model: str, temperature: float, max_tokens: int) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = httpx.AsyncClient(timeout=30.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def generate_signal(self, market_data: Iterable[MarketSnapshot]) -> TradeSignal:
        payload = {
            "model": self._model,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a quantitative crypto trading assistant. Produce concise JSON instructions.",
                },
                {
                    "role": "user",
                    "content": self._build_prompt(market_data),
                },
            ],
        }

        response = await self._client.post(
            f"{self._api_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            content=json.dumps(payload),
        )
        response.raise_for_status()
        content = response.json()
        message = content["choices"][0]["message"]["content"]
        return self._parse_signal(message)

    def _build_prompt(self, market_data: Iterable[MarketSnapshot]) -> str:
        snapshots = [snapshot.dict() for snapshot in market_data]
        return (
            "Given the following Hyperliquid market snapshots, recommend a single trade instruction as JSON with the"
            " fields: symbol, side ('buy'/'sell'), size, leverage, confidence (0-1), and narrative."
            f"\n\nSnapshots:\n{json.dumps(snapshots, default=str)}"
        )

    def _parse_signal(self, message: str) -> TradeSignal:
        try:
            parsed: Dict[str, Any] = json.loads(_extract_json_block(message))
            return TradeSignal(
                symbol=parsed["symbol"],
                side=OrderSide(parsed["side"].lower()),
                size=float(parsed["size"]),
                leverage=float(parsed.get("leverage", 1.0)) if parsed.get("leverage") else None,
                confidence=float(parsed.get("confidence", 0.5)),
                narrative=parsed.get("narrative"),
            )
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Unable to parse Grok response: {message}") from exc


def _extract_json_block(message: str) -> str:
    start = message.find("{")
    end = message.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in Grok response")
    return message[start : end + 1]
