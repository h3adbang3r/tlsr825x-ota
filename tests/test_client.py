from pathlib import Path

import pytest

from tlsr825x_ota.client import OTAClient
from tlsr825x_ota.firmware import FirmwareImage
from tlsr825x_ota.ota import FlashOptions


@pytest.mark.asyncio
async def test_info_delegates_to_existing_implementation(monkeypatch):
    expected = {"connected": True, "mtu": 23}
    calls = []

    async def fake_inspect(address: str, timeout: float):
        calls.append((address, timeout))
        return expected

    monkeypatch.setattr("tlsr825x_ota.client.inspect_device", fake_inspect)

    result = await OTAClient("AA:BB:CC:DD:EE:FF", timeout=12.5).info()

    assert result is expected
    assert calls == [("AA:BB:CC:DD:EE:FF", 12.5)]


@pytest.mark.asyncio
async def test_dry_run_delegates_with_logger(monkeypatch):
    expected = {"firmware_blocks_written": 0}
    calls = []
    logger = object()

    async def fake_dry_run(address: str, timeout: float, settle_delay: float, logger):
        calls.append((address, timeout, settle_delay, logger))
        return expected

    monkeypatch.setattr("tlsr825x_ota.client.ota_dry_run", fake_dry_run)

    result = await OTAClient("device", timeout=9.0, logger=logger).dry_run(settle_delay=0.75)

    assert result is expected
    assert calls == [("device", 9.0, 0.75, logger)]


@pytest.mark.asyncio
async def test_flash_delegates_without_changing_options(monkeypatch, tmp_path: Path):
    path = tmp_path / "fw.bin"
    data = bytearray(16)
    data[8:12] = b"KNLT"
    path.write_bytes(data)
    image = FirmwareImage.load(path)
    options = FlashOptions(timeout=17.0, delay_ms=5.0)
    progress = object()
    logger = object()
    expected = {"blocks_written": 1}
    calls = []

    async def fake_flash(address, firmware, received_options, progress=None, logger=None):
        calls.append((address, firmware, received_options, progress, logger))
        return expected

    monkeypatch.setattr("tlsr825x_ota.client.flash_firmware", fake_flash)

    result = await OTAClient("device", timeout=99.0, logger=logger).flash(
        image,
        options=options,
        progress=progress,
    )

    assert result is expected
    assert calls == [("device", image, options, progress, logger)]


@pytest.mark.asyncio
async def test_flash_builds_default_options_from_client_timeout(monkeypatch, tmp_path: Path):
    path = tmp_path / "fw.bin"
    data = bytearray(16)
    data[8:12] = b"KNLT"
    path.write_bytes(data)
    image = FirmwareImage.load(path)
    captured = {}

    async def fake_flash(address, firmware, options, progress=None, logger=None):
        captured["options"] = options
        return {}

    monkeypatch.setattr("tlsr825x_ota.client.flash_firmware", fake_flash)

    await OTAClient("device", timeout=44.0).flash(image)

    assert captured["options"].timeout == 44.0
