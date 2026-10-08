from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.assessment import AssessmentCriterion, AssessmentFact, AssessmentResult
from app.models.reference import Department
from app.models.security import User
from app.schemas.assessment import (
    AssessmentComputeRequest,
    AssessmentComputeResponse,
    AssessmentCriterionResponse,
    AssessmentFactResponse,
    AssessmentFactSave,
    AssessmentResultDetail,
    AssessmentResultResponse,
    AssessmentResultSave,
)
from app.services.assessment import SERVICE_SUBJECT_KEY, compute_assessment, save_fact, subject_key_for

router = APIRouter(tags=["assessment"])


def _checked_department_name(database: Session, department_id: UUID | None) -> str | None:
    if department_id is None:
        return None
    department = database.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Подразделение не найдено")
    return department.name


def _fact_response(fact: AssessmentFact, criterion_code: str) -> AssessmentFactResponse:
    return AssessmentFactResponse.model_validate(fact).model_copy(update={"criterion_code": criterion_code})


@router.get("/assessment/criteria", response_model=list[AssessmentCriterionResponse])
def assessment_criteria(
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[AssessmentCriterionResponse]:
    criteria = database.scalars(
        select(AssessmentCriterion)
        .where(AssessmentCriterion.is_active.is_(True))
        .order_by(AssessmentCriterion.display_order)
    )
    return [AssessmentCriterionResponse.model_validate(criterion) for criterion in criteria]


@router.post("/assessment/compute", response_model=AssessmentComputeResponse)
def assessment_compute(
    request: AssessmentComputeRequest,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AssessmentComputeResponse:
    _checked_department_name(database, request.department_id)
    try:
        return compute_assessment(
            database,
            period_type=request.period_type,
            period_year=request.period_year,
            period_index=request.period_index,
            department_id=request.department_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error


@router.get("/assessment/facts", response_model=list[AssessmentFactResponse])
def assessment_facts(
    period_type: str = Query(pattern="^(quarter|half_year|nine_months|year)$"),
    period_year: int = Query(ge=2000, le=2100),
    period_index: int = Query(ge=1, le=4),
    department_id: UUID | None = Query(default=None),
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[AssessmentFactResponse]:
    _checked_department_name(database, department_id)
    subject_keys = [SERVICE_SUBJECT_KEY]
    if department_id is not None:
        subject_keys.append(f"department:{department_id}")
    rows = database.execute(
        select(AssessmentFact, AssessmentCriterion.criterion_code)
        .join(AssessmentCriterion, AssessmentFact.criterion_id == AssessmentCriterion.id)
        .where(
            AssessmentFact.period_year == period_year,
            AssessmentFact.period_type == period_type,
            AssessmentFact.period_index == period_index,
            AssessmentFact.subject_key.in_(subject_keys),
        )
        .order_by(AssessmentCriterion.display_order)
    ).all()
    return [_fact_response(fact, criterion_code) for fact, criterion_code in rows]


@router.post("/assessment/facts", response_model=AssessmentFactResponse)
def assessment_fact_save(
    payload: AssessmentFactSave,
    current_user: User = Depends(require_roles("Administrator", "Specialist")),
    database: Session = Depends(get_db),
) -> AssessmentFactResponse:
    criterion = database.get(AssessmentCriterion, payload.criterion_id)
    if criterion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Критерий не найден")
    _checked_department_name(database, payload.department_id)
    try:
        fact = save_fact(
            database,
            criterion,
            period_type=payload.period_type,
            period_year=payload.period_year,
            period_index=payload.period_index,
            department_id=payload.department_id,
            values=payload.values,
            not_applicable=payload.not_applicable,
            comment=payload.comment,
            user_id=current_user.id,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    database.commit()
    database.refresh(fact)
    return _fact_response(fact, criterion.criterion_code)


@router.post("/assessment/results", response_model=AssessmentResultResponse)
def assessment_result_save(
    payload: AssessmentResultSave,
    current_user: User = Depends(require_roles("Administrator", "Specialist")),
    database: Session = Depends(get_db),
) -> AssessmentResultResponse:
    department_name = _checked_department_name(database, payload.department_id)
    try:
        computed = compute_assessment(
            database,
            period_type=payload.period_type,
            period_year=payload.period_year,
            period_index=payload.period_index,
            department_id=payload.department_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    subject_key = subject_key_for(computed.subject_type, payload.department_id)
    result = database.scalar(
        select(AssessmentResult).where(
            AssessmentResult.period_year == payload.period_year,
            AssessmentResult.period_type == payload.period_type,
            AssessmentResult.period_index == payload.period_index,
            AssessmentResult.subject_key == subject_key,
        )
    )
    if result is None:
        result = AssessmentResult(
            period_year=payload.period_year,
            period_type=payload.period_type,
            period_index=payload.period_index,
            subject_type=computed.subject_type,
            department_id=payload.department_id,
            subject_key=subject_key,
            created_by_id=current_user.id,
        )
        database.add(result)
    result.criteria_payload = [item.model_dump(mode="json") for item in computed.criteria]
    result.average_score = computed.summary.average_score
    result.verdict = computed.summary.verdict
    result.applicable_count = computed.summary.applicable_count
    result.not_applicable_count = computed.summary.not_applicable_count
    result.missing_input_count = computed.summary.missing_input_count
    result.created_by_id = current_user.id
    database.commit()
    database.refresh(result)
    return AssessmentResultResponse.model_validate(result).model_copy(update={"department_name": department_name})


@router.get("/assessment/results", response_model=list[AssessmentResultResponse])
def assessment_results(
    period_type: str | None = Query(default=None, pattern="^(quarter|half_year|nine_months|year)$"),
    period_year: int | None = Query(default=None, ge=2000, le=2100),
    department_id: UUID | None = Query(default=None),
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[AssessmentResultResponse]:
    statement = (
        select(AssessmentResult, Department.name)
        .join(Department, AssessmentResult.department_id == Department.id, isouter=True)
        .order_by(AssessmentResult.period_year.desc(), AssessmentResult.period_index.desc(), Department.name)
    )
    if period_type is not None:
        statement = statement.where(AssessmentResult.period_type == period_type)
    if period_year is not None:
        statement = statement.where(AssessmentResult.period_year == period_year)
    if department_id is not None:
        statement = statement.where(
            AssessmentResult.subject_key.in_([SERVICE_SUBJECT_KEY, f"department:{department_id}"])
        )
    rows = database.execute(statement).all()
    return [
        AssessmentResultResponse.model_validate(result).model_copy(update={"department_name": department_name})
        for result, department_name in rows
    ]


@router.get("/assessment/results/{result_id}", response_model=AssessmentResultDetail)
def assessment_result_detail(
    result_id: UUID,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AssessmentResultDetail:
    row = database.execute(
        select(AssessmentResult, Department.name)
        .join(Department, AssessmentResult.department_id == Department.id, isouter=True)
        .where(AssessmentResult.id == result_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Результат оценки не найден")
    result, department_name = row
    return AssessmentResultDetail.model_validate(result).model_copy(update={"department_name": department_name})
