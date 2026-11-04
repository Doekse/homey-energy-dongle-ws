"""Parsing of assembled DSMR payloads via ``dsmr_parser``."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dsmr_parser import telegram_specifications
from dsmr_parser.exceptions import InvalidChecksumError, ParseError
from dsmr_parser.objects import Telegram
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


def _parse(parser: TelegramParser, telegram_str: str) -> Telegram:
    """Run ``parser.parse`` and map ``dsmr_parser`` errors to library exceptions."""
    try:
        return parser.parse(telegram_str)
    except InvalidChecksumError as exc:
        raise TelegramChecksumError("DSMR telegram checksum validation failed") from exc
    except ParseError as exc:
        raise TelegramParseError("Failed to parse DSMR telegram") from exc


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
