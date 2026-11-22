import type { PlayerAdapter, PlayerEvent, PlayerState } from "./PlayerAdapter";

// Minimal typing for the parts of MusicKit JS v3 we use. Names checked against the shipped
// musickit.js (previewOnly, isAuthorized, seekToTime, the playback events, "musickitloaded").
interface MKInstance {
  authorize(): Promise<unknown>;
  setQueue(options: { album: string; startPlaying?: boolean }): Promise<unknown>;
  play(): Promise<unknown>;
  pause(): unknown;
  seekToTime(seconds: number): Promise<unknown>;
  changeToMediaAtIndex(index: number): Promise<unknown>;
  addEventListener(name: string, cb: () => void): void;
  removeEventListener(name: string, cb: () => void): void;
  nowPlayingItem?: { id: string } | null;
  queue: { items: { id: string }[] };
  currentPlaybackTime: number;
  currentPlaybackDuration: number;
  isPlaying: boolean;
  isAuthorized: boolean;
  previewOnly: boolean;
  shuffleMode: number;
}

interface MKGlobal {
  configure(config: {
    developerToken: string;
    app: { name: string; build: string };
  }): Promise<MKInstance>;
}

declare global {
  interface Window {
    MusicKit?: MKGlobal;
  }
}

const SCRIPT_URL = "https://js-cdn.music.apple.com/musickit/v3/musickit.js";
const SHUFFLE_OFF = 0;

const MK_EVENTS: Record<PlayerEvent, string> = {
  time: "playbackTimeDidChange",
  track: "nowPlayingItemDidChange",
  state: "playbackStateDidChange",
};

function loadScript(): Promise<MKGlobal> {
  if (window.MusicKit) return Promise.resolve(window.MusicKit);
  return new Promise((resolve, reject) => {
    const onLoaded = () => (window.MusicKit ? resolve(window.MusicKit) : reject(new Error("MusicKit missing")));
    document.addEventListener("musickitloaded", onLoaded, { once: true });
    const s = document.createElement("script");
    s.src = SCRIPT_URL;
    s.async = true;
    s.onerror = () => reject(new Error("Could not load MusicKit JS"));
    document.head.appendChild(s);
  });
}

export interface MusicKitPlayerOptions {
  /** Full URL of the API's `/musickit/developer-token`. */
  tokenUrl: string;
  appName?: string;
}

/**
 * Apple Music playback through MusicKit JS v3. Browser only.
 * Non-subscribers (or signed-out users) get previews of about 30 s per track; `previewOnly`
 * in state() reports that. Timing always comes from MusicKit's own events.
 */
export class MusicKitPlayer implements PlayerAdapter {
  private mk: Promise<MKInstance> | null = null;
  private instance: MKInstance | null = null;
  private disposers: (() => void)[] = [];

  constructor(private readonly options: MusicKitPlayerOptions) {}

  get isAuthorized(): boolean {
    return this.instance?.isAuthorized ?? false;
  }

  private ensureConfigured(): Promise<MKInstance> {
    this.mk ??= (async () => {
      const [MusicKit, res] = await Promise.all([loadScript(), fetch(this.options.tokenUrl)]);
      if (!res.ok) throw new Error(`Developer token request failed (${res.status})`);
      const { token } = (await res.json()) as { token: string };
      const instance = await MusicKit.configure({
        developerToken: token,
        app: { name: this.options.appName ?? "Album Deep-Dive", build: "0.1.0" },
      });
      instance.shuffleMode = SHUFFLE_OFF;
      this.instance = instance;
      return instance;
    })();
    // Let a later call retry after a failure.
    this.mk.catch(() => {
      this.mk = null;
    });
    return this.mk;
  }

  async connect(): Promise<void> {
    const mk = await this.ensureConfigured();
    try {
      await mk.authorize();
    } catch {
      // Declined or no subscription: previews still work, state().previewOnly says so.
    }
  }

  async loadAlbum(appleMusicAlbumId: string): Promise<void> {
    const mk = await this.ensureConfigured();
    await mk.setQueue({ album: appleMusicAlbumId, startPlaying: false });
    mk.shuffleMode = SHUFFLE_OFF;
  }

  async playTrack(appleMusicTrackId: string): Promise<void> {
    const mk = await this.ensureConfigured();
    const index = mk.queue.items.findIndex((i) => i.id === appleMusicTrackId);
    if (index < 0) throw new Error(`Track ${appleMusicTrackId} is not in the queued album`);
    await mk.changeToMediaAtIndex(index);
  }

  async play(): Promise<void> {
    await (await this.ensureConfigured()).play();
  }

  async pause(): Promise<void> {
    (await this.ensureConfigured()).pause();
  }

  async seek(ms: number): Promise<void> {
    await (await this.ensureConfigured()).seekToTime(ms / 1000);
  }

  state(): PlayerState {
    const mk = this.instance;
    if (!mk) {
      return { trackId: null, positionMs: 0, durationMs: null, playing: false, previewOnly: false };
    }
    const duration = mk.currentPlaybackDuration;
    return {
      trackId: mk.nowPlayingItem?.id ?? null,
      positionMs: Math.round((mk.currentPlaybackTime || 0) * 1000),
      durationMs: duration > 0 ? Math.round(duration * 1000) : null,
      playing: mk.isPlaying,
      previewOnly: mk.previewOnly,
    };
  }

  on(event: PlayerEvent, cb: () => void): () => void {
    let off = () => {};
    let cancelled = false;
    // Listeners may be registered before MusicKit has loaded; attach once it has.
    this.ensureConfigured().then(
      (mk) => {
        if (cancelled) return;
        mk.addEventListener(MK_EVENTS[event], cb);
        off = () => mk.removeEventListener(MK_EVENTS[event], cb);
      },
      () => {},
    );
    const dispose = () => {
      cancelled = true;
      off();
    };
    this.disposers.push(dispose);
    return dispose;
  }

  dispose(): void {
    for (const d of this.disposers) d();
    this.disposers = [];
  }
}
