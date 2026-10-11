"""Close policy — the cross-cutting rules in one module.

What a complete close requires, and what counts as an instruction
hiding in free text, are business decisions before they are code.
They live here, in one place, so a deployment tunes them in the
open. (Per-metric rules — formulas, eliminations, thresholds —
live in the versioned definition pack instead; see
:mod:`.definitions`. This module holds only what is not a metric.)
"""

from __future__ import annotations

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
