from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable

from bleak import BleakClient

from .constants import OTA_CHARACTERISTIC_UUID, OTA_SERVICE_UUID, START_COMMANDS
from .firmware import FirmwareImage
from .protocol import build_data_packet, build_finish_packet

ProgressCallback = Callable[[int, int, float], None]


@dataclass(frozen=True)
class FlashOptions:
    delay_ms: float = 10.0
    ack_every: int = 8
    timeout: float = 30.0
    start_delay: float = 0.5
    data_start_delay: float = 0.3
    finish_wait: float = 5.0


class OtaError(RuntimeError):
    pass


def _service_dump(client: BleakClient) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for service in client.services:
        chars: list[dict[str, object]] = []
        for char in service.characteristics:
            chars.append(
                {
                    "uuid": char.uuid,
                    "handle": char.handle,
                    "properties": list(char.properties),
                    "max_write_without_response_size": char.max_write_without_response_size,
                }
            )
        result.append({"uuid": service.uuid, "handle": service.handle, "characteristics": chars})
    return result


async def _acquire_mtu_best_effort(client: BleakClient, logger: logging.Logger | None = None) -> tuple[int, str | None]:
    logger = logger or logging.getLogger(__name__)
    note: str | None = None
    backend = getattr(client, "_backend", None)
    acquire = getattr(backend, "_acquire_mtu", None)
    if callable(acquire):
        try:
            await acquire()
        except Exception as exc:
            note = f"MTU-Ermittlung nicht möglich: {exc}"
            logger.debug(note, exc_info=True)
    else:
        note = "Backend bietet keine explizite MTU-Ermittlung an."
    return client.mtu_size, note


def _require_ota_characteristic(client: BleakClient):
    characteristic = client.services.get_characteristic(OTA_CHARACTERISTIC_UUID)
    if characteristic is None:
        raise OtaError("Telink-OTA-Characteristic wurde nicht gefunden.")
    if "write-without-response" not in characteristic.properties and "write" not in characteristic.properties:
        raise OtaError(f"OTA-Characteristic ist nicht beschreibbar: {characteristic.properties}")
    if "read" not in characteristic.properties:
        raise OtaError(f"OTA-Characteristic ist nicht lesbar: {characteristic.properties}")
    if characteristic.max_write_without_response_size < 20:
        raise OtaError(
            "Die OTA-Characteristic erlaubt weniger als 20 Byte pro Write; "
            "das klassische Telink-OTA-Paket passt nicht."
        )
    return characteristic


async def _read_status(client: BleakClient, *, context: str) -> bytes:
    try:
        status = bytes(await client.read_gatt_char(OTA_CHARACTERISTIC_UUID))
    except Exception as exc:
        raise OtaError(f"Statusabfrage {context} fehlgeschlagen: {exc}") from exc
    if status != b"\x00":
        raise OtaError(f"Gerät meldet OTA-Fehler {status.hex() or '<leer>'} ({context}).")
    return status


async def inspect_device(address: str, timeout: float = 20.0) -> dict[str, object]:
    async with BleakClient(address, timeout=timeout) as client:
        service = client.services.get_service(OTA_SERVICE_UUID)
        characteristic = client.services.get_characteristic(OTA_CHARACTERISTIC_UUID)
        mtu, mtu_note = await _acquire_mtu_best_effort(client)
        return {
            "connected": client.is_connected,
            "mtu": mtu,
            "mtu_note": mtu_note,
            "ota_service": service is not None,
            "ota_characteristic": characteristic is not None,
            "properties": list(characteristic.properties) if characteristic else [],
            "max_write_without_response_size": characteristic.max_write_without_response_size if characteristic else None,
            "services": _service_dump(client),
        }


async def ota_dry_run(
    address: str,
    timeout: float = 20.0,
    settle_delay: float = 0.5,
    logger: logging.Logger | None = None,
) -> dict[str, object]:
    logger = logger or logging.getLogger(__name__)
    expected_shutdown = False

    def on_disconnect(_: BleakClient) -> None:
        if not expected_shutdown:
            logger.warning("BLE-Verbindung wurde während des Dry-Runs getrennt.")

    async with BleakClient(address, timeout=timeout, disconnected_callback=on_disconnect) as client:
        if not client.is_connected:
            raise OtaError("Verbindung konnte nicht aufgebaut werden.")
        characteristic = _require_ota_characteristic(client)
        mtu, mtu_note = await _acquire_mtu_best_effort(client, logger)
        max_write = characteristic.max_write_without_response_size
        logger.info("Verbunden; MTU=%s; max_write_without_response=%s", mtu, max_write)
        await asyncio.sleep(settle_delay)

        for index, command in enumerate(START_COMMANDS, start=1):
            logger.info("OTA-Startkommando %d/%d: %s", index, len(START_COMMANDS), command.hex())
            await client.write_gatt_char(characteristic, command, response=False)
            await asyncio.sleep(0.1)

        status = await _read_status(client, context="nach Handshake")
        logger.info("OTA-Status nach Handshake: %s", status.hex())
        expected_shutdown = True
        return {
            "connected": client.is_connected,
            "mtu": mtu,
            "mtu_note": mtu_note,
            "max_write_without_response_size": max_write,
            "status": status,
            "commands": [command.hex() for command in START_COMMANDS],
            "firmware_blocks_written": 0,
        }


