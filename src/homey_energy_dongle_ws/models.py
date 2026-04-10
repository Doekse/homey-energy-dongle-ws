"""Data models for DSMR and device connection settings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from dsmr_parser import telegram_specifications

from homey_energy_dongle_ws.constants import (
    DEFAULT_PORT,
    DEFAULT_WS_PATH,
    PING_INTERVAL_S,
    PING_TIMEOUT_S,
    RECONNECT_DELAY_S,
)


@dataclass(frozen=True)
class EnergyDongleConnectionSettings:
    """Immutable host, timing, and parser options for the Energy Dongle client.

    Used with :class:`~homey_energy_dongle_ws.client.EnergyDongleClient` and
    :meth:`~homey_energy_dongle_ws.client.EnergyDongleClient.from_settings`.
    """

    host: str
    port: int = DEFAULT_PORT
    path: str = DEFAULT_WS_PATH
    ping_interval_s: float = PING_INTERVAL_S
    ping_timeout_s: float = PING_TIMEOUT_S
    reconnect_delay_s: float = RECONNECT_DELAY_S
    telegram_specification: Mapping[str, Any] = field(
        default_factory=lambda: telegram_specifications.V5,
    )
    apply_checksum_validation: bool = True
