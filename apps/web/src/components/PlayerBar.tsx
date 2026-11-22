"use client";

import { formatMs } from "@/lib/format";
import { usePlayback } from "@/player/PlaybackProvider";

/** Fixed bar with transport controls. Calm by default: no shuffle, no motion. */
export function PlayerBar() {
  const { kind, tracks, state, connected, error, connect, play, pause, seek } = usePlayback();
  const current = tracks.find((t) => t.id === state.trackId) ?? tracks[0];
  // The scrubber follows what the player reports: a preview is shorter than the track.
  const duration = state.durationMs ?? current?.durationMs ?? 0;
  const position = Math.min(state.positionMs, duration);

  return (
    <div
      role="region"
      aria-label="Player"
      className="fixed inset-x-0 bottom-0 border-t border-neutral-800 bg-neutral-950/95 backdrop-blur"
    >
      {(error || kind === "fake" || (kind === "musickit" && state.previewOnly)) && (
        <p className="bg-neutral-900 px-6 py-1.5 text-center text-xs text-neutral-400" role="status">
          {error
            ? error
            : kind === "fake"
              ? "Demo player: no audio. Add Apple Music credentials to hear the album."
              : "Previews only (about 30 s per track)."}
        </p>
      )}
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-3">
        <button
          type="button"
          onClick={() => (state.playing ? pause() : play())}
          disabled={kind === null}
          aria-label={state.playing ? "Pause" : "Play"}
          className="h-10 w-10 shrink-0 rounded-full bg-neutral-100 text-neutral-950 disabled:opacity-40"
        >
          {state.playing ? "❚❚" : "▶"}
        </button>

        <div className="min-w-0 flex-1">
          <div className="truncate text-sm">
            {current ? `${current.number}. ${current.title}` : "Loading player…"}
          </div>
          <div className="mt-1 flex items-center gap-3 text-xs tabular-nums text-neutral-500">
            <span>{formatMs(position)}</span>
            <input
              type="range"
              aria-label="Seek"
              min={0}
              max={Math.max(duration, 1)}
              step={1000}
              value={position}
              disabled={kind === null || duration === 0}
              onChange={(e) => seek(Number(e.target.value))}
              className="h-1 flex-1 accent-neutral-100"
            />
            <span>{formatMs(duration)}</span>
          </div>
        </div>

        {kind === "musickit" && !connected && (
          <button
            type="button"
            onClick={() => connect()}
            className="shrink-0 rounded-full border border-neutral-600 px-4 py-2 text-sm hover:border-neutral-300"
          >
            Connect Apple Music
          </button>
        )}
      </div>
    </div>
  );
}
