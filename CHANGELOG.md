# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-10

### Added

- `EnergyDongleClient` for async WebSocket access to the Energy Dongle local API, with streams for raw payloads, assembled telegram text, and parsed DSMR `Telegram` objects (via `dsmr-parser`).
- LAN mDNS discovery via `discover_energy_dongles()` and `DiscoveredEnergyDongle` (including TXT-derived WebSocket path when advertised).
- `TelegramAssembler` for framing complete DSMR telegrams from chunked messages.
- `parse_telegram()` and typed errors `TelegramParseError` / `TelegramChecksumError` for DSMR parsing failures.

[Unreleased]: https://github.com/Doekse/homey-energy-dongle-ws/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Doekse/homey-energy-dongle-ws/releases/tag/v0.1.0
