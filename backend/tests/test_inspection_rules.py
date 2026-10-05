from datetime import date

import pytest
from fastapi import HTTPException

from app.models.inspection import InspectionState, Violation, ViolationStatus
from app.models.reference import ControlType
from app.services.inspections import (
    calculate_violation_status,
    normalize_document_number,
    recalculate_elimination_flags,
    validate_deadline_fields,
    validate_state_transition,
)


def test_document_number_normalization_collapses_supported_variants() -> None:
    variants = ("№ А-1", "а / 1", "А_1", "А–1")

    assert {normalize_document_number(value) for value in variants} == {"а/1"}


def test_violation_status_uses_calendar_days_and_elimination_is_not_a_status() -> None:
    violation = Violation(annulled=False, due_date=date(2026, 10, 5), elimination_date=None)
    assert calculate_violation_status(violation, today=date(2026, 10, 5)) == ViolationStatus.NOT_ELIMINATED

    violation.due_date = date(2026, 10, 4)
    assert calculate_violation_status(violation, today=date(2026, 10, 5)) == ViolationStatus.OVERDUE

    violation.elimination_date = date(2026, 10, 6)
    recalculate_elimination_flags(violation)
    assert calculate_violation_status(violation, today=date(2026, 10, 7)) == ViolationStatus.ELIMINATED
    assert violation.eliminated_late is True
    assert violation.days_overdue_at_elimination == 2


def test_annulled_violation_has_no_working_status() -> None:
    violation = Violation(annulled=True, due_date=date(2026, 10, 1), elimination_date=None)

    assert calculate_violation_status(violation, today=date(2026, 10, 5)) is None


def test_only_sequential_inspection_state_transitions_are_allowed() -> None:
    validate_state_transition(InspectionState.DRAFT, InspectionState.EDITING)
    validate_state_transition(InspectionState.EDITING, InspectionState.IN_PROGRESS)

    with pytest.raises(HTTPException):
        validate_state_transition(InspectionState.DRAFT, InspectionState.IN_PROGRESS)


def test_pc_ii_rejects_deadline_data() -> None:
    control_type = ControlType(code="PC_II", name="ПК II", has_deadline_control=False)

    with pytest.raises(HTTPException):
        validate_deadline_fields(control_type, {"due_date": date(2026, 10, 8)})

    validate_deadline_fields(control_type, {"due_date": None, "due_date_basis": None})
