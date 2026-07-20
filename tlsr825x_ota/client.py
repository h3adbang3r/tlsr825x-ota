"""High-level public API for Telink TLSR825x OTA operations.

This module intentionally delegates to the proven implementation in :mod:`ota`.
It introduces a stable application-facing API without changing protocol behavior.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .firmware import FirmwareImage
from .ota import FlashOptions, ProgressCallback, flash_firmware, inspect_device, ota_dry_run


@dataclass(slots=True)
class OTAClient:
    """High-level facade for operations against one BLE device.

    The first implementation is deliberately thin: all protocol-critical work remains
    in the already hardware-tested functions in :mod:`tlsr825x_ota.ota`.
    """

    address: str
    timeout: float = 20.0
    logger: logging.Logger | None = None

    async def info(self) -> dict[str, object]:
        """Read device, GATT and OTA capability information without writing data."""
        return await inspect_device(self.address, timeout=self.timeout)

    async def dry_run(self, *, settle_delay: float = 0.5) -> dict[str, object]:
        """Run the existing OTA handshake without transferring firmware blocks."""
        return await ota_dry_run(
            self.address,
            timeout=self.timeout,
            settle_delay=settle_delay,
            logger=self.logger,
        )

    async def flash(
        self,
        firmware: FirmwareImage,
        *,
        options: FlashOptions | None = None,
        progress: ProgressCallback | None = None,
    ) -> dict[str, object]:
        """Flash a validated firmware image using the existing OTA implementation."""
        effective_options = options or FlashOptions(timeout=self.timeout)
        return await flash_firmware(
            self.address,
            firmware,
            effective_options,
            progress=progress,
            logger=self.logger,
        )
