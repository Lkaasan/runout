const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type AlbumSummary = {
  slug: string;
  title: string;
  artist: string;
  artwork_url: string | null;
};

// Replaced by the generated OpenAPI client in Milestone 3.
export async function fetchAlbums(): Promise<AlbumSummary[]> {
  const res = await fetch(`${API_URL}/albums`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /albums failed: ${res.status}`);
  return res.json();
}
