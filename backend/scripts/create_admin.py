"""Create or promote an administrator account.

Administrators are **never** created by the public sign-up endpoint - a
public registration must not be able to escalate its own privileges.  This
script is the only supported way to bootstrap the first administrator, and
it is meant to be run on the server by an operator:

    python -m scripts.create_admin --email admin@example.com --name "Site Admin"

If the account already exists it is promoted to the ``admin`` role instead
of being duplicated.

Password handling
-----------------
The password is read from the ``--password`` argument (visible in the shell
history) or, preferably, from the ``AGRIVISION_ADMIN_PASSWORD`` environment
variable or an interactive prompt.  No default password is ever accepted -
the script refuses to run with a password shorter than 12 characters.

Usage
-----
    python -m scripts.create_admin --email admin@example.com --name "Site Admin"
    python -m scripts.create_admin --email admin@example.com --password 'S3cret-Pass!'
    AGRIVISION_ADMIN_PASSWORD='S3cret-Pass!' python -m scripts.create_admin \
        --email admin@example.com
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from typing import Any

# Allow ``python scripts/create_admin.py`` as well as ``python -m scripts.create_admin``.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings  # noqa: E402
from app.core.logging_config import configure_logging, get_logger  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database.connection import db_manager  # noqa: E402
from app.models.user import UserDocument, UserRole  # noqa: E402
from app.repositories.user_repository import UserRepository  # noqa: E402

logger = get_logger(__name__)

MINIMUM_PASSWORD_LENGTH = 12


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="create_admin",
        description="Create or promote an AgriVision AI administrator account.",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email address of the administrator account.",
    )
    parser.add_argument(
        "--name",
        default="Administrator",
        help="Display name for the account (default: 'Administrator').",
    )
    parser.add_argument(
        "--password",
        default=None,
        help=(
            "Password to set. Prefer the AGRIVISION_ADMIN_PASSWORD environment "
            "variable or the interactive prompt so the value never appears in "
            "the shell history."
        ),
    )
    parser.add_argument(
        "--location",
        default=None,
        help="Optional location shown on the profile.",
    )
    return parser.parse_args(argv)


def resolve_password(cli_password: str | None) -> str:
    """Obtain the administrator password without shipping a default."""
    candidate = cli_password or os.environ.get("AGRIVISION_ADMIN_PASSWORD")

    if not candidate:
        if not sys.stdin.isatty():
            raise SystemExit(
                "No password supplied. Use --password, set "
                "AGRIVISION_ADMIN_PASSWORD, or run this command in a terminal "
                "to be prompted."
            )
        first = getpass.getpass("Administrator password: ")
        second = getpass.getpass("Confirm administrator password: ")
        if first != second:
            raise SystemExit("The passwords did not match.")
        candidate = first

    if len(candidate) < MINIMUM_PASSWORD_LENGTH:
        raise SystemExit(
            f"The administrator password must be at least "
            f"{MINIMUM_PASSWORD_LENGTH} characters long."
        )

    has_letter = any(char.isalpha() for char in candidate)
    has_digit = any(char.isdigit() for char in candidate)
    if not (has_letter and has_digit):
        raise SystemExit(
            "The administrator password must contain at least one letter and "
            "one number."
        )
    return candidate


async def promote_or_create(
    *, email: str, name: str, password: str, location: str | None
) -> dict[str, Any]:
    """Create the administrator, or promote the account if it already exists."""
    repository = UserRepository(db_manager.get_database())
    normalised_email = email.strip().lower()

    existing = await repository.get_by_email(normalised_email)
    if existing is not None:
        logger.info("Account %s already exists - promoting it to admin.", normalised_email)
        await repository.update(
            existing["_id"],
            {
                "role": UserRole.ADMIN.value,
                "password_hash": hash_password(password),
                "updated_at": existing.get("updated_at"),
            },
        )
        updated = await repository.get_by_id(existing["_id"])
        assert updated is not None  # noqa: S101 - just refreshed
        return updated

    document = UserDocument(
        name=name,
        email=normalised_email,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
        location=location,
    ).to_mongo()
    created = await repository.create(document)
    logger.info("Created administrator account %s.", normalised_email)
    return created


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(level="INFO")

    settings = get_settings()
    if not settings.has_database:
        print(
            "ERROR: MONGODB_URI is not configured.\n"
            "       Add your Atlas connection string to backend/.env (or the "
            "root .env) and try again.",
            file=sys.stderr,
        )
        return 1

    try:
        password = resolve_password(args.password)
    except SystemExit as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    connected = await db_manager.connect()
    if not connected:
        print(
            f"ERROR: Could not connect to MongoDB ({db_manager.last_error}).\n"
            "       Check MONGODB_URI, your IP allow-list in Atlas and the "
            "network route.",
            file=sys.stderr,
        )
        await db_manager.disconnect()
        return 1

    try:
        user = await promote_or_create(
            email=args.email,
            name=args.name,
            password=password,
            location=args.location,
        )
    finally:
        await db_manager.disconnect()

    print("")
    print("Administrator account ready.")
    print(f"  id    : {user['_id']}")
    print(f"  email : {user['email']}")
    print(f"  name  : {user.get('name')}")
    print(f"  role  : {user.get('role')}")
    print("")
    print("Sign in at http://localhost:5173/login with this account.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
