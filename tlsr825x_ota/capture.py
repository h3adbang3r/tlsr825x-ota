from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path

from .diagnostics import host_diagnostics, mtu_diagnostics, write_json


async def capture_mtu_session(
    address: str,
    *,
    output_root: Path,
    timeout: float,
    observe_seconds: float,
    adapter_index: int | None = None,
) -> dict[str, object]:
    """Start btmon and run a read-only MTU diagnostic session."""
    btmon = shutil.which("btmon")
    if btmon is None:
        raise RuntimeError("btmon wurde nicht gefunden. Unter Arch/CachyOS: Paket 'bluez-utils' installieren.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = output_root / f"mtu_{stamp}"
    session_dir.mkdir(parents=True, exist_ok=False)
    btsnoop_path = session_dir / "btmon.btsnoop"
    stderr_path = session_dir / "btmon.stderr.log"

    command = [btmon]
    if adapter_index is not None:
        command += ["--index", str(adapter_index)]
    command += ["--write", str(btsnoop_path)]

    with stderr_path.open("wb") as stderr_file:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=stderr_file,
        )
        try:
            await asyncio.sleep(0.75)
            if process.returncode is not None:
                raise RuntimeError(
                    "btmon wurde sofort beendet. Prüfe die Berechtigungen; gegebenenfalls "
                    "das Tool einmal mit sudo ausführen."
                )
            result = await mtu_diagnostics(
                address,
                timeout=timeout,
                observe_seconds=observe_seconds,
            )
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=3)
                except TimeoutError:
                    process.kill()
                    await process.wait()

    payload: dict[str, object] = {
        "mode": "read-only-mtu-capture",
        "session_dir": str(session_dir.resolve()),
        "btmon_file": str(btsnoop_path.resolve()),
        "host": host_diagnostics(),
        "device": result,
    }
    write_json(session_dir / "summary.json", payload)
    (session_dir / "README.txt").write_text(
        "Read-only MTU capture. No OTA handshake and no GATT writes were performed.\n"
        "Open btmon.btsnoop with: btmon --read btmon.btsnoop\n",
        encoding="utf-8",
    )
    return payload
