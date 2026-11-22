"use client";

import { useSyncExternalStore } from "react";
import type { AlbumDetail, TrackDetail } from "@/api/client";
import { availableTabs, nextTab, resolveTab, type TabId } from "@/lib/panel";
import { usePlayback } from "@/player/PlaybackProvider";
import { AlbumTab } from "./AlbumTab";
import { MeaningTab } from "./MeaningTab";
import { NowTab } from "./NowTab";
import { usePanel } from "./PanelProvider";

export interface PanelTrack {
  /** Player id (see playbackId). */
  id: string;
  number: number;
  title: string;
  detail: TrackDetail | null;
}

const LABELS: Record<TabId, string> = { now: "Now", meaning: "Meaning", album: "Album" };

const STORAGE_KEY = "runout.panel.tab";
const listeners = new Set<() => void>();

function readStoredTab(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** Choose a tab (and remember it). Also used by the album title to open the Album tab. */
export function selectPanelTab(id: TabId) {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // Storage can be blocked; the panel still works without remembering.
  }
  listeners.forEach((l) => l());
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

export function SidePanel({ tracks, album }: { tracks: PanelTrack[]; album: AlbumDetail }) {
  const { activeId, browsing, unpin } = usePanel();
  const { state } = usePlayback();
  // Server render and first paint use "no remembered tab"; the browser value follows.
  const stored = useSyncExternalStore(subscribe, readStoredTab, () => null);

  const track = tracks.find((t) => t.id === activeId) ?? null;
  const detail = track?.detail ?? null;
  const tabIds = availableTabs(detail !== null);
  const tab = (resolveTab(stored, tabIds) ?? "album") as TabId;
  const songView = track && detail && tab !== "album";

  return (
    <aside
      aria-label="About this album and song"
      className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5 lg:min-h-[24rem]"
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-widest text-neutral-500">
            {songView ? (browsing ? "Reading about" : "Now playing") : "About the album"}
          </div>
          <h2 className="truncate text-xl">
            {songView ? `${track.number}. ${track.title}` : album.title}
          </h2>
        </div>
        {browsing && (
          <button
            type="button"
            onClick={unpin}
            className="shrink-0 rounded-full border border-neutral-600 px-3 py-1 text-sm hover:border-neutral-300"
          >
            Back to now playing
          </button>
        )}
      </header>

      <div
        role="tablist"
        aria-label="Information"
        className="mt-4 flex gap-1 border-b border-neutral-800"
        onKeyDown={(e) => {
          const next = nextTab(tabIds, tab, e.key) as TabId;
          if (next !== tab) {
            e.preventDefault();
            selectPanelTab(next);
            document.getElementById(`tab-${next}`)?.focus();
          }
        }}
      >
        {tabIds.map((id) => (
          <button
            key={id}
            id={`tab-${id}`}
            role="tab"
            type="button"
            aria-selected={tab === id}
            aria-controls={`tabpanel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            onClick={() => selectPanelTab(id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              tab === id
                ? "border-neutral-100 text-neutral-100"
                : "border-transparent text-neutral-500 hover:text-neutral-300"
            }`}
          >
            {LABELS[id]}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`tabpanel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        className="mt-5"
      >
        {tab === "album" && <AlbumTab album={album} />}
        {tab === "meaning" && track && detail && <MeaningTab key={track.id} detail={detail} />}
        {tab === "now" && track && detail && (
          <NowTab
            key={track.id}
            detail={detail}
            positionMs={state.positionMs}
            live={!browsing && state.trackId === track.id}
          />
        )}
      </div>
    </aside>
  );
}
