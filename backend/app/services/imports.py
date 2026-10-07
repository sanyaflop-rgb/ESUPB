from datetime import date
from io import BytesIO
from pathlib import Path
import re

from docx import Document
from fastapi import HTTPException, status
from openpyxl import load_workbook


MAX_IMPORT_SIZE = 10 * 1024 * 1024
REQUIRED_FIELDS = ("formulation", "requirement", "measure", "responsible")
PERSON_NAME_PATTERN = re.compile(r"([А-ЯЁ][а-яёЁ\-]+)\s+([А-ЯЁ])\.\s*([А-ЯЁ])\.", re.IGNORECASE)


def _cell(value: object) -> str:
    return "" if value is None else str(value).strip()


def _is_numbering_row(row: list[str]) -> bool:
    populated = [value.strip() for value in row if value.strip()]
    return bool(populated) and all(value.isdigit() for value in populated)


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).casefold()


def suggest_mapping(headers: list[str], supplied_mapping: dict[str, str]) -> dict[str, str]:
    """Fill omitted mappings from common Russian inspection-document headings."""
    mapping = {key: value for key, value in supplied_mapping.items() if value in headers}
    normalized = [_normalized(header) for header in headers]
    claimed: set[str] = set()

    def find(tokens: tuple[str, ...]) -> str:
        return next(
            (
                header
                for index, header in enumerate(headers)
                if header not in claimed and any(token in normalized[index] for token in tokens)
            ),
            "",
        )

    def claim(header: str) -> str:
        if header:
            claimed.add(header)
        return header

    def is_numbering(header: str) -> bool:
        compact = re.sub(r"[^a-zа-яё0-9]", "", _normalized(header))
        return compact in {"", "n", "no", "пп", "номер", "номерпп"} or compact.isdigit()

    responsible_header = claim(find(("ответствен",)))
    # «Меры и срок устранения» is a measure column that mentions the deadline,
    # so measure must be claimed before the due column to keep them apart.
    measure_header = claim(find(("мероприят",)) or find(("меры", "устранени")))
    due_header = claim(find(("срок", "дата устранения")))
    requirement_header = find(("требован",))
    content_header = find(("формулировк", "содержание нарушения", "несоответств", "выявленн", "нарушени", "описание"))
    if not content_header:
        content_header = next(
            (
                header
                for header in headers
                if header not in claimed and header != requirement_header and not is_numbering(header)
            ),
            "",
        )
    for field, header in {
        "formulation": content_header,
        "requirement": requirement_header or content_header,
        "measure": measure_header,
        "responsible": responsible_header,
        "due_date": due_header,
    }.items():
        if not mapping.get(field) and header:
            mapping[field] = header
    return mapping


DATE_PATTERN = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})")


def parse_date_value(value: str) -> date | None:
    """Parse the first date found in a cell, tolerant to «до 30.10.2026» and «30.10.2026 г.»."""
    match = DATE_PATTERN.search(value)
    if not match:
        return None
    day, month, year = match.groups()
    if len(year) == 2:
        year = f"20{year}"
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def extract_due_date(value: str) -> date | None:
    match = re.search(r"(?:срок|исполнить\s+до)\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", value, re.IGNORECASE)
    if not match:
        return None
    raw_value = match.group(1).replace("/", ".").replace("-", ".")
    day, month, year = raw_value.split(".")
    if len(year) == 2:
        year = f"20{year}"
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def parse_responsible(value: str) -> dict[str, str | None]:
    """Extract «Фамилия И.О.» and the leading position text from a responsible cell."""
    text = re.sub(r"\s+", " ", value.replace("\n", " ")).strip()
    match = PERSON_NAME_PATTERN.search(text)
    if not match:
        return {"name": None, "position": text or None}
    surname, first_initial, second_initial = match.groups()
    name = f"{surname} {first_initial.upper()}.{second_initial.upper()}."
    position = re.sub(r"\s+", " ", f"{text[:match.start()]} {text[match.end():]}").strip(" |,;·").strip()
    return {"name": name, "position": position or None}


