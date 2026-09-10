"""Eligibility filtering and fit scoring.

Tiers, in order of precedence:
  - EXCLUDED: a hard-filter dimension definitively fails (e.g. GPA below the
    scholarship's stated minimum). Never shown in the report's two main
    sections.
  - NEEDS_MANUAL_REVIEW: at least one eligibility dimension is missing,
    ambiguous, or references something the profile can't confirm
    (e.g. an unconfirmed parent employer). Never silently excluded or
    silently included.
  - HIGH_CONFIDENCE_MATCH: every dimension we can check passes, and there is
    nothing left unresolved.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from .models import EligibilityCriteria, Scholarship

EXCLUDED = "excluded"
NEEDS_MANUAL_REVIEW = "needs_manual_review"
HIGH_CONFIDENCE_MATCH = "high_confidence_match"

# identity_requirements keys the matcher knows how to check against profile.json.
# Any other key on a scholarship record is treated as UNKNOWN (-> manual review).
KNOWN_IDENTITY_KEYS = {
    "lgbtq",
    "adhd_or_learning_disability",
    "first_generation_strict",
    "first_generation_broad",
    "military_dependent",
    "military_dependent_killed_or_disabled",
    "single_parent_background",
}


def _get(d: dict[str, Any], *path: str) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _check_identity(key: str, profile: dict[str, Any]) -> Optional[bool]:
    """Return True/False if we can evaluate this identity requirement, None if unknown."""
    if key == "lgbtq":
        v = _get(profile, "demographics", "lgbtq_identity")
        return bool(v) and str(v).strip().lower() not in ("", "none", "n/a")
    if key == "adhd_or_learning_disability":
        v = str(_get(profile, "demographics", "disability_status") or "").lower()
        return any(term in v for term in ("adhd", "learning disability", "dyslexia", "autism"))
    if key == "first_generation_strict":
        return bool(_get(profile, "demographics", "first_generation_status", "strict_definition"))
    if key == "first_generation_broad":
        strict = _get(profile, "demographics", "first_generation_status", "strict_definition")
        note = str(_get(profile, "demographics", "first_generation_status", "note") or "")
        return bool(strict) or bool(note.strip())
    if key == "military_dependent":
        return _get(profile, "family_and_community", "military_affiliation") is not None
    if key == "military_dependent_killed_or_disabled":
        mil = _get(profile, "family_and_community", "military_affiliation")
        if mil is None:
            return None
        killed = mil.get("killed_in_service")
        disabled = mil.get("service_connected_disability")
        if killed is None and disabled is None:
            return None
        return bool(killed) or bool(disabled)
    if key == "single_parent_background":
        return bool(_get(profile, "special_circumstances", "single_parent_background"))
    return None  # unknown key


@dataclass
class Evaluation:
    tier: str
    reasons: list[str]  # human-readable reasons feeding "why I'm eligible" / why excluded / what's unclear
    fit_score: int


def evaluate(scholarship: Scholarship, profile: dict[str, Any]) -> Evaluation:
    ec: EligibilityCriteria = scholarship.eligibility_criteria
    reasons_pass: list[str] = []
    reasons_unclear: list[str] = []
    exclude_reason: Optional[str] = None

    # low confidence in the scraped data itself is always a reason for manual review
    if scholarship.data_confidence == "low":
        reasons_unclear.append("Scraped eligibility data has low confidence -- verify on the official page.")

    if ec.gpa_min is not None:
        gpa = _get(profile, "academic", "gpa")
        if gpa is None:
            reasons_unclear.append(f"Requires GPA >= {ec.gpa_min}, but profile has no GPA on file.")
        elif gpa < ec.gpa_min:
            exclude_reason = f"GPA {gpa} is below the required minimum of {ec.gpa_min}."
        else:
            reasons_pass.append(f"GPA {gpa} meets the {ec.gpa_min} minimum.")

    if exclude_reason is None and ec.state_residency:
        residency = _get(profile, "geography", "legal_residency")
        if residency is None:
            reasons_unclear.append(f"Requires residency in {ec.state_residency}, residency not on file.")
        elif residency not in ec.state_residency:
            exclude_reason = f"Requires legal residency in {ec.state_residency}; profile residency is {residency}."
        else:
            reasons_pass.append(f"Legal residency ({residency}) matches requirement.")

    if exclude_reason is None and ec.school_states:
        school_loc = _get(profile, "geography", "school_location")
        if school_loc is None:
            reasons_unclear.append(f"Requires school located in {ec.school_states}; school location not on file.")
        elif school_loc not in ec.school_states:
            exclude_reason = f"Requires attending school in {ec.school_states}; profile school is in {school_loc}."
        else:
            reasons_pass.append(f"School location ({school_loc}) matches requirement.")

    if exclude_reason is None and ec.majors:
        major = str(_get(profile, "academic", "major") or "").lower()
        if not major:
            reasons_unclear.append(f"Requires major in {ec.majors}; no major on file.")
        elif not any(m.lower() in major or major in m.lower() for m in ec.majors):
            exclude_reason = f"Requires major in {ec.majors}; profile major is '{major}'."
        else:
            reasons_pass.append(f"Major matches ({major}).")

    if exclude_reason is None and (ec.age_min is not None or ec.age_max is not None):
        age = _get(profile, "demographics", "age")
        if age is None:
            reasons_unclear.append("Age-restricted, but no age on file.")
        else:
            if ec.age_min is not None and age < ec.age_min:
                exclude_reason = f"Requires age >= {ec.age_min}; profile age is {age}."
            elif ec.age_max is not None and age > ec.age_max:
                reasons_unclear.append(
                    f"Requires age <= {ec.age_max}; profile age is {age} (close to the cutoff -- "
                    "verify exact program-year age rule, e.g. age as of a specific date)."
                )
            else:
                reasons_pass.append(f"Age {age} is within the required range.")

    if exclude_reason is None and ec.citizenship:
        citizenship = str(_get(profile, "demographics", "citizenship_residency") or "").lower()
        if not citizenship:
            reasons_unclear.append(f"Requires citizenship in {ec.citizenship}; not on file.")
        elif not any(c.lower() in citizenship for c in ec.citizenship):
            exclude_reason = f"Requires citizenship in {ec.citizenship}; profile is '{citizenship}'."
        else:
            reasons_pass.append("Citizenship/residency status matches requirement.")

    if exclude_reason is None and ec.gender_requirements:
        gender = str(_get(profile, "demographics", "gender_identity") or "").strip().lower()
        if not gender:
            reasons_unclear.append(f"Requires gender in {ec.gender_requirements}; not on file.")
        elif gender not in [g.lower() for g in ec.gender_requirements]:
            exclude_reason = f"Requires gender in {ec.gender_requirements}; profile gender is '{gender}'."
        else:
            reasons_pass.append("Gender matches requirement.")

    if exclude_reason is None and ec.requires_entering_freshman:
        education_level = str(_get(profile, "academic", "education_level") or "").lower()
        if "high school" in education_level or "senior" in education_level:
            reasons_pass.append("Open to entering high school seniors, and profile is one.")
        elif education_level:
            exclude_reason = (
                "Requires applying as an entering/graduating high school senior (pre-enrollment); "
                f"profile education level is '{education_level}' (already enrolled)."
            )
        else:
            reasons_unclear.append("Requires applying as an entering high school senior; education level not on file.")

    if exclude_reason is None and ec.identity_requirements:
        for key in ec.identity_requirements:
            if key not in KNOWN_IDENTITY_KEYS:
                reasons_unclear.append(f"Targets identity criterion '{key}' -- not recognized by the matcher, verify manually.")
                continue
            result = _check_identity(key, profile)
            if result is None:
                reasons_unclear.append(f"Targets identity criterion '{key}' -- profile data insufficient to confirm.")
            elif result is False:
                exclude_reason = f"Targets identity criterion '{key}', which the profile does not confirm."
            else:
                reasons_pass.append(f"Matches identity criterion '{key}'.")

    if exclude_reason:
        return Evaluation(tier=EXCLUDED, reasons=[exclude_reason], fit_score=0)

    if reasons_unclear:
        return Evaluation(tier=NEEDS_MANUAL_REVIEW, reasons=reasons_unclear + reasons_pass, fit_score=_fit_score(scholarship, profile))

    if not reasons_pass:
        reasons_pass.append("No restrictive eligibility criteria found -- open to all applicants.")

    return Evaluation(tier=HIGH_CONFIDENCE_MATCH, reasons=reasons_pass, fit_score=_fit_score(scholarship, profile))


def _fit_score(scholarship: Scholarship, profile: dict[str, Any]) -> int:
    """Soft-criteria score used only to explain match strength, not to gate eligibility."""
    score = 0
    industry = str(_get(profile, "field_and_career", "industry_interest") or "").lower()
    text = (scholarship.eligibility_criteria.text + " " + scholarship.name + " " + scholarship.sponsor).lower()
    if industry and industry in text:
        score += 2
    for tie in _get(profile, "geography", "regional_ties") or []:
        if str(tie).lower() in text:
            score += 1
    effort = scholarship.application_effort
    time_available = str(_get(profile, "application_preferences", "time_available_per_week") or "").lower()
    if "couple" in time_available or "few" in time_available:
        if effort.estimated_time == "low":
            score += 2
        elif effort.estimated_time == "high":
            score -= 1
    if effort.essay_required is False:
        score += 1
    return score


def deadline_sort_key(scholarship: Scholarship, today: Optional[date] = None) -> tuple:
    """(bucket, date_or_zero, -amount_hint) -- soonest real deadlines first, then
    rolling/unknown, then expired ones last (most-recently-expired first)."""
    today = today or date.today()
    d = scholarship.deadline
    if d:
        try:
            dt = date.fromisoformat(d)
        except ValueError:
            dt = None
    else:
        dt = None

    if dt is not None and dt >= today:
        return (0, dt.toordinal())
    if dt is None:
        return (1, 0)
    return (2, -dt.toordinal())  # expired: most recently expired sorts first within this bucket
