import { describe, expect, it } from "vitest";
import { playbackId, toPlaybackTracks } from "./playback";

const base = { disc: 1, number: 2, title: "Two", duration_ms: 90_000, apple_music_id: "123" };

describe("playback helpers", () => {
  it("prefers the Apple Music id, falls back to disc-number", () => {
    expect(playbackId(base)).toBe("123");
    expect(playbackId({ ...base, apple_music_id: null })).toBe("1-2");
  });

  it("maps tracks and fills a missing duration", () => {
    const [a, b] = toPlaybackTracks([base, { ...base, number: 3, duration_ms: null }]);
    expect(a).toEqual({ id: "123", title: "Two", number: 2, durationMs: 90_000 });
    expect(b.durationMs).toBeGreaterThan(0);
  });
});
