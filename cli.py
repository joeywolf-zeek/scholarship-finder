#!/usr/bin/env python3
"""Personal scholarship-matching CLI.

Commands:
  match     Score data/scholarships.json against profile.json and write a report.
  status    View or update your application status for a scholarship.
  refresh   Explains how to pull fresh scholarship listings (see README).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from scholarship_finder.matcher import evaluate
from scholarship_finder.models import load_profile, load_scholarships
from scholarship_finder.report import build_rows, render_csv, render_markdown
from scholarship_finder.status_store import load_statuses, set_status

ROOT = Path(__file__).resolve().parent
PROFILE_PATH = ROOT / "profile.json"
SCHOLARSHIPS_PATH = ROOT / "data" / "scholarships.json"
STATUS_PATH = ROOT / "data" / "status.json"
REPORTS_DIR = ROOT / "reports"


def cmd_match(args: argparse.Namespace) -> int:
    profile = load_profile(PROFILE_PATH)
    scholarships = load_scholarships(SCHOLARSHIPS_PATH)
    statuses = load_statuses(STATUS_PATH)

    evaluations = {s.id: evaluate(s, profile) for s in scholarships}
    rows = build_rows(scholarships, evaluations, statuses)

    today = date.today()
    md = render_markdown(rows, today)
    md_path = REPORTS_DIR / "report.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md)

    csv_path = REPORTS_DIR / "report.csv"
    render_csv(rows, csv_path)

    high = sum(1 for r in rows if r.evaluation.tier == "high_confidence_match")
    review = sum(1 for r in rows if r.evaluation.tier == "needs_manual_review")
    excluded = sum(1 for r in rows if r.evaluation.tier == "excluded")
    print(f"{high} high-confidence match(es), {review} needs manual review, {excluded} excluded.")
    print(f"Report written to {md_path} and {csv_path}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    if args.scholarship_id is None:
        statuses = load_statuses(STATUS_PATH)
        scholarships = {s.id: s.name for s in load_scholarships(SCHOLARSHIPS_PATH)}
        if not statuses:
            print("No statuses recorded yet. Use: cli.py status <scholarship-id> <new-status>")
            return 0
        for sid, info in sorted(statuses.items()):
            name = scholarships.get(sid, "(unknown scholarship id)")
            print(f"{sid:35s} {info['status']:12s} {name}")
        return 0

    if args.new_status is None:
        print("Provide a new status: not started | in progress | submitted | awarded | rejected")
        return 1

    try:
        set_status(STATUS_PATH, args.scholarship_id, args.new_status)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"Updated {args.scholarship_id} -> {args.new_status}")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    print(
        "This CLI matches and reports against data/scholarships.json -- it does not\n"
        "call out to the web itself. To pull fresh listings:\n"
        "\n"
        "  1. Open this project in Claude Code again.\n"
        "  2. Ask it to refresh scholarship data using WebSearch/WebFetch, following\n"
        "     the same normalization schema documented in README.md.\n"
        "  3. It will update data/scholarships.json in place (existing entries keep\n"
        "     their ids and your status.json application-status tracking, so nothing\n"
        "     you've already logged is lost).\n"
        "  4. Re-run: python cli.py match\n"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_match = sub.add_parser("match", help="Score scholarships against your profile and write a report.")
    p_match.set_defaults(func=cmd_match)

    p_status = sub.add_parser("status", help="View or update application status.")
    p_status.add_argument("scholarship_id", nargs="?", default=None)
    p_status.add_argument("new_status", nargs="?", default=None,
                           help="one of: not started, in progress, submitted, awarded, rejected")
    p_status.set_defaults(func=cmd_status)

    p_refresh = sub.add_parser("refresh", help="How to pull fresh scholarship listings.")
    p_refresh.set_defaults(func=cmd_refresh)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
