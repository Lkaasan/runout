import Link from "next/link";
import { api } from "@/api/client";

export const dynamic = "force-dynamic";

export default async function Shelf() {
  const { data: albums, error } = await api
    .GET("/albums")
    .catch(() => ({ data: undefined, error: true }));

  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-4xl font-semibold tracking-tight">Albums</h1>
      {error || !albums ? (
        <p className="mt-8 text-neutral-400">The API is not reachable. Is it running?</p>
      ) : albums.length === 0 ? (
        <p className="mt-8 text-neutral-400">
          Nothing on the shelf yet. Import an album with{" "}
          <code>uv run python -m app.seed import &lt;slug&gt;</code>.
        </p>
      ) : (
        <ul className="mt-8 grid gap-6 sm:grid-cols-2">
          {albums.map((a) => (
            <li key={a.slug}>
              <Link
                href={`/album/${a.slug}`}
                className="flex gap-4 rounded-lg p-3 hover:bg-neutral-900"
              >
                <div className="size-20 shrink-0 rounded bg-neutral-800" aria-hidden />
                <div>
                  <div className="text-xl">{a.title}</div>
                  <div className="text-neutral-400">{a.artist}</div>
                  {a.release_date && (
                    <div className="text-sm text-neutral-500">{a.release_date.slice(0, 4)}</div>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
