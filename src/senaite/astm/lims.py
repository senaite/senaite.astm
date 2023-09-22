# -*- coding: utf-8 -*-

from time import sleep

import requests

from senaite.astm import logger

# SENAITE.JSONAPI route
API_BASE_URL = "@@API/senaite/v1"


def post_to_senaite(messages, session, **kwargs):
    """POST ASTM messages to SENAITE
    """
    attempt = 1
    retries = kwargs.get('retries', 3)
    delay = kwargs.get('delay', 5)
    consumer = kwargs.get('consumer', 'senaite.lis2a.import')
    success = False

    while True:
        # Open a session with SENAITE and authenticate
        authenticated = session.auth()
        # Build the POST payload
        payload = {
            'consumer': consumer,
            'messages': messages,
        }
        if authenticated:
            # Send the message
            response = session.post('push', payload)
            success = response.get('success')
            if success:
                break

        # the break here ensures that at least one time is tried
        if attempt >= retries:
            break

        # increase attempts
        attempt += 1

        logger.warn('Could not push. Retrying {}/{}'.format(
            attempt, retries))

        # Sleep before we retry
        sleep(delay)

    if not success:
        logger.error('Could not push the message')


class Session(object):
    """SENAITE Request Session
    """

    def __init__(self, url, **kw):
        auth = requests.utils.get_auth_from_url(url)
        self.username = auth[0]
        self.password = auth[1]
        self.url = requests.utils.urldefragauth(url)

    @property
    def session(self):
        session = requests.Session()
        session.auth = (self.username, self.password)
        return session

    def auth(self):
        logger.info("Starting session with SENAITE ...")

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
