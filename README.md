# TLSR825x OTA CLI

Nativer Linux-CLI-Flasher für das klassische Telink-SDK-BLE-OTA-Protokoll.

## Sicherheit

Das Programm erkennt nur eine Telink-Firmware-Signatur. Es kann **nicht** zuverlässig feststellen, ob eine Firmware zum konkreten Gerät gehört.

Für das Xiaomi **LYWSD03MMC** ausschließlich die passende `ATC_*.bin` verwenden. `BTH_*.bin` ist für das MJWSD05MMC und darf nicht auf das LYWSD03MMC geschrieben werden.

Ein OTA-Transfer darf nicht unterbrochen werden. Gerät direkt neben den Bluetooth-Adapter legen und eine frische Batterie verwenden.

## Installation unter CachyOS / fish

```fish
python -m venv .venv
source .venv/bin/activate.fish
python -m pip install -e .
```

## Diagnose

```fish
tlsr825x-ota scan --prefix ATC_
tlsr825x-ota validate ATC_v57.bin
tlsr825x-ota info A4:C1:38:A1:D0:36 --scan-timeout 30 --timeout 30
tlsr825x-ota dry-run A4:C1:38:A1:D0:36 --scan-timeout 30 --timeout 30 --verbose
```

## Flashen

Erster Test ausschließlich mit einem funktionierenden Referenzgerät und der dazu passenden Firmware:

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

Das Protokoll verwendet:

- `00ff`, danach `01ff` als Startkommandos
- pro Paket: 2 Byte Adr-Index, 16 Byte Firmwaredaten, 2 Byte CRC-16/MODBUS
- Status `00` als Erfolgsmeldung
- als Ende: `02ff`, letzter Adr-Index, bitweise 16-Bit-Invertierung des Adr-Index

## Warum es keine automatischen Write-Retries gibt

Die OTA-Characteristic verwendet `write-without-response`. Meldet der Host dabei einen Fehler, ist nicht eindeutig feststellbar, ob das Paket das Gerät bereits erreicht hat. Ein erneutes Senden desselben Adr-Index kann die Sequenzprüfung des Telink-Bootloaders auslösen. Das Tool bricht deshalb ab, statt ein möglicherweise zugestelltes Paket blind zu wiederholen.
