"use client";

import { usePlayback } from "@/player/PlaybackProvider";

export function TrackPlayButton({ trackId, title }: { trackId: string; title: string }) {
  const { kind, state, playTrack, pause } = usePlayback();
  const active = state.trackId === trackId && state.playing;
  return (
    <button
      type="button"
      disabled={kind === null}
      onClick={() => (active ? pause() : playTrack(trackId))}
      aria-label={active ? `Pause ${title}` : `Play ${title}`}
      className="h-8 w-8 shrink-0 self-center rounded-full border border-neutral-700 text-xs text-neutral-300 hover:border-neutral-300 disabled:opacity-40"
    >
      {active ? "❚❚" : "▶"}
    </button>
  );
}
