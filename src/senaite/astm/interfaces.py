# -*- coding: utf-8 -*-
from zope.interface import Interface


class IDataHandler(Interface):
    """Handle custom data
    """

    def can_handle():
        """Checks if the adapter can handle the data
        """

    def handle_data(data):
        """Handle the received data.
        """
