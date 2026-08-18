"""
Embedding service using sentence-transformers.
Generates dense vector representations for RAG.
"""
import logging
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from backend.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Wraps sentence-transformers for local embedding generation."""

    def __init__(self):
        self._model: Optional[SentenceTransformer] = None

    def _load_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info("Embedding model loaded.")
        return self._model

    def embed(self, text: str) -> List[float]:
        """Embed a single text string."""
        model = self._load_model()
        return model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts."""
        model = self._load_model()
        return model.encode(texts, normalize_embeddings=True).tolist()


# Singleton (loaded lazily on first use)
embedding_service = EmbeddingService()
