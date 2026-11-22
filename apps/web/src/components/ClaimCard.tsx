import type { Claim } from "@/api/client";

const LABEL: Record<Claim["type"], string> = {
  fact: "Fact",
  artist_intent: "In the artist's words",
  interpretation: "Interpretation",
  trivia: "Trivia",
};

// Facts, artist intent and interpretation are different kinds of statement and look different.
const STYLE: Record<Claim["type"], string> = {
  fact: "border-neutral-600",
  artist_intent: "border-amber-500/70",
  interpretation: "border-violet-400/70 italic",
  trivia: "border-neutral-800",
};

/**
 * One claim. The short body is always visible; "Go deeper" opens the long body and the sources
 * in place, so depth is part of the card instead of a separate mode.
 */
export function ClaimCard({ claim }: { claim: Claim }) {
  const supporting = claim.sources.filter((s) => s.stance === "supports");
  const contradicting = claim.sources.filter((s) => s.stance === "contradicts");
  const hasMore = Boolean(claim.body_long) || claim.sources.length > 0;

  return (
    <article className={`border-l-2 pl-4 ${STYLE[claim.type]}`}>
      <div className="text-xs uppercase tracking-wide text-neutral-500 not-italic">
        {LABEL[claim.type]}
        {claim.type === "interpretation" && claim.author ? ` · ${claim.author}` : ""}
      </div>
      <p className="mt-1 text-lg leading-relaxed">{claim.body}</p>
      {hasMore && (
        <details className="group mt-2 not-italic">
          <summary className="cursor-pointer text-sm text-neutral-500 hover:text-neutral-300">
            <span className="group-open:hidden">Go deeper</span>
            <span className="hidden group-open:inline">Show less</span>
          </summary>
          {claim.body_long && (
            <p className="mt-2 leading-relaxed text-neutral-300">{claim.body_long}</p>
          )}
          {claim.sources.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm text-neutral-400">
              {[...supporting, ...contradicting].map((s, i) => (
                <li key={i}>
                  {s.stance === "contradicts" && (
                    <span className="text-red-400">Disputed by </span>
                  )}
                  {s.source.url ? (
                    <a href={s.source.url} className="underline hover:text-neutral-200">
                      {s.source.title}
                    </a>
                  ) : (
                    s.source.title
                  )}
                  <span className="text-neutral-500">
                    {" "}
                    · {s.source.tier}
                    {s.locator ? ` · ${s.locator}` : ""}
                  </span>
                  {s.excerpt && <q className="block text-neutral-500">{s.excerpt}</q>}
                </li>
              ))}
            </ul>
          )}
        </details>
      )}
    </article>
  );
}
