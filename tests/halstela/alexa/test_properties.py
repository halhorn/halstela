"""halstela.alexa.properties のテスト"""

from halstela.alexa.properties import (
    AlexaProperty,
    climate_context_properties,
    power_state_property,
    properties_as_dicts,
    report_state_properties,
    temperature_property,
)
from halstela.models.climate_state import ClimateState


class TestAlexaProperty:
    def test_to_dict(self) -> None:
        prop = AlexaProperty(
            namespace="Alexa.PowerController",
            name="powerState",
            value="ON",
            time_of_sample="2026-01-01T00:00:00+00:00",
            uncertainty_in_milliseconds=0,
        )
        assert prop.to_dict() == {
            "namespace": "Alexa.PowerController",
            "name": "powerState",
            "value": "ON",
            "timeOfSample": "2026-01-01T00:00:00+00:00",
            "uncertaintyInMilliseconds": 0,
        }

    def test_power_state_factory(self) -> None:
        prop = power_state_property("OFF", "2026-01-01T00:00:00+00:00")
        assert prop.namespace == "Alexa.PowerController"
        assert prop.name == "powerState"
        assert prop.value == "OFF"

    def test_report_state_includes_power_and_temperature(self) -> None:
        climate = ClimateState(
            inside_temp=21.0, outside_temp=5.0, is_climate_on=True, driver_temp_setting=22.0
        )
        props = report_state_properties(climate)
        assert [p.name for p in props] == ["powerState", "temperature", "connectivity"]
        assert props[0].value == "ON"
        assert props[1].value == {"value": 21.0, "scale": "CELSIUS"}

    def test_climate_context_skips_missing_temperature(self) -> None:
        climate = ClimateState(
            inside_temp=None, outside_temp=None, is_climate_on=False, driver_temp_setting=22.0
        )
        props = climate_context_properties(climate)
        assert [p.name for p in props] == ["connectivity"]

    def test_properties_as_dicts(self) -> None:
        prop = temperature_property(18.0, "2026-01-01T00:00:00+00:00")
        assert properties_as_dicts([prop]) == [prop.to_dict()]
