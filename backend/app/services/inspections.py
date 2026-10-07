import re
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inspection import (
    Inspection,
    InspectionState,
    Violation,
    ViolationMeasure,
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

_DEADLINE_FIELDS = ("due_date", "document_received_date")
DUE_SOON_DAYS = 7


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


def get_measure(database: Session, measure_id: UUID) -> ViolationMeasure:
    measure = database.get(ViolationMeasure, measure_id)
    if measure is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Мероприятие не найдено")
    return measure


def ensure_inspection_editable(inspection: Inspection) -> None:
    if inspection.state == InspectionState.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Состав проверки нельзя изменять после начала работы")


def ensure_unique_document_number(database: Session, control_type_id: UUID, normalized_number: str, inspection_id: UUID | None = None) -> None:
    statement = select(Inspection.id).where(
        Inspection.control_type_id == control_type_id,
        Inspection.document_number_normalized == normalized_number,
    )
    if inspection_id is not None:
        statement = statement.where(Inspection.id != inspection_id)
    if database.scalar(statement) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Проверка с таким номером уже существует для выбранного вида контроля")


def validate_inspection_references(database: Session, control_type_id: UUID, inspection_kind_id: UUID | None) -> ControlType:
    control_type = require_active(database, ControlType, control_type_id, "вид контроля")
    without_kind = {"PC_II", "ROSTECHNADZOR", "GAZNADZOR"}
    if control_type.code in without_kind:
        if inspection_kind_id is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Для выбранного вида контроля вид проверки не указывается")
    elif inspection_kind_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Укажите вид проверки")
    else:
        require_active(database, InspectionKind, inspection_kind_id, "вид проверки")
    return control_type


def validate_inspection_location(database: Session, control_type_id: UUID, inspection_kind_id: UUID | None, department_id: UUID | None, object_id: UUID | None) -> None:
    control_type = require_active(database, ControlType, control_type_id, "вид контроля")
    inspection_kind = require_active(database, InspectionKind, inspection_kind_id, "вид проверки") if inspection_kind_id else None
    requires_location = inspection_kind is not None and inspection_kind.code in {"PLANNED", "UNSCHEDULED"} and control_type.code == "PC_III"
    if requires_location and (department_id is None or object_id is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Для плановой и внеплановой проверки укажите подразделение и объект")
    if not requires_location and (department_id is not None or object_id is not None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Подразделение и объект не указываются для целевых проверок, Ростехнадзора и Газнадзора")
    if department_id is None or object_id is None:
        return
    department = require_active(database, Department, department_id, "подразделение проверки")
    production_object = require_active(database, ProductionObject, object_id, "объект проверки")
    if production_object.owner_department_id is not None and production_object.owner_department_id != department.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Объект не относится к выбранному подразделению")


def get_control_type(database: Session, inspection: Inspection) -> ControlType:
    control_type = database.get(ControlType, inspection.control_type_id)
    if control_type is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Вид контроля недоступен")
    return control_type


def validate_violation_type(database: Session, violation_type_id: UUID) -> ViolationType:
    return require_active(database, ViolationType, violation_type_id, "тип нарушения")


def validate_measure_references(database: Session, measures: list[dict[str, object]]) -> list[dict[str, object]]:
    if not measures:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Добавьте хотя бы одно мероприятие по устранению")
    normalized: list[dict[str, object]] = []
    assignments: set[tuple[UUID, UUID, UUID]] = set()
    for index, measure in enumerate(measures, start=1):
        department_id = measure["department_id"]
        object_id = measure["object_id"]
        person_id = measure["person_id"]
        if not isinstance(department_id, UUID) or not isinstance(object_id, UUID) or not isinstance(person_id, UUID):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Некорректное назначение меры №{index}")
        department = require_active(database, Department, department_id, "ответственное подразделение")
        production_object = require_active(database, ProductionObject, object_id, "объект")
        person = require_active(database, Person, person_id, "ответственное лицо")
        if person.department_id is not None and person.department_id != department.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Сотрудник в мере №{index} не относится к выбранному подразделению")
        if production_object.owner_department_id is not None and production_object.owner_department_id != department.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Объект в мере №{index} не относится к выбранному подразделению")
        assignment = (department_id, object_id, person_id)
        if assignment in assignments:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Одинаковое назначение ответственного указано несколько раз")
        assignments.add(assignment)
        elimination_measure = str(measure["elimination_measure"]).strip()
        if not elimination_measure:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Не заполнено мероприятие по устранению в строке №{index}")
        normalized.append({**measure, "elimination_measure": elimination_measure})
    return normalized


def validate_deadline_fields(control_type: ControlType, values: dict[str, object]) -> None:
    if control_type.has_deadline_control:
        return
    if values.get("document_received_date") is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Для ПК II контроль сроков не применяется")
    measures = values.get("measures", [])
    if isinstance(measures, list) and any(isinstance(item, dict) and item.get("due_date") is not None for item in measures):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Для ПК II контроль сроков не применяется")


def calculate_measure_status(measure: ViolationMeasure, today: date | None = None) -> ViolationStatus:
    if measure.elimination_date is not None:
        return ViolationStatus.ELIMINATED
    current_date = today or datetime.now(UTC).date()
    if measure.due_date is not None and measure.due_date < current_date:
        return ViolationStatus.OVERDUE
    return ViolationStatus.NOT_ELIMINATED


def calculate_violation_status(violation: Violation, measures: list[ViolationMeasure], today: date | None = None) -> ViolationStatus | None:
    if violation.annulled:
        return None
    statuses = [calculate_measure_status(measure, today) for measure in measures]
    if statuses and all(item == ViolationStatus.ELIMINATED for item in statuses):
        return ViolationStatus.ELIMINATED
    if ViolationStatus.OVERDUE in statuses:
        return ViolationStatus.OVERDUE
    return ViolationStatus.NOT_ELIMINATED


def recalculate_elimination_flags(measure: ViolationMeasure) -> None:
    if measure.elimination_date is None or measure.due_date is None:
        measure.eliminated_late = False
        measure.days_overdue_at_elimination = None
        return
    overdue_days = (measure.elimination_date - measure.due_date).days
    measure.eliminated_late = overdue_days > 0
    measure.days_overdue_at_elimination = max(0, overdue_days)


def days_overdue(measure: ViolationMeasure, today: date | None = None) -> int:
    current_date = today or datetime.now(UTC).date()
    if measure.due_date is None or measure.elimination_date is not None:
        return 0
    return max(0, (current_date - measure.due_date).days)


def days_left(measure: ViolationMeasure, today: date | None = None) -> int | None:
    if measure.due_date is None or measure.elimination_date is not None:
        return None
    current_date = today or datetime.now(UTC).date()
    return (measure.due_date - current_date).days


def is_due_soon(measure: ViolationMeasure, today: date | None = None) -> bool:
    remaining = days_left(measure, today)
    return remaining is not None and 0 <= remaining <= DUE_SOON_DAYS


def validate_state_transition(current: InspectionState | str, target: InspectionState) -> None:
    allowed_transitions = {InspectionState.DRAFT: InspectionState.EDITING, InspectionState.EDITING: InspectionState.IN_PROGRESS}
    current_state = InspectionState(current)
    if allowed_transitions.get(current_state) != target:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Недопустимый переход состояния проверки")


def ensure_not_annulled(violation: Violation) -> None:
    if violation.annulled:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Нарушение аннулировано")


def ensure_deadline_control(database: Session, violation: Violation) -> None:
    if not get_control_type(database, get_inspection(database, violation.inspection_id)).has_deadline_control:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Для ПК II перенос срока недоступен")


def utc_now() -> datetime:
    return datetime.now(UTC)
