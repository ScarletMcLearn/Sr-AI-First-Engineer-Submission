"""Command line entry points: ``python -m app.cli <command>``.

Commands print machine-readable output to stdout only where documented (``rules-report`` and
``openapi``); all diagnostics go to stderr.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import get_settings
from app.db import get_sessionmaker
from app.services.common import company_timezone
from app.services.report import build_report

BACKEND_DIR = Path(__file__).resolve().parents[1]


def migrate() -> None:
    """Apply database migrations (idempotent)."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(config, "head")


def seed(path: Path | None) -> None:
    """Load the seed file idempotently."""
    from app.seed import seed_database

    with get_sessionmaker()() as session:
        seed_database(session, path)


def rules_report() -> None:
    """Print the rules report for the configured APP_NOW as JSON on stdout."""
    settings = get_settings()
    with get_sessionmaker()() as session:
        report = build_report(session, settings.app_now, company_timezone(session))
    sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")


def openapi() -> None:
    """Print the OpenAPI document (used to generate the typed frontend client)."""
    from app.main import app

    sys.stdout.write(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="apply migrations")
    seed_parser = sub.add_parser("seed", help="load seed.json idempotently")
    seed_parser.add_argument("--path", type=Path, default=None)
    sub.add_parser("rules-report", help="print the rules report JSON to stdout")
    sub.add_parser("openapi", help="print the OpenAPI document to stdout")
    args = parser.parse_args(argv)
    if args.cmd == "migrate":
        migrate()
    elif args.cmd == "seed":
        seed(args.path)
    elif args.cmd == "rules-report":
        rules_report()
    else:
        openapi()
    return 0


if __name__ == "__main__":
    sys.exit(main())
