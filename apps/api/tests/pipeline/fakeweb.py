"""A tiny fake of the parts of Wikipedia and MusicBrainz the collectors use. No network."""

import json

import httpx

ARTIST = "Pink Floyd"

ARTICLES = {
    "Animals (Pink Floyd album)": (
        "Animals is the tenth studio album by the English rock band Pink Floyd, released on "
        "21 January 1977. The cover shows a pig over Battersea Power Station."
    ),
    "Dogs (Pink Floyd song)": '"Dogs" is a song by English rock band Pink Floyd, from Animals.',
    "Sheep (Pink Floyd song)": '"Sheep" is a song by the English rock band Pink Floyd.',
    # The animal, linked from the album article as plain "Sheep": must be rejected.
    "Sheep": "Sheep are domesticated ruminant mammals kept as livestock.",
    "Pigs on the Wing": "Pigs on the Wing is a two-part song by Pink Floyd, from Animals.",
}

LINKS = {
    "Animals (Pink Floyd album)": [
        "Sheep",
        "Sheep (Pink Floyd song)",
        "Dogs (Pink Floyd song)",
        "Pigs on the Wing",
        "Battersea Power Station",
    ]
}

EXTLINKS = {
    "Animals (Pink Floyd album)": [f"http://example.com/ref{i}" for i in range(3)],
}

GROUP_ID = "20c77fb4-1c9f-33c8-9d7e-c4977f11e847"
RELEASE_ID = "294992a7-0000-0000-0000-000000000001"


class FakeWeb:
    def __init__(self, *, busy_musicbrainz: int = 0, musicbrainz_down: bool = False):
        self.calls: list[str] = []
        self.busy_musicbrainz = busy_musicbrainz
        self.musicbrainz_down = musicbrainz_down
        self.client = httpx.Client(transport=httpx.MockTransport(self._handle))

    # ---- routing ---------------------------------------------------------------------------

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        host = request.url.host
        if host.endswith("wikipedia.org"):
            return self._wikipedia(request)
        if host == "musicbrainz.org":
            return self._musicbrainz(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        return httpx.Response(200, text="ok")

    def _wikipedia(self, request: httpx.Request) -> httpx.Response:
        q = dict(request.url.params)
        if q.get("list") == "search":
            hits = [{"title": "Animals (Pink Floyd album)"}, {"title": "Sheep (Pink Floyd song)"}]
            return self._json({"query": {"search": hits}})
        title = q.get("titles", "")
        if "extracts" in q.get("prop", ""):
            if title not in ARTICLES:
                return self._json({"query": {"pages": [{"title": title, "missing": True}]}})
            page = {
                "pageid": 1,
                "title": title,
                "extract": ARTICLES[title],
                "revisions": [{"revid": 42, "timestamp": "2026-01-01T00:00:00Z"}],
            }
            return self._json({"query": {"pages": [page]}})
        if q.get("prop") == "extlinks":
            urls = EXTLINKS.get(title, [])
            # Two result pages, to exercise `continue`.
            if "eloffset" not in q and len(urls) > 1:
                body = {
                    "continue": {"eloffset": 1, "continue": "||"},
                    "query": {"pages": [{"title": title, "extlinks": [{"url": urls[0]}]}]},
                }
            else:
                rest = urls[1:] if "eloffset" in q else urls
                body = {
                    "query": {"pages": [{"title": title, "extlinks": [{"url": u} for u in rest]}]}
                }
            return self._json(body)
        if q.get("prop") == "links":
            links = [{"title": t} for t in LINKS.get(title, [])]
            return self._json({"query": {"pages": [{"title": title, "links": links}]}})
        return httpx.Response(400, text="unexpected")

    def _musicbrainz(self, request: httpx.Request) -> httpx.Response:
        if self.musicbrainz_down:
            return httpx.Response(503, text='{"error": "The MusicBrainz web server is busy."}')
        if self.busy_musicbrainz > 0:
            self.busy_musicbrainz -= 1
            return httpx.Response(503, text='{"error": "The MusicBrainz web server is busy."}')
        path = request.url.path
        if path == "/ws/2/release-group":
            groups = [
                {"id": "wrong", "title": "Animals (Live)", "score": 100},
                {
                    "id": GROUP_ID,
                    "title": "Animals",
                    "score": 90,
                    "first-release-date": "1977-01-23",
                },
            ]
            return self._json({"release-groups": groups})
        if path == f"/ws/2/release-group/{GROUP_ID}":
            releases = [
                {"id": "later", "status": "Official", "date": "1994"},
                {"id": RELEASE_ID, "status": "Official", "date": "1977"},
                {"id": "bootleg", "status": "Bootleg", "date": "1970"},
            ]
            return self._json({"id": GROUP_ID, "releases": releases})
        if path == f"/ws/2/release/{RELEASE_ID}":
            return self._json(
                {
                    "title": "Animals",
                    "date": "1977",
                    "country": "GB",
                    "label-info": [{"label": {"name": "Harvest"}}],
                    "artist-credit": [{"artist": {"id": "artist-1", "name": ARTIST}}],
                    "relations": [
                        {"type": "design", "attributes": [], "artist": {"name": "Storm Thorgerson"}}
                    ],
                    "media": [
                        {
                            "tracks": [
                                {
                                    "number": "1",
                                    "title": "Dogs",
                                    "length": 1019666,
                                    "recording": {
                                        "id": "rec-1",
                                        "isrcs": ["GBDJQ7700005"],
                                        "relations": [
                                            {
                                                "type": "instrument",
                                                "attributes": ["guitar"],
                                                "artist": {"name": "David Gilmour"},
                                            }
                                        ],
                                    },
                                }
                            ]
                        }
                    ],
                }
            )
        return httpx.Response(404, text="{}")

    @staticmethod
    def _json(body: dict) -> httpx.Response:
        return httpx.Response(200, text=json.dumps(body))

    # ---- helpers for assertions --------------------------------------------------------------

    def calls_to(self, host: str) -> list[str]:
        return [c for c in self.calls if httpx.URL(c).host.endswith(host)]
