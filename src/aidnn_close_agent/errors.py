"""Error taxonomy for the close agent.

Every failure the service can hit is one of these, so the API maps
them to honest HTTP responses instead of stack traces:

- :class:`EngineNotConfigured` — the aidnn engine was selected
  without the workspace configuration a deployment agrees with
  Isotopes during onboarding. Startup fails loudly rather than
  substituting another engine's answers under aidnn's name.
- :class:`EngineUnavailable` — the engine was configured but
  could not be reached, or rejected the defined queries.
- :class:`ChecklistIncomplete` — a pack build was attempted
  before every required source for the period was ingested. The
  close checklist is a state machine, not a suggestion.
- :class:`GateError` — a sign-off the pack's state does not
  allow (blocked, stale, already signed, or anonymous).
- :class:`EvidenceError` — an audit evidence bundle that
  cannot be honestly generated: the pack is not signed, or a
  completeness check finds a gap (a figure without its
  definition or verdict, a stamped source missing from the
  store, a run that is not closed). The refusal names the gap;
  a partial bundle is never written.
- :class:`DrillError` — a figure drill-down that cannot be
  honestly served: the composition does not foot to the figure
  (``DRILL_MISMATCH``), a stamped source is missing or moved
  in the store, or the figure's definition has a shape the
  close does not define line semantics for. The refusal names
  its ground; an approximate drill is never served.
- :class:`RunNotFound` / :class:`PackNotFound` /
  :class:`BatchNotFound` / :class:`BundleNotFound` /
  :class:`DrillNotFound` — store misses (a drill for a figure
  the pack does not carry, among them).
"""

from __future__ import annotations


class CloseError(Exception):
    """Base class for all errors this package raises on purpose."""

    status_code = 500


class EngineNotConfigured(CloseError):
    status_code = 503


class EngineUnavailable(CloseError):
    status_code = 502


class ChecklistIncomplete(CloseError):
    """The close checklist forbids this step in the run's state."""

    status_code = 409


class GateError(CloseError):
    """A sign-off action that the pack's state does not allow."""

    status_code = 409


class EvidenceError(CloseError):
    """An evidence bundle that cannot be honestly generated."""

    status_code = 409


class RunNotFound(CloseError):
    status_code = 404


class PackNotFound(CloseError):
    status_code = 404


class BatchNotFound(CloseError):
    status_code = 404


class BundleNotFound(CloseError):
    status_code = 404


class DrillError(CloseError):
    """A figure drill that cannot be honestly served."""

    status_code = 409


class DrillMismatch(DrillError):
    """The drill's composition does not foot to the figure.

    Carries both totals and the line count of the composition
    that was attempted, so a caller (the evidence bundle, say)
    can record the break exactly instead of dropping it."""

    def __init__(self, message: str, *, composed_total: str,
                 figure_value: str, line_count: int) -> None:
        super().__init__(message)
        self.composed_total = composed_total
        self.figure_value = figure_value
        self.line_count = line_count


class DrillNotFound(CloseError):
    status_code = 404
