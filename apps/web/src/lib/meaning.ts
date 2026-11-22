import type { Claim } from "@/api/client";

export interface MeaningSection {
  type: Claim["type"];
  title: string;
  claims: Claim[];
}

export interface Meaning {
  sections: MeaningSection[];
  /** Study-depth claims from every section, shown behind one disclosure. */
  deeper: Claim[];
}

// Who is speaking decides the order: the artist first, then the record, then outside readings.
const ORDER: { type: Claim["type"]; title: string }[] = [
  { type: "artist_intent", title: "In the artist's words" },
  { type: "fact", title: "Documented" },
  { type: "interpretation", title: "Readings" },
  { type: "trivia", title: "Trivia" },
];

/** Groups a song's claims by type; listen-depth claims in sections, study-depth ones apart. */
export function groupMeaning(claims: Claim[]): Meaning {
  const sections = ORDER.map(({ type, title }) => ({
    type,
    title,
    claims: claims.filter((c) => c.type === type && c.depth === "listen"),
  })).filter((s) => s.claims.length > 0);

  const rank = new Map(ORDER.map((o, i) => [o.type, i]));
  const deeper = claims
    .filter((c) => c.depth === "study")
    .sort((a, b) => (rank.get(a.type) ?? 99) - (rank.get(b.type) ?? 99));

  return { sections, deeper };
}
