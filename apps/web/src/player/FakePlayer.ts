import type { PlayerAdapter, PlayerEvent, PlayerState } from "./PlayerAdapter";

export interface FakeTrack {
  id: string;
  durationMs: number;
}

export interface FakePlayerOptions {
  /** Run a real-time timer while playing. Tests turn this off and call `advance()`. */
  autoTick?: boolean;
  /** Simulate a non-subscriber. Defaults to false: the fake plays full-length tracks. */
  previewOnly?: boolean;
}

const TICK_MS = 250;

/**
 * In-memory player with a fake clock and real track durations. No audio.
 * Lets dev and tests run the whole album without Apple credentials.
 */
export class FakePlayer implements PlayerAdapter {
  private index = 0;
  private positionMs = 0;
  private playing = false;
  private loaded = false;
  private timer: ReturnType<typeof setInterval> | null = null;
  private lastTick = 0;
  private listeners: Record<PlayerEvent, Set<() => void>> = {
    time: new Set(),
    track: new Set(),
    state: new Set(),
  };

  constructor(
    private readonly tracks: FakeTrack[],
    private readonly options: FakePlayerOptions = {},
  ) {}

  async connect(): Promise<void> {}

  async loadAlbum(): Promise<void> {
    this.stopTimer();
    this.index = 0;
    this.positionMs = 0;
    this.playing = false;
    this.loaded = this.tracks.length > 0;
    this.emit("track");
    this.emit("state");
    this.emit("time");
  }

  async playTrack(appleMusicTrackId: string): Promise<void> {
    const i = this.tracks.findIndex((t) => t.id === appleMusicTrackId);
    if (i < 0) throw new Error(`Track ${appleMusicTrackId} is not in the loaded album`);
    this.index = i;
    this.positionMs = 0;
    this.loaded = true;
    this.emit("track");
    this.emit("time");
    await this.play();
  }

  async play(): Promise<void> {
    if (!this.loaded) return;
    // Pressing play after the album finished starts it again.
    if (this.atEnd()) {
      this.index = 0;
      this.positionMs = 0;
      this.emit("track");
      this.emit("time");
    }
    if (this.playing) return;
    this.playing = true;
    this.startTimer();
    this.emit("state");
  }

  async pause(): Promise<void> {
    if (!this.playing) return;
    this.playing = false;
    this.stopTimer();
    this.emit("state");
  }

  async seek(ms: number): Promise<void> {
    const duration = this.current()?.durationMs ?? 0;
    this.positionMs = Math.min(Math.max(0, ms), duration);
    this.emit("time");
  }

  /** Move the fake clock forward. Drives playback; tests call it directly. */
  advance(ms: number): void {
    if (!this.playing) return;
    let remaining = ms;
    let trackChanged = false;
    while (remaining > 0) {
      const duration = this.current()?.durationMs ?? 0;
      const left = duration - this.positionMs;
      if (remaining < left) {
        this.positionMs += remaining;
        remaining = 0;
      } else if (this.index < this.tracks.length - 1) {
        remaining -= left;
        this.index += 1;
        this.positionMs = 0;
        trackChanged = true;
      } else {
        this.positionMs = duration;
        this.playing = false;
        this.stopTimer();
        remaining = 0;
        this.emit("state");
      }
    }
    if (trackChanged) this.emit("track");
    this.emit("time");
  }

  state(): PlayerState {
    const t = this.current();
    return {
      trackId: t?.id ?? null,
      positionMs: this.positionMs,
      durationMs: t?.durationMs ?? null,
      playing: this.playing,
      previewOnly: this.options.previewOnly ?? false,
    };
  }

  on(event: PlayerEvent, cb: () => void): () => void {
    this.listeners[event].add(cb);
    return () => {
      this.listeners[event].delete(cb);
    };
  }

  dispose(): void {
    this.stopTimer();
    for (const set of Object.values(this.listeners)) set.clear();
  }

  private current(): FakeTrack | undefined {
    return this.tracks[this.index];
  }

  private atEnd(): boolean {
    const last = this.tracks.length - 1;
    return this.index === last && this.positionMs >= (this.tracks[last]?.durationMs ?? 0);
  }

  private emit(event: PlayerEvent): void {
    for (const cb of [...this.listeners[event]]) cb();
  }

  private startTimer(): void {
    if (this.options.autoTick === false || this.timer) return;
    this.lastTick = Date.now();
    this.timer = setInterval(() => {
      const now = Date.now();
      const elapsed = now - this.lastTick;
      this.lastTick = now;
      this.advance(elapsed);
    }, TICK_MS);
  }

  private stopTimer(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }
}
