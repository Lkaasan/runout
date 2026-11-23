"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

interface Panel {
  /** The song the panel is about, or null for the album as a whole. */
  selectedId: string | null;
  /** Select a song (or null for the album). The address is updated so the view can be shared. */
  select(id: string | null): void;
}

const PanelContext = createContext<Panel | null>(null);

/**
 * Which song the information panel shows. It is chosen by the reader, and mirrored in the page
 * address as `?track=N`, so a link to a song's page opens straight on it.
 */
export function PanelProvider({
  tracks,
  initialId,
  children,
}: {
  tracks: { id: string; number: number }[];
  initialId: string | null;
  children: React.ReactNode;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(initialId);

  const select = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      try {
        const url = new URL(window.location.href);
        const number = tracks.find((t) => t.id === id)?.number;
        if (number !== undefined) url.searchParams.set("track", String(number));
        else url.searchParams.delete("track");
        window.history.replaceState(null, "", url);
      } catch {
        // The address is a convenience; the panel works without it.
      }
    },
    [tracks],
  );

  const value = useMemo<Panel>(() => ({ selectedId, select }), [selectedId, select]);
  return <PanelContext.Provider value={value}>{children}</PanelContext.Provider>;
}

export function usePanel(): Panel {
  const ctx = useContext(PanelContext);
  if (!ctx) throw new Error("usePanel must be used inside <PanelProvider>");
  return ctx;
}
