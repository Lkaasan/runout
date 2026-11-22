"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { FakePlayer } from "./FakePlayer";
import { MusicKitPlayer } from "./MusicKitPlayer";
import type { PlayerAdapter, PlayerState } from "./PlayerAdapter";

export interface PlaybackTrack {
  /** apple_music_id, or "<disc>-<number>" when the track has none. */
  id: string;
  title: string;
  number: number;
  durationMs: number;
}

export type PlayerKind = "musickit" | "fake";

interface Playback {
  /** null until the provider has picked and loaded a player. */
  kind: PlayerKind | null;
  tracks: PlaybackTrack[];
  state: PlayerState;
  /** True once the listener has signed in to Apple Music. Always true for the fake player. */
  connected: boolean;
  error: string | null;
  connect(): Promise<void>;
  play(): Promise<void>;
  pause(): Promise<void>;
  seek(ms: number): Promise<void>;
  playTrack(id: string): Promise<void>;
}

const IDLE: PlayerState = {
  trackId: null,
  positionMs: 0,
  durationMs: null,
  playing: false,
  previewOnly: false,
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const OVERRIDE = process.env.NEXT_PUBLIC_PLAYER; // "fake" | "musickit" | undefined

const PlaybackContext = createContext<Playback | null>(null);

type Disposable = PlayerAdapter & { dispose(): void };

async function tokenAvailable(): Promise<boolean> {
  try {
    return (await fetch(`${API_URL}/musickit/developer-token`)).ok;
  } catch {
    return false;
  }
}

/** One player for the whole album page. Timing comes from the player's events, never timers here. */
export function PlaybackProvider({
  albumAppleMusicId,
  tracks,
  children,
}: {
  albumAppleMusicId: string | null;
  tracks: PlaybackTrack[];
  children: React.ReactNode;
}) {
  const adapter = useRef<Disposable | null>(null);
  const [kind, setKind] = useState<PlayerKind | null>(null);
  const [state, setState] = useState<PlayerState>(IDLE);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let offs: (() => void)[] = [];

    async function start(candidate: Disposable, chosen: PlayerKind) {
      const refresh = () => setState(candidate.state());
      offs = (["time", "track", "state"] as const).map((e) => candidate.on(e, refresh));
      await candidate.loadAlbum(albumAppleMusicId ?? "");
      if (cancelled) return;
      adapter.current = candidate;
      setKind(chosen);
      setConnected(chosen === "fake");
      refresh();
    }

    async function init() {
      const fake = () =>
        new FakePlayer(tracks.map((t) => ({ id: t.id, durationMs: t.durationMs })));
      const wantsMusicKit =
        albumAppleMusicId !== null &&
        OVERRIDE !== "fake" &&
        (OVERRIDE === "musickit" || (await tokenAvailable()));
      if (cancelled) return;

      if (wantsMusicKit) {
        const mk = new MusicKitPlayer({ tokenUrl: `${API_URL}/musickit/developer-token` });
        try {
          await start(mk, "musickit");
          return;
        } catch (e) {
          // Script blocked, token endpoint down, album not in the catalogue... keep the page usable.
          offs.forEach((off) => off());
          mk.dispose();
          if (cancelled) return;
          setError(e instanceof Error ? e.message : "Apple Music is unavailable");
        }
      }
      const f = fake();
      await start(f, "fake");
    }

    init().catch((e) => {
      if (!cancelled) setError(e instanceof Error ? e.message : "Player failed to start");
    });

    return () => {
      cancelled = true;
      offs.forEach((off) => off());
      adapter.current?.dispose();
      adapter.current = null;
      setKind(null);
      setState(IDLE);
    };
  }, [albumAppleMusicId, tracks]);

  const run = useCallback(async (fn: (a: Disposable) => Promise<void>) => {
    if (!adapter.current) return;
    try {
      setError(null);
      await fn(adapter.current);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Playback failed");
    }
  }, []);

  const value = useMemo<Playback>(
    () => ({
      kind,
      tracks,
      state,
      connected,
      error,
      connect: () =>
        run(async (a) => {
          await a.connect();
          setConnected(a instanceof MusicKitPlayer ? a.isAuthorized : true);
        }),
      play: () =>
        run((a) => (a.state().trackId || !tracks[0] ? a.play() : a.playTrack(tracks[0].id))),
      pause: () => run((a) => a.pause()),
      seek: (ms) => run((a) => a.seek(ms)),
      playTrack: (id) => run((a) => a.playTrack(id)),
    }),
    [kind, tracks, state, connected, error, run],
  );

  return <PlaybackContext.Provider value={value}>{children}</PlaybackContext.Provider>;
}

export function usePlayback(): Playback {
  const ctx = useContext(PlaybackContext);
  if (!ctx) throw new Error("usePlayback must be used inside <PlaybackProvider>");
  return ctx;
}
