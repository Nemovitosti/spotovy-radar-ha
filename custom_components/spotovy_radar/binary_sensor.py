"""Binární senzor „Levná elektřina teď“: běžící čtvrthodina v pásmu cheap nebo negative."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.util import dt as dt_util

from .entity import SpotovyRadarEntity
from .forecast import CHEAP_BANDS, current_point

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SpotovyRadarConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpotovyRadarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([CheapNowSensor(entry.runtime_data, "cheap_now")])


class CheapNowSensor(SpotovyRadarEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool | None:
        point = current_point(self.coordinator.data.points, dt_util.utcnow())
        return None if point is None else point.band in CHEAP_BANDS
