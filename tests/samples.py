"""Shared telegram samples for tests."""

# Minimal telegram matching dsmr_parser's framing regex (``/`` … ``!`` + hex + CRLF).
# Also valid under the ``V3`` specification used by the parser tests.
GOLDEN = (
    "/FOO5\\2BAR\r\n"
    "1-3:0.2.8(42)(0)(0)(0)(0)\r\n"
    "!1234\r\n"
)
