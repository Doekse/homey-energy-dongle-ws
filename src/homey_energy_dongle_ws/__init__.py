"""Homey Energy Dongle: async WebSocket client for DSMR smart-meter data."""

from homey_energy_dongle_ws.client import EnergyDongleClient
from homey_energy_dongle_ws.discovery import (
    DiscoveredEnergyDongle,
    discover_energy_dongles,
)
from homey_energy_dongle_ws.exceptions import TelegramChecksumError, TelegramParseError
from homey_energy_dongle_ws.parser import parse_telegram
from homey_energy_dongle_ws.telegram_assembly import TelegramAssembler

__all__ = [
    "DiscoveredEnergyDongle",
    "EnergyDongleClient",
    "TelegramAssembler",
    "TelegramChecksumError",
    "TelegramParseError",
    "__version__",
    "discover_energy_dongles",
    "parse_telegram",
]

__version__ = "0.1.0"
