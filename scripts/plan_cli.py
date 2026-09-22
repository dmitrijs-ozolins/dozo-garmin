#!/usr/bin/env python3
"""Manage planned workouts and injury flags (PLAN.md Phase 2).

PLAN.md originally sketched these as YAML files committed to the repo, but
this repo is public — personal training-plan and injury details stay out
of git entirely and live in the same Postgres DB as everything else.

Usage:
    python scripts/plan_cli.py add-workout 2026-09-01 running "Easy 8km"
    python scripts/plan_cli.py add-injury 2026-08-20 "Left knee soreness" --severity warning
    python scripts/plan_cli.py resolve-injury 3
    python scripts/plan_cli.py list-workouts [--from-date DATE] [--to-date DATE]
    python scripts/plan_cli.py list-injuries [--active-only]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from garmin_sync.db import connect, init_db


def add_workout(args: argparse.Namespace) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO planned_workouts (day, workout_type, description) VALUES (%s, %s, %s)",
            (args.date, args.type, args.description),
        )
        conn.commit()
    print(f"Added planned {args.type} on {args.date}")


def add_injury(args: argparse.Namespace) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO injury_log (day, severity, note) VALUES (%s, %s, %s)",
            (args.date, args.severity, args.note),
        )
        conn.commit()
    print(f"Logged injury flag on {args.date}")


def resolve_injury(args: argparse.Namespace) -> None:
    with connect() as conn:
        result = conn.execute(
            "UPDATE injury_log SET status = 'resolved', resolved_at = now() WHERE id = %s",
            (args.id,),
        )
        conn.commit()
        if result.rowcount == 0:
            print(f"No injury_log entry with id {args.id}")
            return
    print(f"Marked injury #{args.id} resolved")


def list_workouts(args: argparse.Namespace) -> None:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, day, workout_type, description FROM planned_workouts
            WHERE (%(from_date)s::date IS NULL OR day >= %(from_date)s)
              AND (%(to_date)s::date IS NULL OR day <= %(to_date)s)
            ORDER BY day
            """,
            {"from_date": args.from_date, "to_date": args.to_date},
        ).fetchall()
    for r in rows:
        print(f"#{r['id']:<4} {r['day']}  {r['workout_type'] or '-':12} {r['description'] or ''}")


def list_injuries(args: argparse.Namespace) -> None:
    with connect() as conn:
        query = "SELECT id, day, status, severity, note FROM injury_log"
        if args.active_only:
            query += " WHERE status = 'active'"
        query += " ORDER BY day"
        rows = conn.execute(query).fetchall()
    for r in rows:
        print(f"#{r['id']:<4} {r['day']}  {r['status']:8} {r['severity'] or '-':8} {r['note'] or ''}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add-workout", help="Add a planned workout")
    p.add_argument("date", help="YYYY-MM-DD")
    p.add_argument("type", help="Free-form label, e.g. running, cycling, rest")
    p.add_argument("description")
    p.set_defaults(func=add_workout)

    p = sub.add_parser("add-injury", help="Flag an active injury")
    p.add_argument("date", help="YYYY-MM-DD")
    p.add_argument("note")
    p.add_argument("--severity", default="warning")
    p.set_defaults(func=add_injury)

    p = sub.add_parser("resolve-injury", help="Mark an injury_log entry resolved")
    p.add_argument("id", type=int)
    p.set_defaults(func=resolve_injury)

    p = sub.add_parser("list-workouts")
    p.add_argument("--from-date", dest="from_date", default=None)
    p.add_argument("--to-date", dest="to_date", default=None)
    p.set_defaults(func=list_workouts)

    p = sub.add_parser("list-injuries")
    p.add_argument("--active-only", action="store_true")
    p.set_defaults(func=list_injuries)

    args = parser.parse_args()
    load_dotenv()
    init_db()
    args.func(args)


if __name__ == "__main__":
    main()
