"""The HTTP surface: console, runs, ingestion, packs, the gate.

Thin by design — every behaviour lives in the service, so what
the tests pin is what the console shows. The API's own jobs are
request IDs, JSON logging, honest error mapping, and naming the
live wiring (engine, store, definition pack version) on
``/readiness`` so an operator can see at a glance which
deployment they are looking at — including when the answers are
"offline" and "in-memory".
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    Response,
)
from pydantic import BaseModel

from . import db
from .checkpoints import checkpointer_name
from .config import finance_engine, load_dotenv
from .errors import CloseError
from .observability import configure_json_logging, new_request_id, request_id_ctx
from .service import CloseService
from .wiring import build_service

log = logging.getLogger(__name__)
_STATIC = Path(__file__).resolve().parent / "static"


class CreateRunRequest(BaseModel):
    period: str


class IngestRequest(BaseModel):
    batch_ids: list[str]


class SignOffRequest(BaseModel):
    decision: str
    actor: str
    reason: str = ""


class ReceiveSourceRequest(BaseModel):
    batch_id: str


class AcknowledgeRequest(BaseModel):
    actor: str
    note: str


class DispositionRequest(BaseModel):
    code: str
    actor: str
    reason: str
    entity_id: str | None = None
    metric_id: str | None = None
    subject: str | None = None


def create_app(service: CloseService | None = None) -> FastAPI:
    load_dotenv()
    configure_json_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.run_migrations()
        yield

    app = FastAPI(title="Trida Blueprint — aidnn Month-End Close, Deployed",
                  lifespan=lifespan)
    state: dict[str, CloseService] = {}

    def svc() -> CloseService:
        if "service" not in state:
            state["service"] = service or build_service()
        return state["service"]

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = request_id
        log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response

    @app.exception_handler(CloseError)
    def close_error_handler(request: Request, exc: CloseError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon_svg() -> FileResponse:
        return FileResponse(_STATIC / "brand" / "favicon.svg")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon_ico() -> FileResponse:
        return FileResponse(_STATIC / "brand" / "favicon.ico")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (_STATIC / "index.html").read_text(encoding="utf-8")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readiness")
    def readiness() -> JSONResponse:
        service = svc()
        payload = {
            "ready": True,
            "finance_engine": finance_engine(),
            "store": service.store.name,
            "checkpointer": checkpointer_name(),
            "definition_pack": (
                f"{service.pack_def.pack_id} v{service.pack_def.version}"
            ),
        }
        return JSONResponse(content=payload)

    @app.get("/evals/results")
    def eval_results() -> dict:
        path = Path(__file__).resolve().parent / "data" / "eval_results.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"status": "not run yet — `make evals` produces this file"}

    @app.get("/world/batches")
    def world_batches() -> list[dict]:
        return [
            {
                "batch_id": b.batch_id, "kind": b.kind,
                "entity_id": b.entity_id, "version": b.version,
                "supersedes": b.supersedes, "phase": b.phase,
            }
            for b in svc().connector.available()
        ]

    @app.post("/demo/run", status_code=201)
    def demo_run() -> dict:
        """The whole synthetic story in one call: the first close
        attempt, the late extracts, the rebuilt pack — returned as
        both packs so the console can show the arc."""
        from .datasets import PERIOD, build_world

        service = svc()
        world = build_world()
        run = service.create_run(PERIOD)
        service.ingest(run.run_id,
                       [b.batch_id for b in world.batches_in_phase("initial")])
        first = service.build_pack(run.run_id)
        service.ingest(run.run_id,
                       [b.batch_id for b in world.batches_in_phase("late")])
        second = service.build_pack(run.run_id)
        return {
            "run": service.get_run(run.run_id).model_dump(),
            "first_pack": service.get_pack(first.pack_id).model_dump(),
            "second_pack": second.model_dump(),
        }

    @app.post("/runs", status_code=201)
    def create_run(request: CreateRunRequest) -> dict:
        return svc().create_run(request.period).model_dump()

    @app.get("/runs")
    def list_runs() -> list[dict]:
        return [r.model_dump() for r in svc().list_runs()]

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        service = svc()
        run = service.get_run(run_id)
        payload = run.model_dump()
        payload["missing_sources"] = service.missing(run)
        return payload

    @app.post("/runs/{run_id}/ingest")
    def ingest(run_id: str, request: IngestRequest) -> dict:
        return svc().ingest(run_id, request.batch_ids).model_dump()

    @app.post("/runs/{run_id}/packs", status_code=201)
    def build_pack(run_id: str) -> dict:
        return svc().build_pack(run_id).model_dump()

    @app.get("/packs/{pack_id}")
    def get_pack(pack_id: str) -> dict:
        return svc().get_pack(pack_id).model_dump()

    @app.post("/packs/{pack_id}/sign-off")
    def sign_off(pack_id: str, request: SignOffRequest) -> dict:
        pack = svc().sign_off(pack_id, request.decision, request.actor,
                              request.reason)
        return pack.model_dump()

    @app.post("/sources/receive")
    def receive_source(request: ReceiveSourceRequest) -> dict:
        """Take delivery of a restated extract for a period whose
        pack is already signed. It attaches to no run; the next
        period's comparative layer picks it up by supersession."""
        batch = svc().receive_restatement(request.batch_id)
        return {
            "batch_id": batch.batch_id, "kind": batch.kind,
            "entity_id": batch.entity_id, "version": batch.version,
            "supersedes": batch.supersedes, "phase": batch.phase,
        }

    @app.post("/packs/{pack_id}/acknowledge-restatement")
    def acknowledge_restatement(pack_id: str,
                                request: AcknowledgeRequest) -> dict:
        pack = svc().acknowledge_restatement(pack_id, request.actor,
                                             request.note)
        return pack.model_dump()

    @app.post("/packs/{pack_id}/dispositions")
    def record_disposition(pack_id: str,
                           request: DispositionRequest) -> dict:
        """Record a named controller's acceptance of one
        blocking variance on a blocked pack (ACCEPTED_CARRY).
        Refused (409, ground named) for an unnamed controller,
        a missing reason, a pack that is not BLOCKED, a
        non-blocking code, or a code that names no break on
        the pack. The pack stays BLOCKED; the close's next
        build is presented for sign-off only when every
        blocking variance is covered."""
        pack = svc().record_disposition(
            pack_id, code=request.code, actor=request.actor,
            reason=request.reason, entity_id=request.entity_id,
            metric_id=request.metric_id, subject=request.subject)
        return pack.model_dump()

    @app.post("/packs/{pack_id}/evidence", status_code=201)
    def generate_evidence(pack_id: str) -> dict:
        """Generate the audit evidence bundle for a signed pack.
        Refused (409, state named) for any pack that is not
        SIGNED_OFF, and for any completeness gap the assembly
        finds. Idempotent: a pack regenerates the byte-identical
        bundle and the same record."""
        return svc().generate_evidence(pack_id).model_dump()

    @app.get("/packs/{pack_id}/evidence")
    def get_evidence(pack_id: str) -> dict:
        return svc().get_evidence(pack_id).model_dump()

    @app.get("/packs/{pack_id}/evidence/download")
    def download_evidence(pack_id: str, format: str = "json") -> Response:
        data, content_type = svc().evidence_download(pack_id, format)
        filename = f"evidence-{pack_id}.{format}"
        return Response(
            content=data, media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )

    return app


app = create_app()