def _fold(value: str) -> str:
    return value.casefold().replace("ё", "е")


def person_key(full_name: str) -> tuple[str, str] | None:
    """Normalize «Фамилия Имя Отчество» and «Фамилия И.О.» to a comparable key."""
    words = [word for word in re.split(r"\s+", full_name.strip()) if word]
    if len(words) < 2:
        return None
    if any("." in word for word in words[1:]):
        letters = re.sub(r"[^А-ЯЁа-яё]", "", "".join(words[1:]))
        initials = letters[:2]
    else:
        initials = "".join(word[0] for word in words[1:3])
    initials = initials.upper()
    if len(initials) < 2:
        return None
    return (_fold(words[0]), initials)


def resolve_responsibles(rows: list[dict[str, object]], mapping: dict[str, str], persons: list[tuple[object, str]]) -> None:
    """Attach parsed and reference-matched responsible info to preview rows."""
    column = mapping.get("responsible", "")
    index: dict[tuple[str, str], tuple[object, str]] = {}
    for person_id, full_name in persons:
        key = person_key(full_name)
        if key is not None and key not in index:
            index[key] = (person_id, full_name)
    for row in rows:
        values = row["values"]
        raw = values.get(column, "") if column and isinstance(values, dict) else ""
        raw = raw.strip() if isinstance(raw, str) else ""
        if not raw:
            row["responsible"] = None
            continue
        parsed = parse_responsible(raw)
        matched_id: object | None = None
        matched_name: str | None = None
        name = parsed["name"]
        if name:
            key = person_key(name)
            if key is not None and key in index:
                matched_id, matched_name = index[key]
        row["responsible"] = {
            "raw": raw,
            "name": name,
            "position": parsed["position"],
            "person_id": matched_id,
            "person_name": matched_name,
        }


def parse_import_file(file_name: str, content: bytes, header_row: int) -> tuple[list[str], list[list[str]]]:
    if len(content) > MAX_IMPORT_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Размер файла не должен превышать 10 МБ")
    suffix = Path(file_name).suffix.lower()
    if header_row < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Номер строки заголовков должен быть не меньше 1")
    if suffix in {".xlsx", ".xls"}:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        rows = [[_cell(value) for value in row] for row in workbook.active.iter_rows(values_only=True)]
    elif suffix == ".docx":
        document = Document(BytesIO(content))
        if not document.tables:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="В документе Word не найдена таблица")
        rows = [[_cell(cell.text) for cell in row.cells] for row in document.tables[0].rows]
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Поддерживаются только файлы .xlsx, .xls и .docx")
    if len(rows) < header_row:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Указанная строка заголовков отсутствует в файле")
    headers = rows[header_row - 1]
    if not any(headers):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Строка заголовков пуста")
    return headers, rows[header_row:]


def preview_rows(headers: list[str], rows: list[list[str]], supplied_mapping: dict[str, str]) -> tuple[dict[str, str], list[dict[str, object]]]:
    mapping = suggest_mapping(headers, supplied_mapping)
    result = []
    for row_number, row in enumerate(rows, start=1):
        if not any(row) or _is_numbering_row(row):
            continue
        values = {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        measure_value = values.get(mapping.get("measure", ""), "")
        due_column = mapping.get("due_date", "")
        due_value = values.get(due_column, "").strip() if due_column else ""
        due_date = parse_date_value(due_value) if due_value else None
        if due_date is None:
            due_date = extract_due_date(measure_value)
        errors = []
        for field in REQUIRED_FIELDS:
            column = mapping.get(field, "")
            if not column:
                errors.append(f"Не сопоставлена колонка «{field}»")
            elif not values.get(column, "").strip():
                errors.append(f"Не заполнено поле «{column}»")
        if due_date is None:
            if due_column and due_value:
                errors.append(f"Не удалось распознать срок устранения в колонке «{due_column}»")
            elif "срок" in measure_value.casefold():
                errors.append("Не удалось распознать срок устранения в тексте мероприятия")
        result.append({"row_number": row_number, "values": values, "due_date": due_date, "errors": errors})
    return mapping, result
