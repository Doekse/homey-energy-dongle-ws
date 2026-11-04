"""Tests for WebSocket transport (mocked; no real Energy Dongle)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from dsmr_parser import telegram_specifications as ts
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosedError, InvalidStatus
from websockets.frames import Close
from websockets.http11 import Response

from homey_energy_dongle_ws.client import EnergyDongleClient, build_ws_url
from homey_energy_dongle_ws.constants import RECONNECT_DELAY_S
from homey_energy_dongle_ws.exceptions import (
    ConnectionLimitError,
    ConnectionLostError,
    HomeyWebSocketError,
    LocalApiDisabledError,
    _raise_for_homey_close,
)
from homey_energy_dongle_ws.models import EnergyDongleConnectionSettings


def _fake_connect(
    socket: object | None = None,
    *,
    raises: BaseException | None = None,
) -> object:
    """Return a ``connect`` stand-in that yields ``socket`` or raises ``raises``."""

    class ConnectCtx:
        async def __aenter__(self) -> object:
            if raises is not None:
                raise raises
            return socket

        async def __aexit__(self, *a: object) -> None:
            return None

    def mock_connect(*a: object, **k: object) -> ConnectCtx:
        return ConnectCtx()

    return mock_connect


class _ClosedSocket:
    def __aiter__(self) -> _ClosedSocket:
        return self

    async def __anext__(self) -> bytes:
        raise StopAsyncIteration


class _PolicyCloseSocket:
    def __init__(self, reason: str) -> None:
        self._reason = reason

    def __aiter__(self) -> _PolicyCloseSocket:
        return self

    async def __anext__(self) -> bytes:
        raise ConnectionClosedError(
            rcvd=Close(1008, self._reason),
            sent=None,
        )

    async def close(self) -> None:
        return None


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
    async def run() -> None:
        client = EnergyDongleClient("127.0.0.1")
        with patch(
            "homey_energy_dongle_ws.client.connect",
            _fake_connect(_PolicyCloseSocket("Local API disabled")),
        ):
            agen = client.iter_raw_bytes()
            with pytest.raises(LocalApiDisabledError):
                await agen.__anext__()

    asyncio.run(run())


def test_iter_raw_bytes_raises_connection_limit() -> None:
    async def run() -> None:
        client = EnergyDongleClient("127.0.0.1")
        with patch(
            "homey_energy_dongle_ws.client.connect",
            _fake_connect(_PolicyCloseSocket("Connection limit reached")),
        ):
            agen = client.iter_raw_bytes()
            with pytest.raises(ConnectionLimitError):
                await agen.__anext__()

    asyncio.run(run())


def _invalid_status() -> InvalidStatus:
    return InvalidStatus(Response(503, "Service Unavailable", Headers()))


def _connect_errors() -> tuple[BaseException, ...]:
    return (OSError("connection refused"), _invalid_status())


@pytest.mark.parametrize(
    "connect_error",
    _connect_errors(),
    ids=["oserror", "invalid_handshake"],
)
def test_reconnect_uses_reconnect_delay_after_connect_error(
    connect_error: BaseException,
) -> None:
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)
        await asyncio.sleep(0)

    async def run() -> None:
        client = EnergyDongleClient("127.0.0.1")

        async def wait_for_first_sleep() -> None:
            agen = client.iter_raw_bytes()
            await agen.__anext__()

        sleep_patch = patch(
            "homey_energy_dongle_ws.client._sleep_reconnect_delay",
            record_sleep,
        )
        with (
            patch(
                "homey_energy_dongle_ws.client.connect",
                _fake_connect(raises=connect_error),
            ),
            sleep_patch,
        ):
            task = asyncio.create_task(wait_for_first_sleep())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run())

    assert sleeps and sleeps[0] == RECONNECT_DELAY_S


@pytest.mark.parametrize(
    "connect_error",
    _connect_errors(),
    ids=["oserror", "invalid_handshake"],
)
def test_no_reconnect_raises_on_connect_failure(
    connect_error: BaseException,
) -> None:
    async def run() -> None:
        client = EnergyDongleClient("127.0.0.1", reconnect=False)
        with patch(
            "homey_energy_dongle_ws.client.connect",
            _fake_connect(raises=connect_error),
        ):
            with pytest.raises(ConnectionLostError):
                await client.iter_raw_bytes().__anext__()

    asyncio.run(run())


def test_no_reconnect_raises_on_clean_close() -> None:
    async def run() -> None:
        client = EnergyDongleClient("127.0.0.1", reconnect=False)
        with patch(
            "homey_energy_dongle_ws.client.connect",
            _fake_connect(_ClosedSocket()),
        ):
            with pytest.raises(ConnectionLostError):
                await client.iter_raw_bytes().__anext__()

    asyncio.run(run())


def test_dsmr_version_selects_specification() -> None:
    client = EnergyDongleClient("127.0.0.1", dsmr_version="5B")
    assert client._telegram_specification is ts.BELGIUM_FLUVIUS


def test_unknown_dsmr_version_raises() -> None:
    with pytest.raises(ValueError):
        EnergyDongleClient("127.0.0.1", dsmr_version="MSn")


def test_from_settings_builds_same_url() -> None:
    s = EnergyDongleConnectionSettings(host="x.test")
    c = EnergyDongleClient.from_settings(s)
    assert c.ws_url == "ws://x.test:80/ws"
