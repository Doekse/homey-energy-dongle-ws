"""Tests for high-level stream helpers (mocked ``iter_raw_bytes``; no Energy Dongle)."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import patch

import pytest
from dsmr_parser import telegram_specifications as ts
from dsmr_parser.objects import Telegram

from homey_energy_dongle_ws.client import EnergyDongleClient
from homey_energy_dongle_ws.exceptions import TelegramParseError
from test_telegram_assembly import GOLDEN

# Same sample as ``tests/test_parser.py`` — parses under ``V3``.
GOLDEN_V3 = (
    "/FOO5\\2BAR\r\n"
    "1-3:0.2.8(42)(0)(0)(0)(0)\r\n"
    "!1234\r\n"
)


def _split_golden_chunks() -> list[bytes]:
    a, b = 7, 22
    return [
        GOLDEN[:a].encode("utf-8"),
        GOLDEN[a:b].encode("utf-8"),
        GOLDEN[b:].encode("utf-8"),
    ]


def test_stream_telegrams_from_chunked_raw() -> None:
    chunks = _split_golden_chunks()

    async def mock_iter_raw_bytes(self: EnergyDongleClient) -> object:
        for c in chunks:
            yield c

    async def run() -> None:
        client = EnergyDongleClient("127.0.0.1")
        with patch.object(
            EnergyDongleClient,
            "iter_raw_bytes",
            mock_iter_raw_bytes,
        ):
            out: list[str] = []
            async for t in client.stream_telegrams():
                out.append(t)
            assert out == [GOLDEN]

    asyncio.run(run())


def test_stream_parsed_skip_parse_errors(caplog: pytest.LogCaptureFixture) -> None:
    chunks = _split_golden_chunks()

    async def mock_iter_raw_bytes(self: EnergyDongleClient) -> object:
        for c in chunks:
            yield c

    def boom(
        telegram_str: str,
        *,
        telegram_specification: object,
        apply_checksum_validation: bool,
    ) -> None:
        raise TelegramParseError("bad telegram")

    async def run() -> None:
        caplog.set_level(logging.WARNING)
        client = EnergyDongleClient(
            "127.0.0.1",
            telegram_specification=ts.V3,
        )
        with (
            patch.object(
                EnergyDongleClient,
                "iter_raw_bytes",
                mock_iter_raw_bytes,
            ),
            patch("homey_energy_dongle_ws.client.parse_telegram", boom),
        ):
            count = 0
            async for _ in client.stream_parsed(skip_parse_errors=True):
                count += 1
            assert count == 0
        assert "Skipping telegram" in caplog.text

    asyncio.run(run())


def test_stream_parsed_yields_telegram() -> None:
    chunks = _split_golden_chunks()
    # GOLDEN matches assembly test; same string as GOLDEN_V3 in parser tests.
    assert GOLDEN == GOLDEN_V3

    async def mock_iter_raw_bytes(self: EnergyDongleClient) -> object:
        for c in chunks:
            yield c

    async def run() -> None:
        client = EnergyDongleClient(
            "127.0.0.1",
            telegram_specification=ts.V3,
        )
        with patch.object(
            EnergyDongleClient,
            "iter_raw_bytes",
            mock_iter_raw_bytes,
        ):
            count = 0
            async for telegram in client.stream_parsed():
                count += 1
                assert isinstance(telegram, Telegram)
            assert count == 1

    asyncio.run(run())


def test_second_stream_blocks_until_first_releases_lock() -> None:
    """Second stream waits while the first holds the lock on ``iter_raw_bytes``."""

    async def mock_iter_raw_bytes(self: EnergyDongleClient) -> object:
        yield b"x"
        await asyncio.Future()

    async def run() -> None:
        client = EnergyDongleClient("127.0.0.1")
        with patch.object(
            EnergyDongleClient,
            "iter_raw_bytes",
            mock_iter_raw_bytes,
        ):

            async def first_consumer() -> None:
                async for _ in client.stream_raw():
                    pass

            async def second_consumer() -> None:
                async for _ in client.stream_raw():
                    break

            t1 = asyncio.create_task(first_consumer())
            await asyncio.sleep(0)
            t2 = asyncio.create_task(second_consumer())
            await asyncio.sleep(0)
            assert not t2.done()

            t1.cancel()
            try:
                await t1
            except asyncio.CancelledError:
                pass
            await asyncio.wait_for(t2, timeout=2.0)

    asyncio.run(run())


def test_stream_raw_matches_iter_raw_bytes_under_mock() -> None:
    chunks = [b"a", b"b"]

    async def mock_iter_raw_bytes(self: EnergyDongleClient) -> object:
        for c in chunks:
            yield c

    async def run() -> None:
        client = EnergyDongleClient("127.0.0.1")
        with patch.object(
            EnergyDongleClient,
            "iter_raw_bytes",
            mock_iter_raw_bytes,
        ):
            raw = [x async for x in client.stream_raw()]
            direct = [x async for x in client.iter_raw_bytes()]
            assert raw == direct == chunks

    asyncio.run(run())
