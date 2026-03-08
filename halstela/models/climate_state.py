"""気候状態データクラス"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ClimateState:
    inside_temp: float | None
    outside_temp: float | None
    is_climate_on: bool
    driver_temp_setting: float
