from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inspection import Inspection, Violation, ViolationMeasure, ViolationStatus
from app.models.reference import ControlType, Department, ProductionObject, ViolationType
from app.schemas.analytics import (
    AnalyticsControlTypeItem,
    AnalyticsDepartmentItem,
    AnalyticsDynamicsPoint,
    AnalyticsObjectItem,
    AnalyticsResponse,
    AnalyticsSeverityItem,
    AnalyticsSummary,
    AnalyticsViolationTypeItem,
)
from app.services.inspections import calculate_violation_status, is_due_soon

ANALYTICS_STATUS_FILTERS = ("eliminated", "not_eliminated", "overdue", "due_soon")
HEAVY_SEVERITY = 8

@dataclass
class MeasureRecord:
    department_id: UUID
    department_name: str
    object_id: UUID
    object_name: str
    due_soon: bool
    eliminated_late: bool


@dataclass
class ViolationRecord:
    id: UUID
    control_type_id: UUID
    control_type_code: str
    control_type_name: str
    control_type_order: int
    violation_type_id: UUID
    violation_type_code: str
    violation_type_name: str
    severity: int
    inspection_date: date
    status: ViolationStatus
    due_soon: bool
    eliminated_late: bool
    measures: list[MeasureRecord] = field(default_factory=list)

    @property
    def heavy(self) -> bool:
        return self.severity >= HEAVY_SEVERITY


def _load_records(
    database: Session,
    date_from: date | None,
    date_to: date | None,
    control_type_id: UUID | None,
    severity: int | None,
) -> list[ViolationRecord]:
    statement = (
        select(Violation, Inspection, ControlType, ViolationType)
        .join(Inspection, Violation.inspection_id == Inspection.id)
        .join(ControlType, Inspection.control_type_id == ControlType.id)
        .join(ViolationType, Violation.violation_type_id == ViolationType.id)
        .where(Violation.annulled.is_(False), ControlType.has_deadline_control.is_(True))
    )
    if date_from is not None:
        statement = statement.where(Inspection.inspection_date >= date_from)
    if date_to is not None:
        statement = statement.where(Inspection.inspection_date <= date_to)
    if control_type_id is not None:
        statement = statement.where(Inspection.control_type_id == control_type_id)
    if severity is not None:
        statement = statement.where(Violation.severity == severity)

    records: list[ViolationRecord] = []
    violation_ids: list[UUID] = []
    for violation, inspection, control_type, violation_type in database.execute(statement):
        violation_ids.append(violation.id)
        records.append(
            ViolationRecord(
                id=violation.id,
                control_type_id=control_type.id,
                control_type_code=control_type.code,
                control_type_name=control_type.name,
                control_type_order=control_type.display_order,
                violation_type_id=violation_type.id,
                violation_type_code=violation_type.code,
                violation_type_name=violation_type.name,
                severity=violation.severity,
                inspection_date=inspection.inspection_date,
                status=ViolationStatus.NOT_ELIMINATED,
                due_soon=False,
                eliminated_late=False,
            )
        )

    if records:
        measure_statement = (
            select(ViolationMeasure, Department, ProductionObject)
            .join(Department, ViolationMeasure.department_id == Department.id)
            .join(ProductionObject, ViolationMeasure.object_id == ProductionObject.id)
            .where(ViolationMeasure.violation_id.in_(violation_ids))
        )
        measures_by_violation: dict[UUID, list[tuple[ViolationMeasure, str, str]]] = defaultdict(list)
        for measure, department, production_object in database.execute(measure_statement):
            measures_by_violation[measure.violation_id].append((measure, department.name, production_object.name))
        by_id = {record.id: record for record in records}
        today = datetime.now(UTC).date()
        for violation_id, pairs in measures_by_violation.items():
            record = by_id[violation_id]
            measures = [measure for measure, _, _ in pairs]
            record.status = calculate_violation_status(Violation(annulled=False), measures, today=today) or record.status
            record.due_soon = any(is_due_soon(measure, today) for measure in measures)
            record.eliminated_late = any(measure.eliminated_late for measure in measures)
            record.measures = [
                MeasureRecord(
                    department_id=measure.department_id,
                    department_name=department_name,
                    object_id=measure.object_id,
                    object_name=object_name,
                    due_soon=is_due_soon(measure, today),
                    eliminated_late=measure.eliminated_late,
                )
                for measure, department_name, object_name in pairs
            ]
    return records


def _matches_status(record: ViolationRecord, status_filter: str | None) -> bool:
    if status_filter is None:
        return True
    if status_filter == "due_soon":
        return record.due_soon
    return record.status == ViolationStatus(status_filter)


def _matches_measures(record: ViolationRecord, department_id: UUID | None, object_id: UUID | None) -> bool:
    if department_id is not None and not any(measure.department_id == department_id for measure in record.measures):
        return False
    if object_id is not None and not any(measure.object_id == object_id for measure in record.measures):
        return False
    return True


