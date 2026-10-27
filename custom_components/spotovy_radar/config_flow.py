"""Nastavení přes UI: vložení API klíče a jeho výměna, když přestane platit."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import AuthError, RateLimitError, SpotovyRadarClient, SpotovyRadarError, SubscriptionError
from .const import ACCOUNT_URL, DOMAIN
from .forecast import key_prefix

SCHEMA = vol.Schema(
    {vol.Required(CONF_API_KEY): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
)


class SpotovyRadarConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, key: str) -> str | None:
        """Kód chyby pro formulář, nebo None, když klíč funguje."""
        if key_prefix(key) is None:
            return "invalid_format"
        client = SpotovyRadarClient(async_get_clientsession(self.hass), key)
        try:
            await client.forecast(hours=1)
        except AuthError:
            return "invalid_auth"
        except SubscriptionError:
            return "subscription_required"
        except RateLimitError:
            return "rate_limited"
        except SpotovyRadarError:
            return "cannot_connect"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            if (error := await self._validate(key)) is None:
                await self.async_set_unique_id(key_prefix(key))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Spotový Radar", data={CONF_API_KEY: key})
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA,
            errors=errors,
            description_placeholders={"account_url": ACCOUNT_URL},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            if (error := await self._validate(key)) is None:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: key}
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=SCHEMA,
            errors=errors,
            description_placeholders={"account_url": ACCOUNT_URL},
        )
