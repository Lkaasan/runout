// Contract from docs/PLAN.md. `durationMs` was added in Milestone 4 so the scrubber can follow
// what the player actually reports (a ~30 s preview is shorter than the catalogue duration).
export interface PlayerState {
  trackId: string | null;
  positionMs: number;
  /** Playable length of the current item as the player reports it; null when unknown. */
  durationMs: number | null;
  playing: boolean;
  previewOnly: boolean;
}

export type PlayerEvent = "time" | "track" | "state";

export interface PlayerAdapter {
  connect(): Promise<void>;
  loadAlbum(appleMusicAlbumId: string): Promise<void>;
  playTrack(appleMusicTrackId: string): Promise<void>;
  play(): Promise<void>;
  pause(): Promise<void>;
  seek(ms: number): Promise<void>;
  state(): PlayerState;
  on(event: PlayerEvent, cb: () => void): () => void;
}
