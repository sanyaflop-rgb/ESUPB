from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.inspection import (
    DeadlineChange,
    Inspection,
    InspectionScope,
    RepeatLink,
    Violation,
    ViolationResponsibleDepartment,
    ViolationResponsiblePerson,
)
from app.models.security import User
from app.schemas.inspections import (
    AnnulmentCreate,
    DeadlineChangeCreate,
    DeadlineChangeResponse,
    EliminationCreate,
    InspectionCreate,
    InspectionResponse,
    InspectionScopeCreate,
    InspectionScopeResponse,
    InspectionStateChange,
    InspectionUpdate,
    RepeatDecisionUpdate,
    RepeatLinkResponse,
    ViolationCreate,
    ViolationResponse,
    ViolationUpdate,
)
from app.services.audit import record_audit
from app.services.inspections import (
    calculate_violation_status,
    ensure_deadline_control,
    ensure_inspection_editable,
    ensure_not_annulled,
    ensure_unique_document_number,
    get_control_type,
    get_inspection,
    get_violation,
    normalize_document_number,
    recalculate_elimination_flags,
    utc_now,
    validate_deadline_fields,
    validate_inspection_references,
    validate_responsible_references,
    validate_scope_for_inspection,
    validate_scope_references,
    validate_state_transition,
    validate_violation_type,
)

router = APIRouter(tags=["Проверки и нарушения"])
RequireWriter = Depends(require_roles("Administrator", "Specialist"))


def inspection_snapshot(item: Inspection) -> dict[str, Any]:
    return {
        "control_type_id": str(item.control_type_id),
        "inspection_kind_id": str(item.inspection_kind_id),
        "document_number": item.document_number,
        "inspection_date": item.inspection_date.isoformat(),
        "state": item.state,
        "comment": item.comment,
    }


def responsible_ids(database: Session, violation_id: UUID) -> tuple[list[UUID], list[UUID]]:
    department_ids = list(
        database.scalars(
            select(ViolationResponsibleDepartment.department_id).where(
                ViolationResponsibleDepartment.violation_id == violation_id
            )
        )
    )
    person_ids = list(
        database.scalars(
            select(ViolationResponsiblePerson.person_id).where(
                ViolationResponsiblePerson.violation_id == violation_id
            )
        )
    )
    return department_ids, person_ids


