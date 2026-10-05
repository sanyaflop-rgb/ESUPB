"""Создать справочники, RBAC и аудит.

Revision ID: 20261005_01
Revises:
Create Date: 2026-10-05
"""
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20261005_01"
down_revision = None
branch_labels = None
depends_on = None


ROLES = [
    ("Administrator", "Администратор", "Полный доступ к системе"),
    ("Specialist", "Специалист СППБиБДД", "Рабочая роль специалиста производственного контроля"),
    ("Manager", "Руководитель", "Просмотр, аналитика, отчёты и экспорт"),
    ("DepartmentResponsible", "Ответственный подразделения", "Работа с назначенными нарушениями"),
]
CONTROL_TYPES = [
    ("PC_III", "ПК III уровня", True),
    ("PC_II", "ПК II уровня", False),
    ("ROSTECHNADZOR", "Ростехнадзор", True),
    ("GAZNADZOR", "Газнадзор", True),
]
INSPECTION_KINDS = [("PLANNED", "Плановая"), ("UNSCHEDULED", "Внеплановая"), ("TARGETED", "Целевая")]
GROUPS = [
    ("1", "Документация"),
    ("2", "Экспертиза промышленной безопасности"),
    ("3", "Готовность к ликвидации последствий аварий и инцидентов"),
    ("4", "Оформление информационными знаками и знаками безопасности"),
    ("5", "Содержание объектов и оборудования"),
    ("6", "Организация рабочего процесса и безопасности персонала"),
]
VIOLATION_TYPES = [
    ("1", "1.1", "Оформление документации по работам повышенной опасности (наряды-допуски, перечни, журналы регистрации, инструкции и т.д.)", 7),
    ("1", "1.2", "Оформление разрешительной документации (лицензии и т.д)", 7),
    ("1", "1.3.1", "Оформления деклараций и прочие", 7),
    ("1", "1.3.2", "Оформление свидетельств о регистрации ОПО (идентификация и регистрация ОПО)", 7),
    ("1", "1.3.3", "Проектная документация (отсутствие, частичное отсутствие и не внесение информации)", 7),
    ("1", "1.4", "Оформление руководящих документов (приказы, технологические регламенты, схемы, инструкции, графики, режимные карты, технологические карты и т.д.)", 6),
    ("1", "1.5", "Оформление и предоставление отчетности", 3),
    ("1", "1.6", "Ведение эксплуатационной документации (журналы, формуляры, паспорта на оборудование и т.д.)", 4),
    ("1", "1.7", "Наличия и оформления исполнительной документации", 5),
    ("1", "1.8", "Оформление документации по регламентным работам", 6),
    ("2", "2.1", "Эксплуатация оборудования за пределами расчетного срока службы без проведения экспертизы промышленной безопасности", 9),
    ("2", "2.2", "Эксплуатация оборудования с неисполненными обязательными условиями экспертизы промышленной безопасности", 9),
    ("2", "2.3", "Несоответствия в части содержания (оформления) экспертизы промышленной безопасности", 5),
    ("2", "2.4", "Регистрация заключения экспертизы промышленной безопасности, порядок хранения и использования (в т.ч. отметка о разрешении на дальнейшую эксплуатацию, ознакомление ответственных лиц с ЗЭПБ)", 4),
    ("3", "3.1", "Содержание и оформление Плана мероприятий по локализации и ликвидации последствий аварий (ПМЛА) (в т.ч. учет всех возможных сценариев)", 6),
    ("3", "3.2", "Отсутствие согласования ПМЛА (с аварийно-спасательными формированиями (АСФ) и третьими лицами), в т.ч. договора с АСФ, наличие собственной АСФ", 6),
    ("3", "3.3", "Содержание аварийного запаса", 7),
    ("3", "3.4", "Аварийное освещение, сигнализация, противоаварийная автоматика", 8),
    ("3", "3.5", "Проведение противоаварийных тренировок (в т.ч. несвоевременное либо непроведение отдельным специалистам)", 7),
    ("3", "3.6", "Готовность и техническое состояние АВП, УАВР, ПАСФ, НАСФ и т.д.", 8),
    ("3", "3.7", "Не размещена на видном месте оперативная часть ПМЛА", 5),
    ("3", "3.8", "Оформление результатов проведения противоаварийных тренировок", 5),
    ("3", "3.9", "Отсутствие ознакомления сотрудников с ПМЛА", 4),
    ("4", "4.1", "Информационное обозначение контрольно-измерительных приборов", 3),
    ("4", "4.2", "Обозначения (маркировка) трубопровода", 4),
    ("4", "4.3", "Обозначения технических устройств (информация о маркировке, номере, положении затвора и т.п.)", 4),
    ("4", "4.4", "Знаки безопасности", 5),
    ("4", "4.5", "Информационные знаки", 4),
    ("5", "5.1", "Несоответствие конструктивного исполнения оборудования действующим НТД", 7),
    ("5", "5.2", "Несоответствия в части целостности и исправности (работоспособности) оборудования", 9),
    ("5", "5.3", "Несоответствия в части необходимого наличия и состояния контрольно-измерительных приборов", 6),
    ("5", "5.4", "Непроектное выполнение оборудования", 8),
    ("5", "5.5", "Несоответствия в части содержания территорий, зданий и ограждений объектов", 3),
    ("5", "5.6", "Несоответствия установленным требованиям защитного покрытия трубопроводов, фундаментов и оборудования", 4),
    ("5", "5.7", "Несоответствия в части организации и проведении диагностических работ", 6),
    ("5", "5.8", "Не соблюдение требований при складировании технических устройств", 3),
    ("5", "5.9", "Несоответствия при проведении регламентных работ (технического обслуживания, текущего ремонта и т.д.)", 7),
    ("5", "5.10", "Несоответствия при проведении работ повышенной опасности", 9),
    ("5", "5.11", "Несоответствие НТД, отсутствие или повреждение охранной сигнализации по периметру ограждения КС, ГРС, СКЗ", 4),
    ("5", "5.12", "Несоответствия, связанные с режимами эксплуатации", 8),
    ("5", "5.13", "Утечки газа", 8),
    ("5", "5.14", "Несоответствия, связанные с поверкой контрольно-измерительных приборов и средств измерений", 5),
    ("6", "6.1", "Оснащенность и укомплектованность служб и подразделений", 6),
    ("6", "6.2", "Несоответствия в части организации, проведения, оформления результатов АПК", 6),
    ("6", "6.3", "Несоответствие при проведении инструктажей, обучения, аттестации и т.д., неинформирование персонала", 6),
]


