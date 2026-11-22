import { describe, expect, it, vi } from "vitest";
import { FakePlayer } from "./FakePlayer";

const tracks = [
  { id: "a", durationMs: 10_000 },
  { id: "b", durationMs: 5_000 },
];

async function loaded(options = {}) {
  const p = new FakePlayer(tracks, { autoTick: false, ...options });
  await p.loadAlbum();
  return p;
}

describe("FakePlayer", () => {
  it("loads paused on the first track", async () => {
    const p = await loaded();
    expect(p.state()).toEqual({
      trackId: "a",
      positionMs: 0,
      durationMs: 10_000,
      playing: false,
      previewOnly: false,
    });
  });

  it("only advances while playing", async () => {
    const p = await loaded();
    p.advance(3_000);
    expect(p.state().positionMs).toBe(0);
    await p.play();
    p.advance(3_000);
    expect(p.state().positionMs).toBe(3_000);
  });

  it("plays through both tracks and stops at the end", async () => {
    const p = await loaded();
    const seen: (string | null)[] = [];
    p.on("track", () => seen.push(p.state().trackId));
    await p.play();
    p.advance(12_000);
    expect(p.state()).toMatchObject({ trackId: "b", positionMs: 2_000, playing: true });
    p.advance(10_000);
    expect(p.state()).toMatchObject({ trackId: "b", positionMs: 5_000, playing: false });
    expect(seen).toEqual(["b"]);
  });

  it("carries leftover time across a track boundary", async () => {
    const p = await loaded();
    await p.play();
    p.advance(10_000 + 1_500);
    expect(p.state()).toMatchObject({ trackId: "b", positionMs: 1_500 });
  });

  it("seeks within the track and clamps to its length", async () => {
    const p = await loaded();
    await p.seek(4_000);
    expect(p.state().positionMs).toBe(4_000);
    await p.seek(99_000);
    expect(p.state().positionMs).toBe(10_000);
    await p.seek(-5);
    expect(p.state().positionMs).toBe(0);
  });

  it("playTrack jumps to a track and starts playing", async () => {
    const p = await loaded();
    await p.playTrack("b");
    expect(p.state()).toMatchObject({ trackId: "b", positionMs: 0, playing: true });
    await expect(p.playTrack("zzz")).rejects.toThrow();
  });

  it("restarts the album when play is pressed after the end", async () => {
    const p = await loaded();
    await p.play();
    p.advance(60_000);
    expect(p.state().playing).toBe(false);
    await p.play();
    expect(p.state()).toMatchObject({ trackId: "a", positionMs: 0, playing: true });
  });

  it("emits time, track and state events and can unsubscribe", async () => {
    const p = await loaded();
    const time = vi.fn();
    const state = vi.fn();
    const off = p.on("time", time);
    p.on("state", state);
    await p.play();
    expect(state).toHaveBeenCalledTimes(1);
    p.advance(1_000);
    expect(time).toHaveBeenCalledTimes(1);
    off();
    p.advance(1_000);
    expect(time).toHaveBeenCalledTimes(1);
    await p.pause();
    expect(state).toHaveBeenCalledTimes(2);
  });

  it("can simulate a preview-only listener", async () => {
    const p = await loaded({ previewOnly: true });
    expect(p.state().previewOnly).toBe(true);
  });

  it("drives itself with a timer when autoTick is on", async () => {
    vi.useFakeTimers();
    try {
      const p = new FakePlayer(tracks);
      await p.loadAlbum();
      await p.play();
      vi.advanceTimersByTime(2_000);
      expect(p.state().positionMs).toBeGreaterThanOrEqual(1_750);
      p.dispose();
    } finally {
      vi.useRealTimers();
    }
  });
});
