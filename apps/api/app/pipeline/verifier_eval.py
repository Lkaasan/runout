"""Does the verifier actually catch bad claims? Test it on errors we plant ourselves.

Take real, quote-checked claims, damage some of them in ways a careless extraction could (a
changed number, the wrong speaker, an invented detail, an opinion stated as fact), leave the
rest alone, shuffle them together and run the verifier. Two numbers matter:

- caught: how many of the planted errors were flagged (higher is better);
- false alarms: how many untouched claims were flagged (lower is better).

The planting is deterministic, so a change in the numbers comes from the verifier, not luck.
"""

import re
from dataclasses import dataclass, field

from app.pipeline.llm import LLMBackend
from app.pipeline.models import Candidate, Page
from app.pipeline.verifier import verify_candidates

NAMES = ["Waters", "Gilmour", "Mason", "Wright"]


def _change_number(c: Candidate) -> str | None:
    m = re.search(r"\b(\d{2,4})\b", c.body)
    if not m:
        return None
    n = int(m.group(1))
    new = str(n + 7 if n > 1900 else n + 3)
    return c.body[: m.start()] + new + c.body[m.end() :]


def _swap_speaker(c: Candidate) -> str | None:
    for name in NAMES:
        if name in c.body:
            other = NAMES[(NAMES.index(name) + 1) % len(NAMES)]
            return c.body.replace(name, other)
    return None


def _invent_detail(c: Candidate) -> str | None:
    return c.body.rstrip(".") + ", during a secret late-night session in a Paris hotel room."


def _overclaim(c: Candidate) -> str | None:
    return (
        c.body.rstrip(".") + ", and it is widely agreed to be the finest thing the band ever did."
    )


MUTATIONS = {
    "changed number": _change_number,
    "wrong speaker": _swap_speaker,
    "invented detail": _invent_detail,
    "opinion as fact": _overclaim,
}


def plant_errors(candidates: list[Candidate]) -> tuple[list[Candidate], dict[str, str]]:
    """Return (the claims with some damaged, {claim id: how it was damaged}).

    Every second claim is damaged, cycling through the kinds that apply to it.
    """
    out: list[Candidate] = []
    planted: dict[str, str] = {}
    kinds = list(MUTATIONS)
    turn = 0
    for i, c in enumerate(candidates):
        copy = c.model_copy(deep=True)
        if i % 2 == 1:
            for step in range(len(kinds)):
                kind = kinds[(turn + step) % len(kinds)]
                new_body = MUTATIONS[kind](copy)
                if new_body and new_body != copy.body:
                    copy.body = new_body
                    planted[copy.id] = kind
                    turn += step + 1
                    break
        out.append(copy)
    return out, planted


@dataclass
class EvalReport:
    planted: int = 0
    caught: int = 0
    untouched: int = 0
    false_alarms: int = 0
    missed: list[str] = field(default_factory=list)
    false_alarm_issues: list[str] = field(default_factory=list)
    caught_by_kind: dict[str, tuple[int, int]] = field(default_factory=dict)

    def summary(self) -> str:
        pct = lambda a, b: f"{a}/{b}" + (f" ({a / b:.0%})" if b else "")  # noqa: E731
        lines = [
            "Verifier test on planted errors",
            f"  planted errors caught  {pct(self.caught, self.planted)}",
            f"  false alarms           {pct(self.false_alarms, self.untouched)}",
        ]
        for kind, (hit, total) in sorted(self.caught_by_kind.items()):
            lines.append(f"    {kind:<16} {pct(hit, total)}")
        lines += [f"  missed: {m}" for m in self.missed[:8]]
        lines += [f"  false alarm: {m}" for m in self.false_alarm_issues[:8]]
        return "\n".join(lines)


def run_eval(
    backend: LLMBackend, candidates: list[Candidate], pages: list[Page], *, limit: int = 40
) -> EvalReport:
    sample = candidates[:limit]
    damaged, planted = plant_errors(sample)
    result = verify_candidates(backend, damaged, pages)

    report = EvalReport()
    by_kind: dict[str, list[int]] = {}
    dropped_bodies = {d.body for d in result.dropped}
    for c in damaged:
        v = result.verdicts.get(c.id)
        # A claim the verifier dropped counts as flagged (it is flagged and removed).
        flagged = (v.flagged if v else True) or c.body in dropped_bodies
        if c.id in planted:
            report.planted += 1
            hit, total = by_kind.setdefault(planted[c.id], [0, 0])
            by_kind[planted[c.id]] = [hit + flagged, total + 1]
            if flagged:
                report.caught += 1
            else:
                report.missed.append(f"{planted[c.id]}: {c.body[:100]}")
        else:
            report.untouched += 1
            if flagged:
                report.false_alarms += 1
                issue = v.issue if v else "unverified"
                report.false_alarm_issues.append(f"{c.body[:70]} -> {issue[:70]}")
    report.caught_by_kind = {k: (v[0], v[1]) for k, v in by_kind.items()}
    return report
