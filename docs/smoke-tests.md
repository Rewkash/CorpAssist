# Runtime Smoke Tests

Use this checklist after backend refactors, dependency changes, or local infrastructure changes.

## Prerequisites

- PostgreSQL, Redis, and Ollama are running or intentionally unavailable for degraded checks.
- Database migrations were applied with `alembic upgrade head`.
- Backend is started with local environment values.
- Frontend is started and points to the backend.

## Backend startup

- [ ] Run `cd backend` and `.\.venv\Scripts\alembic.exe upgrade head`.
- [ ] Start backend without import errors.
- [ ] Confirm startup finishes without schema mutation errors.
- [ ] Confirm no unexpected traceback appears in logs.

## Existing database inspection before stamping

Run these before `alembic stamp head` on an existing dev DB:

```powershell
docker compose exec postgres psql -U corpassist -d corpassist -c "\d users"
docker compose exec postgres psql -U corpassist -d corpassist -c "\d conversations"
docker compose exec postgres psql -U corpassist -d corpassist -c "\d chat_messages"
docker compose exec postgres psql -U corpassist -d corpassist -c "\d message_history"
```

Stamp only if the schema matches the Alembic baseline:

```powershell
cd backend
.\.venv\Scripts\alembic.exe stamp 20260610_0001
.\.venv\Scripts\alembic.exe upgrade head
cd ..
```

Do not run the baseline upgrade against an existing DB that already has these
tables. `20260610_0002` reconciles known legacy dev schema drift after the DB is
stamped at `20260610_0001`. Legacy extra `ix_*_id` indexes are intentionally left
in place.

## Health

- [ ] `GET /health` returns HTTP `200`.
- [ ] Response contains `status: "ok"`.
- [ ] `ollama` is either `connected` or `unavailable` depending on local Ollama state.

## Auth

- [ ] Register a new client with `POST /auth/register`.
- [ ] Login with `POST /auth/login`.
- [ ] Call `GET /auth/me` with the bearer token.
- [ ] Confirm email and role match the registered user.

## Chat REST flow

- [ ] Start a conversation with `POST /chat/conversations/start` as a client.
- [ ] List conversations with `GET /chat/conversations`.
- [ ] Register/login a worker or admin.
- [ ] Take the conversation with `POST /chat/conversations/{conversation_id}/take`.
- [ ] Send a message with `POST /chat/messages`.
- [ ] Get messages with `GET /chat/messages/{conversation_id}`.
- [ ] Mark messages read with `POST /chat/messages/read`.
- [ ] Close the conversation with `POST /chat/conversations/{conversation_id}/close`.

## Tags

- [ ] Suggest tags with `GET /chat/conversations/{conversation_id}/suggest-tags` as worker/admin.
- [ ] Confirm response contains a `tags` array.

## WebSocket chat

- [ ] Connect to `/ws/chat/{conversation_id}?token=...`.
- [ ] Confirm initial `connected` event.
- [ ] Send a chat message through REST.
- [ ] Confirm websocket receives `message_created`.

## WebSocket updates

- [ ] Connect to `/ws/chat-updates?token=...`.
- [ ] Confirm initial `connected` event.
- [ ] Trigger conversation changes through REST.
- [ ] Confirm updates are delivered.

## REST assist

- [ ] Call REST assist reply endpoint with valid auth and text.
- [ ] Call REST assist improve endpoint with valid auth and text.
- [ ] Confirm model-loading state errors are readable if LLM is unavailable/loading.

## WebSocket assist

- [ ] Connect to `/ws/assist?token=...`.
- [ ] Send `reply` mode payload with text.
- [ ] Confirm analysis/generation events or clear model-state errors.
- [ ] Send `improve` mode payload with text.
- [ ] Confirm improved response or clear model-state errors.

## Debug LLM

- [ ] Set `ENABLE_LLM_DEBUG=true` before backend startup in local/dev only.
- [ ] Open `GET /debug/llm`.
- [ ] Confirm page renders.
- [ ] Check model status.
- [ ] If safe locally, test model load/unload controls.
