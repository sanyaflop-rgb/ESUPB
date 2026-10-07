from datetime import date

import pytest
from fastapi import HTTPException

from app.models.inspection import InspectionState, Violation, ViolationMeasure, ViolationStatus
from app.models.reference import ControlType
from app.services.inspections import (
    calculate_measure_status,
    calculate_violation_status,
    days_left,
    days_overdue,
    is_due_soon,
    normalize_document_number,
    recalculate_elimination_flags,
    validate_deadline_fields,
    validate_state_transition,
)


def test_document_number_normalization_collapses_supported_variants() -> None:
    variants = ("№ А-1", "а / 1", "А_1", "А–1")
    assert {normalize_document_number(value) for value in variants} == {"а/1"}


def test_measure_status_uses_calendar_days_and_elimination_is_not_a_status() -> None:
    measure = ViolationMeasure(due_date=date(2026, 10, 5), elimination_date=None)
    assert calculate_measure_status(measure, today=date(2026, 10, 5)) == ViolationStatus.NOT_ELIMINATED
    measure.due_date = date(2026, 10, 4)
    assert calculate_measure_status(measure, today=date(2026, 10, 5)) == ViolationStatus.OVERDUE
    measure.elimination_date = date(2026, 10, 6)
    recalculate_elimination_flags(measure)
    assert calculate_measure_status(measure, today=date(2026, 10, 7)) == ViolationStatus.ELIMINATED
    assert measure.eliminated_late is True
    assert measure.days_overdue_at_elimination == 2


def test_violation_status_aggregates_individual_measures() -> None:
    violation = Violation(annulled=False)
    eliminated = ViolationMeasure(elimination_date=date(2026, 10, 4))
    overdue = ViolationMeasure(due_date=date(2026, 10, 4))
    assert calculate_violation_status(violation, [eliminated, overdue], today=date(2026, 10, 5)) == ViolationStatus.OVERDUE
    overdue.elimination_date = date(2026, 10, 5)
    assert calculate_violation_status(violation, [eliminated, overdue], today=date(2026, 10, 5)) == ViolationStatus.ELIMINATED


def test_annulled_violation_has_no_working_status() -> None:
    assert calculate_violation_status(Violation(annulled=True), [], today=date(2026, 10, 5)) is None


def test_only_sequential_inspection_state_transitions_are_allowed() -> None:
    validate_state_transition(InspectionState.DRAFT, InspectionState.EDITING)
    validate_state_transition(InspectionState.EDITING, InspectionState.IN_PROGRESS)
    with pytest.raises(HTTPException):
        validate_state_transition(InspectionState.DRAFT, InspectionState.IN_PROGRESS)


def test_pc_ii_rejects_measure_deadline_data() -> None:
    control_type = ControlType(code="PC_II", name="ПК II", has_deadline_control=False)
    with pytest.raises(HTTPException):
        validate_deadline_fields(control_type, {"measures": [{"due_date": date(2026, 10, 8)}]})
    validate_deadline_fields(control_type, {"document_received_date": None, "measures": [{"due_date": None}]})


def test_days_overdue_and_days_left_are_calendar_based() -> None:
    measure = ViolationMeasure(due_date=date(2026, 10, 10))
    assert days_overdue(measure, today=date(2026, 10, 5)) == 0
    assert days_left(measure, today=date(2026, 10, 5)) == 5
    assert days_overdue(measure, today=date(2026, 10, 13)) == 3
    assert days_left(measure, today=date(2026, 10, 13)) == -3


def test_counters_freeze_without_due_date_or_after_elimination() -> None:
    no_due = ViolationMeasure(due_date=None)
    assert days_overdue(no_due, today=date(2026, 10, 5)) == 0
    assert days_left(no_due, today=date(2026, 10, 5)) is None
    eliminated = ViolationMeasure(due_date=date(2026, 10, 4), elimination_date=date(2026, 10, 6))
    assert days_overdue(eliminated, today=date(2026, 10, 10)) == 0
    assert days_left(eliminated, today=date(2026, 10, 10)) is None


def test_due_soon_window_is_seven_calendar_days() -> None:
    measure = ViolationMeasure(due_date=date(2026, 10, 12))
    assert is_due_soon(measure, today=date(2026, 10, 5)) is True
    assert is_due_soon(measure, today=date(2026, 10, 12)) is True
    assert is_due_soon(measure, today=date(2026, 10, 4)) is False
    assert is_due_soon(measure, today=date(2026, 10, 13)) is False
    eliminated = ViolationMeasure(due_date=date(2026, 10, 12), elimination_date=date(2026, 10, 6))
    assert is_due_soon(eliminated, today=date(2026, 10, 5)) is False
    assert is_due_soon(ViolationMeasure(due_date=None), today=date(2026, 10, 5)) is False
