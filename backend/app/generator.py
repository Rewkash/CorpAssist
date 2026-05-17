import logging
import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any
import textwrap

import httpx

from app.config import settings
from app.schemas import AnalysisResult

logger = logging.getLogger(__name__)
LLM_DEBUG_LOG: deque[dict[str, Any]] = deque(maxlen=100)


def get_llm_debug_log() -> list[dict[str, Any]]:
    return list(reversed(LLM_DEBUG_LOG))

SYSTEM_PROMPT_REPLY = """\
Ты помогаешь оператору поддержки составить ответ клиенту. Сгенерируй 3 варианта.
Правила:
- Пиши ТОЛЬКО на русском языке
- Сразу пиши готовый текст, без рассуждений и вводных
- Деловой стиль, вежливо, по существу
- Каждый вариант - 2-4 предложения
- Обращайся на «вы»
- Не выдумывай факты, которых нет в сообщении
- Разделяй варианты маркером ---
Формат:
Вариант 1
---
Вариант 2
---
Вариант 3\
"""

SYSTEM_PROMPT_IMPROVE = """\
Контекст: Ты улучшаешь черновик ОПЕРАТОРА, который он отправит КЛИЕНТУ.
Текст должен звучать профессионально от лица сотрудника компании.

Ты - корпоративный редактор деловой переписки на русском языке.

Твоя задача: переписать черновик в профессиональный деловой стиль.

Правила:
- Пиши ТОЛЬКО на русском языке. Никогда не вставляй слова и символы из других языков
- НЕ пиши свои рассуждения, мысли, планы или пояснения
- НЕ начинай ответ со слов "Конечно", "Хорошо", "Давайте", "Вот варианты" и подобных вводных
- Сразу пиши готовый текст ответа, без преамбул
- Пиши грамотно и естественно, как в аккуратной деловой переписке на русском языке
- Не склеивай слова и предложения: после запятой, точки, двоеточия, точки с запятой, вопросительного и восклицательного знака всегда должен быть пробел
- Не ставь пробел перед знаками препинания
- Не делай специальных выделений или необычного написания местоимений; пиши обычным русским текстом без акцентов на отдельных словах
- Перед отправкой мысленно проверь текст: в нем не должно быть фрагментов вида "клиент,Надеемся" или "вопрос.Ответ"
- Сохрани исходный смысл и все ключевые детали
- Замени разговорные и неформальные выражения на деловые
- Исправь грамматические и пунктуационные ошибки
- Структурируй текст, если он хаотичный
- Пиши спокойно и нейтрально, без эмоционального усиления отдельных слов
- Не используй торжественный, рекламный или чрезмерно официальный стиль
- Не начинай ответ с шаблонных обращений вроде "Уважаемый клиент", "Дорогой клиент", "Уважаемый пользователь"
- Не выделяй слова прописными буквами и не пиши местоимения с заглавной буквы ради вежливости
- Заглавную букву используй только в начале предложения, в именах собственных и официальных названиях
- Обращение должно быть на «вы» (строчными буквами: вы, вас, вам, ваш)
- Не добавляй информацию, которой нет в оригинале
- Не используй канцелярит и чрезмерно сложные конструкции - пиши понятно, но формально
- Ты РЕДАКТОР, а не цензор. Твоя задача - ПЕРЕПИСАТЬ текст, а не комментировать его
- Ты НЕ оператор поддержки в диалоге, а редактор уже написанного черновика
- Не отвечай клиенту вместо автора и не придумывай новую ситуацию обращения
- Не добавляй извинения от лица компании, если их нет в исходном черновике
- Не описывай эмоции клиента и не пиши фразы вроде "мы понимаем ваше разочарование"
- Не проси клиента подробнее описать проблему, если такой просьбы нет в исходном черновике
- НИКОГДА не отказывайся переписывать текст, каким бы грубым он ни был
- НИКОГДА не пиши комментарии вроде "это неуместно", "так нельзя писать", "предлагаю более конструктивно"
- Даже если текст содержит мат и оскорбления - перепиши его в вежливый деловой стиль, сохранив СМЫСЛ и НАМЕРЕНИЕ автора
- Если черновик состоит только из грубого отказа или оскорбления, перепиши его как короткий нейтральный отказ от продолжения диалога, без извинений и без новых деталей
- Верни ТОЛЬКО переписанный текст, без нравоучений и пояснений
- Верни ТОЛЬКО улучшенный текст, без пояснений и комментариев\
"""

