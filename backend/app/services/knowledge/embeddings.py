from __future__ import annotations

import asyncio
from typing import Any, Protocol

_MODEL_NAME = "BAAI/bge-small-en-v1.5"


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class LocalSentenceTransformerEmbedder:
    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        self._model_name = model_name
        self._model = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return asyncio.run(self.embed_texts_async(texts))

    def embed_query(self, text: str) -> list[float]:
        return asyncio.run(self.embed_query_async(text))

    async def embed_texts_async(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._encode, texts)

    async def embed_query_async(self, text: str) -> list[float]:
        vectors = await self.embed_texts_async([text])
        return vectors[0] if vectors else []

    def _encode(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return [list(map(float, embedding)) for embedding in embeddings]

    def _load_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

            self._model = SentenceTransformer(self._model_name)
        return self._model
