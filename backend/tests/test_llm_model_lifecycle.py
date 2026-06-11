import pytest

from app.llm.model_lifecycle import ModelLifecycleManager


class FakeOllamaClient:
    def __init__(self, model: str = 'previous') -> None:
        self.model = model
        self.calls: list[tuple[str, str | None]] = []
        self.fail_preload = False

    def set_model(self, model: str) -> None:
        self.calls.append(('set_model', model))
        self.model = model

    async def unload_model(self, model: str) -> None:
        self.calls.append(('unload_model', model))

    async def preload_model(self, model: str) -> None:
        self.calls.append(('preload_model', model))
        if self.fail_preload:
            raise RuntimeError('preload failed')

    async def list_models(self) -> list[str]:
        self.calls.append(('list_models', None))
        return ['previous', 'target']


@pytest.fixture
def saved_models() -> list[str]:
    return []


@pytest.fixture
def cleared_models() -> list[str]:
    return []


def make_manager(
    fake_llm: FakeOllamaClient,
    saved_models: list[str] | None = None,
    cleared_models: list[str] | None = None,
) -> ModelLifecycleManager:
    saved = saved_models if saved_models is not None else []
    cleared = cleared_models if cleared_models is not None else []

    def clear() -> None:
        cleared.append('cleared')

    return ModelLifecycleManager(fake_llm, save_model_fn=saved.append, clear_saved_model_fn=clear)


@pytest.mark.asyncio
async def test_switch_model_success_unloads_previous_sets_target_preloads_and_saves(saved_models):
    fake_llm = FakeOllamaClient('previous')
    lifecycle = make_manager(fake_llm, saved_models=saved_models)

    await lifecycle.switch_model('target')

    assert fake_llm.calls == [
        ('unload_model', 'previous'),
        ('set_model', 'target'),
        ('preload_model', 'target'),
    ]
    assert saved_models == ['target']
    assert lifecycle.model == 'target'
    assert lifecycle.model_status == 'Модель target готова'
    assert lifecycle.model_loading is False


@pytest.mark.asyncio
async def test_switch_model_failed_preload_rolls_back_without_saving(saved_models):
    fake_llm = FakeOllamaClient('previous')
    fake_llm.fail_preload = True
    lifecycle = make_manager(fake_llm, saved_models=saved_models)

    with pytest.raises(RuntimeError, match='preload failed'):
        await lifecycle.switch_model('target')

    assert fake_llm.calls == [
        ('unload_model', 'previous'),
        ('set_model', 'target'),
        ('preload_model', 'target'),
        ('set_model', 'previous'),
    ]
    assert saved_models == []
    assert lifecycle.model == 'previous'
    assert lifecycle.model_status == 'Не удалось загрузить модель target'
    assert lifecycle.model_loading is False


@pytest.mark.asyncio
async def test_unload_current_model_unloads_current_and_resets_loading():
    fake_llm = FakeOllamaClient('current')
    lifecycle = make_manager(fake_llm)

    await lifecycle.unload_current_model()

    assert fake_llm.calls == [('unload_model', 'current')]
    assert lifecycle.model_status == 'Модель current выгружена'
    assert lifecycle.model_loading is False


def test_ensure_ready_allows_ready_and_raises_current_status_when_loading():
    fake_llm = FakeOllamaClient('current')
    lifecycle = make_manager(fake_llm)

    lifecycle.ensure_ready()

    lifecycle._model_loading = True
    lifecycle._model_status = 'Загружается модель current'

    with pytest.raises(RuntimeError, match='Загружается модель current'):
        lifecycle.ensure_ready()


@pytest.mark.asyncio
async def test_cancel_loading_and_clear_without_active_loading_unloads_current_and_clears(cleared_models):
    fake_llm = FakeOllamaClient('current')
    lifecycle = make_manager(fake_llm, cleared_models=cleared_models)

    await lifecycle.cancel_loading_and_clear()

    assert fake_llm.calls == [('unload_model', 'current')]
    assert cleared_models == ['cleared']
    assert lifecycle.model_status == 'Загрузка остановлена, модель выгружена, выбор очищен'
    assert lifecycle.model_loading is False
