import argparse
import json
from pathlib import Path

from .config import MAX_BYTES, profiles
from .db import engine, migrate
from .service import Pipeline


def main():
    parser = argparse.ArgumentParser(description="Self-Correcting Data Pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    ingest = commands.add_parser("ingest")
    ingest.add_argument("file", type=Path)
    ingest.add_argument("--profile", choices=profiles(), default="us_sales")
    summary = commands.add_parser("summary")
    summary.add_argument("batch_id", type=int)
    retry = commands.add_parser("retry")
    retry.add_argument("batch_id", type=int)
    args = parser.parse_args()
    db = engine()
    migrate(db)
    service = Pipeline(db)
    if args.command == "migrate":
        print("Schema version 1 is ready")
        return
    if args.command == "ingest":
        with args.file.open("rb") as handle:
            content = handle.read(MAX_BYTES + 1)
        batch_id = service.submit(content, args.file.name, profiles()[args.profile])
    else:
        batch_id = args.batch_id
        if args.command == "retry":
            service.process(batch_id)
    print(json.dumps(service.summary(batch_id), indent=2))


if __name__ == "__main__":
    main()
