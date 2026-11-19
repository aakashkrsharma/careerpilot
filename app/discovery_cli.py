"""One-shot discovery entry point for cron, systemd timers, or Task Scheduler."""
import argparse
from dataclasses import asdict
import json
import sys

from app.database.database import init_db
from app.models.workflow import JobDiscoveryCriteria
from app.services.candidate_service import candidate_service
from app.services.job_discovery_service import job_discovery_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run due, enabled CareerPilot job-source connectors once."
    )
    parser.add_argument("--candidate-id", type=int, required=True)
    parser.add_argument(
        "--query",
        help="Role/search terms to share with sources; defaults to the candidate's preferred roles.",
    )
    parser.add_argument(
        "--locations",
        help="Comma-separated target locations; defaults to profile preferences or India hubs.",
    )
    parser.add_argument(
        "--all-regions",
        action="store_true",
        help="Disable the default India/APAC eligibility filter.",
    )
    parser.add_argument("--limit", type=int, default=50, help="Maximum per source (1-100).")
    parser.add_argument(
        "--source-id",
        type=int,
        action="append",
        help="Run only this registered source ID; may be supplied more than once.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.limit <= 100:
        print("Limit must be between 1 and 100.", file=sys.stderr)
        return 2
    init_db()
    candidate = candidate_service.get_candidate_by_id(args.candidate_id)
    if candidate is None:
        print("Candidate was not found.", file=sys.stderr)
        return 2

    query = args.query
    if query is None:
        query = candidate.preferred_roles or None
    if args.locations is not None:
        locations = tuple(
            item.strip() for item in args.locations.split(",") if item.strip()
        )
    elif candidate.preferred_locations:
        locations = tuple(
            item.strip()
            for item in candidate.preferred_locations.split(",")
            if item.strip()
        )
    else:
        locations = JobDiscoveryCriteria().locations

    criteria = JobDiscoveryCriteria(
        query=query.strip() if query and query.strip() else None,
        roles=tuple(
            item.strip()
            for item in (candidate.preferred_roles or "").split(",")
            if item.strip()
        ),
        locations=locations,
        limit=args.limit,
        india_first=not args.all_regions,
    )
    result = job_discovery_service.run(
        candidate.id,
        criteria,
        source_ids=set(args.source_id) if args.source_id else None,
    )
    print(
        json.dumps(
            {
                "candidate_id": result.candidate_id,
                "started_at": result.started_at,
                "completed_at": result.completed_at,
                "sources": [asdict(source) for source in result.source_results],
            },
            indent=2,
        )
    )
    return 1 if any(source.status == "failed" for source in result.source_results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
