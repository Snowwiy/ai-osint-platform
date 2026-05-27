# Phase 0: Foundation — Implementation Plan (Part 1B)

Continues from Part 1A. Covers Tasks 4–6.

---

## Task 4: ORM Models (`backend/app/models/`)

**Files:**
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/investigation.py`
- Create: `backend/app/models/investigation_member.py`
- Create: `backend/app/models/target.py`
- Create: `backend/app/models/scan_job.py`
- Create: `backend/app/models/finding.py`
- Create: `backend/app/models/ai_analysis.py`
- Create: `backend/app/models/report.py`
- Create: `backend/app/models/audit_log.py`
- Create: `backend/app/models/__init__.py`

Write all model files before running any migration. Alembic generates the migration by reading `Base.metadata`, which is only populated if all models are imported.

---

- [ ] **Step 4.1 — Write `backend/app/models/base.py`**

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Adds created_at and updated_at to any model that inherits it."""

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4.2 — Write `backend/app/models/user.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'analyst')", name="ck_users_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="analyst")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
```

- [ ] **Step 4.3 — Write `backend/app/models/investigation.py`**

```python
from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Investigation(Base, TimestampMixin):
    __tablename__ = "investigations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'completed', 'archived')",
            name="ck_investigations_status",
        ),
        CheckConstraint(
            "length(trim(authorization_statement)) >= 100",
            name="ck_investigations_auth_statement",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    authorization_statement: Mapped[str] = mapped_column(Text, nullable=False)
    scope_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4.4 — Write `backend/app/models/investigation_member.py`**

> **Critical:** This table has a **composite primary key** — no separate `id` column.

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InvestigationMember(Base):
    __tablename__ = "investigation_members"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'collaborator')",
            name="ck_investigation_members_role",
        ),
    )

    # Composite primary key — no separate id column
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="collaborator"
    )
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4.5 — Write `backend/app/models/target.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Target(Base):
    __tablename__ = "targets"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('domain', 'ip', 'email', 'username', 'org', 'url')",
            name="ck_targets_type",
        ),
        UniqueConstraint(
            "investigation_id", "target_type", "target_value",
            name="uq_targets_inv_type_val",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_value: Mapped[str] = mapped_column(String(500), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4.6 — Write `backend/app/models/scan_job.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ScanJob(Base):
    __tablename__ = "scan_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'partial', 'failed')",
            name="ck_scan_jobs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE"),
        nullable=False,
    )
    initiated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    adapters_requested: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    adapters_completed: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    adapters_failed: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4.7 — Write `backend/app/models/finding.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_findings_risk_score"),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')", name="ck_findings_confidence"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        nullable=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalized_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    risk_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    evidence_urls: Mapped[list] = mapped_column(ARRAY(Text), server_default="{}")
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4.8 — Write `backend/app/models/ai_analysis.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AiAnalysis(Base):
    __tablename__ = "ai_analyses"
    __table_args__ = (
        CheckConstraint(
            "risk_assessment IN ('none', 'low', 'medium', 'high', 'critical')",
            name="ck_ai_analyses_risk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE"),
        nullable=False,
    )
    finding_ids: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"
    )
    analysis_text: Mapped[str] = mapped_column(Text, nullable=False)
    risk_assessment: Mapped[str] = mapped_column(
        String(20), nullable=False, default="none"
    )
    framework_mappings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    recommendations: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    rag_sources: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4.9 — Write `backend/app/models/report.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "report_format IN ('pdf', 'html', 'json')", name="ck_reports_format"
        ),
        CheckConstraint(
            "status IN ('pending', 'generating', 'ready', 'failed')",
            name="ck_reports_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_format: Mapped[str] = mapped_column(
        String(10), nullable=False, default="html"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4.10 — Write `backend/app/models/audit_log.py`**

> **Critical:** Primary key is `BigInteger` with `autoincrement=True` — NOT a UUID.

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4.11 — Write `backend/app/models/__init__.py`**

This is the file that makes Alembic see all tables. If any model is missing here, Alembic will not include its table in the migration.

```python
from app.models.base import Base
from app.models.user import User
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.target import Target
from app.models.scan_job import ScanJob
from app.models.finding import Finding
from app.models.ai_analysis import AiAnalysis
from app.models.report import Report
from app.models.audit_log import AuditLog

