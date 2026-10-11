from __future__ import annotations
from enum import Enum

class AreaUnit(str, Enum):
    M2 = 'm2'
    KM2 = 'km2'
    HA = 'ha'
    ACRE = 'acre'

class LengthUnit(str, Enum):
    M = 'm'
    KM = 'km'
    MI = 'mi'
    FT = 'ft'
_AREA_TO_M2: dict[AreaUnit, float] = {AreaUnit.M2: 1.0, AreaUnit.KM2: 1000000.0, AreaUnit.HA: 10000.0, AreaUnit.ACRE: 4046.8564224}
_LENGTH_TO_M: dict[LengthUnit, float] = {LengthUnit.M: 1.0, LengthUnit.KM: 1000.0, LengthUnit.MI: 1609.344, LengthUnit.FT: 0.3048}

class UnitConverter:

    @staticmethod
    def convert_area(value_m2: float, to_unit: AreaUnit | str) -> float:
        unit = AreaUnit(to_unit) if isinstance(to_unit, str) else to_unit
        return value_m2 / _AREA_TO_M2[unit]

    @staticmethod
    def convert_length(value_m: float, to_unit: LengthUnit | str) -> float:
        unit = LengthUnit(to_unit) if isinstance(to_unit, str) else to_unit
        return value_m / _LENGTH_TO_M[unit]

    @staticmethod
    def area_unit_label(unit: AreaUnit | str) -> str:
        labels = {AreaUnit.M2: 'm²', AreaUnit.KM2: 'km²', AreaUnit.HA: 'ha', AreaUnit.ACRE: 'acre'}
        return labels[AreaUnit(unit) if isinstance(unit, str) else unit]

    @staticmethod
    def length_unit_label(unit: LengthUnit | str) -> str:
        labels = {LengthUnit.M: 'm', LengthUnit.KM: 'km', LengthUnit.MI: 'mi', LengthUnit.FT: 'ft'}
        return labels[LengthUnit(unit) if isinstance(unit, str) else unit]

    @staticmethod
    def supported_area_units() -> list[str]:
        return [u.value for u in AreaUnit]

    @staticmethod
    def supported_length_units() -> list[str]:
        return [u.value for u in LengthUnit]
