# Contributing to homey-energy-dongle-ws

Thank you for taking the time to contribute. This document describes how to set up a development environment, run the same checks as CI, and propose changes.

## Questions and bug reports

Use [Issues](https://github.com/Doekse/homey-energy-dongle-ws/issues) for bug reports and feature discussion. Include enough detail to reproduce a problem (Python version, library version, minimal example or traceback, and what you expected to happen).

## Development setup

Requirements:

- **Python 3.11+** (see `requires-python` in `pyproject.toml`).

Clone the repository and install the package in editable mode with dev dependencies:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Checks (match CI)

Before opening a pull request, run lint and tests locally:

```bash
ruff check src tests
pytest -m "not integration"
```

CI runs these commands on Python 3.11 and 3.12. Keeping changes passing on both versions avoids surprises.

## Integration tests (optional)

Tests that talk to real hardware or the LAN are **opt-in** and never run in default CI.

**WebSocket / DSMR:** set `HOMEY_ENERGY_DONGLE_HOST` to the Energy Dongle address, then run:

```bash
pytest -m integration
```

**mDNS browse only:** set `HOMEY_MDNS_LIVE=1` on a machine on the same LAN as an Energy Dongle (may return an empty list):

```bash
HOMEY_MDNS_LIVE=1 pytest -m "integration and mdns_live"
```

Default `pytest` (and CI) runs `pytest -m "not integration"` so live tests are not required.

## Pull requests

- **Scope:** Prefer focused changes that address one concern. That makes review and history easier to follow.
- **Tests:** Add or adjust tests when you change behavior or fix a bug. Default `pytest` (and CI) must stay green without integration markers.
- **Style:** `ruff` enforces import order and common issues; fixing new lint in touched files keeps the tree consistent.

Maintainers handle releases separately.
