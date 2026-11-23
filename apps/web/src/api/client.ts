import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Typed client generated from the API's OpenAPI schema (`pnpm gen:api`). */
export const api = createClient<paths>({
  baseUrl,
  // Content changes when claims are reviewed; never serve a stale page.
  fetch: (req) => fetch(req, { cache: "no-store" }),
});

type Schemas = components["schemas"];
export type AlbumSummary = Schemas["AlbumSummary"];
export type AlbumDetail = Schemas["AlbumDetail"];
export type TrackDetail = Schemas["TrackDetail"];
export type Claim = Schemas["ClaimOut"];
export type ClaimSource = Schemas["ClaimSourceOut"];
export type Link = Schemas["LinkOut"];
export type ArtistSummary = Schemas["ArtistSummary"];
export type ArtistDetail = Schemas["ArtistDetail"];
export type SearchResults = Schemas["SearchResults"];
