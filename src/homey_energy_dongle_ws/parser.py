"""Parsing of assembled DSMR payloads via ``dsmr_parser``."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dsmr_parser import telegram_specifications
from dsmr_parser.exceptions import InvalidChecksumError, ParseError
from dsmr_parser.objects import Telegram
from dsmr_parser.parsers import TelegramParser

from homey_energy_dongle_ws.exceptions import TelegramChecksumError, TelegramParseError


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
    parser = TelegramParser(
        telegram_specification,
        apply_checksum_validation=apply_checksum_validation,
    )
    try:
        return parser.parse(telegram_str)
    except InvalidChecksumError as exc:
        raise TelegramChecksumError("DSMR telegram checksum validation failed") from exc
    except ParseError as exc:
        raise TelegramParseError("Failed to parse DSMR telegram") from exc
