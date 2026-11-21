import { describe, expect, it } from "vitest";
import { fetchAlbums } from "./lib-api";

describe("fetchAlbums", () => {
  it("is exported", () => {
    expect(typeof fetchAlbums).toBe("function");
  });
});
