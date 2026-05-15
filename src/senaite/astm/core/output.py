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


def _default_payload(envelope):
    """Default extractor: the raw ASTM payload from ``metadata.astm``."""
    return envelope.metadata.astm or ""


class DiskCaptureHandler(object):
    """Persist a per-envelope payload to disk.

    :param path: Target directory. May not yet exist; it will be
        created on first write. ``None`` or an empty string makes the
        handler a no-op (used by the CLI when ``--output`` is not set).
    :param payload: Callable that extracts the bytes / string to
        write from an envelope. Defaults to
        :attr:`Envelope.metadata.astm` so the ASTM CLI keeps its
        historical behaviour; the HL7 CLI passes a lambda for
        :attr:`Envelope.metadata.hl7`.
    :param ext: File extension. Defaults to ``.txt`` to keep existing
        ASTM captures intact; HL7 callers typically pass ``.hl7``.

    Each invocation writes one timestamped file containing the value
    returned by ``payload(envelope)``.
    """

    name = "disk_capture"

    def __init__(self, path, payload=_default_payload, ext=".txt"):
        self.path = path
        self.payload = payload
        self.ext = ext

    async def __call__(self, envelope):
        if not self.path:
            return
        message = self.payload(envelope) or ""
        await asyncio.to_thread(write_message, message, self.path,
                                ext=self.ext)
