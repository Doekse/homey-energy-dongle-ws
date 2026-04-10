"""Tests for ``TelegramAssembler``."""

from __future__ import annotations

from homey_energy_dongle_ws.telegram_assembly import TelegramAssembler

# Minimal telegram matching dsmr_parser's framing regex (``/`` … ``!`` + hex + CRLF).
GOLDEN = (
    "/FOO5\\2BAR\r\n"
    "1-3:0.2.8(42)(0)(0)(0)(0)\r\n"
    "!1234\r\n"
)


def test_one_telegram_split_across_chunks() -> None:
    asm = TelegramAssembler()
    a, b = 7, 22
    chunks = [
        GOLDEN[:a].encode("utf-8"),
        GOLDEN[a:b].encode("utf-8"),
        GOLDEN[b:].encode("utf-8"),
    ]
    assert len(chunks) >= 3
    assembled: list[str] = []
    for chunk in chunks:
        assembled.extend(asm.feed(chunk))
    assert assembled == [GOLDEN]


def test_two_telegrams_in_one_chunk() -> None:
    asm = TelegramAssembler()
    combined = (GOLDEN + GOLDEN).encode("utf-8")
    assert list(asm.feed(combined)) == [GOLDEN, GOLDEN]


def test_partial_feeds_then_completion() -> None:
    asm = TelegramAssembler()
    bang = GOLDEN.index("!")
    assert list(asm.feed_str(GOLDEN[:bang])) == []
    tail = GOLDEN[bang:]
    assert list(asm.feed_str(tail[:2])) == []
    assert list(asm.feed_str(tail[2:])) == [GOLDEN]
