"use client";

import Link from "next/link";
import type { AlbumDetail, TrackDetail } from "@/api/client";
import { formatMs } from "@/lib/format";
import { trackKey } from "@/lib/tracks";
import { AlbumCover } from "./AlbumCover";
import { PanelProvider, usePanel } from "./panel/PanelProvider";
import { type PanelTrack, selectPanelTab, SidePanel } from "./panel/SidePanel";

/** The album page: the tracklist on the left, everything we know on the right. */
export function AlbumSession({
  album,
  details,
  initialTrackId = null,
}: {
  album: AlbumDetail;
  /** Same order as album.tracks; null if a track failed to load. */
  details: (TrackDetail | null)[];
  /** The song to open on, from `?track=N`. */
  initialTrackId?: string | null;
}) {
  const panelTracks: PanelTrack[] = album.tracks.map((t, i) => ({
    id: trackKey(t),
    number: t.number,
    title: t.title,
    detail: details[i] ?? null,
  }));

  return (
    <PanelProvider tracks={panelTracks} initialId={initialTrackId}>
      <main className="mx-auto max-w-6xl px-6 pb-24 pt-12">
        <nav className="text-sm text-neutral-400">
          <Link href="/" className="hover:text-neutral-100">
            ← Albums
          </Link>
        </nav>

        <header className="mt-8 flex items-end gap-5">
          <AlbumCover url={album.artwork_url} title={album.title} className="size-32" />
          <div className="min-w-0">
            <h1 className="text-4xl font-semibold tracking-tight">
              <AlbumTitle title={album.title} />
            </h1>
            <p className="mt-1 text-lg text-neutral-400">
              {album.artist}
              {album.release_date ? ` · ${album.release_date.slice(0, 4)}` : ""}
            </p>
          </div>
        </header>

        <div className="mt-8 grid items-start gap-8 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <section aria-label="Tracklist" className="lg:sticky lg:top-6">
            <h2 className="text-sm uppercase tracking-widest text-neutral-500">Tracks</h2>
            <ol className="mt-3 space-y-1">
              {panelTracks.map((t, i) => (
                <TrackRow
                  key={t.id}
                  id={t.id}
                  number={t.number}
                  title={t.title}
                  durationMs={album.tracks[i].duration_ms}
                  notes={t.detail?.claims.length ?? 0}
                />
              ))}
            </ol>
          </section>

          <SidePanel tracks={panelTracks} album={album} />
        </div>
      </main>
    </PanelProvider>
  );
}

/** The album's name: opens the whole-album view in the panel. */
function AlbumTitle({ title }: { title: string }) {
  const { select } = usePanel();
  return (
    <button
      type="button"
      onClick={() => {
        select(null);
        selectPanelTab("album");
      }}
      title="About the album"
      className="text-left hover:text-neutral-300"
    >
      {title}
    </button>
  );
}

function TrackRow({
  id,
  number,
  title,
  durationMs,
  notes,
}: {
  id: string;
  number: number;
  title: string;
  durationMs: number | null;
  /** How many approved claims we have about this song. */
  notes: number;
}) {
  const { selectedId, select } = usePanel();
  const selected = selectedId === id;

  return (
    <li>
      <button
        type="button"
        onClick={() => {
          select(id);
          selectPanelTab("meaning");
        }}
        aria-current={selected ? "true" : undefined}
        title="Read about this song"
        className={`flex w-full items-center gap-4 rounded-lg px-3 py-2 text-left hover:bg-neutral-900 ${
          selected ? "bg-neutral-900" : ""
        }`}
      >
        <span className="w-6 text-right tabular-nums text-neutral-500">{number}</span>
        <span
          className={`min-w-0 flex-1 truncate text-lg ${
            selected ? "text-neutral-100" : "text-neutral-300"
          }`}
        >
          {title}
        </span>
        {notes > 0 && (
          <span
            title={`${notes} notes about this song`}
            className="rounded-full bg-neutral-800 px-2 text-xs tabular-nums text-neutral-400"
          >
            {notes}
          </span>
        )}
        {durationMs != null && (
          <span className="tabular-nums text-neutral-500">{formatMs(durationMs)}</span>
        )}
      </button>
    </li>
  );
}
