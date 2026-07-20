# MTU-Diagnose unter Linux/BlueZ

`tlsr825x-ota mtu-test` führt ausschließlich Lese- und Linkdiagnosen aus. Es wird
kein OTA-Handshake ausgelöst und kein GATT-Wert geschrieben.

Bleak gibt für `BleakClient.mtu_size` unter BlueZ regulär den Mindestwert 23 aus.
Das Tool ruft deshalb – sofern vorhanden – zusätzlich den BlueZ-spezifischen
Backend-Hook zur MTU-Ermittlung auf und beobachtet parallel
`max_write_without_response_size`.

```bash
tlsr825x-ota mtu-test A4:C1:38:A1:D0:36 --observe 10 --json mtu.json
```

Für einen HCI-Mitschnitt:

```bash
tlsr825x-ota capture-mtu A4:C1:38:A1:D0:36 --observe 10
```

Der Mitschnitt enthält `btmon.btsnoop` und `summary.json`. Falls `btmon` wegen
fehlender Rechte sofort beendet wird, den Befehl mit passenden Capabilities oder
vorübergehend mit `sudo` ausführen. Im Capture-Modus werden ebenfalls keine
GATT-Schreibzugriffe durchgeführt.
