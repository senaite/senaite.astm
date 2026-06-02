# -*- coding: utf-8 -*-

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

import responses

from senaite.astm.core.lims import PushResult
from senaite.astm.core.lims import SenaiteAuthError
from senaite.astm.core.lims import SenaiteHTTPError
from senaite.astm.core.lims import SenaiteUnreachableError
from senaite.astm.core.lims import Session
from senaite.astm.core.lims import post_to_senaite

URL = "http://admin:secret@senaite.example.com"
BASE = "http://senaite.example.com/@@API/senaite/v1"


def auth_ok():
    responses.add(
        responses.GET,
        "{}/version".format(BASE),
        json={"version": "2.6.0"},
        status=200)
    responses.add(
        responses.GET,
        "{}/users/current".format(BASE),
        json={"items": [{"authenticated": True, "username": "admin"}]},
        status=200)


def auth_no_jsonapi():
    responses.add(
        responses.GET,
        "{}/version".format(BASE),
        json={},
        status=200)


def auth_bad_credentials():
    responses.add(
        responses.GET,
        "{}/version".format(BASE),
        json={"version": "2.6.0"},
        status=200)
    responses.add(
        responses.GET,
        "{}/users/current".format(BASE),
        json={"items": [{"authenticated": False}]},
        status=200)


class SessionAuthTest(unittest.TestCase):
    """Session.auth() exercises the version probe and the user probe.
    """

    def test_init_extracts_credentials_from_url(self):
        session = Session(URL)
        self.assertEqual(session.username, "admin")
        self.assertEqual(session.password, "secret")
        self.assertEqual(session.url, "http://senaite.example.com")

    def test_get_url_joins_endpoint(self):
        session = Session(URL)
        self.assertEqual(
            session.get_url("push"),
            "http://senaite.example.com/@@API/senaite/v1/push")

    def test_session_is_cached_across_calls(self):
        """The TLS handshake is amortised by reusing one
        requests.Session across all calls.
        """
        session = Session(URL)
        self.assertIs(session.session, session.session)

    @responses.activate
    def test_auth_happy_path(self):
        auth_ok()
        # auth() returns None on success and raises on failure.
        self.assertIsNone(Session(URL).auth())

    @responses.activate
    def test_auth_raises_when_jsonapi_missing(self):
        auth_no_jsonapi()
        with self.assertRaises(SenaiteAuthError):
            Session(URL).auth()

    @responses.activate
    def test_auth_raises_when_credentials_invalid(self):
        auth_bad_credentials()
        with self.assertRaises(SenaiteAuthError):
            Session(URL).auth()

    @responses.activate
    def test_get_raises_http_error_on_non_200(self):
        responses.add(
            responses.GET,
            "{}/anything".format(BASE),
            json={"error": "boom"},
            status=500)
        with self.assertRaises(SenaiteHTTPError) as ctx:
            Session(URL).get("anything")
        self.assertEqual(ctx.exception.status_code, 500)

    @responses.activate
    def test_get_raises_unreachable_on_connection_error(self):
        # No matching response registered -> requests raises
        with self.assertRaises(SenaiteUnreachableError):
            Session(URL).get("anything")

    @responses.activate
    def test_post_raises_unreachable_on_connection_error(self):
        with self.assertRaises(SenaiteUnreachableError):
            Session(URL).post("push", {"x": 1})

    @responses.activate
    def test_post_raises_http_error_on_non_200(self):
        responses.add(
            responses.POST,
            "{}/push".format(BASE),
            json={"error": "boom"},
            status=503)
        with self.assertRaises(SenaiteHTTPError) as ctx:
            Session(URL).post("push", {"x": 1})
        self.assertEqual(ctx.exception.status_code, 503)

    def test_post_passes_default_timeout(self):
        """A blocking POST behind a hung Zope worker would pin a
        thread-pool worker indefinitely. Confirm the session always
        passes a timeout tuple through to requests."""
        from senaite.astm.core.lims import DEFAULT_HTTP_TIMEOUT
        session = Session(URL)
        with patch.object(session._session, "post") as fake_post:
            fake_post.return_value = MagicMock(
                status_code=200, json=lambda: {})
            session.post("push", {"x": 1})
        kwargs = fake_post.call_args.kwargs
        self.assertEqual(kwargs.get("timeout"), DEFAULT_HTTP_TIMEOUT)

    def test_get_passes_default_timeout(self):
        from senaite.astm.core.lims import DEFAULT_HTTP_TIMEOUT
        session = Session(URL)
        with patch.object(session._session, "get") as fake_get:
            fake_get.return_value = MagicMock(
                status_code=200, json=lambda: {})
            session.get("anything")
        kwargs = fake_get.call_args.kwargs
        self.assertEqual(kwargs.get("timeout"), DEFAULT_HTTP_TIMEOUT)


