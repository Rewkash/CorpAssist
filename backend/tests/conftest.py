import os
import sys
import types
from collections.abc import AsyncIterator
from importlib import import_module

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text


APP_MODULE_PREFIXES = (
    'app.main',
    'app.database',
    'app.config',
    'app.models',
    'app.deps',
    'app.auth',
    'app.routes',
    'app.services',
    'app.realtime',
    'app.generator',
    'app.nlp',
)


def _fake_sentiment_pipeline(*args, **kwargs):
    def analyze(text: str):
        return [{'label': 'neutral', 'score': 1.0}]

    return analyze


def _configure_test_environment() -> None:
    os.environ['POSTGRES_DB'] = 'corpassist_test'
    os.environ['POSTGRES_HOST'] = 'localhost'
    os.environ['POSTGRES_PORT'] = '5432'
    os.environ['POSTGRES_USER'] = 'corpassist'
    os.environ['POSTGRES_PASSWORD'] = 'corpassist'
    os.environ['JWT_SECRET'] = 'test-secret'
    os.environ.setdefault('OLLAMA_BASE_URL', 'http://localhost:11434')


def _install_fake_transformers() -> None:
    fake_transformers = types.ModuleType('transformers')
    fake_transformers.pipeline = _fake_sentiment_pipeline
    sys.modules['transformers'] = fake_transformers


def _clear_app_modules() -> None:
    for name in list(sys.modules):
        if name == 'app' or name.startswith('app.'):
            del sys.modules[name]


async def _clean_database(AsyncSessionLocal) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                'TRUNCATE TABLE chat_messages, conversations, message_history, users '
                'RESTART IDENTITY CASCADE'
            )
        )
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    _clear_app_modules()
    _configure_test_environment()
    _install_fake_transformers()

    database = import_module('app.database')
    main = import_module('app.main')

    try:
        async with main.app.router.lifespan_context(main.app):
            await _clean_database(database.AsyncSessionLocal)

            transport = ASGITransport(app=main.app)
            async with AsyncClient(transport=transport, base_url='http://testserver') as async_client:
                yield async_client
    finally:
        await database.engine.dispose()
        _clear_app_modules()
