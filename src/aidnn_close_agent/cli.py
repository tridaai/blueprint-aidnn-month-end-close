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
    p_receive = sub.add_parser(
        "receive-restatement",
        help="take delivery of a restated extract for a signed period")
    p_receive.add_argument("batch_id")
    p_ack = sub.add_parser(
        "acknowledge-restatement",
        help="record a controller's acknowledgement of a pack's restatement")
    p_ack.add_argument("pack_id")
    p_ack.add_argument("--actor", required=True)
    p_ack.add_argument("--note", required=True)
    p_disp = sub.add_parser(
        "dispose-variance",
        help="record a controller's acceptance of one blocking "
             "variance on a blocked pack (ACCEPTED_CARRY); the "
             "close's next build is presented for sign-off only "
             "when every blocking variance is covered")
    p_disp.add_argument("pack_id")
    p_disp.add_argument("--code", required=True)
    p_disp.add_argument("--actor", required=True)
    p_disp.add_argument("--reason", required=True)
    p_disp.add_argument("--entity", default=None)
    p_disp.add_argument("--metric", default=None)
    p_disp.add_argument("--subject", default=None)
    p_drill = sub.add_parser(
        "drill",
        help="open one figure on a pack into the source lines "
             "it stands on — a re-performance from the pack's "
             "stamped sources, served only when the composition "
             "foots to the figure (DRILL_MISMATCH otherwise)")
    p_drill.add_argument("pack_id")
    p_drill.add_argument("metric_id")
    p_drill.add_argument("--entity", default=None)
    p_drill.add_argument("--text", action="store_true",
                         help="print the readable tree instead "
                              "of JSON")
    p_evidence = sub.add_parser(
        "evidence",
        help="generate a signed pack's audit evidence bundle "
             "(or print a stored rendering with --download)")
    p_evidence.add_argument("pack_id")
    p_evidence.add_argument("--download", choices=["json", "txt"],
                            default=None)
    p_defs = sub.add_parser(
        "definitions",
        help="print the definition-governance state: registry "
             "versions, dry-runs, activations, and the version "
             "governing --period when one is named")
    p_defs.add_argument("--period", default=None)
    p_dry = sub.add_parser(
        "definition-dry-run",
        help="compute a candidate version's impact over a "
             "signed period and record it (signs nothing, "
             "activates nothing)")
    p_dry.add_argument("--version", required=True)
    p_dry.add_argument("--reference-period", default=None)
    p_act = sub.add_parser(
        "definition-activate",
        help="make a version govern closes from --from-period "
             "onward, as a named act citing a recorded dry-run")
    p_act.add_argument("--version", required=True)
    p_act.add_argument("--from-period", required=True)
    p_act.add_argument("--actor", required=True)
    p_act.add_argument("--reason", required=True)
    p_ready = sub.add_parser(
        "readiness",
        help="the pre-close readiness check for a run: the "
             "period's governing manifest against the run's "
             "received sources, every failing item named (a "
             "pure read — it registers nothing)")
    p_ready.add_argument("run_id")
    p_ready.add_argument("--text", action="store_true",
                         help="print the readable report instead "
                              "of JSON")
    p_manifests = sub.add_parser(
        "manifests",
        help="list the expectation manifests on record, "
             "optionally for one --period")
    p_manifests.add_argument("--period", default=None)
    p_manifest = sub.add_parser(
        "record-manifest",
        help="record a named controller's expectation "
             "manifest for a period (append-only: a new "
             "version, naming the one it supersedes)")
    p_manifest.add_argument("--period", required=True)
    p_manifest.add_argument("--actor", required=True)
    p_manifest.add_argument("--note", required=True)
    p_manifest.add_argument(
        "--entries", required=True,
        help="the entries as a JSON list of "
             "{slot, kind, entity_id, expected_version, "
             "expected_batch_id}")
    p_waivers = sub.add_parser(
        "waivers",
        help="list the readiness waivers on record, "
             "optionally for one --period")
    p_waivers.add_argument("--period", default=None)
    p_waiver = sub.add_parser(
        "record-waiver",
        help="record a named controller's readiness waiver: "
             "the period's close may be built despite the "
             "named failing items (a blanket waiver, naming "
             "nothing, is refused)")
    p_waiver.add_argument("--period", required=True)
    p_waiver.add_argument("--actor", required=True)
    p_waiver.add_argument("--reason", required=True)
    p_waiver.add_argument("--item", action="append", required=True,
                          help="one failing item's exact name; "
                               "repeat for each item covered")
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
        elif args.command == "receive-restatement":
            batch = service.receive_restatement(args.batch_id)
            print(batch.model_dump_json(indent=2))
        elif args.command == "acknowledge-restatement":
            pack = service.acknowledge_restatement(args.pack_id, args.actor,
                                                   args.note)
            print(pack.model_dump_json(indent=2))
        elif args.command == "dispose-variance":
            pack = service.record_disposition(
                args.pack_id, code=args.code, actor=args.actor,
                reason=args.reason, entity_id=args.entity,
                metric_id=args.metric, subject=args.subject)
            print(pack.model_dump_json(indent=2))
        elif args.command == "drill":
            drill = service.figure_drill(args.pack_id, args.metric_id,
                                         args.entity)
            if args.text:
                from .drill import render_text
                sys.stdout.write(render_text(drill))
            else:
                print(drill.model_dump_json(indent=2))
        elif args.command == "evidence":
            record = service.generate_evidence(args.pack_id)
            if args.download:
                data, _ = service.evidence_download(args.pack_id,
                                                    args.download)
                sys.stdout.write(data.decode("utf-8"))
            else:
                print(record.model_dump_json(indent=2))
        elif args.command == "definitions":
            print(json.dumps(service.definition_state(args.period),
                             indent=2))
        elif args.command == "definition-dry-run":
            record = service.dry_run_definition_change(
                args.version, args.reference_period)
            print(record.model_dump_json(indent=2))
        elif args.command == "definition-activate":
            record = service.activate_definition_pack(
                args.version, args.from_period, args.actor, args.reason)
            print(record.model_dump_json(indent=2))
        elif args.command == "readiness":
            report = service.readiness(args.run_id)
            if args.text:
                from .readiness import render_text
                sys.stdout.write(render_text(report))
            else:
                print(report.model_dump_json(indent=2))
        elif args.command == "manifests":
            print(json.dumps(
                [m.model_dump()
                 for m in service.list_manifests(args.period)],
                indent=2))
        elif args.command == "record-manifest":
            from .schemas import ManifestEntry
            entries = [ManifestEntry.model_validate(e)
                       for e in json.loads(args.entries)]
            record = service.record_manifest(
                args.period, entries, args.actor, args.note)
            print(record.model_dump_json(indent=2))
        elif args.command == "waivers":
            print(json.dumps(
                [w.model_dump()
                 for w in service.list_waivers(args.period)],
                indent=2))
        elif args.command == "record-waiver":
            record = service.record_waiver(
                args.period, args.item, args.actor, args.reason)
            print(record.model_dump_json(indent=2))
        elif args.command == "runs":
            print(json.dumps([r.model_dump() for r in service.list_runs()],
                             indent=2))
    except CloseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
