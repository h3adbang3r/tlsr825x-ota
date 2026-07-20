#!/usr/bin/env bash
set -euo pipefail

# Für das LYWSD03MMC ausschließlich die passende ATC-Firmware einsetzen.
tlsr825x-ota validate ATC_v57.bin
tlsr825x-ota info ATC_A1D036
tlsr825x-ota flash --device ATC_A1D036 --delay 20 --ack-every 8 ATC_v57.bin
