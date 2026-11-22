# Information finder: run log

One row per live run against the gold set (`evals/gold/<slug>.yaml`). A change to a prompt, tool or
rule is kept only if it improves these numbers without breaking the "must be 0" columns. Runs use
Claude Code with the owner's subscription; cost is the list-price equivalent, not a charge.
Model output varies from run to run, so treat differences of one or two items as noise.

Command: `uv run python -m app.research collect animals` then
`uv run python -m app.research extract animals --ignore-seed` (the seed is ignored so the finder
is measured against the gold set built from it).

| Run | Change | Model, effort | Kept / proposed | Recall, collected pages | Facts | Intent | Conflict | Errors | Dropped for | Calls, time, list cost |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | First prompt, excerpt cap 40 words | sonnet, medium | 84 / 93 | n/a (metric added later) | 22/25 | 2/9 | 0/1 | 0 | 5 long excerpt, 3 intent without author, 1 invented excerpt | 5, 159 s, $0.30 |
| 2 | Prompt: author is mandatory, count words | sonnet, medium | 87 / 95 | 23/28 | 20/25 | 4/9 | 0/1 | 1 duplicate | 6 long excerpt, 1 empty body, 1 invented excerpt | 5, 155 s, $0.29 |
| 3 | Excerpt cap raised to 60 words (a longer verbatim quote is still checkable) | sonnet, medium | 85 / 86 | 23/28 | 20/25 | 4/9 | 0/1 | 0 | 1 invented excerpt | 5, 189 s, $0.37 |

Notes
- Gold items marked `collected: false` come from press pages (Louder, Far Out, Songfacts, American
  Songwriter) that the finder does not fetch until step 4, so they cannot be found yet. The
  "collected pages" column leaves them out.
- The conflict item (the pig's size) needs a second source page and the verifier: step 3.
- The check that caught an invented quote in every run is the verbatim excerpt match.
