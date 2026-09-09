from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.models.ioc import IOC, IOCObservation
from app.services.data_quality import QualityCandidate, _check_demo_state
from app.services.demo import _ensure_ioc
from sqlalchemy.ext.asyncio import AsyncSession


async def test_ensure_ioc_reuses_existing_natural_key() -> None:
    existing_ioc = IOC(
        id=uuid.uuid4(),
        value="demo.raventech.invalid",
        normalized_value="demo.raventech.invalid",
        ioc_type="domain",
        source="manual_qa",
        confidence="medium",
        confidence_reason="Existing synthetic IOC created before demo refresh.",
        tags=["demo"],
    )
    db = MagicMock(spec=AsyncSession)
    db.get = AsyncMock(side_effect=[None, None])
    db.scalar = AsyncMock(side_effect=[existing_ioc, None])
    db.flush = AsyncMock()

    ioc_id = await _ensure_ioc(db, datetime.now(UTC))

    assert ioc_id == existing_ioc.id
    db.flush.assert_not_awaited()
    added = db.add.call_args.args[0]
    assert isinstance(added, IOCObservation)
    assert added.ioc_id == existing_ioc.id


async def test_ensure_ioc_reuses_existing_natural_key_observation() -> None:
    existing_ioc = MagicMock(spec=IOC)
    existing_ioc.id = uuid.uuid4()
    existing_observation = MagicMock(spec=IOCObservation)
    db = MagicMock(spec=AsyncSession)
    db.get = AsyncMock(side_effect=[None, None])
    db.scalar = AsyncMock(side_effect=[existing_ioc, existing_observation])
    db.flush = AsyncMock()

    ioc_id = await _ensure_ioc(db, datetime.now(UTC))

    assert ioc_id == existing_ioc.id
    db.add.assert_not_called()
    db.flush.assert_not_awaited()


def test_demo_quality_accepts_reused_natural_key_ioc() -> None:
    item = lambda value: SimpleNamespace(id=uuid.UUID(value))  # noqa: E731
    output: list[QualityCandidate] = []

    _check_demo_state(
        output,
        [item("70000000-0000-4000-8000-000000000001")],
        [item("70000000-0000-4000-8000-000000000007")],
        [item("70000000-0000-4000-8000-000000000010")],
        [
            SimpleNamespace(
                id=uuid.uuid4(),
                ioc_type="domain",
                normalized_value="demo.raventech.invalid",
            )
        ],
        [item("70000000-0000-4000-8000-000000000031")],
        [item("70000000-0000-4000-8000-000000000035")],
        [item("70000000-0000-4000-8000-000000000041")],
        [item("70000000-0000-4000-8000-000000000046")],
    )

    assert not any(issue.issue_type == "incomplete_demo_data" for issue in output)
