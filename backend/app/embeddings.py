import asyncio
import logging
from collections import OrderedDict

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaEmbeddings:
    """Клиент для эндпоинта /api/embeddings Ollama с in-memory LRU кэшем."""

    def __init__(self, base_url: str, model: str, dim: int, cache_size: int = 2048) -> None:
        self._base_url = base_url.rstrip('/')
        self._model = model
        self._dim = dim
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_size = cache_size
        self._lock = asyncio.Lock()

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model(self) -> str:
        return self._model

    def _cache_get(self, key: str) -> list[float] | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_put(self, key: str, value: list[float]) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    async def embed(self, text: str) -> list[float]:
        cleaned = text.strip()
        if not cleaned:
            return [0.0] * self._dim

        cached = self._cache_get(cleaned)
        if cached is not None:
            return cached

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f'{self._base_url}/api/embeddings',
                json={'model': self._model, 'prompt': cleaned},
            )
            response.raise_for_status()
            data = response.json()
        vector = data.get('embedding') or []
        if not isinstance(vector, list) or len(vector) != self._dim:
            raise RuntimeError(
                f'Ollama вернул эмбеддинг неожиданной размерности: '
                f'ожидали {self._dim}, получили {len(vector) if isinstance(vector, list) else type(vector).__name__}'
            )
        result = [float(x) for x in vector]
        async with self._lock:
            self._cache_put(cleaned, result)
        return result

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(t) for t in texts]


embeddings_service = OllamaEmbeddings(
    base_url=settings.ollama_base_url,
    model=settings.embedding_model,
    dim=settings.embedding_dim,
)
