"""A tiny router over http.server.

Views are pure functions `view(req) -> Response`, so every page can be
tested without a socket. `dispatch(req)` is the whole request lifecycle:
match a route, call the view, turn a ValueError into an error banner (never
a traceback), and hand anything else to a 500 that logs and says little.
"""
import re
import sys
import traceback
from collections import namedtuple
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import html

STATIC = Path(__file__).resolve().parent / "static"

Request = namedtuple("Request", "method path params form args store")


class Response:
    def __init__(self, body="", status=200, location=None,
                 content_type="text/html; charset=utf-8", cache=None):
        self.body = body
        self.status = status
        self.location = location
        self.content_type = content_type
        self.cache = cache          # Cache-Control, for the font files


ROUTES = []       # (method, compiled pattern, view)


def route(method, pattern):
    """Register a view; a later registration for the same route wins."""
    def deco(view):
        ROUTES[:] = [r for r in ROUTES
                     if not (r[0] == method and r[1].pattern == pattern)]
        ROUTES.append((method, re.compile(pattern), view))
        return view
    return deco


def redirect(path, msg=None, kind="ok"):
    """303 to a same-site path, carrying a banner in the query string."""
    path = (path or "/").replace("\r", "").replace("\n", "")
    if not path.startswith("/") or path.startswith("//"):
        path = "/"
    # the banner rides in the query, so it must go before any #fragment —
    # a browser never sends the fragment, and a banner hidden in it is a
    # refusal the owner never sees
    path, _, frag = path.partition("#")
    if msg:
        sep = "&" if "?" in path else "?"
        path = f"{path}{sep}msg={quote(msg)}&kind={kind}"
    if frag:
        path = f"{path}#{frag}"
    return Response("", 303, location=path)


def page(title, body, req, active="/"):
    """A rendered page, with any ?msg= banner the redirect carried."""
    return Response(html.page(title, body, active, req.params.get("msg"),
                              req.params.get("kind", "ok")))


def dispatch(req):
    for method, pat, view in ROUTES:
        if method != req.method:
            continue
        m = pat.fullmatch(req.path)
        if m:
            try:
                return view(req._replace(args=m.groups()))
            except ValueError as e:
                # a number the owner typed that the math refused — say so,
                # on a page, with the banner; never a traceback
                return Response(html.page("Hmm", "", "/", str(e), "err"))
    return Response(html.page("Not found",
                              f"<p>Nothing lives at {html.esc(req.path)}.</p>",
                              "/"), 404)


class Handler(BaseHTTPRequestHandler):
    store = None          # set by make_server
    MAX_FORM_BYTES = 200_000

    def log_message(self, fmt, *args):
        pass

    def _query(self):
        # keep blanks: a cleared ABV field means "set by OG", not "default"
        return {k: v[0] for k, v in
                parse_qs(urlparse(self.path).query,
                         keep_blank_values=True).items()}

    def _form(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > self.MAX_FORM_BYTES:
            raise ValueError("that form is too big to be a form")
        body = self.rfile.read(length).decode()
        return {k: v[0] for k, v in
                parse_qs(body, keep_blank_values=True).items()}

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        host = self.headers.get("Host") or ""
        return origin in (f"http://{host}", f"https://{host}")

    def _handle(self, method):
        try:
            path = urlparse(self.path).path
            form = self._form() if method == "POST" else {}
            if method == "POST" and not self._origin_ok():
                resp = Response(html.page("Refused", "<p>Cross-site form "
                                          "posts are refused.</p>", "/"), 403)
            else:
                resp = dispatch(Request(method, path, self._query(), form, (),
                                        self.store))
        except Exception:
            sys.stderr.write(traceback.format_exc())
            sys.stderr.flush()
            resp = Response(html.page("Error", "<p>Something went wrong on "
                                      "the server — the details are in the "
                                      "terminal it runs in.</p>", "/"), 500)
        body = (resp.body if isinstance(resp.body, bytes)
                else resp.body.encode())
        self.send_response(resp.status)
        if resp.location:
            self.send_header("Location", resp.location)
        if resp.cache:
            self.send_header("Cache-Control", resp.cache)
        self.send_header("Content-Type", resp.content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


def make_server(store=None, host="127.0.0.1", port=8765):
    handler = type("BoundHandler", (Handler,), {"store": store})
    return ThreadingHTTPServer((host, port), handler)


# --- the vendored display faces --------------------------------------------
# Served from the app itself so the cellar keeps its typography with no wifi.
# Two files, one route each, immutable — the only static surface there is.
FONT_CSS = """
@font-face { font-family:"Caprasimo"; font-style:normal; font-weight:400;
  font-display:swap; src:url(/static/caprasimo-400.woff2) format("woff2"); }
@font-face { font-family:"Figtree"; font-style:normal; font-weight:400 700;
  font-display:swap; src:url(/static/figtree.woff2) format("woff2"); }
"""


@route("GET", "/fonts.css")
def fonts_css(req):
    return Response(FONT_CSS, content_type="text/css; charset=utf-8",
                    cache="max-age=31536000, immutable")


@route("GET", r"/static/([a-z0-9-]+\.woff2)")
def static_font(req):
    path = STATIC / req.args[0]
    if not path.exists():
        return Response("not found", 404, content_type="text/plain")
    return Response(path.read_bytes(), content_type="font/woff2",
                    cache="max-age=31536000, immutable")


# --- views register their routes on import ---------------------------------
from . import (views_today, views_design, views_recipes,  # noqa: E402,F401
               views_must, views_batches, views_vessels,  # noqa: F401
               views_ttb, views_documents)  # noqa: F401
