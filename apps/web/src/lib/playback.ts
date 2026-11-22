import type { PlaybackTrack } from "@/player/PlaybackProvider";

const FALLBACK_DURATION_MS = 180_000;

interface TrackLike {
  disc: number;
  number: number;
  title: string;
  duration_ms: number | null;
  apple_music_id: string | null;
}

/** Stable player id for a track: its Apple Music id, or "<disc>-<number>" if it has none. */
export function playbackId(t: Pick<TrackLike, "disc" | "number" | "apple_music_id">): string {
  return t.apple_music_id ?? `${t.disc}-${t.number}`;
}

export function toPlaybackTracks(tracks: TrackLike[]): PlaybackTrack[] {
  return tracks.map((t) => ({
    id: playbackId(t),
    title: t.title,
    number: t.number,
    durationMs: t.duration_ms ?? FALLBACK_DURATION_MS,
  }));
}
