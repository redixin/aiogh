import asyncio
from urllib import parse
import random
import string
import json

import aiohttp
from . import exceptions


REQ_ACCESS_URL = "https://github.com/login/oauth/authorize"
REQ_TOKEN_URL = "https://github.com/login/oauth/access_token"
API_URL = "https://api.github.com/"


class Response:
    """Wrapper class for aiohttp response"""

    def __init__(self, response):
        self._response = response

    @property
    def status(self):
        return self._response.status

    @asyncio.coroutine
    def json(self):
        return (yield from self._response.json())


class Client:
    """Represent github api client.

    Usage:
        from aiogh import github
        token = "token"  # get token somehow
        c = github.Client(token)
        data = c.get("user")
        email = data["email"]

    """

    def __init__(self, token=None, scopes=None):
        self.token = token
        self.scopes = scopes
        self.headers = {
            "Accept": "application/json",
        }
        if token:
            self.headers.update({"Authorization": "token " + token})

    @asyncio.coroutine
    def get(self, uri, full_response=False, **params):
        resp = yield from aiohttp.get(API_URL + uri,
                                      params=params,
                                      headers=self.headers)
        if 200 > resp.status > 300:
            raise exceptions.HttpError(Response(resp))
        if full_response:
            return Response(resp)
        return (yield from resp.json())


class OAuth:
    """Handle OAuth github protocol.

    Usage:
        from aiogh import github

        ...
        # somewhere in your app
        self.oauth = github.Oauth("my_client_id", "secret")
        ...

        ...
        # somewhere in web page handler
        url = self.oauth.generate_request_url(("put", "scopes", "here"))
        # make user open it
        return http_redirect(url)
        ...

        ...
        # somewhere in oauth callback handler
        code = request.GET["code"]
        state = request.GET["state"]
        client = oauth.oauth(code, state)
        # save user token if needed
        self.db.save_token(client.token)
        ...

    """

    def __init__(self, client_id, client_secret):
        """Init github oauth app.

        :param string client_id: Client ID
        :param string client_secret: Client Secret
        """
        self._client_id = client_id
        self._client_secret = client_secret
        self._requested_scopes = {}

    def generate_request_url(self, scopes: tuple):
        """Generate OAuth request url.

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

        'code' and 'state' are GET variables given by github

        :param string code:
        :param string state:
        :return: Client instance
        :raises: exceptions.GithubException
        """
        try:
            scopes = self._requested_scopes.pop(state)
        except KeyError:
            raise exceptions.UnknownState(state)
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
        data = yield from response.json()
        return Client(data["access_token"], scopes)
