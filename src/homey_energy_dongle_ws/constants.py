"""Default connection and timing values for the Homey Energy Dongle client."""

DEFAULT_PORT = 80
DEFAULT_WS_PATH = "/ws"
PING_INTERVAL_S = 10.0
# Below :data:`PING_INTERVAL_S` so a missing pong fails before the next ping.
PING_TIMEOUT_S = 9.0
RECONNECT_DELAY_S = 5.0
