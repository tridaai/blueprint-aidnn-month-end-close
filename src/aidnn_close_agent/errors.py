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
- :class:`RunNotFound` / :class:`PackNotFound` /
  :class:`BatchNotFound` — store misses.
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


class RunNotFound(CloseError):
    status_code = 404


class PackNotFound(CloseError):
    status_code = 404


class BatchNotFound(CloseError):
    status_code = 404
