"""halstela.models.climate_state のテスト"""

from halstela.models.climate_state import ClimateState


class TestClimateState:
    def test_create_with_temps(self) -> None:
        cs = ClimateState(
            inside_temp=22.5,
            outside_temp=18.0,
            is_climate_on=True,
            driver_temp_setting=21.0,
        )
        assert cs.inside_temp == 22.5
        assert cs.outside_temp == 18.0
        assert cs.is_climate_on is True
        assert cs.driver_temp_setting == 21.0

    def test_create_with_none_temps(self) -> None:
        cs = ClimateState(
            inside_temp=None,
            outside_temp=None,
            is_climate_on=False,
            driver_temp_setting=0.0,
        )
        assert cs.inside_temp is None
        assert cs.outside_temp is None
