import { api } from "@/api/client";
import { AlbumCard } from "@/components/AlbumCard";
import { ArtistCard } from "@/components/ArtistCard";
import { SearchBox } from "@/components/SearchBox";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [albums, artists] = await Promise.all([
    api.GET("/albums").then((r) => r.data),
    api.GET("/artists").then((r) => r.data),
  ]).catch(() => [undefined, undefined] as const);

  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-4xl font-semibold tracking-tight">Dive into a record</h1>
      <p className="mt-2 text-neutral-400">
        What is known about an album and its songs, with the sources behind it.
      </p>
      <div className="mt-8">
        <SearchBox autoFocus />
      </div>

      {!albums || !artists ? (
        <p className="mt-12 text-neutral-400">The API is not reachable. Is it running?</p>
      ) : albums.length === 0 ? (
        <p className="mt-12 text-neutral-400">
          Nothing here yet. Import an album with{" "}
          <code>uv run python -m app.seed import &lt;slug&gt;</code>.
        </p>
      ) : (
        <>
          <h2 className="mt-12 text-sm uppercase tracking-widest text-neutral-500">Albums</h2>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {albums.map((a) => (
              <li key={a.slug}>
                <AlbumCard album={a} />
              </li>
            ))}
          </ul>
          <h2 className="mt-12 text-sm uppercase tracking-widest text-neutral-500">Artists</h2>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {artists.map((a) => (
              <li key={a.slug}>
                <ArtistCard artist={a} />
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
