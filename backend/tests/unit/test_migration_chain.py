from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_chain_is_linear_single_head_and_storage_safe() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())
    base_revisions = [
        revision for revision in revisions if revision.down_revision is None
    ]

    assert script.get_heads() == ["0035_phase5ae_agents"]
    assert len(base_revisions) == 1
    assert all(
        revision.down_revision is None or isinstance(revision.down_revision, str)
        for revision in revisions
    )
    assert all(len(revision.revision) <= 32 for revision in revisions)
    assert len({revision.revision for revision in revisions}) == len(revisions)
