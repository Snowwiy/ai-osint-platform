from __future__ import annotations

# Phase 1 will add OSINT, AI, and report tasks.
# Celery tasks that need async database or network calls should remain sync wrappers
# that call asyncio.run(...) inside the prefork worker process.
