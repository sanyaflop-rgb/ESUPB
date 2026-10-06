from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.inspection import (
    DeadlineChange,
    Inspection,
    RepeatLink,
    Violation,
    ViolationMeasure,
)
from app.models.security import User
from app.schemas.inspections import (
    AnnulmentCreate,
    DeadlineChangeCreate,
    DeadlineChangeResponse,
    EliminationCreate,
    InspectionCreate,
    InspectionResponse,
    InspectionStateChange,
    InspectionUpdate,
    RepeatDecisionUpdate,
    RepeatLinkResponse,
    ViolationCreate,
    ViolationMeasureInput,
    ViolationMeasureResponse,
    ViolationMeasureUpdate,
    ViolationResponse,
    ViolationUpdate,
)
from app.services.audit import record_audit
from app.services.inspections import (
    calculate_measure_status,
    calculate_violation_status,
    ensure_deadline_control,
    ensure_inspection_editable,
    ensure_not_annulled,
    ensure_unique_document_number,
    get_control_type,
    get_inspection,
    get_measure,
    get_violation,
    normalize_document_number,
    recalculate_elimination_flags,
    utc_now,
    validate_deadline_fields,
    validate_inspection_references,
    validate_inspection_location,
    validate_measure_references,
    validate_state_transition,
    validate_violation_type,
)

router = APIRouter(tags=["Проверки и нарушения"])
RequireWriter = Depends(require_roles("Administrator", "Specialist"))


def inspection_snapshot(item: Inspection) -> dict[str, Any]:
    return {
        "control_type_id": str(item.control_type_id),
        "inspection_kind_id": str(item.inspection_kind_id),
        "department_id": str(item.department_id) if item.department_id else None,
        "object_id": str(item.object_id) if item.object_id else None,
        "document_number": item.document_number,
        "inspection_date": item.inspection_date.isoformat(),
        "state": item.state,
        "comment": item.comment,
    }


def measures_for(database: Session, violation_id: UUID) -> list[ViolationMeasure]:
    return list(database.scalars(select(ViolationMeasure).where(ViolationMeasure.violation_id == violation_id).order_by(ViolationMeasure.created_at)))


