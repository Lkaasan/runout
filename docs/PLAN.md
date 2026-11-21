# Album Deep-Dive App — Foundations Build Plan

Source: the "Album Deep-Dive App — Foundations Build Plan" doc (20 Nov 2026). Mockups: the "Album Deep-Dive App — Mockups" design canvas.

## Context

Build the foundations of a web app for focused, sit-down album listening. It plays an album through Apple Music and adds synced lyrics, timestamped "moments" and layered context (artist → album → track). Every piece of context is a sourced claim.

**Product principles**

- The listening experience is the product. Content exists to serve it.
- Depth follows the record: heavy context before playing, notes you can glance at during a track, short intros between tracks, the deep dive after.
- Every factual statement is a claim with at least one source. Facts, artist intent and interpretation are separate types and are displayed differently.
- The deep dive is a graph: people, samples and influences link across albums, and a linked track can be played right away.
- Two modes: **Listen** (minimal) and **Study** (everything).

**What "foundations" means:** a running web app where one hand-curated album can be played start to finish through all four session phases. Content loads from seed files into Postgres, and a minimal admin view lets claims be reviewed. Foundations do not include an AI content pipeline, community features or user accounts beyond Apple Music sign-in.

## Scope

**In foundations**

- Monorepo, local dev environment, CI
- Data model for artists, albums, tracks, people, claims, sources, moments and links, with migrations
- Seed-file importer for hand-written album content
- Read API (approved content only) and a typed frontend client
- Apple Music playback through MusicKit JS, behind a player interface, plus a fake player for dev and tests
- Listening screen with before / during / between / after phases, Listen and Study modes
- Deep-dive pages for people, samples and influences, with play-the-original
- Minimal admin claim-review queue
- Installable PWA shell

**Explicitly out (later)**

- AI source gathering, claim extraction and verification (interfaces only)
- Community contributions, reputation, verified artist accounts
- Licensed lyrics provider (stubbed behind an interface)
- Native iOS / Android apps, Spotify support
- User accounts, saved sessions, social features
- Payments

**Added after the plan was written (design for it, build after Milestone 6)**

- Live layer: performances of each song over time (official YouTube embeds, Apple Music live recordings, Internet Archive), with notes on what changed live.
- Photos from the album's era: Wikimedia Commons, fan uploads with a licence grant, label press photos. Each with photographer credit, licence, date and venue.
- Shows and setlists (setlist.fm: free for non-commercial use only; agree terms before charging).
- Store links, IDs, credits and licences only, never copies of photos or videos.

## Tech stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Frontend | Next.js (App Router), TypeScript, Tailwind | MusicKit JS v3 loaded client-side only |
| Backend | Python 3.12, FastAPI, Pydantic v2 | Python suits the future content pipeline |
| Database | Postgres 16, SQLAlchemy 2, Alembic | Graph edges as tables; no graph DB yet |
| API contract | OpenAPI from FastAPI → openapi-typescript | Types end to end |
| Tooling | uv (Python), pnpm (JS), docker-compose | Postgres runs in Docker locally |
| Quality | ruff, pytest, ESLint, Vitest, Playwright | GitHub Actions CI on every PR |
| Admin auth | Single password from env, HTTP basic | Replace when real accounts arrive |

```
album-app/
  apps/
    web/                 Next.js frontend
      src/player/        PlayerAdapter, MusicKitPlayer, FakePlayer
      src/lyrics/        LyricsProvider interface + stub
    api/                 FastAPI backend
      app/models/        SQLAlchemy models
      app/routes/        public + admin routes
      app/services/      claim rules, importer, token minting
      app/pipeline/      interfaces only (collector, extractor, verifier)
      alembic/
      tests/
  content/
    albums/<slug>/       album.yaml, tracks/NN-<slug>.yaml, sources.yaml
  docs/
    PLAN.md              this document
    adr/                 short decision records
  docker-compose.yml
  .env.example
  CLAUDE.md
```

## Data model

Everything a user reads is a **claim** attached to a subject, backed by **sources**, and placed in a session phase.

