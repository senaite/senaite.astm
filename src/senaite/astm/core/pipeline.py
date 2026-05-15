# -*- coding: utf-8 -*-
"""Message pipeline.

A :class:`Pipeline` runs a sequence of registered handlers against a
parsed :class:`~senaite.astm.core.envelope.Envelope`. Handlers are
async callables ``handler(envelope) -> awaitable``. They are invoked
in registration order. An exception raised by one handler is logged
and does not prevent later handlers from running.

The transport layer (TCP listener, framing, wrapper) is intentionally
unaware of the pipeline. The CLI server wires the two together so
new outputs (S3 archive, message bus, metrics) become a new
``Handler`` rather than edits to ``server.main``.
"""

import asyncio
import inspect

from senaite.astm import logger


class Pipeline(object):
    """Run handlers in order, isolating exceptions.

    :param handlers: Iterable of async or sync callables that accept
        a single envelope argument. Sync callables are executed via
        :func:`asyncio.to_thread`.
    """

    def __init__(self, handlers=None):
        self.handlers = list(handlers or [])

    def add(self, handler):
        """Append a handler to the pipeline."""
        self.handlers.append(handler)

    def __len__(self):
        return len(self.handlers)

    async def run(self, envelope):
        """Run every handler against ``envelope``.

        Returns a list of ``(handler_name, exception_or_None)`` in
        the order the handlers were registered.
        """
        results = []
        for handler in self.handlers:
            name = self._handler_name(handler)
            try:
                await self._invoke(handler, envelope)
                results.append((name, None))
            except Exception as exc:
                logger.error(
                    "Pipeline handler %r failed: %r", name, exc)
                results.append((name, exc))
        return results

    @staticmethod
    async def _invoke(handler, envelope):
        if inspect.iscoroutinefunction(handler):
            return await handler(envelope)
        result = handler(envelope)
        if inspect.isawaitable(result):
            return await result
        return result

    @staticmethod
    def _handler_name(handler):
        return getattr(handler, "name", None) \
            or getattr(handler, "__name__", None) \
            or handler.__class__.__name__


async def run_pipeline_in_thread(pipeline, envelope):
    """Run a pipeline whose handlers are blocking (sync) in a thread.

    Convenience for callers that compose pipelines from sync handlers
    only and want every handler off the event-loop thread.
    """
    return await asyncio.to_thread(asyncio.run, pipeline.run(envelope))
