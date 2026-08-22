"""Alexa Smart Home の property オブジェクト組み立て。"""

from datetime import datetime, timezone
from typing import Any

from halstela.models.climate_state import ClimateState


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def power_state_property(state: str, sampled_at: str | None = None) -> dict[str, Any]:
    return {
        "namespace": "Alexa.PowerController",
        "name": "powerState",
        "value": state,
        "timeOfSample": sampled_at or iso_now(),
        "uncertaintyInMilliseconds": 0,
    }


def temperature_property(celsius: float, sampled_at: str | None = None) -> dict[str, Any]:
    return {
        "namespace": "Alexa.TemperatureSensor",
        "name": "temperature",
        "value": {"value": celsius, "scale": "CELSIUS"},
        "timeOfSample": sampled_at or iso_now(),
        "uncertaintyInMilliseconds": 60000,
    }


def connectivity_ok_property(sampled_at: str | None = None) -> dict[str, Any]:
    return {
        "namespace": "Alexa.EndpointHealth",
        "name": "connectivity",
        "value": {"value": "OK"},
        "timeOfSample": sampled_at or iso_now(),
        "uncertaintyInMilliseconds": 0,
    }


def climate_context_properties(climate: ClimateState) -> list[dict[str, Any]]:
    now = iso_now()
    properties: list[dict[str, Any]] = []
    if climate.inside_temp is not None:
        properties.append(temperature_property(climate.inside_temp, now))
    properties.append(connectivity_ok_property(now))
    return properties


def report_state_properties(climate: ClimateState) -> list[dict[str, Any]]:
    now = iso_now()
    properties = [power_state_property("ON" if climate.is_climate_on else "OFF", now)]
    properties.extend(climate_context_properties(climate))
    return properties