__all__ = [
    "Base",
    "User",
    "Investigation",
    "InvestigationMember",
    "Target",
    "ScanJob",
    "Finding",
    "AiAnalysis",
    "Report",
    "AuditLog",
]
```

- [ ] **Step 4.12 — Verify all models import without errors**

```bash
cd backend
python -c "from app.models import *; print('All models imported:', Base.metadata.tables.keys())"
```

Expected output lists all 10 table names:
```
All models imported: dict_keys(['users', 'investigations', 'investigation_members',
'targets', 'scan_jobs', 'findings', 'ai_analyses', 'reports', 'audit_logs'])
```

If any table is missing, the corresponding model file has an import error. Fix before continuing.

- [ ] **Step 4.13 — Commit**

```bash
git add backend/app/models/
git commit -m "feat: add all SQLAlchemy 2.0 ORM models (9 tables + base)"
```

**Definition of done:** Step 4.12 prints all 9 table names without errors.

---

## Task 5: Alembic Setup

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Generate: `backend/alembic/versions/0001_initial.py` (via `alembic revision --autogenerate`)

---

- [ ] **Step 5.1 — Write `backend/alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
# sqlalchemy.url is NOT set here — env.py reads it from Settings
sqlalchemy.url =

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 5.2 — Write `backend/alembic/env.py`**

> This is the most critical file in Phase 0. Read the comments carefully before modifying.

```python
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# ── Path setup ───────────────────────────────────────────────────────────────
# backend/ must be on sys.path so "from app.core.config import settings" works.
# This file lives at backend/alembic/env.py, so parent.parent = backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.models.base import Base  # noqa: E402, F401
import app.models  # noqa: E402, F401 — side effect: registers all models with Base.metadata

# ── Alembic config ───────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ── CRITICAL: convert asyncpg URL → psycopg2 URL ─────────────────────────────
# The app uses asyncpg for async operations. Alembic requires a SYNCHRONOUS
# connection. Do NOT use create_async_engine here. Do NOT use asyncio.run().
# Simply replace the driver string in the URL.
sync_database_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL only)."""
    context.configure(
        url=sync_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB (normal mode)."""
    connectable = create_engine(sync_database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,       # detect column type changes
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5.3 — Write `backend/alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5.4 — Ensure PostgreSQL extensions exist before generating migration**

The `users.id` uses `gen_random_uuid()` and `pg_trgm` is needed for target fuzzy search. Run this once against your dev DB:

```bash
# Connect to the dev DB and create extensions
docker compose exec postgres psql -U raventech -d raventech -c "
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
"
```

- [ ] **Step 5.5 — Generate the initial migration**

```bash
# Run from inside the backend container or with the .env loaded
cd backend
alembic revision --autogenerate -m "initial"
```

Expected: creates `backend/alembic/versions/XXXX_initial.py`.

**Before running Step 5.6, open the generated file and verify:**
- All 9 table create statements are present (`op.create_table(...)` for each)
- `audit_logs.id` is `sa.BigInteger()` (not UUID)
- `investigation_members` has no separate `id` column — primary key is the composite `(investigation_id, user_id)`
- All `CheckConstraint` entries match the model definitions
- There are no unexpected `drop_table` or `alter_column` statements

If the generated file has only `pass` in `upgrade()`, `app.models` was not imported in `env.py`. Double-check Step 5.2.

- [ ] **Step 5.6 — Apply the migration**

```bash
alembic upgrade head
```

Expected output ends with: `INFO  [alembic.runtime.migration] Running upgrade  -> XXXX, initial`

- [ ] **Step 5.7 — Verify tables exist in the database**

```bash
docker compose exec postgres psql -U raventech -d raventech -c "\dt"
```