def serialize_measure(item: ViolationMeasure) -> ViolationMeasureResponse:
    return ViolationMeasureResponse(
        id=item.id,
        violation_id=item.violation_id,
        department_id=item.department_id,
        object_id=item.object_id,
        person_id=item.person_id,
        elimination_measure=item.elimination_measure,
        due_date=item.due_date,
        original_due_date=item.original_due_date,
        elimination_date=item.elimination_date,
        eliminated_during_inspection=item.eliminated_during_inspection,
        eliminated_late=item.eliminated_late,
        days_overdue_at_elimination=item.days_overdue_at_elimination,
        status=calculate_measure_status(item),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def serialize_violation(database: Session, item: Violation) -> ViolationResponse:
    measures = measures_for(database, item.id)
    return ViolationResponse(
        id=item.id,
        inspection_id=item.inspection_id,
        formulation=item.formulation,
        violated_requirement=item.violated_requirement,
        violation_type_id=item.violation_type_id,
        severity=item.severity,
        document_received_date=item.document_received_date,
        annulled=item.annulled,
        annulled_at=item.annulled_at,
        annulled_by_id=item.annulled_by_id,
        annulment_reason=item.annulment_reason,
        measures=[serialize_measure(measure) for measure in measures],
        status=calculate_violation_status(item, measures),
        created_by_id=item.created_by_id,
        updated_by_id=item.updated_by_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def measure_snapshot(item: ViolationMeasure) -> dict[str, Any]:
    return {
        "department_id": str(item.department_id),
        "object_id": str(item.object_id),
        "person_id": str(item.person_id),
        "elimination_measure": item.elimination_measure,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "elimination_date": item.elimination_date.isoformat() if item.elimination_date else None,
        "status": calculate_measure_status(item).value,
    }


def violation_snapshot(database: Session, item: Violation) -> dict[str, Any]:
    return {
        "formulation": item.formulation,
        "violated_requirement": item.violated_requirement,
        "violation_type_id": str(item.violation_type_id),
        "severity": item.severity,
        "document_received_date": item.document_received_date.isoformat() if item.document_received_date else None,
        "annulled": item.annulled,
        "status": (calculated_status.value if (calculated_status := calculate_violation_status(item, measures_for(database, item.id))) else None),
        "measures": [measure_snapshot(measure) for measure in measures_for(database, item.id)],
    }


def add_measures(database: Session, violation: Violation, values: list[dict[str, object]]) -> list[ViolationMeasure]:
    items: list[ViolationMeasure] = []
    for value in values:
        item = ViolationMeasure(
            violation_id=violation.id,
            department_id=value["department_id"],
            object_id=value["object_id"],
            person_id=value["person_id"],
            elimination_measure=value["elimination_measure"],
            due_date=value.get("due_date"),
            original_due_date=value.get("due_date"),
        )
        database.add(item)
        items.append(item)
    database.flush()
    return items


@router.get("/inspections", response_model=list[InspectionResponse])
def list_inspections(_: User = Depends(get_current_user), database: Session = Depends(get_db)) -> list[Inspection]:
    return list(database.scalars(select(Inspection).order_by(Inspection.inspection_date.desc(), Inspection.document_number)))


@router.post("/inspections", response_model=InspectionResponse, status_code=status.HTTP_201_CREATED)
def create_inspection(payload: InspectionCreate, writer: User = RequireWriter, database: Session = Depends(get_db)) -> Inspection:
    validate_inspection_references(database, payload.control_type_id, payload.inspection_kind_id)
    validate_inspection_location(database, payload.inspection_kind_id, payload.department_id, payload.object_id)
    normalized_number = normalize_document_number(payload.document_number)
    ensure_unique_document_number(database, payload.control_type_id, normalized_number)
    item = Inspection(
        control_type_id=payload.control_type_id,
        inspection_kind_id=payload.inspection_kind_id,
        department_id=payload.department_id,
        object_id=payload.object_id,
        document_number=payload.document_number.strip(),
        document_number_normalized=normalized_number,
        inspection_date=payload.inspection_date,
        comment=payload.comment.strip() if payload.comment else None,
        created_by_id=writer.id,
        updated_by_id=writer.id,
    )
    database.add(item)
    database.flush()
    record_audit(database, actor_id=writer.id, entity_type="inspections", entity_id=item.id, action="create", new_value=inspection_snapshot(item))
    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Проверка с таким номером уже существует") from error
    database.refresh(item)
    return item


@router.get("/inspections/{inspection_id}", response_model=InspectionResponse)
def read_inspection(inspection_id: UUID, _: User = Depends(get_current_user), database: Session = Depends(get_db)) -> Inspection:
    return get_inspection(database, inspection_id)


@router.patch("/inspections/{inspection_id}", response_model=InspectionResponse)
def update_inspection(inspection_id: UUID, payload: InspectionUpdate, writer: User = RequireWriter, database: Session = Depends(get_db)) -> Inspection:
    item = get_inspection(database, inspection_id)
    ensure_inspection_editable(item)
    old_value = inspection_snapshot(item)
    next_kind_id = payload.inspection_kind_id if payload.inspection_kind_id is not None else item.inspection_kind_id
    next_department_id = payload.department_id if "department_id" in payload.model_fields_set else item.department_id
    next_object_id = payload.object_id if "object_id" in payload.model_fields_set else item.object_id
    validate_inspection_references(database, item.control_type_id, next_kind_id)
    validate_inspection_location(database, next_kind_id, next_department_id, next_object_id)
    if payload.inspection_kind_id is not None:
        item.inspection_kind_id = payload.inspection_kind_id
    if "department_id" in payload.model_fields_set:
        item.department_id = payload.department_id
    if "object_id" in payload.model_fields_set:
        item.object_id = payload.object_id
    if payload.document_number is not None:
        normalized_number = normalize_document_number(payload.document_number)
        ensure_unique_document_number(database, item.control_type_id, normalized_number, item.id)
        item.document_number = payload.document_number.strip()
        item.document_number_normalized = normalized_number
    if payload.inspection_date is not None:
        item.inspection_date = payload.inspection_date
    if "comment" in payload.model_fields_set:
        item.comment = payload.comment.strip() if payload.comment else None
    item.updated_by_id = writer.id
    record_audit(database, actor_id=writer.id, entity_type="inspections", entity_id=item.id, action="update", old_value=old_value, new_value=inspection_snapshot(item))
    database.commit()
    database.refresh(item)
    return item


@router.post("/inspections/{inspection_id}/state", response_model=InspectionResponse)
def change_inspection_state(inspection_id: UUID, payload: InspectionStateChange, writer: User = RequireWriter, database: Session = Depends(get_db)) -> Inspection:
    item = get_inspection(database, inspection_id)
    validate_state_transition(item.state, payload.state)
    old_value = inspection_snapshot(item)
    item.state = payload.state
    item.updated_by_id = writer.id
    record_audit(database, actor_id=writer.id, entity_type="inspections", entity_id=item.id, action="change_state", old_value=old_value, new_value=inspection_snapshot(item))
    database.commit()
    database.refresh(item)
    return item


@router.get("/inspections/{inspection_id}/violations", response_model=list[ViolationResponse])
def list_inspection_violations(inspection_id: UUID, include_annulled: bool = False, _: User = Depends(get_current_user), database: Session = Depends(get_db)) -> list[ViolationResponse]:
    get_inspection(database, inspection_id)
    statement = select(Violation).where(Violation.inspection_id == inspection_id).order_by(Violation.created_at)
    if not include_annulled:
        statement = statement.where(Violation.annulled.is_(False))
    return [serialize_violation(database, item) for item in database.scalars(statement)]


@router.post("/inspections/{inspection_id}/violations", response_model=ViolationResponse, status_code=status.HTTP_201_CREATED)
def create_violation(inspection_id: UUID, payload: ViolationCreate, writer: User = RequireWriter, database: Session = Depends(get_db)) -> ViolationResponse:
    inspection = get_inspection(database, inspection_id)
    ensure_inspection_editable(inspection)
    control_type = get_control_type(database, inspection)
    values = payload.model_dump()
    validate_deadline_fields(control_type, values)
    measures = validate_measure_references(database, values["measures"])
    violation_type = validate_violation_type(database, payload.violation_type_id)
    item = Violation(
        inspection_id=inspection_id,
        formulation=payload.formulation.strip(),
        violated_requirement=payload.violated_requirement.strip(),
        violation_type_id=payload.violation_type_id,
        severity=violation_type.severity,
        document_received_date=payload.document_received_date,
        created_by_id=writer.id,
        updated_by_id=writer.id,
    )
    database.add(item)
    database.flush()
    new_measures = add_measures(database, item, measures)
    record_audit(database, actor_id=writer.id, entity_type="violations", entity_id=item.id, action="create", new_value=violation_snapshot(database, item))
    for measure in new_measures:
        record_audit(database, actor_id=writer.id, entity_type="violation_measures", entity_id=measure.id, action="create", new_value=measure_snapshot(measure))
    database.commit()
    database.refresh(item)
    return serialize_violation(database, item)


@router.get("/violations", response_model=list[ViolationResponse])
def list_violations(
    include_annulled: bool = False,
    department_id: UUID | None = Query(default=None),
    object_id: UUID | None = Query(default=None),
    person_id: UUID | None = Query(default=None),
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[ViolationResponse]:
    statement = select(Violation).order_by(Violation.created_at.desc())
    if department_id is not None or object_id is not None or person_id is not None:
        statement = statement.join(ViolationMeasure)
        if department_id is not None:
            statement = statement.where(ViolationMeasure.department_id == department_id)
        if object_id is not None:
            statement = statement.where(ViolationMeasure.object_id == object_id)
        if person_id is not None:
            statement = statement.where(ViolationMeasure.person_id == person_id)
        statement = statement.distinct()
    if not include_annulled:
        statement = statement.where(Violation.annulled.is_(False))
    return [serialize_violation(database, item) for item in database.scalars(statement)]


@router.get("/violations/{violation_id}", response_model=ViolationResponse)
def read_violation(violation_id: UUID, _: User = Depends(get_current_user), database: Session = Depends(get_db)) -> ViolationResponse:
    return serialize_violation(database, get_violation(database, violation_id))


@router.patch("/violations/{violation_id}", response_model=ViolationResponse)
def update_violation(violation_id: UUID, payload: ViolationUpdate, writer: User = RequireWriter, database: Session = Depends(get_db)) -> ViolationResponse:
    item = get_violation(database, violation_id)
    ensure_not_annulled(item)
    ensure_inspection_editable(get_inspection(database, item.inspection_id))
    old_value = violation_snapshot(database, item)
    if payload.formulation is not None:
        item.formulation = payload.formulation.strip()
    if payload.violated_requirement is not None:
        item.violated_requirement = payload.violated_requirement.strip()
    if payload.violation_type_id is not None:
        violation_type = validate_violation_type(database, payload.violation_type_id)
        item.violation_type_id = violation_type.id
        item.severity = violation_type.severity
    if "document_received_date" in payload.model_fields_set:
        control_type = get_control_type(database, get_inspection(database, item.inspection_id))
        validate_deadline_fields(control_type, {"document_received_date": payload.document_received_date})
        item.document_received_date = payload.document_received_date
    item.updated_by_id = writer.id
    record_audit(database, actor_id=writer.id, entity_type="violations", entity_id=item.id, action="update", old_value=old_value, new_value=violation_snapshot(database, item))
    database.commit()
    database.refresh(item)
    return serialize_violation(database, item)


@router.post("/violations/{violation_id}/measures", response_model=ViolationMeasureResponse, status_code=status.HTTP_201_CREATED)
def create_measure(violation_id: UUID, payload: ViolationMeasureInput, writer: User = RequireWriter, database: Session = Depends(get_db)) -> ViolationMeasureResponse:
    violation = get_violation(database, violation_id)
    ensure_not_annulled(violation)
    ensure_inspection_editable(get_inspection(database, violation.inspection_id))
    control_type = get_control_type(database, get_inspection(database, violation.inspection_id))
    values = payload.model_dump()
    validate_deadline_fields(control_type, {"measures": [values]})
    value = validate_measure_references(database, [values])[0]
    measure = add_measures(database, violation, [value])[0]
    record_audit(database, actor_id=writer.id, entity_type="violation_measures", entity_id=measure.id, action="create", new_value=measure_snapshot(measure))
    database.commit()
    database.refresh(measure)
    return serialize_measure(measure)


@router.patch("/measures/{measure_id}", response_model=ViolationMeasureResponse)
def update_measure(measure_id: UUID, payload: ViolationMeasureUpdate, writer: User = RequireWriter, database: Session = Depends(get_db)) -> ViolationMeasureResponse:
    measure = get_measure(database, measure_id)
    violation = get_violation(database, measure.violation_id)
    ensure_not_annulled(violation)
    ensure_inspection_editable(get_inspection(database, violation.inspection_id))
    old_value = measure_snapshot(measure)
    values = {
        "department_id": payload.department_id or measure.department_id,
        "object_id": payload.object_id or measure.object_id,
        "person_id": payload.person_id or measure.person_id,
        "elimination_measure": payload.elimination_measure if payload.elimination_measure is not None else measure.elimination_measure,
    }
    validated = validate_measure_references(database, [values])[0]
    measure.department_id = validated["department_id"]
    measure.object_id = validated["object_id"]
    measure.person_id = validated["person_id"]
    measure.elimination_measure = validated["elimination_measure"]
    database.flush()
    record_audit(database, actor_id=writer.id, entity_type="violation_measures", entity_id=measure.id, action="update", old_value=old_value, new_value=measure_snapshot(measure))
    database.commit()
    database.refresh(measure)
    return serialize_measure(measure)


@router.post("/measures/{measure_id}/elimination", response_model=ViolationMeasureResponse)
def eliminate_measure(measure_id: UUID, payload: EliminationCreate, writer: User = RequireWriter, database: Session = Depends(get_db)) -> ViolationMeasureResponse:
    measure = get_measure(database, measure_id)
    violation = get_violation(database, measure.violation_id)
    ensure_not_annulled(violation)
    inspection = get_inspection(database, violation.inspection_id)
    if payload.elimination_date < inspection.inspection_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Дата устранения не может быть раньше даты проверки")
    old_value = measure_snapshot(measure)
    measure.elimination_date = payload.elimination_date
    measure.eliminated_during_inspection = payload.eliminated_during_inspection
    recalculate_elimination_flags(measure)
    violation.updated_by_id = writer.id
    record_audit(database, actor_id=writer.id, entity_type="violation_measures", entity_id=measure.id, action="eliminate", old_value=old_value, new_value=measure_snapshot(measure))
    database.commit()
    database.refresh(measure)
    return serialize_measure(measure)


@router.post("/violations/{violation_id}/annulment", response_model=ViolationResponse)
def annul_violation(violation_id: UUID, payload: AnnulmentCreate, writer: User = RequireWriter, database: Session = Depends(get_db)) -> ViolationResponse:
    item = get_violation(database, violation_id)
    ensure_not_annulled(item)
    old_value = violation_snapshot(database, item)
    item.annulled = True
    item.annulled_at = utc_now()
    item.annulled_by_id = writer.id
    item.annulment_reason = payload.reason.strip()
    item.updated_by_id = writer.id
    record_audit(database, actor_id=writer.id, entity_type="violations", entity_id=item.id, action="annul", old_value=old_value, new_value=violation_snapshot(database, item), reason=item.annulment_reason)
    database.commit()
    database.refresh(item)
    return serialize_violation(database, item)


@router.get("/measures/{measure_id}/deadline-changes", response_model=list[DeadlineChangeResponse])
def list_deadline_changes(measure_id: UUID, _: User = Depends(get_current_user), database: Session = Depends(get_db)) -> list[DeadlineChange]:
    get_measure(database, measure_id)
    return list(database.scalars(select(DeadlineChange).where(DeadlineChange.violation_measure_id == measure_id).order_by(DeadlineChange.changed_at)))


@router.post("/measures/{measure_id}/deadline-changes", response_model=DeadlineChangeResponse, status_code=status.HTTP_201_CREATED)
def change_deadline(measure_id: UUID, payload: DeadlineChangeCreate, writer: User = RequireWriter, database: Session = Depends(get_db)) -> DeadlineChange:
    measure = get_measure(database, measure_id)
    violation = get_violation(database, measure.violation_id)
    ensure_not_annulled(violation)
    ensure_deadline_control(database, violation)
    if measure.elimination_date is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Нельзя перенести срок устранённого мероприятия")
    if measure.due_date is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="У мероприятия не установлен срок")
    if payload.new_due_date == measure.due_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Новый срок совпадает с текущим")
    old_value = measure_snapshot(measure)
    history = DeadlineChange(
        violation_measure_id=measure.id,
        old_due_date=measure.due_date,
        new_due_date=payload.new_due_date,
        reason=payload.reason.strip(),
        changed_by_id=writer.id,
    )
    measure.due_date = payload.new_due_date
    recalculate_elimination_flags(measure)
    violation.updated_by_id = writer.id
    database.add(history)
    database.flush()
    record_audit(database, actor_id=writer.id, entity_type="violation_measures", entity_id=measure.id, action="change_deadline", old_value=old_value, new_value=measure_snapshot(measure), reason=history.reason)
    database.commit()
    database.refresh(history)
    return history


@router.get("/violations/{violation_id}/repeat-candidates", response_model=list[ViolationResponse])
def list_repeat_candidates(violation_id: UUID, _: User = Depends(get_current_user), database: Session = Depends(get_db)) -> list[ViolationResponse]:
    source = get_violation(database, violation_id)
    if source.annulled:
        return []
    source_measures = measures_for(database, source.id)
    department_ids = [item.department_id for item in source_measures]
    object_ids = [item.object_id for item in source_measures]
    if not department_ids and not object_ids:
        return []
    statement = (
        select(Violation)
        .join(ViolationMeasure)
        .where(
            Violation.id != source.id,
            Violation.annulled.is_(False),
            Violation.violation_type_id == source.violation_type_id,
            or_(ViolationMeasure.department_id.in_(department_ids), ViolationMeasure.object_id.in_(object_ids)),
        )
        .order_by(Violation.created_at.desc())
        .distinct()
    )
    return [serialize_violation(database, item) for item in database.scalars(statement)]


@router.put("/violations/{violation_id}/repeat-links/{candidate_id}", response_model=RepeatLinkResponse)
def decide_repeat_link(violation_id: UUID, candidate_id: UUID, payload: RepeatDecisionUpdate, writer: User = RequireWriter, database: Session = Depends(get_db)) -> RepeatLink:
    source = get_violation(database, violation_id)
    candidate = get_violation(database, candidate_id)
    ensure_not_annulled(source)
    ensure_not_annulled(candidate)
    if source.id == candidate.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Нельзя связать нарушение с самим собой")
    link = database.scalar(select(RepeatLink).where(or_(
        (RepeatLink.source_violation_id == source.id) & (RepeatLink.candidate_violation_id == candidate.id),
        (RepeatLink.source_violation_id == candidate.id) & (RepeatLink.candidate_violation_id == source.id),
    )))
    if link is None:
        link = RepeatLink(source_violation_id=source.id, candidate_violation_id=candidate.id)
        database.add(link)
        action = "create_repeat_link"
        old_value = None
    else:
        action = "decide_repeat_link"
        old_value = {"decision": link.decision}
    link.decision = payload.decision
    link.decided_by_id = writer.id
    link.decided_at = utc_now()
    database.flush()
    record_audit(database, actor_id=writer.id, entity_type="repeat_links", entity_id=link.id, action=action, old_value=old_value, new_value={"decision": link.decision, "source_violation_id": str(link.source_violation_id), "candidate_violation_id": str(link.candidate_violation_id)})
    database.commit()
    database.refresh(link)
    return link