class PushResultTest(unittest.TestCase):
    """PushResult is the documented return type of post_to_senaite."""

    def test_default_last_error_is_none(self):
        result = PushResult(success=True, attempts=1)
        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 1)
        self.assertIsNone(result.last_error)

    def test_carries_last_error(self):
        err = SenaiteHTTPError("boom", status_code=500)
        result = PushResult(success=False, attempts=3, last_error=err)
        self.assertFalse(result.success)
        self.assertEqual(result.attempts, 3)
        self.assertIs(result.last_error, err)


class PostToSenaiteTest(unittest.TestCase):
    """post_to_senaite authenticates once, then retries POST only.

    The loop reads `time.sleep` from `senaite.astm.core.lims`, so we
    patch that import to keep the tests fast.
    """

    def setUp(self):
        sleep_patcher = patch("senaite.astm.core.lims.sleep")
        self.sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    @responses.activate
    def test_happy_path_no_retry(self):
        auth_ok()
        responses.add(
            responses.POST,
            "{}/push".format(BASE),
            json={"success": True},
            status=200)
        result = post_to_senaite([b"msg"], Session(URL))
        # 1 auth pair (2 GETs) + 1 POST = 3 calls
        self.assertEqual(len(responses.calls), 3)
        self.sleep.assert_not_called()
        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 1)
        self.assertIsNone(result.last_error)

    @responses.activate
    def test_retry_then_success_authenticates_only_once(self):
        auth_ok()
        responses.add(
            responses.POST,
            "{}/push".format(BASE),
            json={"success": False},
            status=200)
        responses.add(
            responses.POST,
            "{}/push".format(BASE),
            json={"success": True},
            status=200)
        result = post_to_senaite(
            [b"msg"], Session(URL), retries=3, delay=1)
        # 1 auth pair + 2 POSTs = 4 calls (no second auth)
        self.assertEqual(len(responses.calls), 4)
        self.sleep.assert_called_once_with(1)
        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 2)

    @responses.activate
    def test_retry_exhausted(self):
        auth_ok()
        for _ in range(3):
            responses.add(
                responses.POST,
                "{}/push".format(BASE),
                json={"success": False},
                status=200)
        result = post_to_senaite(
            [b"msg"], Session(URL), retries=3, delay=1)
        # 1 auth pair + 3 POSTs = 5 calls (auth not re-run)
        self.assertEqual(len(responses.calls), 5)
        # two sleeps: between attempts 1-2 and 2-3, none after the last
        self.assertEqual(self.sleep.call_count, 2)
        self.assertFalse(result.success)
        self.assertEqual(result.attempts, 3)
        self.assertIsInstance(result.last_error, SenaiteHTTPError)

    def test_retry_recovers_from_connection_error(self):
        """Connection-level failures are retried, not propagated."""
        session = MagicMock()
        session.auth.return_value = True
        session.post.side_effect = [
            SenaiteUnreachableError("network blip"),
            {"success": True},
        ]
        result = post_to_senaite(
            [b"msg"], session, retries=3, delay=0)
        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(session.post.call_count, 2)

    def test_auth_failure_skips_post_and_does_not_retry(self):
        """If auth fails the loop bails out without firing POSTs."""
        session = MagicMock()
        session.auth.side_effect = SenaiteAuthError("nope")
        result = post_to_senaite(
            [b"msg"], session, retries=3, delay=0)
        session.auth.assert_called_once()
        session.post.assert_not_called()
        self.assertFalse(result.success)
        self.assertEqual(result.attempts, 0)
        self.assertIsInstance(result.last_error, SenaiteAuthError)

    def test_consumer_arg_passed_through(self):
        """`consumer` propagates from kwargs into the POST payload."""
        session = MagicMock()
        session.auth.return_value = True
        session.post.return_value = {"success": True}
        post_to_senaite(
            [b"msg"], session, consumer="custom.consumer")
        session.post.assert_called_once_with(
            "push",
            {"consumer": "custom.consumer", "messages": [b"msg"]})

    def test_default_consumer(self):
        session = MagicMock()
        session.auth.return_value = True
        session.post.return_value = {"success": True}
        post_to_senaite([b"msg"], session)
        _, payload = session.post.call_args[0]
        self.assertEqual(payload["consumer"], "senaite.lis2a.import")
