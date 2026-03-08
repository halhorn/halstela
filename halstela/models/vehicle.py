"""車両データクラス"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Vehicle:
    id: str
    vin: str
    display_name: str
    state: str
