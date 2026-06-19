import logging
from typing import Any
import textwrap

from app.config import settings
from app.llm.fallbacks import fallback_improve, fallback_replies
from app.llm.model_lifecycle import ModelLifecycleManager
from app.llm.model_store import load_saved_model
from app.llm.ollama_client import OllamaClient, get_llm_debug_log
from app.parsers.draft_improvement import is_acceptable_improvement
from app.parsers.llm_responses import parse_reply_variants, strip_intro
from app.parsers.tag_suggestions import empty_tag_suggestions, parse_tag_suggestions, tag_suggestion_schema
from app.prompts.llm_prompts import (
    SYSTEM_PROMPT_IMPROVE,
    SYSTEM_PROMPT_REPLY,
    SYSTEM_PROMPT_TAGS,
)
from app.schemas import AnalysisResult

logger = logging.getLogger(__name__)

class BusinessTextGenerator:
    def __init__(self) -> None:
        self._llm = OllamaClient(settings.ollama_base_url, load_saved_model())
        self._lifecycle = ModelLifecycleManager(self._llm)

    @property
    def model(self) -> str:
        return self._lifecycle.model

    def set_model(self, model: str) -> None:
        self._lifecycle.set_model(model)

    async def unload_current_model(self) -> None:
        await self._lifecycle.unload_current_model()

    @property
    def model_loading(self) -> bool:
        return self._lifecycle.model_loading

    @property
    def model_status(self) -> str:
        return self._lifecycle.model_status

    def ensure_ready(self) -> None:
        self._lifecycle.ensure_ready()

    async def switch_model(self, model: str) -> None:
        await self._lifecycle.switch_model(model)

    async def cancel_loading_and_clear(self) -> None:
        await self._lifecycle.cancel_loading_and_clear()

    async def list_models(self) -> list[str]:
        return await self._lifecycle.list_models()

    async def suggest_replies(self, incoming_text: str, analysis: AnalysisResult, context: str = '') -> list[str]:
        context_block = ''
        if context.strip():
            short_context = textwrap.shorten(context, width=1500, placeholder='...')
            context_block = f'Контекст общения с клиентом:\n{short_context}\n\n'

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
            context_block = f'Контекст общения с клиентом (для понимания темы и истории). Не переписывай его и не отвечай на него:\n{short_context}\n\n'

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
                if is_acceptable_improvement(improved):
                    return improved
                if attempt == 0:
                    user_prompt = f'{user_prompt}\n\nНапоминание: верни только переписанный текст без комментариев.'
            except Exception:
                logger.exception('Ollama improve_draft failed, retry/fallback')

        return fallback_improve(draft)

    async def suggest_tags(self, conversation_text: str) -> dict[str, Any]:
        user_prompt = f'Текст диалога:\n\n{conversation_text[:4000]}'

        for _ in range(2):
            try:
                raw = await self._llm.generate(
                    system_prompt=SYSTEM_PROMPT_TAGS,
                    user_prompt=user_prompt,
                    schema=tag_suggestion_schema(),
                    temperature=0.1,
                    max_tokens=200,
                    mode='suggest_tags',
                )
                return parse_tag_suggestions(raw)
            except Exception:
                logger.exception('Ollama suggest_tags failed, retry/fallback')

        return empty_tag_suggestions()

generator_service = BusinessTextGenerator()
