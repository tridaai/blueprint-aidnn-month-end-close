"""Write the synthetic close world to disk as extract files.

The connectors in this repo serve the world from code; this
script materializes the same world as JSON files under
``data/extracts/`` — one file per source batch — so a reader can
inspect exactly what a NetSuite / QuickBooks / Salesforce extract
looks like when it lands, versions and planted traps included.

    uv run python data/generate_dataset.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aidnn_close_agent.datasets import (  # noqa: E402
    build_october_world,
    build_world,
    restatement_batch,
)


def main() -> int:
    out_dir = Path(__file__).resolve().parent / "extracts"
    out_dir.mkdir(parents=True, exist_ok=True)
    batches = (
        list(build_world().batches)
        + list(build_october_world().batches)
        + [restatement_batch()]
    )
    for batch in batches:
        path = out_dir / f"{batch.batch_id}.json"
        path.write_text(batch.model_dump_json(indent=2), encoding="utf-8")
        print(f"wrote {path.name} ({batch.kind}, "
              f"{batch.entity_id or 'GROUP'}, v{batch.version}, "
              f"phase {batch.phase})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
