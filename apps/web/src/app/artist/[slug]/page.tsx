import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/api/client";
import { AlbumCard } from "@/components/AlbumCard";
import { ClaimCard } from "@/components/ClaimCard";

export const dynamic = "force-dynamic";

export default async function ArtistPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const { data: artist, response } = await api.GET("/artists/{slug}", {
    params: { path: { slug } },
  });
  if (response.status === 404) notFound();
  if (!artist) throw new Error(`GET /artists/${slug} failed: ${response.status}`);

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <nav className="text-sm text-neutral-400">
        <Link href="/" className="hover:text-neutral-100">
          ← Home
        </Link>
      </nav>
      <h1 className="mt-8 text-4xl font-semibold tracking-tight">{artist.name}</h1>

      <h2 className="mt-10 text-sm uppercase tracking-widest text-neutral-500">Albums</h2>
      <ul className="mt-3 grid gap-2 sm:grid-cols-2">
        {artist.albums.map((a) => (
          <li key={a.slug}>
            <AlbumCard album={a} showArtist={false} />
          </li>
        ))}
      </ul>

      {artist.claims.length > 0 && (
        <>
          <h2 className="mt-10 text-sm uppercase tracking-widest text-neutral-500">About</h2>
          <div className="mt-3 space-y-4">
            {artist.claims.map((c) => (
              <ClaimCard key={c.id} claim={c} />
            ))}
          </div>
        </>
      )}
    </main>
  );
}
