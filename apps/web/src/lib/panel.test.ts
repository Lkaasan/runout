import { describe, expect, it } from "vitest";
import { availableTabs, nextTab, resolveTab } from "./panel";

describe("resolveTab", () => {
  it("keeps a remembered tab that still exists", () => {
    expect(resolveTab("listen", ["meaning", "listen"])).toBe("listen");
  });
  it("falls back to the first tab", () => {
    expect(resolveTab("gone", ["meaning", "album"])).toBe("meaning");
    expect(resolveTab(null, ["album"])).toBe("album");
    expect(resolveTab(null, [])).toBeNull();
  });
  it("forgets tabs from the old player layout", () => {
    expect(resolveTab("now", availableTabs(true))).toBe("meaning");
  });
});

describe("nextTab", () => {
  const tabs = ["meaning", "listen", "album"];
  it("moves with arrow keys and wraps", () => {
    expect(nextTab(tabs, "meaning", "ArrowRight")).toBe("listen");
    expect(nextTab(tabs, "album", "ArrowRight")).toBe("meaning");
    expect(nextTab(tabs, "meaning", "ArrowLeft")).toBe("album");
  });
  it("jumps with Home and End and ignores other keys", () => {
    expect(nextTab(tabs, "listen", "Home")).toBe("meaning");
    expect(nextTab(tabs, "listen", "End")).toBe("album");
    expect(nextTab(tabs, "listen", "a")).toBe("listen");
  });
});

describe("availableTabs", () => {
  it("offers only the Album tab when no song is selected", () => {
    expect(availableTabs(false)).toEqual(["album"]);
    expect(availableTabs(false, true)).toEqual(["album"]);
  });
  it("offers Meaning and Album for a song", () => {
    expect(availableTabs(true)).toEqual(["meaning", "album"]);
  });
  it("adds Listen for only when the song has moments", () => {
    expect(availableTabs(true, true)).toEqual(["meaning", "listen", "album"]);
  });
});
