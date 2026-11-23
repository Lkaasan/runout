/** Stable id for a track on an album page, and reading one back from the address. */

export function trackKey(t: { disc: number; number: number }): string {
  return `${t.disc}-${t.number}`;
}

/** `?track=3` names a track number; the first disc's track wins if numbers repeat across discs. */
export function trackKeyFromParam(
  tracks: { disc: number; number: number }[],
  param: string | string[] | undefined,
): string | null {
  const raw = Array.isArray(param) ? param[0] : param;
  const number = Number(raw);
  if (!raw || !Number.isInteger(number)) return null;
  const match = [...tracks]
    .sort((a, b) => a.disc - b.disc || a.number - b.number)
    .find((t) => t.number === number);
  return match ? trackKey(match) : null;
}
