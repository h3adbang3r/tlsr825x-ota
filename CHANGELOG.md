# Changelog

Alle wesentlichen Änderungen an diesem Projekt werden hier dokumentiert.

## Unreleased

### Geändert

- `OTAClient` als öffentliche High-Level-API eingeführt.
- Die bestehenden CLI-Befehle `info`, `dry-run` und `flash` über `OTAClient` geführt.
- Die auf echter Hardware getestete OTA-Protokollimplementierung unverändert gelassen.

## [0.2.1] – 2026-07-20

### Hinzugefügt

- `mtu-test`: vollständig schreibfreier BLE-/MTU-Diagnosetest ohne OTA-Handshake.
- Beobachtung von `mtu_size` und `max_write_without_response_size` über mehrere Sekunden.
- Best-Effort-MTU-Ermittlung über das BlueZ-Backend von Bleak.
- `capture-mtu`: paralleler `btmon`-Mitschnitt als BTSnoop-Datei plus JSON-Zusammenfassung.
- Auslesen standardisierter Device-Information-Characteristics, sofern vorhanden.
- JSON-Export für `info`, `mtu-test` und `validate`.
- SHA-256-Ausgabe bei der Firmwarevalidierung.
- GitHub-Actions-Testmatrix für Python 3.11 bis 3.14.
- Dokumentation zur MTU-Diagnose unter BlueZ.

### Behoben

- Ein lokaler Disconnect beim Verlassen des Bleak-Kontextes wird nicht mehr fälschlich
  als beobachteter Geräte-Neustart protokolliert.

### Sicherheit

- `mtu-test` und `capture-mtu` führen keinen OTA-Handshake und keine
  GATT-Schreibzugriffe aus.

## [0.2.0] – 2026-07-20

- Vollständiger Telink-OTA-Datenstrom mit 16-Byte-Blöcken, CRC, Statusabfragen und
  Abschlusskommando.
