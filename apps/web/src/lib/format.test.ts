import { describe, expect, it } from "vitest";
import { formatMs } from "./format";

describe("formatMs", () => {
  it("formats minutes and seconds", () => {
    expect(formatMs(134_000)).toBe("2:14");
    expect(formatMs(5_000)).toBe("0:05");
  });
  it("formats hours", () => {
    expect(formatMs(3_723_000)).toBe("1:02:03");
  });
});
