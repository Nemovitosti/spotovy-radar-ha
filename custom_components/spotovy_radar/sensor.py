"""Senzory: cena teď, spot teď, cenové pásmo, pravděpodobnost záporné ceny, nejlevnější okno."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.util import dt as dt_util

from .const import CHEAPEST_WINDOW_HOURS, CHEAPEST_WITHIN
from .coordinator import SpotovyRadarCoordinator
from .entity import SpotovyRadarEntity
from .forecast import BANDS, Forecast, cheapest_window, current_point, upcoming

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SpotovyRadarConfigEntry

PRICE_UNIT = "CZK/kWh"


def _iso(moment: datetime) -> str:
    return dt_util.as_local(moment).isoformat()


def _price_now(data: Forecast, now: datetime) -> float | None:
    point = current_point(data.points, now)
    return None if point is None else point.price


def _price_attrs(data: Forecast, now: datetime) -> dict[str, Any]:
    return {
        "price_type": "final" if data.has_final else "spot",
        "vat_included": data.vat_included,
        "forecast_issued_at": None if data.issued_at is None else _iso(data.issued_at),
        "official_until": None if data.official_until is None else _iso(data.official_until),
        "forecast": [
            {
                "start": _iso(p.start),
                "end": _iso(p.end),
                "price": p.price,
                "price_p10": p.price_p10,
                "price_p90": p.price_p90,
                "official": p.official,
                "band": p.band,
            }
            for p in upcoming(data.points, now)
        ],
    }


def _spot_now(data: Forecast, now: datetime) -> float | None:
    point = current_point(data.points, now)
    return None if point is None else point.spot


def _spot_attrs(data: Forecast, now: datetime) -> dict[str, Any]:
    point = current_point(data.points, now)
    if point is None:
        return {}
    return {"spot_p10": point.spot_p10, "spot_p90": point.spot_p90, "official": point.official}


def _band_now(data: Forecast, now: datetime) -> str | None:
    point = current_point(data.points, now)
    return None if point is None else point.band


def _negative_now(data: Forecast, now: datetime) -> float | None:
    point = current_point(data.points, now)
    return None if point is None else round(point.p_negative * 100, 1)


def _cheapest_start(data: Forecast, now: datetime) -> datetime | None:
    point = cheapest_window(data.points, now, hours=CHEAPEST_WINDOW_HOURS, within=CHEAPEST_WITHIN)
    return None if point is None else point.start


def _issued_at(data: Forecast, _now: datetime) -> datetime | None:
    return data.issued_at


@dataclass(frozen=True, kw_only=True)
class SpotovyRadarSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Forecast, datetime], float | str | datetime | None]
    attrs_fn: Callable[[Forecast, datetime], dict[str, Any]] | None = None


SENSORS: tuple[SpotovyRadarSensorDescription, ...] = (
    SpotovyRadarSensorDescription(
        key="price_now",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=2,
        value_fn=_price_now,
        attrs_fn=_price_attrs,
    ),
    SpotovyRadarSensorDescription(
        key="spot_now",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=2,
        value_fn=_spot_now,
        attrs_fn=_spot_attrs,
    ),
    SpotovyRadarSensorDescription(
        key="band_now",
        device_class=SensorDeviceClass.ENUM,
        options=list(BANDS),
        value_fn=_band_now,
    ),
    SpotovyRadarSensorDescription(
        key="negative_probability",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=_negative_now,
    ),
    SpotovyRadarSensorDescription(
        key="cheapest_window_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_cheapest_start,
    ),
    SpotovyRadarSensorDescription(
        key="forecast_issued_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_issued_at,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpotovyRadarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SpotovyRadarSensor(coordinator, d) for d in SENSORS)


class SpotovyRadarSensor(SpotovyRadarEntity, SensorEntity):
    entity_description: SpotovyRadarSensorDescription
    # Výhled má stovky bodů, do historie (recorder) se neukládá.
    _unrecorded_attributes = frozenset({"forecast"})

    def __init__(
        self, coordinator: SpotovyRadarCoordinator, description: SpotovyRadarSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | str | datetime | None:
        return self.entity_description.value_fn(self.coordinator.data, dt_util.utcnow())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data, dt_util.utcnow())
