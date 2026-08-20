"""
RAG Vector Store – modular abstraction over ChromaDB.
Swap the implementation here without touching the rest of the RAG pipeline.
"""
import logging
from typing import List, Dict, Any, Optional
from backend.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Modular vector store wrapper.
    Currently backed by ChromaDB with a persistent local directory.
    """

    def __init__(self):
        self._client: Any = None
        self._collection = None

    def _get_client(self):
        if self._client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            self._client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    def get_collection(self):
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def add_documents(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> None:
        """Add documents with pre-computed embeddings to the vector store."""
        col = self.get_collection()
        col.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info(f"Added {len(documents)} documents to vector store.")

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the top-N most similar documents.

        Returns:
            List of dicts with keys: document, metadata, distance, id.
        """
        col = self.get_collection()
        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = col.query(**kwargs)
        output = []
        for i, doc in enumerate(results["documents"][0]):
            output.append({
                "document": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "id": results["ids"][0][i],
            })
        return output

    def delete_by_metadata(self, where: Dict[str, Any]) -> None:
        """Delete documents matching a metadata filter."""
        col = self.get_collection()
        col.delete(where=where)

    def delete_by_ids(self, ids: List[str]) -> None:
        """Delete documents by their IDs."""
        col = self.get_collection()
        col.delete(ids=ids)

    def count(self) -> int:
        """Return total number of documents stored."""
        return self.get_collection().count()

    def reset(self) -> None:
        """WARNING: Clears the entire collection."""
        client = self._get_client()
        client.delete_collection(settings.CHROMA_COLLECTION_NAME)
        self._collection = None
        logger.warning("Vector store collection reset.")


# Singleton
vector_store = VectorStore()
