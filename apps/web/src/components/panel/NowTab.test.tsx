// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { Claim, TrackDetail } from "@/api/client";
import { NowTab } from "./NowTab";

afterEach(cleanup);

function claim(id: number, body: string, depth: Claim["depth"] = "listen"): Claim {
  return {
    id,
    subject_type: "track",
    subject_id: 1,
    type: "fact",
    body,
    body_long: null,
    phase: "during",
    depth,
    author: null,
    confidence: null,
    sources: [],
  };
}

const detail = {
  number: 1,
  disc: 1,
  title: "Opener",
  duration_ms: 190_000,
  apple_music_id: null,
  isrc: null,
  album_slug: "x",
  between: claim(1, "The first song written for the record."),
  moments: [
    { start_ms: 45_000, end_ms: 60_000, claim: claim(2, "The drum loop is from a b-side.") },
    { start_ms: 100_000, end_ms: null, claim: claim(3, "A quiet extra detail.", "study") },
  ],
  annotations: [],
  credits: [],
  links: [],
} as TrackDetail;

describe("NowTab (live)", () => {
  it("shows the intro at the start, then the moment from its timestamp", () => {
    const { rerender } = render(<NowTab detail={detail} positionMs={1_000} live />);
    expect(screen.getByText(/first song written/)).toBeTruthy();
    expect(screen.queryByText(/drum loop/)).toBeNull();

    rerender(<NowTab detail={detail} positionMs={45_000} live />);
    expect(screen.queryByText(/first song written/)).toBeNull(); // intro faded after 8 s
    expect(screen.getByText(/drum loop/)).toBeTruthy();
  });

  it("moves a finished moment to 'Heard so far'", () => {
    render(<NowTab detail={detail} positionMs={70_000} live />);
    expect(screen.getByText("Heard so far")).toBeTruthy();
    expect(screen.getAllByText(/drum loop/).length).toBeGreaterThan(0);
  });

  it("is correct after seeking back", () => {
    const { rerender } = render(<NowTab detail={detail} positionMs={70_000} live />);
    rerender(<NowTab detail={detail} positionMs={2_000} live />);
    expect(screen.queryByText("Heard so far")).toBeNull();
    expect(screen.queryByText(/drum loop/)).toBeNull();
  });

  it("shows study-depth moments as a chip, not a card", () => {
    render(<NowTab detail={detail} positionMs={101_000} live />);
    expect(screen.getByText(/Deeper note/)).toBeTruthy();
  });
});

describe("NowTab (browsing another song)", () => {
  it("lists everything to listen for, without timing", () => {
    render(<NowTab detail={detail} positionMs={0} live={false} />);
    expect(screen.getByText("Listen for")).toBeTruthy();
    expect(screen.getByText(/drum loop/)).toBeTruthy();
    expect(screen.getByText(/first song written/)).toBeTruthy();
  });
});
