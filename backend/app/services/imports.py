from datetime import date
from io import BytesIO
from pathlib import Path
import re

from docx import Document
from fastapi import HTTPException, status
from openpyxl import load_workbook


MAX_IMPORT_SIZE = 10 * 1024 * 1024
REQUIRED_FIELDS = ("formulation", "requirement", "measure", "responsible")
DUE_DATE_KEY = "__due_date__"


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
    content_header = next(
        (header for header in headers if any(token in _normalized(header) for token in ("содержание нарушения", "выявленн", "нарушени"))),
        headers[1] if len(headers) > 1 else "",
    )
    measure_header = next(
        (header for header in headers if any(token in _normalized(header) for token in ("мероприят", "устранени"))),
        headers[2] if len(headers) > 2 else "",
    )
    responsible_header = next(
        (header for header in headers if "ответствен" in _normalized(header)),
        headers[3] if len(headers) > 3 else "",
    )
    for field, header in {
        "formulation": content_header,
        "requirement": content_header,
        "measure": measure_header,
        "responsible": responsible_header,
    }.items():
        if not mapping.get(field) and header:
            mapping[field] = header
    return mapping


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
        due_date = extract_due_date(measure_value)
        errors = []
        for field in REQUIRED_FIELDS:
            column = mapping.get(field, "")
            if not column:
                errors.append(f"Не сопоставлена колонка «{field}»")
            elif not values.get(column, "").strip():
                errors.append(f"Не заполнено поле «{column}»")
        if "срок" in measure_value.casefold() and due_date is None:
            errors.append("Не удалось распознать срок устранения в тексте мероприятия")
        result.append({"row_number": row_number, "values": values, "due_date": due_date, "errors": errors})
    return mapping, result
