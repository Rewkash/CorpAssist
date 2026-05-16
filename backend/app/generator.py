import logging
from typing import Any
import textwrap

import httpx

from app.config import settings
from app.schemas import AnalysisResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_REPLY = """\
Контекст: Ты помогаешь ОПЕРАТОРУ службы поддержки составить ответ КЛИЕНТУ.
Оператор - сотрудник компании. Клиент - обратившийся за помощью.
Пиши ответ ОТ ЛИЦА ОПЕРАТОРА для клиента.

Ты - корпоративный ассистент для деловой переписки на русском языке.

Твоя задача: на основе входящего сообщения сгенерировать ровно 3 варианта делового ответа.

Правила:
- Пиши ТОЛЬКО на русском языке. Никогда не вставляй слова и символы из других языков
- НЕ пиши свои рассуждения, мысли, планы или пояснения
- НЕ начинай ответ со слов "Конечно", "Хорошо", "Давайте", "Вот варианты" и подобных вводных
- Сразу пиши готовый текст ответа, без преамбул
- Пиши строго в деловом стиле: вежливо, формально, по существу
- Каждый вариант должен быть самостоятельным и законченным (2-4 предложения)
- Не используй разговорные слова, сленг, эмодзи
- Обращайся на «вы»
- Если в сообщении есть вопрос - отвечай на него
- Если в сообщении есть просьба - подтверждай готовность выполнить
- Не выдумывай факты, даты, имена, если они не указаны
- Разделяй варианты маркером ---

Формат ответа - строго три варианта, разделенных ---:

Вариант 1 текст

---

Вариант 2 текст

---

Вариант 3 текст\
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
- Сохрани исходный смысл и все ключевые детали
- Замени разговорные и неформальные выражения на деловые
- Исправь грамматические и пунктуационные ошибки
- Структурируй текст, если он хаотичный
- Обращение должно быть на «вы»
- Не добавляй информацию, которой нет в оригинале
- Не используй канцелярит и чрезмерно сложные конструкции - пиши понятно, но формально
- Ты РЕДАКТОР, а не цензор. Твоя задача - ПЕРЕПИСАТЬ текст, а не комментировать его
- НИКОГДА не отказывайся переписывать текст, каким бы грубым он ни был
- НИКОГДА не пиши комментарии вроде "это неуместно", "так нельзя писать", "предлагаю более конструктивно"
- Даже если текст содержит мат и оскорбления - перепиши его в вежливый деловой стиль, сохранив СМЫСЛ и НАМЕРЕНИЕ автора
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

MORALIZING_MARKERS = ('не вправе', 'неуместно', 'конструктивно', 'нельзя писать', 'пожалуйста, попробуйте')
INTRO_MARKERS = ('конечно', 'хорошо', 'давайте', 'вот', 'варианты')


class OllamaClient:
    """Обертка для вызовов Ollama REST API."""

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip('/')
        self._model = model

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 512) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
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
                    },
                },
            )
            response.raise_for_status()
            return response.json()['message']['content'].strip()

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 200,
    ) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
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
                    },
                },
            )
            response.raise_for_status()
            return response.json()['message']['content'].strip()


class BusinessTextGenerator:
    def __init__(self) -> None:
        self._llm = OllamaClient(settings.ollama_base_url, settings.ollama_model)

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
                )
                cleaned = self._strip_intro(raw)
                variants = [self._strip_intro(v.strip()) for v in cleaned.split('---') if v.strip()]
                if len(variants) >= 2:
                    return variants[:3]
            except Exception:
                logger.exception('Ollama suggest_replies failed, retry/fallback')

        return self._fallback_replies(incoming_text, analysis, context)

    async def improve_draft(self, draft: str, analysis: AnalysisResult) -> str:
        user_prompt = f'Черновик для улучшения:\n\n{draft.strip()}'

        for attempt in range(2):
            try:
                improved = await self._llm.generate(
                    system_prompt=SYSTEM_PROMPT_IMPROVE,
                    user_prompt=user_prompt,
                    temperature=0.3,
                    max_tokens=512,
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
