# -*- coding: utf-8 -*-

import asyncio
from dataclasses import dataclass
from time import sleep
from typing import Optional

import requests

from senaite.astm import logger
from senaite.astm.core.envelope import serialize_envelope

# SENAITE.JSONAPI route
API_BASE_URL = "@@API/senaite/v1"

DEFAULT_RETRIES = 3
DEFAULT_DELAY = 5
DEFAULT_CONSUMER = "senaite.lis2a.import"


class SenaiteError(Exception):
    """Base class for SENAITE LIMS push errors."""


class SenaiteUnreachableError(SenaiteError):
    """Raised when the SENAITE host cannot be reached at all."""


class SenaiteHTTPError(SenaiteError):
    """Raised when SENAITE responds with a non-200 status code."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class SenaiteAuthError(SenaiteError):
    """Raised when authentication against SENAITE fails."""


@dataclass
class PushResult:
    """Outcome of a `post_to_senaite` invocation.

    :param success: True if a push attempt succeeded.
    :param attempts: Number of push attempts that were made.
    :param last_error: The exception from the final failed attempt,
        or `None` on success.
    """
    success: bool
    attempts: int
    last_error: Optional[Exception] = None


class Session(object):
    """SENAITE Request Session.

    A single `requests.Session` is created in `__init__` and reused
    for all calls, so the TLS handshake is amortised across the
    connection rather than being repeated for every request.
    """

    def __init__(self, url):
        auth = requests.utils.get_auth_from_url(url)
        self.username = auth[0]
        self.password = auth[1]
        self.url = requests.utils.urldefragauth(url)
        self._session = requests.Session()
        self._session.auth = (self.username, self.password)

    @property
    def session(self):
        return self._session

    def auth(self):
        """Authenticate against SENAITE.

        :raises SenaiteAuthError: when the JSON API is missing or the
            credentials are rejected.
        :raises SenaiteUnreachableError: when the host cannot be
            reached.
        """
        logger.info("Starting session with SENAITE ...")

        version = self.get("version")
        if not version or not version.get("version"):
            raise SenaiteAuthError(
                "senaite.jsonapi not found at {}".format(self.url))

        user = self.get("users/current")
        user = user.get("items", [{}])[0]
        if not user or user.get("authenticated") is False:
            raise SenaiteAuthError("Wrong username/password")

        logger.info("Session established ('{}') with '{}'"
                    .format(self.username, self.url))

    def post(self, endpoint, payload):
        """Send a POST request to SENAITE.

        :returns: Parsed JSON response.
        :raises SenaiteUnreachableError: on connection-level failures.
        :raises SenaiteHTTPError: on non-200 responses.
        """
        url = self.get_url(endpoint)
        try:
            response = self._session.post(url, data=payload)
        except requests.RequestException as exc:
            raise SenaiteUnreachableError(
                "Could not POST to {}: {}".format(url, exc)) from exc

        if response.status_code != 200:
            raise SenaiteHTTPError(
                "POST {} returned {}".format(endpoint, response.status_code),
                status_code=response.status_code)

        return response.json()

    def get(self, endpoint, timeout=60):
        """Fetch the given endpoint and return parsed JSON.

        :raises SenaiteUnreachableError: on connection-level failures.
        :raises SenaiteHTTPError: on non-200 responses.
        """
        url = self.get_url(endpoint)
        try:
            response = self._session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            raise SenaiteUnreachableError(
                "Could not GET {}: {}".format(url, exc)) from exc

        if response.status_code != 200:
            raise SenaiteHTTPError(
                "GET {} returned {}".format(endpoint, response.status_code),
                status_code=response.status_code)

        return response.json()

    def get_url(self, endpoint):
        """Build an absolute API URL from an endpoint."""
        return "{}/{}/{}".format(self.url, API_BASE_URL, endpoint)


def post_to_senaite(messages, session, retries=DEFAULT_RETRIES,
                    delay=DEFAULT_DELAY, consumer=DEFAULT_CONSUMER):
    """POST ASTM messages to SENAITE.

    Authenticates **once** per call. Retries on push failure only
    re-call `session.post()`, not `session.auth()`.

    :returns: A :class:`PushResult` describing the outcome.
    """
    try:
        session.auth()
    except SenaiteError as exc:
        logger.error("Authentication failed: {}".format(exc))
        return PushResult(success=False, attempts=0, last_error=exc)

    payload = {
        "consumer": consumer,
        "messages": messages,
    }

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = session.post("push", payload)
        except SenaiteError as exc:
            last_error = exc
            logger.warning(
                "Push attempt {}/{} failed: {}: {}".format(
                    attempt, retries, type(exc).__name__, exc))
        else:
            if response.get("success"):
                return PushResult(
                    success=True, attempts=attempt, last_error=None)
            last_error = SenaiteHTTPError(
                "SENAITE returned success=False: {!r}".format(response))
            logger.warning(
                "Push attempt {}/{} rejected by SENAITE".format(
                    attempt, retries))

        if attempt < retries:
            sleep(delay)

    logger.error("Could not push the message after {} attempts".format(
        retries))
    return PushResult(
        success=False, attempts=retries, last_error=last_error)


class LimsPushHandler(object):
    """Pipeline handler that pushes a serialised envelope to SENAITE.

    The handler is async-callable so it slots into
    :class:`senaite.astm.core.pipeline.Pipeline` directly. The
    blocking ``post_to_senaite`` runs via :func:`asyncio.to_thread`
    so the event loop remains responsive while requests are in
    flight.
    """

    name = "lims_push"

    def __init__(self, session, retries=DEFAULT_RETRIES,
                 delay=DEFAULT_DELAY, consumer=DEFAULT_CONSUMER,
                 message_format="json"):
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
        return result
