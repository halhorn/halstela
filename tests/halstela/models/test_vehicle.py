"""halstela.models.vehicle のテスト"""

from halstela.models.vehicle import Vehicle


class TestVehicle:
    def test_create(self) -> None:
        v = Vehicle(id="123", vin="5YJ3E1EA1NF", display_name="My Tesla", state="online")
        assert v.id == "123"
        assert v.vin == "5YJ3E1EA1NF"
        assert v.display_name == "My Tesla"
        assert v.state == "online"

    def test_frozen(self) -> None:
        v = Vehicle(id="1", vin="VIN", display_name="T", state="online")
        try:
            v.state = "asleep"  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass
