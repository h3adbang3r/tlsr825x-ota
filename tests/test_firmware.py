from pathlib import Path

import pytest

from tlsr825x_ota.firmware import FirmwareError, FirmwareImage


def test_load_and_padding(tmp_path: Path):
    data = bytearray(17)
    data[8:12] = b"KNLT"
    path = tmp_path / "ATC_test.bin"
    path.write_bytes(data)
    image = FirmwareImage.load(path)
    assert image.original_size == 17
    assert len(image.padded) == 32
    assert image.block_count == 2


def test_reject_bad_magic(tmp_path: Path):
    path = tmp_path / "bad.bin"
    path.write_bytes(b"x" * 32)
    with pytest.raises(FirmwareError):
        FirmwareImage.load(path)
