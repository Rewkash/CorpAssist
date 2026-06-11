import logging
import asyncio
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import textwrap

import httpx

from app.config import settings
from app.llm.fallbacks import fallback_improve, fallback_replies
from app.parsers.llm_responses import parse_reply_variants, strip_intro
from app.prompts.llm_prompts import (
    SYSTEM_PROMPT_IMPROVE,
    SYSTEM_PROMPT_REPLY,
    SYSTEM_PROMPT_TAGS,
)
from app.schemas import AnalysisResult

logger = logging.getLogger(__name__)
LLM_DEBUG_LOG: deque[dict[str, Any]] = deque(maxlen=100)
RUNTIME_MODEL_FILE = Path(__file__).resolve().parents[1] / '.runtime_ollama_model'


def get_llm_debug_log() -> list[dict[str, Any]]:
    return list(reversed(LLM_DEBUG_LOG))

MORALIZING_MARKERS = (
    'не вправе',
    'неуместно',
    'конструктивно',
    'нельзя писать',
    'пожалуйста, попробуйте',
    'приносим свои извинения за ненормативную лексику',
    'мы понимаем, что вы испытываете',
    'опишите вашу проблему более подробно',
)


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
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f'{self._base_url}/api/chat',
                    json={
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
                    },
                )
                response.raise_for_status()
                result = response.json()['message']['content'].strip()
                debug_item['response'] = result
                return result
            except Exception as exc:
                debug_item['error'] = repr(exc)
                raise
            finally:
                LLM_DEBUG_LOG.append(debug_item)

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 200,
        mode: str = 'structured',
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
            'schema': schema,
            'response': '',
            'error': '',
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f'{self._base_url}/api/chat',
                    json={
                        'model': self._model,
                        'messages': [
                            {'role': 'system', 'content': system_prompt},
                            {'role': 'user', 'content': user_prompt},
                        ],
                        'raw': False,
                        'stream': False,
                        'format': schema,
                        'options': {
                            'temperature': temperature,
                            'top_p': 0.9,
                            'num_predict': max_tokens,
                            'num_ctx': 8192,
                        },
                    },
                )
                response.raise_for_status()
                result = response.json()['message']['content'].strip()
                debug_item['response'] = result
                return result
            except Exception as exc:
                debug_item['error'] = repr(exc)
                raise
            finally:
                LLM_DEBUG_LOG.append(debug_item)


