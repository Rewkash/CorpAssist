import asyncio
import logging
from collections.abc import Callable
from typing import Any

from app.llm.model_store import clear_saved_model, save_model

logger = logging.getLogger(__name__)


class ModelLifecycleManager:
    def __init__(
        self,
        llm: Any,
        save_model_fn: Callable[[str], None] = save_model,
        clear_saved_model_fn: Callable[[], None] = clear_saved_model,
    ) -> None:
        self._llm = llm
        self._save_model = save_model_fn
        self._clear_saved_model = clear_saved_model_fn
        self._model_lock = asyncio.Lock()
        self._model_loading = False
        self._model_status = 'ready'
        self._model_switch_task: asyncio.Task[Any] | None = None

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
