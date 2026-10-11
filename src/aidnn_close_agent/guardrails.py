"""Guardrails as code: the injection screen and the checklist.

These run before and beside any engine — never inside a prompt.

- **Injection screen** — journal memos are free text written by
  anyone with posting rights, and in a deployed close they travel
  toward model surfaces (an engine's narrative step, a reviewer's
  summary). Text is scanned at ingestion for instruction-like
  payloads; hits are flagged on the close run and the payload
  lines are fenced out of the copy the mart carries, so no
  downstream consumer ever sees the memo as something to obey.
  The figures never read memos at all — the screen protects the
  text surfaces, and the test suite pins that a flagged memo
  changes no number.
- **Close checklist** — a pure function over the run's checklist
  state: which required sources are still missing. The service
  refuses to build a pack while the list is non-empty
  (:class:`~.errors.ChecklistIncomplete`), and refuses sign-off
  on anything but an AWAITING_CONTROLLER pack. No state
  transition lives anywhere else.
"""

from __future__ import annotations

from .policy import ENTITY_REQUIRED_SOURCES, GROUP_REQUIRED_SOURCES, INJECTION_MARKERS
from .schemas import CloseRun

_FENCE = "[fenced by injection screen]"


def screen_injection(text: str) -> tuple[list[str], str]:
    """Scan free text for instruction-like payloads.

    Returns ``(flags, fenced_text)``: flags name each marker hit;
    in the fenced text, offending lines are replaced with a fence
    marker so downstream consumers never see the payload as text
    they might act on.
    """
    flags: list[str] = []
    out_lines: list[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        hit = next((m for m in INJECTION_MARKERS if m in lowered), None)
        if hit:
            flags.append(f"INJECTION_MARKER: {hit!r}")
            out_lines.append(_FENCE)
        else:
            out_lines.append(line)
    return flags, "\n".join(out_lines)


def missing_sources(run: CloseRun, entity_ids: list[str]) -> list[str]:
    """What the checklist still waits for, as ``ENTITY:kind`` /
    ``GROUP:kind`` labels. Empty means the run may build a pack."""
    missing: list[str] = []
    for entity_id in entity_ids:
        ingested = run.checklist.get(entity_id, {})
        for kind in ENTITY_REQUIRED_SOURCES:
            if kind not in ingested:
                missing.append(f"{entity_id}:{kind}")
    for kind in GROUP_REQUIRED_SOURCES:
        if kind not in run.group_checklist:
            missing.append(f"GROUP:{kind}")
    return missing
