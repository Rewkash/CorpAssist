# CorpAssist - Intelligent Business Messaging Assistant

Полноценное веб-приложение для помощи в деловой переписке на русском языке.

## Возможности

- **Режим 1: Помощь с ответом** - анализ входящего сообщения и генерация 2-3 вариантов делового ответа.
- **Режим 2: Улучшение текста** - исправление черновика, перевод в деловой стиль, подсветка изменений.
- **Краткий анализ текста** - тональность, ключевые темы, степень формальности.
- **Real-time взаимодействие** - WebSocket между клиентом и сервером.
- **Авторизация** - JWT access token.
- **История запросов** - сохранение операций пользователя в PostgreSQL.
- **Кэш** - Redis для ускорения повторного анализа.

## Технологический стек

- Frontend: React 18, Vite, Tailwind CSS, Zustand
- Backend: FastAPI (Python 3.11), WebSocket, JWT
- NLP/ML: spaCy, Hugging Face Transformers, PyTorch, fallback-генерация
- Data: PostgreSQL, Redis, Alembic migrations
- Infra: Docker, Docker Compose

## Быстрый старт

```bash
docker compose up --build
```

После запуска:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs

## Тестовый пользователь

Скрипт инициализации создает пользователя:

- `email`: `demo@corpassist.local`
- `password`: `DemoPass123!`

## Локальный запуск без Docker

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Миграции БД

Локальная БД:

```powershell
cd backend
.\.venv\Scripts\alembic.exe upgrade head
cd ..
```

Тестовая БД:

```powershell
$env:POSTGRES_DB="corpassist_test"
$env:POSTGRES_HOST="localhost"
$env:POSTGRES_PORT="5432"
$env:POSTGRES_USER="corpassist"
$env:POSTGRES_PASSWORD="corpassist"
cd backend
.\.venv\Scripts\alembic.exe upgrade head
cd ..
& "backend\.venv\Scripts\pytest.exe"
```

Existing dev DB можно помечать как актуальную только после inspection схемы:

```powershell
docker compose exec postgres psql -U corpassist -d corpassist -c "\d users"
docker compose exec postgres psql -U corpassist -d corpassist -c "\d conversations"
docker compose exec postgres psql -U corpassist -d corpassist -c "\d chat_messages"
docker compose exec postgres psql -U corpassist -d corpassist -c "\d message_history"
cd backend
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe stamp 20260610_0001
.\.venv\Scripts\alembic.exe upgrade head
cd ..
```

Не запускайте baseline migration на existing DB, где таблицы уже созданы.
Сначала проверьте схему, затем используйте `stamp 20260610_0001`, после чего
`upgrade head` применит reconcile migration для known legacy drift. Лишние legacy
индексы `ix_*_id` не удаляются автоматически.

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## Примечания по ML

- Используются lightweight-классификаторы из `transformers pipeline`.
- Если генеративный API не настроен, применяется локальный fallback-движок с деловыми шаблонами.
- Для production стоит подключить полноценный LLaMA endpoint или GPT API через переменные окружения.
