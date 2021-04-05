# -*- coding: utf-8 -*-

class BaseASTMException(Exception):
    """Base ASTM error.
    """


class NotAccepted(BaseASTMException):
    """Received data is not acceptable.
    """


class InvalidState(BaseASTMException):
    """Should be raised in case of invalid ASTM handler state.
    """
