import logging
import textwrap

import httpx

from app.config import settings
from app.schemas import AnalysisResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_REPLY = """\
Ты - корпоративный ассистент для деловой переписки на русском языке.

Твоя задача: на основе входящего сообщения сгенерировать ровно 3 варианта делового ответа.

Правила:
- Пиши ТОЛЬКО на русском языке. Никогда не вставляй слова и символы из других языков
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
Ты - корпоративный редактор деловой переписки на русском языке.

Твоя задача: переписать черновик в профессиональный деловой стиль.

Правила:
- Пиши ТОЛЬКО на русском языке. Никогда не вставляй слова и символы из других языков
- Сохрани исходный смысл и все ключевые детали
- Замени разговорные и неформальные выражения на деловые
- Исправь грамматические и пунктуационные ошибки
- Структурируй текст, если он хаотичный
- Обращение должно быть на «вы»
- Не добавляй информацию, которой нет в оригинале
- Не используй канцелярит и чрезмерно сложные конструкции - пиши понятно, но формально
- Верни ТОЛЬКО улучшенный текст, без пояснений и комментариев\
"""

SYSTEM_PROMPT_TAGS = """\
Ты - корпоративный аналитик переписки.

На основе текста диалога определи 2-5 коротких тегов на русском языке, описывающих тематику обращения.

Правила:
- Пиши ТОЛЬКО на русском языке
- Теги - это ключевые темы: «оплата», «доставка», «возврат», «техподдержка», «жалоба» и т.п.
- Каждый тег - одно-два слова
- Верни теги через запятую, без нумерации и пояснений\
"""


class OllamaClient:
    """Обертка для вызовов Ollama REST API."""

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip('/')
        self._model = model

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 512) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f'{self._base_url}/api/generate',
                json={
                    'model': self._model,
                    'system': system_prompt,
                    'prompt': user_prompt,
                    'stream': False,
                    'options': {
                        'temperature': temperature,
                        'top_p': 0.9,
                        'num_predict': max_tokens,
                    },
                },
            )
            response.raise_for_status()
            return response.json()['response'].strip()


class BusinessTextGenerator:
    def __init__(self) -> None:
        self._llm = OllamaClient(settings.ollama_base_url, settings.ollama_model)

    async def suggest_replies(self, incoming_text: str, analysis: AnalysisResult, context: str = '') -> list[str]:
        context_block = ''
        if context.strip():
            short_context = textwrap.shorten(context, width=300, placeholder='...')
            context_block = f'\n\nКонтекст предыдущего общения с клиентом:\n{short_context}'

        user_prompt = f'Входящее сообщение:{context_block}\n\n{incoming_text.strip()}'

        try:
            raw = await self._llm.generate(
                system_prompt=SYSTEM_PROMPT_REPLY,
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=600,
            )
            variants = [v.strip() for v in raw.split('---') if v.strip()]
            if len(variants) >= 2:
                return variants[:3]
        except Exception:
            logger.exception('Ollama suggest_replies failed, using fallback')

        return self._fallback_replies(incoming_text, analysis, context)

    async def improve_draft(self, draft: str, analysis: AnalysisResult) -> str:
        user_prompt = f'Черновик для улучшения:\n\n{draft.strip()}'

        try:
            improved = await self._llm.generate(
                system_prompt=SYSTEM_PROMPT_IMPROVE,
                user_prompt=user_prompt,
                temperature=0.4,
                max_tokens=512,
            )
            if len(improved) > 10:
                return improved
        except Exception:
            logger.exception('Ollama improve_draft failed, using fallback')

        return self._fallback_improve(draft)

    async def suggest_tags(self, conversation_text: str) -> list[str]:
        user_prompt = f'Текст диалога:\n\n{conversation_text[:4000]}'

        try:
            raw = await self._llm.generate(
                system_prompt=SYSTEM_PROMPT_TAGS,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=100,
            )
            tags = [t.strip().capitalize() for t in raw.split(',') if t.strip()]
            if tags:
                return tags[:5]
        except Exception:
            logger.exception('Ollama suggest_tags failed')

        return []

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