Expected — 10 rows (9 domain tables + alembic_version):
```
              List of relations
 Schema |          Name           | Type  |   Owner
--------+-------------------------+-------+-----------
 public | ai_analyses             | table | raventech
 public | alembic_version         | table | raventech
 public | audit_logs              | table | raventech
 public | findings                | table | raventech
 public | investigation_members   | table | raventech
 public | investigations          | table | raventech
 public | reports                 | table | raventech
 public | scan_jobs               | table | raventech
 public | targets                 | table | raventech
 public | users                   | table | raventech
```

- [ ] **Step 5.8 — Commit**

```bash
git add backend/alembic.ini backend/alembic/
git commit -m "feat: add Alembic setup with sync psycopg2 env.py and initial migration"
```

**Definition of done:** Steps 5.6 and 5.7 succeed. All 10 tables visible in psql.

---

## Task 6: Security (`backend/app/core/security.py`)

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/tests/unit/test_security.py`

This module is pure functions — no DB, no HTTP, no Redis. Write the tests first.

---

- [ ] **Step 6.1 — Write the failing tests first**

Create `backend/tests/unit/test_security.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


# ── Password hashing ──────────────────────────────────────────────────────────

def test_hash_password_produces_bcrypt_hash():
    hashed = hash_password("SecurePass123!")
    assert hashed.startswith("$2b$")
    assert hashed != "SecurePass123!"


def test_hash_password_is_different_each_call():
    """bcrypt generates a random salt per call — two hashes of the same password differ."""
    h1 = hash_password("SamePassword1!")
    h2 = hash_password("SamePassword1!")
    assert h1 != h2


def test_verify_password_correct_password():
    hashed = hash_password("CorrectPass123!")
    assert verify_password("CorrectPass123!", hashed) is True


def test_verify_password_wrong_password():
    hashed = hash_password("CorrectPass123!")
    assert verify_password("WrongPass456!", hashed) is False


def test_verify_password_empty_string_fails():
    hashed = hash_password("ValidPass123!")
    assert verify_password("", hashed) is False


# ── Access token ──────────────────────────────────────────────────────────────

def test_create_access_token_has_required_claims():
    token = create_access_token(user_id="user-abc", role="analyst")
    payload = decode_token(token)
    assert payload["sub"] == "user-abc"
    assert payload["role"] == "analyst"
    assert payload["type"] == "access"
    assert "jti" in payload
    assert "exp" in payload
    assert "iat" in payload


def test_create_access_token_expires_in_30_minutes():
    token = create_access_token(user_id="user-abc", role="admin")
    payload = decode_token(token)
    now = datetime.now(timezone.utc)
    expected_exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # Allow 5-second tolerance for test execution time
    assert abs(payload["exp"] - expected_exp.timestamp()) < 5


def test_create_access_token_unique_jti_each_call():
    t1 = create_access_token("user-1", "analyst")
    t2 = create_access_token("user-1", "analyst")
    p1 = decode_token(t1)
    p2 = decode_token(t2)
    assert p1["jti"] != p2["jti"]


# ── Refresh token ─────────────────────────────────────────────────────────────

def test_create_refresh_token_returns_token_and_jti():
    token, jti = create_refresh_token(user_id="user-xyz")
    assert isinstance(token, str)
    assert isinstance(jti, str)
    assert len(jti) == 36  # UUID4 string length


def test_refresh_token_jti_matches_payload():
    token, jti = create_refresh_token(user_id="user-xyz")
    payload = decode_token(token)
    assert payload["jti"] == jti


def test_refresh_token_type_is_refresh():
    token, _ = create_refresh_token(user_id="user-xyz")
    payload = decode_token(token)
    assert payload["type"] == "refresh"
    # Refresh token must NOT carry a role claim
    assert "role" not in payload


# ── Token decode / validation ─────────────────────────────────────────────────

