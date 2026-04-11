# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-11

### Added

- Public `ENERGY_DONGLE_SERVICE_TYPE` for Zeroconf DNS-SD browse/resolve of `_energydongle._tcp.local.`.
- `service_instance_display_name()` and `DiscoveredEnergyDongle.instance_display_name` to derive a human-facing instance label from `zeroconf.ServiceInfo.name`.
- `DiscoveredEnergyDongle.service_name` holding the full mDNS service instance name returned by discovery.

### Changed

- Discovery module documentation expanded for DNS-SD instance names and UI labeling.
- `async_get_service_info` resolve timeout limits are named (`_RESOLVE_TIMEOUT_MS_MIN` / `_RESOLVE_TIMEOUT_MS_MAX`); behavior remains a 200–3000 ms window scaled from `timeout_s`.
- `scripts/interactive_stream.py` prints each dongle’s instance display name when listing discovered devices.
- README formatting and minor wording edits.
- `DiscoveredEnergyDongle` now requires `service_name`. Code that constructs the dataclass by hand must supply the same string Zeroconf uses for `ServiceInfo.name` (discovery continues to populate it automatically).

### Removed

- Private `_ENERGY_DONGLE_SERVICE_TYPE`; callers should use `ENERGY_DONGLE_SERVICE_TYPE`.

## [0.1.0] - 2026-04-10

### Added

- `EnergyDongleClient` for async WebSocket access to the Energy Dongle local API, with streams for raw payloads, assembled telegram text, and parsed DSMR `Telegram` objects (via `dsmr-parser`).
- LAN mDNS discovery via `discover_energy_dongles()` and `DiscoveredEnergyDongle` (including TXT-derived WebSocket path when advertised).
- `TelegramAssembler` for framing complete DSMR telegrams from chunked messages.
- `parse_telegram()` and typed errors `TelegramParseError` / `TelegramChecksumError` for DSMR parsing failures.

[Unreleased]: https://github.com/Doekse/homey-energy-dongle-ws/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Doekse/homey-energy-dongle-ws/releases/tag/v0.2.0
[0.1.0]: https://github.com/Doekse/homey-energy-dongle-ws/releases/tag/v0.1.0
