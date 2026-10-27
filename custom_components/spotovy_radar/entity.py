"""Společný základ entit: zařízení „Spotový Radar“ a posun na začátku každé čtvrthodiny."""

from __future__ import annotations

from datetime import datetime

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BASE_URL, DOMAIN
from .coordinator import SpotovyRadarCoordinator


class SpotovyRadarEntity(CoordinatorEntity[SpotovyRadarCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SpotovyRadarCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Spotový Radar",
            manufacturer="Spotový Radar",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"{BASE_URL}/prehled",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Běžící čtvrthodina se mění i mezi dotazy na API.
        self.async_on_remove(
            async_track_time_change(self.hass, self._quarter_hour, minute=[0, 15, 30, 45], second=1)
        )

    @callback
    def _quarter_hour(self, _now: datetime) -> None:
        self.async_write_ha_state()
