# Plan: play an album (Milestone 4 + a minimal player UI)

## Context

The app can show an album's content (Milestones 1–3, merged) but cannot play anything. The feature list in the original plan didn't make it to this computer, so for now the goal is narrow: **get the app to a state where an album can be played start to finish.** This is [PLAN.md](../../Documents/Projects/runout/docs/PLAN.md) Milestone 4 (player foundation), plus just enough UI on the existing album page to use it. The timed phases, moment cards, lyrics, entity pages, admin UI and PWA (Milestones 5–8) stay out.

Done when:
- With no Apple credentials, `pnpm dev` lets you press play on the placeholder album and hear/see it advance through both tracks (FakePlayer).
- With Apple credentials and a real album seeded, the album plays as ~30 s previews per track (full length for subscribers comes later, see "Decision" below).

## Decision: preview-first, full length later

For now, ~30 s previews are good enough for testing. Build and verify against previews, but keep the code ready for full playback so the switch needs no rewrite:
- Treat `previewOnly` as normal state, not an error. The banner reads "Previews only (about 30 s per track)" and never blocks the UI.
- Keep timing logic (scrubber, durations) driven by player events and the track's real `duration_ms`, never by an assumed 30 s. Clamp the scrubber to the actual playable length the player reports.
- FakePlayer keeps full-length behaviour (real durations) so moment timing in Milestone 5 can be tested without a subscription.
- **Migration to full length (later, no code change expected):** a subscriber signs in via "Connect Apple Music" and `previewOnly` flips to false. Remaining work then is only: confirm full playback in Chrome and Safari over https, and decide on organisation developer account if public users need it (PLAN.md "Before Milestone 4" checklist). Record this as a short "Going to full length" note in `docs/ARCHITECTURE.md`.
- Moment cards at timestamps past 0:30 can't fire in preview mode; that's expected until full length is on.

## Scope

**In:** `PlayerAdapter` implementations, `PlaybackProvider`, developer-token endpoint, a player bar and per-track play buttons on `/album/[slug]`, tests.
**Out:** before/during/between/after phases, moment timing, lyrics, "play the original", admin UI, PWA. Don't touch claim rules or the importer.

## Steps

### 0. Save this plan in the repo
Per standing preference: copy this plan to `plans/player-foundation/plan.md` in the repo before any code changes. Implement on Sonnet.

### 1. Verify Apple details first (CLAUDE.md rule)
Before writing token or MusicKit code, check current Apple docs for: developer-token JWT header/claims (`alg: ES256`, `kid`, `iss`, `iat`, `exp`, max lifetime), MusicKit JS v3 script URL and `MusicKit.configure` shape, `authorize()`, `setQueue({ album })`, playback events (`playbackTimeDidChange`, `nowPlayingItemDidChange`, `playbackStateDidChange`), and how to detect non-subscribers / preview-only. Record anything surprising in the PR description.

### 2. Backend: developer-token endpoint
- `apps/api/app/config.py`: add `apple_team_id`, `apple_key_id`, `apple_private_key_path` (already in `.env.example`).
- New `apps/api/app/services/musickit_token.py`: mint ES256 JWT from the .p8, cache in memory, re-mint ~1 day before expiry.
- New `apps/api/app/routes/musickit.py`: `GET /musickit/developer-token` → `{token, expires_at}`; returns **503** with a clear message when the three env values are missing (this is how the web app knows to fall back to FakePlayer). Register in `main.py`.
- `apps/api/pyproject.toml`: add `pyjwt[crypto]` (via `uv add`).
- Tests: `apps/api/tests/test_musickit.py`: 503 when unconfigured; with a throwaway generated EC key, the token decodes with the right header/claims; second call is served from cache.
- Run `pnpm gen:api` and commit `openapi.json` + `schema.d.ts` (CI checks freshness).

### 3. Web: player layer in `apps/web/src/player/`
- `FakePlayer.ts`: implements `PlayerAdapter` with an injectable clock; takes track list with real `duration_ms`; advances to the next track at the end; emits `time` / `track` / `state`. Playable with no audio.
- `MusicKitPlayer.ts`: loads MusicKit v3 script client-side only, fetches the token from the API, configures, `connect()` = `authorize()`, `loadAlbum()` queues the album in order with shuffle off, maps MusicKit events to the adapter events, sets `previewOnly` for non-subscribers.
- `PlaybackProvider.tsx` (client context): owns one adapter, exposes state + actions. Picks the adapter on mount: try the token endpoint; 200 → `MusicKitPlayer`, 503/failure → `FakePlayer`. Override with `NEXT_PUBLIC_PLAYER=fake|musickit` for dev and tests.
- Unit tests (Vitest) for `FakePlayer`: plays through, seek, auto-advance, track-change event, subscribe/unsubscribe. No test may need Apple credentials or a browser audio device.

### 4. Web: minimal playback UI on the album page
- `apps/web/src/app/album/[slug]/page.tsx` stays a server component; wrap its content in `PlaybackProvider` (passing the album's `apple_music_id` and tracks).
- New client components in `apps/web/src/components/`: `PlayerBar` (fixed bottom: current track, play/pause, scrub bar, elapsed/total via existing `formatMs`, "Connect Apple Music" button when needed, a gentle banner when `previewOnly`) and `TrackPlayButton` (per-track play next to each title).
- No shuffle control. Respect `prefers-reduced-motion`. Keep the existing dark, calm styling.

### 5. Config and docs
- `.env.example`: change the "(Milestone 4)" comment; add optional `NEXT_PUBLIC_PLAYER`.
- Update the status line and "Where the rest fits" in `docs/ARCHITECTURE.md` and tick Milestone 4 in `docs/PLAN.md`.

## Real-album note
The placeholder album has fake Apple IDs (`0000000001`), so real playback can't be tested with it. To try Apple playback you need an Apple Developer MusicKit key (.p8, Team ID, Key ID) and an album seeded under `content/albums/<slug>/` with real `apple_music_id`s. Until then FakePlayer covers dev and tests.

## Verification
1. `pnpm lint` and `pnpm test` pass (new FakePlayer and token tests included); `pnpm gen:api` leaves no diff.
2. `pnpm setup && pnpm dev`, open `/album/placeholder-album`: play, pause, seek, and let track 1 run into track 2; the player bar and play buttons follow along.
3. With real credentials in `.env` and a real album imported: play the album in Chrome and Safari; each track plays a ~30 s preview, advances to the next, and the preview banner shows. (Full-length check is deferred.)
4. Confirm the .p8 and `.env` are not staged.

## Delivery
Per CLAUDE.md: one PR for this milestone (branch `milestone-4-player`), then stop for review. Commit trailer per the session attribution.
