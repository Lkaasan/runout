import { describe, expect, it } from "vitest";
import type { SearchResults } from "@/api/client";
import { moveHighlight, suggestions } from "./search";

const results = {
  query: "smog",
  artists: [{ slug: "smog", name: "Smog", album_count: 1, artwork_url: null }],
  albums: [
    {
      slug: "knock-knock",
      title: "Knock Knock",
      artist: "Smog",
      artist_slug: "smog",
      release_date: null,
      artwork_url: null,
    },
  ],
} as SearchResults;

describe("suggestions", () => {
  it("lists artists before albums with links", () => {
    expect(suggestions(results).map((s) => [s.kind, s.href, s.hint])).toEqual([
      ["artist", "/artist/smog", "1 album"],
      ["album", "/album/knock-knock", "Smog"],
    ]);
  });
});

describe("moveHighlight", () => {
  it("wraps and starts from the right end", () => {
    expect(moveHighlight(-1, 1, 3)).toBe(0);
    expect(moveHighlight(-1, -1, 3)).toBe(2);
    expect(moveHighlight(2, 1, 3)).toBe(0);
    expect(moveHighlight(0, -1, 3)).toBe(2);
    expect(moveHighlight(-1, 1, 0)).toBe(-1);
  });
});