def build_analytics(
    database: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    control_type_id: UUID | None = None,
    department_id: UUID | None = None,
    object_id: UUID | None = None,
    severity: int | None = None,
    status_filter: str | None = None,
) -> AnalyticsResponse:
    records = [
        record
        for record in _load_records(database, date_from, date_to, control_type_id, severity)
        if _matches_status(record, status_filter) and _matches_measures(record, department_id, object_id)
    ]

    summary = AnalyticsSummary(
        total=len(records),
        eliminated=sum(1 for record in records if record.status == ViolationStatus.ELIMINATED),
        not_eliminated=sum(1 for record in records if record.status == ViolationStatus.NOT_ELIMINATED),
        overdue=sum(1 for record in records if record.status == ViolationStatus.OVERDUE),
        due_soon=sum(1 for record in records if record.due_soon),
        eliminated_late=sum(1 for record in records if record.eliminated_late),
        heavy=sum(1 for record in records if record.heavy),
    )

    type_groups: dict[UUID, list[ViolationRecord]] = defaultdict(list)
    type_labels: dict[UUID, tuple[int, str, str]] = {}
    for record in records:
        type_groups[record.control_type_id].append(record)
        type_labels[record.control_type_id] = (record.control_type_order, record.control_type_code, record.control_type_name)
    by_control_type = [
        AnalyticsControlTypeItem(
            control_type_id=control_type_id,
            code=type_labels[control_type_id][1],
            name=type_labels[control_type_id][2],
            total=len(group),
            eliminated=sum(1 for record in group if record.status == ViolationStatus.ELIMINATED),
            not_eliminated=sum(1 for record in group if record.status == ViolationStatus.NOT_ELIMINATED),
            overdue=sum(1 for record in group if record.status == ViolationStatus.OVERDUE),
            heavy=sum(1 for record in group if record.heavy),
        )
        for control_type_id, group in type_groups.items()
    ]
    by_control_type.sort(key=lambda item: (type_labels[item.control_type_id][0], item.name))

    severity_groups: dict[int, int] = defaultdict(int)
    for record in records:
        severity_groups[record.severity] += 1
    by_severity = [AnalyticsSeverityItem(severity=key, total=value) for key, value in sorted(severity_groups.items())]

    department_groups: dict[UUID, dict[str, object]] = {}
    object_groups: dict[UUID, dict[str, object]] = {}
    for record in records:
        seen_departments: set[UUID] = set()
        seen_objects: set[UUID] = set()
        for measure in record.measures:
            department_bucket = department_groups.setdefault(
                measure.department_id,
                {"name": measure.department_name, "ids": set(), "statuses": [], "heavy": 0},
            )
            if measure.department_id not in seen_departments:
                seen_departments.add(measure.department_id)
                department_bucket["ids"].add(record.id)
                department_bucket["statuses"].append(record.status)
                department_bucket["heavy"] += 1 if record.heavy else 0
            object_bucket = object_groups.setdefault(
                measure.object_id,
                {"name": measure.object_name, "ids": set(), "heavy": 0},
            )
            if measure.object_id not in seen_objects:
                seen_objects.add(measure.object_id)
                object_bucket["ids"].add(record.id)
                object_bucket["heavy"] += 1 if record.heavy else 0
    by_department = [
        AnalyticsDepartmentItem(
            department_id=department_id,
            name=bucket["name"],
            total=len(bucket["ids"]),
            eliminated=sum(1 for status in bucket["statuses"] if status == ViolationStatus.ELIMINATED),
            not_eliminated=sum(1 for status in bucket["statuses"] if status == ViolationStatus.NOT_ELIMINATED),
            overdue=sum(1 for status in bucket["statuses"] if status == ViolationStatus.OVERDUE),
            heavy=bucket["heavy"],
        )
        for department_id, bucket in department_groups.items()
    ]
    by_department.sort(key=lambda item: (-item.total, item.name))
    by_object = [
        AnalyticsObjectItem(object_id=object_id, name=bucket["name"], total=len(bucket["ids"]), heavy=bucket["heavy"])
        for object_id, bucket in object_groups.items()
    ]
    by_object.sort(key=lambda item: (-item.total, item.name))

    month_groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for record in records:
        month_key = record.inspection_date.strftime("%Y-%m")
        month_groups[month_key][""] += 1
        month_groups[month_key][record.control_type_code] += 1
    dynamics = [
        AnalyticsDynamicsPoint(month=month, total=bucket[""], by_control_type={code: count for code, count in bucket.items() if code})
        for month, bucket in sorted(month_groups.items())
    ]

    violation_type_groups: dict[UUID, dict[str, object]] = {}
    for record in records:
        bucket = violation_type_groups.setdefault(
            record.violation_type_id,
            {"code": record.violation_type_code, "name": record.violation_type_name, "severity": record.severity, "total": 0},
        )
        bucket["total"] += 1
    by_violation_type = [
        AnalyticsViolationTypeItem(
            violation_type_id=violation_type_id,
            code=bucket["code"],
            name=bucket["name"],
            severity=bucket["severity"],
            total=bucket["total"],
        )
        for violation_type_id, bucket in violation_type_groups.items()
    ]
    by_violation_type.sort(key=lambda item: (-item.total, item.code))

    return AnalyticsResponse(
        period_from=date_from,
        period_to=date_to,
        summary=summary,
        by_control_type=by_control_type,
        by_severity=by_severity,
        by_department=by_department,
        by_object=by_object,
        dynamics=dynamics,
        by_violation_type=by_violation_type,
    )
