from __future__ import annotations

from dataclasses import dataclass

from bleak import BleakScanner


@dataclass(frozen=True)
class ScanResult:
    address: str
    name: str
    rssi: int | None


async def scan_devices(timeout: float = 8.0, prefix: str | None = None) -> list[ScanResult]:
    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    results: list[ScanResult] = []
    for _key, (device, advertisement) in found.items():
        name = device.name or advertisement.local_name or "(ohne Namen)"
        if prefix and not name.lower().startswith(prefix.lower()):
            continue
        results.append(
            ScanResult(
                address=device.address,
                name=name,
                rssi=getattr(advertisement, "rssi", None),
            )
        )
    return sorted(results, key=lambda item: item.rssi if item.rssi is not None else -999, reverse=True)


async def resolve_address(target: str, timeout: float = 10.0) -> str:
    direct = await BleakScanner.find_device_by_address(target, timeout=timeout)
    if direct is not None:
        return direct.address

    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    target_lower = target.lower()
    matches = []
    for _key, (device, advertisement) in found.items():
        name = device.name or advertisement.local_name or ""
        if name.lower() == target_lower or name.lower().startswith(target_lower):
            matches.append(device)
    if not matches:
        raise RuntimeError(f"BLE-Gerät nicht gefunden: {target}")
    if len(matches) > 1:
        addresses = ", ".join(device.address for device in matches)
        raise RuntimeError(f"Mehrere passende Geräte gefunden ({addresses}); bitte MAC-Adresse verwenden.")
    return matches[0].address
