// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { AlbumDetail, Claim, TrackDetail } from "@/api/client";
import { AlbumTab } from "./AlbumTab";
import { MeaningTab } from "./MeaningTab";

afterEach(cleanup);

function claim(id: number, type: Claim["type"], body: string, depth: Claim["depth"] = "listen"): Claim {
  return {
    id,
    subject_type: "track",
    subject_id: 1,
    type,
    body,
    body_long: null,
    phase: "during",
    depth,
    author: type === "interpretation" ? "A Critic" : null,
    confidence: null,
    sources: [],
  };
}

const detail = (claims: Claim[]) => ({ claims }) as TrackDetail;

describe("MeaningTab", () => {
  it("groups claims by who is speaking, with deeper notes folded away", () => {
    render(
      <MeaningTab
        detail={detail([
          claim(1, "fact", "A documented fact."),
          claim(2, "artist_intent", "In the band's words."),
          claim(3, "fact", "A deep detail.", "study"),
        ])}
      />,
    );
    expect(screen.getByRole("heading", { name: "In the artist's words" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Documented" })).toBeTruthy();
    expect(screen.getByText(/Deeper notes \(1\)/)).toBeTruthy();
    expect(screen.queryByText("Readings")).toBeNull();
  });

  it("credits interpretations to their author", () => {
    render(<MeaningTab detail={detail([claim(1, "interpretation", "A reading.")])} />);
    expect(screen.getByText("A Critic")).toBeTruthy();
  });

  it("says so when nothing is reviewed yet", () => {
    render(<MeaningTab detail={detail([])} />);
    expect(screen.getByText(/Nothing reviewed about this song/)).toBeTruthy();
  });
});

describe("AlbumTab", () => {
  const album = (over: Partial<AlbumDetail>) =>
    ({ title: "Animals", before: [], after: [], credits: [], ...over }) as AlbumDetail;

  it("shows before, after and credits", () => {
    render(
      <AlbumTab
        album={album({
          before: [claim(1, "fact", "Recorded in 1976.")],
          after: [claim(2, "fact", "Reached number 2.")],
          credits: [{ person: "Brian Humphries", role: "engineer" }],
        })}
      />,
    );
    expect(screen.getByText("Before you listen")).toBeTruthy();
    expect(screen.getByText("After")).toBeTruthy();
    expect(screen.getByText("Brian Humphries")).toBeTruthy();
  });

  it("handles an album with nothing reviewed", () => {
    render(<AlbumTab album={album({})} />);
    expect(screen.getByText(/Nothing reviewed about this album/)).toBeTruthy();
  });
});
