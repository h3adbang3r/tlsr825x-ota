from tlsr825x_ota.protocol import build_data_packet, build_finish_packet, crc16_modbus


def test_crc_known_modbus_vector():
    assert crc16_modbus(b"123456789") == 0x4B37


def test_data_packet_layout():
    packet = build_data_packet(0x1234, bytes(range(16)))
    assert len(packet) == 20
    assert packet[:2] == b"\x34\x12"
    assert packet[2:18] == bytes(range(16))
    assert int.from_bytes(packet[-2:], "little") == crc16_modbus(packet[:-2])


def test_finish_packet():
    assert build_finish_packet(7) == bytes.fromhex("02ff0700f8ff")
