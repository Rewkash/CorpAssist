import json
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decode_access_token
from app.database import get_db
from app.generator import generator_service, get_llm_debug_log
from app.models import User

router = APIRouter()


async def require_admin_token(
    request: Request,
    token: str = Query(default='', alias='token'),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Auth for debug page: accept token via query param or Authorization header."""
    email = None
    auth_header = request.headers.get('authorization', '')
    if auth_header.startswith('Bearer '):
        email = decode_access_token(auth_header[7:])
    elif token:
        email = decode_access_token(token)
    if not email:
        raise HTTPException(status_code=401, detail='Unauthorized')
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or user.role != 'admin':
        raise HTTPException(status_code=403, detail='Admin role required')
    return user


@router.get('/debug/llm', response_class=HTMLResponse, include_in_schema=False)
async def llm_debug_page(admin: User = Depends(require_admin_token)) -> str:
    current_model = generator_service.model
    model_error = ''
    try:
        available_models = await generator_service.list_models()
    except Exception as exc:
        available_models = [current_model]
        model_error = f'Не удалось получить список моделей из Ollama: {exc!r}'
    if current_model not in available_models:
        available_models.insert(0, current_model)
    model_options = ''.join(
        f'<option value="{escape(model)}"{" selected" if model == current_model else ""}>{escape(model)}</option>'
        for model in available_models
    )
    items = get_llm_debug_log()
    cards = []
    for index, item in enumerate(items, start=1):
        error = item.get('error') or ''
        status = 'error' if error else 'ok'
        schema = item.get('schema')
        schema_block = ''
        if schema:
            schema_block = f'<h3>JSON schema</h3><pre>{escape(json.dumps(schema, ensure_ascii=False, indent=2))}</pre>'
        cards.append(
            f'''
            <section class="card {status}">
              <div class="meta">
                <strong>#{index} {escape(str(item.get('mode', '')))}</strong>
                <span>{escape(str(item.get('created_at', '')))}</span>
                <span>model: {escape(str(item.get('model', '')))}</span>
                <span>temp: {escape(str(item.get('temperature', '')))}</span>
                <span>tokens: {escape(str(item.get('max_tokens', '')))}</span>
              </div>
              {'<p class="error">' + escape(error) + '</p>' if error else ''}
              <h3>System prompt</h3>
              <pre>{escape(str(item.get('system_prompt', '')))}</pre>
              <h3>User prompt</h3>
              <pre>{escape(str(item.get('user_prompt', '')))}</pre>
              {schema_block}
              <h3>LLM response</h3>
              <pre>{escape(str(item.get('response', '')))}</pre>
            </section>
            '''
        )

    body = '\n'.join(cards) or '<p class="empty">Пока нет вызовов нейронки. Выполни подсказку ответа, улучшение текста или теги.</p>'
    return f'''
    <!doctype html>
    <html lang="ru">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>LLM Debug</title>
      <style>
        body {{ margin: 0; padding: 24px; background: #0f172a; color: #e5e7eb; font-family: Arial, sans-serif; }}
        header {{ display: flex; justify-content: space-between; gap: 16px; align-items: baseline; margin-bottom: 18px; }}
        h1 {{ margin: 0; font-size: 24px; }}
        a {{ color: #93c5fd; }}
        form {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
        select {{ min-width: 260px; border: 1px solid #475569; border-radius: 8px; background: #020617; color: #e5e7eb; padding: 9px 10px; }}
        button {{ border: 0; border-radius: 8px; background: #2563eb; color: white; padding: 9px 12px; cursor: pointer; }}
        .hint {{ color: #94a3b8; font-size: 14px; }}
        .card {{ background: #111827; border: 1px solid #334155; border-radius: 14px; padding: 18px; margin: 0 0 16px; }}
        .card.error {{ border-color: #ef4444; }}
        .meta {{ display: flex; flex-wrap: wrap; gap: 10px; color: #cbd5e1; margin-bottom: 14px; }}
        .meta strong {{ color: #f8fafc; }}
        h3 {{ margin: 16px 0 8px; font-size: 14px; color: #bfdbfe; }}
        pre {{ white-space: pre-wrap; word-break: break-word; background: #020617; border-radius: 10px; padding: 12px; line-height: 1.45; color: #e2e8f0; }}
        .error {{ color: #fecaca; background: #7f1d1d; padding: 10px; border-radius: 8px; }}
        .empty {{ color: #cbd5e1; }}
      </style>
    </head>
    <body>
      <header>
        <div>
          <h1>LLM Debug</h1>
          <div class="hint">Публичная страница без авторизации. Хранятся последние 100 вызовов в памяти backend.</div>
          <form id="model-form">
            <select id="model-select" name="model">{model_options}</select>
            <button id="model-submit" type="submit">Сменить модель</button>
            <button id="model-unload" type="button">Выгрузить</button>
            <button id="model-stop" type="button">Остановить загрузку</button>
          </form>
          <div id="model-status" class="hint">Текущая модель: {escape(current_model)}</div>
          {'<div class="error">' + escape(model_error) + '</div>' if model_error else ''}
        </div>
        <a id="refresh-link" href="/debug/llm">обновить</a>
      </header>
      {body}
      <script>
        const form = document.getElementById('model-form');
        const select = document.getElementById('model-select');
        const button = document.getElementById('model-submit');
        const unloadButton = document.getElementById('model-unload');
        const stopButton = document.getElementById('model-stop');
        const statusEl = document.getElementById('model-status');
        const qsToken = new URLSearchParams(location.search).get('token');
        if (qsToken) document.getElementById('refresh-link').href = '/debug/llm?token=' + encodeURIComponent(qsToken);
        const authHeaders = qsToken ? {{ 'Authorization': 'Bearer ' + qsToken, 'Content-Type': 'application/json' }} : {{ 'Content-Type': 'application/json' }};

        function setControlsDisabled(disabled) {{
          button.disabled = disabled;
          unloadButton.disabled = disabled;
          stopButton.disabled = disabled;
          select.disabled = disabled;
        }}

        form.addEventListener('submit', async (event) => {{
          event.preventDefault();
          const selectedModel = select.value;
          setControlsDisabled(true);
          button.textContent = 'Модель загружается...';
          statusEl.textContent = `Выгружается старая модель и загружается ${{selectedModel}}...`;
          const response = await fetch('/debug/llm/model', {{
            method: 'POST',
            headers: authHeaders,
            body: JSON.stringify({{ model: selectedModel }})
          }});
          const data = await response.json();
          if (!response.ok) {{
            statusEl.textContent = data.status || 'Ошибка смены модели';
            setControlsDisabled(false);
            button.textContent = 'Сменить модель';
            return;
          }}
          statusEl.textContent = data.status || `Текущая модель: ${{data.model}}`;
          if (data.model) select.value = data.model;
          setControlsDisabled(false);
          button.textContent = 'Сменить модель';
        }});

        unloadButton.addEventListener('click', async () => {{
          setControlsDisabled(true);
          statusEl.textContent = `Выгружается модель ${{select.value}}...`;
          const response = await fetch('/debug/llm/unload', {{ method: 'POST', headers: authHeaders }});
          const data = await response.json();
          statusEl.textContent = data.status || 'Модель выгружена';
          setControlsDisabled(false);
          button.textContent = 'Сменить модель';
        }});

        stopButton.addEventListener('click', async () => {{
          setControlsDisabled(true);
          statusEl.textContent = 'Останавливается загрузка и очищается выбранная модель...';
          const response = await fetch('/debug/llm/stop-loading', {{ method: 'POST', headers: authHeaders }});
          const data = await response.json();
          statusEl.textContent = data.status || 'Загрузка остановлена';
          setControlsDisabled(false);
          button.textContent = 'Сменить модель';
        }});
      </script>
    </body>
    </html>
    '''


@router.post('/debug/llm/model', include_in_schema=False)
async def set_llm_debug_model(payload: dict[str, str], _: User = Depends(require_admin_token)) -> JSONResponse:
    model = (payload.get('model') or '').strip()
    if not model:
        return JSONResponse({'ok': False, 'status': 'Модель не указана'}, status_code=400)
    if generator_service.model_loading:
        return JSONResponse({'ok': False, 'status': generator_service.model_status}, status_code=409)
    if model == generator_service.model:
        return JSONResponse({'ok': True, 'model': generator_service.model, 'status': generator_service.model_status})

    try:
        await generator_service.switch_model(model)
    except Exception as exc:
        return JSONResponse({'ok': False, 'status': f'Не удалось загрузить модель {model}: {exc!r}'}, status_code=500)
    return JSONResponse({'ok': True, 'model': generator_service.model, 'status': generator_service.model_status})


@router.post('/debug/llm/unload', include_in_schema=False)
async def unload_llm_debug_model(_: User = Depends(require_admin_token)) -> JSONResponse:
    if generator_service.model_loading:
        return JSONResponse({'ok': False, 'status': generator_service.model_status}, status_code=409)
    try:
        await generator_service.unload_current_model()
    except Exception as exc:
        return JSONResponse({'ok': False, 'status': f'Не удалось выгрузить модель: {exc!r}'}, status_code=500)
    return JSONResponse({'ok': True, 'model': generator_service.model, 'status': generator_service.model_status})


@router.post('/debug/llm/stop-loading', include_in_schema=False)
async def stop_llm_loading(_: User = Depends(require_admin_token)) -> JSONResponse:
    try:
        await generator_service.cancel_loading_and_clear()
    except Exception as exc:
        return JSONResponse({'ok': False, 'status': f'Не удалось остановить загрузку: {exc!r}'}, status_code=500)
    return JSONResponse({'ok': True, 'model': generator_service.model, 'status': generator_service.model_status})
