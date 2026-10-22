"""Fiscal device / e-invoicing hook.

The Ministry of Revenues requires sales to be registered on an approved fiscal
device or e-invoicing system. The exact device and protocol must be confirmed
with the hotel before go-live, so this module defines the interface and a
logging driver. Add a driver for the hotel's printer model and point
FISCAL_DRIVER at it.
"""

import logging
import os
from importlib import import_module

logger = logging.getLogger("vora.fiscal")


class LoggingFiscalDriver:
    """Records what would be sent; returns no fiscal number."""

    def register_invoice(self, invoice):
        logger.info("Fiscal registration (no device configured): %s total %s", invoice["invoice_number"], invoice["totals"]["total"])
        return ""


def get_driver():
    path = os.environ.get("FISCAL_DRIVER")
    if not path:
        return LoggingFiscalDriver()
    module, _, name = path.rpartition(".")
    return getattr(import_module(module), name)()
