# -*- coding: utf-8 -*-
"""Built-in pipeline handlers.

Each handler is a callable invoked by :class:`Pipeline` with a parsed
:class:`~senaite.astm.core.envelope.Envelope`. Handlers consume the
envelope: write the raw ASTM payload to disk, push the serialised
envelope to SENAITE, etc. New outputs (S3 archive, message bus,
metrics) become a new handler rather than edits to the CLI server.

Handlers expose a ``name`` attribute used by the pipeline's
exception reporting.
"""

import asyncio
import os

from senaite.astm import logger
from senaite.astm.core.lims import post_to_senaite
from senaite.astm.utils import write_message


def serialize_envelope(envelope, message_format="json"):
    """Serialise an envelope according to ``message_format``.

    Returns a string. Raises :class:`ValueError` for unknown formats.
    """
    if message_format == "json":
        return envelope.model_dump_json()
    if message_format == "astm":
        return envelope.metadata.astm or ""
    if message_format == "lis2a":
        return envelope.metadata.lis2a or ""
    raise ValueError("Unknown message_format: %r" % message_format)


class DiskCaptureHandler(object):
    """Write the raw ASTM payload to disk.

    Mirrors today's behaviour of ``server.dispatch_astm_message`` /
    ``protocol.log_message``: the raw ASTM string lands in ``path``,
    one file per message, named with a timestamp. PR-H tightens the
    semantics (no implicit ``$CWD/astm_messages`` directory).
    """

    name = "disk_capture"

    def __init__(self, path):
        self.path = path

    async def __call__(self, envelope):
        if not self.path:
            return
        message = envelope.metadata.astm or ""
        await asyncio.to_thread(write_message, message, self.path)


class LimsPushHandler(object):
    """Push the serialised envelope to SENAITE."""

    name = "lims_push"

    def __init__(self, session, retries=3, delay=5,
                 consumer="senaite.lis2a.import", message_format="json"):
        self.session = session
        self.retries = retries
        self.delay = delay
        self.consumer = consumer
        self.message_format = message_format

    async def __call__(self, envelope):
        payload = serialize_envelope(envelope, self.message_format)
        result = await asyncio.to_thread(
            post_to_senaite,
            payload,
            self.session,
            retries=self.retries,
            delay=self.delay,
            consumer=self.consumer,
        )
        if not result.success:
            logger.error(
                "LIMS push gave up after %d attempts: %r",
                result.attempts, result.last_error)


def default_disk_capture_path():
    """Return the legacy implicit capture directory if present.

    Preserves PR-F behaviour for the implicit
    ``$CWD/astm_messages/`` directory; PR-H removes this magic.
    """
    candidate = os.path.join(os.getcwd(), "astm_messages")
    if os.path.isdir(candidate):
        return candidate
    return None