| Entity | Key fields | Notes |
| --- | --- | --- |
| artist | id, name, apple_music_id, musicbrainz_id | |
| album | id, slug, artist_id, title, release_date, apple_music_id, musicbrainz_release_id, artwork_url | |
| track | id, album_id, disc, number, title, duration_ms, apple_music_id, isrc | Match to Apple Music by ID, fall back to ISRC |
| person | id, name, musicbrainz_id | Producers, engineers, session players |
| credit | person_id, album_id or track_id, role | |
| source | id, kind, title, url, publisher, author, published_at, tier | kind: interview, liner_notes, documentary, press, social_post, database, book. tier: primary, secondary, tertiary |
| claim | id, subject_type, subject_id, type, body, body_long, phase, depth, status, confidence | type: fact, artist_intent, interpretation, trivia. phase: before, during, between, after. depth: listen, study. status: draft, approved, rejected |
| claim_source | claim_id, source_id, stance, excerpt, locator | stance: supports or contradicts. locator: page or video timestamp |
| moment | id, track_id, start_ms, end_ms, claim_id | A "listen for this" card shown at a timestamp |
| annotation | id, track_id, line_start, line_end, claim_id | Anchors a claim to lyric line indexes from the lyrics provider |
| link | from_type, from_id, to_type, to_id, relation, claim_id, target_apple_music_id | relation: samples, influenced_by, features, covers, references |

**Rules enforced in the service layer, with tests:**

1. A `fact` claim cannot be approved without at least one supporting source.
2. An `artist_intent` claim needs at least one supporting source of tier `primary`.
3. A claim with any contradicting source is flagged for review and cannot be auto-approved.
4. `interpretation` claims may have no source, but always display as interpretation, credited to their author.
5. Public endpoints only ever return `approved` claims.

Do not store lyric text in the database. Lyrics come from the `LyricsProvider` at runtime; annotations reference line indexes only.

## Backend API

| Method | Path | Returns |
| --- | --- | --- |
| GET | /health | Liveness check |
| GET | /albums | Curated album shelf |
| GET | /albums/{slug} | Album, tracklist, credits, `before` and `after` claims |
| GET | /albums/{slug}/tracks/{number} | Track, `between` intro, `during` moments, annotations, credits, links |
| GET | /entities/{type}/{id} | Deep-dive card with claims and links in both directions |
| GET | /musickit/developer-token | Short-lived MusicKit developer token (cached server-side) |
| GET | /admin/claims?status=draft | Review queue with sources and any contradictions |
| PATCH | /admin/claims/{id} | Approve, reject or edit; 422 if a claim rule fails |
| POST | /admin/import/{slug} | Re-import an album's seed files |

Filter by `depth` with a query param (`?depth=listen`). Generate the TypeScript client from the OpenAPI schema in CI so the two can't drift.

## Frontend

| Route | Purpose |
| --- | --- |
| / | Curated album shelf |
| /album/[slug] | The session: before, during, between and after phases |
| /entity/[type]/[id] | Deep-dive page for a person, sample, influence or linked track |
| /admin | Claim review queue (basic auth) |

- **Before:** artwork, the artist's situation at the time, how the album was made. "Start listening" connects Apple Music and queues the album.
- **During:** synced lyrics with annotation markers; moment cards fade in at `start_ms` and out after `end_ms` (or ~12 s).
- **Between:** a short intro card for the next song that fades out after ~8 s unless tapped.
- **After:** reception, legacy, interviews, rabbit holes.
- Artist / Album / Track (and later Live) layers sit one tap away without stopping playback.
- Listen / Study toggle; Study shows everything. Remember the choice in localStorage.
- "Play the original" pauses the album, plays the linked track, and "Back to the album" resumes at the saved position.
- One `PlaybackProvider` context owns the player; timing comes from the player's time events, not your own timers.
- Calm by default: dark theme, large type, no shuffle, respect `prefers-reduced-motion`. Laptop and tablet first, phone second.

## Apple Music integration

Check every API detail against Apple's current MusicKit docs before coding.

- Backend mints an ES256 JWT developer token from the .p8 key, Team ID and Key ID (env only), caches it and re-mints before expiry. Served from `GET /musickit/developer-token`, CORS limited to the web origin.
- Client loads MusicKit v3 client-side, configures it with the token, calls `authorize()` on "Connect Apple Music", queues the album in order with shuffle off, and feeds playback events into `PlaybackProvider`.
- Non-subscribers get previews only: detect it, show a gentle banner, keep the content available.

