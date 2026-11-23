import Link from "next/link";
import { api } from "@/api/client";
import { AlbumCard } from "@/components/AlbumCard";
import { ArtistCard } from "@/components/ArtistCard";
import { SearchBox } from "@/components/SearchBox";

export const dynamic = "force-dynamic";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string | string[] }>;
}) {
  const { q: raw } = await searchParams;
  const q = (Array.isArray(raw) ? raw[0] : raw)?.trim() ?? "";
  const results = q
    ? await api
        .GET("/search", { params: { query: { q, limit: 50 } } })
        .then((r) => r.data)
        .catch(() => undefined)
    : undefined;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <nav className="text-sm text-neutral-400">
        <Link href="/" className="hover:text-neutral-100">
          ← Home
        </Link>
      </nav>
      <div className="mt-6">
        <SearchBox initial={q} />
      </div>

      {!q ? null : !results ? (
        <p className="mt-10 text-neutral-400">Search is not available right now.</p>
      ) : results.artists.length === 0 && results.albums.length === 0 ? (
        <p className="mt-10 text-neutral-400">
          Nothing in the library matches &ldquo;{q}&rdquo;. We only hold albums that have been
          researched.
        </p>
      ) : (
        <>
          {results.artists.length > 0 && (
            <>
              <h2 className="mt-10 text-sm uppercase tracking-widest text-neutral-500">Artists</h2>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {results.artists.map((a) => (
                  <li key={a.slug}>
                    <ArtistCard artist={a} />
                  </li>
                ))}
              </ul>
            </>
          )}
          {results.albums.length > 0 && (
            <>
              <h2 className="mt-10 text-sm uppercase tracking-widest text-neutral-500">Albums</h2>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {results.albums.map((a) => (
                  <li key={a.slug}>
                    <AlbumCard album={a} />
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </main>
  );
}
