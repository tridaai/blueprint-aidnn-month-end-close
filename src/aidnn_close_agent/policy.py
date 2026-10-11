"""Close policy — the cross-cutting rules in one module.

What a complete close requires, and what counts as an instruction
hiding in free text, are business decisions before they are code.
They live here, in one place, so a deployment tunes them in the
open. (Per-metric rules — formulas, eliminations, thresholds —
live in the versioned definition pack instead; see
:mod:`.definitions`. This module holds only what is not a metric.)
"""

from __future__ import annotations

# Flux materiality: when a figure's period-over-period movement
# counts as *material* — large enough that the board will ask why
# it moved, so the flux schedule (see :mod:`.flux`) itemises its
# drivers. A movement is material when it reaches either bar:
# the absolute bar, in the figure's own currency, or the
# percentage bar against the prior figure. The thresholds ride
# every schedule the pack carries, so a reader never has to ask
# which ruler judged a line.
FLUX_MATERIAL_ABS = "50000.00"
FLUX_MATERIAL_PCT = "10.00"

# Source kinds every entity must deliver before a pack may be
# built for the period. A missing kind keeps the run COLLECTING
# and makes build attempts fail with ChecklistIncomplete.
ENTITY_REQUIRED_SOURCES = ("gl", "ar")

# Group-level sources the close as a whole requires.
GROUP_REQUIRED_SOURCES = ("fx", "crm")

# Words that, appearing in a journal memo bound for any model
# call, mark the memo for fencing: memos are data, never
# instructions. The screen runs at ingestion; flagged memos are
# fenced in the mart and the flag rides the close run.
INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all instructions",
    "disregard the above",
    "you are now",
    "system prompt",
    "mark all variances",
    "approve the close",
    "report revenue as",
    "override the verifier",
)
