"""
Usage: python -m app.scripts.create_admin --email admin@example.com --password secret123
"""
import argparse
import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def _create(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            user.role = "admin"
            user.password_hash = hash_password(password)
            print(f"Updated existing user {email} to admin.")
        else:
            user = User(email=email, password_hash=hash_password(password), name="Admin", role="admin", email_verified=True)
            db.add(user)
            print(f"Created admin user {email}.")
        await db.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(_create(args.email, args.password))


if __name__ == "__main__":
    main()
