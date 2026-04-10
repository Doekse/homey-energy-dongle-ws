#!/usr/bin/env python3
"""Interactively pick a Homey Energy Dongle (mDNS or manual IP) and stream DSMR data.

Prompts for connection method and data mode (raw bytes, assembled telegram text, or
parsed objects), then prints until Ctrl+C. mDNS browse uses a fixed duration (5s).

Usage::

    python scripts/interactive_stream.py

Requires the package installed (e.g. ``pip install -e .`` from the repo root).
"""

from __future__ import annotations

import asyncio
import sys
from typing import Literal

from homey_energy_dongle_ws import EnergyDongleClient, discover_energy_dongles
from homey_energy_dongle_ws.constants import DEFAULT_PORT, DEFAULT_WS_PATH
from homey_energy_dongle_ws.discovery import DiscoveredEnergyDongle

# Matches ``print_telegrams.py`` default ``--discover-timeout``; not user-configurable here.
MDNS_BROWSE_TIMEOUT_S = 5.0

StreamMode = Literal["telegrams", "parsed", "raw"]


def _prompt_non_empty(prompt: str) -> str:
    """Read a non-empty line from stdin, re-prompting until one is given."""
    while True:
        line = input(prompt).strip()
        if line:
            return line
        print("Please enter a value.", file=sys.stderr)


def _prompt_connection_mode() -> Literal["mdns", "manual"]:
    """Ask whether to resolve the dongle via mDNS or a fixed host/port/path."""
    while True:
        print("\nConnection:")
        print("  1) Discover via mDNS")
        print("  2) Manual IP or hostname")
        choice = input("Choose 1 or 2: ").strip()
        if choice == "1":
            return "mdns"
        if choice == "2":
            return "manual"
        print("Invalid choice; enter 1 or 2.", file=sys.stderr)


def _format_device_line(i: int, d: DiscoveredEnergyDongle) -> str:
    """Build one human-readable line for a discovered dongle (1-based index)."""
    path = d.ws_path if d.ws_path is not None else "(no WebSocket path in mDNS)"
    ver = d.version if d.version is not None else "?"
    return f"  {i}) {d.host}:{d.port}  path={path}  v={ver}"


def _prompt_mdns_device(devices: list[DiscoveredEnergyDongle]) -> tuple[str, int, str]:
    """Let the user pick a discovered dongle; requires an mDNS-advertised WebSocket path."""
    if not devices:
        print("No Energy Dongles found on the network.", file=sys.stderr)
        raise SystemExit(1)

    with_path = [d for d in devices if d.ws_path is not None]
    if not with_path:
        print("\nDiscovered devices:")
        for idx, d in enumerate(devices, start=1):
            print(_format_device_line(idx, d))
        print(
            "None advertise a WebSocket path (`p`). Enable Local API or use manual connection.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print("\nDiscovered devices (choose one that has a WebSocket path):")
    for idx, d in enumerate(devices, start=1):
        print(_format_device_line(idx, d))
    if any(d.ws_path is None for d in devices):
        print(
            "\nNote: entries without a path usually mean Local API is off; pick another row or use manual IP.",
            file=sys.stderr,
        )

    while True:
        raw = input(f"Select 1–{len(devices)}: ").strip()
        try:
            n = int(raw)
        except ValueError:
            print("Enter a number.", file=sys.stderr)
            continue
        if not (1 <= n <= len(devices)):
            print(f"Enter a number from 1 to {len(devices)}.", file=sys.stderr)
            continue
        chosen = devices[n - 1]
        if chosen.ws_path is None:
            print(
                "That device has no WebSocket path in mDNS. Enable Local API or choose another.",
                file=sys.stderr,
            )
            continue
        return chosen.host, chosen.port, chosen.ws_path


def _prompt_manual_target() -> tuple[str, int, str]:
    """Read host, port, and WebSocket path from the user with defaults."""
    host = _prompt_non_empty("Host or IP: ").strip()
    port_raw = input(f"TCP port [{DEFAULT_PORT}]: ").strip()
    port = DEFAULT_PORT if not port_raw else int(port_raw)
    path_raw = input(f"WebSocket path [{DEFAULT_WS_PATH}]: ").strip()
    path = DEFAULT_WS_PATH if not path_raw else path_raw
    if not path.startswith("/"):
        path = f"/{path}"
    return host, port, path


def _prompt_stream_mode() -> StreamMode:
    """Ask whether to print raw WebSocket payloads, telegram text, or parsed objects."""
    while True:
        print("\nData to show:")
        print("  1) Raw — WebSocket message payloads (bytes on stdout)")
        print("  2) Telegrams — assembled DSMR telegram strings")
        print("  3) Parsed — dsmr_parser Telegram objects")
        choice = input("Choose 1, 2, or 3: ").strip()
        if choice == "1":
            return "raw"
        if choice == "2":
            return "telegrams"
        if choice == "3":
            return "parsed"
        print("Invalid choice; enter 1, 2, or 3.", file=sys.stderr)


async def _print_stream(host: str, port: int, path: str, *, mode: StreamMode) -> None:
    """Open a client and print telegram strings, parsed objects, or raw WebSocket bytes."""
    async with EnergyDongleClient(host, port=port, path=path) as client:
        if mode == "parsed":
            async for telegram in client.stream_parsed():
                print(telegram, flush=True)
        elif mode == "raw":
            async for chunk in client.stream_raw():
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
        else:
            async for text in client.stream_telegrams():
                print(text, flush=True)


def main() -> None:
    """Run prompts, then connect and stream until interrupted."""
    print("Homey Energy Dongle — interactive stream")
    mode_conn = _prompt_connection_mode()

    if mode_conn == "mdns":
        print(f"\nBrowsing mDNS ({MDNS_BROWSE_TIMEOUT_S:g}s)...")
        found = asyncio.run(
            discover_energy_dongles(timeout_s=MDNS_BROWSE_TIMEOUT_S),
        )
        host, port, path = _prompt_mdns_device(found)
    else:
        try:
            host, port, path = _prompt_manual_target()
        except ValueError as e:
            print(f"Invalid input: {e}", file=sys.stderr)
            raise SystemExit(1) from e

    mode = _prompt_stream_mode()
    print(f"\nConnecting to ws://{host}:{port}{path} — Ctrl+C to stop.\n")

    try:
        asyncio.run(_print_stream(host, port, path, mode=mode))
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
