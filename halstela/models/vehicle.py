"""車両データクラス"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Vehicle:
    id: str
    vin: str
    display_name: str
    state: str
