"""mDNS discovery for Homey Energy Dongle services (`_energydongle._tcp`).

Browses the LAN for advertised Energy Dongles and reads TXT records
(`p` = WebSocket path, `v` = version). Prefer :func:`discover_energy_dongles` over
guessing IPs when the client is on the same link-local segment and multicast is
allowed. Use :func:`service_instance_display_name` for a UI label from
``ServiceInfo.name``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from zeroconf import IPVersion, ServiceInfo, ServiceListener, Zeroconf
from zeroconf.asyncio import AsyncZeroconf

# Full DNS-SD registration type (``.local.``) for Zeroconf; the same suffix appears on
# ``ServiceInfo.name`` and is stripped by :func:`service_instance_display_name`.
ENERGY_DONGLE_SERVICE_TYPE = "_energydongle._tcp.local."

# Per ``async_get_service_info`` call: scale with ``timeout_s``, cap total wait, and
# keep a minimum so short browse windows still allow a useful resolve attempt.
_RESOLVE_TIMEOUT_MS_MAX = 3000
_RESOLVE_TIMEOUT_MS_MIN = 200


def service_instance_display_name(service_name: str) -> str:
    """Return the DNS-SD *instance* label from a full service instance name.

    ``service_name`` is the FQDN-style string from :attr:`zeroconf.ServiceInfo.name`
    (e.g. ``<Instance>._energydongle._tcp.local.``; instance text may contain spaces).
    Removes ``.`` + :data:`ENERGY_DONGLE_SERVICE_TYPE` from the end when present
    (the form :attr:`~zeroconf.ServiceInfo.name` uses). Empty input returns ``""``.

    Args:
        service_name: Full DNS-SD service instance name from a browser or resolver.

    Returns:
        Instance label for display.
    """
    return service_name.removesuffix("." + ENERGY_DONGLE_SERVICE_TYPE)


@dataclass(frozen=True)
class DiscoveredEnergyDongle:
    """One Energy Dongle instance found via mDNS after SRV/TXT/A resolution."""

    host: str
    port: int
    ws_path: str | None
    version: str | None
    service_name: str
    txt: dict[str, str | None] = field(default_factory=dict)

    @property
    def instance_display_name(self) -> str:
        """DNS-SD instance label for UI (see :func:`service_instance_display_name`)."""
        return service_instance_display_name(self.service_name)


def _normalize_ws_path(raw: str | None) -> str | None:
    """Ensure a leading ``/`` for URL path joining; ``None`` when not advertised."""
    if not raw:
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
    if info.port is None:
        return None

    decoded = dict(info.decoded_properties)
    p_raw = decoded.get("p")
    v_raw = decoded.get("v")

    return DiscoveredEnergyDongle(
        host=host,
        port=info.port,
        ws_path=_normalize_ws_path(p_raw),
        version=v_raw,
        service_name=info.name,
        txt=decoded,
    )


class _EnergyDongleListener(ServiceListener):
    """Collects resolved services keyed by mDNS instance name."""

    def __init__(
        self,
        aiozc: AsyncZeroconf,
        results: dict[str, DiscoveredEnergyDongle],
        *,
        resolve_timeout_ms: int,
    ) -> None:
        self._aiozc = aiozc
        self._results = results
        self._resolve_timeout_ms = resolve_timeout_ms
        self._tasks: set[asyncio.Task[None]] = set()

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._schedule_ingest(type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._results.pop(name, None)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._schedule_ingest(type_, name)

    def _schedule_ingest(self, type_: str, name: str) -> None:
        task = asyncio.create_task(self._ingest(type_, name))
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
        self._results[name] = discovered

    async def await_pending(self) -> None:
        """Wait for in-flight resolutions started during the browse window."""
        if not self._tasks:
            return
        await asyncio.gather(*self._tasks, return_exceptions=True)


def _dedupe_by_host_port(
    results: dict[str, DiscoveredEnergyDongle],
) -> list[DiscoveredEnergyDongle]:
    """Collapse name-keyed results to one entry per ``(host, port)``; last name wins."""
    by_host_port: dict[tuple[str, int], DiscoveredEnergyDongle] = {}
    for dongle in results.values():
        by_host_port[(dongle.host, dongle.port)] = dongle
    return sorted(by_host_port.values(), key=lambda d: (d.host, d.port))


async def discover_energy_dongles(
    *,
    timeout_s: float = 5.0,
) -> list[DiscoveredEnergyDongle]:
    """Browse for ``_energydongle._tcp`` services and return resolved Energy Dongles.

    Results are **deduplicated** by ``(host, port)`` when returning; later updates
    replace earlier entries for the same key (including
    :attr:`DiscoveredEnergyDongle.service_name`). If a service disappears during the
    browse window, it is removed by mDNS instance name. Entries are sorted by
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

    results: dict[str, DiscoveredEnergyDongle] = {}
    resolve_timeout_ms = min(
        _RESOLVE_TIMEOUT_MS_MAX,
        max(_RESOLVE_TIMEOUT_MS_MIN, int(timeout_s * 1000)),
    )

    async with AsyncZeroconf(ip_version=IPVersion.All) as aiozc:
        listener = _EnergyDongleListener(
            aiozc,
            results,
            resolve_timeout_ms=resolve_timeout_ms,
        )
        await aiozc.async_add_service_listener(ENERGY_DONGLE_SERVICE_TYPE, listener)
        try:
            await asyncio.sleep(timeout_s)
        finally:
            await aiozc.async_remove_all_service_listeners()
        await listener.await_pending()

    return _dedupe_by_host_port(results)
