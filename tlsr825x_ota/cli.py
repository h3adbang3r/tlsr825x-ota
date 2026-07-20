from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from . import __version__
from .firmware import FirmwareError, FirmwareImage
from .capture import capture_mtu_session
from .diagnostics import firmware_metadata, host_diagnostics, mtu_diagnostics, write_json
from .logging_setup import configure_logging
from .client import OTAClient
from .ota import FlashOptions, OtaError
from .scanner import resolve_address, scan_devices

app = typer.Typer(no_args_is_help=True, help="Nativer Telink TLSR825x BLE-OTA-Flasher.")
console = Console()


def _run(coro):
    return asyncio.run(coro)


@app.command()
def version() -> None:
    """Programmversion anzeigen."""
    console.print(f"tlsr825x-ota {__version__}")


@app.command()
def scan(
    timeout: float = typer.Option(8.0, min=1.0, help="Scandauer in Sekunden."),
    prefix: str | None = typer.Option(None, help="Optionaler Gerätenamens-Präfix, z. B. ATC_."),
) -> None:
    """Bluetooth-LE-Geräte suchen."""
    try:
        devices = _run(scan_devices(timeout, prefix))
    except Exception as exc:
        console.print(f"[red]Scan fehlgeschlagen:[/red] {exc}")
        raise typer.Exit(1)
    table = Table("Name", "Adresse", "RSSI")
    for device in devices:
        table.add_row(device.name, device.address, "?" if device.rssi is None else f"{device.rssi} dBm")
    console.print(table if devices else "Keine passenden Geräte gefunden.")


@app.command()
def validate(
    firmware: Path = typer.Argument(..., exists=True, dir_okay=False),
    json_file: Path | None = typer.Option(None, "--json", help="Prüfergebnis als JSON speichern."),
) -> None:
    """Firmwaredatei prüfen, ohne Bluetooth zu verwenden."""
    try:
        image = FirmwareImage.load(firmware)
    except FirmwareError as exc:
        console.print(f"[red]Ungültig:[/red] {exc}")
        raise typer.Exit(1)
    console.print("[green]Telink-Signatur gültig.[/green]")
    console.print(f"Datei: {image.path}")
    console.print(f"Größe: {image.original_size} Byte")
    console.print(f"OTA-Blöcke: {image.block_count} × 16 Byte")
    console.print(f"Padding: {len(image.padded) - image.original_size} Byte")
    metadata = firmware_metadata(firmware)
    console.print(f"SHA-256: {metadata['sha256']}")
    if json_file is not None:
        payload = {**metadata, "block_count": image.block_count, "padding": len(image.padded) - image.original_size}
        write_json(json_file, payload)
        console.print(f"JSON: {json_file}")


@app.command()
def info(
    device: str = typer.Argument(..., help="MAC-Adresse oder Gerätename, z. B. ATC_A1D036."),
    scan_timeout: float = typer.Option(10.0, min=1.0),
    timeout: float = typer.Option(20.0, min=1.0),
    json_file: Path | None = typer.Option(None, "--json", help="Diagnose als JSON speichern."),
) -> None:
    """OTA-Service und Characteristic eines Geräts prüfen; schreibt keine Daten."""
    try:
        address = _run(resolve_address(device, scan_timeout))
        result = _run(OTAClient(address, timeout=timeout).info())
    except Exception as exc:
        console.print(f"[red]Diagnose fehlgeschlagen:[/red] {exc}")
        raise typer.Exit(1)
    console.print(f"Adresse: {address}")
    console.print(f"Verbunden: {result['connected']}")
    console.print(f"MTU: {result['mtu']}")
    console.print(f"OTA-Service: {result['ota_service']}")
    console.print(f"OTA-Characteristic: {result['ota_characteristic']}")
    console.print(f"Eigenschaften: {', '.join(result['properties']) or '-'}")
    console.print(f"Max. Write ohne Antwort: {result['max_write_without_response_size']} Byte")
    info_values = result.get("device_information", {})
    if any(info_values.values()):
        console.print("[bold]Geräteinformationen:[/bold]")
        for key, value in info_values.items():
            if value:
                console.print(f"  {key}: {value}")
    if result.get("mtu_note"):
        console.print(f"[yellow]Hinweis:[/yellow] {result['mtu_note']}")

    table = Table("Service / Characteristic", "Handle", "Eigenschaften", "Max. Write")
    for service in result["services"]:
        table.add_row(f"[bold]{service['uuid']}[/bold]", str(service["handle"]), "Service", "-")
        for char in service["characteristics"]:
            table.add_row(
                f"  {char['uuid']}",
                str(char["handle"]),
                ", ".join(char["properties"]) or "-",
                str(char["max_write_without_response_size"]),
            )
    console.print(table)
    if json_file is not None:
        write_json(json_file, {"address": address, **result})
        console.print(f"JSON: {json_file}")


