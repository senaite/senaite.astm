# -*- coding: utf-8 -*-
"""Tests for :class:`senaite.astm.core.pipeline.Pipeline`.

The pipeline is the seam between the transport (which produces
:class:`Envelope` objects) and the outputs (disk capture, LIMS push,
future archivers). The contract under test:

- handlers fire in registration order
- a sync handler is awaited like an async one
- an exception in handler N is caught, recorded, and does not skip
  handler N+1
- the recorded results name handlers via their ``name`` attribute
  when one is set, falling back to ``__name__`` / ``__class__``
"""

import unittest

from senaite.astm.core.pipeline import Pipeline


class PipelineTest(unittest.IsolatedAsyncioTestCase):

    async def test_handlers_run_in_order(self):
        order = []

        async def first(env):
            order.append("first")

        async def second(env):
            order.append("second")

        async def third(env):
            order.append("third")

        pipeline = Pipeline([first, second, third])
        await pipeline.run(envelope=object())

        self.assertEqual(order, ["first", "second", "third"])

    async def test_sync_handler_is_awaited(self):
        seen = []

        def sync_handler(env):
            seen.append(env)

        pipeline = Pipeline([sync_handler])
        await pipeline.run("payload")

        self.assertEqual(seen, ["payload"])

    async def test_exception_in_handler_does_not_skip_next(self):
        order = []

        async def first(env):
            order.append("first")

        async def boom(env):
            order.append("boom-entered")
            raise RuntimeError("expected")

        async def third(env):
            order.append("third")

        pipeline = Pipeline([first, boom, third])
        results = await pipeline.run(object())

        self.assertEqual(order, ["first", "boom-entered", "third"])

        names = [name for name, _ in results]
        self.assertEqual(names[0], "first")
        self.assertEqual(names[2], "third")

        errors = [exc for _, exc in results]
        self.assertIsNone(errors[0])
        self.assertIsInstance(errors[1], RuntimeError)
        self.assertIsNone(errors[2])

    async def test_handler_name_attribute_wins(self):
        class NamedHandler(object):
            name = "my_handler"

            async def __call__(self, env):
                pass

        pipeline = Pipeline([NamedHandler()])
        results = await pipeline.run(object())
        self.assertEqual(results[0][0], "my_handler")

    async def test_handler_function_name_fallback(self):
        async def disk_capture(env):
            pass

        pipeline = Pipeline([disk_capture])
        results = await pipeline.run(object())
        self.assertEqual(results[0][0], "disk_capture")

    async def test_empty_pipeline_is_a_noop(self):
        pipeline = Pipeline()
        results = await pipeline.run(object())
        self.assertEqual(results, [])
        self.assertEqual(len(pipeline), 0)

    async def test_add_appends_handler(self):
        pipeline = Pipeline()

        async def h(env):
            pass

        pipeline.add(h)
        self.assertEqual(len(pipeline), 1)


class HandlersTest(unittest.IsolatedAsyncioTestCase):

    def test_serialize_envelope_json(self):
        from senaite.astm.core.envelope import Envelope, Metadata
        from senaite.astm.core.handlers import serialize_envelope

        envelope = Envelope(metadata=Metadata(astm="A", lis2a="L"))
        payload = serialize_envelope(envelope, "json")
        self.assertIn("\"astm\":\"A\"", payload)
        self.assertIn("\"envelope_version\"", payload)

    def test_serialize_envelope_astm_uses_metadata(self):
        from senaite.astm.core.envelope import Envelope, Metadata
        from senaite.astm.core.handlers import serialize_envelope

        envelope = Envelope(metadata=Metadata(astm="raw-astm", lis2a="L"))
        self.assertEqual(
            serialize_envelope(envelope, "astm"), "raw-astm")

    def test_serialize_envelope_lis2a_uses_metadata(self):
        from senaite.astm.core.envelope import Envelope, Metadata
        from senaite.astm.core.handlers import serialize_envelope

        envelope = Envelope(metadata=Metadata(astm="A", lis2a="raw-lis2a"))
        self.assertEqual(
            serialize_envelope(envelope, "lis2a"), "raw-lis2a")

    def test_serialize_envelope_unknown_format_raises(self):
        from senaite.astm.core.envelope import Envelope, Metadata
        from senaite.astm.core.handlers import serialize_envelope

        envelope = Envelope(metadata=Metadata(astm="A", lis2a="L"))
        with self.assertRaises(ValueError):
            serialize_envelope(envelope, "xml")

    async def test_disk_capture_noop_without_path(self):
        from senaite.astm.core.envelope import Envelope, Metadata
        from senaite.astm.core.handlers import DiskCaptureHandler

        handler = DiskCaptureHandler(path=None)
        envelope = Envelope(metadata=Metadata(astm="A", lis2a="L"))
        await handler(envelope)  # must not raise


if __name__ == "__main__":
    unittest.main()
