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

| 4 | Step 3: four press pages added, verifier and conflict detection on | sonnet, medium | 138 / 150 | 29/35 (83%) | 20/25 | 8/9 | 1/1 | 0 | 11 invented excerpt (a spacing bug in the web-page text, fixed in run 5), 1 verifier | 27, 842 s, $2.13 |
| 5 | Web text keeps inline markup joined ("Animals, the album"); verifier told who counts as the artist | sonnet, medium | 142 / 149 | 27/35 (77%) | 20/25 | 6/9 | 1/1 | 0 | 4 intent without speaker, 2 invented excerpt, 1 verifier | 22 (5 saved), 545 s, $1.58 |
| 6 | Speaker recovered from the claim when the page confirms the name | sonnet, medium | 143 / 149 | 28/35 (80%) | 20/25 | 7/9 | 1/1 | 0 | 3 intent without speaker, 2 invented excerpt, 1 verifier | 9 (18 saved), 207 s, $0.78 |

Verifier test on planted errors (`app.research verify-eval animals`, 40 claims from run 6, every second one damaged):
caught 20/20 (invented detail 8/8, opinion stated as fact 8/8, wrong speaker 4/4), false alarms 0/20.
The damage is fairly blatant and no changed-number case came up in this sample, so this shows the
verifier is not asleep, not that it catches every subtle slip.

Notes
- Run 6 reported conflict recall 0/1 only because the gold item did not list "12-metre"; the
  finder had flagged the pig's size (12 metres on Wikipedia against a 30-foot pig in American
  Songwriter). The gold keywords were widened and the score recomputed offline to 1/1.
- Gold items marked `collected: false` come from press pages (Louder, Far Out, Songfacts, American
  Songwriter) that the finder does not fetch until step 4, so they cannot be found yet. The
  "collected pages" column leaves them out.
- Run 4 onward read four hand-picked press pages listed in `content/albums/animals/research.yaml`
  (Louder, American Songwriter, Far Out, Songfacts), so no gold item is unreachable any more.
- Conflict detection finds real disagreements (pig size, Heathrow flights, fiancée versus wife,
  recording dates) and some weak ones (wording differences); each comes with its quote and
  explanation for a human to judge.
- The check that caught an invented quote in every run is the verbatim excerpt match.

## Tracing to the original (step 4)

`uv run python -m app.research trace animals --limit 10`: for each of 10 artist-intent claims a model
with web search and fetch (addresses out only) looked for the original publication, our fetcher
downloaded what it named, and a tool-less model quoted the speaker's own first-person words, which code
verified.

| Claims examined | Original proposed as primary | Pages read | Addresses refused | Calls, list cost |
|---|---|---|---|---|
| 10 | 1 | 6 | 1 | 16, $1.81 |

- Found: a CNN transcript of Waters' 2017 interview (the "surprised anyone could have listened to my songs for
  50 years" quote), with a verbatim first-person excerpt.
- Not found, and why: two archive.org pages for Nick Mason's book (they hold the catalogue record, not the text),
  a Louder piece on a lost Wright interview and a Rolling Stone story that did not contain the words, Ultimate
  Classic Rock (quotes the words but is not the original), and a fan-site transcript that returned HTTP 403.
- One in ten is a modest hit rate, and most of these statements come from books and old magazines that are not
  freely readable online. The step is working as designed: it says "not found" instead of guessing.

