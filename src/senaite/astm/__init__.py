# -*- coding: utf-8 -*-

import logging
import logging.handlers

from zope.interface.registry import Components

LOG_LEVEL = logging.INFO

logger = logging.getLogger("senaite.astm")
# Set the log level to LOG_LEVEL
logger.setLevel(LOG_LEVEL)

# global adapter registry
adapter_registry = Components()

# Make sure adapters are initialized *after* the adapter registry is in place!
from senaite.astm import adapters  # noqa: F401,E402
