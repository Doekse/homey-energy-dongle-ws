"""WebSocket client for the Homey Energy Dongle.

Uses :mod:`websockets` keepalive (``ping_interval`` / ``ping_timeout``) aligned with
Athom's ~10s behavior. TLS (``wss://``) is not implemented; use
:func:`~homey_energy_dongle_ws.discovery.discover_energy_dongles` for LAN discovery.

After transient failures, reconnection waits
:data:`~homey_energy_dongle_ws.constants.RECONNECT_DELAY_S`. Close code **1008** with
"Local API disabled" or "Connection limit reached" maps to specific exceptions and is
not retried in a tight loop.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
from collections.abc import AsyncIterator, Mapping
from typing import Any, Self

from dsmr_parser import telegram_specifications
from dsmr_parser.objects import Telegram
from dsmr_parser.parsers import TelegramParser
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from homey_energy_dongle_ws.constants import (
    DEFAULT_PORT,
    DEFAULT_WS_PATH,
    PING_INTERVAL_S,
    PING_TIMEOUT_S,
    RECONNECT_DELAY_S,
)
from homey_energy_dongle_ws.exceptions import (
    ConnectionLimitError,
    ConnectionLostError,
    HomeyWebSocketError,
    LocalApiDisabledError,
    TelegramParseError,
)
from homey_energy_dongle_ws.models import EnergyDongleConnectionSettings
from homey_energy_dongle_ws.parser import TELEGRAM_SPECIFICATIONS, _parse
from homey_energy_dongle_ws.telegram_assembly import TelegramAssembler

logger = logging.getLogger(__name__)


def _raise_for_policy_close(exc: ConnectionClosed) -> None:
    """Map Athom **1008** close reasons to specific errors; no-op otherwise.

    Other codes are treated as recoverable by the client's reconnect loop.
    Unknown **1008** reasons still abort reconnection (policy rejection).
    """
    if exc.rcvd is None or exc.rcvd.code != 1008:
        return
    reason = exc.rcvd.reason
    text = (reason or "").strip()
    if "Local API disabled" in text:
        raise LocalApiDisabledError(
            text,
            close_code=1008,
            close_reason=reason,
        ) from None
    if "Connection limit reached" in text:
        raise ConnectionLimitError(
            text,
            close_code=1008,
            close_reason=reason,
        ) from None
    raise HomeyWebSocketError(
        f"WebSocket policy violation (1008): {reason!r}",
        close_code=1008,
        close_reason=reason,
    ) from None


def _format_host_for_ws_url(host: str) -> str:
    """Return host suitable for authority in a ``ws://`` URL (brackets for IPv6)."""
    raw = host.strip()
    if not raw:
        return raw
    pct = raw.find("%")
    addr_part = raw[:pct] if pct != -1 else raw
    zone = raw[pct:] if pct != -1 else ""
    try:
        ip = ipaddress.ip_address(addr_part)
    except ValueError:
        return raw
    if ip.version == 4:
        return str(ip)
    inner = ip.compressed
    if zone:
        inner = f"{inner}%25{zone[1:]}"
    return f"[{inner}]"


def build_ws_url(
    host: str,
    port: int = DEFAULT_PORT,
    path: str = DEFAULT_WS_PATH,
) -> str:
    """Build ``ws://`` URL (LAN default; ``wss://`` is not used here)."""
    normalized = path if path.startswith("/") else f"/{path}"
    host_in_url = _format_host_for_ws_url(host)
    return f"ws://{host_in_url}:{port}{normalized}"


def _payload_to_bytes(message: str | bytes) -> bytes:
    """Normalize messages to bytes; text frames use UTF-8."""
    if isinstance(message, bytes):
        return message
    return message.encode("utf-8")


async def _sleep_reconnect_delay(seconds: float) -> None:
    """Await reconnect backoff (tests patch this, not :func:`asyncio.sleep`)."""
    await asyncio.sleep(seconds)


