import type { TrackDetail } from "@/api/client";
import { groupMeaning } from "@/lib/meaning";
import { ClaimCard } from "../ClaimCard";

/** Everything we can say about a song, grouped by who is speaking. */
export function MeaningTab({ detail }: { detail: TrackDetail }) {
  const { sections, deeper } = groupMeaning(detail.claims);

  if (sections.length === 0 && deeper.length === 0) {
    return <p className="text-neutral-500">Nothing reviewed about this song yet.</p>;
  }

  return (
    <div className="space-y-8">
      {sections.map((s) => (
        <section key={s.type} aria-label={s.title} className="space-y-5">
          <h3 className="text-xs uppercase tracking-widest text-neutral-500">{s.title}</h3>
          {s.claims.map((c) => (
            <ClaimCard key={c.id} claim={c} showType={false} />
          ))}
        </section>
      ))}
      {deeper.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-sm text-neutral-500 hover:text-neutral-300">
            Deeper notes ({deeper.length})
          </summary>
          <div className="mt-5 space-y-5">
            {deeper.map((c) => (
              <ClaimCard key={c.id} claim={c} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
