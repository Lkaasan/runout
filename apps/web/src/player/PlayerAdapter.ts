// Contract from docs/PLAN.md. Implementations arrive in Milestone 4.
export interface PlayerState {
  trackId: string | null;
  positionMs: number;
  playing: boolean;
  previewOnly: boolean;
}

export interface PlayerAdapter {
  connect(): Promise<void>;
  loadAlbum(appleMusicAlbumId: string): Promise<void>;
  playTrack(appleMusicTrackId: string): Promise<void>;
  play(): Promise<void>;
  pause(): Promise<void>;
  seek(ms: number): Promise<void>;
  state(): PlayerState;
  on(event: "time" | "track" | "state", cb: () => void): () => void;
}
