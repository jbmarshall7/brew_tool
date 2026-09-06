"""The router: pure dispatch, error banners instead of tracebacks, and one
real HTTP round trip."""
import http.client
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brew import server
from brew.server import Request, dispatch, make_server, route


def get(path, params=None, store=None):
    return dispatch(Request("GET", path, params or {}, {}, (), store))


def post(path, form=None, store=None):
    return dispatch(Request("POST", path, {}, form or {}, (), store))


class DispatchTest(unittest.TestCase):
    def test_home_renders(self):
        r = get("/")
        self.assertEqual(r.status, 200)
        self.assertIn("brew_tool", r.body)
        self.assertIn('<meta name="viewport"', r.body)

    def test_unknown_path_is_404(self):
        r = get("/nowhere")
        self.assertEqual(r.status, 404)
        self.assertIn("Nothing lives at /nowhere", r.body)

    def test_value_error_becomes_a_banner_not_a_traceback(self):
        @route("GET", "/__boom")
        def boom(req):
            raise ValueError("batch volume 'abc' isn't a number")
        try:
            r = get("/__boom")
            self.assertEqual(r.status, 200)
            self.assertIn('class="msg err"', r.body)
            self.assertIn("isn&#x27;t a number", r.body)
            self.assertNotIn("Traceback", r.body)
        finally:
            server.ROUTES[:] = [x for x in server.ROUTES
                                if x[1].pattern != "/__boom"]

    def test_redirect_carries_the_banner_and_stays_on_site(self):
        r = server.redirect("/recipes/x", "Saved it", "ok")
        self.assertEqual(r.status, 303)
        self.assertEqual(r.location, "/recipes/x?msg=Saved%20it&kind=ok")
        self.assertEqual(server.redirect("//evil.example", "x").location[:2],
                         "/?")
        self.assertEqual(server.redirect("http://evil.example").location, "/")
        # the banner goes before any #fragment, or the browser never sends it
        self.assertEqual(
            server.redirect("/recipes/x/must?gal=6#record", "No", "err").location,
            "/recipes/x/must?gal=6&msg=No&kind=err#record")

    def test_banner_from_query(self):
        r = get("/", {"msg": "Hello <cellar>", "kind": "warn"})
        self.assertIn('class="msg warn"', r.body)
        self.assertIn("Hello &lt;cellar&gt;", r.body)


class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = make_server(None, "127.0.0.1", 0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        text = resp.read().decode()
        conn.close()
        return resp, text

    def test_get_home(self):
        resp, text = self.request("GET", "/")
        self.assertEqual(resp.status, 200)
        self.assertIn("brew_tool", text)
        self.assertTrue(resp.getheader("Content-Type").startswith("text/html"))

    def test_blank_query_values_reach_the_view(self):
        resp, text = self.request("GET", "/?gal=6&abv=&og=1.1067")
        self.assertIn('name="abv" type="number" value=""', text)
        self.assertIn("Strength is set by the OG below", text)

    def test_cross_site_post_refused(self):
        resp, _ = self.request(
            "POST", "/", body="a=1",
            headers={"Origin": "http://evil.example",
                     "Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(resp.status, 403)


if __name__ == "__main__":
    unittest.main()
