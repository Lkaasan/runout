import { fetchAlbums, type AlbumSummary } from "@/lib-api";

export const dynamic = "force-dynamic";

export default async function Shelf() {
  let albums: AlbumSummary[] = [];
  let unavailable = false;
  try {
    albums = await fetchAlbums();
  } catch {
    unavailable = true;
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-4xl font-semibold tracking-tight">Albums</h1>
      {unavailable ? (
        <p className="mt-8 text-neutral-400">The API is not reachable. Is it running?</p>
      ) : albums.length === 0 ? (
        <p className="mt-8 text-neutral-400">Nothing on the shelf yet.</p>
      ) : (
        <ul className="mt-8 grid gap-6 sm:grid-cols-2">
          {albums.map((a) => (
            <li key={a.slug}>
              <a href={`/album/${a.slug}`} className="text-xl hover:underline">
                {a.title}
              </a>
              <div className="text-neutral-400">{a.artist}</div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
