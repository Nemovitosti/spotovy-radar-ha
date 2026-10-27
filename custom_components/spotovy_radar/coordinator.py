"""Stahování výhledu každých 5 minut, jeden dotaz pro všechny entity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthError, RateLimitError, SpotovyRadarClient, SpotovyRadarError, SubscriptionError
from .const import DOMAIN, LOGGER, UPDATE_INTERVAL
from .forecast import Forecast

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


class SpotovyRadarCoordinator(DataUpdateCoordinator[Forecast]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SpotovyRadarClient) -> None:
        super().__init__(
            hass, LOGGER, name=DOMAIN, config_entry=entry, update_interval=UPDATE_INTERVAL
        )
        self.client = client

    async def _async_update_data(self) -> Forecast:
        try:
            return await self.client.forecast()
        except AuthError as err:
            raise ConfigEntryAuthFailed("API klíč neplatí nebo byl zrušen") from err
        except SubscriptionError as err:
            raise UpdateFailed("API je součástí tarifu Smart Home") from err
        except RateLimitError as err:
            raise UpdateFailed("Překročený limit dotazů na API") from err
        except SpotovyRadarError as err:
            raise UpdateFailed(f"Spotový Radar je nedostupný: {err}") from err