@app.command("mtu-test")
def mtu_test(
    device: str = typer.Argument(..., help="MAC-Adresse oder Gerätename."),
    scan_timeout: float = typer.Option(20.0, min=1.0),
    timeout: float = typer.Option(30.0, min=1.0),
    observe: float = typer.Option(5.0, min=0.0, help="Beobachtungszeit in Sekunden."),
    json_file: Path | None = typer.Option(None, "--json", help="Diagnose als JSON speichern."),
) -> None:
    """Reiner Lese-/Linktest: kein OTA-Handshake und keine GATT-Schreibzugriffe."""
    try:
        address = _run(resolve_address(device, scan_timeout))
        result = _run(mtu_diagnostics(address, timeout=timeout, observe_seconds=observe))
    except Exception as exc:
        console.print(f"[red]MTU-Test fehlgeschlagen:[/red] {exc}")
        raise typer.Exit(1)

    console.print("[green]Read-only MTU-Test abgeschlossen.[/green]")
    console.print(f"Adresse: {address}")
    console.print(f"Backend: {result['backend']}")
    console.print(f"MTU vor Acquire: {result['mtu_before_acquire']}")
    console.print(f"MTU nach Acquire: {result['mtu_after_acquire']}")
    console.print(f"Max. Write vorher: {result['max_write_before_acquire']} Byte")
    console.print(f"Max. Write nachher: {result['max_write_after_acquire']} Byte")
    console.print(f"Acquire unterstützt: {result['acquire_supported']}")
    if result.get("acquire_error"):
        console.print(f"[yellow]Acquire-Fehler:[/yellow] {result['acquire_error']}")
    console.print(f"GATT-Schreibzugriffe: {result['writes_performed']}")

    samples = Table("Zeit", "MTU", "Max. Write ohne Antwort")
    for sample in result["samples"]:
        samples.add_row(f"{sample['elapsed_s']:.1f} s", str(sample["mtu_reported"]), f"{sample['max_write_without_response']} Byte")
    console.print(samples)
    if json_file is not None:
        write_json(json_file, {"host": host_diagnostics(), "device": result})
        console.print(f"JSON: {json_file}")


@app.command("capture-mtu")
def capture_mtu(
    device: str = typer.Argument(..., help="MAC-Adresse oder Gerätename."),
    output: Path = typer.Option(Path("captures"), "--output", help="Zielordner für den Mitschnitt."),
    scan_timeout: float = typer.Option(20.0, min=1.0),
    timeout: float = typer.Option(30.0, min=1.0),
    observe: float = typer.Option(5.0, min=0.0),
    adapter: int | None = typer.Option(None, "--adapter", help="Optionaler btmon-Controllerindex, z. B. 1."),
) -> None:
    """Read-only MTU-Test parallel als btmon-BTSnoop aufzeichnen."""
    try:
        address = _run(resolve_address(device, scan_timeout))
        result = _run(capture_mtu_session(address, output_root=output, timeout=timeout, observe_seconds=observe, adapter_index=adapter))
    except Exception as exc:
        console.print(f"[red]Capture fehlgeschlagen:[/red] {exc}")
        raise typer.Exit(1)
    console.print("[green]Read-only Capture abgeschlossen.[/green]")
    console.print(f"Ordner: {result['session_dir']}")
    console.print(f"BTSnoop: {result['btmon_file']}")
    console.print("GATT-Schreibzugriffe: 0")


