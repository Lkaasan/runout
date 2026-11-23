import type { TrackDetail } from "@/api/client";
import { formatMs } from "@/lib/format";
import { ClaimCard } from "../ClaimCard";

/** The moments in a song worth noticing, in the order they occur, each with its timestamp. */
export function ListenForTab({ detail }: { detail: TrackDetail }) {
  const moments = [...detail.moments].sort((a, b) => a.start_ms - b.start_ms);
  if (moments.length === 0) {
    return <p className="text-neutral-500">Nothing to listen for in this song yet.</p>;
  }
  return (
    <div className="space-y-6">
      {moments.map((m) => (
        <div key={m.start_ms}>
          <div className="mb-1 text-sm tabular-nums text-neutral-500">
            At {formatMs(m.start_ms)}
          </div>
          <ClaimCard claim={m.claim} />
        </div>
      ))}
    </div>
  );
}