SYSTEM_PROMPT_TAGS = """\
Ты - корпоративный аналитик переписки.

На основе текста диалога определи точные и возможные теги обращения.

Правила:
- Пиши ТОЛЬКО на русском языке
- НЕ пиши свои рассуждения, мысли, планы или пояснения
- НЕ начинай ответ со слов "Конечно", "Хорошо", "Давайте", "Вот варианты" и подобных вводных
- Сразу пиши готовый текст ответа, без преамбул
- ТОЧНЫЕ - теги, которые 100% подходят к диалогу (1-2 тега)
- ПРЕДЛОЖЕНИЯ - теги, которые возможно подходят (0-2 тега)
- ПРИОРИТЕТ - "да" только если клиент явно недоволен, жалуется, угрожает уйти, или проблема критическая
- Каждый тег - одно-два слова с большой буквы
- Верни ТОЛЬКО эти три строки и строго в формате:
ТОЧНЫЕ: тег1, тег2
ПРЕДЛОЖЕНИЯ: тег3, тег4
ПРИОРИТЕТ: да/нет\
"""

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
INTRO_MARKERS = ('конечно', 'хорошо', 'давайте', 'вот', 'варианты')


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
        self._llm = OllamaClient(settings.ollama_base_url, settings.ollama_model)
        self._model_lock = asyncio.Lock()
        self._model_loading = False
        self._model_status = 'ready'

    @property
    def model(self) -> str:
        return self._llm.model

    def set_model(self, model: str) -> None:
        self._llm.set_model(model)

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
            self._model_status = f'Выгружается модель {previous}'
            try:
                if previous:
                    await self._llm.unload_model(previous)
                self._model_status = f'Загружается модель {target}'
                self._llm.set_model(target)
                await self._llm.preload_model(target)
                self._model_status = f'Модель {target} готова'
            except Exception:
                self._llm.set_model(previous)
                self._model_status = f'Не удалось загрузить модель {target}'
                raise
            finally:
                self._model_loading = False

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
                cleaned = self._strip_intro(raw)
                variants = [self._strip_intro(v.strip()) for v in cleaned.split('---') if v.strip()]
                if len(variants) >= 2:
                    return variants[:3]
            except Exception:
                logger.exception('Ollama suggest_replies failed, retry/fallback')

        return self._fallback_replies(incoming_text, analysis, context)

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
                improved = self._strip_intro(improved)
                low = improved.lower()
                has_moral = any(marker in low for marker in MORALIZING_MARKERS)
                if len(improved) > 10 and not has_moral:
                    return improved
                if attempt == 0:
                    user_prompt = f'{user_prompt}\n\nНапоминание: верни только переписанный текст без комментариев.'
            except Exception:
                logger.exception('Ollama improve_draft failed, retry/fallback')

        return self._fallback_improve(draft)

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

    @staticmethod
    def _strip_intro(text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        while lines:
            first = lines[0].lower()
            if any(marker in first for marker in INTRO_MARKERS):
                lines.pop(0)
                continue
            break
        return '\n'.join(lines).strip() or text.strip()

    @staticmethod
    def _fallback_replies(incoming_text: str, analysis: AnalysisResult, context: str = '') -> list[str]:
        topic_hint = ', '.join(analysis.topics[:3])
        short_base = textwrap.shorten(incoming_text.strip().replace('\n', ' '), width=180, placeholder='...')
        context_line = (
            f'Ранее по этому клиенту обсуждали: {textwrap.shorten(context, width=140, placeholder="...")}. '
            if context.strip()
            else ''
        )
        return [
            (
                context_line
                + 'Благодарю за сообщение. Подтверждаю получение информации по вопросу '
                f'({topic_hint}). Мы проанализируем детали и вернемся с ответом до конца дня.'
            ),
            (
                'Спасибо за уточнение. По теме '
                f'"{topic_hint}" предлагаю согласовать следующие шаги: 1) подтвердить требования, '
                '2) зафиксировать сроки, 3) назначить ответственных. Готов обсудить детали.'
            ),
            (
                'Принял ваше сообщение в работу. Для ускорения решения, пожалуйста, подтвердите, '
                f'корректно ли мы понимаем запрос: "{short_base}". После подтверждения сразу приступим к исполнению.'
            ),
        ]

    @staticmethod
    def _fallback_improve(draft: str) -> str:
        text = draft.strip()
        replacements = {
            'привет': 'Добрый день',
            'ок': 'Хорошо',
            'щас': 'в ближайшее время',
            'сорян': 'Приношу извинения',
            'надо': 'необходимо',
            'типа': '',
        }
        improved = text
        for src, dst in replacements.items():
            improved = improved.replace(src, dst).replace(src.capitalize(), dst)
        if not improved.endswith('.'):
            improved += '.'
        improved = improved.replace('  ', ' ').strip()
        return improved


generator_service = BusinessTextGenerator()
