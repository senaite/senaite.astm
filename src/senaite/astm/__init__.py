# -*- coding: utf-8 -*-

import logging
import logging.handlers


LOG_LEVEL = logging.INFO
LOG_FILENAME = "senaite-astm.log"

logger = logging.getLogger("senaite.astm")
# Set the log level to LOG_LEVEL
logger.setLevel(LOG_LEVEL)
# Make a handler that writes to a file, making a new file at midnight and
# keeping 3 backups
handler = logging.handlers.TimedRotatingFileHandler(
    LOG_FILENAME, when="midnight", backupCount=3)
# Format each log message like this
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
# Attach the formatter to the handler
handler.setFormatter(formatter)
# Attach the handler to the logger
logger.addHandler(handler)
