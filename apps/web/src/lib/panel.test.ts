import { describe, expect, it } from "vitest";
import { availableTabs, isBrowsing, nextTab, resolveActiveTrack, resolveTab } from "./panel";

describe("resolveActiveTrack", () => {
  it("follows the playing song when nothing is pinned", () => {
    expect(resolveActiveTrack(null, "a")).toBe("a");
    expect(resolveActiveTrack(null, null)).toBeNull();
  });
  it("shows the pinned song while another plays", () => {
    expect(resolveActiveTrack("b", "a")).toBe("b");
  });
});

describe("isBrowsing", () => {
  it("is only true when pinned to a different song", () => {
    expect(isBrowsing(null, "a")).toBe(false);
    expect(isBrowsing("a", "a")).toBe(false);
    expect(isBrowsing("b", "a")).toBe(true);
    expect(isBrowsing("b", null)).toBe(true);
  });
});

describe("resolveTab", () => {
  it("keeps a remembered tab that still exists", () => {
    expect(resolveTab("lyrics", ["now", "lyrics"])).toBe("lyrics");
  });
  it("falls back to the first tab", () => {
    expect(resolveTab("gone", ["now", "lyrics"])).toBe("now");
    expect(resolveTab(null, ["now"])).toBe("now");
    expect(resolveTab(null, [])).toBeNull();
  });
});

describe("nextTab", () => {
  const tabs = ["now", "meaning", "lyrics"];
  it("moves with arrow keys and wraps", () => {
    expect(nextTab(tabs, "now", "ArrowRight")).toBe("meaning");
    expect(nextTab(tabs, "lyrics", "ArrowRight")).toBe("now");
    expect(nextTab(tabs, "now", "ArrowLeft")).toBe("lyrics");
  });
  it("jumps with Home and End and ignores other keys", () => {
    expect(nextTab(tabs, "meaning", "Home")).toBe("now");
    expect(nextTab(tabs, "meaning", "End")).toBe("lyrics");
    expect(nextTab(tabs, "meaning", "a")).toBe("meaning");
  });
});

describe("availableTabs", () => {
  it("offers only the Album tab when no song is active", () => {
    expect(availableTabs(false)).toEqual(["album"]);
  });
  it("adds the song tabs when a song is active", () => {
    expect(availableTabs(true)).toEqual(["now", "meaning", "album"]);
  });
  it("falls back to the first tab when a remembered song tab disappears", () => {
    expect(resolveTab("meaning", availableTabs(false))).toBe("album");
  });
});
