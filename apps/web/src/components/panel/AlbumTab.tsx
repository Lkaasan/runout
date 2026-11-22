import type { AlbumDetail } from "@/api/client";
import { ClaimList } from "../ClaimList";

/** The album as a whole: context before you listen, what came after, and who made it. */
export function AlbumTab({ album }: { album: AlbumDetail }) {
  const empty = album.before.length === 0 && album.after.length === 0 && album.credits.length === 0;
  if (empty) return <p className="text-neutral-500">Nothing reviewed about this album yet.</p>;

  return (
    <div className="space-y-10">
      {album.before.length > 0 && (
        <section aria-label="Before you listen" className="space-y-5">
          <h3 className="text-xs uppercase tracking-widest text-neutral-500">Before you listen</h3>
          <ClaimList claims={album.before} />
        </section>
      )}
      {album.after.length > 0 && (
        <section aria-label="After" className="space-y-5">
          <h3 className="text-xs uppercase tracking-widest text-neutral-500">After</h3>
          <ClaimList claims={album.after} />
        </section>
      )}
      {album.credits.length > 0 && (
        <section aria-label="Credits" className="space-y-3">
          <h3 className="text-xs uppercase tracking-widest text-neutral-500">Credits</h3>
          <dl className="space-y-1 text-sm">
            {album.credits.map((c, i) => (
              <div key={i} className="flex gap-3">
                <dt className="w-44 shrink-0 text-neutral-200">{c.person}</dt>
                <dd className="text-neutral-400">{c.role}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </div>
  );
}
