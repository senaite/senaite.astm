# -*- coding: utf-8 -*-

from senaite.astm import logger


class Dispatcher(object):
    """ASTM Message dispatcher
    """
    def __init__(self, data):
        self.data = data

    def default_handler(self, data):
        raise ValueError('Unable to dispatch data: %r', data)

    def on_enq(self, data):
        """Calls on <ENQ> message receiving."""
        logger.warning('on_enq: %r', data)

    def on_ack(self, data):
        """Calls on <ACK> message receiving."""
        logger.warning('on_ack: %r', data)

    def on_nak(self, data):
        """Calls on <NAK> message receiving."""
        logger.warning('on_nak: %r', data)

    def on_eot(self, data):
        """Calls on <EOT> message receiving."""
        logger.warning('on_eot: %r', data)

    def on_message(self, data):
        """Calls on ASTM message receiving."""
        logger.warning('on_message: %r', data)

    def on_timeout(self, data):
        """Calls when timeout event occurs. Used to limit waiting time for
        response data."""
        logger.warning('on_timeout: %r', data)
