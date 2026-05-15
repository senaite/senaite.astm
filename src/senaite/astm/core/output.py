# -*- coding: utf-8 -*-
"""Disk-capture output handler for the message pipeline.

Before PR-H, raw-message capture was an implicit side effect of
``protocol.log_message``: if a directory named ``astm_messages``
existed in the server's current working directory, every message
landed there. The behaviour was undocumented, untestable in
isolation, and surprised every reader.

PR-H promotes capture to a first-class :class:`Pipeline` handler.
The capture target is configured exclusively via ``--output``; no
filesystem is consulted to *discover* whether capture should be on.
The implicit ``$CWD/astm_messages/`` directory is gone.
"""

import asyncio

from senaite.astm.utils import write_message


class DiskCaptureHandler(object):
    """Persist the raw ASTM payload of every envelope to disk.

    :param path: Target directory. May not yet exist; it will be
        created on first write. ``None`` or an empty string makes the
        handler a no-op (used by the CLI when ``--output`` is not set).

    Each invocation writes one timestamped file containing the raw
    ASTM bytes carried in :attr:`Envelope.metadata.astm`.
    """

    name = "disk_capture"

    def __init__(self, path):
        self.path = path

    async def __call__(self, envelope):
        if not self.path:
            return
        message = envelope.metadata.astm or ""
        await asyncio.to_thread(write_message, message, self.path)
