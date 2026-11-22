import type { Claim } from "@/api/client";
import { ClaimCard } from "./ClaimCard";

/** Listen-depth claims first; study-depth ones sit behind a quiet disclosure. */
export function ClaimList({ claims }: { claims: Claim[] }) {
  const main = claims.filter((c) => c.depth === "listen");
  const deeper = claims.filter((c) => c.depth === "study");
  return (
    <div className="space-y-6">
      {main.map((c) => (
        <ClaimCard key={c.id} claim={c} />
      ))}
      {deeper.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-sm text-neutral-500 hover:text-neutral-300">
            Deeper notes ({deeper.length})
          </summary>
          <div className="mt-4 space-y-6">
            {deeper.map((c) => (
              <ClaimCard key={c.id} claim={c} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
