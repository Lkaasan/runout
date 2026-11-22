# Feature backlog

The living list of what we want to build. Tick items off as they ship, add new ideas at the bottom of the right section, and keep the status line current.
[PLAN.md](PLAN.md) holds the original foundations plan; this file is where it grows from here.

**How to use it**
- `[x]` shipped, `[~]` in progress, `[ ]` not started. Put the PR link next to anything finished.
- IDs (`P1`, `S3`...) are stable so we can refer to them in PRs and chat. Don't renumber.
- One feature per PR where possible. Features are grouped by area, not ordered: you decide what to build next and move it into **Next up**.
- Anything with a ⚠️ has a legal, licensing or account decision to make before building.

**Status (2026-11-22):** foundations M1 to M4 are merged (read API, admin API, importer, player). The album page has the tracklist on the left and all information on the right, in a panel with Now, Meaning and Album tabs. Lyrics, Making and Sources are next, per [plans/side-panel/plan.md](../plans/side-panel/plan.md).

## The vision

Press play on an album and it plays song by song. While a song plays, a panel on the right shows what you can read about it, organised in tabs. The listening experience comes first; content serves it.

```
┌──────────────────────────────────────────┬───────────────────────┐
│  Album art                               │ [Now][Lyrics][Meaning]│
│  Track list, current song highlighted    │ [Making][Links][Live] │
│                                          │ ───────────────────── │
│  ◀◀   ▶ / ❚❚   ▶▶    ─────●────  2:14   │  tab content          │
│                                          │  (moment cards fade   │
│                                          │   in as the song      │
│  [Listen | Study]                        │   plays)              │
└──────────────────────────────────────────┴───────────────────────┘
```

---

## Play the music

Foundations milestone 4.

