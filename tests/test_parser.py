"""Tests for ``parse_telegram``."""

from __future__ import annotations

import pytest
from dsmr_parser import telegram_specifications as ts
from dsmr_parser.objects import Telegram

from homey_energy_dongle_ws.exceptions import TelegramChecksumError, TelegramParseError
from homey_energy_dongle_ws.parser import parse_telegram
from samples import GOLDEN


def test_golden_complete_telegram_parses() -> None:
    result = parse_telegram(GOLDEN, telegram_specification=ts.V3)
    assert isinstance(result, Telegram)


def test_wrong_spec_raises_telegram_checksum_error() -> None:
    """Same string with a spec whose CRC rules do not match the sample footer."""
    with pytest.raises(TelegramChecksumError) as ctx:
        parse_telegram(GOLDEN, telegram_specification=ts.V4)
    assert isinstance(ctx.value.__cause__, Exception)


def test_truncated_telegram_raises_telegram_parse_error() -> None:
    incomplete = "/FOO5\\2BAR\r\n"
    with pytest.raises(TelegramParseError) as ctx:
        parse_telegram(incomplete, telegram_specification=ts.V4)
    assert isinstance(ctx.value.__cause__, Exception)


def test_garbage_raises_telegram_parse_error() -> None:
    """Unstructured text fails when the spec expects a framed telegram with CRC."""
    with pytest.raises(TelegramParseError):
        parse_telegram("not a telegram", telegram_specification=ts.V4)
