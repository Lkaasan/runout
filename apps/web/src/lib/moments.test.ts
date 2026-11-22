import { describe, expect, it } from "vitest";
import {
  DEFAULT_MOMENT_MS,
  heardMoments,
  INTRO_MS,
  introVisible,
  visibleMoments,
} from "./moments";

const withEnd = { start_ms: 45_000, end_ms: 60_000 };
const noEnd = { start_ms: 100_000, end_ms: null };

describe("visibleMoments", () => {
  it("appears at start_ms and not before", () => {
    expect(visibleMoments([withEnd], 44_999)).toEqual([]);
    expect(visibleMoments([withEnd], 45_000)).toEqual([withEnd]);
  });

  it("disappears at end_ms", () => {
    expect(visibleMoments([withEnd], 59_999)).toEqual([withEnd]);
    expect(visibleMoments([withEnd], 60_000)).toEqual([]);
  });

  it("falls back to about 12 s when there is no end", () => {
    expect(visibleMoments([noEnd], 100_000 + DEFAULT_MOMENT_MS - 1)).toEqual([noEnd]);
    expect(visibleMoments([noEnd], 100_000 + DEFAULT_MOMENT_MS)).toEqual([]);
  });

  it("is correct after seeking forward and back", () => {
    const moments = [withEnd, noEnd];
    expect(visibleMoments(moments, 50_000)).toEqual([withEnd]);
    expect(visibleMoments(moments, 105_000)).toEqual([noEnd]); // seek forward
    expect(visibleMoments(moments, 10_000)).toEqual([]); // seek back before both
    expect(visibleMoments(moments, 46_000)).toEqual([withEnd]); // and into the first again
  });
});

describe("heardMoments", () => {
  it("lists moments that started and are no longer showing", () => {
    expect(heardMoments([withEnd, noEnd], 30_000)).toEqual([]);
    expect(heardMoments([withEnd, noEnd], 50_000)).toEqual([]);
    expect(heardMoments([withEnd, noEnd], 70_000)).toEqual([withEnd]);
    expect(heardMoments([withEnd, noEnd], 200_000)).toEqual([withEnd, noEnd]);
  });

  it("forgets moments after a seek back", () => {
    expect(heardMoments([withEnd], 10_000)).toEqual([]);
  });
});

describe("introVisible", () => {
  it("shows for the first 8 s of a song", () => {
    expect(introVisible(0, false)).toBe(true);
    expect(introVisible(INTRO_MS - 1, false)).toBe(true);
    expect(introVisible(INTRO_MS, false)).toBe(false);
  });

  it("stays when tapped", () => {
    expect(introVisible(60_000, true)).toBe(true);
  });
});
