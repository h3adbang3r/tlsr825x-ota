# Changelog

## 0.2.0 – 2026-07-20

- vollständiger klassischer Telink-SDK-OTA-Datenstrom auf Basis des dokumentierten 20-Byte-PDU-Formats
- Handshake-Status wird vor dem ersten Firmwareblock zwingend geprüft
- Status `00` wird während und nach dem Datentransfer validiert
- abschließende Statusabfrage auch dann, wenn die Blockzahl nicht durch das Prüfintervall teilbar ist
- OTA-Endepaket enthält letzten Adr-Index und dessen 16-Bit-Invertierung
- erwarteter Neustart/Disconnect nach OTA-Ende wird protokolliert
- automatische Write-Wiederholungen entfernt: Wiederholen eines möglicherweise bereits zugestellten Write Commands könnte den Adr-Index doppelt senden
- irreführende Disconnect-Warnung beim normalen Verlassen des Dry-Runs beseitigt
- zusätzliche Protokolltests

## 0.1.1 – 2026-07-20

- Service-Dump, MTU-Ermittlung und Dry-Run ergänzt

## 0.1.0 – 2026-07-20

- erste Projektversion
