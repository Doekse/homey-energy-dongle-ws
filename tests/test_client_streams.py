"""Tests for high-level stream helpers (mocked ``iter_raw_bytes``; no Energy Dongle)."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import patch

import pytest
from dsmr_parser import telegram_specifications as ts
from dsmr_parser.objects import Telegram
from dsmr_parser.parsers import TelegramParser

from homey_energy_dongle_ws.client import EnergyDongleClient
from homey_energy_dongle_ws.exceptions import TelegramParseError
from samples import GOLDEN


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


def _v4_crc_telegram(text: str) -> str:
    """Return *text* with a CRC that passes V4 checksum validation."""
    body = text[: text.index("!") + 1]
    crc = TelegramParser.crc16(body)
    return f"{body}{crc:04X}\r\n"


def test_stream_parsed_skips_non_ascii_corrupt_telegram_and_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-ASCII wire bytes are replaced, fail checksum, and do not stop the stream."""
    good = _v4_crc_telegram(GOLDEN)
    corrupt = bytearray(good.encode("ascii"))
    corrupt[corrupt.index(b"FOO") + 1] = 0xFF
    chunks = [bytes(corrupt), good.encode("ascii")]

    async def mock_iter_raw_bytes(self: EnergyDongleClient) -> object:
        for c in chunks:
            yield c

    async def run() -> None:
        caplog.set_level(logging.WARNING)
        client = EnergyDongleClient(
            "127.0.0.1",
            telegram_specification=ts.V4,
        )
        with patch.object(
            EnergyDongleClient,
            "iter_raw_bytes",
            mock_iter_raw_bytes,
        ):
            out: list[Telegram] = []
            async for telegram in client.stream_parsed(skip_parse_errors=True):
                out.append(telegram)
            assert len(out) == 1
            assert isinstance(out[0], Telegram)
        assert "Skipping telegram" in caplog.text

    asyncio.run(run())


def test_stream_parsed_yields_telegram() -> None:
    chunks = _split_golden_chunks()

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
