"""The one thin wrapper every model call goes through; the provider is a config setting."""
import json
import subprocess
from pathlib import Path


class ModelUnavailable(Exception):
    pass


class NoModel:
    provider, name = "none", "none"

    def ask(self, task, system, user, schema):
        raise ModelUnavailable("model switched off")


class ReplayModel:
    """Returns the responses saved beside an application, so tests never call a model."""
    provider = "replay"

    def __init__(self, folder: Path):
        self.folder = folder
        self.name = json.loads((folder / "extract.json").read_text())["model"]

    def ask(self, task, system, user, schema):
        return json.loads((self.folder / f"{task}.json").read_text())["response"]


class AnthropicModel:
    provider = "anthropic"

    def __init__(self, name: str, record_to: Path | None = None):
        self.name = name
        self.record_to = record_to

    def ask(self, task, system, user, schema):
        import anthropic
        response = anthropic.Anthropic().messages.create(
            model=self.name,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        )
        if response.stop_reason != "end_turn":
            raise ModelUnavailable(f"model stopped with {response.stop_reason}")
        return self.record(task, response.model, json.loads(next(b.text for b in response.content if b.type == "text")))

    def record(self, task, model, answer):
        if self.record_to:
            self.record_to.mkdir(exist_ok=True)
            saved = {"_generated": f"GENERATED: recorded model response ({self.provider})", "model": model,
                     "response": answer}
            (self.record_to / f"{task}.json").write_text(json.dumps(saved, indent=2) + "\n")
        return answer


class ClaudeCodeModel(AnthropicModel):
    """The same prompts through Claude Code (claude -p) on its own login, with no tools: no API key needed."""
    provider = "claude-code"

    def ask(self, task, system, user, schema):
        done = subprocess.run(["claude", "-p", "--model", self.name, "--system-prompt", system, "--tools", "",
                               "--json-schema", json.dumps(schema), "--output-format", "json"],
                              input=user, capture_output=True, text=True, timeout=900)
        result = json.loads(done.stdout or "{}")
        if done.returncode or result.get("is_error") or "structured_output" not in result:
            raise ModelUnavailable(f"claude -p failed: {result.get('result') or done.stderr.strip()}")
        return self.record(task, self.name, result["structured_output"])


def make_model(provider: str, name: str, application: Path, record: bool = False):
    if provider == "none":
        return NoModel()
    if provider == "replay":
        return ReplayModel(application / "model-responses")
    if provider == "anthropic":
        return AnthropicModel(name, application / "model-responses" if record else None)
    if provider == "claude-code":
        return ClaudeCodeModel(name, application / "live-responses" if record else None)
    raise ValueError(f"unknown model provider {provider!r}")