- [x] **P1 Player interface and fake player.** Use the existing `PlayerAdapter` interface. Build a `FakePlayer` with a fake clock and real track durations so everything below can be built and tested without Apple credentials.
- [x] **P2 Playback state provider.** One `PlaybackProvider` context owns the player. All timing comes from the player's time events, never our own timers.
- [x] **P3 Player bar.** Play/pause, next/previous, seek, current time, track title. Press play on the album to start track 1; songs play in order, no shuffle.
- [~] **P4 Apple Music playback ⚠️.** (built in PR #4, not yet tested with real credentials) `MusicKitPlayer` using MusicKit JS, plus `GET /musickit/developer-token` on the API (ES256 JWT from the .p8 key, cached). Needs the Apple Developer Program account and a MusicKit key. Match tracks by Apple Music ID, fall back to ISRC.
- [x] **P5 Non-subscriber handling.** Detect preview-only playback, show a gentle banner, keep the content readable.
- [x] **P6 Track highlighting and queue.** Current song highlighted in the tracklist; click a song to jump to it.

**Decision needed ⚠️:** does full playback for public users need an organisation developer account? (Open since the plan.) Also pick the first real album.

## The side panel and its tabs

The core product surface. Foundations milestone 5. The panel shell comes before any individual tab.

- [x] **S1 Side panel shell.** Tracklist on the left, information panel on the right on laptop and tablet; on small screens it stacks above the tracklist (a true bottom sheet is still to do, see X3). Tab bar, remembers the last tab, follows the playing song with a browse pin, never interrupts playback.
- [x] **S2 Embedded depth.** Replaces the Listen/Study toggle. Cards show the short body with a "Go deeper" disclosure; study-depth notes sit under "Deeper notes" and show as small chips in Now.
- [~] **S3 "Now" tab: moments.** (built and unit-tested; the Playwright 500 ms check is still to do) Cards fade in at `start_ms` and out after `end_ms` (or about 12 seconds), including after a seek. Respect `prefers-reduced-motion`. Test: each moment appears within 500 ms of its timestamp on the fake player.
- [x] **S4 Between-songs intro.** A short intro card for the next song that fades after about 8 seconds unless tapped.
- [ ] **S5 Layers.** Artist, album and track layers one tap away without stopping playback.

### Proposed tabs

| Tab | What it shows | Depends on |
|-----|---------------|------------|
| **Now** | Timed moment cards for the current song | S3 |
| **Lyrics** | Synced lyrics with markers where annotations exist | L1 to L3 |
| **Meaning** | Sourced explanation of the song: artist's own words first, then documented background, then interpretations, each styled differently | Existing claims |
| **Community** | Other listeners' readings of the song or a line ⚠️ | C1 to C4 |
| **Making** | How it was recorded, who played what, credits, gear, studio | Credits data |
| **Connections** | Samples, influences, covers, people; click to play the original | G1 to G3 |
| **Live** | Performances over time and photos from the era | V1 to V5, F1 to F5 |
| **Sources** | Every source behind what you have read, with stance and excerpts | Existing claims |

Open question: eight tabs is a lot. Probably start with Now, Lyrics, Meaning, Making and Sources, then add the rest as they earn their place. Check this with a mockup before building.

## Lyrics

- [ ] **L1 Lyrics provider ⚠️.** Keep the `LyricsProvider` interface. Choose a licensed route (Musixmatch or LyricFind) before any public launch. Lyrics are never stored in our database or repo.
- [ ] **L2 Lyrics tab.** Scrolling lyrics for the current song, synced to playback when the provider has timings, plain otherwise.
- [ ] **L3 Annotation markers.** Lines with an annotation get a marker; click to read the claim. Annotations reference line indexes only.
- [ ] **L4 Lyrics page.** A full-page lyrics view for reading without the player, with the same annotations.
- [ ] **L5 Dev lyrics stub.** Tiny fake provider with made-up lines so the above can be built and tested before a licence exists.

## Content depth

Making the content that exists richer and more trustworthy.

- [ ] **K1 Real first album.** Pick it, write its seed content with every fact sourced. *Animals* research is already in [research/](research/); the song-meaning gaps list what to chase.
- [ ] **K2 Primary-source retrieval.** For each artist-intent claim, find the original interview or book and record it as a primary source. This is the hardest and most valuable content step.
- [ ] **K3 Credits and "Making" data.** Per-track credits (players, engineers, studios, gear) from seed files and MusicBrainz.
- [ ] **K4 Source-conflict display.** Show disputed claims honestly in Study mode (already styled; needs review).
- [ ] **K5 Album shelf and artwork.** Real artwork and a better shelf page.

## Connections (the deep-dive graph)

Foundations milestone 6.

- [ ] **G1 Entity pages.** People, samples and influences, with links in both directions.
- [ ] **G2 Play the original.** From a sample moment, pause the album, play the linked track, then "Back to the album" resumes at the saved position.
- [ ] **G3 Graph browsing.** Follow links across albums and artists.

## Live layer and photos ⚠️

Your idea to see the band at shows from around the time the album came out, plus performances of each song.

- [ ] **F1 Photo data model.** Store links, IDs, credits and licences only, never copies. Fields: image URL at source, photographer, licence, date, venue, source page.
- [ ] **F2 Photos from open sources.** Wikimedia Commons first (clear licences). Show photographer credit and licence on every image.
- [ ] **F3 Photos tab.** Era-matched gallery for the album (shows around release, tour, studio), grouped by date or tour leg.
- [ ] **F4 Photo rights decisions ⚠️.** Press photos from labels, fan uploads with a licence grant, and anything from photographers directly each need an explicit rule before use.
- [ ] **V1 Performances data.** Per song: official YouTube embeds, Apple Music live recordings, Internet Archive recordings, with notes on what changed live.
- [ ] **V2 Live tab.** Performances of the current song over time.
- [ ] **V3 Shows and setlists ⚠️.** setlist.fm data is free for non-commercial use only; agree terms before charging.
- [ ] **V4 Tour timeline.** Where the band was while the album came out.

## Community ⚠️

Needs user accounts, which the foundations plan explicitly left out. Decide the rules before building anything.

- [ ] **C1 Accounts.** Sign-in beyond Apple Music, so contributions have an author.
- [ ] **C2 Submit a reading.** Let a listener write their interpretation of a song or a lyric line. These are always shown as interpretation, credited to the author, never as fact.
- [ ] **C3 Moderation.** Review queue for submissions (reuse the admin review flow), reporting, removal.
- [ ] **C4 Community tab.** Show approved readings per song and per line, with votes or "this helped me".
- [ ] **C5 Fact suggestions.** Let people propose a fact with a source; it goes through the same claim rules as everything else.
- [ ] **C6 Reputation and verified artists.** Later.

**Decisions needed ⚠️:** who may post, whether readings need approval before showing, how to handle abuse, and what the legal terms say about user content. Also whether community readings can ever be quoted back as lyrics-adjacent content (they must not reproduce lyric text).

## Admin and operations

- [ ] **A1 Admin review UI.** Review queue with sources, contradictions and inline approve, reject and edit. Show the API's rule error when approval is blocked.
- [ ] **A2 Content importer from the browser.** Re-import an album from the admin page and show the import report.
- [ ] **A3 Hosting.** Decide where it runs before the first public link.
- [ ] **A4 Real admin auth.** Replace the single shared password once there are accounts.

## Polish

- [ ] **X1 PWA shell.** Manifest, icons, installable on Chrome and iPad Safari.
- [ ] **X2 Accessibility pass.** No serious issues in an automated check; keyboard control of the player.
- [ ] **X3 Tablet and phone layouts.** Laptop and tablet first, phone second.
- [ ] **X4 Calm design pass.** Dark theme, large type, motion respects reduced-motion.
- [ ] **X5 Search.** Find a song, person or claim.

## Later and maybe

- [~] **Z1 AI source gathering and claim extraction (the information finder).** Plan: [plans/information-finder/plan.md](../plans/information-finder/plan.md). Must keep human review and the claim rules.
  - [x] Z1.0 Spec, gold set (Animals) and scoring: `uv run python -m app.research score animals --oracle`
  - [x] Z1.1 No-AI collectors (MusicBrainz, Wikipedia) and page cache: `uv run python -m app.research collect animals`
  - [x] Z1.2 Extractor (Claude Code, subscription) and deterministic code checks (verbatim excerpt match, tiers, lyric guard): `uv run python -m app.research extract animals`; run log in `apps/api/evals/RESULTS.md`
  - [x] Z1.3 Verifier and conflict detection, plus reading hand-picked press pages (`research.yaml`): `app.research extract`, `app.research verify-eval`
  - [ ] Z1.4 Agentic web search and primary-source tracing (also K2)
  - [ ] Z1.5 Proposals as a PR with provenance
  - [ ] Z1.6 Eval loop on held-out albums; second gold album
  - [ ] Z1.7 Admin-queue integration (needs A1)
- [ ] **Z2 Spotify support.**
- [ ] **Z3 Native iOS and Android apps.**
- [ ] **Z4 Saved sessions and listening history.**
- [ ] **Z5 Social features and sharing.**
- [ ] **Z6 Payments.**

---

## Next up

Features you have chosen to build next, in order. Move IDs here from the sections above.

1. Side panel tabs, one PR each (Now, Meaning and Album are done): Lyrics (dev stub), then Making and Sources. See [plans/side-panel/plan.md](../plans/side-panel/plan.md).

Dependencies to keep in mind when choosing (not a build order): the player bar (P3) and playback provider (P2) need the fake player (P1); every tab needs the panel shell (S1); the Lyrics tab (L2) can be built on the dev stub (L5) before a licence exists; the Live and Photos tabs need their data models (F1, V1); Community (C) needs accounts (C1).

## Open decisions

| # | Decision | Needed before |
|---|----------|---------------|
| D1 | Apple Developer account and MusicKit key; org account needed for public playback? | P4 |
| D2 | First real album | K1 |
| D3 | Working name for the app | First public link |
| D4 | Lyrics licence route (Musixmatch or LyricFind) | L1, public launch |
| D5 | ~~Which tabs ship first~~ Decided: Now, Meaning, Lyrics, Making, Sources | S1 |
| D6 | Photo and video rights policy | F2 |
| D7 | Community rules, moderation and legal terms | C1 |
| D8 | Hosting | A3 |

## Done log

Shipped items with PR links go here, newest first.

- Layout: tracklist left, information right; Album tab (before, after, credits) and Meaning tab (all of a song's approved claims, grouped by who is speaking)
- Animals seed content: [#6](https://github.com/Lkaasan/runout/pull/6)
- Side panel shell and Now tab, embedded depth: [#5](https://github.com/Lkaasan/runout/pull/5)
- Side panel shell and Now tab, embedded depth (S1, S2, S3, S4)
- Foundations M4 player foundation (P1 to P6): [#4](https://github.com/Lkaasan/runout/pull/4)
- Foundations M1 repo and tooling: [#1](https://github.com/Lkaasan/runout/pull/1)
- Foundations M2 data model, migrations, importer: [#2](https://github.com/Lkaasan/runout/pull/2)
- Foundations M3 read API, typed client, admin API, runnable web UI: [#3](https://github.com/Lkaasan/runout/pull/3)
