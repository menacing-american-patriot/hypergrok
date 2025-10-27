"""Command-line entry point for Hypergrok."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from hypergrok.config import AppConfig
from hypergrok.engine import TradingEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Hypergrok trading engine")
    parser.add_argument("--config", type=Path, help="Path to JSON config file", required=False)
    parser.add_argument("--env", type=Path, help="Path to .env file", required=False)
    parser.add_argument("--cycles", type=int, help="Number of trading cycles to run", required=False)
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser.parse_args()


def load_config(args: argparse.Namespace) -> AppConfig:
    if args.config:
        return AppConfig.from_file(args.config)
    return AppConfig.from_env(args.env)


async def main_async(args: argparse.Namespace) -> None:
    config = load_config(args)
    async with TradingEngine(config) as engine:
        await engine.run(cycles=args.cycles)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
