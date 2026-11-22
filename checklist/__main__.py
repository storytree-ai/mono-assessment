"""python -m checklist <application folder> [--model anthropic|replay] [--down sharepoint] [--as-of YYYY-MM-DD]"""
import argparse
import tomllib
from datetime import date
from pathlib import Path

from .engine import SOURCES, run
from .model import make_model
from .report import render

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    config = tomllib.loads((ROOT / "config.toml").read_text())
    parser = argparse.ArgumentParser(prog="checklist", description="Print an application's current-state checklist.")
    parser.add_argument("application", type=Path)
    parser.add_argument("--model", choices=["anthropic", "replay"], default=config["model"]["provider"])
    parser.add_argument("--down", action="append", choices=list(SOURCES), default=[],
                        help="simulate a source system being unavailable")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--record", action="store_true", help="save the model's responses for replay")
    args = parser.parse_args(argv)
    model = make_model(args.model, config["model"]["name"], args.application, args.record)
    report = run(args.application, model, args.as_of, set(args.down), ROOT / config["audit"]["path"])
    print(render(report))


if __name__ == "__main__":
    main()
