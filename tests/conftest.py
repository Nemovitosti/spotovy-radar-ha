"""Společné fixtures: odpověď API `spotovyradar-forecast/1` a zapnuté vlastní integrace."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from custom_components.spotovy_radar.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry

API_URL = "https://spotovyradar.cz/api/v1/forecast"
API_KEY = "sr_live_abcdefgh_" + "A" * 43
NOW = datetime(2026, 10, 24, 12, 7, tzinfo=UTC)
SLOT = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _point(index: int, *, final: bool) -> dict[str, Any]:
    start = SLOT + index * timedelta(minutes=15)
    official = index < 8
    # 12:15 záporná cena, 18:00–21:00 nejlevnější blok predikce, jinak 2 Kč.
    if index == 1:
        spot, band = -0.5, "negative"
    elif 24 <= index < 36:
        spot, band = 0.4, "cheap"
    else:
        spot, band = 2.0, "normal"
    low, high = (spot, spot) if official else (spot - 0.5, spot + 0.5)
    point: dict[str, Any] = {
        "start": _iso(start),
        "end": _iso(start + timedelta(minutes=15)),
        "source": "official" if official else "forecast",
        "spot": spot,
        "spot_p10": low,
        "spot_p90": high,
        "p_negative": 1.0 if spot < 0 else 0.05,
        "band": band,
    }
    if final:
        point["final"] = round(spot + 2.84, 4)
        point["final_p10"] = round(low + 2.84, 4)
        point["final_p90"] = round(high + 2.84, 4)
    return point


def forecast_body(*, final: bool = True, count: int = 288) -> dict[str, Any]:
    points = [_point(i, final=final) for i in range(count)]
    return {
        "format": "spotovyradar-forecast/1",
        "generated_at": _iso(NOW),
        "forecast_issued_at": "2026-10-24T11:05:00Z",
        "official_until": "2026-10-24T14:00:00Z",
        "currency": "CZK",
        "unit": "CZK/kWh",
        "interval_minutes": 15,
        "has_final": final,
        "vat_included": final,
        "now": points[0] if points else None,
        "points": points,
    }


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Bez tohohle Home Assistant integraci z `custom_components` nenačte."""


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Spotový Radar",
        data={CONF_API_KEY: API_KEY},
        unique_id="abcdefgh",
    )
