"""Library-specific exceptions for DSMR parsing and Homey WebSocket transport."""

from __future__ import annotations


class TelegramParseError(Exception):
    """Raised when a complete DSMR telegram string cannot be parsed."""


class TelegramChecksumError(TelegramParseError):
    """Raised when the telegram CRC does not match the expected value."""


class HomeyWebSocketError(Exception):
    """Base for WebSocket errors raised by the client."""

    def __init__(
        self,
        message: str,
        *,
        close_code: int | None = None,
        close_reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.close_code = close_code
        self.close_reason = close_reason


class LocalApiDisabledError(HomeyWebSocketError):
    """Raised when the server closes with 1008 because the local API is disabled."""


class ConnectionLimitError(HomeyWebSocketError):
    """Raised on 1008 when the two WebSocket connection limit was reached."""


class ConnectionLostError(HomeyWebSocketError):
    """Raised when a ``reconnect=False`` client cannot connect or gets disconnected.

    Lets callers mark the device unavailable and own the retry policy instead of
    the client reconnecting silently.
    """
