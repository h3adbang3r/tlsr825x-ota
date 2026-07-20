from pathlib import Path

from tlsr825x_ota.diagnostics import firmware_metadata, write_json


def test_firmware_metadata(tmp_path: Path):
    path = tmp_path / "fw.bin"
    path.write_bytes(b"12345678KNLTpayload")
    result = firmware_metadata(path)
    assert result["size"] == 19
    assert result["telink_signature_offset_8"] is True
    assert len(result["sha256"]) == 64


def test_write_json(tmp_path: Path):
    path = tmp_path / "nested" / "result.json"
    write_json(path, {"ok": True})
    assert '"ok": true' in path.read_text(encoding="utf-8")
