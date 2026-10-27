"""Spuštění integrace, hodnoty entit, posun čtvrthodin a chyby API po nastavení."""

from __future__ import annotations

from datetime import timedelta

import pytest
from custom_components.spotovy_radar.const import DOMAIN, UPDATE_INTERVAL
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import API_URL, NOW, forecast_body


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id is not None, key
    return entity_id


def _state(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str):  # type: ignore[no-untyped-def]
    state = hass.states.get(_entity_id(hass, entry, platform, key))
    assert state is not None, key
    return state


@pytest.fixture(autouse=True)
def _frozen_time(freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to(NOW)


async def test_entities_with_final_price(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_entry: MockConfigEntry
) -> None:
    aioclient_mock.get(API_URL, json=forecast_body())
    await _setup(hass, mock_entry)
    assert mock_entry.state is ConfigEntryState.LOADED

    price = _state(hass, mock_entry, "sensor", "price_now")
    assert float(price.state) == 4.84
    assert price.attributes["unit_of_measurement"] == "CZK/kWh"
    assert price.attributes["price_type"] == "final"
    assert price.attributes["vat_included"] is True
    forecast = price.attributes["forecast"]
    assert len(forecast) == 288
    assert forecast[1]["price"] == round(-0.5 + 2.84, 4)
    assert forecast[1]["band"] == "negative"

    spot = _state(hass, mock_entry, "sensor", "spot_now")
    assert float(spot.state) == 2.0
    assert spot.attributes["official"] is True

    assert _state(hass, mock_entry, "sensor", "band_now").state == "normal"
    assert float(_state(hass, mock_entry, "sensor", "negative_probability").state) == 5.0
    # Nejlevnější 3 h v příštích 24 h: blok 0,4 Kč od 18:00 UTC.
    cheapest = _state(hass, mock_entry, "sensor", "cheapest_window_start")
    assert cheapest.state == "2026-10-24T18:00:00+00:00"
    issued = _state(hass, mock_entry, "sensor", "forecast_issued_at")
    assert issued.state == "2026-10-24T11:05:00+00:00"
    assert _state(hass, mock_entry, "binary_sensor", "cheap_now").state == STATE_OFF


async def test_spot_only_without_tariff(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_entry: MockConfigEntry
) -> None:
    aioclient_mock.get(API_URL, json=forecast_body(final=False))
    await _setup(hass, mock_entry)

    price = _state(hass, mock_entry, "sensor", "price_now")
    assert float(price.state) == 2.0
    assert price.attributes["price_type"] == "spot"


async def test_quarter_hour_moves_without_new_data(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    aioclient_mock.get(API_URL, json=forecast_body())
    await _setup(hass, mock_entry)

    # 12:15:01: běží záporná čtvrthodina. Odpověď API je pořád ta z 12:07, entity se
    # posunou podle hodin.
    freezer.move_to(NOW + timedelta(minutes=8, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert float(_state(hass, mock_entry, "sensor", "spot_now").state) == -0.5
    assert _state(hass, mock_entry, "sensor", "band_now").state == "negative"
    assert float(_state(hass, mock_entry, "sensor", "negative_probability").state) == 100.0
    assert _state(hass, mock_entry, "binary_sensor", "cheap_now").state == STATE_ON


async def test_polls_every_five_minutes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    aioclient_mock.get(API_URL, json=forecast_body())
    await _setup(hass, mock_entry)
    calls = aioclient_mock.call_count

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == calls + 1
    _, url, _, _ = aioclient_mock.mock_calls[-1]
    assert url.query["hours"] == "72"


async def test_outage_after_setup_makes_entities_unavailable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    aioclient_mock.get(API_URL, json=forecast_body())
    await _setup(hass, mock_entry)

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, status=503)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _state(hass, mock_entry, "sensor", "price_now").state == STATE_UNAVAILABLE


async def test_revoked_key_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_entry: MockConfigEntry
) -> None:
    aioclient_mock.get(API_URL, status=401)
    mock_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]


async def test_subscription_ended_retries_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_entry: MockConfigEntry
) -> None:
    aioclient_mock.get(API_URL, status=402)
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_entry: MockConfigEntry
) -> None:
    aioclient_mock.get(API_URL, json=forecast_body())
    await _setup(hass, mock_entry)

    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.NOT_LOADED
