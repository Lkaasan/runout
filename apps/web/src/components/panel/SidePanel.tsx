"use client";

import { useSyncExternalStore } from "react";
import type { TrackDetail } from "@/api/client";
import { nextTab, resolveTab } from "@/lib/panel";
import { usePlayback } from "@/player/PlaybackProvider";
import { NowTab } from "./NowTab";
import { usePanel } from "./PanelProvider";

export interface PanelTrack {
  /** Player id (see playbackId). */
  id: string;
  number: number;
  title: string;
  detail: TrackDetail | null;
}

interface TabDef {
  id: string;
  label: string;
  /** Tabs with nothing to show for this song are hidden. */
  available(detail: TrackDetail): boolean;
}

// More tabs (Meaning, Lyrics, Making, Sources) are added here as they are built.
const TABS: TabDef[] = [{ id: "now", label: "Now", available: () => true }];

const STORAGE_KEY = "runout.panel.tab";
const listeners = new Set<() => void>();

function readStoredTab(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeTab(id: string) {
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

export function SidePanel({ tracks }: { tracks: PanelTrack[] }) {
  const { activeId, browsing, unpin } = usePanel();
  const { state } = usePlayback();
  // Server render and first paint use "no remembered tab"; the browser value follows.
  const stored = useSyncExternalStore(subscribe, readStoredTab, () => null);

  const track = tracks.find((t) => t.id === activeId) ?? null;
  const detail = track?.detail ?? null;
  const tabs = detail ? TABS.filter((t) => t.available(detail)) : [];
  const tabIds = tabs.map((t) => t.id);
  const tab = resolveTab(stored, tabIds);

  const choose = storeTab;

  return (
    <aside
      aria-label="About this song"
      className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5 lg:sticky lg:top-6 lg:max-h-[calc(100vh-9rem)] lg:overflow-y-auto"
    >
      {!track || !detail ? (
        <p className="text-neutral-500">
          Press play, or choose a song, to see what to listen for.
        </p>
      ) : (
        <>
          <header className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs uppercase tracking-widest text-neutral-500">
                {browsing ? "Reading about" : "Now playing"}
              </div>
              <h2 className="truncate text-xl">
                {track.number}. {track.title}
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
            aria-label="Song information"
            className="mt-4 flex gap-1 border-b border-neutral-800"
            onKeyDown={(e) => {
              if (!tab) return;
              const next = nextTab(tabIds, tab, e.key);
              if (next !== tab) {
                e.preventDefault();
                choose(next);
                document.getElementById(`tab-${next}`)?.focus();
              }
            }}
          >
            {tabs.map((t) => (
              <button
                key={t.id}
                id={`tab-${t.id}`}
                role="tab"
                type="button"
                aria-selected={tab === t.id}
                aria-controls={`tabpanel-${t.id}`}
                tabIndex={tab === t.id ? 0 : -1}
                onClick={() => choose(t.id)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm ${
                  tab === t.id
                    ? "border-neutral-100 text-neutral-100"
                    : "border-transparent text-neutral-500 hover:text-neutral-300"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div
            role="tabpanel"
            id={`tabpanel-${tab}`}
            aria-labelledby={`tab-${tab}`}
            className="mt-5"
          >
            {tab === "now" && (
              <NowTab
                key={track.id}
                detail={detail}
                positionMs={state.positionMs}
                live={!browsing && state.trackId === track.id}
              />
            )}
          </div>
        </>
      )}
    </aside>
  );
}
