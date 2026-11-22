import { describe, expect, it } from "vitest";
import type { Claim } from "@/api/client";
import { groupMeaning } from "./meaning";

function claim(id: number, type: Claim["type"], depth: Claim["depth"] = "listen"): Claim {
  return {
    id,
    subject_type: "track",
    subject_id: 1,
    type,
    body: `claim ${id}`,
    body_long: null,
    phase: "during",
    depth,
    author: null,
    confidence: null,
    sources: [],
  };
}

describe("groupMeaning", () => {
  it("orders sections: artist, documented, readings, trivia", () => {
    const { sections } = groupMeaning([
      claim(1, "trivia"),
      claim(2, "interpretation"),
      claim(3, "fact"),
      claim(4, "artist_intent"),
    ]);
    expect(sections.map((s) => s.title)).toEqual([
      "In the artist's words",
      "Documented",
      "Readings",
      "Trivia",
    ]);
  });

  it("omits empty sections", () => {
    expect(groupMeaning([claim(1, "fact")]).sections.map((s) => s.type)).toEqual(["fact"]);
    expect(groupMeaning([]).sections).toEqual([]);
  });

  it("puts study-depth claims in one list, in the same speaker order", () => {
    const { sections, deeper } = groupMeaning([
      claim(1, "fact"),
      claim(2, "fact", "study"),
      claim(3, "artist_intent", "study"),
    ]);
    expect(sections[0].claims.map((c) => c.id)).toEqual([1]);
    expect(deeper.map((c) => c.id)).toEqual([3, 2]);
  });
});
