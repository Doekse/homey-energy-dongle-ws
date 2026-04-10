"""Stream DSMR P1 wire data into complete telegram strings.

Bytes from a WebSocket (or similar) are decoded once at this boundary as
**ASCII** (strict). DSMR P1 telegrams are plain 7-bit text; this matches
``dsmr_parser``'s socket client and keeps decoding simple and predictable.
Non-ASCII bytes raise :exc:`UnicodeDecodeError`.

Framing follows ``dsmr_parser``'s ``TelegramBuffer`` (``append`` then
``get_all``). Only **complete** telegrams are yielded; partial data stays
buffered until the upstream regex sees a full telegram (``/`` … ``!`` + optional
checksum + CRLF).
"""

from __future__ import annotations

from collections.abc import Iterator

from dsmr_parser.clients.telegram_buffer import TelegramBuffer

_CHUNK_ENCODING = "ascii"


class TelegramAssembler:
    """Holds one :class:`TelegramBuffer` for a single stream consumer."""

    def __init__(self) -> None:
        self._telegram_buffer = TelegramBuffer()

    def feed(self, chunk: bytes) -> Iterator[str]:
        """Decode *chunk* and drain any complete telegrams produced after appending.

        Args:
            chunk: Raw wire bytes; decoded strictly as ASCII (see module docstring).

        Yields:
            Zero or more complete telegram strings per call, depending on chunk size
            and alignment with telegram boundaries.
        """
        text = chunk.decode(_CHUNK_ENCODING)
        self._telegram_buffer.append(text)
        yield from self._telegram_buffer.get_all()

    def feed_str(self, chunk: str) -> Iterator[str]:
        """Append text that is already a string (bypasses bytes decoding).

        Intended for tests and callers that do not have raw wire bytes.

        Args:
            chunk: Telegram fragment text.

        Yields:
            Same semantics as :meth:`feed`.
        """
        self._telegram_buffer.append(chunk)
        yield from self._telegram_buffer.get_all()
