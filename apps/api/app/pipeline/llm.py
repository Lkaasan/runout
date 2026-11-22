"""The model behind the finder, behind one small interface.

`ClaudeCodeBackend` runs the installed `claude` program in headless mode, so the work counts
against the user's own Claude subscription (their login), not a pay-per-token API key. It is a
personal research tool run on the owner's machine: Anthropic's terms allow the unmodified Claude
Code to be used with your own subscription, but not to route other people's requests through it.
For anything bigger, add an API-key backend behind the same interface.

Isolation, because the model reads untrusted web text:
- `--tools ""` removes every built-in tool, so the model can only return text.
- `--safe-mode` turns off CLAUDE.md, skills, hooks, plugins and MCP, but keeps the subscription
  login (`--bare` would drop it, so it is deliberately not used).
- `--permission-mode dontAsk` denies anything that would ask, `--no-session-persistence` keeps
  nothing on disk, and the process runs in an empty temporary folder.
- API-key and token variables are removed from the environment, so a stray key can never switch a
  run from the subscription to paid API billing.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class LLMError(Exception):
    pass


@dataclass
class LLMUsage:
    """What a run cost. On a subscription `cost_usd` is the list-price equivalent, not a charge."""

    calls: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0


class LLMBackend(Protocol):
    usage: LLMUsage

    def run_structured(self, *, system: str, prompt: str, schema: dict) -> dict:
        """Return the model's answer as a dict that validates against `schema`."""
        ...


# Variables that would move a run onto paid API billing or a different provider.
_BILLING_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


def find_claude() -> str:
    """The real `claude` program. On Windows the npm shim is a .cmd file that re-parses
    arguments through cmd.exe, so we use the .exe next to it, which does not."""
    found = shutil.which("claude")
    if not found:
        raise LLMError("The 'claude' program was not found. Install Claude Code and sign in.")
    path = Path(found)
    if path.suffix.lower() in (".cmd", ".bat", ".ps1"):
        exe = path.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return str(exe)
    return found


def clean_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if environ is None else environ)
    for key in list(env):
        if key in _BILLING_ENV or key.startswith("CLAUDE_CODE_USE_"):
            del env[key]
    return env


class ClaudeCodeBackend:
    def __init__(
        self,
        model: str = "sonnet",
        effort: str = "medium",
        timeout: float = 600,
        runner=subprocess.run,
        claude_path: str | None = None,
    ):
        self.model, self.effort, self.timeout = model, effort, timeout
        self._run = runner
        self._claude_path = claude_path
        self.usage = LLMUsage()

    def command(self, system: str, schema: dict) -> list[str]:
        return [
            self._claude_path or find_claude(),
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema),
            "--tools",
            "",
            "--safe-mode",
            "--no-session-persistence",
            "--permission-mode",
            "dontAsk",
            "--model",
            self.model,
            "--effort",
            self.effort,
            "--system-prompt",
            system,
        ]

    def run_structured(self, *, system: str, prompt: str, schema: dict) -> dict:
        with tempfile.TemporaryDirectory(prefix="finder-") as workdir:
            try:
                proc = self._run(
                    self.command(system, schema),
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.timeout,
                    env=clean_env(),
                    cwd=workdir,
                )
            except subprocess.TimeoutExpired as exc:
                raise LLMError(f"claude timed out after {self.timeout:.0f}s") from exc

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            detail = (proc.stderr or proc.stdout or "no output").strip()[:300]
            raise LLMError(f"claude returned no JSON (exit {proc.returncode}): {detail}") from exc

        self.usage.calls += 1
        self.usage.cost_usd += float(data.get("total_cost_usd") or 0)
        self.usage.seconds += float(data.get("duration_ms") or 0) / 1000

        if data.get("is_error") or proc.returncode != 0:
            # Limit messages ("You've hit your session limit...") arrive here as the result.
            raise LLMError(str(data.get("result") or data.get("subtype") or "claude failed")[:300])
        output = data.get("structured_output")
        if not isinstance(output, dict):
            raise LLMError("claude gave no structured output (it may have declined the request)")
        return output


class CachingBackend:
    """Remembers every answer, so a re-run only pays for prompts that changed.

    Useful while tuning the checks and the verifier: the same pages and prompts give the same
    answers, so a difference in the result is the change you made, not model variation. Pass
    `fresh=True` to ask the model again (and replace what was remembered).
    """

    def __init__(self, inner: LLMBackend, root: Path, *, fresh: bool = False):
        self.inner = inner
        self.folder = Path(root) / "llm"
        self.fresh = fresh
        self.hits = 0

    @property
    def usage(self) -> LLMUsage:
        return self.inner.usage

    def run_structured(self, *, system: str, prompt: str, schema: dict) -> dict:
        identity = [
            getattr(self.inner, "model", ""),
            getattr(self.inner, "effort", ""),
            system,
            prompt,
            schema,
        ]
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        path = self.folder / f"{key}.json"
        if not self.fresh and path.exists():
            self.hits += 1
            return json.loads(path.read_text("utf-8"))
        answer = self.inner.run_structured(system=system, prompt=prompt, schema=schema)
        self.folder.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(answer), encoding="utf-8")
        return answer
