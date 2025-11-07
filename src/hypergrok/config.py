"""Configuration models and loaders for the Hypergrok trading system."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, HttpUrl, ValidationError


class WalletConfig(BaseModel):
    base_asset: str = Field(..., min_length=1)
    initial_balance: float = Field(..., gt=0)
    min_cash_reserve: float = Field(0.0, ge=0)


class RiskConfig(BaseModel):
    max_position_size: float = Field(..., gt=0)
    max_leverage: float = Field(..., gt=0)
    max_daily_loss: float = Field(..., ge=0)


class HyperliquidConfig(BaseModel):
    base_url: HttpUrl
    api_key: str = Field(..., min_length=10)
    api_secret: str = Field(..., min_length=10)
    subaccount: Optional[str] = None
    account_address: Optional[str] = None


class GrokConfig(BaseModel):
    api_url: HttpUrl
    api_key: str = Field(..., min_length=10)
    model: str = Field(default="grok-beta")
    temperature: float = Field(default=0.1, ge=0, le=2)
    max_tokens: int = Field(default=512, gt=0)


class StrategyConfig(BaseModel):
    poll_interval_seconds: float = Field(default=5.0, gt=0)
    trading_pairs: List[str] = Field(default_factory=lambda: ["BTC-PERP"])
    enable_live_trading: bool = False
    auto_max_profit: bool = False
    auto_target_leverage: float = Field(default=3.0, gt=0)
    auto_position_fraction: float = Field(default=1.0, gt=0, le=1.0)


class AppConfig(BaseModel):
    wallet: WalletConfig
    risk: RiskConfig
    hyperliquid: HyperliquidConfig
    grok: GrokConfig
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)

    @classmethod
    def from_env(cls, env_path: Optional[Path] = None) -> "AppConfig":
        load_dotenv(dotenv_path=env_path if env_path else None)

        wallet_base_asset = _require_env("WALLET_BASE_ASSET")
        wallet_initial_balance = float(_require_env("WALLET_INITIAL_BALANCE"))
        wallet_min_reserve = float(_get_env("WALLET_MIN_CASH_RESERVE", 0.0))

        auto_max_profit = _parse_bool(_get_env("STRATEGY_AUTO_MAX_PROFIT", "false"))
        auto_target_leverage = float(_get_env("STRATEGY_AUTO_TARGET_LEVERAGE", 3.0))
        auto_position_fraction = float(_get_env("STRATEGY_AUTO_POSITION_FRACTION", 1.0))

        risk_max_position_raw = _get_env("RISK_MAX_POSITION")
        if risk_max_position_raw is None:
            if auto_max_profit:
                risk_max_position = wallet_initial_balance * 10
            else:
                raise RuntimeError("Environment variable RISK_MAX_POSITION is required")
        else:
            risk_max_position = float(risk_max_position_raw)

        risk_max_leverage_raw = _get_env("RISK_MAX_LEVERAGE")
        if risk_max_leverage_raw is None:
            if auto_max_profit:
                risk_max_leverage = max(auto_target_leverage, 1.0)
            else:
                raise RuntimeError("Environment variable RISK_MAX_LEVERAGE is required")
        else:
            risk_max_leverage = float(risk_max_leverage_raw)

        risk_max_daily_loss_raw = _get_env("RISK_MAX_DAILY_LOSS")
        if risk_max_daily_loss_raw is None:
            if auto_max_profit:
                risk_max_daily_loss = wallet_initial_balance
            else:
                raise RuntimeError("Environment variable RISK_MAX_DAILY_LOSS is required")
        else:
            risk_max_daily_loss = float(risk_max_daily_loss_raw)

        trading_pairs_raw = _get_env("STRATEGY_TRADING_PAIRS", "BTC-PERP")
        trading_pairs = [pair.strip() for pair in trading_pairs_raw.split(",") if pair.strip()]

        env_mapping = {
            "wallet": {
                "base_asset": wallet_base_asset,
                "initial_balance": wallet_initial_balance,
                "min_cash_reserve": wallet_min_reserve,
            },
            "risk": {
                "max_position_size": risk_max_position,
                "max_leverage": risk_max_leverage,
                "max_daily_loss": risk_max_daily_loss,
            },
            "hyperliquid": {
                "base_url": _require_env("HYPERLIQUID_BASE_URL"),
                "api_key": _require_env("HYPERLIQUID_API_KEY"),
                "api_secret": _require_env("HYPERLIQUID_API_SECRET"),
                "subaccount": _get_env("HYPERLIQUID_SUBACCOUNT"),
                "account_address": _get_env("HYPERLIQUID_ACCOUNT_ADDRESS"),
            },
            "grok": {
                "api_url": _require_env("GROK_API_URL"),
                "api_key": _require_env("GROK_API_KEY"),
                "model": _get_env("GROK_MODEL", "grok-beta"),
                "temperature": float(_get_env("GROK_TEMPERATURE", 0.1)),
                "max_tokens": int(_get_env("GROK_MAX_TOKENS", 512)),
            },
            "strategy": {
                "poll_interval_seconds": float(_get_env("STRATEGY_POLL_INTERVAL", 5.0)),
                "trading_pairs": trading_pairs,
                "enable_live_trading": _parse_bool(_get_env("STRATEGY_ENABLE_LIVE", "false")),
                "auto_max_profit": auto_max_profit,
                "auto_target_leverage": auto_target_leverage,
                "auto_position_fraction": auto_position_fraction,
            },
        }

        try:
            return cls(**env_mapping)
        except ValidationError as exc:
            raise RuntimeError(f"Invalid configuration: {exc}") from exc

    @classmethod
    def from_file(cls, path: Path) -> "AppConfig":
        data = _load_config_file(path)
        try:
            return cls(**data)
        except ValidationError as exc:
            raise RuntimeError(f"Invalid configuration file: {exc}") from exc


def _load_config_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    import json

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _require_env(key: str) -> str:
    value = _get_env(key)
    if value is None:
        raise RuntimeError(f"Environment variable {key} is required")
    return value


def _get_env(key: str, default: Optional[object] = None) -> Optional[str]:
    import os

    value = os.getenv(key)
    if value is None:
        return None if default is None else str(default)
    return value


def _parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}
