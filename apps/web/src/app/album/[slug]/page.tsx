import { notFound } from "next/navigation";
import { api } from "@/api/client";
import { AlbumSession } from "@/components/AlbumSession";
import { trackKeyFromParam } from "@/lib/tracks";

export const dynamic = "force-dynamic";

// Fetches the album and every track's content; the client component does the rest.
// Everything is fetched at every depth: depth is handled in the UI ("Go deeper"), not by a mode.
// `?track=3` opens the page on that song, so a song can be linked to.
export default async function AlbumPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ track?: string | string[] }>;
}) {
  const { slug } = await params;
  const { track } = await searchParams;

  const { data: album, response } = await api.GET("/albums/{slug}", {
    params: { path: { slug } },
  });
  if (response.status === 404) notFound();
  if (!album) throw new Error(`GET /albums/${slug} failed: ${response.status}`);

  const details = await Promise.all(
    album.tracks.map(async (t) => {
      const { data } = await api.GET("/albums/{slug}/tracks/{number}", {
        params: { path: { slug, number: t.number }, query: { disc: t.disc } },
      });
      return data ?? null;
    }),
  );

  return (
    <AlbumSession
      album={album}
      details={details}
      initialTrackId={trackKeyFromParam(album.tracks, track)}
    />
  );
}