class BusinessTextGenerator:
    def __init__(self) -> None:
        self._llm = OllamaClient(settings.ollama_base_url, self._load_saved_model())
        self._model_lock = asyncio.Lock()
        self._model_loading = False
        self._model_status = 'ready'
        self._model_switch_task: asyncio.Task[Any] | None = None

    @staticmethod
    def _load_saved_model() -> str:
        try:
            saved_model = RUNTIME_MODEL_FILE.read_text(encoding='utf-8').strip()
            return saved_model or settings.ollama_model
        except OSError:
            return settings.ollama_model

    @staticmethod
    def _save_model(model: str) -> None:
        RUNTIME_MODEL_FILE.write_text(model.strip(), encoding='utf-8')

    @staticmethod
    def _clear_saved_model() -> None:
        try:
            RUNTIME_MODEL_FILE.unlink()
        except OSError:
            pass

    @property
    def model(self) -> str:
        return self._llm.model

    def set_model(self, model: str) -> None:
        self._llm.set_model(model)

    async def unload_current_model(self) -> None:
        async with self._model_lock:
            current = self.model
            if not current:
                return
            self._model_loading = True
            self._model_status = f'Выгружается модель {current}'
            try:
                await self._llm.unload_model(current)
                self._model_status = f'Модель {current} выгружена'
            finally:
                self._model_loading = False

    @property
    def model_loading(self) -> bool:
        return self._model_loading

    @property
    def model_status(self) -> str:
        return self._model_status

    def ensure_ready(self) -> None:
        if self._model_loading:
            raise RuntimeError(self._model_status)

    async def switch_model(self, model: str) -> None:
        async with self._model_lock:
            target = model.strip()
            if not target:
                return
            if target == self.model and not self._model_loading:
                return

            previous = self.model
            self._model_loading = True
            self._model_switch_task = asyncio.current_task()
            self._model_status = f'Выгружается модель {previous}'
            try:
                if previous:
                    await self._llm.unload_model(previous)
                self._model_status = f'Загружается модель {target}'
                self._llm.set_model(target)
                await self._llm.preload_model(target)
                self._save_model(target)
                self._model_status = f'Модель {target} готова'
            except asyncio.CancelledError:
                self._model_status = f'Загрузка модели {target} остановлена'
                raise
            except Exception:
                self._llm.set_model(previous)
                self._model_status = f'Не удалось загрузить модель {target}'
                raise
            finally:
                self._model_loading = False
                self._model_switch_task = None

    async def cancel_loading_and_clear(self) -> None:
        current_task = self._model_switch_task
        if self._model_loading and current_task and not current_task.done():
            self._model_status = 'Останавливается загрузка модели...'
            current_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(current_task), timeout=5.0)
            except (asyncio.CancelledError, TimeoutError):
                pass
            except Exception:
                pass

        async with self._model_lock:
            self._model_loading = False
            current = self.model
            if current:
                try:
                    await self._llm.unload_model(current)
                except Exception:
                    logger.exception('Failed to unload current model during cancel')
            self._clear_saved_model()
            self._model_status = 'Загрузка остановлена, модель выгружена, выбор очищен'

    async def list_models(self) -> list[str]:
        return await self._llm.list_models()

    async def suggest_replies(self, incoming_text: str, analysis: AnalysisResult, context: str = '') -> list[str]:
        context_block = ''
        if context.strip():
            short_context = textwrap.shorten(context, width=300, placeholder='...')
            context_block = f'Контекст предыдущего общения:\n{short_context}\n\n'

        user_prompt = f'{context_block}Последнее сообщение клиента:\n{incoming_text.strip()}'

        for _ in range(2):
            try:
                raw = await self._llm.generate(
                    system_prompt=SYSTEM_PROMPT_REPLY,
                    user_prompt=user_prompt,
                    temperature=0.7,
                    max_tokens=600,
                    mode='suggest_replies',
                )
                cleaned = strip_intro(raw)
                variants = parse_reply_variants(cleaned)
                if len(variants) >= 2:
                    return variants[:3]
            except Exception:
                logger.exception('Ollama suggest_replies failed, retry/fallback')

        return fallback_replies(incoming_text, analysis, context)

    async def improve_draft(self, draft: str, analysis: AnalysisResult, context: str = '') -> str:
        context_block = ''
        if context.strip():
            short_context = textwrap.shorten(context, width=3000, placeholder='...')
            context_block = f'Контекст диалога только для понимания темы. Не переписывай его и не отвечай на него:\n{short_context}\n\n'

        user_prompt = f'{context_block}Черновик оператора для улучшения:\n\n{draft.strip()}'

        for attempt in range(2):
            try:
                improved = await self._llm.generate(
                    system_prompt=SYSTEM_PROMPT_IMPROVE,
                    user_prompt=user_prompt,
                    temperature=0.3,
                    max_tokens=512,
                    mode='improve_draft',
                )
                improved = strip_intro(improved)
                low = improved.lower()
                has_moral = any(marker in low for marker in MORALIZING_MARKERS)
                if len(improved) > 10 and not has_moral:
                    return improved
                if attempt == 0:
                    user_prompt = f'{user_prompt}\n\nНапоминание: верни только переписанный текст без комментариев.'
            except Exception:
                logger.exception('Ollama improve_draft failed, retry/fallback')

        return fallback_improve(draft)

    async def suggest_tags(self, conversation_text: str) -> dict[str, Any]:
        user_prompt = f'Текст диалога:\n\n{conversation_text[:4000]}'
        schema = {
            'type': 'object',
            'properties': {
                'auto_tags': {'type': 'array', 'items': {'type': 'string'}},
                'suggested_tags': {'type': 'array', 'items': {'type': 'string'}},
                'priority': {'type': 'boolean'},
            },
            'required': ['auto_tags', 'suggested_tags', 'priority'],
        }

        for _ in range(2):
            try:
                raw = await self._llm.generate_structured(
                    system_prompt=SYSTEM_PROMPT_TAGS,
                    user_prompt=user_prompt,
                    schema=schema,
                    temperature=0.1,
                    max_tokens=200,
                    mode='suggest_tags',
                )
                import json

                parsed = json.loads(raw)
                auto_tags = [str(tag).strip().capitalize() for tag in parsed.get('auto_tags', []) if str(tag).strip()][:2]
                suggested_tags = [str(tag).strip().capitalize() for tag in parsed.get('suggested_tags', []) if str(tag).strip()][:2]
                priority = bool(parsed.get('priority', False))
                return {
                    'auto_tags': auto_tags,
                    'suggested_tags': suggested_tags,
                    'priority': priority,
                }
            except Exception:
                logger.exception('Ollama suggest_tags failed, retry/fallback')

        return {'auto_tags': [], 'suggested_tags': [], 'priority': False}

generator_service = BusinessTextGenerator()
