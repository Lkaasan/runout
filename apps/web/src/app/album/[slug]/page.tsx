import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/api/client";
import { ClaimCard } from "@/components/ClaimCard";
import { PlayerBar } from "@/components/PlayerBar";
import { TrackPlayButton } from "@/components/TrackPlayButton";
import { formatMs, parseMode } from "@/lib/format";
import { playbackId, toPlaybackTracks } from "@/lib/playback";
import { PlaybackProvider } from "@/player/PlaybackProvider";

export const dynamic = "force-dynamic";

// The session page: content plus a basic player (Milestone 4). Phases and timed moments come later.
export default async function AlbumPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ mode?: string }>;
}) {
  const { slug } = await params;
  const mode = parseMode((await searchParams).mode);
  const study = mode === "study";
  const query = study ? {} : { depth: "listen" as const };

  const { data: album, response } = await api.GET("/albums/{slug}", {
    params: { path: { slug }, query },
  });
  if (response.status === 404) notFound();
  if (!album) throw new Error(`GET /albums/${slug} failed: ${response.status}`);

  const tracks = await Promise.all(
    album.tracks.map(async (t) => {
      const { data } = await api.GET("/albums/{slug}/tracks/{number}", {
        params: { path: { slug, number: t.number }, query: { ...query, disc: t.disc } },
      });
      return data;
    }),
  );

  return (
    <PlaybackProvider
      albumAppleMusicId={album.apple_music_id}
      tracks={toPlaybackTracks(album.tracks)}
    >
    <main className="mx-auto max-w-3xl px-6 pb-40 pt-12">
      <nav className="flex items-center justify-between text-sm text-neutral-400">
        <Link href="/" className="hover:text-neutral-100">
          ← Albums
        </Link>
        <div role="group" aria-label="Mode" className="flex gap-1 rounded-full bg-neutral-900 p-1">
          {(["listen", "study"] as const).map((m) => (
            <Link
              key={m}
              href={`/album/${slug}?mode=${m}`}
              aria-current={mode === m ? "true" : undefined}
              className={`rounded-full px-3 py-1 capitalize ${
                mode === m ? "bg-neutral-100 text-neutral-950" : "hover:text-neutral-100"
              }`}
            >
              {m}
            </Link>
          ))}
        </div>
      </nav>

      <header className="mt-10">
        <h1 className="text-5xl font-semibold tracking-tight">{album.title}</h1>
        <p className="mt-2 text-xl text-neutral-400">
          {album.artist}
          {album.release_date ? ` · ${album.release_date.slice(0, 4)}` : ""}
        </p>
      </header>

      {album.before.length > 0 && (
        <section className="mt-12 space-y-6" aria-label="Before you listen">
          <h2 className="text-sm uppercase tracking-widest text-neutral-500">Before you listen</h2>
          {album.before.map((c) => (
            <ClaimCard key={c.id} claim={c} study={study} />
          ))}
        </section>
      )}

      <section className="mt-14" aria-label="Tracklist">
        <h2 className="text-sm uppercase tracking-widest text-neutral-500">Tracks</h2>
        <ol className="mt-4 space-y-10">
          {album.tracks.map((t, i) => {
            const detail = tracks[i];
            return (
              <li key={`${t.disc}-${t.number}`}>
                <div className="flex items-baseline gap-4">
                  <TrackPlayButton trackId={playbackId(t)} title={t.title} />
                  <span className="w-6 text-right text-neutral-500">{t.number}</span>
                  <h3 className="text-2xl">{t.title}</h3>
                  {t.duration_ms != null && (
                    <span className="text-neutral-500">{formatMs(t.duration_ms)}</span>
                  )}
                </div>
                {detail && (
                  <div className="mt-4 space-y-5 pl-10">
                    {detail.between && <ClaimCard claim={detail.between} study={study} />}
                    {detail.moments.map((m) => (
                      <div key={m.start_ms}>
                        <div className="mb-1 text-sm text-neutral-500">
                          At {formatMs(m.start_ms)}
                        </div>
                        <ClaimCard claim={m.claim} study={study} />
                      </div>
                    ))}
                    {study &&
                      detail.annotations.map((a) => (
                        <div key={a.line_start}>
                          <div className="mb-1 text-sm text-neutral-500">
                            Lines {a.line_start}–{a.line_end}
                          </div>
                          <ClaimCard claim={a.claim} study={study} />
                        </div>
                      ))}
                    {detail.links.map((l, j) => (
                      <p key={j} className="text-sm text-neutral-400">
                        {l.relation.replace("_", " ")}{" "}
                        <span className="text-neutral-200">{l.target_title ?? "linked track"}</span>
                      </p>
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      </section>

      {album.after.length > 0 && (
        <section className="mt-14 space-y-6" aria-label="After">
          <h2 className="text-sm uppercase tracking-widest text-neutral-500">After</h2>
          {album.after.map((c) => (
            <ClaimCard key={c.id} claim={c} study={study} />
          ))}
        </section>
      )}
    </main>
    <PlayerBar />
    </PlaybackProvider>
  );
}
