# -*- coding: utf-8 -*-

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

import responses

from senaite.astm import lims
from senaite.astm.lims import Session
from senaite.astm.lims import post_to_senaite

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
    """Session.auth() exercises both the version probe and the user probe.
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

    @responses.activate
    def test_auth_happy_path(self):
        auth_ok()
        self.assertTrue(Session(URL).auth())

    @responses.activate
    def test_auth_returns_false_when_jsonapi_missing(self):
        auth_no_jsonapi()
        self.assertFalse(Session(URL).auth())

    @responses.activate
    def test_auth_returns_false_when_credentials_invalid(self):
        auth_bad_credentials()
        self.assertFalse(Session(URL).auth())

    @responses.activate
    def test_get_returns_empty_dict_on_non_200(self):
        responses.add(
            responses.GET,
            "{}/anything".format(BASE),
            json={"error": "boom"},
            status=500)
        self.assertEqual(Session(URL).get("anything"), {})

    @responses.activate
    def test_get_returns_empty_dict_on_connection_error(self):
        # No matching response registered → ConnectionError
        self.assertEqual(Session(URL).get("anything"), {})

    @responses.activate
    def test_post_returns_empty_dict_on_connection_error(self):
        self.assertEqual(Session(URL).post("push", {"x": 1}), {})


class PostToSenaiteTest(unittest.TestCase):
    """post_to_senaite handles auth, push, and the retry/delay loop.

    The loop reads `time.sleep` from `senaite.astm.lims`, so we patch
    that import to keep the tests fast.
    """

    def setUp(self):
        sleep_patcher = patch("senaite.astm.lims.sleep")
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
        post_to_senaite([b"msg"], Session(URL))
        # auth (2 GETs) + 1 POST = 3 calls
        self.assertEqual(len(responses.calls), 3)
        self.sleep.assert_not_called()

    @responses.activate
    def test_retry_then_success(self):
        # auth happens once per attempt; register enough responses for two
        for _ in range(2):
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
        post_to_senaite([b"msg"], Session(URL), retries=3, delay=1)
        # 2 auth pairs + 2 POSTs = 6 calls
        self.assertEqual(len(responses.calls), 6)
        # one sleep between the two attempts
        self.sleep.assert_called_once_with(1)

    @responses.activate
    def test_retry_exhausted(self):
        for _ in range(3):
            auth_ok()
        for _ in range(3):
            responses.add(
                responses.POST,
                "{}/push".format(BASE),
                json={"success": False},
                status=200)
        post_to_senaite([b"msg"], Session(URL), retries=3, delay=1)
        # 3 auth pairs + 3 POSTs = 9 calls
        self.assertEqual(len(responses.calls), 9)
        # two sleeps: between attempts 1-2 and 2-3, none after the last
        self.assertEqual(self.sleep.call_count, 2)

    def test_auth_failure_still_retries(self):
        """If auth fails the loop should still respect the retry budget."""
        session = MagicMock()
        session.auth.return_value = False
        post_to_senaite([b"msg"], session, retries=3, delay=0)
        self.assertEqual(session.auth.call_count, 3)
        session.post.assert_not_called()

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


class LimsModuleSurfaceTest(unittest.TestCase):
    """Lock down the public surface of the module so refactors that
    rename or move these symbols break this test loudly.
    """

    def test_post_to_senaite_is_exported(self):
        self.assertTrue(callable(lims.post_to_senaite))

    def test_session_is_exported(self):
        self.assertTrue(callable(lims.Session))

    def test_api_base_url_constant(self):
        self.assertEqual(lims.API_BASE_URL, "@@API/senaite/v1")
