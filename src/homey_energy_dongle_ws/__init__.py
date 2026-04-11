"""Homey Energy Dongle: async WebSocket client for DSMR smart-meter data.

DNS-SD instance names from mDNS (e.g. :attr:`zeroconf.ServiceInfo.name`) can be
turned into a display label with :func:`service_instance_display_name`.
"""

from homey_energy_dongle_ws.client import EnergyDongleClient
from homey_energy_dongle_ws.discovery import (
    ENERGY_DONGLE_SERVICE_TYPE,
    DiscoveredEnergyDongle,
    discover_energy_dongles,
    service_instance_display_name,
)
from homey_energy_dongle_ws.exceptions import TelegramChecksumError, TelegramParseError
from homey_energy_dongle_ws.parser import parse_telegram
from homey_energy_dongle_ws.telegram_assembly import TelegramAssembler

__all__ = [
    "ENERGY_DONGLE_SERVICE_TYPE",
    "DiscoveredEnergyDongle",
    "EnergyDongleClient",
    "TelegramAssembler",
    "TelegramChecksumError",
    "TelegramParseError",
    "__version__",
    "discover_energy_dongles",
    "parse_telegram",
    "service_instance_display_name",
]

__version__ = "0.1.0"
