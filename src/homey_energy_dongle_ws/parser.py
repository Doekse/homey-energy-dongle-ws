"""Parsing of assembled DSMR payloads via ``dsmr_parser``."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from dsmr_parser import telegram_specifications
from dsmr_parser.exceptions import InvalidChecksumError, ParseError
from dsmr_parser.objects import CosemObject, Telegram
from dsmr_parser.parsers import TelegramParser

from homey_energy_dongle_ws.exceptions import TelegramChecksumError, TelegramParseError

# Same version codes and specifications as ``dsmr_parser``'s serial reader; the
# encrypted variants are left out because telegrams are not decrypted here.
TELEGRAM_SPECIFICATIONS: Mapping[str, Mapping[str, Any]] = {
    "5": telegram_specifications.V5,
    "5B": telegram_specifications.BELGIUM_FLUVIUS,
    "5L": telegram_specifications.LUXEMBOURG_SMARTY,
    "5S": telegram_specifications.SWEDEN,
    "Q3D": telegram_specifications.Q3D,
    "5EONHU": telegram_specifications.EON_HUNGARY,
    "4": telegram_specifications.V4,
    "2.2": telegram_specifications.V2_2,
}
DSMR_VERSIONS: tuple[str, ...] = tuple(TELEGRAM_SPECIFICATIONS)

# DSMR 2.2 and 4 field names of the gas meter, with their DSMR 5 M-Bus name.
_LEGACY_MBUS_NAMES: Mapping[str, str] = {
    "DEVICE_TYPE": "MBUS_DEVICE_TYPE",
    "EQUIPMENT_IDENTIFIER_GAS": "MBUS_EQUIPMENT_IDENTIFIER",
    "HOURLY_GAS_METER_READING": "MBUS_METER_READING",
    "GAS_METER_READING": "MBUS_METER_READING",
}

# OBIS id without the channel. Q3D inserts ``*255`` before the value group.
_OBIS_LINE = re.compile(r"(?m)^[0-9]-[0-9]:([0-9]+(?:\.[0-9]+)*)(?:\*\d+)?\(([^)]*)\)")
_CHECKSUM_LINE = re.compile(r"(?m)^![0-9A-Fa-f]{1,4}\r?$")


def _obis_values(telegram: str) -> dict[str, str]:
    """Return the first value of each OBIS id in ``telegram``."""
    values: dict[str, str] = {}
    for code, value in _OBIS_LINE.findall(telegram):
        values.setdefault(code, value)
    return values


def detect_dsmr_version(telegram: str) -> str | None:
    """Return the ``DSMR_VERSIONS`` code for one telegram, or ``None``.

    Country profiles are tested before ``1-3:0.2.8``. Luxembourg writes ``42``
    there, and Belgian meters share Hungary's extra tariff registers. Reactive
    energy with neither an equipment id nor tariff 1 is Swedish. DSMR 3 has no
    checksum and uses the ``2.2`` specification. ``None`` means the telegram
    matched no supported profile.
    """
    obis = _obis_values(telegram)
    if "96.1.4" in obis or "1.4.0" in obis:
        return "5B"
    if ("1.8.3" in obis and "1.8.4" in obis) or "14.7.0" in obis:
        return "5EONHU"
    if "42.0.0" in obis:
        return "5L"
    if "96.1.255" in obis:
        return "Q3D"
    if (
        "96.1.1" not in obis
        and "1.8.1" not in obis
        and ("23.7.0" in obis or "3.8.0" in obis)
    ):
        return "5S"
    version = obis.get("0.2.8", "")
    if version[:1] in {"4", "5"} and version[1:].isdigit():
        return version[:1]
    if (
        telegram.startswith("/")
        and "!" in telegram
        and _CHECKSUM_LINE.search(telegram) is None
    ):
        return "2.2"
    return None


def _alias_legacy_mbus(telegram: Telegram) -> None:
    """Expose DSMR 2.2 and 4 gas meter fields under the DSMR 5 M-Bus names.

    The aliases are attributes only, so iteration and ``to_json()`` are unchanged.
    """
    for device in getattr(telegram, "MBUS_DEVICES", []):
        for legacy, name in _LEGACY_MBUS_NAMES.items():
            obj = getattr(device, legacy, None)
            if obj is None or hasattr(device, name):
                continue
            if name == "MBUS_DEVICE_TYPE" and isinstance(obj.value, str):
                # DSMR 2.2 sends the type as text; DSMR 5 parses it as a number.
                if not obj.value.isdigit():
                    continue
                obj = CosemObject(
                    obj.obis_id_code, [{"value": int(obj.value), "unit": ""}]
                )
            setattr(device, name, obj)


def _parse(parser: TelegramParser, telegram_str: str) -> Telegram:
    """Run ``parser.parse`` and map ``dsmr_parser`` errors to library exceptions."""
    try:
        telegram = parser.parse(telegram_str)
    except InvalidChecksumError as exc:
        raise TelegramChecksumError("DSMR telegram checksum validation failed") from exc
    # dsmr_parser re-raises value conversion errors (Decimal, int) unwrapped.
    except (ParseError, ValueError, ArithmeticError) as exc:
        raise TelegramParseError("Failed to parse DSMR telegram") from exc
    _alias_legacy_mbus(telegram)
    return telegram


def parse_telegram(
    telegram_str: str,
    *,
    telegram_specification: Mapping[str, Any] = telegram_specifications.V5,
    apply_checksum_validation: bool = True,
) -> Telegram:
    """Parse a full DSMR telegram string into a ``dsmr_parser`` ``Telegram``.

    ``telegram_str`` must be a complete telegram (from ``/`` through ``!`` and CRC
    line endings), such as strings yielded by ``TelegramAssembler``.

    Args:
        telegram_str: Raw telegram text.
        telegram_specification: OBIS specification (for example ``V3`` or ``V5``).
        apply_checksum_validation: When ``True``, validate the CRC where the spec
            supports it.

    Returns:
        Parsed ``Telegram`` instance (same type as ``TelegramParser.parse``).

    Raises:
        TelegramChecksumError: When checksum validation fails.
        TelegramParseError: When parsing fails for any other reason.
    """
    return _parse(
        TelegramParser(
            telegram_specification,
            apply_checksum_validation=apply_checksum_validation,
        ),
        telegram_str,
    )