def common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def reference_columns() -> list[sa.Column]:
    return [
        *common_columns(),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    op.create_table(
        "roles", *common_columns(),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_roles_code", "roles", ["code"])
    op.create_table(
        "users", *common_columns(),
        sa.Column("login", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("login"),
    )
    op.create_index("ix_users_login", "users", ["login"])
    op.create_index("ix_users_is_active", "users", ["is_active"])
    op.create_table(
        "user_roles", *common_columns(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role_id", sa.Uuid(), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )
    op.create_table(
        "departments", *reference_columns(),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("departments.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_departments_is_active", "departments", ["is_active"])
    op.create_table(
        "objects", *reference_columns(),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_department_id", sa.Uuid(), sa.ForeignKey("departments.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_objects_is_active", "objects", ["is_active"])
    op.create_table(
        "persons", *reference_columns(),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("position", sa.String(length=255)),
        sa.Column("department_id", sa.Uuid(), sa.ForeignKey("departments.id", ondelete="RESTRICT")),
    )
    op.create_index("ix_persons_is_active", "persons", ["is_active"])
    op.create_table(
        "control_types", *reference_columns(),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("has_deadline_control", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_control_types_is_active", "control_types", ["is_active"])
    op.create_table(
        "inspection_kinds", *reference_columns(),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_inspection_kinds_is_active", "inspection_kinds", ["is_active"])
    op.create_table(
        "violation_groups", *reference_columns(),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_violation_groups_is_active", "violation_groups", ["is_active"])
    op.create_table(
        "violation_types", *reference_columns(),
        sa.Column("group_id", sa.Uuid(), sa.ForeignKey("violation_groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.CheckConstraint("severity BETWEEN 1 AND 9", name="ck_violation_types_severity_range"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("group_id", "code", name="uq_violation_types_group_code"),
    )
    op.create_index("ix_violation_types_is_active", "violation_types", ["is_active"])
    op.create_table(
        "audit_log", *common_columns(),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("old_value", sa.JSON()),
        sa.Column("new_value", sa.JSON()),
        sa.Column("reason", sa.Text()),
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_entity_type", "audit_log", ["entity_type"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])

    now = datetime.now(UTC)
    roles = sa.table("roles", sa.column("id", sa.Uuid()), sa.column("code", sa.String()), sa.column("name", sa.String()), sa.column("description", sa.Text()), sa.column("is_system", sa.Boolean()), sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)))
    op.bulk_insert(roles, [{"id": uuid4(), "code": code, "name": name, "description": description, "is_system": True, "created_at": now, "updated_at": now} for code, name, description in ROLES])
    controls = sa.table("control_types", sa.column("id", sa.Uuid()), sa.column("code", sa.String()), sa.column("name", sa.String()), sa.column("has_deadline_control", sa.Boolean()), sa.column("is_active", sa.Boolean()), sa.column("display_order", sa.Integer()), sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)))
    op.bulk_insert(controls, [{"id": uuid4(), "code": code, "name": name, "has_deadline_control": deadlines, "is_active": True, "display_order": index, "created_at": now, "updated_at": now} for index, (code, name, deadlines) in enumerate(CONTROL_TYPES, 1)])
    kinds = sa.table("inspection_kinds", sa.column("id", sa.Uuid()), sa.column("code", sa.String()), sa.column("name", sa.String()), sa.column("is_active", sa.Boolean()), sa.column("display_order", sa.Integer()), sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)))
    op.bulk_insert(kinds, [{"id": uuid4(), "code": code, "name": name, "is_active": True, "display_order": index, "created_at": now, "updated_at": now} for index, (code, name) in enumerate(INSPECTION_KINDS, 1)])
    groups = sa.table("violation_groups", sa.column("id", sa.Uuid()), sa.column("code", sa.String()), sa.column("name", sa.String()), sa.column("is_active", sa.Boolean()), sa.column("display_order", sa.Integer()), sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)))
    group_ids = {code: uuid4() for code, _ in GROUPS}
    op.bulk_insert(groups, [{"id": group_ids[code], "code": code, "name": name, "is_active": True, "display_order": int(code), "created_at": now, "updated_at": now} for code, name in GROUPS])
    types = sa.table("violation_types", sa.column("id", sa.Uuid()), sa.column("group_id", sa.Uuid()), sa.column("code", sa.String()), sa.column("name", sa.Text()), sa.column("severity", sa.Integer()), sa.column("is_active", sa.Boolean()), sa.column("display_order", sa.Integer()), sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)))
    op.bulk_insert(types, [{"id": uuid4(), "group_id": group_ids[group_code], "code": code, "name": name, "severity": severity, "is_active": True, "display_order": index, "created_at": now, "updated_at": now} for index, (group_code, code, name, severity) in enumerate(VIOLATION_TYPES, 1)])


def downgrade() -> None:
    for table in ["audit_log", "violation_types", "violation_groups", "inspection_kinds", "control_types", "persons", "objects", "departments", "user_roles", "users", "roles"]:
        op.drop_table(table)
