import Link from "next/link";
import type { ArtistSummary } from "@/api/client";
import { AlbumCover } from "./AlbumCover";

export function ArtistCard({ artist }: { artist: ArtistSummary }) {
  return (
    <Link
      href={`/artist/${artist.slug}`}
      className="flex gap-4 rounded-lg p-3 hover:bg-neutral-900"
    >
      <AlbumCover url={artist.artwork_url} title={artist.name} className="size-20" />
      <div className="min-w-0">
        <div className="text-xl">{artist.name}</div>
        <div className="text-neutral-400">
          {artist.album_count === 1 ? "1 album" : `${artist.album_count} albums`}
        </div>
      </div>
    </Link>
  );
}
