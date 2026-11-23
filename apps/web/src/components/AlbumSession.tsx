"use client";

import Link from "next/link";
import type { AlbumDetail, TrackDetail } from "@/api/client";
import { formatMs } from "@/lib/format";
import { playbackId, toPlaybackTracks } from "@/lib/playback";
import { PlaybackProvider, usePlayback } from "@/player/PlaybackProvider";
import { PanelProvider, usePanel } from "./panel/PanelProvider";
import { type PanelTrack, selectPanelTab, SidePanel } from "./panel/SidePanel";
import { AlbumCover } from "./AlbumCover";
import { PlayerBar } from "./PlayerBar";
import { TrackPlayButton } from "./TrackPlayButton";

/** The album page: content on the left, the song panel on the right, the player below. */
export function AlbumSession({
  album,
  details,
}: {
  album: AlbumDetail;
  /** Same order as album.tracks; null if a track failed to load. */
  details: (TrackDetail | null)[];
}) {
  const panelTracks: PanelTrack[] = album.tracks.map((t, i) => ({
    id: playbackId(t),
    number: t.number,
    title: t.title,
    detail: details[i] ?? null,
  }));

  return (
    <PlaybackProvider
      albumAppleMusicId={album.apple_music_id}
      tracks={toPlaybackTracks(album.tracks)}
    >
      <PanelProvider>
        <main className="mx-auto max-w-6xl px-6 pb-40 pt-12">
          <nav className="text-sm text-neutral-400">
            <Link href="/" className="hover:text-neutral-100">
              ← Albums
            </Link>
          </nav>

          <header className="mt-8 flex items-end gap-5">
            <AlbumCover url={album.artwork_url} title={album.title} className="size-32" />
            <div className="min-w-0">
              <h1 className="text-4xl font-semibold tracking-tight">
                <button
                  type="button"
                  onClick={() => selectPanelTab("album")}
                  title="About the album"
                  className="text-left hover:text-neutral-300"
                >
                  {album.title}
                </button>
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
                {album.tracks.map((t) => (
                  <TrackRow
                    key={`${t.disc}-${t.number}`}
                    id={playbackId(t)}
                    number={t.number}
                    title={t.title}
                    durationMs={t.duration_ms}
                  />
                ))}
              </ol>
            </section>

            <SidePanel tracks={panelTracks} album={album} />
          </div>
        </main>
        <PlayerBar />
      </PanelProvider>
    </PlaybackProvider>
  );
}

function TrackRow({
  id,
  number,
  title,
  durationMs,
}: {
  id: string;
  number: number;
  title: string;
  durationMs: number | null;
}) {
  const { state } = usePlayback();
  const { activeId, pin } = usePanel();
  const playing = state.trackId === id;
  const shown = activeId === id;

  return (
    <li
      aria-current={playing ? "true" : undefined}
      className={`flex items-center gap-4 rounded-lg px-3 py-2 ${
        shown ? "bg-neutral-900" : ""
      }`}
    >
      <TrackPlayButton trackId={id} title={title} />
      <span className="w-6 text-right tabular-nums text-neutral-500">{number}</span>
      <button
        type="button"
        onClick={() => pin(id)}
        title="Read about this song"
        className={`min-w-0 flex-1 truncate text-left text-lg hover:text-neutral-100 ${
          playing ? "text-neutral-100" : "text-neutral-300"
        }`}
      >
        {title}
      </button>
      {durationMs != null && (
        <span className="tabular-nums text-neutral-500">{formatMs(durationMs)}</span>
      )}
    </li>
  );
}
