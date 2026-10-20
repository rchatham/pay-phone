"""Functional no-key public services, with fixed-host bounded weather I/O."""
from __future__ import annotations

import http.client
import json
import logging
import math
import random
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from typing import Callable

logger = logging.getLogger(__name__)
WEATHER_HOST = "api.open-meteo.com"
WEATHER_TIMEOUT = 4.0
MAX_WEATHER_BYTES = 32768
CACHE_SECONDS = 600
MAX_STALE_SECONDS = 21600
# Even DNS resolution and slow-drip response headers must not pin a call. At
# most one background request exists process-wide; a stuck resolver prevents
# further requests rather than creating an unbounded set of abandoned threads.
_REQUEST_GATE = threading.Lock()
JOKES = (
    "Why did the bicycle fall over? It was two tired.",
    "What do you call a bear with no teeth? A gummy bear.",
    "Why did the tomato blush? It saw the salad dressing.",
    "What did one wall say to the other? I'll meet you at the corner.",
)
CONDITIONS = {
    0: "clear skies", 1: "mainly clear skies", 2: "partly cloudy skies", 3: "overcast skies",
    45: "fog", 48: "depositing rime fog", 51: "light drizzle", 53: "moderate drizzle",
    55: "dense drizzle", 56: "light freezing drizzle", 57: "dense freezing drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain", 66: "light freezing rain",
    67: "heavy freezing rain", 71: "slight snow", 73: "moderate snow", 75: "heavy snow",
    77: "snow grains", 80: "slight rain showers", 81: "moderate rain showers",
    82: "violent rain showers", 85: "slight snow showers", 86: "heavy snow showers",
    95: "a thunderstorm", 96: "a thunderstorm with slight hail", 99: "a thunderstorm with heavy hail",
}


def current_time_text(zone: str, now: datetime | None = None) -> str:
    """Use the real clock, OS-local zone or an explicit IANA timezone."""
    now = now or datetime.now(timezone.utc)
    current = now.astimezone(None if zone == "local" else ZoneInfo(zone))
    return f"The current time is {current.strftime('%I:%M %p')}, {current.strftime('%A, %B %d, %Y')}, {current.tzname()}."


def joke_text() -> str:
    return random.choice(JOKES)


def fetch_weather(settings: dict) -> dict:
    """One HTTPS GET, no redirects/proxies/retries/custom hosts, bounded response."""
    query = urlencode({
        "latitude": settings["latitude"], "longitude": settings["longitude"],
        "temperature_unit": settings["units"], "current": "temperature_2m,weather_code",
        "timezone": "UTC", "forecast_days": 1,
    })
    connection = http.client.HTTPSConnection(WEATHER_HOST, timeout=WEATHER_TIMEOUT)
    deadline = time.monotonic() + WEATHER_TIMEOUT
    try:
        connection.request("GET", "/v1/forecast?" + query,
                           headers={"User-Agent": "PayphoneInformationBooth/1.0", "Accept": "application/json"})
        if connection.sock is not None:
            connection.sock.settimeout(max(0.01, deadline - time.monotonic()))
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("Weather service returned an unsuccessful status")
        if response.getheader("Content-Type", "").split(";")[0].strip() != "application/json":
            raise ValueError("Weather service returned non-JSON content")
        chunks = []
        length = 0
        while length <= MAX_WEATHER_BYTES:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Weather request timed out")
            if connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = response.read1(min(4096, MAX_WEATHER_BYTES + 1 - length))
            if not chunk:
                break
            chunks.append(chunk)
            length += len(chunk)
        if length > MAX_WEATHER_BYTES:
            raise ValueError("Weather response is too large")
        return json.loads(b"".join(chunks))
    finally:
        connection.close()


def validate_weather(data: object, units: str) -> str:
    if not isinstance(data, dict) or not isinstance(data.get("current"), dict):
        raise ValueError("Missing current weather")
    current = data["current"]
    number = current.get("temperature_2m")
    code = current.get("weather_code")
    if type(number) not in (int, float) or not math.isfinite(number) or not -150 <= number <= 150:
        raise ValueError("Invalid temperature")
    if type(code) is not int or code not in CONDITIONS:
        raise ValueError("Invalid weather condition")
    returned_units = data.get("current_units")
    if not isinstance(returned_units, dict) or returned_units.get("temperature_2m") != ("°C" if units == "celsius" else "°F"):
        raise ValueError("Weather unit mismatch")
    if data.get("utc_offset_seconds") != 0:
        raise ValueError("Weather timestamp must be UTC")
    timestamp = datetime.fromisoformat(current["time"])
    if timestamp.tzinfo is not None and timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("Weather timestamp has a non-UTC offset")
    timestamp = timestamp.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - timestamp).total_seconds()
    if not -900 <= age <= 3600:
        raise ValueError("Weather service data is not current")
    return (f"For the configured location, the temperature is {number:g} degrees {units}, "
            f"with {CONDITIONS[code]}. Data from Open Meteo, updated at {timestamp.strftime('%H:%M')} UTC.")


def bounded_weather(settings: dict, active: Callable[[], bool]) -> dict:
    """Enforce a caller wall-clock bound, including DNS and header parsing.

    The worker never touches audio, hardware, cache or mutable Booth content.
    Cancellation discards its eventual result. Socket-level timeouts still
    apply; the process-wide gate caps outstanding work even if DNS gets stuck.
    """
    if not active():
        raise TimeoutError("Weather request cancelled")
    if not _REQUEST_GATE.acquire(blocking=False):
        raise TimeoutError("A weather request is still outstanding")
    done = threading.Event()
    outcome: dict = {}

    def request() -> None:
        try:
            outcome["data"] = fetch_weather(dict(settings))
        except Exception as exc:
            outcome["error"] = exc
        finally:
            _REQUEST_GATE.release()
            done.set()

    worker = threading.Thread(target=request, name="booth-weather", daemon=True)
    try:
        worker.start()
    except Exception:
        _REQUEST_GATE.release()
        raise
    deadline = time.monotonic() + WEATHER_TIMEOUT
    while active() and time.monotonic() < deadline:
        if done.wait(min(0.05, max(0.001, deadline - time.monotonic()))):
            if "error" in outcome:
                raise OSError(f"Weather request failed: {outcome['error']}") from outcome["error"]
            return outcome["data"]
    raise TimeoutError("Weather request cancelled or timed out")


class WeatherService:
    def __init__(self) -> None:
        self.cache: dict[tuple, tuple[float, str]] = {}

    def report(self, settings: dict, active: Callable[[], bool] = lambda: True) -> str:
        key = (settings["latitude"], settings["longitude"], settings["units"])
        cached = self.cache.get(key)
        if cached and time.monotonic() - cached[0] <= CACHE_SECONDS:
            return "Recent cached weather. " + cached[1]
        try:
            text = validate_weather(bounded_weather(settings, active), settings["units"])
        except (OSError, ValueError, TypeError, KeyError, http.client.HTTPException, RecursionError) as exc:
            logger.warning("Weather unavailable: %s", exc)
            if cached and time.monotonic() - cached[0] <= MAX_STALE_SECONDS:
                return "Weather is offline. This is stale cached weather, not a current report. " + cached[1]
            return "Weather is currently unavailable. Please try again later."
        self.cache[key] = (time.monotonic(), text)
        # Keep memory bounded even after repeated location edits.
        if len(self.cache) > 16:
            del self.cache[next(iter(self.cache))]
        return text
