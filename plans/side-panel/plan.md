# Plan: the side panel and its tabs

## Context

Playback now exists (PR #4: `PlaybackProvider`, `FakePlayer`, `MusicKitPlayer`, `PlayerBar`). The album page is still one long scrolling column that prints every track's content inline. The product vision is different: press play, and a panel beside the player shows what you can read about the song that is playing, split into tabs. This plan settles what the panel does and what the first tabs are, and slices the work so each slice is one PR.

Decisions made with the user:
- **First tabs:** Now, Meaning, Lyrics, Making, Sources.
- **No Listen / Study toggle.** Depth is embedded: every card shows the short version, and a "Go deeper" disclosure reveals the long body, sources and deeper notes in place. This replaces the plan's two-mode principle, so `docs/PLAN.md` and `docs/FEATURES.md` (S2) need updating.
- **The panel follows the playing song**, with a browse pin: click another song to read about it without stopping playback, and a "Back to now playing" button returns.

## Layout

- Laptop and tablet landscape: two columns. Left: album header and tracklist (title, duration, play button, the current song highlighted). Right: the panel, sticky, full height above the existing fixed `PlayerBar`.
- Tablet portrait and phone: the panel becomes a bottom sheet over the page, collapsed to a one-line peek showing the latest moment card.
- The long inline per-track content on `apps/web/src/app/album/[slug]/page.tsx` goes away; it lives in the panel instead. "Before" and "After" album-level claims stay on the page (they are not tied to a song). **Superseded:** they now live in an Album tab in the panel, and the left column is only the tracklist (see the restructure PR).
- Tab bar follows the ARIA tabs pattern (tablist, arrow keys). The last chosen tab is remembered per browser (localStorage, wrapped in try/catch). Tabs with nothing to show for the current song are hidden, except Now and Lyrics.

## Panel behaviour

- Source of truth for "which song" is `usePlayback().state.trackId` from `apps/web/src/player/PlaybackProvider.tsx`. A small `PanelProvider` adds one piece of state: `pinnedTrackId | null`. Null means follow the playing song.
- Clicking a song's title in the tracklist pins it; a "Back to now playing" chip appears while pinned and the song's title is shown at the top of the panel either way.
- Panel data is fetched client-side per track (`GET /albums/{slug}/tracks/{number}`), cached in memory so switching is instant and the next track is prefetched.

## The tabs

| Tab | What it shows | Data today |
|---|---|---|
| **Now** | Moment cards fade in at `start_ms` and out after `end_ms` (or about 12 s); a "heard so far" list under them so nothing is lost if you look away; the between-songs intro for the next song (fades after about 8 s unless tapped) | `moments`, `between` already returned |
| **Meaning** | What the song is about, grouped by who is speaking: *In the artist's words* (artist intent), *Documented* (facts), *Readings* (interpretations, credited to their author), trivia last. Fact, intent and interpretation keep their different styling from `ClaimCard` | Needs all of a track's claims (see API change) |
| **Lyrics** | Lyrics from `LyricsProvider`, scrolling and synced to position when the provider has timings; a marker on lines with annotations; click to read | `annotations` returned; lyrics from the stub until licensed |
| **Making** | Credits (track and album level), studio, how it was recorded | `credits` returned; making claims need a topic (see API change) |
| **Sources** | A bibliography for the song: every source behind what was shown, its tier, the claims it backs, any that dispute | Derivable from the claims already returned |

Depth, embedded: each `ClaimCard` shows `body`. "Go deeper" expands `body_long`, excerpts and sources. Claims with `depth: study` are not hidden; they sit under a quiet "Deeper notes (n)" disclosure in their tab, and in Now they appear as a small chip at their timestamp instead of a full card, so a deep note never interrupts listening. Validate this with a mockup before polishing.

## API and data changes

1. **Track detail returns all approved claims on the track.** Add `claims: ClaimOut[]` to `TrackDetail` in `apps/api/app/schemas.py`, built with `serialize.public_claims` in `apps/api/app/routes/albums.py`. Needed by Meaning, Making and Sources. Moments, annotations and `between` stay as they are.
2. **Claim topic.** Today nothing says whether a fact is about the song's meaning or how it was made. Add an optional `topic` (`meaning`, `making`, `context`) on `Claim`: a model column and Alembic migration in `apps/api/app/models/entities.py`, a field in `apps/api/app/services/seed_schema.py`, and the importer in `apps/api/app/services/importer.py`. Default when omitted: `artist_intent` and `interpretation` go to `meaning`, `fact` and `trivia` go to `making`. The placeholder album under `content/albums/placeholder-album/` gets a couple of explicit topics so the tabs have something to show.
3. The `depth` query parameter stops being used by the web app (it fetches everything and the UI decides). Keep it on the API.
4. Run `pnpm gen:api` and commit `openapi.json` and `schema.d.ts` (CI checks they match).

## Build slices

Each slice is one PR, built and verified on the `FakePlayer`.

1. **Panel shell and Now tab.** Two-column layout, `PanelProvider` with follow and pin, tab bar with persistence, the Now tab with timed moment cards, the between intro, and the "heard so far" list. Remove the mode toggle (`parseMode`, the toggle in the nav, and the `study` prop on `ClaimCard`) and replace it with the embedded "Go deeper" disclosure. Tick FEATURES S1, S3, S4.
2. **Meaning tab.** API change 1 and 2, then the tab.
3. **Lyrics tab.** Dev lyrics stub with made-up lines, the tab, and annotation markers. Real lyrics wait for a licence (FEATURES L1).
4. **Making and Sources tabs.**

## Reuse

- `usePlayback()` and `PlaybackProvider` in `apps/web/src/player/PlaybackProvider.tsx` for song and position (timing from player events only, per the plan).
- `ClaimCard` in `apps/web/src/components/ClaimCard.tsx`, extended with the disclosure.
- `formatMs` in `apps/web/src/lib/format.ts`, the typed `api` client in `apps/web/src/api/client.ts`, and `LyricsProvider` with its stub in `apps/web/src/lyrics/LyricsProvider.ts`.
- `FakePlayer` for tests; its injectable clock makes timing tests deterministic.

## Preview caveat

With Apple previews (about 30 s per song) moments after 0:30 cannot fire. The placeholder moment is at 0:45, so test on the `FakePlayer`, which plays full durations.

## Verification

- Pure function `visibleMoments(moments, positionMs, seenIds)` in `apps/web/src/lib/`, unit-tested with Vitest: appears at `start_ms`, gone after `end_ms` or 12 s, correct after a seek forward and back.
- Component tests for tab persistence, follow versus pin, and hidden empty tabs.
- API tests: `claims` on track detail contains approved claims only; `topic` defaults and overrides; migration matches models (existing drift test).
- Manual: `pnpm dev`, open `/album/placeholder-album`, press play on the fake player, watch the moment card appear at 0:45, click another song's title and confirm the pin and "Back to now playing", reload and confirm the tab is remembered.
- A Playwright check (moment within 500 ms of its timestamp, including after a seek) once Playwright is added; it is the done-criterion for the plan's Milestone 5.
- `pnpm lint`, `pnpm test`, `pnpm gen:api` leaves no diff.

## Docs to update when building

- `docs/PLAN.md`: replace the two-mode principle and the Listen/Study toggle line with embedded depth.
- `docs/FEATURES.md`: rewrite S2 as "Embedded depth", tick items as they ship, add the tab decisions.
- `docs/ARCHITECTURE.md`: describe the panel and the follow/pin state.

## Open items (not blocking slice 1)

- Whether study-depth moments should appear as chips (as proposed) or as normal cards.
- Whether the Artist, Album and Track layers (FEATURES S5) become a scope switch inside Meaning later.
- Later tabs, once their data exists: Connections, Live, Photos, Community (the last needs accounts).
