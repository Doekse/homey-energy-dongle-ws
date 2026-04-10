# homey-energy-dongle-ws

[![PyPI version](https://img.shields.io/pypi/v/homey-energy-dongle-ws)](https://pypi.org/project/homey-energy-dongle-ws/)
[![PyPI downloads](https://img.shields.io/pypi/dm/homey-energy-dongle-ws)](https://pypi.org/project/homey-energy-dongle-ws/)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://pypi.org/project/homey-energy-dongle-ws/)
[![CI](https://img.shields.io/github/actions/workflow/status/Doekse/homey-energy-dongle-ws/ci.yml?branch=main)](https://github.com/Doekse/homey-energy-dongle-ws/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/Doekse/homey-energy-dongle-ws/blob/HEAD/LICENSE)

Async Python client for the **Homey Energy Dongle** WebSocket API. It streams DSMR smart-meter data in three layers: raw WebSocket payloads, complete telegram strings, or parsed `[dsmr_parser](https://pypi.org/project/dsmr-parser/)` `Telegram` objects. The library is **standalone** (not Home Assistant–specific).

## Prerequisites

- Python 3.11+
- A Homey Energy Dongle
- Enabling the local API on the Homey Energy Dongle in the Homey app. Please reference [this](https://support.homey.app/hc/en-us/articles/18985951863452-Enabling-the-Homey-Energy-Dongle-s-Local-API) knowledge base article

See Athom’s [Homey Energy Dongle WebSocket example](https://github.com/athombv/node-dsmr-parser/blob/master/examples/homey-energy-dongle-ws.js) for more context.

## Install

```bash
pip install homey-energy-dongle-ws
```

`zeroconf` is a **core** dependency so mDNS discovery works with a normal install.

Or install from Git:

```bash
pip install git+https://github.com/Doekse/homey-energy-dongle-ws.git
```

## Quick start (discovery first)

On the same LAN as the Energy Dongle, call `**discover_energy_dongles()**`, pick a result that has `**ws_path**` set when possible, then open `**EnergyDongleClient**` (or use `**build_ws_url**` with the chosen host, port, and path).

```python
import asyncio

from homey_energy_dongle_ws import (
    DiscoveredEnergyDongle,
    EnergyDongleClient,
    discover_energy_dongles,
)


async def main() -> None:
    found: list[DiscoveredEnergyDongle] = await discover_energy_dongles(timeout_s=5.0)
    if not found:
        print("No Energy Dongles discovered; use manual connection (below).")
        return

    d = next((x for x in found if x.ws_path is not None), None)
    if d is None:
        print("No advertised WebSocket path (TXT p); enable Local API or use manual connection.")
        return

    async with EnergyDongleClient(d.host, port=d.port, path=d.ws_path) as client:
        async for telegram in client.stream_parsed():
            print(telegram)
            break


asyncio.run(main())
```

**TXT records (mDNS):**

- `**p`** — WebSocket path (e.g. `/ws`). If **missing**, the library sets `ws_path` to `None` (Athom: WebSocket not advertised / Local API off).
- `**v`** — Version string (`DiscoveredEnergyDongle.version`). Full decoded TXT is in `**DiscoveredEnergyDongle.txt`**.

**Firewall / network:** the client host must allow **mDNS** (UDP **5353** inbound/outbound) and LAN traffic to the Energy Dongle. Routers, VLANs, VPNs, or “guest” Wi‑Fi often block multicast, use manual connection instead.

## Manual connection (fallback)

Use this when discovery returns nothing, times out, `**p`** is missing and you know Local API should work, or you are not on the same L2 segment:

1. Open the **Homey** app → your Energy Dongle → **Settings** → **Advanced Settings**, then note the **IP address** which is listed.
2. Connect with defaults `**ws://<host>:80/ws`** (or pass `port` / `path` if yours differ). For **IPv6** literals, `build_ws_url()` and `EnergyDongleClient.ws_url` use bracketed hosts (e.g. `ws://[2001:db8::1]:80/ws`) as required by the WebSocket URL syntax.

```python
import asyncio
from homey_energy_dongle_ws import EnergyDongleClient


async def main() -> None:
    async with EnergyDongleClient("192.168.x.x") as client:
        async for telegram in client.stream_parsed():
            print(telegram)
            break


asyncio.run(main())
```

## DSMR version

Parsing uses `telegram_specification` from `[dsmr_parser.telegram_specifications](https://dsmr-parser.readthedocs.io/)` (default: **V5**). If your meter uses another DSMR version, pass the matching spec to `EnergyDongleClient(..., telegram_specification=...)`. A wrong spec typically causes parse errors, not silent wrong data.

For long-running processes, `stream_parsed(skip_parse_errors=True)` logs and skips a bad telegram instead of stopping the stream (default remains fail-fast).

## Limits

The Energy Dongle allows at most **two** concurrent WebSocket clients. A third connection is rejected with close code **1008**; this library raises `**ConnectionLimitError`**.

## Troubleshooting

- **Local API disabled** in the app → the server closes with **1008** and this library raises `**LocalApiDisabledError`** (check `**close_code`** / `**close_reason`** on `**HomeyWebSocketError`** subclasses for logging).
- **Connection limit** → `**ConnectionLimitError`** (1008).

## For maintainers

Development setup, local checks, and pull requests: see [CONTRIBUTING.md](CONTRIBUTING.md). Release history: [CHANGELOG.md](CHANGELOG.md).
