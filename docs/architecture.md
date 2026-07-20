# Architektur

## Aktueller Umbau

`OTAClient` ist die öffentliche High-Level-API für Geräteinformationen, OTA-Handshakes und Firmwareübertragungen.

Im ersten Refactoring-Schritt delegiert die Klasse bewusst alle protokollkritischen Aufgaben an die vorhandenen,
auf echter Hardware getesteten Funktionen in `ota.py`. Dadurch bleiben das Verhalten der CLI, die Paketbildung
und der OTA-Ablauf unverändert. Gleichzeitig entsteht ein stabiler Einstiegspunkt für die CLI, spätere
Recovery-Werkzeuge und externe Python-Anwendungen.

```text
CLI / spätere GUI / Python-Anwendungen
                  |
                  v
              OTAClient
                  |
                  v
   bestehende Implementierung in ota.py
```

In späteren Refactoring-Schritten können Transport und Protokoll hinter eigene Schnittstellen verschoben werden.
Das geschieht erst, wenn Tests und Hardwareprüfungen das bisherige Verhalten ausreichend absichern.
