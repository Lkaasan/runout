import Link from "next/link";
import type { AlbumSummary } from "@/api/client";
import { AlbumCover } from "./AlbumCover";

export function AlbumCard({
  album,
  showArtist = true,
}: {
  album: AlbumSummary;
  showArtist?: boolean;
}) {
  return (
    <Link href={`/album/${album.slug}`} className="flex gap-4 rounded-lg p-3 hover:bg-neutral-900">
      <AlbumCover url={album.artwork_url} title={album.title} className="size-20" />
      <div className="min-w-0">
        <div className="text-xl">{album.title}</div>
        {showArtist && <div className="text-neutral-400">{album.artist}</div>}
        {album.release_date && (
          <div className="text-sm text-neutral-500">{album.release_date.slice(0, 4)}</div>
        )}
      </div>
    </Link>
  );
}
