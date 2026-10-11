"""The aidnn adapter: the FinanceEnginePort against a deployed
aidnn workspace.

Read this first, because it is the honest part of the blueprint:
**aidnn publishes no public API.** There is no documented REST
surface to code against (checked October 2026), and this module
does not invent one and call it theirs. What a deployment
actually looks like — and what this adapter encodes — is an
*integration contract* that the FDE team implements with
Isotopes during onboarding:

- aidnn's connectors (NetSuite, QuickBooks, Salesforce, …) are
  pointed at the customer's systems; the governed marts this
  blueprint builds are the shape those feeds are normalized to
  before aidnn's agents see them;
- the definition pack is loaded into the workspace as its metric
  catalog (aidnn's NeoCortex layer) — the same versioned file
  the verifier reads here;
- the workspace is asked the pack's defined questions, and its
  proposed analysis comes back through its plan-review flow for
  exactly the figures the pack defines.

The wire shape below — one POST of the defined queries plus the
mart snapshot they run over, one JSON figure set back — is the
blueprint's concrete expression of that contract: the seam an
FDE implements against the real workspace (whose transport is
agreed during deployment and may be its UI-driven review flow
behind a thin internal service, not a public endpoint). It is
configurable precisely because it is contractual:
``AIDNN_WORKSPACE_URL`` names the deployment's endpoint and
``AIDNN_API_TOKEN`` its credential. Without the URL the adapter
refuses to start (:class:`EngineNotConfigured`) — the service
never silently serves the offline engine's answers under
aidnn's name.

The verifier does not know or care that this adapter exists: it
recomputes from source and disposes of whatever the engine —
aidnn in production, the reference engine here — proposes.
"""

from __future__ import annotations

import httpx

from .definitions import DefinitionPack
from .errors import EngineNotConfigured, EngineUnavailable
from .fx import money
from .marts import MartSet
from .schemas import Figure

CONTRACT_VERSION = "trida-defined-queries/1"


def _mart_snapshot(marts: MartSet) -> dict:
    """The governed dataset the defined queries run over, in the
    contract's wire shape. Voided lines are excluded — the engine
    never sees a duplicate the pack's rules already disposed of."""
    return {
        "mart_version": marts.mart_version,
        "gl_lines": [
            {
                "entity_id": line.entity_id,
                "journal_id": line.journal_id,
                "account": line.account,
                "debit": money(line.debit),
                "credit": money(line.credit),
                "ic_counterparty": line.ic_counterparty,
            }
            for line in marts.gl()
        ],
        "ar_billings": {
            entity_id: {"billings": b.billings, "currency": b.currency}
            for entity_id, b in marts.ar_billings.items()
        },
        "opportunities": [
            {"name": o.name, "amount": o.amount, "stage": o.stage}
            for o in marts.opportunities
        ],
        "rate_table": marts.rate_table.model_dump(),
    }


class AidnnEngineAdapter:
    """FinanceEnginePort against a deployed aidnn workspace."""

    name = "aidnn"

    def __init__(self, workspace_url: str | None, api_token: str | None = None,
                 *, timeout_seconds: float = 120.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        if not workspace_url:
            raise EngineNotConfigured(
                "FINANCE_ENGINE=aidnn needs AIDNN_WORKSPACE_URL: the endpoint "
                "of the customer's deployed aidnn workspace, agreed with "
                "Isotopes during deployment. aidnn publishes no public API, "
                "so there is no default to fall back to — and the offline "
                "engine's answers are never served under aidnn's name."
            )
        self._workspace_url = workspace_url.rstrip("/")
        self._api_token = api_token
        self._timeout = timeout_seconds
        self._transport = transport

    def answer(self, pack: DefinitionPack, marts: MartSet) -> list[Figure]:
        payload = {
            "contract": CONTRACT_VERSION,
            "definition_pack": {
                "pack_id": pack.pack_id,
                "version": pack.version,
                "reporting_currency": pack.reporting_currency,
                "metrics": [m.model_dump() for m in pack.metrics],
                "eliminations": [e.model_dump() for e in pack.eliminations],
                "plan": pack.plan,
            },
            "marts": _mart_snapshot(marts),
        }
        headers = {"Content-Type": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.post(
                    f"{self._workspace_url}/defined-queries",
                    json=payload, headers=headers,
                )
        except httpx.HTTPError as exc:
            raise EngineUnavailable(
                f"aidnn workspace at {self._workspace_url} unreachable: {exc}"
            ) from exc
        if response.status_code != 200:
            raise EngineUnavailable(
                f"aidnn workspace answered HTTP {response.status_code} "
                "for the defined queries"
            )
        try:
            rows = response.json()["figures"]
        except (ValueError, KeyError, TypeError) as exc:
            raise EngineUnavailable(
                "aidnn workspace response did not carry a figures list"
            ) from exc

        figures: list[Figure] = []
        for row in rows:
            figures.append(Figure(
                metric_id=row["metric_id"],
                label=row.get("label", row["metric_id"]),
                scope=row["scope"],
                entity_id=row.get("entity_id"),
                value=str(row["value"]),
                currency=row["currency"],
                status="proposed",
                definition_pack_version=pack.version,
                source_versions=marts.source_versions,
            ))
        return figures
