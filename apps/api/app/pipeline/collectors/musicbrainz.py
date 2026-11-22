"""MusicBrainz: ids, track lengths, ISRCs and the credits the community has entered.

The release is rendered to plain text so later stages can quote and verify it like any page. The
structured values (ids, lengths, ISRCs) are kept in `meta` for filling `musicbrainz_id`,
`isrc` and `duration` in the seed, which must still be reviewed by a human.
"""

import json

from app.pipeline.http import Fetcher, NotFound
from app.pipeline.models import Page

WS = "https://musicbrainz.org/ws/2"


def _mmss(ms: int | None) -> str:
    if not ms:
        return "?"
    total = round(ms / 1000)
    return f"{total // 60}:{total % 60:02d}"


class MusicBrainzCollector:
    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    def collect(self, album: str, artist: str) -> tuple[list[Page], list[str]]:
        group = self._find_release_group(album, artist)
        if group is None:
            return [], [f"No MusicBrainz release group found for '{album}' by {artist}."]
        release_id = self._earliest_official_release(group["id"])
        if release_id is None:
            return [], [f"MusicBrainz has no official release for '{album}'."]

        try:
            record = self.fetcher.fetch(
                f"{WS}/release/{release_id}",
                {
                    "inc": "recordings artist-credits artist-rels recording-rels isrcs labels",
                    "fmt": "json",
                },
            )
        except NotFound:
            return [], [f"MusicBrainz release {release_id} not found."]
        release = json.loads(record.text)
        text, tracks = self._render(release, group)
        page = Page(
            url=f"https://musicbrainz.org/release/{release_id}",
            title=f"{release['title']} (MusicBrainz release)",
            kind="musicbrainz",
            fetched_at=record.fetched_at,
            text=text,
            meta={
                "release_group_id": group["id"],
                "release_id": release_id,
                "artist_ids": sorted(
                    {c["artist"]["id"] for c in release.get("artist-credit", []) if "artist" in c}
                ),
                "tracks": tracks,
            },
        )
        return [page], []

    # ---- steps -----------------------------------------------------------------------------

    def _find_release_group(self, album: str, artist: str) -> dict | None:
        query = f'releasegroup:"{album}" AND artist:"{artist}" AND primarytype:album'
        data = self.fetcher.get_json(
            f"{WS}/release-group", {"query": query, "fmt": "json", "limit": 5}
        )
        groups = data.get("release-groups", [])
        exact = [g for g in groups if g["title"].lower() == album.lower()]
        return max(exact or groups, key=lambda g: g.get("score", 0), default=None)

    def _earliest_official_release(self, group_id: str) -> str | None:
        data = self.fetcher.get_json(
            f"{WS}/release-group/{group_id}", {"inc": "releases", "fmt": "json"}
        )
        official = [r for r in data.get("releases", []) if r.get("status") == "Official"]
        official.sort(key=lambda r: (r.get("date") or "9999", r["id"]))
        return official[0]["id"] if official else None

    # ---- rendering -------------------------------------------------------------------------

    def _render(self, release: dict, group: dict) -> tuple[str, list[dict]]:
        labels = ", ".join(
            sorted({li["label"]["name"] for li in release.get("label-info", []) if li.get("label")})
        )
        lines = [
            f"Release: {release['title']} ({release.get('date', 'date unknown')})"
            + (f", label {labels}" if labels else "")
            + f", country {release.get('country', '?')}",
            f"Release group first released: {group.get('first-release-date', 'unknown')}",
        ]
        for rel in release.get("relations", []):
            if "artist" in rel:
                lines.append(f"Credit: {self._relation(rel)}")

        tracks: list[dict] = []
        for medium in release.get("media", []):
            for t in medium.get("tracks", []):
                rec = t.get("recording", {})
                isrcs = sorted(rec.get("isrcs", []))
                lines.append(
                    f"Track {t['number']}: {t['title']} ({_mmss(t.get('length'))})"
                    + (f", ISRC {', '.join(isrcs)}" if isrcs else "")
                )
                for rel in rec.get("relations", []):
                    if "artist" in rel:
                        lines.append(f"Track {t['number']} credit: {self._relation(rel)}")
                tracks.append(
                    {
                        "number": t["number"],
                        "title": t["title"],
                        "length_ms": t.get("length"),
                        "isrcs": isrcs,
                        "recording_id": rec.get("id"),
                    }
                )
        return "\n".join(lines), tracks

    @staticmethod
    def _relation(rel: dict) -> str:
        attrs = ", ".join(rel.get("attributes", []))
        what = rel["type"] + (f" ({attrs})" if attrs else "")
        return f"{what} - {rel['artist']['name']}"
