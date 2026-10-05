# PK CONTROL

Внутренняя система учёта и анализа нарушений производственного контроля для ООО «Газпром переработка Благовещенск».

## Структура

- `docs/` — архитектурные решения, модель данных и план разработки.
- `backend/` — API FastAPI, SQLAlchemy и миграции Alembic.
- `frontend/` — веб-интерфейс React + TypeScript + Vite.

## Требования для локальной разработки

- Python 3.11 или новее;
- Node.js 20.19+ или 22.12+;
- npm 10+.

## Быстрый запуск

### Backend

```bash
cd backend
python -m venv .venv
# Git Bash
source .venv/Scripts/activate
# PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy ..\.env.example .env  # Windows CMD; в Git Bash: cp ../.env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Проверка: `http://127.0.0.1:8000/api/v1/health`, документация API: `http://127.0.0.1:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Интерфейс будет доступен по адресу `http://127.0.0.1:5173`; запросы `/api` проксируются на backend.

## Важные ограничения

SQLite размещается только на диске сервера, не на SMB-сетевой папке. В сетевых каталогах хранятся только документы и резервные копии. Подробности — в [архитектуре](docs/ARCHITECTURE.md).

Исходные требования и принятые решения: [SOURCE_DOCUMENTS.md](docs/SOURCE_DOCUMENTS.md) и [DECISIONS.md](docs/DECISIONS.md).
