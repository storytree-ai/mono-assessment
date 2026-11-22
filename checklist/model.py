"""The one thin wrapper every model call goes through; the provider is a config setting."""
import json
from pathlib import Path


class ModelUnavailable(Exception):
    pass


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
        import anthropic
        self.client = anthropic.Anthropic()
        self.name = name
        self.record_to = record_to

    def ask(self, task, system, user, schema):
        response = self.client.messages.create(
            model=self.name,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        )
        if response.stop_reason != "end_turn":
            raise ModelUnavailable(f"model stopped with {response.stop_reason}")
        answer = json.loads(next(block.text for block in response.content if block.type == "text"))
        if self.record_to:
            self.record_to.mkdir(exist_ok=True)
            saved = {"_generated": "GENERATED: recorded model response", "model": response.model, "response": answer}
            (self.record_to / f"{task}.json").write_text(json.dumps(saved, indent=2) + "\n")
        return answer


def make_model(provider: str, name: str, application: Path, record: bool = False):
    if provider == "replay":
        return ReplayModel(application / "model-responses")
    if provider == "anthropic":
        return AnthropicModel(name, application / "model-responses" if record else None)
    raise ValueError(f"unknown model provider {provider!r}")
