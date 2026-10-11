from __future__ import annotations
import pytest
from app.services.unit_converter import AreaUnit, LengthUnit, UnitConverter

class TestAreaConversion:

    def test_m2_to_m2_identity(self) -> None:
        assert UnitConverter.convert_area(1.0, AreaUnit.M2) == pytest.approx(1.0)

    def test_m2_to_hectare(self) -> None:
        assert UnitConverter.convert_area(10000.0, AreaUnit.HA) == pytest.approx(1.0, rel=1e-10)

    def test_m2_to_km2(self) -> None:
        assert UnitConverter.convert_area(1000000.0, AreaUnit.KM2) == pytest.approx(1.0, rel=1e-10)

    def test_m2_to_acre_exact_constant(self) -> None:
        result = UnitConverter.convert_area(4046.8564224, AreaUnit.ACRE)
        assert result == pytest.approx(1.0, rel=1e-10)

    def test_100_ha_in_m2(self) -> None:
        area_m2 = 100 * 10000
        assert UnitConverter.convert_area(area_m2, AreaUnit.KM2) == pytest.approx(1.0, rel=1e-08)

    def test_string_unit_accepted(self) -> None:
        assert UnitConverter.convert_area(10000.0, 'ha') == pytest.approx(1.0, rel=1e-10)

    def test_invalid_unit_raises(self) -> None:
        with pytest.raises(ValueError):
            UnitConverter.convert_area(1.0, 'furlongs')

    def test_acre_known_value(self) -> None:
        result = UnitConverter.convert_area(40468.564224, AreaUnit.ACRE)
        assert result == pytest.approx(10.0, rel=1e-06)

class TestLengthConversion:

    def test_m_to_m_identity(self) -> None:
        assert UnitConverter.convert_length(1.0, LengthUnit.M) == pytest.approx(1.0)

    def test_m_to_km(self) -> None:
        assert UnitConverter.convert_length(1000.0, LengthUnit.KM) == pytest.approx(1.0)

    def test_m_to_mile_exact(self) -> None:
        assert UnitConverter.convert_length(1609.344, LengthUnit.MI) == pytest.approx(1.0, rel=1e-10)

    def test_m_to_feet_exact(self) -> None:
        assert UnitConverter.convert_length(0.3048, LengthUnit.FT) == pytest.approx(1.0, rel=1e-10)

class TestUnitLabels:

    def test_area_labels(self) -> None:
        assert UnitConverter.area_unit_label(AreaUnit.M2) == 'm²'
        assert UnitConverter.area_unit_label(AreaUnit.HA) == 'ha'
        assert UnitConverter.area_unit_label(AreaUnit.KM2) == 'km²'
        assert UnitConverter.area_unit_label(AreaUnit.ACRE) == 'acre'

    def test_length_labels(self) -> None:
        assert UnitConverter.length_unit_label(LengthUnit.M) == 'm'
        assert UnitConverter.length_unit_label(LengthUnit.KM) == 'km'
        assert UnitConverter.length_unit_label(LengthUnit.MI) == 'mi'

    def test_supported_area_units(self) -> None:
        units = UnitConverter.supported_area_units()
        assert 'm2' in units
        assert 'ha' in units
        assert 'km2' in units
        assert 'acre' in units
