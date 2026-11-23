import { describe, expect, it } from "vitest";
import { trackKey, trackKeyFromParam } from "./tracks";

const tracks = [
  { disc: 1, number: 1 },
  { disc: 1, number: 2 },
  { disc: 2, number: 1 },
];

describe("trackKey", () => {
  it("combines disc and number", () => {
    expect(trackKey({ disc: 2, number: 5 })).toBe("2-5");
  });
});

describe("trackKeyFromParam", () => {
  it("finds a track by its number", () => {
    expect(trackKeyFromParam(tracks, "2")).toBe("1-2");
  });
  it("prefers the first disc when numbers repeat", () => {
    expect(trackKeyFromParam(tracks, "1")).toBe("1-1");
  });
  it("uses the first value if the parameter is repeated", () => {
    expect(trackKeyFromParam(tracks, ["2", "1"])).toBe("1-2");
  });
  it("ignores missing, unknown and malformed values", () => {
    expect(trackKeyFromParam(tracks, undefined)).toBeNull();
    expect(trackKeyFromParam(tracks, "")).toBeNull();
    expect(trackKeyFromParam(tracks, "99")).toBeNull();
    expect(trackKeyFromParam(tracks, "two")).toBeNull();
    expect(trackKeyFromParam(tracks, "1.5")).toBeNull();
  });
});
