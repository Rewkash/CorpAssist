# CorpAssist - Intelligent Business Messaging Assistant

Полноценное веб-приложение для помощи в деловой переписке на русском языке.

## Возможности

- **Режим 1: Помощь с ответом** - анализ входящего сообщения и генерация 2-3 вариантов делового ответа.
- **Режим 2: Улучшение текста** - исправление черновика, перевод в деловой стиль, подсветка изменений.
- **Краткий анализ текста** - тональность, ключевые темы, степень формальности.
- **Real-time взаимодействие** - WebSocket между клиентом и сервером.
- **Авторизация** - JWT access token.
- **История запросов** - сохранение операций пользователя в PostgreSQL.
- **RAG-знания** - pgvector + bge-m3 эмбеддинги; модель работает с базой знаний как со «своими» знаниями.
- **Семантический кэш** - повторные похожие запросы возвращают сохранённые ответы без вызова LLM.

## База знаний (RAG)

Запросы `/assist/reply`, `/assist/improve` и `/chat/conversations/{id}/suggest-tags` получают
автоматически найденные «известные факты» из базы знаний в системный промпт. Источники:

- `chat` — индексируется фоном после каждого сообщения в `send_chat_message` (привязка к клиенту).
- `kb` — кураторская база знаний (`KnowledgeEntry`): регламенты, FAQ, описания продуктов.

### Эндпоинты администрирования базы знаний

- `GET /knowledge` — список (worker/admin).
- `POST /knowledge` — создать запись (`{title, body, tags, scope: 'global'|'client', client_id?}`).
- `PUT /knowledge/{id}` — обновить.
- `DELETE /knowledge/{id}` — удалить (с очисткой чанков).
- `POST /knowledge/search` — отладочный семантический поиск.

### Бэкфилл существующих сообщений

```bash
docker compose exec backend python -m app.backfill_knowledge
```

Скрипт проиндексирует уже накопленные `chat_messages` (по `client_id`) и существующие `KnowledgeEntry`.

## Технологический стек

- Frontend: React 18, Vite, Tailwind CSS, Zustand
- Backend: FastAPI (Python 3.11), WebSocket, JWT
- NLP/ML: spaCy, Hugging Face Transformers, PyTorch, fallback-генерация
- Data: PostgreSQL, Redis
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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

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
