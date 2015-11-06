import dbm
import asyncio
from aiohttp import web
import configparser
import sys
import os.path
import json

from aiogh import github

from aiohttp_session import get_session, session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage


@asyncio.coroutine
def req_data(request):
    print(request)
    print(request.headers)
    data = yield from request.post()
    print(data.items())


class RallyCI:

    def __init__(self, loop, cfgfile):
        self.loop = loop
        cfg = configparser.ConfigParser()
        cfg.read(cfgfile)
        cfg = cfg["github"]
        self._webhook_secret = cfg["webhook_secret"]
        self._session_key = cfg["session_key"].encode('ascii')
        db_dir = cfg["db_dir"]
        self._tokens = dbm.open(os.path.join(db_dir, "tokens.db"), "cs")
        self._repos = dbm.open(os.path.join(db_dir, "repos.db"), "cs")
        self._oauth = github.OAuth(cfg["client_id"], cfg["client_secret"])

    @asyncio.coroutine
    def home(self, request):
        session = yield from get_session(request)
        token = self._tokens.get(session.get("uid", ""), b"")
        c = github.Client(token.decode('ascii'))
        if not c.token:
            return web.Response(body=b"""<form action=authorize method=post />
                    <input name=ok value=ok type=hidden>
                    <input type=submit value=Register></input></form>""")

        repos_data = yield from c.get("user/repos", affiliation="owner")
        repos = []
        for repo in repos_data:
            repo_id = str(repo["id"])
            repo_data = self._repos.get(repo_id)
            if not repo_data:
                repo_data = [repo["full_name"], None]
                self._repos[repo_id] = json.dumps(repo_data)
            else:
                repo_data = json.loads(repo_data.decode('ascii'))
            repos.append((
                repo_id,
                repo["name"],
                repo["full_name"],
                repo["description"],
                repo_data[1],
            ))
        with open("app.html", "r") as app:
            app = app.read()
        app = app % json.dumps(repos)
        return web.Response(body=app.encode("utf8"))

    @asyncio.coroutine
    def setup(self, request):
        session = yield from get_session(request)
        token = self._tokens.get(session.get("uid", ""))
        if not token:
            return web.HTTPUnauthorized()
        c = github.Client(token.decode('ascii'))
        yield from request.post()
        repo_data = json.loads(self._repos.get(
            request.POST["id"]).decode('ascii'))
        owner, repo = repo_data[0].split('/')
        res = yield from c.get("/repos/:owner/:repo/hooks", owner, repo)
        if len(res) == 0:
            config = {
                "url": "https://eyein.tk/webhook",
                "secret": self._webhook_secret,
            }
            events = ["push", "pull_request"]
            res = yield from c.post("/repos/:owner/:repo/hooks", owner, repo,
                                    name="web", active=True, config=config,
                                    events=events)
            print(res)
        else:
            print(res)

    @asyncio.coroutine
    def authorize(self, request):
        yield from req_data(request)
        url = self._oauth.generate_request_url(("repo:status",
                                                "write:repo_hook"))
        return web.HTTPFound(url)

    @asyncio.coroutine
    def oauth(self, request):
        yield from req_data(request)
        c = yield from self._oauth.oauth(request.GET["code"],
                                         request.GET["state"])
        user_data = yield from c.get("user")
        uid = hex(user_data["id"])[2:]
        self._tokens[uid] = c.token
        session = yield from get_session(request)
        session["uid"] = uid
        return web.HTTPFound("home")

    @asyncio.coroutine
    def webhook(self, request):
        print(request)
        yield from request.post()
        print(request.POST)
        return web.Response(body=b"ok")

    @asyncio.coroutine
    def run(self):
        sm = session_middleware(EncryptedCookieStorage(self._session_key))
        self.app = web.Application(middlewares=[sm])
        self.app.router.add_route('POST', '/webhook', self.webhook)
        self.app.router.add_route('POST', '/setup', self.setup)
        self.app.router.add_route('GET', '/home', self.home)
        self.app.router.add_route('POST', '/authorize', self.authorize)
        self.app.router.add_route('GET', '/oauth', self.oauth)
        self.handler = self.app.make_handler()
        self.srv = yield from self.loop.create_server(self.handler,
                                                      '127.0.0.1', 8082)
        yield from self.srv.wait_closed()

    @asyncio.coroutine
    def cleanup(self):
        yield from self.handler.finish_connections(1.0)
        self.srv.close()
        yield from self.srv.wait_closed()
        yield from self.app.finish()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    rci = RallyCI(loop, "/etc/rci.ini")
    try:
        loop.run_until_complete(rci.run())
    except KeyboardInterrupt:
        sys.exit(0)
    finally:
        loop.run_until_complete(rci.cleanup())
    sys.exit(1)
