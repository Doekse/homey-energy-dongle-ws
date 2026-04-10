"""Tests for WebSocket transport (mocked; no real Energy Dongle)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

from homey_energy_dongle_ws.client import EnergyDongleClient, build_ws_url
from homey_energy_dongle_ws.constants import RECONNECT_DELAY_S
from homey_energy_dongle_ws.exceptions import (
    ConnectionLimitError,
    HomeyWebSocketError,
    LocalApiDisabledError,
    _raise_for_homey_close,
)
from homey_energy_dongle_ws.models import EnergyDongleConnectionSettings


def test_build_ws_url_defaults_match_constants() -> None:
    assert build_ws_url("homey.local") == "ws://homey.local:80/ws"


def test_build_ws_url_ipv6_uses_brackets() -> None:
    assert build_ws_url("2001:db8::5") == "ws://[2001:db8::5]:80/ws"


def test_build_ws_url_ipv4_unchanged() -> None:
    assert build_ws_url("192.168.0.1") == "ws://192.168.0.1:80/ws"


def test_raise_for_homey_close_local_api() -> None:
    with pytest.raises(LocalApiDisabledError):
        _raise_for_homey_close(1008, "Local API disabled")


def test_raise_for_homey_close_limit() -> None:
    with pytest.raises(ConnectionLimitError):
        _raise_for_homey_close(1008, "Connection limit reached")


def test_raise_for_homey_close_unknown_1008() -> None:
    with pytest.raises(HomeyWebSocketError):
        _raise_for_homey_close(1008, "other policy")


def test_raise_for_homey_close_non_1008_noop() -> None:
    _raise_for_homey_close(1011, "oops")


def test_raise_for_homey_close_sets_close_metadata_on_local_api() -> None:
    with pytest.raises(LocalApiDisabledError) as ctx:
        _raise_for_homey_close(1008, "Local API disabled")
    assert ctx.value.close_code == 1008
    assert ctx.value.close_reason == "Local API disabled"


def test_raise_for_homey_close_sets_close_metadata_on_unknown_1008() -> None:
    with pytest.raises(HomeyWebSocketError) as ctx:
        _raise_for_homey_close(1008, "other policy")
    assert ctx.value.close_code == 1008
    assert ctx.value.close_reason == "other policy"


def test_iter_raw_bytes_raises_local_api_disabled() -> None:
    class FailingSocket:
        def __aiter__(self) -> FailingSocket:
            return self

        async def __anext__(self) -> bytes:
            raise ConnectionClosedError(
                rcvd=Close(1008, "Local API disabled"),
                sent=None,
            )

        async def close(self) -> None:
            return None

    class ConnectCtx:
        async def __aenter__(self) -> FailingSocket:
            return FailingSocket()

        async def __aexit__(self, *a: object) -> None:
            return None

    def mock_connect(*a: object, **k: object) -> ConnectCtx:
        return ConnectCtx()

    async def run() -> None:
        client = EnergyDongleClient("127.0.0.1")
        with patch("homey_energy_dongle_ws.client.connect", mock_connect):
            agen = client.iter_raw_bytes()
            with pytest.raises(LocalApiDisabledError):
                await agen.__anext__()

    asyncio.run(run())


def test_iter_raw_bytes_raises_connection_limit() -> None:
    class FailingSocket:
        def __aiter__(self) -> FailingSocket:
            return self

        async def __anext__(self) -> bytes:
            raise ConnectionClosedError(
                rcvd=Close(1008, "Connection limit reached"),
                sent=None,
            )

        async def close(self) -> None:
            return None

    class ConnectCtx:
        async def __aenter__(self) -> FailingSocket:
            return FailingSocket()

        async def __aexit__(self, *a: object) -> None:
            return None

    def mock_connect(*a: object, **k: object) -> ConnectCtx:
        return ConnectCtx()

    async def run() -> None:
        client = EnergyDongleClient("127.0.0.1")
        with patch("homey_energy_dongle_ws.client.connect", mock_connect):
            agen = client.iter_raw_bytes()
            with pytest.raises(ConnectionLimitError):
                await agen.__anext__()

    asyncio.run(run())


def test_reconnect_uses_reconnect_delay_after_oserror() -> None:
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)
        await asyncio.sleep(0)

    class ConnectCtx:
        async def __aenter__(self) -> object:
            raise OSError("connection refused")

        async def __aexit__(self, *a: object) -> None:
            return None

    def mock_connect(*a: object, **k: object) -> ConnectCtx:
        return ConnectCtx()

    async def run() -> None:
        client = EnergyDongleClient("127.0.0.1")

        async def wait_for_first_sleep() -> None:
            agen = client.iter_raw_bytes()
            await agen.__anext__()

        sleep_patch = patch(
            "homey_energy_dongle_ws.client._sleep_reconnect_delay",
            record_sleep,
        )
        with patch("homey_energy_dongle_ws.client.connect", mock_connect), sleep_patch:
            task = asyncio.create_task(wait_for_first_sleep())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run())

    assert sleeps and sleeps[0] == RECONNECT_DELAY_S


def test_from_settings_builds_same_url() -> None:
    s = EnergyDongleConnectionSettings(host="x.test")
    c = EnergyDongleClient.from_settings(s)
    assert c.ws_url == "ws://x.test:80/ws"
