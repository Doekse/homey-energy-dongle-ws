"""Tests for :func:`homey_energy_dongle_ws.discovery.service_instance_display_name`."""

from __future__ import annotations

import pytest

from homey_energy_dongle_ws.discovery import service_instance_display_name


@pytest.mark.parametrize(
    ("fqdn", "expected"),
    [
        (
            "Homey Energy Dongle 37e4._energydongle._tcp.local.",
            "Homey Energy Dongle 37e4",
        ),
        (
            "Preserves CaSe._energydongle._tcp.local.",
            "Preserves CaSe",
        ),
    ],
)
def test_strips_energy_dongle_suffix(fqdn: str, expected: str) -> None:
    assert service_instance_display_name(fqdn) == expected


def test_empty_string() -> None:
    assert service_instance_display_name("") == ""


@pytest.mark.parametrize(
    ("wrong",),
    [
        ("Some Other._printer._tcp.local.",),
        ("not-mdns-name",),
    ],
)
def test_non_energy_dongle_name_unchanged(wrong: str) -> None:
    assert service_instance_display_name(wrong) == wrong


def test_name_without_terminal_dot_unchanged() -> None:
    """``ServiceInfo.name`` uses a trailing root dot; other shapes are left as-is."""
    fqdn = "Homey Energy Dongle 37e4._energydongle._tcp.local"
    assert service_instance_display_name(fqdn) == fqdn


def test_non_lowercase_type_suffix_not_stripped() -> None:
    """Only the dongle's lowercase ``_energydongle._tcp.local`` form is recognized."""
    fqdn = "MyDevice._ENERGYDONGLE._TCP.LOCAL."
    assert service_instance_display_name(fqdn) == fqdn


def test_suffix_only_yields_empty_instance() -> None:
    assert service_instance_display_name("._energydongle._tcp.local.") == ""