def serialize_violation(database: Session, item: Violation) -> ViolationResponse:
    department_ids, person_ids = responsible_ids(database, item.id)
    return ViolationResponse(
        id=item.id,
        inspection_id=item.inspection_id,
        inspection_scope_id=item.inspection_scope_id,
        formulation=item.formulation,
        violated_requirement=item.violated_requirement,
        violation_type_id=item.violation_type_id,
        severity=item.severity,
        due_date=item.due_date,
        original_due_date=item.original_due_date,
        due_date_basis=item.due_date_basis,
        due_date_source_text=item.due_date_source_text,
        document_received_date=item.document_received_date,
        elimination_date=item.elimination_date,
        eliminated_during_inspection=item.eliminated_during_inspection,
        eliminated_late=item.eliminated_late,
        days_overdue_at_elimination=item.days_overdue_at_elimination,
        annulled=item.annulled,
        annulled_at=item.annulled_at,
        annulled_by_id=item.annulled_by_id,
        annulment_reason=item.annulment_reason,
        responsible_department_ids=department_ids,
        responsible_person_ids=person_ids,
        status=calculate_violation_status(item),
        created_by_id=item.created_by_id,
        updated_by_id=item.updated_by_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def violation_snapshot(database: Session, item: Violation) -> dict[str, Any]:
    department_ids, person_ids = responsible_ids(database, item.id)
    return {
        "inspection_scope_id": str(item.inspection_scope_id),
        "formulation": item.formulation,
        "violated_requirement": item.violated_requirement,
        "violation_type_id": str(item.violation_type_id),
        "severity": item.severity,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "elimination_date": item.elimination_date.isoformat() if item.elimination_date else None,
        "annulled": item.annulled,
        "responsible_department_ids": [str(value) for value in department_ids],
        "responsible_person_ids": [str(value) for value in person_ids],
    }


def replace_responsibles(
    database: Session,
    violation: Violation,
    department_ids: list[UUID],
    person_ids: list[UUID],
) -> None:
    database.query(ViolationResponsibleDepartment).filter_by(violation_id=violation.id).delete()
    database.query(ViolationResponsiblePerson).filter_by(violation_id=violation.id).delete()
    for department_id in department_ids:
        database.add(ViolationResponsibleDepartment(violation_id=violation.id, department_id=department_id))
    for person_id in person_ids:
        database.add(ViolationResponsiblePerson(violation_id=violation.id, person_id=person_id))
    database.flush()


@router.get("/inspections", response_model=list[InspectionResponse])
def list_inspections(
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[Inspection]:
    return list(database.scalars(select(Inspection).order_by(Inspection.inspection_date.desc(), Inspection.document_number)))


@router.post("/inspections", response_model=InspectionResponse, status_code=status.HTTP_201_CREATED)
def create_inspection(
    payload: InspectionCreate,
    writer: User = RequireWriter,
    database: Session = Depends(get_db),
) -> Inspection:
    validate_inspection_references(database, payload.control_type_id, payload.inspection_kind_id)
    normalized_number = normalize_document_number(payload.document_number)
    ensure_unique_document_number(database, payload.control_type_id, normalized_number)
    item = Inspection(
        control_type_id=payload.control_type_id,
        inspection_kind_id=payload.inspection_kind_id,
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
def read_inspection(
    inspection_id: UUID,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> Inspection:
    return get_inspection(database, inspection_id)


@router.patch("/inspections/{inspection_id}", response_model=InspectionResponse)
def update_inspection(
    inspection_id: UUID,
    payload: InspectionUpdate,
    writer: User = RequireWriter,
    database: Session = Depends(get_db),
) -> Inspection:
    item = get_inspection(database, inspection_id)
    ensure_inspection_editable(item)
    old_value = inspection_snapshot(item)
    if payload.inspection_kind_id is not None:
        validate_inspection_references(database, item.control_type_id, payload.inspection_kind_id)
        item.inspection_kind_id = payload.inspection_kind_id
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
def change_inspection_state(
    inspection_id: UUID,
    payload: InspectionStateChange,
    writer: User = RequireWriter,
    database: Session = Depends(get_db),
) -> Inspection:
    item = get_inspection(database, inspection_id)
    validate_state_transition(item.state, payload.state)
    old_value = inspection_snapshot(item)
    item.state = payload.state
    item.updated_by_id = writer.id
    record_audit(database, actor_id=writer.id, entity_type="inspections", entity_id=item.id, action="change_state", old_value=old_value, new_value=inspection_snapshot(item))
    database.commit()
    database.refresh(item)
    return item


@router.get("/inspections/{inspection_id}/scopes", response_model=list[InspectionScopeResponse])
def list_scopes(
    inspection_id: UUID,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[InspectionScope]:
    get_inspection(database, inspection_id)
    return list(database.scalars(select(InspectionScope).where(InspectionScope.inspection_id == inspection_id)))


@router.post("/inspections/{inspection_id}/scopes", response_model=InspectionScopeResponse, status_code=status.HTTP_201_CREATED)
def create_scope(
    inspection_id: UUID,
    payload: InspectionScopeCreate,
    writer: User = RequireWriter,
    database: Session = Depends(get_db),
) -> InspectionScope:
    inspection = get_inspection(database, inspection_id)
    ensure_inspection_editable(inspection)
    validate_scope_references(database, payload.department_id, payload.object_id)
    item = InspectionScope(
        inspection_id=inspection_id,
        department_id=payload.department_id,
        object_id=payload.object_id,
        comment=payload.comment.strip() if payload.comment else None,
    )
    database.add(item)
    database.flush()
    record_audit(database, actor_id=writer.id, entity_type="inspection_scopes", entity_id=item.id, action="create", new_value={"inspection_id": str(inspection_id), "department_id": str(item.department_id), "object_id": str(item.object_id)})
    database.commit()
    database.refresh(item)
    return item


@router.get("/inspections/{inspection_id}/violations", response_model=list[ViolationResponse])
def list_inspection_violations(
    inspection_id: UUID,
    include_annulled: bool = False,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[ViolationResponse]:
    get_inspection(database, inspection_id)
    statement = select(Violation).where(Violation.inspection_id == inspection_id).order_by(Violation.created_at)
    if not include_annulled:
        statement = statement.where(Violation.annulled.is_(False))
    return [serialize_violation(database, item) for item in database.scalars(statement)]


@router.post("/inspections/{inspection_id}/violations", response_model=ViolationResponse, status_code=status.HTTP_201_CREATED)
def create_violation(
    inspection_id: UUID,
    payload: ViolationCreate,
    writer: User = RequireWriter,
    database: Session = Depends(get_db),
) -> ViolationResponse:
    inspection = get_inspection(database, inspection_id)
    ensure_inspection_editable(inspection)
    control_type = get_control_type(database, inspection)
    validate_deadline_fields(control_type, payload.model_dump())
    scope = database.get(InspectionScope, payload.inspection_scope_id)
    validate_scope_for_inspection(scope, inspection_id)
    violation_type = validate_violation_type(database, payload.violation_type_id)
    department_ids, person_ids = validate_responsible_references(database, payload.responsible_department_ids, payload.responsible_person_ids)
    item = Violation(
        inspection_id=inspection_id,
        inspection_scope_id=payload.inspection_scope_id,
        formulation=payload.formulation.strip(),
        violated_requirement=payload.violated_requirement.strip(),
        violation_type_id=payload.violation_type_id,
        severity=violation_type.severity,
        due_date=payload.due_date,
        original_due_date=payload.due_date,
        due_date_basis=payload.due_date_basis.strip() if payload.due_date_basis else None,
        due_date_source_text=payload.due_date_source_text.strip() if payload.due_date_source_text else None,
        document_received_date=payload.document_received_date,
        created_by_id=writer.id,
        updated_by_id=writer.id,
    )
    database.add(item)
    database.flush()
    replace_responsibles(database, item, department_ids, person_ids)
    record_audit(database, actor_id=writer.id, entity_type="violations", entity_id=item.id, action="create", new_value=violation_snapshot(database, item))
    database.commit()
    database.refresh(item)
    return serialize_violation(database, item)


@router.get("/violations", response_model=list[ViolationResponse])
def list_violations(
    include_annulled: bool = False,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[ViolationResponse]:
    statement = select(Violation).order_by(Violation.created_at.desc())
    if not include_annulled:
        statement = statement.where(Violation.annulled.is_(False))
    return [serialize_violation(database, item) for item in database.scalars(statement)]


@router.get("/violations/{violation_id}", response_model=ViolationResponse)
def read_violation(
    violation_id: UUID,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> ViolationResponse:
    return serialize_violation(database, get_violation(database, violation_id))


@router.patch("/violations/{violation_id}", response_model=ViolationResponse)
def update_violation(
    violation_id: UUID,
    payload: ViolationUpdate,
    writer: User = RequireWriter,
    database: Session = Depends(get_db),
) -> ViolationResponse:
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
    if payload.responsible_department_ids is not None or payload.responsible_person_ids is not None:
        current_departments, current_persons = responsible_ids(database, item.id)
        department_ids, person_ids = validate_responsible_references(
            database,
            payload.responsible_department_ids if payload.responsible_department_ids is not None else current_departments,
            payload.responsible_person_ids if payload.responsible_person_ids is not None else current_persons,
        )
        replace_responsibles(database, item, department_ids, person_ids)
    item.updated_by_id = writer.id
    record_audit(database, actor_id=writer.id, entity_type="violations", entity_id=item.id, action="update", old_value=old_value, new_value=violation_snapshot(database, item))
    database.commit()
    database.refresh(item)
    return serialize_violation(database, item)


@router.post("/violations/{violation_id}/elimination", response_model=ViolationResponse)
def eliminate_violation(
    violation_id: UUID,
    payload: EliminationCreate,
    writer: User = RequireWriter,
    database: Session = Depends(get_db),
) -> ViolationResponse:
    item = get_violation(database, violation_id)
    ensure_not_annulled(item)
    inspection = get_inspection(database, item.inspection_id)
    if payload.elimination_date < inspection.inspection_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Дата устранения не может быть раньше даты проверки")
    old_value = violation_snapshot(database, item)
    item.elimination_date = payload.elimination_date
    item.eliminated_during_inspection = payload.eliminated_during_inspection
    recalculate_elimination_flags(item)
    item.updated_by_id = writer.id
    record_audit(database, actor_id=writer.id, entity_type="violations", entity_id=item.id, action="eliminate", old_value=old_value, new_value=violation_snapshot(database, item))
    database.commit()
    database.refresh(item)
    return serialize_violation(database, item)


@router.post("/violations/{violation_id}/annulment", response_model=ViolationResponse)
def annul_violation(
    violation_id: UUID,
    payload: AnnulmentCreate,
    writer: User = RequireWriter,
    database: Session = Depends(get_db),
) -> ViolationResponse:
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


@router.get("/violations/{violation_id}/deadline-changes", response_model=list[DeadlineChangeResponse])
def list_deadline_changes(
    violation_id: UUID,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[DeadlineChange]:
    get_violation(database, violation_id)
    return list(database.scalars(select(DeadlineChange).where(DeadlineChange.violation_id == violation_id).order_by(DeadlineChange.changed_at)))


@router.post("/violations/{violation_id}/deadline-changes", response_model=DeadlineChangeResponse, status_code=status.HTTP_201_CREATED)
def change_deadline(
    violation_id: UUID,
    payload: DeadlineChangeCreate,
    writer: User = RequireWriter,
    database: Session = Depends(get_db),
) -> DeadlineChange:
    item = get_violation(database, violation_id)
    ensure_not_annulled(item)
    ensure_deadline_control(database, item)
    if item.elimination_date is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Нельзя перенести срок устранённого нарушения")
    if item.due_date is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="У нарушения не установлен срок")
    if payload.new_due_date == item.due_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Новый срок совпадает с текущим")
    old_value = violation_snapshot(database, item)
    history = DeadlineChange(
        violation_id=item.id,
        old_due_date=item.due_date,
        new_due_date=payload.new_due_date,
        reason=payload.reason.strip(),
        changed_by_id=writer.id,
    )
    item.due_date = payload.new_due_date
    recalculate_elimination_flags(item)
    item.updated_by_id = writer.id
    database.add(history)
    database.flush()
    record_audit(database, actor_id=writer.id, entity_type="violations", entity_id=item.id, action="change_deadline", old_value=old_value, new_value=violation_snapshot(database, item), reason=history.reason)
    database.commit()
    database.refresh(history)
    return history


@router.get("/violations/{violation_id}/repeat-candidates", response_model=list[ViolationResponse])
def list_repeat_candidates(
    violation_id: UUID,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[ViolationResponse]:
    source = get_violation(database, violation_id)
    source_scope = database.get(InspectionScope, source.inspection_scope_id)
    if source.annulled or source_scope is None:
        return []
    statement = (
        select(Violation)
        .join(InspectionScope, Violation.inspection_scope_id == InspectionScope.id)
        .where(
            Violation.id != source.id,
            Violation.annulled.is_(False),
            Violation.violation_type_id == source.violation_type_id,
            or_(
                InspectionScope.department_id == source_scope.department_id,
                InspectionScope.object_id == source_scope.object_id,
            ),
        )
        .order_by(Violation.created_at.desc())
    )
    return [serialize_violation(database, item) for item in database.scalars(statement)]


@router.put("/violations/{violation_id}/repeat-links/{candidate_id}", response_model=RepeatLinkResponse)
def decide_repeat_link(
    violation_id: UUID,
    candidate_id: UUID,
    payload: RepeatDecisionUpdate,
    writer: User = RequireWriter,
    database: Session = Depends(get_db),
) -> RepeatLink:
    source = get_violation(database, violation_id)
    candidate = get_violation(database, candidate_id)
    ensure_not_annulled(source)
    ensure_not_annulled(candidate)
    if source.id == candidate.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Нельзя связать нарушение с самим собой")
    link = database.scalar(
        select(RepeatLink).where(
            or_(
                (RepeatLink.source_violation_id == source.id) & (RepeatLink.candidate_violation_id == candidate.id),
                (RepeatLink.source_violation_id == candidate.id) & (RepeatLink.candidate_violation_id == source.id),
            )
        )
    )
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
