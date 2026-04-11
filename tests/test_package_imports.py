"""Smoke tests that the package installs and exposes a version."""

import homey_energy_dongle_ws


def test_import_and_version() -> None:
    assert hasattr(homey_energy_dongle_ws, "discover_energy_dongles")
    assert hasattr(homey_energy_dongle_ws, "DiscoveredEnergyDongle")
    assert hasattr(homey_energy_dongle_ws, "service_instance_display_name")
    assert hasattr(homey_energy_dongle_ws, "ENERGY_DONGLE_SERVICE_TYPE")
    assert hasattr(homey_energy_dongle_ws, "__version__")
    assert isinstance(homey_energy_dongle_ws.__version__, str)
    parts = homey_energy_dongle_ws.__version__.split(".")
    assert len(parts) >= 2
    for part in parts:
        assert part.isdigit()
