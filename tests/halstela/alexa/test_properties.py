"""halstela.alexa.properties のテスト"""

import pytest

from halstela.alexa.properties import (
    AlexaProperty,
    climate_context_property,
    power_state_from_climate,
    power_state_property,
    report_state_properties,
    temperature_property,
)
from halstela.models.climate_state import ClimateState


class TestAlexaProperty:
    def test_to_serializable(self) -> None:
        prop = AlexaProperty(
            namespace="Alexa.PowerController",
            name="powerState",
            value="ON",
            time_of_sample="2026-01-01T00:00:00+00:00",
            uncertainty_in_milliseconds=0,
        )
        assert prop.to_serializable() == {
            "namespace": "Alexa.PowerController",
            "name": "powerState",
            "value": "ON",
            "timeOfSample": "2026-01-01T00:00:00+00:00",
            "uncertaintyInMilliseconds": 0,
        }

    def test_power_state_from_climate(self) -> None:
        on = ClimateState(
            inside_temp=21.0, outside_temp=5.0, is_climate_on=True, driver_temp_setting=22.0
        )
        off = ClimateState(
            inside_temp=21.0, outside_temp=5.0, is_climate_on=False, driver_temp_setting=22.0
        )
        assert power_state_from_climate(climate=on).value == "ON"
        assert power_state_from_climate(climate=off).value == "OFF"

    def test_power_state_factory(self) -> None:
        prop = power_state_property(state="OFF", sampled_at="2026-01-01T00:00:00+00:00")
        assert prop.namespace == "Alexa.PowerController"
        assert prop.name == "powerState"
        assert prop.value == "OFF"

    def test_report_state_includes_power_temperature_and_connectivity(self) -> None:
        climate = ClimateState(
            inside_temp=21.0, outside_temp=5.0, is_climate_on=True, driver_temp_setting=22.0
        )
        props = report_state_properties(climate=climate)
        assert [p.name for p in props] == ["powerState", "temperature", "connectivity"]
        assert props[0].value == "ON"
        assert props[1].value == {"value": 21.0, "scale": "CELSIUS"}

    def test_climate_context_requires_temperature(self) -> None:
        climate = ClimateState(
            inside_temp=None, outside_temp=None, is_climate_on=False, driver_temp_setting=22.0
        )
        with pytest.raises(ValueError, match="inside_temp"):
            climate_context_property(climate=climate)

    def test_climate_context_is_temperature(self) -> None:
        climate = ClimateState(
            inside_temp=18.0, outside_temp=5.0, is_climate_on=False, driver_temp_setting=22.0
        )
        prop = climate_context_property(climate=climate, sampled_at="2026-01-01T00:00:00+00:00")
        assert prop == temperature_property(celsius=18.0, sampled_at="2026-01-01T00:00:00+00:00")
