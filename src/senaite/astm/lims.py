# -*- coding: utf-8 -*-

import requests

from senaite.astm import logger

# SENAITE.JSONAPI route
API_BASE_URL = "@@API/senaite/v1"


class Session(object):
    """SENAITE Request Session
    """

    def __init__(self, url, **kw):
        auth = requests.utils.get_auth_from_url(url)
        self.username = auth[0]
        self.password = auth[1]
        self.url = requests.utils.urldefragauth(url)
        self.session = requests.Session()

    def auth(self):
        logger.info("Starting session with SENAITE ...")
        self.session.auth = (self.username, self.password)

        # try to get the version of the remote JSON API
        version = self.get("version")
        if not version or not version.get("version"):
            logger.error("senaite.jsonapi not found on at {}".format(self.url))
            return False

        # try to get the current logged in user
        user = self.get("users/current")
        user = user.get("items", [{}])[0]
        if not user or user.get("authenticated") is False:
            logger.error("Wrong username/password")
            return False

        logger.info("Session established ('{}') with '{}'"
                    .format(self.username, self.url))
        return True

    def post(self, endpoint, payload):
        """Sends a POST request to SENAITE
        """
        url = self.get_url(endpoint)
        try:
            response = self.session.post(url, data=payload)
        except Exception as e:
            message = "Could not send POST to {}".format(url)
            logger.error(message)
            logger.error(e)
            return {}

        return response.json()

    def get(self, endpoint, timeout=60):
        """Fetch the given url or endpoint and return a parsed JSON object
        """
        url = self.get_url(endpoint)
        try:
            response = self.session.get(url, timeout=timeout)
        except Exception as e:
            message = "Could not connect to {}".format(url)
            logger.error(message)
            logger.error(e)
            return {}

        status = response.status_code
        if status != 200:
            message = "GET for {} returned {}".format(endpoint, status)
            logger.error(message)
            return {}

        return response.json()

    def get_url(self, endpoint):
        """Create an API URL from an endpoint or absolute url
        """
        return "{}/{}/{}".format(self.url, API_BASE_URL, endpoint)
