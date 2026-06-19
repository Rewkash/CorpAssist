from collections import deque
from datetime import datetime, timezone
from typing import Any

import httpx

LLM_DEBUG_LOG: deque[dict[str, Any]] = deque(maxlen=100)


def get_llm_debug_log() -> list[dict[str, Any]]:
    return list(reversed(LLM_DEBUG_LOG))


class OllamaClient:
    """Обертка для вызовов Ollama REST API."""

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip('/')
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def set_model(self, model: str) -> None:
        self._model = model

    async def unload_model(self, model: str) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f'{self._base_url}/api/generate',
                json={'model': model, 'prompt': '', 'stream': False, 'keep_alive': 0},
            )
            response.raise_for_status()

    async def preload_model(self, model: str) -> None:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f'{self._base_url}/api/generate',
                json={
                    'model': model,
                    'prompt': '',
                    'stream': False,
                    'keep_alive': '30m',
                    'options': {'num_predict': 1, 'num_ctx': 8192},
                },
            )
            response.raise_for_status()

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f'{self._base_url}/api/tags')
            response.raise_for_status()
            data = response.json()
            return [str(item.get('name', '')).strip() for item in data.get('models', []) if item.get('name')]

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        mode: str = 'generate',
        schema: dict[str, Any] | None = None,
    ) -> str:
        debug_item: dict[str, Any] = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'mode': mode,
            'model': self._model,
            'endpoint': '/api/chat',
            'temperature': temperature,
            'max_tokens': max_tokens,
            'system_prompt': system_prompt,
            'user_prompt': user_prompt,
            'response': '',
            'error': '',
        }
        if schema:
            debug_item['schema'] = schema
        payload: dict[str, Any] = {
            'model': self._model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'raw': False,
            'stream': False,
            'options': {
                'temperature': temperature,
                'top_p': 0.9,
                'num_predict': max_tokens,
                'num_ctx': 8192,
            },
        }
        if schema:
            payload['format'] = schema
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(f'{self._base_url}/api/chat', json=payload)
                response.raise_for_status()
                result = response.json()['message']['content'].strip()
                debug_item['response'] = result
                return result
            except Exception as exc:
                debug_item['error'] = repr(exc)
                raise
            finally:
                LLM_DEBUG_LOG.append(debug_item)
