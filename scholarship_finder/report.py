"""Markdown + CSV report generation."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .matcher import EXCLUDED, HIGH_CONFIDENCE_MATCH, NEEDS_MANUAL_REVIEW, Evaluation, deadline_sort_key
from .models import Scholarship


@dataclass
class ReportRow:
    scholarship: Scholarship
    evaluation: Evaluation
    status: str
    is_expired: bool


def build_rows(
    scholarships: list[Scholarship],
    evaluations: dict[str, Evaluation],
    statuses: dict[str, dict[str, str]],
    today: date | None = None,
) -> list[ReportRow]:
    today = today or date.today()
    rows = []
    for s in scholarships:
        ev = evaluations[s.id]
        is_expired = False
        if s.deadline:
            try:
                is_expired = date.fromisoformat(s.deadline) < today
            except ValueError:
                is_expired = False
        status = statuses.get(s.id, {}).get("status", "not started")
        rows.append(ReportRow(scholarship=s, evaluation=ev, status=status, is_expired=is_expired))
    return rows


def _sorted_tier_rows(rows: list[ReportRow], tier: str) -> list[ReportRow]:
    tier_rows = [r for r in rows if r.evaluation.tier == tier]
    return sorted(
        tier_rows,
        key=lambda r: deadline_sort_key(r.scholarship) + (_amount_sort_value(r.scholarship),),
    )


def _amount_sort_value(s: Scholarship) -> float:
    import re

    nums = re.findall(r"\d[\d,]*(?:\.\d+)?", s.amount or "")
    if not nums:
        return 0.0
    return -max(float(n.replace(",", "")) for n in nums)  # negative -> higher amount first


def _fmt_deadline(row: ReportRow) -> str:
    s = row.scholarship
    if not s.deadline:
        note = f" ({s.deadline_note})" if s.deadline_note else " (rolling/unconfirmed -- verify on official page)"
        return f"Unknown{note}"
    if row.is_expired:
        return f"{s.deadline} -- PASSED, check official page for next cycle"
    return s.deadline


def render_markdown(rows: list[ReportRow], generated_at: date) -> str:
    lines = [f"# Scholarship Match Report -- generated {generated_at.isoformat()}", ""]

    def section(title: str, tier: str, description: str) -> None:
        lines.append(f"## {title}")
        lines.append(description)
        lines.append("")
        tier_rows = _sorted_tier_rows(rows, tier)
        if not tier_rows:
            lines.append("_None this run._")
            lines.append("")
            return
        for row in tier_rows:
            s = row.scholarship
            lines.append(f"### {s.name} -- {s.amount}")
            lines.append(f"- **Sponsor:** {s.sponsor}")
            lines.append(f"- **Deadline:** {_fmt_deadline(row)}")
            lines.append(f"- **Renewable:** {s.renewable if s.renewable is not None else 'unknown'}")
            lines.append(f"- **Status:** {row.status}")
            effort = s.application_effort
            effort_bits = []
            if effort.essay_required is not None:
                effort_bits.append(f"essay {'required' if effort.essay_required else 'not required'}")
            if effort.letters_of_rec_required is not None:
                effort_bits.append(f"letters of rec {'required' if effort.letters_of_rec_required else 'not required'}")
            if effort.notes:
                effort_bits.append(effort.notes)
            lines.append(f"- **Application effort:** {'; '.join(effort_bits) if effort_bits else 'unknown'}")
            lines.append("- **Why:** " + "; ".join(row.evaluation.reasons))
            lines.append(f"- **Link:** {s.url}")
            lines.append(f"- _Source: {s.source} (found {s.date_found}, data confidence: {s.data_confidence})_")
            lines.append("")

    section(
        "High Confidence Matches",
        HIGH_CONFIDENCE_MATCH,
        "Every eligibility dimension we could check passes, and nothing about eligibility is ambiguous.",
    )
    section(
        "Possible Matches -- Verify Manually",
        NEEDS_MANUAL_REVIEW,
        "At least one eligibility detail is missing, ambiguous, or unconfirmed. Not excluded, not "
        "guaranteed -- check the official page before spending application time.",
    )

    excluded_rows = _sorted_tier_rows(rows, EXCLUDED)
    if excluded_rows:
        lines.append("## Not Eligible (excluded)")
        lines.append("Kept here for transparency -- shown only so you can see *why* they were dropped.")
        lines.append("")
        for row in excluded_rows:
            s = row.scholarship
            lines.append(f"- **{s.name}** -- {'; '.join(row.evaluation.reasons)}")
        lines.append("")

    return "\n".join(lines)


def render_csv(rows: list[ReportRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = (
        _sorted_tier_rows(rows, HIGH_CONFIDENCE_MATCH)
        + _sorted_tier_rows(rows, NEEDS_MANUAL_REVIEW)
        + _sorted_tier_rows(rows, EXCLUDED)
    )
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["tier", "name", "amount", "deadline", "status", "why", "application_effort", "url", "sponsor"]
        )
        for row in ordered:
            s = row.scholarship
            effort = s.application_effort
            effort_bits = []
            if effort.essay_required is not None:
                effort_bits.append(f"essay {'required' if effort.essay_required else 'not required'}")
            if effort.letters_of_rec_required is not None:
                effort_bits.append(f"letters of rec {'required' if effort.letters_of_rec_required else 'not required'}")
            writer.writerow(
                [
                    row.evaluation.tier,
                    s.name,
                    s.amount,
                    _fmt_deadline(row),
                    row.status,
                    "; ".join(row.evaluation.reasons),
                    "; ".join(effort_bits),
                    s.url,
                    s.sponsor,
                ]
            )