```ts
interface PlayerAdapter {
  connect(): Promise<void>;
  loadAlbum(appleMusicAlbumId: string): Promise<void>;
  playTrack(appleMusicTrackId: string): Promise<void>;
  play(): Promise<void>;
  pause(): Promise<void>;
  seek(ms: number): Promise<void>;
  state(): { trackId: string | null; positionMs: number; playing: boolean; previewOnly: boolean };
  on(event: "time" | "track" | "state", cb: () => void): () => void;
}
```

Ship a `FakePlayer` with a fake clock and real track durations; dev and Playwright tests run against it.

## Content: seed files and review

```yaml
number: 3
title: "<track title>"
apple_music_id: "<id>"
isrc: "<isrc>"
between:
  claim: intro
moments:
  - at: "2:14"
    until: "2:30"
    claim: drum-sample
annotations:
  - lines: [12, 14]
    claim: verse-meaning
links:
  - relation: samples
    to: { type: track, apple_music_id: "<id>", title: "<original>" }
    claim: drum-sample
claims:
  - id: drum-sample
    type: fact
    depth: listen
    body: "<one or two sentences>"
    sources:
      - ref: <source-id from sources.yaml>
        stance: supports
        excerpt: "<short excerpt>"
        locator: "12:40"
    reviewed: true
```

- Importer validates with Pydantic and reports file, path and reason for every error.
- Upserts by stable IDs (`<album-slug>/<claim-id>`) so re-importing is safe.
- `reviewed: true` claims import as approved only if they pass the claim rules; everything else is draft.
- Run as `uv run python -m app.seed import <slug>` and through the admin endpoint.
- Pipeline stubs in `app/pipeline/`: `SourceCollector`, `ClaimExtractor`, `ClaimVerifier` (interfaces and docstrings only).

## Milestones

One PR per milestone; stop for review after each.

1. **Repo and tooling** ✅
    - Monorepo layout, docker-compose Postgres, `.env.example`, CLAUDE.md, CI for both apps.
    - Done when: one command starts Postgres, `/health` responds, the web app renders an empty shelf, CI is green.
2. **Data model, migrations, importer**
    - All entities, Alembic migrations, claim rules, YAML importer, one placeholder two-track album in `content/`.
    - Done when: the importer loads the placeholder album; broken YAML fails with clear errors; tests cover all five claim rules.
3. **Read API and typed client**
    - Public and admin routes, `depth` filtering, generated TypeScript client.
    - Done when: endpoint tests pass, draft claims never appear on public routes, CI fails if the generated client is stale.
4. **Player foundation**
    - `PlayerAdapter`, `FakePlayer`, `MusicKitPlayer`, developer-token endpoint, `PlaybackProvider`.
    - Done when: FakePlayer plays the album through in dev without Apple credentials; with real credentials a subscriber can play the real album in Chrome and Safari.
5. **Listening screen**
    - Before, during, between and after phases, moments, lyrics stub with annotations, layer sheet, Listen/Study toggle.
    - Done when: a Playwright test on FakePlayer asserts each moment appears within 500 ms of its timestamp, including after a seek.
6. **Deep-dive graph**
    - Entity pages, links in both directions, play-the-original and return-to-album.
    - Done when: from a sample moment a user reaches the original, plays it, and returns to the album at the saved position.
7. **Admin review**
    - Review queue with sources, contradictions and inline approve/reject/edit.
    - Done when: approving a sourceless fact is blocked with the API's error shown in the UI.
8. **PWA and polish**
    - Manifest, icons, installable shell, reduced-motion support, tablet layout.
    - Done when: it installs from Chrome and iPad Safari and passes an accessibility check with no serious issues.

## Before Milestone 4

- [ ] Join the Apple Developer Program and create a MusicKit key (.p8), noting the Team ID and Key ID
- [ ] Check whether full playback for public users needs an organisation developer account
- [ ] Pick the first album: one with a well-documented backstory and interviews you can source
- [ ] Write its content in the seed format, with every fact sourced
- [ ] Choose a working name for the app
- [ ] Decide hosting before the first public link
- [ ] Pick a licensed lyrics route (Musixmatch or LyricFind) before any public launch
