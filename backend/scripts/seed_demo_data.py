from __future__ import annotations

import argparse
import asyncio

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services.demo import (
    DEMO_INVESTIGATION_ID,
    clear_demo_workspace,
    ensure_demo_workspace,
)
from sqlalchemy import select


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed or clear the RavenTech synthetic defensive demo workspace.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove fixed synthetic demo records instead of seeding them.",
    )
    parser.add_argument(
        "--confirm-clear",
        metavar="PHRASE",
        help="Required with --clear; must be CLEAR-DEMO-DATA.",
    )
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User)
            .where(User.role == "admin", User.is_active.is_(True))
            .order_by(User.created_at.asc())
            .limit(1)
        )
        admin = result.scalar_one_or_none()
        if admin is None:
            raise SystemExit("No active admin user found to own demo data.")

        if args.clear:
            if args.confirm_clear != "CLEAR-DEMO-DATA":
                raise SystemExit(
                    "Refusing to clear demo records. Re-run with "
                    "--confirm-clear CLEAR-DEMO-DATA."
                )
            await clear_demo_workspace(db, admin)
            await db.commit()
            print("Synthetic demo workspace records were cleared.")
            return

        await ensure_demo_workspace(db, admin)
        await db.commit()
        print(f"Synthetic demo workspace is ready: {DEMO_INVESTIGATION_ID}")


if __name__ == "__main__":
    asyncio.run(main())
