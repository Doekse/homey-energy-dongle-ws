"""Optional live tests against a real Homey Energy Dongle (opt-in via env)."""

from __future__ import annotations

import asyncio
import os

import pytest

from homey_energy_dongle_ws.client import EnergyDongleClient

pytestmark = pytest.mark.integration

LIVE_HOST = os.environ.get("HOMEY_ENERGY_DONGLE_HOST")


@pytest.mark.skipif(
    not LIVE_HOST,
    reason=(
        "Set HOMEY_ENERGY_DONGLE_HOST to the Energy Dongle IP/hostname for live tests."
    ),
)
def test_live_stream_parsed_one_telegram() -> None:
    """Connect and receive at least one parsed telegram within a bounded wait."""

    async def run() -> None:
        assert LIVE_HOST is not None
        async with EnergyDongleClient(LIVE_HOST) as client:

            async def first_telegram() -> object:
                async for telegram in client.stream_parsed():
                    return telegram
                raise AssertionError("stream ended without a telegram")

            telegram = await asyncio.wait_for(first_telegram(), timeout=120.0)
            assert telegram is not None

    asyncio.run(run())
