"use client";

import { useState } from "react";

/**
 * An album's cover, hot-linked from `artwork_url` (never copied into the repo). If there is no
 * address, or the image fails to load, a quiet placeholder keeps the layout steady.
 */
export function AlbumCover({
  url,
  title,
  className = "size-24",
}: {
  url: string | null | undefined;
  title: string;
  /** Tailwind size classes, e.g. "size-24". The cover is always square. */
  className?: string;
}) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const failed = failedUrl === url;

  if (!url || failed) {
    return (
      <div
        role="img"
        aria-label={`${title} (no cover available)`}
        className={`${className} shrink-0 rounded bg-neutral-800`}
      />
    );
  }

  return (
    // A plain <img>: the address redirects to an archive host, so Next's image optimiser,
    // which wants fixed hosts, is not a fit.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={`${title} album cover`}
      width={500}
      height={500}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailedUrl(url)}
      className={`${className} shrink-0 rounded bg-neutral-800 object-cover`}
    />
  );
}
