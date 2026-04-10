"""Library-specific exceptions for DSMR parsing and Homey WebSocket transport."""

from __future__ import annotations

from websockets.exceptions import ConnectionClosed


class TelegramParseError(Exception):
    """Raised when a complete DSMR telegram string cannot be parsed."""


class TelegramChecksumError(TelegramParseError):
    """Raised when the telegram CRC does not match the expected value."""


class HomeyWebSocketError(Exception):
    """Base for unrecoverable WebSocket policy or configuration errors."""

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

    def __init__(
        self,
        reason: str = "",
        *,
        close_code: int = 1008,
        close_reason: str | None = None,
    ) -> None:
        text = (reason or "").strip() or "Local API disabled"
        super().__init__(
            text,
            close_code=close_code,
            close_reason=close_reason if close_reason is not None else reason,
        )


class ConnectionLimitError(HomeyWebSocketError):
    """Raised on 1008 when the two WebSocket connection limit was reached."""

    def __init__(
        self,
        reason: str = "",
        *,
        close_code: int = 1008,
        close_reason: str | None = None,
    ) -> None:
        text = (reason or "").strip() or "Connection limit reached"
        super().__init__(
            text,
            close_code=close_code,
            close_reason=close_reason if close_reason is not None else reason,
        )


def _close_code_and_reason(exc: ConnectionClosed) -> tuple[int, str]:
    """Best-effort close code and reason from ``ConnectionClosed``."""
    if exc.rcvd is not None:
        return int(exc.rcvd.code), exc.rcvd.reason
    if exc.sent is not None:
        return int(exc.sent.code), exc.sent.reason
    return 1006, ""


def _raise_for_homey_close(code: int, reason: str) -> None:
    """Map Athom **1008** reasons to specific errors; no-op for other codes.

    Other codes are treated as recoverable by the client's reconnect loop.
    Unknown **1008** reasons still abort reconnection (policy rejection).
    """
    if code != 1008:
        return
    text = (reason or "").strip()
    if "Local API disabled" in text:
        raise LocalApiDisabledError(
            reason,
            close_code=code,
            close_reason=reason,
        ) from None
    if "Connection limit reached" in text:
        raise ConnectionLimitError(
            reason,
            close_code=code,
            close_reason=reason,
        ) from None
    msg = f"WebSocket policy violation (1008): {reason!r}"
    raise HomeyWebSocketError(
        msg,
        close_code=code,
        close_reason=reason,
    ) from None
