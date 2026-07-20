# TLSR825x OTA CLI

Nativer Linux-CLI-Flasher und Diagnosewerkzeug für Telink-TLSR825x-BLE-Geräte.
Das Projekt wurde mit dem Xiaomi LYWSD03MMC und der ATC/PVVX-Firmware getestet.

> **Wichtig:** Eine gültige Telink-Signatur bestätigt nicht das konkrete Gerätemodell.
> Für das LYWSD03MMC die passende `ATC_*.bin` verwenden. `BTH_*.bin` gehört nicht
> zu diesem Modell.

## Installation unter CachyOS/fish

```fish
python -m venv .venv
source .venv/bin/activate.fish
python -m pip install -e .
```

Für `capture-mtu` wird `btmon` aus `bluez-utils` benötigt.

## Sichere Diagnose ohne Schreibzugriffe

```fish
tlsr825x-ota scan --prefix ATC_

tlsr825x-ota info A4:C1:38:A1:D0:36 \
  --scan-timeout 30 \
  --timeout 30

tlsr825x-ota mtu-test A4:C1:38:A1:D0:36 \
  --scan-timeout 30 \
  --timeout 30 \
  --observe 10 \
  --json mtu.json
```

`mtu-test` löst **keinen OTA-Handshake** aus und führt **keine GATT-Schreibzugriffe**
aus. Er zeigt den von Bleak gemeldeten MTU-Wert vor und nach der BlueZ-spezifischen
Best-Effort-Ermittlung sowie die maximale Größe für Write Without Response.

Unter BlueZ kann `BleakClient.mtu_size` weiterhin 23 melden. Für den OTA-Transfer
ist die entscheidende Größe `max_write_without_response_size`; das klassische
Telink-Paket benötigt exakt 20 Byte.

## Read-only-Mitschnitt mit btmon

```fish
tlsr825x-ota capture-mtu A4:C1:38:A1:D0:36 \
  --scan-timeout 30 \
  --timeout 30 \
  --observe 10
```

Erzeugt beispielsweise:

```text
captures/mtu_20260720_190000/
├── btmon.btsnoop
├── btmon.stderr.log
├── summary.json
└── README.txt
```

Auswertung:

```fish
btmon --read captures/mtu_*/btmon.btsnoop
```

Falls `btmon` sofort wegen fehlender Rechte endet, den Capture-Befehl mit den
passenden Systemberechtigungen ausführen. Der normale `mtu-test` benötigt keinen
`btmon`-Mitschnitt.

## Firmware prüfen

```fish
tlsr825x-ota validate ATC_v57.bin --json firmware.json
```

Geprüft werden Telink-Signatur, Dateigröße, Blockzahl und SHA-256. Eine
Modellzuordnung ist damit nicht möglich.

## OTA-Dry-Run

```fish
tlsr825x-ota dry-run A4:C1:38:A1:D0:36 \
  --scan-timeout 30 \
  --timeout 30 \
  --verbose
```

Der Dry-Run sendet den OTA-Handshake und liest den Status, überträgt aber keine
Firmwareblöcke.

## Firmware übertragen

```fish
tlsr825x-ota flash ATC_v57.bin \
  --device A4:C1:38:A1:D0:36 \
  --scan-timeout 30 \
  --timeout 30 \
  --delay 20 \
  --ack-every 8 \
  --finish-wait 8 \
  --verbose
```

Der Transfer verwendet feste 16-Byte-Firmwareblöcke in 20-Byte-GATT-Paketen.
Automatische Wiederholungen von Write-Without-Response-Paketen erfolgen bewusst
nicht, weil nicht sicher feststellbar ist, ob ein Paket das Gerät bereits erreicht
hat.

## Entwicklung

```fish
python -m pip install -e . pytest pytest-asyncio build
pytest -q
python -m build
```

## Lizenz

MIT
