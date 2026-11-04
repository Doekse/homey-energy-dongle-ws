"""Tests for ``detect_dsmr_version``."""

from __future__ import annotations

import pytest

from homey_energy_dongle_ws.parser import DSMR_VERSIONS, detect_dsmr_version


def _telegram(*lines: str, checksum: str | None = "0000") -> str:
    """Build a framed telegram. ``checksum=None`` is the DSMR 2.2 footer."""
    footer = "!\r\n" if checksum is None else f"!{checksum}\r\n"
    body = "".join(f"{line}\r\n" for line in lines)
    return f"/XMX5TEST\r\n\r\n{body}{footer}"


@pytest.mark.parametrize(
    ("telegram", "version"),
    [
        pytest.param(
            _telegram("1-3:0.2.8(50)", "0-0:96.1.1(ABCD)", "1-0:1.8.1(1*kWh)"),
            "5",
            id="dsmr5",
        ),
        pytest.param(
            _telegram("1-3:0.2.8(42)", "0-0:96.1.1(ABCD)", "1-0:1.8.1(1*kWh)"),
            "4",
            id="dsmr4",
        ),
        pytest.param(
            _telegram("0-0:96.1.1(ABCD)", "1-0:1.8.1(1*kWh)", checksum=None),
            "2.2",
            id="dsmr2",
        ),
        pytest.param(
            _telegram(
                "0-0:96.1.4(50217)",
                "1-0:1.8.3(0*kWh)",
                "1-0:1.8.4(0*kWh)",
                "1-0:31.4.0(999*A)",
            ),
            "5B",
            id="belgium-not-hungary",
        ),
        pytest.param(
            _telegram("1-0:1.4.0(00.052*kW)", "1-0:31.4.0(999*A)"),
            "5B",
            id="belgium-demand-only",
        ),
        pytest.param(
            _telegram(
                "0-0:42.0.0(ABCD)",
                "1-0:1.8.3(0*kWh)",
                "1-0:1.8.4(0*kWh)",
                "1-0:14.7.0(50.00*Hz)",
            ),
            "5EONHU",
            id="hungary-not-luxembourg",
        ),
        pytest.param(
            _telegram(
                "1-3:0.2.8(42)",
                "0-0:42.0.0(ABCD)",
                "1-0:3.8.0(1*kvarh)",
                "1-0:23.7.0(0*kvar)",
            ),
            "5L",
            id="luxembourg-not-dsmr4-or-sweden",
        ),
        pytest.param(
            _telegram(
                "1-0:0.0.0*255(1336001560)",
                "0-0:96.1.255*255(1ESY1336001560)",
                checksum=None,
            ),
            "Q3D",
            id="q3d-not-dsmr2",
        ),
        pytest.param(
            _telegram(
                "1-3:0.2.8(50)",
                "1-0:1.8.0(1*kWh)",
                "1-0:3.8.0(1*kvarh)",
                "1-0:23.7.0(0*kvar)",
            ),
            "5S",
            id="sweden-not-dsmr5",
        ),
        pytest.param(
            _telegram("1-3:0.2.8(50)", "1-0:31.4.0(16*A)", "0-0:96.1.1(ABCD)"),
            "5",
            id="fuse-threshold-is-not-belgium",
        ),
        pytest.param(
            _telegram("1-3:0.2.8(50)", "1-0:1.8.0(1*kWh)", checksum="B9F"),
            "5",
            id="short-checksum",
        ),
        pytest.param(
            _telegram("1-0:0.0.0(00000000)", "1-0:1.8.1(1*kWh)", "0-0:96.1.1(ABCD)"),
            None,
            id="iskra-is-unrecognized",
        ),
        pytest.param("not a telegram", None, id="garbage"),
        pytest.param("", None, id="empty"),
    ],
)
def test_detect_dsmr_version(telegram: str, version: str | None) -> None:
    detected = detect_dsmr_version(telegram)
    assert detected == version
    assert detected is None or detected in DSMR_VERSIONS
