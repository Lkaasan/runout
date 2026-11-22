/** Timing rules for the "Now" tab. Pure, so they can be tested without a player or a clock. */

export interface TimedMoment {
  start_ms: number;
  end_ms: number | null;
}

/** How long a moment stays up when the seed gives no end time. */
export const DEFAULT_MOMENT_MS = 12_000;
/** How long the between-songs intro stays up unless the listener taps it. */
export const INTRO_MS = 8_000;

/** The half-open window [start, end) in which a moment is on screen. */
export function momentWindow(m: TimedMoment): [number, number] {
  return [m.start_ms, m.end_ms ?? m.start_ms + DEFAULT_MOMENT_MS];
}

export function isVisible(m: TimedMoment, positionMs: number): boolean {
  const [start, end] = momentWindow(m);
  return positionMs >= start && positionMs < end;
}

/** Moments on screen right now. Correct after any seek, because it only looks at the position. */
export function visibleMoments<T extends TimedMoment>(moments: T[], positionMs: number): T[] {
  return moments.filter((m) => isVisible(m, positionMs));
}

/** Moments already heard (started at or before the position) that are no longer on screen. */
export function heardMoments<T extends TimedMoment>(moments: T[], positionMs: number): T[] {
  return moments.filter((m) => m.start_ms <= positionMs && !isVisible(m, positionMs));
}

export function introVisible(positionMs: number, tapped: boolean): boolean {
  return tapped || positionMs < INTRO_MS;
}
