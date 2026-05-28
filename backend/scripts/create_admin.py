from __future__ import annotations

import asyncio
import getpass
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.user import validate_password_strength  # noqa: E402


async def main() -> None:
    username = settings.ADMIN_USERNAME or input("Admin username: ").strip()
    email = settings.ADMIN_EMAIL or input("Admin email: ").strip()
    password = settings.ADMIN_PASSWORD or getpass.getpass("Admin password: ").strip()

    if not username or not email:
        print("ERROR: ADMIN_USERNAME and ADMIN_EMAIL are required.", file=sys.stderr)
        raise SystemExit(1)

    try:
        validate_password_strength(password)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email.lower()))
        existing = result.scalar_one_or_none()
        if existing is not None:
            if existing.role == "admin":
                print(f"Admin already exists: {email}")
            else:
                existing.role = "admin"
                existing.is_active = True
                db.add(existing)
                await db.commit()
                print(f"Promoted existing user to admin: {email}")
            return

        user = User(
            username=username.lower(),
            email=email.lower(),
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"Admin created: {email} id={user.id}")


if __name__ == "__main__":
    asyncio.run(main())
