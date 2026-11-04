# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-11-04

### Added

- `detect_dsmr_version()` returns a `DSMR_VERSIONS` code from one telegram string, or `None` when the profile is not recognized.

## [0.3.0] - 2026-11-04

### Added

- Debug log before reconnect sleep when a connect attempt fails with `OSError`, `TimeoutError`, or `InvalidHandshake` and `reconnect=True`.
- `reconnect` option on `EnergyDongleClient`. With `reconnect=False`, a failed connect or any disconnect raises the new `ConnectionLostError` instead of reconnecting silently, so callers can mark the device unavailable and own the retry policy.
- `ConnectionLimitError`, `ConnectionLostError`, `HomeyWebSocketError` and `LocalApiDisabledError` are exported from the package root.
- `dsmr_version` option on `EnergyDongleClient` that selects the telegram specification from a DSMR version code (for example `"5"` or `"5B"`), using the same codes as `dsmr_parser`. The supported codes are exported as `DSMR_VERSIONS`.

### Changed

- CI runs `ruff check .` so `.github` scripts are linted with the rest of the repository.
- `scripts/interactive_stream.py` prints `client.ws_url` (bracketed IPv6) and wraps long lines for ruff.
- README: fix nested bold/backtick markup; document `dsmr_version` / `DSMR_VERSIONS`, `reconnect=False` / `ConnectionLostError`, and that a closed client cannot be reused.
- `EnergyDongleClient` computes `ws_url` once in `__init__` instead of rebuilding it from stored host/port/path on each access.
- Discovery tracks services by mDNS instance name and deduplicates by `(host, port)` when returning results, instead of maintaining parallel name/key maps under a lock.
- `stream_parsed` builds on `stream_telegrams` and reuses one `TelegramParser` per client instead of assembling and constructing a parser on every telegram.
- Simplify WebSocket close-code mapping: policy closes are handled in one client helper, and `LocalApiDisabledError` / `ConnectionLimitError` no longer override `__init__`.

### Fixed

- Require `websockets>=13.0`, matching the `websockets.asyncio.client` API the client imports.
- Treat WebSocket handshake failures (`InvalidHandshake`, including `InvalidStatus`) like other transient connect errors: raise `ConnectionLostError` when `reconnect=False`, otherwise wait and retry.
- Decode DSMR wire bytes as ASCII with `errors="replace"` so non-ASCII bytes are substituted and framing can continue, instead of raising `UnicodeDecodeError` and aborting the stream. A still-framed telegram fails checksum only when the specification validates a CRC.
- Raise `ValueError` when both `dsmr_version` and `telegram_specification` are set on `EnergyDongleClient`. Omit both to keep the V5 default.

### Removed

- Public `EnergyDongleClient.iter_raw_bytes`; use `stream_raw`, `stream_telegrams`, or `stream_parsed` instead. The reconnect loop remains as private `_iter_raw_bytes`.
- `TelegramAssembler.feed_str`; pass encoded bytes to `feed` instead.
- `EnergyDongleConnectionSettings` and `EnergyDongleClient.from_settings`. Pass connection options to `EnergyDongleClient` directly.

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

[Unreleased]: https://github.com/Doekse/homey-energy-dongle-ws/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Doekse/homey-energy-dongle-ws/releases/tag/v0.4.0
[0.3.0]: https://github.com/Doekse/homey-energy-dongle-ws/releases/tag/v0.3.0
[0.2.0]: https://github.com/Doekse/homey-energy-dongle-ws/releases/tag/v0.2.0
[0.1.0]: https://github.com/Doekse/homey-energy-dongle-ws/releases/tag/v0.1.0
