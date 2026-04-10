"""mDNS discovery for Homey Energy Dongle services (`_energydongle._tcp`).

Browses the LAN for advertised Energy Dongles and reads TXT records
(`p` = WebSocket path, `v` = version). Prefer :func:`discover_energy_dongles` over
guessing IPs when the client
is on the same link-local segment and multicast is allowed.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from zeroconf import IPVersion, ServiceInfo, ServiceListener, Zeroconf
from zeroconf.asyncio import AsyncZeroconf

# Fully qualified type name for zeroconf browse / resolve.
_ENERGY_DONGLE_SERVICE_TYPE = "_energydongle._tcp.local."


@dataclass(frozen=True)
class DiscoveredEnergyDongle:
    """One Energy Dongle instance found via mDNS after SRV/TXT/A resolution."""

    host: str
    port: int
    ws_path: str | None
    version: str | None
    txt: dict[str, str | None] = field(default_factory=dict)
    """Decoded TXT key/value pairs from the advertisement (e.g. ``p``, ``v``)."""


def _normalize_ws_path(raw: str | None) -> str | None:
    """Return a path starting with ``/``, or ``None`` if WebSocket is not advertised."""
    if raw is None or raw == "":
        return None
    return raw if raw.startswith("/") else f"/{raw}"


def _energy_dongle_from_service_info(
    info: ServiceInfo,
) -> DiscoveredEnergyDongle | None:
    """Build a :class:`DiscoveredEnergyDongle` from resolved ``ServiceInfo``."""
    v4 = info.parsed_addresses(IPVersion.V4Only)
    v6 = info.parsed_addresses(IPVersion.V6Only)
    if v4:
        host = v4[0]
    elif v6:
        host = v6[0]
    else:
        return None

    decoded = dict(info.decoded_properties)
    p_raw = decoded.get("p")
    v_raw = decoded.get("v")

    return DiscoveredEnergyDongle(
        host=host,
        port=int(info.port),
        ws_path=_normalize_ws_path(p_raw),
        version=v_raw,
        txt=decoded,
    )


class _EnergyDongleListener(ServiceListener):
    """Collects resolved services into a shared map, deduped by ``(host, port)``."""

    def __init__(
        self,
        aiozc: AsyncZeroconf,
        results: dict[tuple[str, int], DiscoveredEnergyDongle],
        lock: asyncio.Lock,
        *,
        resolve_timeout_ms: int,
    ) -> None:
        self._aiozc = aiozc
        self._results = results
        self._lock = lock
        self._resolve_timeout_ms = resolve_timeout_ms
        self._tasks: set[asyncio.Task[None]] = set()
        self._name_to_key: dict[str, tuple[str, int]] = {}
        self._key_to_names: dict[tuple[str, int], set[str]] = {}

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._schedule_ingest(type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._schedule_remove(name)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._schedule_ingest(type_, name)

    def _schedule_ingest(self, type_: str, name: str) -> None:
        task = asyncio.create_task(self._ingest(type_, name))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _schedule_remove(self, name: str) -> None:
        task = asyncio.create_task(self._remove(name))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _ingest(self, type_: str, name: str) -> None:
        info = await self._aiozc.async_get_service_info(
            type_,
            name,
            timeout=self._resolve_timeout_ms,
        )
        if info is None:
            return
        discovered = _energy_dongle_from_service_info(info)
        if discovered is None:
            return
        key = (discovered.host, discovered.port)
        async with self._lock:
            prev = self._name_to_key.get(name)
            if prev is not None and prev != key:
                old_names = self._key_to_names.get(prev)
                if old_names:
                    old_names.discard(name)
                    if not old_names:
                        del self._key_to_names[prev]
                        self._results.pop(prev, None)
            self._name_to_key[name] = key
            self._key_to_names.setdefault(key, set()).add(name)
            self._results[key] = discovered

    async def _remove(self, name: str) -> None:
        async with self._lock:
            key = self._name_to_key.pop(name, None)
            if key is None:
                return
            names = self._key_to_names.get(key)
            if names:
                names.discard(name)
                if not names:
                    del self._key_to_names[key]
                    self._results.pop(key, None)

    async def await_pending(self) -> None:
        """Wait for in-flight resolutions started during the browse window."""
        if not self._tasks:
            return
        await asyncio.gather(*self._tasks, return_exceptions=True)


async def discover_energy_dongles(
    *,
    timeout_s: float = 5.0,
) -> list[DiscoveredEnergyDongle]:
    """Browse for ``_energydongle._tcp`` services and return resolved Energy Dongles.

    Results are **deduplicated** by ``(host, port)``; later updates replace earlier
    entries for the same key. If a service disappears during the browse window, it is
    removed when possible (tracked by mDNS instance name). Entries are sorted by
    ``(host, port)``.

    If TXT key ``p`` is absent, :attr:`DiscoveredEnergyDongle.ws_path` is ``None``
    (Local API / WebSocket may be off). Uses IPv4 addresses when present, otherwise
    the first IPv6 address.

    Args:
        timeout_s: Seconds to listen for advertisements before returning.

    Returns:
        Resolved dongles, sorted by ``(host, port)``.
    """
    if timeout_s < 0:
        raise ValueError("timeout_s must be >= 0")

    results: dict[tuple[str, int], DiscoveredEnergyDongle] = {}
    lock = asyncio.Lock()
    resolve_timeout_ms = min(3000, max(200, int(timeout_s * 1000)))

    async with AsyncZeroconf(ip_version=IPVersion.All) as aiozc:
        listener = _EnergyDongleListener(
            aiozc,
            results,
            lock,
            resolve_timeout_ms=resolve_timeout_ms,
        )
        await aiozc.async_add_service_listener(_ENERGY_DONGLE_SERVICE_TYPE, listener)
        try:
            await asyncio.sleep(timeout_s)
        finally:
            await aiozc.async_remove_all_service_listeners()
        await listener.await_pending()

    return sorted(results.values(), key=lambda d: (d.host, d.port))
