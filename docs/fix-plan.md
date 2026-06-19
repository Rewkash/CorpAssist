# План исправлений CorpAssist

## Этап 1 — Обязательно перед production (блокирующие проблемы) ✅

- [x] 1.1 assist_ws: db-сессия используется после закрытия `async with`
- [x] 1.2 JWT-секрет: убрать дефолт, добавить startup-проверку
- [x] 1.3 IDOR в assist: добавить проверку доступа к conversation
- [x] 1.4 CORS: указать конкретные origins
- [x] 1.5 Rate limiting на `/auth/login`

## Этап 2 — Желательно исправить (важные улучшения) ✅

- [x] 2.1 N+1 в `build_conversation_items`
- [x] 2.2 `push_conversations_snapshot` — множитель N+1
- [x] 2.3 Assist context duplication (DRY)
- [x] 2.4 Теги: инкапсулировать parse/serialize
- [x] 2.5 Debug-endpoints: авторизация при включении

## Этап 3 — Архитектурный рефакторинг ✅

- [x] 3.1 Alembic-миграции — уже были настроены
- [x] 3.2 NlpService lazy init — тяжёлые модели загружаются при первом вызове
- [x] 3.3 `text()` → ORM `update()` — заменены 4 raw SQL на SQLAlchemy ORM
- [x] 3.4 `generate`/`generate_structured` объединены в один метод с `schema=None`
- [x] 3.5 `useChat.ts` cleanup — извлечена `connectWithReconnect()` + `cleanupSocket()`
- [x] 3.6 Role enum — `StrEnum` в `models.py`, обратная совместимость со строками
- [x] 3.7 Пагинация — `offset`/`limit` для `/history` и `/chat/messages`
- [x] 3.8 NlpService lazy init — то же что 3.2

---

## Сводка изменений по файлам

| Файл | Изменения |
|------|-----------|
| `backend/app/main.py` | lifespan check_jwt_secret, CORS origin, slowapi limiter, assist_ws db fix, build_assist_context, import cleanup |
| `backend/app/config.py` | +check_jwt_secret(), +cors_origin field |
| `backend/app/models.py` | +Role StrEnum, +get_tags()/set_tags() на Conversation |
| `backend/app/nlp.py` | Lazy init spacy + transformers при первом вызове |
| `backend/app/routes/auth.py` | +limiter 5/minute на login/register, +Request param |
| `backend/app/routes/assist.py` | build_assist_context(), пагинация history (offset/limit) |
| `backend/app/routes/chat.py` | conversation.set_tags(), ORM update(), пагинация messages |
| `backend/app/routes/debug_llm.py` | +require_admin_token, auth headers в JS |
| `backend/app/services/assist_context.py` | +build_assist_context() с IDOR защитой |
| `backend/app/services/conversation_presenter.py` | Агрегирующий SQL (LATERAL), row.get_tags() |
| `backend/app/services/conversation_tags.py` | set_tags(), ORM func.now() |
| `backend/app/realtime/conversation_snapshots.py` | Batch fetch пользователей |
| `backend/app/llm/ollama_client.py` | generate_structured → generate(schema=...) |
| `backend/app/generator.py` | Вызов generate() вместо generate_structured() |
| `frontend/src/useChat.ts` | Извлечена connectWithReconnect(), cleanupSocket() |
| `backend/requirements.txt` | +slowapi==0.1.9 |
| `docker-compose.yml` | JWT_SECRET через env, +CORS_ORIGIN |
| `backend/.env.example` | Новый файл |

## Прогресс

Все этапы (1, 2, 3) завершены.
