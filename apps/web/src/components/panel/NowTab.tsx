"use client";

import { useState } from "react";
import type { TrackDetail } from "@/api/client";
import { formatMs } from "@/lib/format";
import { heardMoments, introVisible, visibleMoments } from "@/lib/moments";
import { ClaimCard } from "../ClaimCard";

type Moment = TrackDetail["moments"][number];

/**
 * Live view: cards for the moment in progress, from the player's position only.
 * Browse view (not playing this song): everything to listen for, without timing.
 */
export function NowTab({
  detail,
  positionMs,
  live,
}: {
  detail: TrackDetail;
  positionMs: number;
  live: boolean;
}) {
  // Tapping the intro keeps it open. State is reset by keying this component on the track.
  const [introTapped, setIntroTapped] = useState(false);

  const showIntro = detail.between && (!live || introVisible(positionMs, introTapped));

  if (!live) {
    return (
      <div className="space-y-6">
        {detail.between && <ClaimCard claim={detail.between} />}
        {detail.moments.length === 0 ? (
          <p className="text-neutral-500">Nothing to listen for in this song yet.</p>
        ) : (
          <>
            <h3 className="text-xs uppercase tracking-widest text-neutral-500">Listen for</h3>
            {detail.moments.map((m) => (
              <MomentCard key={m.start_ms} moment={m} />
            ))}
          </>
        )}
      </div>
    );
  }

  const visible = visibleMoments(detail.moments, positionMs);
  const heard = heardMoments(detail.moments, positionMs);
  // Deeper notes never interrupt: they show as a small chip instead of a full card.
  const cards = visible.filter((m) => m.claim.depth === "listen");
  const chips = visible.filter((m) => m.claim.depth === "study");

  return (
    <div className="space-y-6">
      {showIntro && detail.between && (
        <div
          onClick={() => setIntroTapped((t) => !t)}
          className="panel-fade cursor-pointer"
          title="Tap to keep or dismiss"
        >
          <ClaimCard claim={detail.between} />
        </div>
      )}

      {cards.length === 0 && chips.length === 0 && !showIntro && (
        <p className="text-neutral-500">Listening… notes appear here as the song plays.</p>
      )}

      {cards.map((m) => (
        <div key={m.start_ms} className="panel-fade">
          <MomentCard moment={m} />
        </div>
      ))}

      {chips.map((m) => (
        <details key={m.start_ms} className="panel-fade group">
          <summary className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-neutral-700 px-3 py-1 text-sm text-neutral-300 hover:border-neutral-400">
            Deeper note · {formatMs(m.start_ms)}
          </summary>
          <div className="mt-3">
            <ClaimCard claim={m.claim} />
          </div>
        </details>
      ))}

      {heard.length > 0 && (
        <section aria-label="Heard so far">
          <h3 className="text-xs uppercase tracking-widest text-neutral-500">Heard so far</h3>
          <ul className="mt-3 space-y-2">
            {heard.map((m) => (
              <li key={m.start_ms}>
                <details className="group">
                  <summary className="cursor-pointer text-neutral-300 hover:text-neutral-100">
                    <span className="mr-2 text-sm tabular-nums text-neutral-500">
                      {formatMs(m.start_ms)}
                    </span>
                    {m.claim.body}
                  </summary>
                  <div className="mt-3">
                    <ClaimCard claim={m.claim} />
                  </div>
                </details>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function MomentCard({ moment }: { moment: Moment }) {
  return (
    <div>
      <div className="mb-1 text-sm tabular-nums text-neutral-500">At {formatMs(moment.start_ms)}</div>
      <ClaimCard claim={moment.claim} />
    </div>
  );
}
