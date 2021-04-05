# -*- coding: utf-8 -*-

from senaite.astm import logger
from senaite.astm.codecs import is_chunked_message
from senaite.astm.codecs import join
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.constants import EOT
from senaite.astm.constants import NAK
from senaite.astm.constants import STX
from senaite.astm.dispatcher import Dispatcher
from senaite.astm.exceptions import InvalidState
from senaite.astm.exceptions import NotAccepted


class Request(object):
    """ASTM data wrapper
    """

    def __init__(self, data, **kw):
        self.data = data
        self.response = None
        self.dispatcher = Dispatcher()
        self._is_transfer_state = False
        self._chunks = []

    def __call__(self):
        self.response = self.handle_data(self.data)
        return self.response

    def handle_data(self, data):
        """Process incoming data
        """
        if data.startswith(ENQ):
            resp = self.on_enq(data)
        elif data.startswith(ACK):
            resp = self.on_ack(data)
        elif data.startswith(NAK):
            resp = self.on_nak(data)
        elif data.startswith(EOT):
            resp = self.on_eot(data)
        elif data.startswith(STX):
            resp = self.on_message(data)
        else:
            resp = self.default_handler(data)
        self.response = resp

    def default_handler(self, data):
        raise ValueError('Unable to dispatch data: %r', data)

    def on_enq(self, data):
        """Calls on <ENQ> message receiving."""
        logger.debug('on_enq: %r', data)
        if not self._is_transfer_state:
            self._is_transfer_state = True
            return ACK
        else:
            logger.error('ENQ is not expected')
            return NAK

    def on_ack(self, data):
        """Calls on <ACK> message receiving."""
        logger.debug('on_ack: %r', data)
        raise NotAccepted('Server should not be ACKed.')

    def on_nak(self, data):
        """Calls on <NAK> message receiving."""
        logger.debug('on_nak: %r', data)
        raise NotAccepted('Server should not be NAKed.')

    def on_eot(self, data):
        """Calls on <EOT> message receiving."""
        logger.debug('on_eot: %r', data)
        if self._is_transfer_state:
            self._is_transfer_state = False

    def on_message(self, data):
        """Calls on ASTM message receiving."""
        logger.debug('on_message: %r', data)
        if not self._is_transfer_state:
            self.discard_input_buffers()
            return NAK
        else:
            try:
                self.handle_message(data)
                return ACK
            except Exception as exc:
                logger.error('Error occurred on message handling. {!r}'
                             .format(exc))
                return NAK

    def on_timeout(self, data):
        """Calls when timeout event occurs. Used to limit waiting time for
        response data."""
        logger.debug('on_timeout: %r', data)

    def discard_input_buffers(self):
        """Flush input buffers
        """
        self._chunks = []

    def handle_message(self, message):
        self.is_chunked_transfer = is_chunked_message(message)
        if self.is_chunked_transfer:
            self._chunks.append(message)
        elif self._chunks:
            self._chunks.append(message)
            self.dispatcher(join(self._chunks))
            self._chunks = []
        else:
            self.dispatcher(message)
