import type { SearchResults } from "@/api/client";

export type Suggestion = { kind: "artist" | "album"; href: string; label: string; hint: string };

/** Flatten search results into one keyboard-navigable list: artists first, then albums. */
export function suggestions(r: SearchResults): Suggestion[] {
  return [
    ...r.artists.map((a) => ({
      kind: "artist" as const,
      href: `/artist/${a.slug}`,
      label: a.name,
      hint: a.album_count === 1 ? "1 album" : `${a.album_count} albums`,
    })),
    ...r.albums.map((a) => ({
      kind: "album" as const,
      href: `/album/${a.slug}`,
      label: a.title,
      hint: a.artist,
    })),
  ];
}

/** Move the highlighted row with the arrow keys, wrapping; -1 means none. */
export function moveHighlight(current: number, delta: 1 | -1, count: number): number {
  if (count === 0) return -1;
  if (current === -1) return delta === 1 ? 0 : count - 1;
  return (current + delta + count) % count;
}
