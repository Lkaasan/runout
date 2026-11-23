/** Which tab of the information panel is open. Pure helpers. */

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

export type TabId = "meaning" | "listen" | "album";

/**
 * Song tabs exist only when a song is selected; the Album tab is always there. "Listen for" lists
 * the moments worth noticing in a song, so it only appears when the song has some.
 */
export function availableTabs(hasSong: boolean, hasListenFor = false): TabId[] {
  if (!hasSong) return ["album"];
  return hasListenFor ? ["meaning", "listen", "album"] : ["meaning", "album"];
}