class EnergyDongleClient:
    """One WebSocket to the Energy Dongle; streams DSMR payloads with optional parsing.

    **Multiple dongles:** use **one client instance per device** (each opens its own
    socket and lock). You can run :meth:`stream_parsed` (or another stream helper)
    concurrently across different instances—only concurrent streams on the *same*
    instance are serialized.

    Only **one** of :meth:`stream_raw`, :meth:`stream_telegrams`, or
    :meth:`stream_parsed` may run at a time per client. A second caller **blocks**
    on an internal lock until the active stream finishes (including across
    reconnects inside :meth:`iter_raw_bytes`). :meth:`iter_raw_bytes` is not
    guarded by this lock and must not be used concurrently with those stream
    helpers if you need the single-reader guarantee.
    """

    def __init__(
        self,
        host: str,
        *,
        port: int = DEFAULT_PORT,
        path: str = DEFAULT_WS_PATH,
        ping_interval_s: float = PING_INTERVAL_S,
        ping_timeout_s: float = PING_TIMEOUT_S,
        reconnect_delay_s: float = RECONNECT_DELAY_S,
        reconnect: bool = True,
        telegram_specification: Mapping[str, Any] | None = None,
        apply_checksum_validation: bool = True,
        dsmr_version: str | None = None,
    ) -> None:
        if dsmr_version is not None and telegram_specification is not None:
            raise ValueError(
                "Pass only one of dsmr_version or telegram_specification, not both"
            )
        if dsmr_version is not None:
            if dsmr_version not in TELEGRAM_SPECIFICATIONS:
                raise ValueError(f"Unsupported DSMR version: {dsmr_version!r}")
            resolved_specification = TELEGRAM_SPECIFICATIONS[dsmr_version]
        elif telegram_specification is not None:
            resolved_specification = telegram_specification
        else:
            resolved_specification = telegram_specifications.V5
        self._host = host
        self._port = port
        self._path = path
        self._ping_interval_s = ping_interval_s
        self._ping_timeout_s = ping_timeout_s
        self._reconnect_delay_s = reconnect_delay_s
        self._reconnect = reconnect
        self._telegram_specification = resolved_specification
        self._apply_checksum_validation = apply_checksum_validation
        self._parser = TelegramParser(
            resolved_specification,
            apply_checksum_validation=apply_checksum_validation,
        )
        self._stop = asyncio.Event()
        self._stream_lock = asyncio.Lock()
        self._ws: ClientConnection | None = None

    @classmethod
    def from_settings(cls, settings: EnergyDongleConnectionSettings) -> Self:
        """Construct a client from frozen connection settings.

        ``settings`` supplies host, timing, and parser options in one immutable
        snapshot; see
        :class:`~homey_energy_dongle_ws.models.EnergyDongleConnectionSettings`.
        """
        return cls(
            settings.host,
            port=settings.port,
            path=settings.path,
            ping_interval_s=settings.ping_interval_s,
            ping_timeout_s=settings.ping_timeout_s,
            reconnect_delay_s=settings.reconnect_delay_s,
            reconnect=settings.reconnect,
            telegram_specification=settings.telegram_specification,
            apply_checksum_validation=settings.apply_checksum_validation,
            dsmr_version=settings.dsmr_version,
        )

    @property
    def ws_url(self) -> str:
        """The ``ws://`` URL this client connects to (logging, display, tests)."""
        return build_ws_url(self._host, self._port, self._path)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Signal :meth:`iter_raw_bytes` to stop and close any active WebSocket."""
        self._stop.set()
        ws = self._ws
        if ws is not None:
            await ws.close()

    async def iter_raw_bytes(self) -> AsyncIterator[bytes]:
        """Yield each message as :class:`bytes`; reconnect after transient disconnects.

        With ``reconnect=False``, a failed connect or any disconnect raises
        :exc:`~homey_energy_dongle_ws.exceptions.ConnectionLostError` instead.
        Higher-level helpers buffer these chunks into telegrams and optionally
        parse them.
        """
        while not self._stop.is_set():
            try:
                async with connect(
                    self.ws_url,
                    compression=None,
                    ping_interval=self._ping_interval_s,
                    ping_timeout=self._ping_timeout_s,
                ) as ws:
                    self._ws = ws
                    try:
                        async for message in ws:
                            if self._stop.is_set():
                                return
                            yield _payload_to_bytes(message)
                    except ConnectionClosed as exc:
                        _raise_for_policy_close(exc)
                    finally:
                        self._ws = None
            except (OSError, TimeoutError, InvalidHandshake) as exc:
                if not self._reconnect and not self._stop.is_set():
                    raise ConnectionLostError(
                        f"Cannot connect to {self.ws_url}: {exc}"
                    ) from exc
                if self._reconnect and not self._stop.is_set():
                    logger.debug(
                        "Connection to %s failed: %s; retrying in %ss",
                        self.ws_url,
                        exc,
                        self._reconnect_delay_s,
                    )

            if self._stop.is_set():
                return
            if not self._reconnect:
                raise ConnectionLostError(f"Connection to {self.ws_url} closed")
            await _sleep_reconnect_delay(self._reconnect_delay_s)

    async def stream_raw(self) -> AsyncIterator[bytes]:
        """Yield each WebSocket message payload as :class:`bytes`.

        Same data as :meth:`iter_raw_bytes`, under the client's stream lock.
        """
        async with self._stream_lock:
            async for chunk in self.iter_raw_bytes():
                yield chunk

    async def stream_telegrams(self) -> AsyncIterator[str]:
        """Assemble raw chunks into complete DSMR telegram strings.

        Uses one :class:`~homey_energy_dongle_ws.telegram_assembly.TelegramAssembler`
        for the whole iteration so framing survives transparent reconnects in
        :meth:`iter_raw_bytes`. Non-ASCII bytes are replaced during decode so
        framing can continue instead of raising :exc:`UnicodeDecodeError`.
        This method yields strings. A still-framed telegram fails checksum
        later only when the specification validates a CRC.
        """
        async with self._stream_lock:
            assembler = TelegramAssembler()
            async for chunk in self.iter_raw_bytes():
                for telegram_str in assembler.feed(chunk):
                    yield telegram_str

    async def stream_parsed(
        self,
        *,
        skip_parse_errors: bool = False,
    ) -> AsyncIterator[Telegram]:
        """Yield ``dsmr_parser`` :class:`~dsmr_parser.objects.Telegram` objects.

        Builds on :meth:`stream_telegrams` and parses each string with the
        ``TelegramParser`` created in :meth:`__init__`.

        By default, parse or checksum failure raises
        :exc:`~homey_energy_dongle_ws.exceptions.TelegramParseError` or
        :exc:`~homey_energy_dongle_ws.exceptions.TelegramChecksumError` and ends the
        stream. With ``skip_parse_errors=True``, bad telegrams are logged and
        skipped so the stream can continue.
        """
        async for telegram_str in self.stream_telegrams():
            try:
                telegram = _parse(self._parser, telegram_str)
            except TelegramParseError as exc:
                if not skip_parse_errors:
                    raise
                logger.warning(
                    "Skipping telegram that failed to parse: %s",
                    exc,
                )
                continue
            yield telegram
