// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { Claim, TrackDetail } from "@/api/client";
import { ListenForTab } from "./ListenForTab";

afterEach(cleanup);

const claim = (id: number, body: string): Claim => ({
  id,
  subject_type: "track",
  subject_id: 1,
  type: "fact",
  body,
  body_long: null,
  phase: "during",
  depth: "listen",
  author: null,
  confidence: null,
  sources: [],
});

describe("ListenForTab", () => {
  it("lists moments in time order with their timestamps", () => {
    const detail = {
      moments: [
        { start_ms: 130_000, end_ms: null, claim: claim(2, "Second thing.") },
        { start_ms: 45_000, end_ms: 60_000, claim: claim(1, "First thing.") },
      ],
    } as unknown as TrackDetail;
    render(<ListenForTab detail={detail} />);
    const text = document.body.textContent ?? "";
    expect(text.indexOf("At 0:45")).toBeLessThan(text.indexOf("At 2:10"));
    expect(text.indexOf("First thing.")).toBeLessThan(text.indexOf("Second thing."));
  });

  it("says so when there is nothing", () => {
    render(<ListenForTab detail={{ moments: [] } as unknown as TrackDetail} />);
    expect(screen.getByText(/Nothing to listen for/)).toBeTruthy();
  });
});
