"""Nastavení přes UI: ověření klíče, chyby, duplicita a výměna klíče (reauth)."""

from __future__ import annotations

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.spotovy_radar.const import DOMAIN

from .conftest import API_KEY, API_URL, forecast_body

NEW_KEY = "sr_live_ijklmnop_" + "B" * 43


async def _start(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


async def test_user_flow_creates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(API_URL, json=forecast_body())
    flow_id = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_API_KEY: f"  {API_KEY} "}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Spotový Radar"
    assert result["data"] == {CONF_API_KEY: API_KEY}
    assert result["result"].unique_id == "abcdefgh"
    # Klíč jen v hlavičce, nikdy v adrese.
    _, url, _, headers = aioclient_mock.mock_calls[0]
    assert headers["Authorization"] == f"Bearer {API_KEY}"
    assert API_KEY not in str(url)


async def test_invalid_format_does_not_call_api(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    flow_id = await _start(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_API_KEY: "abc"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_format"}
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, "invalid_auth"),
        (402, "subscription_required"),
        (429, "rate_limited"),
        (503, "cannot_connect"),
    ],
)
async def test_api_errors_are_shown_and_flow_recovers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status: int, error: str
) -> None:
    aioclient_mock.get(API_URL, status=status, json={"error": "x", "message": "x"})
    flow_id = await _start(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_API_KEY: API_KEY})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, json=forecast_body())
    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_API_KEY: API_KEY})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_network_error_and_unknown_body(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(API_URL, exc=aiohttp.ClientConnectionError())
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_API_KEY: API_KEY})
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, json={"format": "neco-jineho/1"})
    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_API_KEY: API_KEY})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_same_key_twice_aborts(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_entry: MockConfigEntry
) -> None:
    mock_entry.add_to_hass(hass)
    aioclient_mock.get(API_URL, json=forecast_body())
    flow_id = await _start(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_API_KEY: API_KEY})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_replaces_key(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_entry: MockConfigEntry
) -> None:
    mock_entry.add_to_hass(hass)
    aioclient_mock.get(API_URL, json=forecast_body())
    result = await mock_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, status=401)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: NEW_KEY}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_URL, json=forecast_body())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: NEW_KEY}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data[CONF_API_KEY] == NEW_KEY
