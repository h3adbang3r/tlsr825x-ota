from __future__ import annotations

import asyncio
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import bleak
from bleak import BleakClient

from .constants import OTA_CHARACTERISTIC_UUID

DEVICE_INFO_UUIDS = {
    "manufacturer": "00002a29-0000-1000-8000-00805f9b34fb",
    "model": "00002a24-0000-1000-8000-00805f9b34fb",
    "serial": "00002a25-0000-1000-8000-00805f9b34fb",
    "firmware": "00002a26-0000-1000-8000-00805f9b34fb",
    "hardware": "00002a27-0000-1000-8000-00805f9b34fb",
    "software": "00002a28-0000-1000-8000-00805f9b34fb",
}


@dataclass(frozen=True)
class MtuSample:
    elapsed_s: float
    mtu_reported: int
    max_write_without_response: int


async def _read_utf8(client: BleakClient, uuid: str) -> str | None:
    char = client.services.get_characteristic(uuid)
    if char is None or "read" not in char.properties:
        return None
    try:
        raw = bytes(await client.read_gatt_char(char))
    except Exception:
        return None
    return raw.rstrip(b"\x00").decode("utf-8", errors="replace") or None


async def collect_device_information(client: BleakClient) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name, uuid in DEVICE_INFO_UUIDS.items():
        result[name] = await _read_utf8(client, uuid)
    return result


async def mtu_diagnostics(
    address: str,
    *,
    timeout: float = 20.0,
    observe_seconds: float = 5.0,
    sample_interval: float = 0.5,
) -> dict[str, Any]:
    """Read-only MTU/link diagnostics.

    No GATT write and no OTA handshake is performed. On BlueZ, Bleak's private
    ``_acquire_mtu`` hook is used only to ask BlueZ for the already negotiated
    ATT channel/MTU metadata. It does not write to a device characteristic.
    """
    disconnected = asyncio.Event()

    def on_disconnect(_: BleakClient) -> None:
        disconnected.set()

    async with BleakClient(address, timeout=timeout, disconnected_callback=on_disconnect) as client:
        if not client.is_connected:
            raise RuntimeError("Verbindung konnte nicht aufgebaut werden.")

        ota_char = client.services.get_characteristic(OTA_CHARACTERISTIC_UUID)
        if ota_char is None:
            raise RuntimeError("Telink-OTA-Characteristic wurde nicht gefunden.")

        mtu_before = client.mtu_size
        max_before = ota_char.max_write_without_response_size
        backend_name = type(getattr(client, "_backend", None)).__name__
        acquire_supported = False
        acquire_error: str | None = None

        backend = getattr(client, "_backend", None)
        acquire = getattr(backend, "_acquire_mtu", None)
        if callable(acquire):
            acquire_supported = True
            try:
                await acquire()
            except Exception as exc:  # backend-/BlueZ-spezifische Diagnose
                acquire_error = f"{type(exc).__name__}: {exc}"

        mtu_after = client.mtu_size
        samples: list[MtuSample] = []
        loop = asyncio.get_running_loop()
        started = loop.time()
        deadline = started + max(0.0, observe_seconds)
        while True:
            now = loop.time()
            samples.append(
                MtuSample(
                    elapsed_s=round(now - started, 3),
                    mtu_reported=client.mtu_size,
                    max_write_without_response=ota_char.max_write_without_response_size,
                )
            )
            if now >= deadline or disconnected.is_set():
                break
            await asyncio.sleep(max(0.1, sample_interval))

        info = await collect_device_information(client)
        return {
            "address": address,
            "connected": client.is_connected,
            "backend": backend_name,
            "bleak_version": getattr(bleak, "__version__", None),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "mtu_before_acquire": mtu_before,
            "mtu_after_acquire": mtu_after,
            "max_write_before_acquire": max_before,
            "max_write_after_acquire": ota_char.max_write_without_response_size,
            "acquire_supported": acquire_supported,
            "acquire_error": acquire_error,
            "samples": [asdict(sample) for sample in samples],
            "device_information": info,
            "disconnected": disconnected.is_set(),
            "writes_performed": 0,
        }


def firmware_metadata(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "telink_signature_offset_8": data[8:12] == b"KNLT" if len(data) >= 12 else False,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def command_version(command: list[str]) -> str | None:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (proc.stdout or proc.stderr).strip()
    return text.splitlines()[0] if text else None


def host_diagnostics() -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "kernel": platform.release(),
        "bluez": command_version(["bluetoothctl", "--version"]),
        "btmon_available": shutil.which("btmon") is not None,
    }
