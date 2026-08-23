"""Alexa Smart Home の property。"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from halstela.models.climate_state import ClimateState


@dataclass(frozen=True)
class AlexaProperty:
    """Alexa イベント / StateReport に載せる 1 プロパティ。"""

    namespace: str
    name: str
    value: str | dict[str, Any]
    time_of_sample: str
    uncertainty_in_milliseconds: int = 0

    def to_serializable(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "name": self.name,
            "value": self.value,
            "timeOfSample": self.time_of_sample,
            "uncertaintyInMilliseconds": self.uncertainty_in_milliseconds,
        }


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def power_state_property(state: str, sampled_at: str | None = None) -> AlexaProperty:
    return AlexaProperty(
        namespace="Alexa.PowerController",
        name="powerState",
        value=state,
        time_of_sample=sampled_at or iso_now(),
        uncertainty_in_milliseconds=0,
    )


def temperature_property(celsius: float, sampled_at: str | None = None) -> AlexaProperty:
    return AlexaProperty(
        namespace="Alexa.TemperatureSensor",
        name="temperature",
        value={"value": celsius, "scale": "CELSIUS"},
        time_of_sample=sampled_at or iso_now(),
        uncertainty_in_milliseconds=60000,
    )


def connectivity_ok_property(sampled_at: str | None = None) -> AlexaProperty:
    return AlexaProperty(
        namespace="Alexa.EndpointHealth",
        name="connectivity",
        value={"value": "OK"},
        time_of_sample=sampled_at or iso_now(),
        uncertainty_in_milliseconds=0,
    )


def climate_context_property(
    climate: ClimateState, sampled_at: str | None = None
) -> AlexaProperty | None:
    if climate.inside_temp is None:
        return None
    return temperature_property(celsius=climate.inside_temp, sampled_at=sampled_at)


def report_state_properties(climate: ClimateState) -> list[AlexaProperty]:
    now = iso_now()
    power = power_state_property(state="ON" if climate.is_climate_on else "OFF", sampled_at=now)
    climate_prop = climate_context_property(climate=climate, sampled_at=now)
    connectivity = connectivity_ok_property(sampled_at=now)
    if climate_prop is None:
        return [power, connectivity]
    return [power, climate_prop, connectivity]
