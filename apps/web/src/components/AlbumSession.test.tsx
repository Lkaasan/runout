// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { AlbumDetail, Claim, TrackDetail } from "@/api/client";
import { AlbumSession } from "./AlbumSession";

beforeEach(() => {
  try {
    localStorage.clear();
  } catch {
    // jsdom without storage: the panel copes.
  }
});
afterEach(cleanup);

function claim(id: number, body: string, type: Claim["type"] = "fact"): Claim {
  return {
    id,
    subject_type: "track",
    subject_id: 1,
    type,
    body,
    body_long: null,
    phase: "during",
    depth: "listen",
    author: null,
    confidence: null,
    sources: [],
  };
}

const album = {
  slug: "x",
  title: "Knock Knock",
  artist: "Smog",
  release_date: "1999-01-12",
  artwork_url: null,
  apple_music_id: null,
  tracks: [
    { number: 1, disc: 1, title: "Held", duration_ms: 242_000, apple_music_id: null },
    { number: 2, disc: 1, title: "River Guard", duration_ms: 382_000, apple_music_id: null },
  ],
  credits: [{ person: "Jim O'Rourke", role: "producer" }],
  before: [claim(100, "Recorded in ten days.")],
  after: [],
} as unknown as AlbumDetail;

const details = [
  {
    number: 1,
    claims: [claim(1, "Held was the first single.")],
    moments: [],
    credits: [],
    links: [],
  },
  {
    number: 2,
    claims: [claim(2, "River Guard was written on a drive.")],
    moments: [{ start_ms: 134_000, end_ms: null, claim: claim(3, "The drums come in halfway.") }],
    credits: [],
    links: [],
  },
] as unknown as TrackDetail[];

describe("AlbumSession", () => {
  it("opens on the album overview with the tracklist beside it", () => {
    render(<AlbumSession album={album} details={details} />);
    expect(screen.getByText("Recorded in ten days.")).toBeTruthy();
    expect(screen.queryByRole("tab", { name: "Meaning" })).toBeNull();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("shows what we know about a song when it is picked", () => {
    render(<AlbumSession album={album} details={details} />);
    fireEvent.click(screen.getByRole("button", { name: /River Guard/ }));
    expect(screen.getByText("River Guard was written on a drive.")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Meaning", selected: true })).toBeTruthy();
    expect(screen.getByRole("button", { name: /River Guard/ }).getAttribute("aria-current")).toBe(
      "true",
    );
  });

  it("offers Listen for only on songs that have moments", () => {
    render(<AlbumSession album={album} details={details} />);
    fireEvent.click(screen.getByRole("button", { name: /Held/ }));
    expect(screen.queryByRole("tab", { name: "Listen for" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /River Guard/ }));
    fireEvent.click(screen.getByRole("tab", { name: "Listen for" }));
    expect(screen.getByText("At 2:14")).toBeTruthy();
    expect(screen.getByText("The drums come in halfway.")).toBeTruthy();
  });

  it("returns to the whole album from the song, and from the album title", () => {
    render(<AlbumSession album={album} details={details} />);
    fireEvent.click(screen.getByRole("button", { name: /Held/ }));
    fireEvent.click(screen.getByRole("button", { name: "Whole album" }));
    expect(screen.getByText("Recorded in ten days.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Held/ }));
    fireEvent.click(screen.getByRole("button", { name: "Knock Knock" }));
    expect(screen.getByText("Recorded in ten days.")).toBeTruthy();
  });

  it("opens on a song named in the address", () => {
    render(<AlbumSession album={album} details={details} initialTrackId="1-2" />);
    expect(screen.getByText("River Guard was written on a drive.")).toBeTruthy();
  });

  it("shows how many notes each song has, and nothing about playback", () => {
    render(<AlbumSession album={album} details={details} />);
    const row = screen.getByRole("button", { name: /Held/ });
    expect(within(row).getByTitle("1 notes about this song")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Play/ })).toBeNull();
    expect(screen.queryByRole("region", { name: "Player" })).toBeNull();
  });
});
