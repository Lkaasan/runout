/** Which song the side panel is about, and which tab is open. Pure helpers. */

/** Pinned song wins; otherwise the panel follows what is playing. */
export function resolveActiveTrack(pinnedId: string | null, playingId: string | null): string | null {
  return pinnedId ?? playingId;
}

/** True when the panel is showing a song other than the one playing. */
export function isBrowsing(pinnedId: string | null, playingId: string | null): boolean {
  return pinnedId !== null && pinnedId !== playingId;
}

/** Use the remembered tab if it still exists, else the first available. */
export function resolveTab(stored: string | null, available: string[]): string | null {
  if (stored && available.includes(stored)) return stored;
  return available[0] ?? null;
}

/** Arrow-key navigation for the tab list (wraps around). */
export function nextTab(available: string[], current: string, key: string): string {
  const i = available.indexOf(current);
  if (i < 0) return available[0] ?? current;
  if (key === "ArrowRight") return available[(i + 1) % available.length];
  if (key === "ArrowLeft") return available[(i - 1 + available.length) % available.length];
  if (key === "Home") return available[0];
  if (key === "End") return available[available.length - 1];
  return current;
}

export type TabId = "now" | "meaning" | "album";

/** Song tabs exist only when a song is active; the Album tab is always there. */
export function availableTabs(hasSong: boolean): TabId[] {
  return hasSong ? ["now", "meaning", "album"] : ["album"];
}