async def _write_packet(client: BleakClient, packet: bytes, *, context: str) -> None:
    """Einmalig schreiben. Keine automatische Wiederholung bei Write Command.

    Bei write-without-response kann der Host nicht sicher unterscheiden, ob ein Paket
    bereits beim Gerät angekommen ist. Eine Wiederholung könnte denselben Adr_Index
    doppelt senden und das Telink-Sequenzprüfverfahren absichtlich zum Abbruch bringen.
    """
    try:
        await client.write_gatt_char(OTA_CHARACTERISTIC_UUID, packet, response=False)
    except Exception as exc:
        raise OtaError(f"Schreiben {context} fehlgeschlagen: {exc}") from exc


async def flash_firmware(
    address: str,
    firmware: FirmwareImage,
    options: FlashOptions,
    progress: ProgressCallback | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, object]:
    logger = logger or logging.getLogger(__name__)
    if options.ack_every < 1:
        raise ValueError("ack_every muss mindestens 1 sein")
    if options.delay_ms < 0:
        raise ValueError("delay_ms darf nicht negativ sein")

    started = time.monotonic()
    disconnected = asyncio.Event()
    finish_sent = False

    def on_disconnect(_: BleakClient) -> None:
        disconnected.set()
        if finish_sent:
            logger.info("Gerät hat nach OTA-Ende getrennt bzw. neu gestartet.")
        else:
            logger.error("BLE-Verbindung vor dem OTA-Ende getrennt.")

    async with BleakClient(address, timeout=options.timeout, disconnected_callback=on_disconnect) as client:
        if not client.is_connected:
            raise OtaError("Verbindung konnte nicht aufgebaut werden.")
        characteristic = _require_ota_characteristic(client)
        mtu, mtu_note = await _acquire_mtu_best_effort(client, logger)
        logger.info(
            "Verbunden; MTU=%s; max_write_without_response=%s%s",
            mtu,
            characteristic.max_write_without_response_size,
            f"; {mtu_note}" if mtu_note else "",
        )
        await asyncio.sleep(options.start_delay)

        for index, command in enumerate(START_COMMANDS, start=1):
            await _write_packet(client, command, context=f"Startkommando {index}/{len(START_COMMANDS)}")
            await asyncio.sleep(0.1)
        await _read_status(client, context="nach Handshake")
        await asyncio.sleep(options.data_start_delay)

        last_status_block = -1
        for block_number in range(firmware.block_count):
            if disconnected.is_set() or not client.is_connected:
                raise OtaError(f"Verbindung vor Block {block_number} verloren.")

            packet = build_data_packet(block_number, firmware.block(block_number))
            await _write_packet(client, packet, context=f"bei Block {block_number}")

            if options.delay_ms:
                await asyncio.sleep(options.delay_ms / 1000.0)

            if (block_number + 1) % options.ack_every == 0:
                status = await _read_status(client, context=f"nach Block {block_number}")
                last_status_block = block_number
                logger.debug("Status nach Block %d: %s", block_number, status.hex())

            if progress:
                progress(block_number + 1, firmware.block_count, time.monotonic() - started)

        # Den letzten, nicht durch das Intervall abgedeckten Paketbereich ebenfalls bestätigen.
        if last_status_block != firmware.block_count - 1:
            status = await _read_status(client, context=f"nach letztem Block {firmware.block_count - 1}")
            logger.debug("Abschließender Datenstatus: %s", status.hex())

        finish = build_finish_packet(firmware.block_count - 1)
        logger.info("Sende OTA-Ende: %s", finish.hex())
        await _write_packet(client, finish, context="beim OTA-Ende")
        finish_sent = True

        # Erfolgreiches OTA führt üblicherweise zu einem Neustart/Disconnect. Ein noch
        # bestehender Link ist ebenfalls kein Fehler; BlueZ kann die Trennung verzögert melden.
        try:
            await asyncio.wait_for(disconnected.wait(), timeout=options.finish_wait)
        except TimeoutError:
            logger.info("Innerhalb von %.1f s kein Disconnect beobachtet.", options.finish_wait)

        return {
            "blocks_written": firmware.block_count,
            "last_block": firmware.block_count - 1,
            "finish_packet": finish,
            "disconnected_after_finish": disconnected.is_set(),
            "elapsed": time.monotonic() - started,
        }
