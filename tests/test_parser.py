"""Tests for ``parse_telegram``."""

from __future__ import annotations

import pytest
from dsmr_parser import telegram_specifications as ts
from dsmr_parser.objects import Telegram

from homey_energy_dongle_ws.exceptions import TelegramChecksumError, TelegramParseError
from homey_energy_dongle_ws.parser import parse_telegram
from samples import GOLDEN, TELEGRAM_V2_2_GAS, TELEGRAM_V4_GAS


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


@pytest.mark.parametrize(
    ("telegram_str", "specification", "identifier", "reading"),
    [
        pytest.param(
            TELEGRAM_V4_GAS,
            ts.V4,
            "4819243993373755377509728609491464",
            "981.443",
            id="dsmr4",
        ),
        pytest.param(TELEGRAM_V2_2_GAS, ts.V2_2, "000000000000", "1.001", id="dsmr2.2"),
    ],
)
def test_legacy_gas_meter_uses_mbus_names(
    telegram_str: str, specification: dict[str, object], identifier: str, reading: str
) -> None:
    """DSMR 2.2 and 4 gas meters read like DSMR 5 M-Bus devices."""
    (device,) = parse_telegram(
        telegram_str, telegram_specification=specification
    ).MBUS_DEVICES

    assert device.MBUS_DEVICE_TYPE.value == 3
    assert device.MBUS_EQUIPMENT_IDENTIFIER.value == identifier
    assert str(device.MBUS_METER_READING.value) == reading
    assert device.MBUS_METER_READING.unit == "m3"
    assert "MBUS_METER_READING" not in dict(device)


def test_garbage_raises_telegram_parse_error() -> None:
    """Unstructured text fails when the spec expects a framed telegram with CRC."""
    with pytest.raises(TelegramParseError):
        parse_telegram("not a telegram", telegram_specification=ts.V4)
