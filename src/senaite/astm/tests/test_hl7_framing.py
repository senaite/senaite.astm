# -*- coding: utf-8 -*-
"""MLLP framing tests for :mod:`senaite.astm.transports.hl7.framing`.

The contract under test:

- :func:`wrap` produces ``SB + payload + EB + CR`` and accepts both
  ``bytes`` and ``str`` inputs.
- :func:`extract_messages` consumes complete MLLP blocks out of a
  streaming buffer, returns the unconsumed tail for the caller's
  next read, and drops bytes that arrive before the first ``SB``.
"""

import unittest

from senaite.astm.transports.hl7.framing import (
    EB, CR, MLLP_END, SB, extract_messages, wrap,
)


def make_block(payload):
    return SB + payload + MLLP_END


class WrapTest(unittest.TestCase):

    def test_wrap_bytes(self):
        self.assertEqual(wrap(b"hello"), SB + b"hello" + EB + CR)

    def test_wrap_str_uses_utf8(self):
        self.assertEqual(wrap("héllo"), SB + "héllo".encode("utf-8")
                         + EB + CR)


class ExtractMessagesTest(unittest.TestCase):

    def test_empty_buffer(self):
        messages, remainder = extract_messages(b"")
        self.assertEqual(messages, [])
        self.assertEqual(remainder, b"")

    def test_one_complete_block(self):
        block = make_block(b"MSH|^~\\&|...")
        messages, remainder = extract_messages(block)
        self.assertEqual(messages, [b"MSH|^~\\&|..."])
        self.assertEqual(remainder, b"")

    def test_two_back_to_back_blocks(self):
        buf = make_block(b"FIRST") + make_block(b"SECOND")
        messages, remainder = extract_messages(buf)
        self.assertEqual(messages, [b"FIRST", b"SECOND"])
        self.assertEqual(remainder, b"")

    def test_partial_block_at_tail_is_returned(self):
        complete = make_block(b"DONE")
        partial = SB + b"NOT-YET-DONE"
        messages, remainder = extract_messages(complete + partial)
        self.assertEqual(messages, [b"DONE"])
        self.assertEqual(remainder, partial)

    def test_pre_sb_garbage_is_dropped(self):
        garbage = b"random junk before framing"
        messages, remainder = extract_messages(garbage)
        self.assertEqual(messages, [])
        # No SB → caller has nothing useful left.
        self.assertEqual(remainder, b"")

    def test_pre_sb_garbage_before_complete_block(self):
        buf = b"junk" + make_block(b"REAL")
        messages, remainder = extract_messages(buf)
        self.assertEqual(messages, [b"REAL"])
        self.assertEqual(remainder, b"")

    def test_streaming_reassembly_in_two_chunks(self):
        """Simulate two TCP reads: first half of a block, then the
        rest. The first call returns no messages but preserves the
        partial frame; the second call yields the complete block."""
        block = make_block(b"STREAMED PAYLOAD")
        chunk_one = block[:5]
        chunk_two = block[5:]

        messages, buffer = extract_messages(chunk_one)
        self.assertEqual(messages, [])
        self.assertEqual(buffer, chunk_one)

        buffer += chunk_two
        messages, buffer = extract_messages(buffer)
        self.assertEqual(messages, [b"STREAMED PAYLOAD"])
        self.assertEqual(buffer, b"")

    def test_eb_without_cr_is_not_a_complete_block(self):
        buf = SB + b"PAYLOAD" + EB
        messages, remainder = extract_messages(buf)
        self.assertEqual(messages, [])
        self.assertEqual(remainder, buf)


if __name__ == "__main__":
    unittest.main()
