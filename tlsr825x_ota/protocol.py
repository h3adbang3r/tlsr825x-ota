from __future__ import annotations

from .constants import PAYLOAD_SIZE


def crc16_modbus(data: bytes) -> int:
    """CRC-16/MODBUS as used by the PVVX TelinkOTA reference implementation."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            odd = crc & 1
            crc >>= 1
            if odd:
                crc ^= 0xA001
    return crc & 0xFFFF


def build_data_packet(block_number: int, payload: bytes) -> bytes:
    if not 0 <= block_number <= 0xFFFF:
        raise ValueError("block_number must be between 0 and 65535")
    if len(payload) != PAYLOAD_SIZE:
        raise ValueError(f"payload must contain exactly {PAYLOAD_SIZE} bytes")

    body = block_number.to_bytes(2, "little") + payload
    return body + crc16_modbus(body).to_bytes(2, "little")


def build_finish_packet(last_block_number: int) -> bytes:
    if not 0 <= last_block_number <= 0xFFFF:
        raise ValueError("last_block_number must be between 0 and 65535")
    inverse = (~last_block_number) & 0xFFFF
    return b"\x02\xff" + last_block_number.to_bytes(2, "little") + inverse.to_bytes(2, "little")
