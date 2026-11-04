"""Stream DSMR P1 wire data into complete telegram strings.

Bytes from a WebSocket (or similar) are decoded once at this boundary as
**ASCII** with ``errors="replace"``. DSMR P1 telegrams are plain 7-bit text.
Non-ASCII bytes become replacement characters so framing can continue instead
of aborting the stream with :exc:`UnicodeDecodeError`. A telegram that still
frames fails checksum validation only when the specification validates a CRC.

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
            chunk: Raw wire bytes; decoded as ASCII with replacement (see module
                docstring).

        Yields:
            Zero or more complete telegram strings per call, depending on chunk size
            and alignment with telegram boundaries.
        """
        text = chunk.decode(_CHUNK_ENCODING, errors="replace")
        self._telegram_buffer.append(text)
        yield from self._telegram_buffer.get_all()
