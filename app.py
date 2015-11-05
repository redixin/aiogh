import dbm
import asyncio
from aiohttp import web
import configparser
import sys

from aiogh import github


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
        db_dir = cfg["db_dir"]
        self._tokens = dbm.open(os.path.join(db_dir, "tokens.db") "cs")
        self._projects = dbm.open(os.path.join(db_dir, "projects.db") "cs")
        self._oauth = github.OAuth(cfg["client_id"], cfg["client_secret"])

    @asyncio.coroutine
    def setup(self, request):
        return web.Response(body=b"""<form action=authorize method=post />
                <input name=ok value=ok type=hidden>
                <input type=submit value=Register></input></form>""")

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
        self._tokens[user_data["id"]] = c.token
        repos_data = yield from c.get("user/repos", affiliation="owner")
        repos = []
        for repo in repos_data:
            repo_id = str(repo["id"])
            repos.append((
                repo_id,
                repo["full_name"],
                repo["description"],
                repo_id in self._db,
            ))
        return web.Response(body=repr(repos).encode("ascii"))

    @asyncio.coroutine
    def run(self):
        self.app = web.Application()
        self.app.router.add_route('GET', '/setup', self.setup)
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