def test_decode_token_raises_on_expired_token():
    from app.core.config import settings

    expired = pyjwt.encode(
        {
            "sub": "user-1",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        settings.APP_SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(expired)


def test_decode_token_raises_on_tampered_signature():
    token = create_access_token("user-1", "analyst")
    tampered = token[:-8] + "XXXXXXXX"
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(tampered)


def test_decode_token_raises_on_wrong_secret():
    from app.core.config import settings

    token = pyjwt.encode(
        {"sub": "user-1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "wrong-secret-key",
        algorithm="HS256",
    )
    with pytest.raises(pyjwt.InvalidSignatureError):
        decode_token(token)
```

- [ ] **Step 6.2 — Run tests to confirm they fail**

```bash
cd backend
pytest tests/unit/test_security.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `app.core.security` does not exist yet. This confirms the test is wired correctly.

- [ ] **Step 6.3 — Write `backend/app/core/security.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt cost factor 12 — per SECURITY_MODEL.md §3
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
REFRESH_TOKEN_EXPIRE_DAYS: int = 7


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt (cost 12). Returns the hash string."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time comparison — safe against timing attacks."""
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(payload: dict[str, Any], expire_delta: timedelta) -> str:
    """Internal helper. Adds iat and exp to payload, then encodes with HS256."""
    now = datetime.now(timezone.utc)
    data = payload.copy()
    data.update({"iat": now, "exp": now + expire_delta})
    return jwt.encode(data, settings.APP_SECRET_KEY, algorithm="HS256")


def create_access_token(user_id: str, role: str) -> str:
    """
    Create a short-lived access token (30 min).
    Payload: sub, role, type='access', jti, iat, exp
    """
    return _create_token(
        {
            "sub": user_id,
            "role": role,
            "type": "access",
            "jti": str(uuid.uuid4()),
        },
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """
    Create a long-lived refresh token (7 days).
    Returns (encoded_token, jti).
    The caller MUST store jti in Redis with TTL=7 days for revocation support.
    Payload: sub, type='refresh', jti, iat, exp  (no role — refresh tokens don't authorize actions)
    """
    jti = str(uuid.uuid4())
    token = _create_token(
        {"sub": user_id, "type": "refresh", "jti": jti},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT signed with APP_SECRET_KEY.

    Raises:
        jwt.ExpiredSignatureError  — token has expired
        jwt.InvalidSignatureError  — signature does not match
        jwt.InvalidTokenError      — any other JWT validation failure
    """
    return jwt.decode(token, settings.APP_SECRET_KEY, algorithms=["HS256"])
```

- [ ] **Step 6.4 — Run tests and confirm they all pass**

```bash
pytest tests/unit/test_security.py -v
```

Expected output — all 13 tests green:
```
tests/unit/test_security.py::test_hash_password_produces_bcrypt_hash PASSED
tests/unit/test_security.py::test_hash_password_is_different_each_call PASSED
tests/unit/test_security.py::test_verify_password_correct_password PASSED
tests/unit/test_security.py::test_verify_password_wrong_password PASSED
tests/unit/test_security.py::test_verify_password_empty_string_fails PASSED
tests/unit/test_security.py::test_create_access_token_has_required_claims PASSED
tests/unit/test_security.py::test_create_access_token_expires_in_30_minutes PASSED
tests/unit/test_security.py::test_create_access_token_unique_jti_each_call PASSED
tests/unit/test_security.py::test_create_refresh_token_returns_token_and_jti PASSED
tests/unit/test_security.py::test_refresh_token_jti_matches_payload PASSED
tests/unit/test_security.py::test_refresh_token_type_is_refresh PASSED
tests/unit/test_security.py::test_decode_token_raises_on_expired_token PASSED
tests/unit/test_security.py::test_decode_token_raises_on_tampered_signature PASSED
tests/unit/test_security.py::test_decode_token_raises_on_wrong_secret PASSED

14 passed in X.Xs
```

If `bcrypt__rounds=12` makes tests slow (>5 seconds): this is expected for the password hash tests — bcrypt intentionally costs CPU. Tests for hashing are slow by design. Do not lower the rounds.

- [ ] **Step 6.5 — Commit**

```bash
git add backend/app/core/security.py backend/tests/unit/test_security.py
git commit -m "feat: add JWT + bcrypt security module with full unit test coverage"
```

**Definition of done:** All 14 unit tests pass. `pytest tests/unit/test_security.py` exits 0.

---

*PART1B COMPLETE — READY FOR PART1C*
