"""Klient API Spotového Radaru. Klíč jde jen v hlavičce `Authorization`, nikdy v URL."""

from __future__ import annotations

import aiohttp

from .const import BASE_URL, HORIZON_HOURS
from .forecast import Forecast, parse_forecast

TIMEOUT = aiohttp.ClientTimeout(total=30)


class SpotovyRadarError(Exception):
    """Server nebo síť nedostupná, případně neznámá odpověď."""


class AuthError(SpotovyRadarError):
    """401: chybí, neplatí nebo je zrušený klíč."""


class SubscriptionError(SpotovyRadarError):
    """402: klíč bez aktivního tarifu Smart Home."""


class RateLimitError(SpotovyRadarError):
    """429: překročený limit dotazů."""


class SpotovyRadarClient:
    def __init__(
        self, session: aiohttp.ClientSession, api_key: str, base_url: str = BASE_URL
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._base_url = base_url

    async def forecast(self, hours: int = HORIZON_HOURS) -> Forecast:
        headers = {"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"}
        try:
            async with self._session.get(
                f"{self._base_url}/api/v1/forecast",
                params={"hours": str(hours)},
                headers=headers,
                timeout=TIMEOUT,
            ) as response:
                if response.status == 401:
                    raise AuthError
                if response.status == 402:
                    raise SubscriptionError
                if response.status == 429:
                    raise RateLimitError
                if response.status >= 400:
                    raise SpotovyRadarError(f"HTTP {response.status}")
                body = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SpotovyRadarError(str(err) or type(err).__name__) from err
        try:
            return parse_forecast(body)
        except ValueError as err:
            raise SpotovyRadarError(str(err)) from err
