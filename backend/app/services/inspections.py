import re
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inspection import (
    Inspection,
    InspectionScope,
    InspectionState,
    Violation,
    ViolationStatus,
)
from app.models.reference import (
    ControlType,
    Department,
    InspectionKind,
    Person,
    ProductionObject,
    ViolationType,
)

_DEADLINE_FIELDS = (
    "due_date",
    "due_date_basis",
    "due_date_source_text",
    "document_received_date",
)


def normalize_document_number(value: str) -> str:
    normalized = re.sub(r"\s+", "", value.strip().casefold().replace("№", ""))
    normalized = re.sub(r"[-_–]+", "/", normalized)
    normalized = re.sub(r"/+", "/", normalized).strip("/")
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Номер документа не заполнен")
    return normalized


def require_active(database: Session, model: type, item_id: UUID, label: str):
    item = database.get(model, item_id)
    if item is None or not item.is_active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Недоступен справочник: {label}")
    return item


def get_inspection(database: Session, inspection_id: UUID) -> Inspection:
    inspection = database.get(Inspection, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проверка не найдена")
    return inspection


def get_violation(database: Session, violation_id: UUID) -> Violation:
    violation = database.get(Violation, violation_id)
    if violation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Нарушение не найдено")
    return violation


def ensure_inspection_editable(inspection: Inspection) -> None:
    if inspection.state == InspectionState.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Состав проверки нельзя изменять после начала работы",
        )


def ensure_unique_document_number(
    database: Session,
    control_type_id: UUID,
    normalized_number: str,
    inspection_id: UUID | None = None,
) -> None:
    statement = select(Inspection.id).where(
        Inspection.control_type_id == control_type_id,
        Inspection.document_number_normalized == normalized_number,
    )
    if inspection_id is not None:
        statement = statement.where(Inspection.id != inspection_id)
    if database.scalar(statement) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Проверка с таким номером уже существует для выбранного вида контроля",
        )


def validate_inspection_references(database: Session, control_type_id: UUID, inspection_kind_id: UUID) -> ControlType:
    control_type = require_active(database, ControlType, control_type_id, "вид контроля")
    require_active(database, InspectionKind, inspection_kind_id, "вид проверки")
    return control_type


def get_control_type(database: Session, inspection: Inspection) -> ControlType:
    control_type = database.get(ControlType, inspection.control_type_id)
    if control_type is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Вид контроля недоступен")
    return control_type


def validate_scope_references(database: Session, department_id: UUID, object_id: UUID) -> None:
    require_active(database, Department, department_id, "подразделение")
    require_active(database, ProductionObject, object_id, "объект")


def validate_scope_for_inspection(scope: InspectionScope | None, inspection_id: UUID) -> InspectionScope:
    if scope is None or scope.inspection_id != inspection_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Область проверки не относится к проверке")
    return scope


def validate_violation_type(database: Session, violation_type_id: UUID) -> ViolationType:
    return require_active(database, ViolationType, violation_type_id, "тип нарушения")


def validate_responsible_references(
    database: Session,
    department_ids: list[UUID],
    person_ids: list[UUID],
) -> tuple[list[UUID], list[UUID]]:
    normalized_departments = list(dict.fromkeys(department_ids))
    normalized_persons = list(dict.fromkeys(person_ids))
    for department_id in normalized_departments:
        require_active(database, Department, department_id, "ответственное подразделение")
    for person_id in normalized_persons:
        require_active(database, Person, person_id, "ответственное лицо")
    return normalized_departments, normalized_persons


def validate_deadline_fields(control_type: ControlType, values: dict[str, object]) -> None:
    if control_type.has_deadline_control:
        return
    if any(values.get(field) is not None for field in _DEADLINE_FIELDS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Для ПК II контроль сроков не применяется",
        )


def calculate_violation_status(violation: Violation, today: date | None = None) -> ViolationStatus | None:
    if violation.annulled:
        return None
    if violation.elimination_date is not None:
        return ViolationStatus.ELIMINATED
    current_date = today or datetime.now(UTC).date()
    if violation.due_date is not None and violation.due_date < current_date:
        return ViolationStatus.OVERDUE
    return ViolationStatus.NOT_ELIMINATED


def recalculate_elimination_flags(violation: Violation) -> None:
    if violation.elimination_date is None or violation.due_date is None:
        violation.eliminated_late = False
        violation.days_overdue_at_elimination = None
        return
    overdue_days = (violation.elimination_date - violation.due_date).days
    violation.eliminated_late = overdue_days > 0
    violation.days_overdue_at_elimination = max(0, overdue_days)


def validate_state_transition(current: InspectionState | str, target: InspectionState) -> None:
    allowed_transitions = {
        InspectionState.DRAFT: InspectionState.EDITING,
        InspectionState.EDITING: InspectionState.IN_PROGRESS,
    }
    current_state = InspectionState(current)
    if allowed_transitions.get(current_state) != target:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Недопустимый переход состояния проверки",
        )


def ensure_not_annulled(violation: Violation) -> None:
    if violation.annulled:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Нарушение аннулировано")


def ensure_deadline_control(database: Session, violation: Violation) -> None:
    inspection = get_inspection(database, violation.inspection_id)
    control_type = get_control_type(database, inspection)
    if not control_type.has_deadline_control:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Для ПК II перенос срока недоступен",
        )


def utc_now() -> datetime:
    return datetime.now(UTC)
