"""Spotový Radar: ceny elektřiny v ČR a predikce na 72 hodin po čtvrthodinách."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SpotovyRadarClient
from .coordinator import SpotovyRadarCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type SpotovyRadarConfigEntry = ConfigEntry[SpotovyRadarCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SpotovyRadarConfigEntry) -> bool:
    client = SpotovyRadarClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    coordinator = SpotovyRadarCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SpotovyRadarConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
