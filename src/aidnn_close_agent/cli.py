"""Command line: drive a close run, print packs as JSON.

The CLI drives the same service as the API, wired from the
environment — so `FINANCE_ENGINE=aidnn` works here exactly as it
does over HTTP, and the whole synthetic story can be run from a
terminal with `run-story`.
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import load_dotenv
from .datasets import PERIOD, build_world
from .errors import CloseError
from .service import CloseService
from .wiring import build_service


def _story(service: CloseService) -> dict:
    world = build_world()
    run = service.create_run(PERIOD)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("initial")])
    first = service.build_pack(run.run_id)
    service.ingest(run.run_id,
                   [b.batch_id for b in world.batches_in_phase("late")])
    second = service.build_pack(run.run_id)
    return {
        "run_id": run.run_id,
        "first_pack": service.get_pack(first.pack_id).model_dump(),
        "second_pack": second.model_dump(),
    }


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="aidnn-close-agent")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run-story", help="run the synthetic close story, both attempts")
    p_create = sub.add_parser("create-run", help="create a close run for a period")
    p_create.add_argument("period")
    p_ingest = sub.add_parser("ingest", help="ingest batches into a run")
    p_ingest.add_argument("run_id")
    p_ingest.add_argument("batch_ids", nargs="+")
    p_build = sub.add_parser("build-pack", help="build a board pack for a run")
    p_build.add_argument("run_id")
    p_sign = sub.add_parser("sign-off", help="sign or return a pack")
    p_sign.add_argument("pack_id")
    p_sign.add_argument("decision", choices=["sign", "return"])
    p_sign.add_argument("--actor", required=True)
    p_sign.add_argument("--reason", default="")
    sub.add_parser("runs", help="list all close runs as JSON")
    args = parser.parse_args(argv)

    service = build_service()
    try:
        if args.command == "run-story":
            print(json.dumps(_story(service), indent=2))
        elif args.command == "create-run":
            print(service.create_run(args.period).model_dump_json(indent=2))
        elif args.command == "ingest":
            print(service.ingest(args.run_id, args.batch_ids).model_dump_json(indent=2))
        elif args.command == "build-pack":
            print(service.build_pack(args.run_id).model_dump_json(indent=2))
        elif args.command == "sign-off":
            pack = service.sign_off(args.pack_id, args.decision, args.actor,
                                    args.reason)
            print(pack.model_dump_json(indent=2))
        elif args.command == "runs":
            print(json.dumps([r.model_dump() for r in service.list_runs()],
                             indent=2))
    except CloseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
