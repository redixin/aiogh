import asyncio
from urllib import parse
import random
import string
import json

import aiohttp

REQ_ACCESS_URL = "https://github.com/login/oauth/authorize"
REQ_TOKEN_URL = "https://github.com/login/oauth/access_token"
API_URL = "https://api.github.com/"


class Client:
    """Represent github api client.

    Usage:
        from aiogh import github
        token = "token"  # get token somehow
        c = github.Client(token)
        data = c.get("user")
        email = data["email"]

    """

    def __init__(self, token, scopes=None):
        self.token = token
        self._scopes = scopes

    @asyncio.coroutine
    def get(self, uri, **params):
        headers = {
            "Accept": "application/json",
            "Authorization": "token " + self.token,
        }
        resp = yield from aiohttp.get(API_URL + uri,
                                      params=params,
                                      headers=headers)
        data = yield from resp.text()
        if resp.headers["content-type"].startswith("application/json"):
            data = json.loads(data)
        return data


class Oauth:

    def __init__(self, client_id, client_secret):
        """Init github oauth app.

        :param string client_id: Client ID
        :param string client_secret: Client Secret
        """
        self._client_id = client_id
        self._client_secret = client_secret
        self._requested_scopes = {}

    def generate_request_url(self, scopes: tuple):
        """Generate url and bind a callback.

        :param scopes: github access scopes
                       (https://developer.github.com/v3/oauth/#scopes)
        :param callback: callback to be called when user authorize request
                         (may be coroutine)
        """
        state = ''.join(random.sample(string.ascii_letters, 16))
        self._requested_scopes[state] = scopes
        qs = parse.urlencode({
            "client_id": self._client_id,
            "scope": ",".join(scopes),
            "state": state,
        })
        return "%s?%s" % (REQ_ACCESS_URL, qs)

    @asyncio.coroutine
    def oauth(self, code, state):
        """Handler for Authorization callback URL.

        :param string code:
        :param string state:
        :return: Client instance
        """
        scopes = self._requested_scopes.pop(state)
        data = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "code": code,
            "state": state,
        }
        headers = {
            "accept": "application/json"
        }
        response = yield from aiohttp.post(REQ_TOKEN_URL,
                                           data=data,
                                           headers=headers)
        data = json.loads((yield from response.text()))
        return Client(data["access_token"], scopes)
