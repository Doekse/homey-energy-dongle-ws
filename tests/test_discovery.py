"""Unit tests for mDNS discovery (mocked); optional live browse behind env + markers."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import MagicMock

import pytest
from zeroconf import ServiceInfo

from homey_energy_dongle_ws.discovery import (
    DiscoveredEnergyDongle,
    _energy_dongle_from_service_info,
    _EnergyDongleListener,
    discover_energy_dongles,
)

_ENERGY_DONGLE_SERVICE_TYPE = "_energydongle._tcp.local."


def _sample_service_info(
    *,
    name: str = "EnergyDongle A._energydongle._tcp.local.",
    addresses: list[str] | None = None,
    port: int = 80,
    properties: dict[str, str] | None = None,
) -> ServiceInfo:
    props = properties if properties is not None else {"p": "ws", "v": "1.0.0"}
    addrs = addresses if addresses is not None else ["192.168.50.10"]
    return ServiceInfo(
        _ENERGY_DONGLE_SERVICE_TYPE,
        name,
        port=port,
        properties=props,
        parsed_addresses=addrs,
    )


def test_energy_dongle_from_service_info_normalizes_path_and_txt() -> None:
    info = _sample_service_info(properties={"p": "ws", "v": "2"})
    d = _energy_dongle_from_service_info(info)
    assert d is not None
    assert d.host == "192.168.50.10"
    assert d.port == 80
    assert d.ws_path == "/ws"
    assert d.version == "2"
    assert d.txt.get("p") == "ws"
    assert d.txt.get("v") == "2"


def test_energy_dongle_from_service_info_missing_p_means_no_ws_path() -> None:
    info = _sample_service_info(properties={"v": "x"})
    d = _energy_dongle_from_service_info(info)
    assert d is not None
    assert d.ws_path is None


def test_energy_dongle_from_service_info_prefers_ipv4() -> None:
    info = ServiceInfo(
        _ENERGY_DONGLE_SERVICE_TYPE,
        "x._energydongle._tcp.local.",
        port=80,
        properties={"p": "/ws"},
        parsed_addresses=["2001:db8::1", "192.168.1.2"],
    )
    d = _energy_dongle_from_service_info(info)
    assert d is not None
    assert d.host == "192.168.1.2"


def test_energy_dongle_from_service_info_ipv6_only() -> None:
    info = ServiceInfo(
        _ENERGY_DONGLE_SERVICE_TYPE,
        "x._energydongle._tcp.local.",
        port=8080,
        properties={"p": "/ws"},
        parsed_addresses=["2001:db8::5"],
    )
    d = _energy_dongle_from_service_info(info)
    assert d is not None
    assert d.host == "2001:db8::5"
    assert d.port == 8080


def test_energy_dongle_from_service_info_no_addresses() -> None:
    info = ServiceInfo(
        _ENERGY_DONGLE_SERVICE_TYPE,
        "x._energydongle._tcp.local.",
        port=80,
        properties={"p": "/ws"},
        parsed_addresses=[],
    )
    assert _energy_dongle_from_service_info(info) is None


def test_discover_energy_dongles_dedupes_by_host_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info_a = _sample_service_info(
        name="A._energydongle._tcp.local.",
        addresses=["192.168.1.1"],
    )
    info_b = _sample_service_info(
        name="B._energydongle._tcp.local.",
        addresses=["192.168.1.1"],
        properties={"p": "/other", "v": "9"},
    )

    fake_holder: list[object] = []

    class FakeAsyncZeroconf:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.zeroconf = MagicMock()
            self._listener: object | None = None
            fake_holder.append(self)

        async def __aenter__(self) -> FakeAsyncZeroconf:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def async_add_service_listener(
            self,
            type_: str,
            listener: object,
        ) -> None:
            assert type_ == _ENERGY_DONGLE_SERVICE_TYPE
            self._listener = listener

        async def async_remove_all_service_listeners(self) -> None:
            pass

        async def async_get_service_info(
            self,
            type_: str,
            name: str,
            timeout: int = 3000,
        ) -> ServiceInfo | None:
            if name == info_a.name:
                return info_a
            if name == info_b.name:
                return info_b
            return None

    monkeypatch.setattr(
        "homey_energy_dongle_ws.discovery.AsyncZeroconf",
        FakeAsyncZeroconf,
    )

    async def run() -> list[DiscoveredEnergyDongle]:
        task = asyncio.create_task(discover_energy_dongles(timeout_s=1.0))

        async def inject() -> None:
            for _ in range(100):
                await asyncio.sleep(0.005)
                if fake_holder and getattr(fake_holder[0], "_listener", None):
                    break
            assert fake_holder and fake_holder[0]._listener is not None
            listener = fake_holder[0]._listener
            zc = fake_holder[0].zeroconf
            listener.add_service(zc, _ENERGY_DONGLE_SERVICE_TYPE, info_a.name)
            listener.add_service(zc, _ENERGY_DONGLE_SERVICE_TYPE, info_b.name)

        gathered = await asyncio.gather(task, inject())
        return gathered[0]

    out = asyncio.run(run())
    assert len(out) == 1
    assert out[0].host == "192.168.1.1"
    assert out[0].ws_path == "/other"
    assert out[0].version == "9"


def test_listener_remove_service_drops_energy_dongle() -> None:
    """When the last mDNS name for a host:port goes away, the entry is removed."""

    info = _sample_service_info(name="Only._energydongle._tcp.local.")

    class FakeAiozc:
        async def async_get_service_info(
            self,
            type_: str,
            name: str,
            timeout: int = 3000,
        ) -> ServiceInfo | None:
            return info

    async def run() -> None:
        results: dict[tuple[str, int], DiscoveredEnergyDongle] = {}
        lock = asyncio.Lock()
        listener = _EnergyDongleListener(
            FakeAiozc(),
            results,
            lock,
            resolve_timeout_ms=1000,
        )
        await listener._ingest(_ENERGY_DONGLE_SERVICE_TYPE, info.name)
        assert len(results) == 1
        await listener._remove(info.name)
        assert len(results) == 0

    asyncio.run(run())


def test_discover_energy_dongles_negative_timeout_raises() -> None:
    async def run() -> None:
        await discover_energy_dongles(timeout_s=-1.0)

    with pytest.raises(ValueError, match="timeout_s"):
        asyncio.run(run())


# --- Optional live mDNS (same LAN as an Energy Dongle; not for CI) ---


@pytest.mark.integration
@pytest.mark.mdns_live
@pytest.mark.skipif(
    os.environ.get("HOMEY_MDNS_LIVE") != "1",
    reason="Set HOMEY_MDNS_LIVE=1 to run live mDNS discovery tests.",
)
def test_live_discover_energy_dongles() -> None:
    """Best-effort browse; may return an empty list if nothing is advertised."""

    async def run() -> list[DiscoveredEnergyDongle]:
        return await discover_energy_dongles(timeout_s=3.0)

    found = asyncio.run(run())
    assert isinstance(found, list)
    for d in found:
        assert d.port >= 0
        assert d.host