@app.command("dry-run")
def dry_run(
    device: str = typer.Argument(..., help="MAC-Adresse oder Gerätename, z. B. ATC_A1D036."),
    scan_timeout: float = typer.Option(20.0, min=1.0),
    timeout: float = typer.Option(30.0, min=1.0),
    settle_delay: float = typer.Option(0.5, min=0.0, help="Pause vor dem Handshake in Sekunden."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """OTA-Handshake und Statusabfrage; überträgt keine Firmwareblöcke."""
    logger, log_path = configure_logging(verbose)
    try:
        address = _run(resolve_address(device, scan_timeout))
        logger.info("Dry-Run-Ziel=%s (%s)", device, address)
        result = _run(OTAClient(address, timeout=timeout, logger=logger).dry_run(settle_delay=settle_delay))
    except Exception as exc:
        logger.exception("OTA-Dry-Run fehlgeschlagen")
        console.print(f"[red]OTA-Dry-Run fehlgeschlagen:[/red] {exc}")
        console.print(f"Logdatei: {log_path}")
        raise typer.Exit(1)

    console.print("[green]OTA-Handshake erfolgreich.[/green]")
    console.print(f"Adresse: {address}")
    console.print(f"MTU: {result['mtu']}")
    console.print(f"Max. Write ohne Antwort: {result['max_write_without_response_size']} Byte")
    info_values = result.get("device_information", {})
    if any(info_values.values()):
        console.print("[bold]Geräteinformationen:[/bold]")
        for key, value in info_values.items():
            if value:
                console.print(f"  {key}: {value}")
    console.print(f"Startkommandos: {', '.join(result['commands'])}")
    console.print(f"Status: {result['status'].hex() or '<leer>'}")
    console.print(f"Firmwareblöcke übertragen: {result['firmware_blocks_written']}")
    if result.get("mtu_note"):
        console.print(f"[yellow]Hinweis:[/yellow] {result['mtu_note']}")
    console.print(f"Logdatei: {log_path}")


@app.command()
def flash(
    firmware: Path = typer.Argument(..., exists=True, dir_okay=False),
    device: str = typer.Option(..., "--device", "-d", help="MAC-Adresse oder eindeutiger Gerätename."),
    delay_ms: float = typer.Option(10.0, "--delay", min=0.0, help="Pause nach jedem Block in ms."),
    ack_every: int = typer.Option(8, min=1, max=256, help="Status-Read nach dieser Anzahl Blöcke."),
    timeout: float = typer.Option(20.0, min=1.0, help="BLE-Verbindungs-Timeout in Sekunden."),
    scan_timeout: float = typer.Option(10.0, min=1.0),
    yes: bool = typer.Option(False, "--yes", "-y", help="Sicherheitsabfrage überspringen."),
    finish_wait: float = typer.Option(5.0, min=0.0, help="Wartezeit auf Neustart/Disconnect nach OTA-Ende."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Firmware über das klassische Telink-SDK-OTA-Protokoll übertragen."""
    try:
        image = FirmwareImage.load(firmware)
    except FirmwareError as exc:
        console.print(f"[red]Firmware abgelehnt:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"Firmware: [bold]{image.path.name}[/bold], {image.original_size} Byte, {image.block_count} Blöcke")
    console.print("[yellow]Warnung:[/yellow] Das Tool prüft nur die Telink-Signatur, nicht das konkrete Gerätemodell.")
    console.print("Für LYWSD03MMC muss die passende ATC-Firmware verwendet werden; BTH gehört zum MJWSD05MMC.")
    if not yes and not typer.confirm("Firmware wirklich übertragen?"):
        raise typer.Abort()

    logger, log_path = configure_logging(verbose)
    logger.info("Firmware=%s Größe=%d Blöcke=%d", image.path, image.original_size, image.block_count)
    try:
        address = _run(resolve_address(device, scan_timeout))
        logger.info("Ziel=%s (%s)", device, address)
        options = FlashOptions(delay_ms=delay_ms, ack_every=ack_every, timeout=timeout, finish_wait=finish_wait)
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("OTA", total=image.block_count)

            def update(done: int, total: int, elapsed: float) -> None:
                progress.update(task, completed=done)

            result = _run(OTAClient(address, timeout=timeout, logger=logger).flash(image, options=options, progress=update))
    except (OtaError, RuntimeError, Exception) as exc:
        logger.exception("OTA fehlgeschlagen")
        console.print(f"[red]OTA fehlgeschlagen:[/red] {exc}")
        console.print(f"Logdatei: {log_path}")
        raise typer.Exit(1)

    console.print("[green]OTA-Daten und Abschlusskommando wurden gesendet.[/green]")
    console.print(f"Blöcke: {result['blocks_written']}")
    console.print(f"OTA-Ende: {result['finish_packet'].hex()}")
    console.print(f"Disconnect/Neustart beobachtet: {result['disconnected_after_finish']}")
    console.print(f"Dauer: {result['elapsed']:.1f} s")
    console.print(f"Logdatei: {log_path}")
