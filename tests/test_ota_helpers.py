import pytest

from tlsr825x_ota.ota import OtaError, _read_status


class FakeClient:
    def __init__(self, value: bytes):
        self.value = value

    async def read_gatt_char(self, uuid):
        return self.value


@pytest.mark.asyncio
async def test_status_ok():
    assert await _read_status(FakeClient(b"\x00"), context="Test") == b"\x00"


@pytest.mark.asyncio
async def test_status_error():
    with pytest.raises(OtaError, match="OTA-Fehler"):
        await _read_status(FakeClient(b"\x01"), context="Test")
