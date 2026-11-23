// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AlbumCover } from "./AlbumCover";

afterEach(cleanup);

describe("AlbumCover", () => {
  it("shows the image with a useful description", () => {
    render(<AlbumCover url="https://img.example/animals.jpg" title="Animals" />);
    const img = screen.getByRole("img", { name: "Animals album cover" });
    expect(img.getAttribute("src")).toBe("https://img.example/animals.jpg");
    expect(img.getAttribute("referrerpolicy")).toBe("no-referrer");
  });

  it("falls back to a placeholder when there is no cover", () => {
    render(<AlbumCover url={null} title="Placeholder Album" />);
    expect(screen.getByRole("img", { name: /no cover available/ })).toBeTruthy();
    expect(document.querySelector("img")).toBeNull();
  });

  it("falls back to a placeholder when the image fails to load", () => {
    render(<AlbumCover url="https://img.example/gone.jpg" title="Animals" />);
    fireEvent.error(screen.getByRole("img", { name: "Animals album cover" }));
    expect(screen.getByRole("img", { name: /no cover available/ })).toBeTruthy();
  });

  it("tries a new address after a failure on the old one", () => {
    const { rerender } = render(<AlbumCover url="https://img.example/gone.jpg" title="Animals" />);
    fireEvent.error(screen.getByRole("img", { name: "Animals album cover" }));
    rerender(<AlbumCover url="https://img.example/new.jpg" title="Animals" />);
    expect(screen.getByRole("img", { name: "Animals album cover" })).toBeTruthy();
  });
});
