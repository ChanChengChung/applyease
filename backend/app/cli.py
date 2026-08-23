import argparse
import getpass
import json
import sys
import time

from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.db.migrations import check_database, upgrade_database
from app.auth import hash_password
from app.crud import user as user_crud
from app.db.session import SessionLocal
from app.schemas.auth import RegisterRequest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="ApplyEase operational commands"
    )

    commands = parser.add_subparsers(dest="command", required=True)

    database = commands.add_parser("db", help="database operations")

    actions = database.add_subparsers(dest="action", required=True)

    actions.add_parser("upgrade", help="adopt a compatible legacy database and migrate to head")

    actions.add_parser("check", help="verify connectivity and migration revision")

    wait = actions.add_parser("wait", help="wait for the database to accept connections")

    wait.add_argument("--timeout", type=int, default=60)

    auth = commands.add_parser("auth", help="account administration")

    auth_actions = auth.add_subparsers(dest="action", required=True)

    claim = auth_actions.add_parser(
        "claim-local", help="assign the migrated local account an email and password"
    )

    claim.add_argument("--email", required=True)

    ai = commands.add_parser("ai", help="AI quality operations")

    ai_actions = ai.add_subparsers(dest="action", required=True)

    evaluate = ai_actions.add_parser("eval", help="run the versioned Stage 10 regression dataset")

    evaluate.add_argument("--provider", choices=("rules", "ollama", "gemini"), default="rules")

    evaluate.add_argument(
        "--confirm-external",
        action="store_true",
        help="required for Gemini because evaluation inputs leave this device and consume quota",
    )
    evaluate.add_argument(
        "--minimum-pass-rate",
        type=float,
        default=1.0,
        help="exit with code 2 when the score is below this 0..1 threshold",
    )

    return parser


def _claim_local(email: str) -> dict:
    password = getpass.getpass("New password: ")

    confirmation = getpass.getpass("Confirm password: ")

    if password != confirmation:

        raise RuntimeError("Passwords do not match")
    validated = RegisterRequest(email=email, password=password)

    with SessionLocal() as db:
        local = user_crud.get_by_email(db, "local@applyease.dev")

        if not local:

            raise RuntimeError("The local compatibility account does not exist")
        existing = user_crud.get_by_email(db, validated.email)

        if existing and existing.id != local.id:

            raise RuntimeError("An account with this email already exists")
        local.email = validated.email

        local.password_hash = hash_password(validated.password)

        db.commit()

        return {"status": "claimed", "user_id": local.id, "email": local.email}


def main() -> int:
    args = _parser().parse_args()

    try:

        if args.command == "ai":

            if not 0 <= args.minimum_pass_rate <= 1:

                raise ValueError("--minimum-pass-rate must be between 0 and 1")

            if args.provider == "gemini" and not args.confirm_external:

                raise RuntimeError("Gemini evaluation requires --confirm-external")
            from app.ai.evaluation import run_evaluation

            result = run_evaluation(args.provider)

        elif args.command == "auth":
            result = _claim_local(args.email)

        elif args.action == "upgrade":
            result = upgrade_database(settings.database_url)

        elif args.action == "check":
            result = check_database(settings.database_url)

            if not result["up_to_date"]:
                print(json.dumps(result))
                return 2

        else:
            deadline = time.monotonic() + args.timeout

            while True:

                try:
                    check_database(settings.database_url)
                    result = {"status": "available"}
                    break

                except SQLAlchemyError:

                    if time.monotonic() >= deadline:
                        raise

                    time.sleep(1)
        print(json.dumps(result))

        if args.command == "ai" and result["pass_rate"] < args.minimum_pass_rate:

            return 2

        return 0

    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        print(f"ApplyEase database command failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":

    raise SystemExit(main())
