import asyncio

import pytest

from app.generator import BusinessTextGenerator


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
def saved_models(monkeypatch) -> list[str]:
    saved: list[str] = []

    monkeypatch.setitem(BusinessTextGenerator.switch_model.__globals__, 'save_model', saved.append)

    return saved


@pytest.fixture
def cleared_models(monkeypatch) -> list[str]:
    cleared: list[str] = []

    def clear() -> None:
        cleared.append('cleared')

    monkeypatch.setitem(BusinessTextGenerator.cancel_loading_and_clear.__globals__, 'clear_saved_model', clear)

    return cleared


def make_generator(fake_llm: FakeOllamaClient) -> BusinessTextGenerator:
    generator = BusinessTextGenerator.__new__(BusinessTextGenerator)
    generator._llm = fake_llm
    generator._model_lock = asyncio.Lock()
    generator._model_loading = False
    generator._model_status = 'ready'
    generator._model_switch_task = None
    return generator


@pytest.mark.asyncio
async def test_switch_model_success_unloads_previous_sets_target_preloads_and_saves(saved_models):
    fake_llm = FakeOllamaClient('previous')
    generator = make_generator(fake_llm)

    await generator.switch_model('target')

    assert fake_llm.calls == [
        ('unload_model', 'previous'),
        ('set_model', 'target'),
        ('preload_model', 'target'),
    ]
    assert saved_models == ['target']
    assert generator.model == 'target'
    assert generator.model_status == 'Модель target готова'
    assert generator.model_loading is False


@pytest.mark.asyncio
async def test_switch_model_failed_preload_rolls_back_without_saving(saved_models):
    fake_llm = FakeOllamaClient('previous')
    fake_llm.fail_preload = True
    generator = make_generator(fake_llm)

    with pytest.raises(RuntimeError, match='preload failed'):
        await generator.switch_model('target')

    assert fake_llm.calls == [
        ('unload_model', 'previous'),
        ('set_model', 'target'),
        ('preload_model', 'target'),
        ('set_model', 'previous'),
    ]
    assert saved_models == []
    assert generator.model == 'previous'
    assert generator.model_status == 'Не удалось загрузить модель target'
    assert generator.model_loading is False


@pytest.mark.asyncio
async def test_unload_current_model_unloads_current_and_resets_loading():
    fake_llm = FakeOllamaClient('current')
    generator = make_generator(fake_llm)

    await generator.unload_current_model()

    assert fake_llm.calls == [('unload_model', 'current')]
    assert generator.model_status == 'Модель current выгружена'
    assert generator.model_loading is False


def test_ensure_ready_allows_ready_and_raises_current_status_when_loading():
    fake_llm = FakeOllamaClient('current')
    generator = make_generator(fake_llm)

    generator.ensure_ready()

    generator._model_loading = True
    generator._model_status = 'Загружается модель current'

    with pytest.raises(RuntimeError, match='Загружается модель current'):
        generator.ensure_ready()


@pytest.mark.asyncio
async def test_cancel_loading_and_clear_without_active_loading_unloads_current_and_clears(cleared_models):
    fake_llm = FakeOllamaClient('current')
    generator = make_generator(fake_llm)

    await generator.cancel_loading_and_clear()

    assert fake_llm.calls == [('unload_model', 'current')]
    assert cleared_models == ['cleared']
    assert generator.model_status == 'Загрузка остановлена, модель выгружена, выбор очищен'
    assert generator.model_loading is False
