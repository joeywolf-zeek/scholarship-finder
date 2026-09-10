"""Data loading for profile.json and data/scholarships.json."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class EligibilityCriteria:
    text: str = ""
    gpa_min: Optional[float] = None
    state_residency: Optional[list[str]] = None  # required state(s) of legal residency
    school_states: Optional[list[str]] = None  # required state(s) where the school is located
    majors: Optional[list[str]] = None  # substrings matched against profile major/field
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    identity_requirements: Optional[list[str]] = None  # see matcher.KNOWN_IDENTITY_KEYS
    citizenship: Optional[list[str]] = None
    gender_requirements: Optional[list[str]] = None  # e.g. ["female"]
    requires_entering_freshman: Optional[bool] = None  # True: must be a HS senior applying pre-enrollment
    requires_pell_eligible: Optional[bool] = None
    other_notes: str = ""

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "EligibilityCriteria":
        return EligibilityCriteria(
            text=d.get("text", ""),
            gpa_min=d.get("gpa_min"),
            state_residency=d.get("state_residency"),
            school_states=d.get("school_states"),
            majors=d.get("majors"),
            age_min=d.get("age_min"),
            age_max=d.get("age_max"),
            identity_requirements=d.get("identity_requirements"),
            citizenship=d.get("citizenship"),
            gender_requirements=d.get("gender_requirements"),
            requires_entering_freshman=d.get("requires_entering_freshman"),
            requires_pell_eligible=d.get("requires_pell_eligible"),
            other_notes=d.get("other_notes", ""),
        )


@dataclass
class ApplicationEffort:
    essay_required: Optional[bool] = None
    letters_of_rec_required: Optional[bool] = None
    estimated_time: Optional[str] = None  # "low" / "medium" / "high"
    notes: str = ""

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "ApplicationEffort":
        return ApplicationEffort(
            essay_required=d.get("essay_required"),
            letters_of_rec_required=d.get("letters_of_rec_required"),
            estimated_time=d.get("estimated_time"),
            notes=d.get("notes", ""),
        )


@dataclass
class Scholarship:
    id: str
    name: str
    sponsor: str
    amount: str
    deadline: Optional[str]  # "YYYY-MM-DD" or None
    deadline_note: str
    renewable: Optional[bool]
    eligibility_criteria: EligibilityCriteria
    application_effort: ApplicationEffort
    url: str
    source: str
    date_found: str
    data_confidence: str  # "high" / "medium" / "low" -- confidence in the scraped data itself
    status: str = "not started"  # not started / in progress / submitted / awarded / rejected

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Scholarship":
        return Scholarship(
            id=d["id"],
            name=d["name"],
            sponsor=d.get("sponsor", ""),
            amount=d.get("amount", ""),
            deadline=d.get("deadline"),
            deadline_note=d.get("deadline_note", ""),
            renewable=d.get("renewable"),
            eligibility_criteria=EligibilityCriteria.from_dict(d.get("eligibility_criteria", {})),
            application_effort=ApplicationEffort.from_dict(d.get("application_effort", {})),
            url=d.get("url", ""),
            source=d.get("source", ""),
            date_found=d.get("date_found", ""),
            data_confidence=d.get("data_confidence", "medium"),
            status="not started",
        )


def load_scholarships(path: Path) -> list[Scholarship]:
    with open(path) as f:
        raw = json.load(f)
    return [Scholarship.from_dict(r) for r in raw]


def load_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Copy profile.example.json to profile.json and fill in "
            "your own answers -- profile.json is gitignored since it holds personal data."
        )
    with open(path) as f:
        return json.load(f)
