from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .constants import PAYLOAD_SIZE, TELINK_MAGIC, TELINK_MAGIC_OFFSET


class FirmwareError(ValueError):
    pass


@dataclass(frozen=True)
class FirmwareImage:
    path: Path
    original: bytes
    padded: bytes

    @property
    def block_count(self) -> int:
        return len(self.padded) // PAYLOAD_SIZE

    @property
    def original_size(self) -> int:
        return len(self.original)

    @classmethod
    def load(cls, path: Path) -> "FirmwareImage":
        path = path.expanduser().resolve()
        if not path.is_file():
            raise FirmwareError(f"Firmwaredatei nicht gefunden: {path}")

        raw = path.read_bytes()
        magic = raw[TELINK_MAGIC_OFFSET : TELINK_MAGIC_OFFSET + len(TELINK_MAGIC)]
        if magic != TELINK_MAGIC:
            raise FirmwareError(
                "Keine gültige Telink-Firmware: Signatur 'KNLT' an Offset 8 fehlt."
            )
        if not raw:
            raise FirmwareError("Firmwaredatei ist leer.")

        padding = (-len(raw)) % PAYLOAD_SIZE
        padded = raw + (b"\xff" * padding)
        if len(padded) // PAYLOAD_SIZE > 0x10000:
            raise FirmwareError("Firmware enthält mehr als 65536 OTA-Blöcke.")
        return cls(path=path, original=raw, padded=padded)

    def block(self, number: int) -> bytes:
        start = number * PAYLOAD_SIZE
        end = start + PAYLOAD_SIZE
        payload = self.padded[start:end]
        if len(payload) != PAYLOAD_SIZE:
            raise IndexError(number)
        return payload
