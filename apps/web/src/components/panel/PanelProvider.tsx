"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { isBrowsing, resolveActiveTrack } from "@/lib/panel";
import { usePlayback } from "@/player/PlaybackProvider";

interface Panel {
  /** The song the panel is about: the pinned one, else whatever is playing. */
  activeId: string | null;
  /** The playing song's id (null before anything has played). */
  playingId: string | null;
  /** True while reading about a song other than the one playing. */
  browsing: boolean;
  pin(id: string): void;
  /** Back to now playing. */
  unpin(): void;
}

const PanelContext = createContext<Panel | null>(null);

/**
 * Which song the side panel shows. It follows the playing song; clicking another song pins the
 * panel to it without touching playback, and a new song starting releases the pin again.
 */
export function PanelProvider({ children }: { children: React.ReactNode }) {
  const { state } = usePlayback();
  const playingId = state.trackId;
  // A pin remembers which song was playing when it was made. When a different song starts the
  // pin no longer matches and is ignored, so the panel follows the new song again.
  const [pinState, setPin] = useState<{ id: string; playingAtPin: string | null } | null>(null);
  const pinnedId = pinState && pinState.playingAtPin === playingId ? pinState.id : null;

  const pin = useCallback((id: string) => setPin({ id, playingAtPin: playingId }), [playingId]);
  const unpin = useCallback(() => setPin(null), []);

  const value = useMemo<Panel>(
    () => ({
      activeId: resolveActiveTrack(pinnedId, playingId),
      playingId,
      browsing: isBrowsing(pinnedId, playingId),
      pin,
      unpin,
    }),
    [pinnedId, playingId, pin, unpin],
  );

  return <PanelContext.Provider value={value}>{children}</PanelContext.Provider>;
}

export function usePanel(): Panel {
  const ctx = useContext(PanelContext);
  if (!ctx) throw new Error("usePanel must be used inside <PanelProvider>");
  return ctx;
}
