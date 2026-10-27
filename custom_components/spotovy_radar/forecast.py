"""Odpověď `GET /api/v1/forecast` (formát `spotovyradar-forecast/1`) a výpočty nad ní.

Čisté funkce bez Home Assistantu a bez I/O, testuje je repozitář Spotového Radaru
(`tests/unit/test_integrations.py`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any

FORMAT = "spotovyradar-forecast/1"
BANDS = ("negative", "cheap", "normal", "expensive")
CHEAP_BANDS = frozenset({"negative", "cheap"})

_KEY_RE = re.compile(r"^sr_live_([a-z2-7]{8})_[A-Za-z0-9_-]{43}$")


@dataclass(frozen=True, slots=True)
class Point:
    start: datetime
    end: datetime
    official: bool
    spot: float
    spot_p10: float
    spot_p90: float
    p_negative: float
    band: str
    final: float | None = None
    final_p10: float | None = None
    final_p90: float | None = None

    @property
    def price(self) -> float:
        """Koncová cena, když je v účtu tarif, jinak spot (Kč/kWh)."""
        return self.spot if self.final is None else self.final

    @property
    def price_p10(self) -> float:
        return self.spot_p10 if self.final_p10 is None else self.final_p10

    @property
    def price_p90(self) -> float:
        return self.spot_p90 if self.final_p90 is None else self.final_p90


@dataclass(frozen=True, slots=True)
class Forecast:
    generated_at: datetime
    issued_at: datetime | None
    official_until: datetime | None
    has_final: bool
    vat_included: bool
    points: tuple[Point, ...]


def key_prefix(key: str) -> str | None:
    """Veřejný prefix klíče `sr_live_<prefix>_<tajemství>`, nebo None u jiného tvaru."""
    match = _KEY_RE.fullmatch(key)
    return match.group(1) if match else None


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Čas není text")
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise ValueError("Čas bez časové zóny")
    return moment


def _optional_time(value: Any) -> datetime | None:
    return None if value is None else _time(value)


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("Hodnota není číslo")
    return float(value)


def _optional_number(value: Any) -> float | None:
    return None if value is None else _number(value)


def _point(raw: Any) -> Point:
    if not isinstance(raw, dict):
        raise ValueError("Bod není objekt")
    band = raw.get("band")
    return Point(
        start=_time(raw.get("start")),
        end=_time(raw.get("end")),
        official=raw.get("source") == "official",
        spot=_number(raw.get("spot")),
        spot_p10=_number(raw.get("spot_p10")),
        spot_p90=_number(raw.get("spot_p90")),
        p_negative=_number(raw.get("p_negative")),
        band=band if band in BANDS else "normal",
        final=_optional_number(raw.get("final")),
        final_p10=_optional_number(raw.get("final_p10")),
        final_p90=_optional_number(raw.get("final_p90")),
    )


def parse_forecast(body: Any) -> Forecast:
    """Ověří formát odpovědi a převede ji na `Forecast`. Jiný tvar → ValueError."""
    if not isinstance(body, dict) or body.get("format") != FORMAT:
        raise ValueError("Neznámý formát odpovědi")
    points = body.get("points")
    if not isinstance(points, list):
        raise ValueError("Odpověď nemá body")
    return Forecast(
        generated_at=_time(body.get("generated_at")),
        issued_at=_optional_time(body.get("forecast_issued_at")),
        official_until=_optional_time(body.get("official_until")),
        has_final=bool(body.get("has_final")),
        vat_included=bool(body.get("vat_included")),
        points=tuple(sorted((_point(p) for p in points), key=lambda p: p.start)),
    )


def current_point(points: Iterable[Point], now: datetime) -> Point | None:
    """Čtvrthodina, která právě běží. Mezi dotazy na API se posouvá podle hodin."""
    return next((p for p in points if p.start <= now < p.end), None)


def upcoming(points: Iterable[Point], now: datetime) -> list[Point]:
    """Běžící a budoucí čtvrthodiny."""
    return [p for p in points if p.end > now]


def cheapest_window(
    points: Sequence[Point], now: datetime, *, hours: float, within: timedelta
) -> Point | None:
    """Začátek nejlevnějšího souvislého okna o délce `hours` od běžící čtvrthodiny, které
    skončí nejpozději za `within`. Rozhoduje průměr ceny (koncová, jinak spot)."""
    future = upcoming(points, now)
    size = round(hours * 4)
    if size < 1:
        return None
    limit = now + within
    best: tuple[float, Point] | None = None
    for i in range(len(future) - size + 1):
        window = future[i : i + size]
        if window[-1].end > limit:
            break
        if any(a.end != b.start for a, b in pairwise(window)):
            continue
        average = sum(p.price for p in window) / size
        if best is None or average < best[0]:
            best = (average, window[0])
    return None if best is None else best[1]
