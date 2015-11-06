import asyncio
import mock
import unittest

from aiogh import github


class FakeClient:
    args = []
    kwargs = []

    def __init__(self, loop, json=None):
        self.loop = loop
        self.json = json

    @asyncio.coroutine
    def post(self, *args, **kwargs):
        self.args.append(args)
        self.kwargs.append(kwargs)
        return mock.Mock(json=self._json)

    @asyncio.coroutine
    def _json(self):
        return self.json


class AsyncTestCase(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.stop()
        del(self.loop)

    def yield_from(self, coro):
        return self.loop.run_until_complete(coro)


class OAuthTestCase(AsyncTestCase):

    @mock.patch("aiogh.github.aiohttp")
    def test_oauth(self, mock_aiohttp):
        fake_client = FakeClient(self.loop, {"access_token": "fake_token"})
        mock_aiohttp.post = fake_client.post
        oauth = github.OAuth("fake_client_id", "fake_secret")
        oauth.generate_request_url(("scope1", "scope2"))
        state = list(oauth._requested_scopes.keys())[0]
        client = self.yield_from(oauth.oauth('fake_code', state))
        self.assertEqual("fake_token", client.token)
        headers = fake_client.kwargs[0]["headers"]
        data = fake_client.kwargs[0]["data"]
        self.assertEqual("application/json", headers.get("accept"))
        self.assertEqual("fake_client_id", data.get("client_id"))
        self.assertEqual("fake_secret", data.get("client_secret"))
        self.assertEqual("fake_code", data.get("code"))
        self.assertEqual(state, data.get("state"))
